"""
Los bordes que quedaban: validadores, saneadores, la lista de filtradas y tres contadores.

Lo último de la cola. Son nueve archivos con cuatro o cinco huecos cada uno, y lo que los
junta aquí es que **todos reciben algo de fuera y deciden qué hacer con lo que no cuadra**:
un formulario del panel, la carga de un CRM ajeno, la respuesta de un modelo de lenguaje,
una contraseña escrita por una persona. Ninguno de esos caminos lo recorre una petición
correcta, que es por lo que estaban sin probar; y todos fallan hacia el mismo lado, que es
**aceptar**.

Lo que se cubre, por si sirve de mapa:

* **`schemas/activity.py`**: la fecha de una reunión agendada, con y sin zona, y en pasado.
* **`schemas/desenlaces.py`**: un tramo de acuerdo que no está en la lista.
* **`crm_service.py`**: una fecha ilegible del CRM, y el apunte del fallo que también falla.
* **`retencion_service.py`**: el lote vacío, el lote que cambió debajo, y el `raise` que
  sube después de deshacer.
* **`prompt_safety.py`**: lo que llega del modelo cuando no tiene la forma prometida.
* **`core/passwords.py`**: la lista de contraseñas filtradas que no se puede leer o que no
  cuadra con su manifiesto.
* **`endpoints/campaigns.py`**: la edición vacía y el cambio de responsable.
* **`scoring_service.py`**: dos tipos de actividad que nadie contaba.
* **`adapters/base.py`**: la versión de motor que declara un adaptador que no la declara.
"""
import datetime
import gzip
import hashlib
import json
import logging
import uuid

import pytest
from app.adapters import prompt_safety
from app.adapters.base import BaseMLScoringAdapter
from app.core import passwords
from app.models.entities import ActivityType

LIMITE = datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc)

# ==============================================================================
# adapters/base.py — el motor que no dice qué motor es
# ==============================================================================

def test_un_adaptador_que_no_declara_su_motor_no_hereda_el_nombre_del_bueno():
    """
    El valor por defecto es deliberadamente poco halagüeño, y por un fallo que ya ocurrió.

    `ScoreHistory` guardaba `settings.MODEL_VERSION`, una constante de configuración, así que
    el historial afirmaba haber usado el modelo híbrido **incluso cuando el artefacto no se
    había cargado y quien puntuó fue el heurístico**. El registro que existe para poder
    explicar por qué se priorizó un prospecto afirmaba algo falso, y la degradación quedaba
    invisible justo en el sitio donde se habría detectado.

    De ahí que el valor por defecto sea «desconocido» y no el nombre del motor bueno: un
    adaptador que no declare el suyo no debe heredarlo.
    """
    class AdaptadorCallado(BaseMLScoringAdapter):
        async def predict_conversion_probability(self, features):
            return 0.5

        def is_healthy(self):
            return True

    assert AdaptadorCallado().version_del_motor() == "desconocido"


# ==============================================================================
# schemas/activity.py — la fecha de una reunión agendada
# ==============================================================================

def _actividad(**cambios):
    from app.schemas.activity import ActivityCreate

    base = {
        "lead_id": 1,
        "activity_type": ActivityType.MEETING_SCHEDULED,
        "channel": "Teléfono",
    }
    base.update(cambios)
    return ActivityCreate(**base)


def test_la_fecha_de_una_reunion_solo_vale_en_una_reunion_agendada():
    """
    `inicio_de_la_reunion` en una llamada no es un descuido: es un dato que nadie leería.

    De ese campo cuelga el recordatorio de la víspera, y el motor de reglas lo busca solo en
    las actividades de tipo reunión. Aceptarlo en una llamada guardaría una fecha que no
    genera ningún recordatorio: el asesor cree que quedó agendado y no le avisa nadie.
    """
    manana = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)

    with pytest.raises(ValueError) as fallo:
        _actividad(activity_type=ActivityType.PHONE_CALL, inicio_de_la_reunion=manana)

    assert "reunión agendada" in str(fallo.value)


