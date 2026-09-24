"""
El desenlace con su motivo: cerrar, el panel y el contador del reentrenamiento (cap. 30).

Lo que estas pruebas sostienen, y por qué cada una:

* **cerrar exige decir algo.** Pasar a ganado o perdido por la edición de la ficha responde
  422 y no mueve nada. Era el camino por el que se cerraban prospectos sin motivo, y cada
  uno de esos cierres es una etiqueta de entrenamiento que después no se puede interpretar;
* **nada de texto libre.** Un motivo que no está en la lista de ese resultado se rechaza,
  un ganado sin tramo también, y un perdido con tramo también: anotar «lo que habríamos
  facturado» sería una previsión de ingresos inventada;
* **el score que se guarda es el del momento.** Cerrar no recalcula. El panel pregunta
  «¿acertaba el score?» y solo se puede responder con el valor que había al decidir;
* **lo cerrado sale del trabajo.** Las tareas abiertas se descartan y las reglas dejan de
  proponer trabajo sobre ese prospecto;
* **el contador no miente.** Cuenta exactamente los cierres que el extractor del dataset
  sabría usar, con los mismos mínimos, y la merma se ve.
"""
import datetime

import pytest
from app.core.agenda import ABIERTA, DESCARTADA, DESENLACES_SUFICIENTES, PRIMER_CONTACTO
from app.core.desenlaces import MINIMO_DE_CASOS, MINIMO_POR_CLASE
from app.core.vector_del_modelo import CONDUCTUALES, VERSION_DEL_VECTOR
from app.models.entities import (
    Aviso,
    Campaign,
    Desenlace,
    Lead,
    LeadActivity,
    LeadStatus,
    ScoreCategory,
    ScoreHistory,
    Tarea,
    User,
)
from app.services import desenlaces as servicio
from app.services.motor_de_reglas import ejecutar
from tests.conftest import TEST_ACCOUNTS

LEADS = "/api/v1/leads"
DESENLACES = "/api/v1/desenlaces"
UTC = datetime.timezone.utc


def _ahora():
    return datetime.datetime.now(UTC)


def _hoy():
    return _ahora().date()


def _instantanea(version=VERSION_DEL_VECTOR):
    """
    Una instantánea **completa** del vector indicado.

    Se construye desde `CONDUCTUALES` y no a mano. Una instantánea a la que le falta una
    variable no es utilizable aunque declare la versión vigente —el extractor la descarta
    porque rellenarla con ceros le diría al modelo «no hubo actividad» donde hay un hueco—,
    así que un diccionario escrito a ojo habría medido el caso equivocado.
    """
    return dict.fromkeys(CONDUCTUALES, 0) | {"version_del_vector": version}


@pytest.fixture
def prospecto(db_session):
    """Un prospecto vivo, con su instantánea de entrada del vector vigente."""
    lead = Lead(
        first_name="Rosa",
        last_name="Lima",
        email="rosa.desenlace@empresa.mx",
        company="Lima SA",
        current_score=72.0,
        score_category=ScoreCategory.HOT,
        status=LeadStatus.NEGOTIATION,
        created_at=_ahora() - datetime.timedelta(days=30),
    )
    db_session.add(lead)
    db_session.commit()
    db_session.add(
        ScoreHistory(
            lead_id=lead.id,
            score=50.0,
            score_category=ScoreCategory.WARM,
            feature_snapshot=_instantanea(),
            calculated_at=_ahora() - datetime.timedelta(days=30),
        )
    )
    db_session.commit()
    db_session.refresh(lead)
    return lead


def _cierre(**extra):
    return {"resultado": "perdido", "motivo": "precio", "cerrado_el": _hoy().isoformat(), **extra}


# ==============================================================================
# Cerrar exige decir algo
# ==============================================================================

def test_la_edicion_de_la_ficha_no_puede_cerrar_un_prospecto(client, lead_headers, prospecto, db_session):
    """
    Era el camino por el que se cerraban prospectos sin decir nada.

    La comprobación está en el endpoint de edición y no solo en la pantalla: una pantalla
    que esconde el botón deja el camino abierto para cualquiera que llame a la API.
    """
    respuesta = client.put(f"{LEADS}/{prospecto.id}", json={"status": "WON"}, headers=lead_headers)

    assert respuesta.status_code == 422
    assert "desenlace" in respuesta.json()["detail"]
    db_session.refresh(prospecto)
    # Y no mueve nada: ni la etapa ni media transacción a medias.
    assert prospecto.status == LeadStatus.NEGOTIATION


