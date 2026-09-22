"""
Arriendo, señal de vida y turno exclusivo del recálculo masivo (N-5).

`scoring_jobs.status` decía qué se pretendía hacer, no qué estaba pasando. Un proceso que
moría a mitad del recorrido dejaba su fila en `RUNNING` para siempre: quien consultaba veía
un avance congelado que no distinguía de uno lento, y el sistema seguía creyendo que había
un recálculo vivo, de modo que ninguno nuevo podía empezar. No había nada que caducara.

Lo que se comprueba aquí:

* que un trabajo nace con arriendo y lo renueva **en cada lote**, no una sola vez;
* que al terminar —bien o mal— libera el turno;
* que un arriendo vencido se recoge, y uno vigente NO;
* que dos recálculos a la vez son imposibles, y que eso lo impone la BASE y no una
  comprobación previa, que sería una carrera.
"""
import datetime

import pytest
from app.models.entities import JobStatus, ScoringJob, utc_now
from app.services import recalculation_service as servicio
from app.services.recalculation_service import (
    CLAVE_DE_TURNO,
    MOTIVO_ARRIENDO_VENCIDO,
    RecalculoEnCurso,
    crear_trabajo_de_recalculo,
    liberar_arriendos_vencidos,
    recuperar_trabajos_huerfanos,
    trabajo_en_curso,
)
from sqlalchemy.exc import IntegrityError

URL_RECALCULO = "/api/v1/leads/batch/recalculate-all"
URL_TRABAJO = "/api/v1/leads/batch/jobs"


def _trabajo_vivo(db_session, *, vencido: bool = False, estado=JobStatus.RUNNING) -> ScoringJob:
    """
    Un trabajo que ocupa el turno, con el arriendo vigente o caducado según se pida.

    Se inserta a mano en lugar de lanzarlo por el endpoint porque el `TestClient` ejecuta
    las tareas de fondo antes de devolver el control: un trabajo lanzado así ya ha
    terminado y ha soltado el turno cuando la prueba llega a mirarlo.
    """
    ahora = utc_now()
    desplazamiento = (
        datetime.timedelta(minutes=-10) if vencido else datetime.timedelta(minutes=5)
    )
    trabajo = ScoringJob(
        id=f"trabajo-{'vencido' if vencido else 'vivo'}-de-prueba",
        job_type="RECALCULATE_ALL",
        status=estado.value,
        total_leads=500,
        processed_leads=120,
        failed_leads=0,
        batch_size=100,
        requested_by="test.lider@plurione.com",
        lease_key=CLAVE_DE_TURNO,
        lease_until=ahora + desplazamiento,
        heartbeat_at=ahora + desplazamiento,
        worker_id="contenedor-imaginario:99",
    )
    db_session.add(trabajo)
    db_session.commit()
    return trabajo


# ==============================================================================
# El arriendo existe y se renueva
# ==============================================================================

def test_el_trabajo_nace_con_turno_arriendo_y_dueno(db_session, sample_leads):
    """Sin estas cuatro columnas rellenas, nada de lo demás puede funcionar."""
    trabajo = crear_trabajo_de_recalculo(db_session, solicitado_por="quien.sea@plurione.com")

    assert trabajo.lease_key == CLAVE_DE_TURNO
    assert trabajo.lease_until is not None
    assert trabajo.heartbeat_at is not None
    assert trabajo.worker_id, "Sin worker_id no se sabe en qué contenedor mirar."


def test_el_arriendo_se_renueva_en_cada_lote_y_no_una_sola_vez(
    client, lead_headers, sample_leads, monkeypatch
):
    """
    La señal de vida tiene que ir pegada al progreso.

    Renovarla una vez al empezar convertiría el arriendo en un simple plazo desde el
    arranque: un recorrido largo lo agotaría trabajando, y otro proceso lo daría por
    muerto. Con seis prospectos en lotes de dos son tres vueltas, más la renovación
    inicial al pasar a RUNNING: cuatro.
    """
    renovaciones = []
    original = servicio._renovar_arriendo

    def contar(trabajo):
        renovaciones.append(trabajo.processed_leads)
        return original(trabajo)

    monkeypatch.setattr(servicio, "_renovar_arriendo", contar)

    client.post(URL_RECALCULO, json={"batch_size": 2}, headers=lead_headers)

    assert len(renovaciones) == 4, (
        f"Se esperaban 4 renovaciones (1 al arrancar + 3 lotes) y hubo {len(renovaciones)}: "
        f"{renovaciones}. Un arriendo que solo se renueva al empezar caduca trabajando."
    )
    # Y cada una llega con más trabajo hecho que la anterior: es lo que hace que la señal
    # de vida signifique «avanza» y no solo «el proceso existe».
    assert renovaciones == sorted(renovaciones)