def test_una_reunion_en_el_pasado_no_se_puede_agendar():
    """
    Una reunión ya pasada no se recuerda, así que agendarla es escribir un recordatorio muerto.

    Es el dedazo normal: el formulario trae la fecha de hoy y alguien escribe el mes
    anterior. Sin esta comprobación la ficha queda con una reunión que ya fue y el
    recordatorio nunca se dispara, de modo que el error no se descubre.
    """
    ayer = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)

    with pytest.raises(ValueError) as fallo:
        _actividad(inicio_de_la_reunion=ayer)

    assert "en el futuro" in str(fallo.value)


def test_una_fecha_de_reunion_sin_zona_se_entiende_en_utc_y_no_revienta():
    """
    Sin zona, se lee como UTC. Compararla *naive* con un instante *aware* es un `TypeError`.

    Y el `TypeError` saldría del validador, o sea como un 500 sobre un formulario correcto:
    un cliente que manda `2026-12-01T10:00:00` sin sufijo —que es lo que escribe cualquier
    `datetime-local` de un navegador— no podría agendar nada.
    """
    futuro_sin_zona = (
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=5)
    ).replace(tzinfo=None)

    actividad = _actividad(inicio_de_la_reunion=futuro_sin_zona)

    assert actividad.inicio_de_la_reunion is not None
    # Y la de enfrente, con zona, para que las dos se lean juntas.
    con_zona = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=5)
    assert _actividad(inicio_de_la_reunion=con_zona) is not None


def test_una_actividad_sin_fecha_de_reunion_no_se_valida_por_ella():
    """La salida temprana: el campo es opcional y lo normal es que no venga."""
    assert _actividad(activity_type=ActivityType.PHONE_CALL).inicio_de_la_reunion is None


# ==============================================================================
# schemas/desenlaces.py — un tramo que no está en la lista
# ==============================================================================

def test_un_tramo_de_acuerdo_que_no_esta_en_la_lista_se_rechaza():
    """
    El tramo es una lista cerrada, y uno inventado entraría en el panel como una categoría nueva.

    El panel de desenlaces agrupa los ganados por tramo, así que un valor libre crea una
    fila que nadie definió y reparte las cifras entre categorías que no existen. Y a
    diferencia del motivo, el tramo alimenta la tabla que se mira para decidir en qué
    tamaño de acuerdo conviene insistir.
    """
    from app.schemas.desenlaces import CierreDelProspecto

    with pytest.raises(ValueError) as fallo:
        CierreDelProspecto(
            resultado="ganado", motivo="precio",
            cerrado_el=datetime.date(2026, 9, 1), tramo="enorme",
        )

    assert "no es un tramo de la lista" in str(fallo.value)


# ==============================================================================
# crm_service.py — lo que el CRM manda mal
# ==============================================================================

def test_una_fecha_del_crm_que_no_es_una_fecha_se_rechaza_nombrando_el_campo():
    """
    El CRM manda sus fechas en ISO; una que no lo es tiene que decir qué campo era.

    Sin el `try`, el `ValueError` sube como 500 y quien integra lee «error del servidor»,
    reintenta la misma carga y vuelve a fallar. Con el campo en el 422 sabe qué corregir.
    """
    from app.services.crm_service import _instante
    from app.services.registro_de_actividad import EventoInvalido

    with pytest.raises(EventoInvalido) as fallo:
        _instante("el martes pasado", "occurred_at")

    assert fallo.value.campo == "occurred_at"
    assert "ISO 8601" in str(fallo.value)


@pytest.mark.parametrize("vacio", [None, ""])
def test_un_instante_del_crm_que_no_viene_es_nada_y_no_un_error(vacio):
    """Un campo opcional ausente no es una fecha mal escrita: son dos cosas distintas."""
    from app.services.crm_service import _instante

    assert _instante(vacio, "occurred_at") is None


# ==============================================================================
# prompt_safety.py — lo que llega del modelo sin la forma prometida
# ==============================================================================