def test_la_edicion_sigue_funcionando_para_el_resto_de_etapas(client, lead_headers, prospecto, db_session):
    """La puerta se cierra para dos etapas, no para la edición entera."""
    respuesta = client.put(
        f"{LEADS}/{prospecto.id}", json={"status": "QUALIFIED"}, headers=lead_headers
    )

    assert respuesta.status_code == 200
    db_session.refresh(prospecto)
    assert prospecto.status == LeadStatus.QUALIFIED


def test_un_prospecto_ya_cerrado_se_puede_seguir_editando(client, lead_headers, prospecto, db_session):
    """
    Corregirle el teléfono a un cliente ganado no es reabrir su trato.

    La guarda mira la etapa que **llega**, no la que el prospecto tiene: si mirara la suya,
    un cliente ganado quedaría congelado y no se le podría ni cambiar la empresa.
    """
    client.post(f"{LEADS}/{prospecto.id}/desenlace", json=_cierre(), headers=lead_headers)

    respuesta = client.put(f"{LEADS}/{prospecto.id}", json={"city": "Monterrey"}, headers=lead_headers)

    assert respuesta.status_code == 200
    db_session.refresh(prospecto)
    assert prospecto.city == "Monterrey"
    assert prospecto.status == LeadStatus.LOST


# ==============================================================================
# Nada de texto libre
# ==============================================================================

def test_el_motivo_sale_de_la_lista_cerrada(client, lead_headers, prospecto):
    respuesta = client.post(
        f"{LEADS}/{prospecto.id}/desenlace",
        json=_cierre(motivo="me cayó mal"),
        headers=lead_headers,
    )
    assert respuesta.status_code == 422


def test_un_motivo_de_ganado_no_vale_para_un_perdido(client, lead_headers, prospecto):
    """
    «Recomendación» explica un trato ganado y no explica ninguno perdido.

    Las dos listas comparten las claves donde el motivo es el mismo eje —precio, plazo,
    perfil se ganan y se pierden— y no comparten el resto; aceptar cualquiera de las dos
    en cualquier desenlace habría hecho del motivo una etiqueta sin significado.
    """
    respuesta = client.post(
        f"{LEADS}/{prospecto.id}/desenlace",
        json=_cierre(motivo="recomendacion"),
        headers=lead_headers,
    )
    assert respuesta.status_code == 422


def test_un_ganado_sin_tramo_se_rechaza(client, lead_headers, prospecto):
    respuesta = client.post(
        f"{LEADS}/{prospecto.id}/desenlace",
        json=_cierre(resultado="ganado", motivo="precio"),
        headers=lead_headers,
    )
    assert respuesta.status_code == 422
    assert "tramo" in respuesta.text


def test_un_perdido_con_tramo_se_rechaza(client, lead_headers, prospecto):
    """Un trato perdido no tiene tamaño: anotarlo sería inventar ingresos que no hubo."""
    respuesta = client.post(
        f"{LEADS}/{prospecto.id}/desenlace",
        json=_cierre(tramo="mas_de_1m"),
        headers=lead_headers,
    )
    assert respuesta.status_code == 422


def test_el_cierre_no_admite_ningun_campo_de_texto(client, lead_headers, prospecto, db_session):
    """
    Un campo de más se descarta en silencio, no se guarda.

    Pydantic ignora lo que no declara, así que esto no es una comprobación de que el
    servidor falle: es la comprobación de que lo que llegue de más **no acabe en la base**.
    """
    respuesta = client.post(
        f"{LEADS}/{prospecto.id}/desenlace",
        json={**_cierre(), "comentario": "Dijo que su jefe Ana no lo aprobó"},
        headers=lead_headers,
    )

    assert respuesta.status_code == 200
    fila = db_session.query(Desenlace).filter(Desenlace.lead_id == prospecto.id).first()
    assert "Ana" not in str({c.name: getattr(fila, c.name) for c in fila.__table__.columns})


def test_la_fecha_de_cierre_no_puede_ser_futura(client, lead_headers, prospecto):
    manana = (_hoy() + datetime.timedelta(days=1)).isoformat()
    respuesta = client.post(
        f"{LEADS}/{prospecto.id}/desenlace", json=_cierre(cerrado_el=manana), headers=lead_headers
    )
    assert respuesta.status_code == 422


