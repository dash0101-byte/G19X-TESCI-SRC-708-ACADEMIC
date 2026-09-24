"""
R-11: acceso y supresión de los datos de una persona.

Las dos pruebas que sostienen el resto no enumeran tablas a mano:

* el mapa de tablas del servicio se compara con las claves foráneas reales del esquema;
* tras suprimir, se recorren TODAS las filas de TODAS las tablas buscando el correo de la
  persona. No basta con que las tablas conocidas queden vacías: lo que hay que demostrar es
  que el dato no está en ninguna parte, incluidas las que nadie pensó que lo guardaban.
"""
import datetime
import hashlib
import re

import pytest
from app.core.audit import registrar_evento
from app.core.database import Base
from app.models.entities import (
    ActivityType,
    AuditLog,
    Aviso,
    CRMIntegrationLog,
    Desenlace,
    Lead,
    LeadActivity,
    ScoreCategory,
    ScoreHistory,
    ScoreHistoryMonthly,
    Tarea,
    User,
    WebhookDelivery,
)
from app.services import derechos_del_titular
from app.services.derechos_del_titular import (
    SUPRIMIDO,
    TABLAS_DEL_PROSPECTO,
    huella_del_titular,
    tablas_que_apuntan_a_leads,
)
from sqlalchemy import inspect, select

LEADS = "/api/v1/leads"
CORREO = "Ana.Titular@Ejemplo.com"
UTC = datetime.timezone.utc


def _ahora():
    return datetime.datetime.now(UTC)


@pytest.fixture
def titular(db_session):
    """
    Una persona con rastro en cada rincón donde el sistema guarda algo de ella.

    Incluye las dos trampas del borrado: una ingesta revertida sin `lead_id` que lleva su
    correo, y otra de «diana.titular@…», que contiene el correo buscado como subcadena y no
    es de ella.
    """
    lead = Lead(
        first_name="Ana",
        last_name="Titular",
        email=CORREO.lower(),
        phone="+52 55 1234 5678",
        company="Conservas Titular",
        raw_metadata={"utm": "otoño"},
    )
    otro = Lead(first_name="Otra", last_name="Persona", email="otra.persona@ejemplo.com", company="Ajena SA")
    db_session.add_all([lead, otro])
    db_session.commit()

    db_session.add_all(
        [
            LeadActivity(lead_id=lead.id, activity_type=ActivityType.PAGE_VIEW, activity_data={"url": "/precios"}),
            LeadActivity(lead_id=lead.id, activity_type=ActivityType.DEMO_REQUEST),
            ScoreHistory(
                lead_id=lead.id,
                score=61.0,
                score_category=ScoreCategory.WARM,
                feature_snapshot={"page_views": 3},
                ai_explanation={"texto": "Visitó precios"},
                calculated_at=_ahora(),
            ),
            ScoreHistoryMonthly(
                lead_id=lead.id,
                month=datetime.date(2025, 1, 1),
                scores_count=2,
                score_sum=80.0,
                score_min=30.0,
                score_max=50.0,
                first_score=30.0,
                first_calculated_at=_ahora(),
                last_score=50.0,
                last_category=ScoreCategory.WARM,
                last_calculated_at=_ahora(),
                category_counts={"WARM": 2},
                model_versions=["v1"],
            ),
            CRMIntegrationLog(lead_id=lead.id, event_type="INGEST", payload={"email": lead.email}),
            CRMIntegrationLog(
                lead_id=None,
                event_type="INGEST",
                sync_status="ERROR",
                payload={"contacto": {"email": CORREO}, "nombre": "Ana"},
            ),
            CRMIntegrationLog(
                lead_id=None,
                event_type="INGEST",
                sync_status="ERROR",
                payload={"contacto": {"email": "di" + lead.email}},
            ),
            WebhookDelivery(
                signature="a" * 64,
                idempotency_key="evento:ana",
                crm_platform="HubSpot",
                event="lead.updated",
                external_lead_id="hs-1",
                lead_id=lead.id,
                response_data={"lead_id": lead.id, "email": lead.email},
                expires_at=_ahora() + datetime.timedelta(minutes=15),
            ),
        ]
    )
    db_session.commit()

    # Capítulo 28: lo que el sistema mandó hacer sobre ella y a quién se lo avisó. Va
    # después del primer commit porque necesita el id de una cuenta ya existente.
    asesor = db_session.query(User).first()
    db_session.add_all(
        [
            Tarea(
                lead_id=lead.id,
                asesor_id=asesor.id,
                regla="primer_contacto",
                clave=str(asesor.id),
                vence_el=_ahora() + datetime.timedelta(hours=24),
                motivo="Prospecto recién asignado, sin contacto todavía.",
                datos={"asignado_en": _ahora().isoformat()},
            ),
            Aviso(
                usuario_id=asesor.id,
                lead_id=lead.id,
                regla="hot_sin_contacto",
                clave="h24",
                texto="Un prospecto HOT lleva 24 h sin contacto.",
                datos={"horas": 24},
            ),
            # Capitulo 30: como acabo el trato con ella. Es un dato suyo —y el unico que el
            # sistema convierte en etiqueta de entrenamiento—, asi que tiene que salir en la
            # exportacion e irse con la supresion.
            Desenlace(
                lead_id=lead.id,
                resultado="perdido",
                motivo="precio",
                cerrado_el=_ahora().date(),
                score_al_cierre=61.0,
                categoria_al_cierre=ScoreCategory.WARM,
                registrado_en=_ahora(),
                registrado_por_id=asesor.id,
            ),
        ]
    )
    db_session.commit()

    registrar_evento(
        db_session,
        accion="lead.crear",
        entidad="lead",
        entidad_id=str(lead.id),
        actor_email="test.lider@plurione.com",
        actor_role="Sales_Lead",
        metadatos={"email": lead.email, "empresa": lead.company, "origen": "Website"},
    )
    registrar_evento(
        db_session,
        accion="lead.crear",
        entidad="lead",
        entidad_id=str(otro.id),
        metadatos={"email": otro.email, "empresa": otro.company},
    )
    return lead, otro