@pytest.mark.parametrize("no_es_un_diccionario", [None, "texto", 7, ["a", "b"]])
def test_unos_metadatos_que_no_son_un_diccionario_se_quedan_en_nada(no_es_un_diccionario):
    """
    `custom_metadata` viene del formulario público: puede ser cualquier cosa.

    Si no es un diccionario no hay claves que extraer, y lo correcto es vaciarlo en lugar de
    reventar: el saneado corre antes de construir el *prompt*, y un error ahí deja sin
    explicación a un prospecto cuyos datos sí eran válidos.
    """
    assert prompt_safety.sanear_metadatos(no_es_un_diccionario) == {}


def test_unos_dias_de_inactividad_que_no_son_un_numero_cuentan_como_cero():
    """
    `days_since_last_activity` entra en el *prompt* como número, y puede llegar como texto.

    Cero es el valor honesto: no consta inactividad. Dejar el texto pasaría al *prompt* un
    valor que el modelo interpretaría como quisiera, y de ahí sale el aviso de atenuación
    temporal que el asesor lee.
    """
    for basura in ("muchos", None, {}, [1]):
        bloque = json.loads(
            prompt_safety.construir_bloque_de_datos(
                {"days_since_last_activity": basura}, 50.0, "WARM", {}
            )
        )
        assert bloque["datos_del_crm_no_confiables"]["days_since_last_activity"] == 0, basura

    # Y un número escrito como texto sí se entiende: lo que se descarta es lo que no lo es.
    bueno = json.loads(
        prompt_safety.construir_bloque_de_datos(
            {"days_since_last_activity": "12"}, 50.0, "WARM", {}
        )
    )
    assert bueno["datos_del_crm_no_confiables"]["days_since_last_activity"] == 12


def test_unas_fortalezas_que_no_son_una_lista_se_descartan_sin_tumbar_la_explicacion():
    """
    El modelo promete una lista y puede mandar una cadena. Se descarta ese campo, no todo.

    El resumen y la recomendación son lo que se guarda y se enseña; las fortalezas son un
    adorno útil. Tirar la explicación entera por un campo con la forma equivocada dejaría la
    ficha sin ninguna explicación, que es peor que dejarla sin fortalezas.
    """
    validado = prompt_safety.validar_explicacion(
        {
            "summary": "Un resumen válido.",
            "recommended_action": "Una acción recomendada.",
            "strengths": "esto tendría que ser una lista",
        }
    )

    assert validado is not None
    assert validado["summary"] == "Un resumen válido."
    assert validado["strengths"] == []


def test_una_fortaleza_que_se_queda_vacia_al_sanearla_no_entra_en_la_lista():
    """
    Una cadena de caracteres de control se queda en nada, y una nada no es una fortaleza.

    Entraría en la interfaz como un punto de lista vacío: quien lee la ficha ve un hueco y
    no sabe si falta un dato o si el sistema se dejó algo a medias.
    """
    validado = prompt_safety.validar_explicacion(
        {
            "summary": "Un resumen válido.",
            "recommended_action": "Una acción recomendada.",
            "strengths": ["\x00\x01\x02", "   ", "Una fortaleza de verdad."],
        }
    )

    assert validado["strengths"] == ["Una fortaleza de verdad."]


# ==============================================================================
# core/passwords.py — la lista de filtradas que no se puede creer
# ==============================================================================

def test_una_contrasena_que_no_viene_se_rechaza_antes_de_medir_nada():
    """
    `None` no es una contraseña corta: es que no hay contraseña, y el motivo lo dice.

    Sin esa salida, la medición en bytes de la línea siguiente sería un `AttributeError`
    sobre `None` en la pantalla de cambio de contraseña obligatorio, que es la primera que
    ve una cuenta nueva.
    """
    assert passwords.evaluar(None) == ["La contraseña es obligatoria."]