def test_la_fecha_de_cierre_no_puede_ser_anterior_al_alta(client, lead_headers, prospecto):
    """
    Un cierre anterior al alta no es un caso raro: es una errata que el panel agruparía en
    un mes en el que ese prospecto no existía.
    """
    antiguo = (_hoy() - datetime.timedelta(days=400)).isoformat()
    respuesta = client.post(
        f"{LEADS}/{prospecto.id}/desenlace", json=_cierre(cerrado_el=antiguo), headers=lead_headers
    )
    assert respuesta.status_code == 422
    assert "anterior al alta" in respuesta.json()["detail"]


# ==============================================================================
# Lo que el cierre guarda
# ==============================================================================

def test_el_cierre_guarda_el_score_del_momento_y_no_recalcula(client, lead_headers, prospecto, db_session):
    """
    El número que el panel pregunta es el que el sistema decía cuando se tomó la decisión.

    Recalcular en el cierre lo sobrescribiría con uno que ya incorpora el desenlace, y la
    pregunta «¿el score acertaba?» dejaría de tener respuesta.
    """
    antes = prospecto.current_score

    respuesta = client.post(
        f"{LEADS}/{prospecto.id}/desenlace",
        json=_cierre(resultado="ganado", motivo="perfil", tramo="de_100k_a_500k"),
        headers=lead_headers,
    )

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["etapa"] == "WON"
    assert cuerpo["score_al_cierre"] == antes
    assert cuerpo["motivo_etiqueta"] == "Perfil"
    assert cuerpo["tramo_etiqueta"] == "De 100 000 a 500 000 MXN"
    db_session.refresh(prospecto)
    assert prospecto.current_score == antes


def test_el_desenlace_apunta_a_la_instantanea_de_entrada_con_su_version(client, lead_headers, prospecto, db_session):
    """Es lo que convierte el cierre en un ejemplo de entrenamiento utilizable tal cual."""
    respuesta = client.post(f"{LEADS}/{prospecto.id}/desenlace", json=_cierre(), headers=lead_headers)

    cuerpo = respuesta.json()
    assert cuerpo["version_del_vector"] == VERSION_DEL_VECTOR
    assert cuerpo["utilizable_para_reentrenar"] is True

    entrada = (
        db_session.query(ScoreHistory)
        .filter(ScoreHistory.lead_id == prospecto.id)
        .order_by(ScoreHistory.calculated_at.asc())
        .first()
    )
    fila = db_session.query(Desenlace).filter(Desenlace.lead_id == prospecto.id).first()
    assert fila.score_history_id == entrada.id


def test_un_cierre_sin_instantanea_se_registra_y_no_cuenta_como_utilizable(client, lead_headers, db_session):
    """
    Un prospecto anterior a que existiera la instantánea se cierra igual.

    Negarse a cerrarlo habría dejado fuera del panel a media cartera vieja; contarlo como
    utilizable habría prometido un ejemplo que el extractor después no encuentra.
    """
    lead = Lead(
        first_name="Viejo", last_name="Caso", email="viejo.caso@empresa.mx",
        current_score=40.0, score_category=ScoreCategory.COLD,
        created_at=_ahora() - datetime.timedelta(days=500),
    )
    db_session.add(lead)
    db_session.commit()

    respuesta = client.post(f"{LEADS}/{lead.id}/desenlace", json=_cierre(), headers=lead_headers)

    assert respuesta.status_code == 200
    assert respuesta.json()["utilizable_para_reentrenar"] is False
    assert respuesta.json()["version_del_vector"] is None


def test_cerrar_dos_veces_deja_un_solo_desenlace_el_ultimo(client, lead_headers, prospecto, db_session):
    """Corregir un cierre equivocado es reescribirlo; dos filas obligarían a elegir una."""
    client.post(f"{LEADS}/{prospecto.id}/desenlace", json=_cierre(), headers=lead_headers)
    client.post(
        f"{LEADS}/{prospecto.id}/desenlace",
        json=_cierre(resultado="ganado", motivo="precio", tramo="no_consta"),
        headers=lead_headers,
    )

    filas = db_session.query(Desenlace).filter(Desenlace.lead_id == prospecto.id).all()
    assert len(filas) == 1
    assert filas[0].resultado == "ganado"
    db_session.refresh(prospecto)
    assert prospecto.status == LeadStatus.WON


