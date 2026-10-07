"""
Las carreras y los desastres de dos piezas que corren solas: la ingesta y el recálculo.

Las dos tienen en común lo que las hace difíciles de probar: **lo que las protege solo
ocurre cuando hay dos a la vez, o cuando algo ya ha fallado**. Un `except` de último recurso
y una comprobación que pierde la carrera no se recorren con una petición ordenada, y lo que
no se recorre está escrito pero no comprobado.

Lo que se cubre aquí:

* **El registro de entregas de webhook**: la fila caducada que hay que retirar para que la
  entrega nueva pueda escribirse, y la purga que no puede tumbar la ingesta que la lanzó.
* **El turno del recálculo**: la carrera que el índice único resuelve cuando dos peticiones
  pasan juntas la comprobación previa, las dos formas de contestarla, el barrido de arranque
  que falla, y el trabajo que ya no está cuando se va a ejecutar.

Las carreras se provocan **sin tocar la guarda que se prueba**: la fila que compite se mete
en el hueco entre la comprobación y el `INSERT`, desde otra sesión y a través de una función
que se llama justo ahí. Eso es exactamente lo que hace otra petición simultánea, y es el
mismo procedimiento que usa `test_la_red_del_alta_de_una_cuenta_contesta_el_conflicto_del_correo`.
"""
import datetime
import logging
import uuid

import pytest
from app.models.entities import JobStatus, ScoringJob, WebhookDelivery, utc_now
from app.services import recalculation_service, webhook_dedup
from app.services.recalculation_service import (
    CLAVE_DE_TURNO,
    DURACION_DEL_ARRIENDO,
    RecalculoEnCurso,
    crear_trabajo_de_recalculo,
)
from app.services.webhook_dedup import EntregaRepetida, EntregaYaAtendida, verificar_entrega

# ==============================================================================
# Las dos mitades de `_aware`, que son las dos mitades de dos motores
# ==============================================================================

@pytest.mark.parametrize("modulo", [webhook_dedup, recalculation_service],
                         ids=["webhook_dedup", "recalculation_service"])
def test_un_instante_sin_zona_se_lee_en_utc_y_uno_con_zona_se_deja(modulo):
    """
    Las dos copias de `_aware`, y las dos salidas de cada una.

    No es una función de adorno: es la que hace que estos dos servicios funcionen igual en
    la suite y en producción. SQLite devuelve los instantes **sin** zona y PostgreSQL
    **con** ella, así que la rama que no se recorre en las pruebas es justo la que corre en
    el servidor —o al revés—. Compararlos sin reponer la zona no es una comparación que
    salga mal: es un `TypeError` que revienta el barrido, que es la peor forma de tenerlo.

    Todo lo que se guarda está en UTC, así que reponer la zona es exacto y no una
    suposición.
    """
    sin_zona = datetime.datetime(2026, 10, 7, 12, 0)
    con_zona = datetime.datetime(2026, 10, 7, 12, 0, tzinfo=datetime.timezone.utc)

    assert modulo._aware(sin_zona) == con_zona
    assert modulo._aware(sin_zona).tzinfo is datetime.timezone.utc
    # Uno que ya la trae se devuelve tal cual, sin volver a ponerle nada.
    assert modulo._aware(con_zona) is con_zona


def test_el_registro_de_entregas_admite_que_no_haya_instante():
    """`_aware(None)` es None: un campo opcional que no viene no es un error."""
    assert webhook_dedup._aware(None) is None
    assert recalculation_service._aware(None) is None


# ==============================================================================
# El registro de entregas: la fila caducada que estorba
# ==============================================================================

def _entrega(db, *, firma, clave, vence_en):
    entrega = WebhookDelivery(
        signature=firma,
        idempotency_key=clave,
        crm_platform="hubspot",
        event="lead.updated",
        external_lead_id="EXT-1",
        response_data={"estado": "ok"},
        received_at=utc_now() - datetime.timedelta(hours=2),
        expires_at=vence_en,
    )
    db.add(entrega)
    db.commit()
    return entrega