def test_una_lista_de_filtradas_que_no_se_puede_leer_se_dice_y_no_se_finge(tmp_path, monkeypatch):
    """
    Si la lista no está, el sistema lo dice en voz alta en lugar de seguir sin comprobar nada.

    Es la decisión importante de este archivo: una lista ausente **no** se trata como «no
    hay contraseñas filtradas». Eso convertiría la comprobación en un adorno justo cuando
    falla, y nadie se enteraría —todas las contraseñas pasarían—. Un error ruidoso al
    arrancar es lo correcto, porque solo puede ocurrir si el despliegue está mal armado.
    """
    monkeypatch.setattr(passwords, "MANIFIESTO_DE_FILTRADAS", tmp_path / "no-esta.json")
    monkeypatch.setattr(passwords, "ARCHIVO_DE_FILTRADAS", tmp_path / "no-esta.gz")
    passwords.contrasenas_filtradas.cache_clear()

    with pytest.raises(passwords.ListaDeFiltradasInvalida) as fallo:
        passwords.contrasenas_filtradas()

    assert "No se puede leer" in str(fallo.value)
    passwords.contrasenas_filtradas.cache_clear()


def test_una_lista_que_no_cuadra_con_su_manifiesto_tampoco_se_acepta(tmp_path, monkeypatch):
    """
    La huella y el número de entradas tienen que cuadrar: si no, la lista no es la que se probó.

    Son dos comprobaciones y las dos importan: la huella detecta un archivo cambiado, y el
    número de entradas detecta un archivo **truncado** cuya huella se recalculó de buena fe.
    Una lista a medias deja pasar justo las contraseñas que se quedaron fuera del corte.
    """
    datos = gzip.compress("una\ndos\ntres\n".encode("utf-8"))
    archivo = tmp_path / "filtradas.gz"
    archivo.write_bytes(datos)
    manifiesto = tmp_path / "filtradas.json"
    # La huella cuadra, el recuento no: un archivo truncado al que alguien le recalculó el sha.
    manifiesto.write_text(
        json.dumps({"sha256": hashlib.sha256(datos).hexdigest(), "entradas": 999}),
        encoding="utf-8",
    )
    monkeypatch.setattr(passwords, "MANIFIESTO_DE_FILTRADAS", manifiesto)
    monkeypatch.setattr(passwords, "ARCHIVO_DE_FILTRADAS", archivo)
    passwords.contrasenas_filtradas.cache_clear()

    with pytest.raises(passwords.ListaDeFiltradasInvalida) as fallo:
        passwords.contrasenas_filtradas()

    assert "entradas que declara" in str(fallo.value)
    passwords.contrasenas_filtradas.cache_clear()


# ==============================================================================
# endpoints/campaigns.py — la edición vacía y el cambio de responsable
# ==============================================================================

def test_una_edicion_de_publicacion_con_el_cuerpo_vacio_no_cambia_ni_anota_nada(
    client, lead_headers, db_session
):
    """
    Lo que manda un formulario del que no se tocó nada: no hay nada que escribir.

    Sin la salida temprana, la edición pasaría por las comprobaciones de fechas y de
    transición de estado con los valores que ya tiene —que podrían no cumplirlas si la
    publicación venció mientras la pantalla estaba abierta— y rechazaría un cambio que no
    cambia nada. Y dejaría en la bitácora que esa publicación se modificó, que es escribir
    algo falso en un registro que no se puede borrar.
    """
    from app.models.entities import AuditLog

    creada = client.post(
        "/api/v1/campaigns", headers=lead_headers,
        json={"name": f"Vacia {uuid.uuid4().hex[:6]}", "channel": "LinkedIn",
              "description": "Texto", "budget": 100.0},
    ).json()
    asientos_antes = db_session.query(AuditLog).count()

    respuesta = client.put(
        f"/api/v1/campaigns/{creada['id']}", headers=lead_headers, json={}
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["name"] == creada["name"]
    # Queda el asiento de la consulta, pero sin ningún campo cambiado dentro.
    db_session.expire_all()
    nuevos = (
        db_session.query(AuditLog)
        .order_by(AuditLog.id.desc())
        .limit(db_session.query(AuditLog).count() - asientos_antes or 1)
        .all()
    )
    for asiento in nuevos:
        metadatos = asiento.event_metadata or {}
        assert "presupuesto_nuevo" not in metadatos
        assert "responsable_nuevo" not in metadatos


def test_cambiar_el_responsable_de_una_publicacion_queda_escrito_con_los_dos_nombres(
    client, lead_headers, db_session
):
    """
    Un traspaso de responsable se anota con quién era y quién es, no solo que hubo cambio.

    Es la misma regla que el resto de la bitácora: lo que se guarda en un registro que no se
    puede borrar tiene que servir para contestar «quién tenía esto antes». Anotar solo el
    valor nuevo deja la pregunta sin respuesta a partir del segundo traspaso.
    """
    from app.models.entities import AuditLog, User

    # Un asesor propio: el responsable tiene que ser un asesor comercial ACTIVO, y las
    # cuentas de la base de pruebas no llevan la marca `is_sales_rep`.
    responsable = User(
        email=f"responsable.{uuid.uuid4().hex[:8]}@plurione.com",
        full_name="Responsable de Pruebas", role="Commercial_Executive",
        hashed_password="!sin-contrasena:prueba", is_sales_rep=True, capacity=30,
    )
    db_session.add(responsable)
    db_session.commit()
    db_session.refresh(responsable)
    creada = client.post(
        "/api/v1/campaigns", headers=lead_headers,
        json={"name": f"Traspaso {uuid.uuid4().hex[:6]}", "channel": "LinkedIn",
              "description": "Texto", "budget": 100.0},
    ).json()

    respuesta = client.put(
        f"/api/v1/campaigns/{creada['id']}", headers=lead_headers,
        json={"responsable_id": responsable.id},
    )

    assert respuesta.status_code == 200, respuesta.text
    db_session.expire_all()
    asiento = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_id == str(creada["id"]))
        .order_by(AuditLog.id.desc())
        .first()
    )
    metadatos = asiento.event_metadata or {}
    assert metadatos.get("responsable_nuevo") == responsable.id
    assert "responsable_anterior" in metadatos