def test_el_cierre_queda_en_la_bitacora_con_su_motivo_y_sin_nombres(client, lead_headers, prospecto, db_session):
    """
    El día que una métrica del modelo sorprenda, la primera pregunta será de dónde salieron
    las etiquetas. Se anota el motivo, nunca el nombre ni la empresa.
    """
    from app.models.entities import AuditLog

    client.post(f"{LEADS}/{prospecto.id}/desenlace", json=_cierre(), headers=lead_headers)

    asiento = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "desenlace.registrar")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert asiento is not None
    assert asiento.actor_email == TEST_ACCOUNTS["Sales_Lead"][0]
    assert asiento.event_metadata["motivo"] == "precio"
    assert prospecto.email not in str(asiento.event_metadata)
    assert prospecto.company not in str(asiento.event_metadata)


def test_la_ficha_ensena_el_desenlace(client, lead_headers, prospecto):
    """Y `None` mientras siga en curso: una tarjeta vacía sugeriría un dato perdido."""
    antes = client.get(f"{LEADS}/{prospecto.id}", headers=lead_headers).json()
    assert antes["desenlace"] is None

    client.post(f"{LEADS}/{prospecto.id}/desenlace", json=_cierre(), headers=lead_headers)

    despues = client.get(f"{LEADS}/{prospecto.id}", headers=lead_headers).json()
    assert despues["desenlace"]["motivo_etiqueta"] == "Precio"
    assert despues["desenlace"]["resultado_etiqueta"] == "Perdido"


# ==============================================================================
# El alcance
# ==============================================================================

def test_un_asesor_cierra_los_suyos_y_no_los_ajenos(client, executive_headers, cartera_repartida):
    """
    Los motivos de un cierre los sabe quien estuvo en la conversación.

    Reservarlo al líder habría convertido el cierre en un trámite que se pide por chat; lo
    ajeno responde 404 y no 403, como todo lo demás, para que recorrer identificadores no
    diga cuánta cartera tiene el resto.
    """
    propios, ajenos = cartera_repartida

    mio = client.post(f"{LEADS}/{propios[0].id}/desenlace", json=_cierre(), headers=executive_headers)
    assert mio.status_code == 200

    suyo = client.post(f"{LEADS}/{ajenos[0].id}/desenlace", json=_cierre(), headers=executive_headers)
    assert suyo.status_code == 404


def test_el_panel_es_de_direccion(client, executive_headers, lead_headers):
    assert client.get(f"{DESENLACES}/panel", headers=executive_headers).status_code == 403
    assert client.get(f"{DESENLACES}/panel", headers=lead_headers).status_code == 200


def test_las_opciones_las_ve_cualquiera_con_sesion(client, executive_headers):
    """Quien cierra un prospecto es quien lo atiende: necesita la lista."""
    respuesta = client.get(f"{DESENLACES}/opciones", headers=executive_headers)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert {r["clave"] for r in cuerpo["resultados"]} == {"ganado", "perdido"}
    ganado = next(r for r in cuerpo["resultados"] if r["clave"] == "ganado")
    assert ganado["pide_tramo"] is True
    assert next(r for r in cuerpo["resultados"] if r["clave"] == "perdido")["pide_tramo"] is False
    # «Otro motivo» está en las dos: una lista cerrada sin salida produce datos falsos.
    for resultado in cuerpo["resultados"]:
        assert "otro" in {m["clave"] for m in resultado["motivos"]}


@pytest.mark.parametrize("ruta,metodo", [("/opciones", "get"), ("/panel", "get")])
def test_sin_sesion_no_se_lee_nada(client, ruta, metodo):
    assert getattr(client, metodo)(f"{DESENLACES}{ruta}").status_code == 401


# ==============================================================================
# Lo cerrado sale del trabajo
# ==============================================================================