def _correo_en_alguna_fila(db, correo):
    """
    Cada fila de cada tabla, todas sus columnas como texto. Devuelve dónde aparece.

    La dirección tiene que aparecer entera: «diana.titular@…» contiene «ana.titular@…» como
    subcadena y es otra persona, que el escenario incluye a propósito.
    """
    patron = re.compile(r"(?<![A-Za-z0-9._%+-])" + re.escape(correo) + r"(?![A-Za-z0-9._%+-])", re.IGNORECASE)
    apariciones = []
    for tabla in Base.metadata.sorted_tables:
        for fila in db.execute(select(tabla)).mappings():
            if patron.search(str(dict(fila))):
                apariciones.append(tabla.name)
    return apariciones


# ==============================================================================
# Un mapa que no se queda atrás
# ==============================================================================

def test_el_mapa_cubre_todas_las_tablas_que_apuntan_a_leads():
    """
    Una tabla nueva con clave foránea hacia `leads` rompe esta prueba hasta que alguien
    decida si se exporta y cómo se suprime. Así se detectó que `score_history_monthly`
    tenía que entrar el mismo día que se creó.
    """
    assert sorted(TABLAS_DEL_PROSPECTO) == tablas_que_apuntan_a_leads()


# ==============================================================================
# Acceso
# ==============================================================================