# ==============================================================================
# scoring_service.py — dos tipos de actividad que nadie contaba
# ==============================================================================

@pytest.mark.parametrize(
    "tipo,campo",
    [
        (ActivityType.EMAIL_CLICK, "email_clicks"),
        (ActivityType.CONTENT_DOWNLOAD, "content_downloads"),
    ],
    ids=["click_en_correo", "descarga_de_contenido"],
)
def test_dos_tipos_de_actividad_que_nadie_contaba_cuentan(db_session, sample_lead, tipo, campo):
    """
    De los seis tipos que el score cuenta, dos no se ejercitaban: el clic y la descarga.

    Son los dos que más dicen del embudo —abrir un correo es casi ruido, pulsar su enlace y
    descargar un documento son actos— y están entre los que más pesan en el bloque de
    comportamiento. Un contador que no sume no da ningún error: el score sale más bajo de lo
    que debería y el prospecto se queda sin atender porque nunca llega a la lista de hoy.
    """
    from app.models.entities import LeadActivity
    from app.services.scoring_service import ScoringService

    ahora = datetime.datetime.now(datetime.timezone.utc)
    for _ in range(2):
        db_session.add(
            LeadActivity(
                lead_id=sample_lead.id, activity_type=tipo, channel="Email",
                source="manual", occurred_at=ahora, activity_data={},
            )
        )
    db_session.commit()
    db_session.refresh(sample_lead)

    comportamiento = ScoringService(db_session).extract_features_from_lead(sample_lead)

    assert comportamiento[campo] == 2, comportamiento


# ==============================================================================
# crm_service.py — el apunte del fallo que tambien falla
# ==============================================================================

def test_si_el_apunte_de_una_ingesta_revertida_falla_no_enmascara_el_error_original(caplog):
    """
    El apunte del fallo va en su propia transaccion, y que falle no puede tapar la causa.

    Este metodo se llama DESPUES de revertir una ingesta: la excepcion de verdad -la que
    hizo revertir- ya esta en camino hacia quien integra. Si el apunte propagara su propio
    error, lo que llegaria seria el segundo y la causa original se perderia; quien lee el
    registro vería «no se pudo escribir un log» y nada sobre por que fallo la ingesta.
    """
    from app.schemas.crm import CRMWebhookPayload
    from app.services.crm_service import CRMService

    class SesionQueNoApunta:
        def add(self, *_a, **_k):
            raise RuntimeError("la tabla de integraciones no acepta la fila")

        def rollback(self):
            pass

        def commit(self):
            pass

    carga = CRMWebhookPayload(
        event="lead.updated",
        crm_platform="hubspot",
        external_lead_id="EXT-1",
        data={"email": "quien.sea@ejemplo.mx"},
    )
    servicio = CRMService(SesionQueNoApunta(), scoring_service=None)

    with caplog.at_level(logging.ERROR):
        # No levanta: es lo que esta prueba comprueba antes que nada.
        servicio._log_failed_ingest(carga, lead_id=None, error_message="algo salio mal")

    assert any("integración CRM fallida" in r.getMessage() for r in caplog.records)