def test_cerrar_descarta_las_tareas_abiertas(client, lead_headers, prospecto, db_session):
    """
    Nadie tiene que llamar a quien ya cerró.

    Se descartan, no se marcan hechas: nadie las hizo y no se resolvieron solas. Juntarlas
    con «hecha» inflaría la primera métrica de cumplimiento que alguien calcule.
    """
    asesor = db_session.query(User).first()
    db_session.add(
        Tarea(
            lead_id=prospecto.id, asesor_id=asesor.id, regla=PRIMER_CONTACTO, clave="x",
            estado=ABIERTA, vence_el=_ahora(), motivo="Sin contactar.", creada_en=_ahora(),
        )
    )
    db_session.commit()

    respuesta = client.post(f"{LEADS}/{prospecto.id}/desenlace", json=_cierre(), headers=lead_headers)

    assert respuesta.json()["tareas_descartadas"] == 1
    tarea = db_session.query(Tarea).filter(Tarea.lead_id == prospecto.id).first()
    db_session.refresh(tarea)
    assert tarea.estado == DESCARTADA
    assert tarea.cerrada_en is not None
    # No la cerró nadie: la cerró el desenlace.
    assert tarea.cerrada_por_id is None


def test_las_reglas_dejan_de_proponer_trabajo_sobre_lo_cerrado(client, lead_headers, prospecto, db_session):
    """
    El filtro va en la consulta de cada regla, no solo en la bandeja.

    Filtrar al pintar habría dejado el motor creando cada madrugada tareas invisibles sobre
    tratos cerrados, ocupando el índice único para siempre.
    """
    asesor = db_session.query(User).first()
    prospecto.assigned_rep_id = asesor.id
    prospecto.created_at = _ahora() - datetime.timedelta(hours=2)
    prospecto.last_activity_at = _ahora()
    db_session.commit()

    client.post(f"{LEADS}/{prospecto.id}/desenlace", json=_cierre(), headers=lead_headers)
    ejecutar(db_session, ahora=_ahora())

    abiertas = (
        db_session.query(Tarea)
        .filter(Tarea.lead_id == prospecto.id, Tarea.estado == ABIERTA)
        .count()
    )
    assert abiertas == 0


def test_la_bandeja_no_ensena_trabajo_de_prospectos_cerrados(client, lead_headers, prospecto, db_session):
    """
    Segunda defensa, para lo que se cerró por otro camino.

    Cubre los prospectos cerrados antes de que el desenlace existiera y cualquiera que
    llegue a esa etapa por una migración o un arreglo a mano en la base.
    """
    lider = db_session.query(User).filter(User.email == TEST_ACCOUNTS["Sales_Lead"][0]).first()
    db_session.add(
        Tarea(
            lead_id=prospecto.id, asesor_id=lider.id, regla=PRIMER_CONTACTO, clave="y",
            estado=ABIERTA, vence_el=_ahora(), motivo="Sin contactar.", creada_en=_ahora(),
        )
    )
    # Se cierra POR DEBAJO del servicio, como lo haría una migración: la tarea se queda.
    prospecto.status = LeadStatus.WON
    db_session.commit()

    bandeja = client.get("/api/v1/agenda/hoy", headers=lead_headers).json()

    assert prospecto.id not in {t["prospecto"]["id"] for t in bandeja["tareas"]}


def test_la_campana_tampoco_avisa_de_lo_cerrado(client, lead_headers, prospecto, db_session):
    """Y el contador de «sin leer» lleva el mismo filtro que la lista, no otro."""
    lider = db_session.query(User).filter(User.email == TEST_ACCOUNTS["Sales_Lead"][0]).first()
    db_session.add(
        Aviso(
            usuario_id=lider.id, lead_id=prospecto.id, regla="hot_sin_contacto",
            clave="z", texto="HOT sin contactar.", creado_en=_ahora(),
        )
    )
    prospecto.status = LeadStatus.WON
    db_session.commit()

    campana = client.get("/api/v1/agenda/avisos", headers=lead_headers).json()

    assert campana["avisos"] == []
    assert campana["sin_leer"] == 0


# ==============================================================================
# El contador del reentrenamiento
# ==============================================================================

_SEMBRADOS = {"n": 0}