def test_la_exportacion_trae_todo_lo_que_el_sistema_guarda(client, lead_headers, titular):
    lead, _ = titular
    respuesta = client.get(f"{LEADS}/{lead.id}/exportar", headers=lead_headers)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["content-disposition"] == f'attachment; filename="prospecto-{lead.id}.json"'
    assert respuesta.headers["cache-control"] == "no-store"

    doc = respuesta.json()
    assert doc["formato"] == "plurione.titular/1"
    assert doc["datos_del_prospecto"]["email"] == lead.email
    assert doc["datos_del_prospecto"]["raw_metadata"] == {"utm": "otoño"}
    assert len(doc["actividades"]) == 2
    assert doc["historial_de_puntuacion"][0]["feature_snapshot"] == {"page_views": 3}
    assert doc["historial_de_puntuacion"][0]["ai_explanation"] == {"texto": "Visitó precios"}
    assert len(doc["resumen_mensual_de_puntuacion"]) == 1
    assert len(doc["integraciones_crm"]) == 1
    assert len(doc["entregas_de_webhook"]) == 1
    # La suya sí; la de «diana.titular…» no.
    assert len(doc["integraciones_crm_sin_vincular"]) == 1
    assert doc["integraciones_crm_sin_vincular"][0]["payload"]["contacto"]["email"] == CORREO
    assert [t["accion"] for t in doc["tratamientos_registrados"]] == ["lead.crear"]
    assert doc["conservacion"]["historial_de_puntuacion"]
    assert doc["fuera_de_la_base"]


def test_cada_columna_de_cada_tabla_sale_en_la_exportacion(client, lead_headers, titular):
    """Las columnas no se listan a mano: una nueva sale en la exportación el día que se crea."""
    lead, _ = titular
    doc = client.get(f"{LEADS}/{lead.id}/exportar", headers=lead_headers).json()

    assert set(doc["datos_del_prospecto"]) == {c.key for c in inspect(Lead).column_attrs}
    for tabla, seccion in TABLAS_DEL_PROSPECTO.items():
        modelo = derechos_del_titular._modelo_de_tabla(tabla)
        assert doc[seccion], f"la sección {seccion} debería traer filas en este escenario"
        assert set(doc[seccion][0]) == {c.key for c in inspect(modelo).column_attrs}, seccion


def test_la_exportacion_no_entrega_datos_personales_de_empleados(client, lead_headers, titular):
    lead, _ = titular
    texto = client.get(f"{LEADS}/{lead.id}/exportar", headers=lead_headers).text
    assert "test.lider@plurione.com" not in texto


def test_exportar_queda_en_la_bitacora_con_recuentos_y_sin_contenido(client, lead_headers, db_session, titular):
    lead, _ = titular
    client.get(f"{LEADS}/{lead.id}/exportar", headers=lead_headers)

    asiento = db_session.query(AuditLog).filter(AuditLog.action == "lead.exportar").one()
    assert asiento.entity_id == str(lead.id)
    assert asiento.actor_role == "Sales_Lead"
    assert asiento.event_metadata["secciones"]["actividades"] == 2
    assert lead.email not in str(asiento.event_metadata).lower()


def test_un_asesor_no_exporta_ni_suprime(client, executive_headers, titular):
    lead, _ = titular
    assert client.get(f"{LEADS}/{lead.id}/exportar", headers=executive_headers).status_code == 403
    assert client.delete(f"{LEADS}/{lead.id}", headers=executive_headers).status_code == 403


def test_exportar_un_prospecto_que_no_existe_es_404(client, admin_headers):
    assert client.get(f"{LEADS}/999999/exportar", headers=admin_headers).status_code == 404


# ==============================================================================
# Supresión
# ==============================================================================

def test_tras_suprimir_el_correo_no_esta_en_ninguna_tabla(client, admin_headers, db_session, titular):
    lead, _ = titular
    lead_id, correo = lead.id, lead.email
    assert _correo_en_alguna_fila(db_session, correo), "el escenario debe partir con el correo repartido"

    assert client.delete(f"{LEADS}/{lead_id}", headers=admin_headers).status_code == 204

    db_session.expire_all()
    assert _correo_en_alguna_fila(db_session, correo) == []