def test_una_entrega_vigente_con_la_misma_firma_se_rechaza(db_session):
    """La mitad conocida, para tener las dos al lado: dentro de la ventana, es repetida."""
    firma, clave = uuid.uuid4().hex, uuid.uuid4().hex
    _entrega(db_session, firma=firma, clave=clave, vence_en=utc_now() + datetime.timedelta(hours=1))

    with pytest.raises(EntregaRepetida):
        verificar_entrega(db_session, signature=firma, idempotency_key=clave)


def test_una_entrega_vigente_con_la_misma_clave_devuelve_la_respuesta_original(db_session):
    """Firma distinta y clave igual: no es un reenvío, es el mismo evento otra vez."""
    clave = uuid.uuid4().hex
    _entrega(db_session, firma=uuid.uuid4().hex, clave=clave,
             vence_en=utc_now() + datetime.timedelta(hours=1))

    with pytest.raises(EntregaYaAtendida) as repetida:
        verificar_entrega(db_session, signature=uuid.uuid4().hex, idempotency_key=clave)

    assert repetida.value.response_data == {"estado": "ok"}
    assert repetida.value.recibida_en.tzinfo is not None


def test_una_fila_caducada_con_la_misma_firma_se_retira_para_dejar_sitio(db_session):
    """
    Pasada la ventana, la fila vieja no rechaza nada: estorba, y hay que quitarla.

    Las dos columnas son únicas, así que una fila muerta con esa firma impediría registrar
    la entrega nueva —un `IntegrityError` en la ingesta, no un rechazo educado—. El camino
    que la retira no lo recorría ninguna prueba: para llegar aquí hace falta una fila ya
    vencida, y la suite siempre las creaba vigentes.
    """
    firma, clave = uuid.uuid4().hex, uuid.uuid4().hex
    _entrega(db_session, firma=firma, clave=clave, vence_en=utc_now() - datetime.timedelta(minutes=1))
    assert db_session.query(WebhookDelivery).filter(WebhookDelivery.signature == firma).count() == 1

    # No levanta nada: la entrega nueva puede seguir.
    verificar_entrega(db_session, signature=firma, idempotency_key=clave)

    assert db_session.query(WebhookDelivery).filter(WebhookDelivery.signature == firma).count() == 0


def test_una_fila_caducada_con_la_misma_clave_tambien_se_retira(db_session):
    """Lo mismo por la otra columna única, que se consulta aparte y se borra aparte."""
    clave = uuid.uuid4().hex
    _entrega(db_session, firma=uuid.uuid4().hex, clave=clave,
             vence_en=utc_now() - datetime.timedelta(minutes=1))

    verificar_entrega(db_session, signature=uuid.uuid4().hex, idempotency_key=clave)

    assert db_session.query(WebhookDelivery).filter(WebhookDelivery.idempotency_key == clave).count() == 0


def test_sin_ninguna_fila_que_estorbar_no_se_borra_ni_se_vacia_nada(db_session):
    """
    La otra salida: no hay nada que retirar, así que no se vacía la sesión.

    Es la diferencia entre «no hay fila» y «hay una muerta», y el `flush` solo corresponde
    al segundo caso: vaciar la sesión por si acaso escribiría en la base cosas a medias de
    la petición que está en curso.
    """
    antes = db_session.query(WebhookDelivery).count()

    verificar_entrega(db_session, signature=uuid.uuid4().hex, idempotency_key=uuid.uuid4().hex)

    assert db_session.query(WebhookDelivery).count() == antes