# ==============================================================================
# retencion_service.py — el lote vacio, el lote que cambio y el resumen que se fusiona
# ==============================================================================

def test_sin_prospectos_no_se_consulta_nada_para_proteger(db_session):
    """
    Un lote vacio devuelve el conjunto vacio sin consultar nada.

    **Lo que esta prueba NO puede demostrar, y el arnes lo dijo:** que la guarda haga falta.
    La version anterior de este docstring afirmaba que sin ella `IN ()` se interpretaria
    como verdadero en algunos motores y «las filas protegidas» serian todas. Eso es falso
    con lo que hay instalado: SQLAlchemy 2.0.52 compila `in_([])` a un POSTCOMPILE y la
    consulta devuelve **cero filas** -comprobado-. Neutralizar la guarda no cambia ningun
    resultado; lo unico que ahorra es un viaje a la base por cada lote vacio.

    Se queda porque el contrato sigue siendo cierto y vale escrito -un lote vacio no
    protege nada- y porque el dia que alguien cambie esa consulta por SQL a mano, la frase
    de arriba deja de valer y conviene que haya una prueba en el sitio. Pero es una
    afirmacion sobre el codigo, no una red: queda inventariada entre las guardas sin
    mutante que matar.
    """
    from app.services.retencion_service import filas_protegidas

    assert filas_protegidas(db_session, []) == set()
    assert filas_protegidas(db_session, iter(())) == set()


def test_un_resumen_que_se_fusiona_conserva_el_primero_y_el_ultimo_de_verdad(db_session):
    """
    Al fusionar dos lotes del mismo mes, el primero y el ultimo son los de todo el mes.

    Los lotes llegan en el orden en que los devuelve la consulta, no en orden de fecha entre
    si: el segundo lote de un mes puede traer filas ANTERIORES a las del primero. Las dos
    comparaciones son las que hacen que el resumen mensual siga diciendo «el score empezo
    aqui y acabo alla» en lugar del primero y el ultimo del ultimo lote procesado.

    De este resumen sale la grafica historica de la ficha cuando el detalle ya se purgo, asi
    que una fecha mal elegida no se puede volver a comprobar contra nada.
    """
    from app.models.entities import ScoreCategory
    from app.services.retencion_service import _nuevo_resumen, _sumar

    class Fila:
        def __init__(self, score, cuando):
            self.lead_id = 1
            self.score = score
            self.score_category = ScoreCategory.WARM
            self.model_version = "v1"
            self.calculated_at = cuando

        id = 0

    mes = datetime.date(2026, 6, 1)
    enmedio = [
        Fila(50.0, datetime.datetime(2026, 6, 10, tzinfo=datetime.timezone.utc)),
        Fila(60.0, datetime.datetime(2026, 6, 20, tzinfo=datetime.timezone.utc)),
    ]
    resumen = _nuevo_resumen(1, mes, enmedio)

    # Un lote posterior con filas de ANTES y de DESPUES del rango que ya tenia.
    _sumar(resumen, [
        Fila(10.0, datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc)),
        Fila(90.0, datetime.datetime(2026, 6, 30, tzinfo=datetime.timezone.utc)),
    ])

    assert resumen.first_score == 10.0, "el primero del mes, no el del primer lote"
    assert resumen.last_score == 90.0, "y el ultimo del mes"
    assert resumen.scores_count == 4
    assert (resumen.score_min, resumen.score_max) == (10.0, 90.0)

    # Y un tercer lote enteramente DENTRO del rango no mueve los extremos.
    _sumar(resumen, [Fila(55.0, datetime.datetime(2026, 6, 15, tzinfo=datetime.timezone.utc))])

    assert (resumen.first_score, resumen.last_score) == (10.0, 90.0)
    assert resumen.scores_count == 5