def _cerrar_muchos(db_session, ganados, perdidos, *, vigente=True, con_instantanea=True):
    """
    Siembra cierres directamente: lo que se mide aquí es el contador, no el endpoint.

    El contador de correos es global y no por llamada porque varias pruebas siembran dos
    tandas seguidas, y `leads.email` es único en toda la tabla: con un índice que empieza
    de cero en cada tanda, la segunda choca con la primera.
    """
    for indice in range(ganados + perdidos):
        gana = indice < ganados
        _SEMBRADOS["n"] += 1
        numero = _SEMBRADOS["n"]
        lead = Lead(
            first_name="Masa", last_name=f"N{numero}", email=f"masa{numero}@empresa.mx",
            current_score=60.0, score_category=ScoreCategory.WARM,
            status=LeadStatus.WON if gana else LeadStatus.LOST,
        )
        db_session.add(lead)
        db_session.flush()
        historial_id = None
        if con_instantanea:
            historial = ScoreHistory(
                lead_id=lead.id, score=50.0, score_category=ScoreCategory.WARM,
                feature_snapshot=_instantanea(VERSION_DEL_VECTOR if vigente else 1),
                calculated_at=_ahora(),
            )
            db_session.add(historial)
            db_session.flush()
            historial_id = historial.id
        db_session.add(
            Desenlace(
                lead_id=lead.id,
                resultado="ganado" if gana else "perdido",
                motivo="precio",
                cerrado_el=_hoy(),
                tramo="no_consta" if gana else None,
                score_al_cierre=60.0,
                categoria_al_cierre=ScoreCategory.WARM,
                score_history_id=historial_id,
                version_del_vector=(VERSION_DEL_VECTOR if vigente else 1) if con_instantanea else None,
                registrado_en=_ahora(),
            )
        )
    db_session.commit()


def test_el_contador_exige_los_mismos_minimos_que_el_extractor(db_session):
    """
    Dos copias del número se habrían desincronizado el día que alguien subiera una, y el
    panel diría «ya se puede reentrenar» mientras el extractor se niega.
    """
    import sys
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[2]
    ruta = str(raiz / "ml_pipeline" / "src")
    if ruta not in sys.path:
        sys.path.insert(0, ruta)
    import feedback_dataset

    assert feedback_dataset.MINIMO_EJEMPLOS == MINIMO_DE_CASOS
    assert feedback_dataset.MINIMO_POR_CLASE == MINIMO_POR_CLASE


def test_el_contador_no_cuenta_lo_que_el_extractor_no_podria_usar(db_session):
    """
    Sin instantánea no hay vector que etiquetar; con una de otra versión, traducirla
    exigiría inventar. Las dos se cuentan aparte para que la merma se vea.
    """
    _cerrar_muchos(db_session, 2, 2)
    _cerrar_muchos(db_session, 1, 1, vigente=False)
    _cerrar_muchos(db_session, 1, 1, con_instantanea=False)

    progreso = servicio.progreso_del_reentrenamiento(db_session)

    assert progreso.cerrados == 8
    assert progreso.utilizables == 4
    assert progreso.de_un_vector_anterior == 2
    assert progreso.sin_instantanea == 2
    assert progreso.alcanzado is False
    assert progreso.faltan_casos == MINIMO_DE_CASOS - 4


def test_una_instantanea_incompleta_no_cuenta_aunque_diga_la_version_vigente(db_session):
    """
    Declarar la versión no basta: hace falta que estén todas las variables.

    Una fila escrita a mano, una migración a medias o una instantánea recortada pueden
    llevar la versión correcta y no tener vector. El contador y el extractor comparten el
    criterio (`vector_del_modelo.instantanea_utilizable`) precisamente por esto: con dos
    copias, el panel prometía ejemplos que el extractor después no encontraba.
    """
    lead = Lead(
        first_name="Media", last_name="Instantanea", email="media.instantanea@empresa.mx",
        current_score=50.0, score_category=ScoreCategory.WARM, status=LeadStatus.LOST,
    )
    db_session.add(lead)
    db_session.flush()
    historial = ScoreHistory(
        lead_id=lead.id, score=50.0, score_category=ScoreCategory.WARM,
        # Le falta todo salvo una variable, y declara la versión vigente.
        feature_snapshot={"page_views": 3, "version_del_vector": VERSION_DEL_VECTOR},
        calculated_at=_ahora(),
    )
    db_session.add(historial)
    db_session.flush()
    db_session.add(
        Desenlace(
            lead_id=lead.id, resultado="perdido", motivo="precio", cerrado_el=_hoy(),
            score_al_cierre=50.0, categoria_al_cierre=ScoreCategory.WARM,
            score_history_id=historial.id, version_del_vector=VERSION_DEL_VECTOR,
            registrado_en=_ahora(),
        )
    )
    db_session.commit()

    progreso = servicio.progreso_del_reentrenamiento(db_session)

    assert progreso.cerrados == 1
    assert progreso.utilizables == 0
    assert progreso.sin_instantanea == 1