def test_la_purga_de_entregas_caducadas_borra_solo_las_vencidas(db_session):
    """Housekeeping: se van las vencidas y se queda la vigente."""
    vencida = uuid.uuid4().hex
    vigente = uuid.uuid4().hex
    _entrega(db_session, firma=vencida, clave=vencida, vence_en=utc_now() - datetime.timedelta(minutes=1))
    _entrega(db_session, firma=vigente, clave=vigente, vence_en=utc_now() + datetime.timedelta(hours=1))

    # `forzar` porque la purga se limita a una cada cierto tiempo: sin él, el cero o el uno
    # dependerian de si otra prueba la llamo hace poco.
    borradas = webhook_dedup.purgar_entregas_caducadas(db_session, forzar=True)

    assert borradas >= 1
    assert db_session.query(WebhookDelivery).filter(WebhookDelivery.signature == vencida).count() == 0
    assert db_session.query(WebhookDelivery).filter(WebhookDelivery.signature == vigente).count() == 1


def test_una_purga_que_falla_no_tumba_la_ingesta_que_la_lanzo(db_session, monkeypatch, caplog):
    """
    La purga es housekeeping: que falle no puede hacer fracasar la ingesta que la disparó.

    Se llama al final de una entrega que ya se atendió, así que propagar su error
    convertiría una ingesta correcta en un 500 por no haber podido borrar filas viejas. El
    `except` devuelve 0, deja el apunte y la ingesta sigue; sin probarlo, nadie sabe si de
    verdad devuelve 0 o si el error sale por arriba.

    Va con `forzar=True` a propósito: la purga se limita a una cada
    `CRM_DEDUP_PURGE_INTERVAL_SECONDS`, y sin forzarla este cero podría venir del reloj y no
    del `except`. Una prueba que no distingue las dos formas de devolver cero no comprueba
    ninguna.
    """
    def revienta(*_args, **_kwargs):
        raise RuntimeError("la base se cayó a mitad del borrado")

    monkeypatch.setattr(db_session, "query", revienta)

    with caplog.at_level(logging.ERROR):
        assert webhook_dedup.purgar_entregas_caducadas(db_session, forzar=True) == 0

    assert any("purgar" in registro.message for registro in caplog.records)


# ==============================================================================
# El turno del recálculo: la carrera que resuelve el índice único
# ==============================================================================

def _ocupar_el_turno(db_session):
    """Otra petición que gana el turno, escrita desde una sesión que no es la nuestra."""
    ahora = utc_now()
    competidor = ScoringJob(
        id=str(uuid.uuid4()),
        job_type="RECALCULATE_ALL",
        status=JobStatus.PENDING.value,
        total_leads=0,
        processed_leads=0,
        failed_leads=0,
        batch_size=100,
        requested_by="la-otra-peticion@plurione.com",
        lease_key=CLAVE_DE_TURNO,
        lease_until=ahora + DURACION_DEL_ARRIENDO,
        heartbeat_at=ahora,
        worker_id="worker-de-al-lado",
    )
    db_session.add(competidor)
    db_session.commit()
    return competidor


def test_el_turno_ocupado_se_contesta_sin_llegar_al_motor(db_session):
    """La mitad conocida: la comprobación previa existe para dar un mensaje útil."""
    ocupado = _ocupar_el_turno(db_session)

    with pytest.raises(RecalculoEnCurso) as conflicto:
        crear_trabajo_de_recalculo(db_session, solicitado_por="yo@plurione.com")

    assert conflicto.value.trabajo.id == ocupado.id