def test_si_el_lote_cambia_debajo_se_descarta_entero_y_se_reintenta(db_session, monkeypatch):
    """
    Se leyeron N filas vencidas y el DELETE borro otra cantidad: el lote no se resume.

    Es la unica proteccion contra resumir mal: los resumenes se calculan sobre las filas que
    se LEYERON y el borrado se hace por condicion, asi que si entre las dos cosas aparece o
    desaparece una fila, el resumen no corresponde al borrado. Resumir de todas formas
    dejaria una media mensual calculada sobre un conjunto que ya no existe, y el detalle
    borrado para no poder comprobarlo. Se deshace todo y se reintenta en la pasada siguiente.
    """
    from app.services import retencion_service

    class Candidata:
        id = 1
        lead_id = 1
        score = 50.0
        score_category = "WARM"
        model_version = "v1"
        calculated_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)

    resultado = retencion_service.ResultadoDeRetencion(limite=LIMITE, meses=12, simulado=False)
    monkeypatch.setattr(retencion_service, "filas_protegidas", lambda *_a, **_k: set())

    class SesionQueBorraDeMas:
        def __init__(self):
            self.deshecha = 0
            self.confirmada = 0

        def query(self, *_a, **_k):
            return self

        def filter(self, *_a, **_k):
            return self

        def order_by(self, *_a, **_k):
            return self

        def all(self):
            return [Candidata()]

        def __iter__(self):
            # El lote recorre el Query de resumenes existentes sin `.all()`.
            return iter(())

        def delete(self, *_a, **_k):
            return 7  # otra purga borro mas de lo que se habia leido

        def rollback(self):
            self.deshecha += 1

        def commit(self):
            self.confirmada += 1

        def add(self, *_a, **_k):
            raise AssertionError("no se resume un lote que cambio debajo")

    sesion = SesionQueBorraDeMas()
    retencion_service._procesar_lote(
        sesion, [1], LIMITE, resultado
    )

    assert resultado.lotes_descartados == 1
    assert sesion.deshecha >= 1 and sesion.confirmada == 0
    assert resultado.filas_resumidas == 0


def test_un_fallo_a_mitad_del_lote_deshace_y_se_propaga(db_session, monkeypatch):
    """
    Lo contrario del caso de arriba: aqui el fallo SI se propaga, y a proposito.

    Un lote descartado por haber cambiado debajo es una carrera inofensiva que se reintenta
    sola. Un error de verdad a mitad del lote -la base cae con el DELETE ya hecho- no se
    puede tragar: si se tragara, la pasada seguiria con los demas lotes creyendo que este
    salio bien, y lo que queda es detalle borrado y resumen sin escribir. Deshacer y
    propagar deja la base como estaba y el error a la vista de quien lanzo la pasada.
    """
    from app.services import retencion_service

    class Vencida:
        id = 1
        lead_id = 1
        score = 50.0
        score_category = "WARM"
        model_version = "v1"
        calculated_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)

    resultado = retencion_service.ResultadoDeRetencion(limite=LIMITE, meses=12, simulado=False)
    monkeypatch.setattr(retencion_service, "filas_protegidas", lambda *_a, **_k: set())

    class SesionQueSeCae:
        """Lee bien y se cae en el DELETE, que es la primera escritura del lote."""

        def __init__(self):
            self.deshecha = 0

        def query(self, *_a, **_k):
            return self

        def filter(self, *_a, **_k):
            return self

        def order_by(self, *_a, **_k):
            return self

        def all(self):
            return [Vencida()]

        def __iter__(self):
            return iter(())

        def delete(self, *_a, **_k):
            raise RuntimeError("la base se cayo con el DELETE ya en marcha")

        def rollback(self):
            self.deshecha += 1

    sesion = SesionQueSeCae()
    with pytest.raises(RuntimeError):
        retencion_service._procesar_lote(
            sesion, [1], LIMITE, resultado
        )

    assert sesion.deshecha == 1, "se deshace antes de propagar"