def test_tras_suprimir_nada_apunta_al_prospecto(client, admin_headers, db_session, titular):
    """Incluidas las entregas de webhook, que con `SET NULL` se habrían quedado huérfanas."""
    lead, _ = titular
    lead_id = lead.id
    client.delete(f"{LEADS}/{lead_id}", headers=admin_headers)

    db_session.expire_all()
    assert db_session.get(Lead, lead_id) is None
    for tabla in tablas_que_apuntan_a_leads():
        modelo = derechos_del_titular._modelo_de_tabla(tabla)
        assert db_session.query(modelo).filter(modelo.lead_id == lead_id).count() == 0, tabla
    assert db_session.query(WebhookDelivery).count() == 0


def test_la_supresion_no_toca_a_quien_solo_se_parece(client, admin_headers, db_session, titular):
    lead, otro = titular
    correo, otro_id, otro_correo = lead.email, otro.id, otro.email
    client.delete(f"{LEADS}/{lead.id}", headers=admin_headers)

    db_session.expire_all()
    assert db_session.get(Lead, otro_id) is not None
    restantes = db_session.query(CRMIntegrationLog).filter(CRMIntegrationLog.lead_id.is_(None)).all()
    assert [r.payload["contacto"]["email"] for r in restantes] == ["di" + correo]
    ajeno = db_session.query(AuditLog).filter(AuditLog.entity_id == str(otro_id)).one()
    assert ajeno.event_metadata["email"] == otro_correo


def test_la_bitacora_conserva_los_hechos_y_pierde_los_datos(client, admin_headers, db_session, titular):
    """
    La bitácora no se borra: quién dio de alta a esta persona y cuándo sigue siendo cierto.
    Lo que se retira es el dato personal que el asiento llevaba dentro.
    """
    lead, _ = titular
    antes = db_session.query(AuditLog).filter(AuditLog.action == "lead.crear", AuditLog.entity_id == str(lead.id)).one()
    hechos = (antes.id, antes.actor_email, antes.actor_role, antes.occurred_at)

    client.delete(f"{LEADS}/{lead.id}", headers=admin_headers)

    db_session.expire_all()
    despues = db_session.get(AuditLog, antes.id)
    assert (despues.id, despues.actor_email, despues.actor_role, despues.occurred_at) == hechos
    assert despues.event_metadata == {"email": SUPRIMIDO, "empresa": SUPRIMIDO, "origen": "Website"}

    borrado = db_session.query(AuditLog).filter(AuditLog.action == "lead.eliminar").one()
    recuento = borrado.event_metadata["supresion"]
    assert recuento["lead_activities"] == 2
    assert recuento["crm_integration_logs_sin_vincular"] == 1
    assert recuento["webhook_deliveries"] == 1
    assert recuento["asientos_con_datos_retirados"] == 1
    assert recuento["leads"] == 1


def test_una_supresion_que_falla_a_mitad_no_borra_nada(client, admin_headers, db_session, titular, monkeypatch):
    lead, _ = titular

    def falla(*_args, **_kwargs):
        raise RuntimeError("fallo a mitad de la supresión")

    monkeypatch.setattr(derechos_del_titular, "_asientos_del_prospecto", falla)
    with pytest.raises(RuntimeError):
        client.delete(f"{LEADS}/{lead.id}", headers=admin_headers)

    db_session.expire_all()
    assert db_session.get(Lead, lead.id) is not None
    assert db_session.query(LeadActivity).filter(LeadActivity.lead_id == lead.id).count() == 2
    assert db_session.query(WebhookDelivery).count() == 1


def test_la_huella_del_titular_lleva_clave(monkeypatch):
    """
    Un SHA-256 a secas del correo lo invierte cualquiera con una lista de correos. Con
    clave, solo quien opera el sistema puede comprobar si una persona fue suprimida.
    """
    from app.core.config import settings

    huella = huella_del_titular(CORREO)
    assert huella == huella_del_titular("  " + CORREO.lower() + " ")
    assert huella not in hashlib.sha256(CORREO.lower().encode()).hexdigest()

    monkeypatch.setattr(settings, "SECRET_KEY", "otra-clave-distinta-para-comprobar-la-dependencia")
    assert huella_del_titular(CORREO) != huella