def test_dos_peticiones_que_pasan_juntas_la_comprobacion_las_separa_el_indice(
    db_session, monkeypatch
):
    """
    La carrera de verdad, provocada sin tocar la guarda que la resuelve.

    Entre «no hay ninguno activo» y el `INSERT` caben dos peticiones, y con dos workers de
    uvicorn eso no es una hipótesis: es lo que pasa cuando alguien pulsa dos veces el botón.
    Lo que impide el segundo recorrido completo de la cartera no es la comprobación previa
    —esa solo da el mensaje— sino el índice único sobre `lease_key`.

    La fila que compite se mete **en el hueco**, a través de `identificador_de_worker`, que
    se llama al construir el `ScoringJob`, o sea justo entre la comprobación y el `commit`.
    Si el índice no estuviera, los dos trabajos quedarían con el turno y la cartera entera
    se recorrería dos veces a la vez, escribiendo scores uno encima del otro.
    """
    original = recalculation_service.identificador_de_worker
    metida = {}

    def entra_otro_en_el_hueco():
        if not metida:
            metida["competidor"] = _ocupar_el_turno(db_session)
        return original()

    monkeypatch.setattr(
        recalculation_service, "identificador_de_worker", entra_otro_en_el_hueco
    )
    # La comprobación previa no ve nada: todavía no hay fila.
    assert recalculation_service.trabajo_en_curso(db_session) is None

    with pytest.raises(RecalculoEnCurso) as conflicto:
        crear_trabajo_de_recalculo(db_session, solicitado_por="yo@plurione.com")

    assert metida, "la fila que compite tiene que haberse metido en el hueco"
    # Se contesta nombrando al que ganó, no al nuestro: quien reintenta tiene que poder
    # consultar el trabajo que de verdad está corriendo.
    assert conflicto.value.trabajo.id == metida["competidor"].id
    assert db_session.query(ScoringJob).filter(ScoringJob.lease_key == CLAVE_DE_TURNO).count() == 1


def test_si_el_ganador_de_la_carrera_termina_antes_de_mirarlo_se_contesta_igual(
    db_session, monkeypatch
):
    """
    Raro pero posible: el que ganó la carrera acabó entre el rechazo y la consulta.

    Entonces no hay a quién nombrar, y la respuesta sigue siendo conflicto: reintentar
    continúa siendo lo correcto, y contestar 201 sobre un trabajo que el motor acaba de
    rechazar entregaría un identificador que no existe en la base.

    `trabajo_en_curso` se hace fallar **una sola vez**, en la consulta de después del
    rechazo, para no tocar la guarda: la comprobación previa sigue viendo lo que vería de
    verdad.
    """
    original_worker = recalculation_service.identificador_de_worker
    original_en_curso = recalculation_service.trabajo_en_curso
    llamadas = {"en_curso": 0}
    metida = {}

    def entra_otro_en_el_hueco():
        if not metida:
            metida["competidor"] = _ocupar_el_turno(db_session)
        return original_worker()

    def en_curso_que_pierde_al_ganador(db):
        llamadas["en_curso"] += 1
        # La primera es la comprobación previa; la segunda, la de después del rechazo.
        if llamadas["en_curso"] >= 2:
            return None
        return original_en_curso(db)

    monkeypatch.setattr(recalculation_service, "identificador_de_worker", entra_otro_en_el_hueco)
    monkeypatch.setattr(recalculation_service, "trabajo_en_curso", en_curso_que_pierde_al_ganador)

    with pytest.raises(RecalculoEnCurso) as conflicto:
        crear_trabajo_de_recalculo(db_session, solicitado_por="yo@plurione.com")

    assert llamadas["en_curso"] >= 2
    # Se nombra el nuestro, que es lo único que hay: no se inventa un ganador.
    assert conflicto.value.trabajo.requested_by == "yo@plurione.com"