def test_el_estado_publica_el_arriendo(client, lead_headers, sample_leads):
    """Quien consulta tiene que poder distinguir «lento» de «muerto» sin entrar a la base."""
    job_id = client.post(URL_RECALCULO, headers=lead_headers).json()["id"]
    estado = client.get(f"{URL_TRABAJO}/{job_id}", headers=lead_headers).json()

    assert "heartbeat_at" in estado
    assert "lease_until" in estado
    assert "worker_id" in estado
    assert estado["heartbeat_at"] is not None
    assert estado["worker_id"]


# ==============================================================================
# El turno se libera al terminar
# ==============================================================================

def test_el_trabajo_completado_suelta_el_turno(client, lead_headers, db_session, sample_leads):
    """
    Sin esto, el primer recálculo de la vida del sistema bloquearía todos los siguientes.

    Es el defecto que más fácil se cuela al implantar un turno: reservarlo y no soltarlo.
    """
    job_id = client.post(URL_RECALCULO, headers=lead_headers).json()["id"]

    db_session.expire_all()
    fila = db_session.query(ScoringJob).filter(ScoringJob.id == job_id).first()
    assert fila.status == JobStatus.COMPLETED.value
    assert fila.lease_key is None
    assert trabajo_en_curso(db_session) is None


def test_el_trabajo_fallido_tambien_suelta_el_turno(
    client, lead_headers, db_session, sample_leads, monkeypatch
):
    """
    Un recorrido que revienta debe dejar el turno libre.

    Es el caso que importa: si solo se soltara en la salida feliz, un único fallo dejaría
    el recálculo masivo inutilizado hasta el siguiente reinicio.
    """
    def consulta_rota(*args, **kwargs):
        raise RuntimeError("la base se cayó a mitad del recorrido")

    monkeypatch.setattr(servicio.ScoringService, "__init__", consulta_rota)

    job_id = client.post(URL_RECALCULO, headers=lead_headers).json()["id"]

    db_session.expire_all()
    fila = db_session.query(ScoringJob).filter(ScoringJob.id == job_id).first()
    assert fila.status == JobStatus.FAILED.value
    assert fila.lease_key is None


# ==============================================================================
# Uno a la vez
# ==============================================================================

def test_con_un_recalculo_vivo_el_segundo_recibe_409(client, lead_headers, db_session, sample_leads):
    _trabajo_vivo(db_session)

    respuesta = client.post(URL_RECALCULO, headers=lead_headers)

    assert respuesta.status_code == 409


def test_el_409_dice_cual_es_el_trabajo_que_ocupa_el_turno(
    client, lead_headers, db_session, sample_leads
):
    """
    «Inténtelo más tarde» obliga a ir a buscar cuál es. El conflicto ya lo sabe.

    Se devuelve el identificador y el avance para que quien lo pidió decida si esperar o si
    lo que hay atascado es un trabajo que conviene mirar.
    """
    vivo = _trabajo_vivo(db_session)

    detalle = client.post(URL_RECALCULO, headers=lead_headers).json()["detail"]

    assert detalle["job_id"] == vivo.id
    assert detalle["procesados"] == 120
    assert detalle["total"] == 500
    assert detalle["solicitado_por"] == "test.lider@plurione.com"


def test_el_409_no_crea_un_trabajo_de_mas(client, lead_headers, db_session, sample_leads):
    """Un conflicto no debe dejar filas huérfanas en la tabla."""
    _trabajo_vivo(db_session)
    antes = db_session.query(ScoringJob).count()

    client.post(URL_RECALCULO, headers=lead_headers)

    db_session.expire_all()
    assert db_session.query(ScoringJob).count() == antes


def test_el_turno_lo_impone_la_base_y_no_el_codigo(db_session, sample_leads):
    """
    La exclusión tiene que estar en el índice único, no solo en el `if` de arriba.

    Entre «no hay ninguno activo» y el INSERT caben dos peticiones simultáneas: con dos
    workers eso no es una hipótesis, es lo que pasa cuando alguien pulsa dos veces el
    botón. Aquí se saltan las comprobaciones del servicio a propósito e se insertan dos
    filas con el mismo turno directamente contra la base.
    """
    _trabajo_vivo(db_session)

    intruso = ScoringJob(
        id="segundo-que-intenta-el-mismo-turno",
        job_type="RECALCULATE_ALL",
        status=JobStatus.PENDING.value,
        total_leads=1,
        processed_leads=0,
        failed_leads=0,
        batch_size=100,
        lease_key=CLAVE_DE_TURNO,
        lease_until=utc_now() + datetime.timedelta(minutes=5),
    )
    db_session.add(intruso)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_el_servicio_levanta_recalculo_en_curso(db_session, sample_leads):
    """La excepción lleva el trabajo consigo: quien la atienda no tiene que ir a buscarlo."""
    vivo = _trabajo_vivo(db_session)

    with pytest.raises(RecalculoEnCurso) as capturada:
        crear_trabajo_de_recalculo(db_session)

    assert capturada.value.trabajo.id == vivo.id


# ==============================================================================
# El arriendo caduca solo
# ==============================================================================