def test_el_aviso_llega_cuando_se_alcanza_el_minimo_y_solo_una_vez(db_session):
    """
    Con la cuenta del día como clave, cada cierre nuevo dispararía otro aviso a partir del
    doscientos. Con los mínimos como clave, avisa una vez.
    """
    _cerrar_muchos(db_session, MINIMO_POR_CLASE, MINIMO_DE_CASOS - MINIMO_POR_CLASE)

    ejecutar(db_session, ahora=_ahora(), reglas=[DESENLACES_SUFICIENTES])
    primera = db_session.query(Aviso).filter(Aviso.regla == DESENLACES_SUFICIENTES).count()

    _cerrar_muchos(db_session, 5, 5)
    ejecutar(db_session, ahora=_ahora(), reglas=[DESENLACES_SUFICIENTES])
    segunda = db_session.query(Aviso).filter(Aviso.regla == DESENLACES_SUFICIENTES).count()

    assert primera >= 1, "nadie se enteró de que ya hay datos para reentrenar"
    assert segunda == primera, "la campana se llenaría del mismo aviso"


def test_sin_alcanzar_el_minimo_no_se_avisa(db_session):
    _cerrar_muchos(db_session, 3, 3)
    ejecutar(db_session, ahora=_ahora(), reglas=[DESENLACES_SUFICIENTES])

    assert db_session.query(Aviso).filter(Aviso.regla == DESENLACES_SUFICIENTES).count() == 0


# ==============================================================================
# El panel
# ==============================================================================

@pytest.fixture
def cartera_cerrada(db_session):
    """
    Cinco cierres: tres por una publicación y dos sin ella, con motivos y redes distintas.

    Es el escenario mínimo para comprobar que las filas suman el total: con todos los
    cierres en el mismo grupo, una atribución que contara dos veces pasaría igual.
    """
    publicacion = Campaign(
        name="Perfiles TI en octubre", channel="LinkedIn", public_slug="perfiles-ti-oct"
    )
    db_session.add(publicacion)
    db_session.commit()

    casos = [
        ("ana", "ganado", "precio", "whatsapp", ScoreCategory.HOT, 88.0),
        ("beto", "perdido", "precio", "whatsapp", ScoreCategory.COLD, 30.0),
        ("cris", "perdido", "no_contesto", "linkedin", ScoreCategory.WARM, 55.0),
        ("dora", "ganado", "recomendacion", None, ScoreCategory.HOT, 91.0),
        ("edu", "perdido", "plazo", None, ScoreCategory.WARM, 48.0),
    ]
    for nombre, resultado, motivo, red, categoria, score in casos:
        lead = Lead(
            first_name=nombre.title(), last_name="Cierre", email=f"{nombre}@cierre.mx",
            current_score=score, score_category=categoria,
            status=LeadStatus.WON if resultado == "ganado" else LeadStatus.LOST,
        )
        db_session.add(lead)
        db_session.flush()
        if red is not None:
            db_session.add(
                LeadActivity(
                    lead_id=lead.id,
                    activity_type="FORM_SUBMIT",
                    source="pagina_de_interes",
                    external_event_id=f"perfiles-ti-oct:{nombre}",
                    activity_data={"publicacion": "perfiles-ti-oct", "red": red},
                    occurred_at=_ahora(),
                )
            )
        db_session.add(
            Desenlace(
                lead_id=lead.id, resultado=resultado, motivo=motivo, cerrado_el=_hoy(),
                tramo="hasta_100k" if resultado == "ganado" else None,
                score_al_cierre=score, categoria_al_cierre=categoria, registrado_en=_ahora(),
            )
        )
    db_session.commit()
    return publicacion


def test_el_panel_responde_que_se_gana_que_se_pierde_y_por_que(client, lead_headers, cartera_cerrada):
    cuerpo = client.get(f"{DESENLACES}/panel", headers=lead_headers).json()

    assert cuerpo["resumen"]["cerrados"] == 5
    assert cuerpo["resumen"]["ganados"] == 2
    assert cuerpo["resumen"]["perdidos"] == 3
    assert cuerpo["resumen"]["tasa_de_ganados"] == 40.0

    perdidos_por_precio = next(
        f for f in cuerpo["por_motivo"] if f["resultado"] == "perdido" and f["motivo"] == "precio"
    )
    assert perdidos_por_precio["casos"] == 1
    # El porcentaje es sobre los perdidos, no sobre todos: «de lo que perdemos, cuánto se
    # va por precio».
    assert perdidos_por_precio["porcentaje"] == round(100 / 3, 1)