def test_el_barrido_de_arranque_que_falla_no_impide_arrancar(monkeypatch, caplog):
    """
    Corre en cada worker de uvicorn al arrancar, y es lo último que puede impedir arrancar.

    Si la base no está lista todavía —el orden de los contenedores— este barrido falla, y
    propagarlo mataría el worker en el arranque: la aplicación no levantaría por no haber
    podido limpiar trabajos de una ejecución anterior. Devuelve la lista vacía, deja el
    apunte y la aplicación sigue.
    """
    class SesionQueNoSirve:
        def __init__(self):
            self.devuelta = False

        def query(self, *_a, **_k):
            raise RuntimeError("la base todavía no acepta conexiones")

        def rollback(self):
            pass

        def close(self):
            self.devuelta = True

    sesion = SesionQueNoSirve()

    with caplog.at_level(logging.ERROR):
        assert recalculation_service.recuperar_trabajos_huerfanos(lambda: sesion) == []

    assert sesion.devuelta, "la sesión se devuelve al pool aunque el barrido falle"
    assert any("huérfanos" in r.message or "huerfanos" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_un_recalculo_cuyo_trabajo_ya_no_esta_no_hace_nada(db_session, caplog):
    """
    El trabajo se busca por su identificador, y puede no estar.

    `ejecutar_recalculo` corre **después** de la respuesta 202, en una tarea de fondo y con
    su propia sesión. Entre una cosa y la otra la fila puede haber desaparecido —una purga,
    una base restaurada, un identificador inventado a mano—. Sin la comprobación, la
    siguiente línea sería un atributo de `None`: una traza en los registros de un proceso
    que nadie está mirando, que es la peor forma de fallar.

    El arnes corrigio esta prueba. La primera version solo comprobaba que el identificador
    apareciera en algun apunte, y neutralizar la comprobacion NO la ponia roja: sin ella el
    `None` revienta dos lineas mas abajo, el `except` de arriba lo recoge y escribe «el
    recalculo <id> se interrumpio», que tambien lleva el identificador dentro. Los dos
    caminos dejaban un apunte con el mismo texto buscado, asi que la prueba no distinguia
    «no existe» de «existe y revento»: ahora exige el mensaje que corresponde y la AUSENCIA
    del otro.
    """
    inventado = str(uuid.uuid4())

    with caplog.at_level(logging.ERROR):
        await recalculation_service.ejecutar_recalculo(inventado, session_factory=lambda: db_session)

    mensajes = [r.message for r in caplog.records]
    assert any("no encontrado" in m and inventado in m for m in mensajes)
    # Y no se intento ejecutar nada: eso habria dejado el apunte de la interrupcion.
    assert not any("se interrumpió" in m for m in mensajes)


def _un_trabajo(db_session):
    """Un trabajo de recalculo en la base, listo para ejecutarse."""
    ahora = utc_now()
    trabajo = ScoringJob(
        id=str(uuid.uuid4()),
        job_type="RECALCULATE_ALL",
        status=JobStatus.PENDING.value,
        total_leads=0,
        processed_leads=0,
        failed_leads=0,
        batch_size=100,
        requested_by="quien.lo.pidio@plurione.com",
        lease_key=CLAVE_DE_TURNO,
        lease_until=ahora + DURACION_DEL_ARRIENDO,
        heartbeat_at=ahora,
        worker_id="worker-de-la-prueba",
    )
    db_session.add(trabajo)
    db_session.commit()
    return trabajo


@pytest.mark.asyncio
async def test_un_recalculo_que_se_interrumpe_queda_marcado_como_fallido(db_session, monkeypatch):
    """
    La mitad que funciona, para tener al lado la que no: el trabajo queda en FAILED.

    El estado del trabajo es lo unico que ve quien lo lanzo —la respuesta fue un 202 con un
    identificador—, asi que un recalculo que se interrumpe y se queda en RUNNING para
    siempre ocupa el turno hasta que vence el arriendo y no le dice nada a nadie.
    """
    # El identificador se guarda aparte: `ejecutar_recalculo` cierra la sesion en su
    # `finally`, y despues de eso el objeto esta desprendido y leerle un atributo es un
    # `DetachedInstanceError`.
    identificador = _un_trabajo(db_session).id

    class ServicioQueNoArranca:
        def __init__(self, _db):
            raise RuntimeError("el modelo no se pudo cargar")

    monkeypatch.setattr(recalculation_service, "ScoringService", ServicioQueNoArranca)

    await recalculation_service.ejecutar_recalculo(
        identificador, session_factory=lambda: db_session
    )

    db_session.expire_all()
    vuelto = db_session.query(ScoringJob).filter(ScoringJob.id == identificador).one()
    assert vuelto.status == JobStatus.FAILED.value
    assert "no se pudo cargar" in (vuelto.error_message or "")
    # Y suelta el turno: si no, el siguiente recalculo recibiria 409 hasta que venciera.
    assert vuelto.lease_key is None


@pytest.mark.asyncio
async def test_un_trabajo_que_desaparece_mientras_falla_no_se_marca_a_nada(
    db_session, monkeypatch, caplog
):
    """
    El trabajo ya no esta cuando se le va a escribir el fallo. No hay nada que marcar.

    Pasa de verdad: `ejecutar_recalculo` corre despues de la respuesta en una tarea de
    fondo, y entre la interrupcion y el `rollback` cabe una purga o una base restaurada.
    Sin la comprobacion, la linea siguiente seria un atributo de `None` DENTRO del manejador
    de errores, o sea un fallo al registrar un fallo: la causa original se perderia y lo que
    quedaria en los registros seria la traza de otra cosa.

    Se provoca haciendo que el trabajo se borre en el mismo hueco en que el recalculo se
    rompe, que es el orden en que ocurriria.
    """
    trabajo = _un_trabajo(db_session)
    identificador = trabajo.id

    class ServicioQueSeLlevaElTrabajo:
        def __init__(self, db):
            db.query(ScoringJob).filter(ScoringJob.id == identificador).delete()
            db.commit()
            raise RuntimeError("se cayo la conexion a mitad")

    monkeypatch.setattr(recalculation_service, "ScoringService", ServicioQueSeLlevaElTrabajo)

    with caplog.at_level(logging.ERROR):
        await recalculation_service.ejecutar_recalculo(
            identificador, session_factory=lambda: db_session
        )

    assert db_session.query(ScoringJob).filter(ScoringJob.id == identificador).count() == 0
    # Queda el apunte de la causa original, y NO el de «ademas no se pudo marcar».
    assert any("se interrumpió" in r.message for r in caplog.records)
    assert not any("no se pudo marcar como fallido" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_si_tampoco_se_puede_marcar_el_fallo_queda_dicho_y_no_se_propaga(
    db_session, monkeypatch, caplog
):
    """
    El `except` de ultimo recurso: ni siquiera se pudo escribir que habia fallado.

    Es el unico camino del servicio que no puede dejar ningun rastro en la base, porque la
    base es justo lo que no responde. Entonces el rastro tiene que quedar en los registros,
    con los DOS apuntes —la causa original y el «ademas»—, y la excepcion no puede salir de
    aqui: esto corre en una tarea de fondo de FastAPI, y lo que sube desde ahi no tiene a
    nadie a quien contestarle.

    Sin probarlo, nadie sabe si de verdad no se propaga. Un `raise` que se escapara de una
    tarea de fondo se registraria como «Task exception was never retrieved» y la causa
    original —la de verdad— no aparece en ese mensaje.
    """
    identificador = _un_trabajo(db_session).id

    class ServicioQueNoArranca:
        def __init__(self, _db):
            raise RuntimeError("el motor de puntuacion no responde")

    def tampoco_se_puede_cerrar(*_a, **_k):
        raise RuntimeError("la base sigue sin responder")

    monkeypatch.setattr(recalculation_service, "ScoringService", ServicioQueNoArranca)
    monkeypatch.setattr(recalculation_service, "_cerrar", tampoco_se_puede_cerrar)

    with caplog.at_level(logging.ERROR):
        # No levanta: es lo que esta prueba comprueba antes que nada.
        await recalculation_service.ejecutar_recalculo(
            identificador, session_factory=lambda: db_session
        )

    mensajes = [r.message for r in caplog.records]
    assert any("se interrumpió" in m for m in mensajes), "la causa original"
    assert any("no se pudo marcar como fallido" in m for m in mensajes), "y el ademas"