def test_un_arriendo_vencido_deja_pasar_al_siguiente(client, lead_headers, db_session, sample_leads):
    """
    Un trabajo cuyo proceso ya no existe no debe bloquear el sistema hasta que alguien
    reinicie la pila. Al intentar crear uno nuevo se recogen primero los muertos.
    """
    muerto = _trabajo_vivo(db_session, vencido=True)

    respuesta = client.post(URL_RECALCULO, headers=lead_headers)
    assert respuesta.status_code == 202

    db_session.expire_all()
    cerrado = db_session.query(ScoringJob).filter(ScoringJob.id == muerto.id).first()
    assert cerrado.status == JobStatus.FAILED.value
    assert cerrado.lease_key is None
    assert cerrado.finished_at is not None
    assert "Arriendo vencido" in (cerrado.error_message or "")


def test_el_barrido_cierra_los_huerfanos(db_session, sample_leads):
    muerto = _trabajo_vivo(db_session, vencido=True)

    cerrados = liberar_arriendos_vencidos(db_session)

    assert cerrados == [muerto.id]
    db_session.expire_all()
    assert db_session.query(ScoringJob).filter(ScoringJob.id == muerto.id).first().status == (
        JobStatus.FAILED.value
    )


def test_el_barrido_respeta_un_arriendo_vigente(db_session, sample_leads):
    """
    Reiniciar un worker no autoriza a dar por muerto lo que otra instancia ejecuta.

    Es la mitad del mecanismo que se olvida: un barrido que cierra todo lo que encuentra en
    RUNNING mata recálculos sanos cada vez que se despliega.
    """
    vivo = _trabajo_vivo(db_session)

    assert liberar_arriendos_vencidos(db_session) == []

    db_session.expire_all()
    intacto = db_session.query(ScoringJob).filter(ScoringJob.id == vivo.id).first()
    assert intacto.status == JobStatus.RUNNING.value
    assert intacto.lease_key == CLAVE_DE_TURNO


def test_un_trabajo_sin_arriendo_cuenta_como_vencido(db_session, sample_leads):
    """
    Las filas anteriores a la migración tienen `lease_until` a NULL.

    Si el NULL se leyera como «vigente para siempre», un trabajo viejo colgado en RUNNING
    bloquearía el turno de forma permanente: justo el defecto que el arriendo viene a
    cerrar, reintroducido por la propia migración.
    """
    antiguo = ScoringJob(
        id="trabajo-anterior-a-la-migracion",
        job_type="RECALCULATE_ALL",
        status=JobStatus.RUNNING.value,
        total_leads=10,
        processed_leads=3,
        failed_leads=0,
        batch_size=100,
        lease_key=CLAVE_DE_TURNO,
        lease_until=None,
    )
    db_session.add(antiguo)
    db_session.commit()

    assert liberar_arriendos_vencidos(db_session) == [antiguo.id]


def test_el_barrido_no_toca_los_trabajos_ya_terminados(db_session, sample_leads):
    """Un COMPLETED sin arriendo no es un huérfano: es un trabajo hecho."""
    terminado = ScoringJob(
        id="trabajo-terminado-hace-tiempo",
        job_type="RECALCULATE_ALL",
        status=JobStatus.COMPLETED.value,
        total_leads=10,
        processed_leads=10,
        failed_leads=0,
        batch_size=100,
        finished_at=utc_now(),
    )
    db_session.add(terminado)
    db_session.commit()

    assert liberar_arriendos_vencidos(db_session) == []
    db_session.expire_all()
    assert db_session.query(ScoringJob).filter(ScoringJob.id == terminado.id).first().status == (
        JobStatus.COMPLETED.value
    )


def test_el_barrido_de_arranque_usa_su_propia_sesion(db_session, sample_leads):
    """
    `recuperar_trabajos_huerfanos` es lo que llama el `lifespan`, donde no hay ninguna
    sesión de petición de la que colgarse: tiene que abrirla y cerrarla él.
    """
    muerto = _trabajo_vivo(db_session, vencido=True)

    from app.core.database import SessionLocal

    cerrados = recuperar_trabajos_huerfanos(session_factory=SessionLocal)

    assert muerto.id in cerrados


def test_el_motivo_del_cierre_explica_que_hacer(db_session, sample_leads):
    """
    El mensaje que queda en `error_message` lo lee quien encuentra el trabajo en FAILED.

    Decir solo «fallido» obliga a esa persona a averiguar por su cuenta si el recálculo
    llegó a hacer algo y si puede relanzarlo.
    """
    assert "vuelva a lanzarlo" in MOTIVO_ARRIENDO_VENCIDO
    _trabajo_vivo(db_session, vencido=True)
    liberar_arriendos_vencidos(db_session)

    fila = db_session.query(ScoringJob).filter(
        ScoringJob.status == JobStatus.FAILED.value
    ).first()
    assert fila.error_message == MOTIVO_ARRIENDO_VENCIDO