def test_cada_cierre_cuenta_una_sola_vez_por_publicacion(client, lead_headers, cartera_cerrada):
    """
    El informe de una publicación cuenta a una persona en todas a las que respondió; aquí
    cada cierre cuenta una vez. Si no, las filas no sumarían el total y el panel tendría
    dos números distintos para lo mismo.
    """
    cuerpo = client.get(f"{DESENLACES}/panel", headers=lead_headers).json()

    total = sum(f["ganados"] + f["perdidos"] for f in cuerpo["por_publicacion"])
    assert total == cuerpo["resumen"]["cerrados"]

    de_la_publicacion = next(f for f in cuerpo["por_publicacion"] if f["publicacion_id"] is not None)
    assert de_la_publicacion["titulo"] == "Perfiles TI en octubre"
    assert de_la_publicacion["ganados"] + de_la_publicacion["perdidos"] == 3


def test_la_red_solo_cuenta_a_quien_llego_por_una_publicacion(client, lead_headers, cartera_cerrada):
    """
    Quien entró por el CRM no llegó «sin red»: no llegó por ninguna red, y meterlo en la
    misma fila que a quien abrió un enlace con el parámetro borrado mezclaría dos cosas.
    """
    cuerpo = client.get(f"{DESENLACES}/panel", headers=lead_headers).json()

    total = sum(f["ganados"] + f["perdidos"] for f in cuerpo["por_red"])
    assert total == 3
    assert {f["red"] for f in cuerpo["por_red"]} == {"whatsapp", "linkedin"}


def test_el_panel_responde_si_el_score_acertaba(client, lead_headers, cartera_cerrada):
    cuerpo = client.get(f"{DESENLACES}/panel", headers=lead_headers).json()

    por_categoria = {f["categoria"]: f for f in cuerpo["acierto_del_score"]}
    # Las tres siempre, aunque alguna esté vacía: sin la fila de los COLD, la comparación
    # que la tabla invita a hacer sería la que no se puede hacer.
    assert set(por_categoria) == {"HOT", "WARM", "COLD"}
    assert por_categoria["HOT"]["ganados"] == 2
    assert por_categoria["HOT"]["tasa_de_ganados"] == 100.0
    assert por_categoria["COLD"]["casos"] == 1
    assert por_categoria["COLD"]["tasa_de_ganados"] == 0.0


def test_el_panel_no_lleva_ni_un_dato_de_contacto(client, lead_headers, cartera_cerrada, db_session):
    """Totales, no filas: quien necesita ver a las personas abre la ficha, y eso se anota."""
    texto = client.get(f"{DESENLACES}/panel", headers=lead_headers).text

    for lead in db_session.query(Lead).all():
        assert lead.email not in texto
        assert lead.first_name not in texto


def test_el_periodo_acota_los_cierres_pero_no_el_contador(client, lead_headers, cartera_cerrada):
    """
    Filtrar un trimestre responde «cómo fue este trimestre»; el reentrenamiento se alimenta
    de todo lo que hay. Mezclarlas haría que el filtro dijera que faltan ciento noventa
    ejemplos cuando en la base hay trescientos.
    """
    ayer = (_hoy() - datetime.timedelta(days=1)).isoformat()
    cuerpo = client.get(f"{DESENLACES}/panel?hasta={ayer}", headers=lead_headers).json()

    assert cuerpo["resumen"]["cerrados"] == 0
    assert cuerpo["reentrenamiento"]["cerrados"] == 5


def test_un_periodo_al_reves_se_rechaza(client, lead_headers):
    respuesta = client.get(
        f"{DESENLACES}/panel?desde=2026-09-30&hasta=2026-09-01", headers=lead_headers
    )
    assert respuesta.status_code == 422


def test_la_consulta_del_panel_queda_en_la_bitacora_sin_filas(client, lead_headers, cartera_cerrada, db_session):
    from app.models.entities import AuditLog

    client.get(f"{DESENLACES}/panel", headers=lead_headers)

    asiento = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "desenlace.panel")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert asiento is not None
    assert asiento.event_metadata["cerrados"] == 5
