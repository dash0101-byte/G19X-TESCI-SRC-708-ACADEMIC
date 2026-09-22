"""
Fase 15 — Cimientos del registro.

Un solo camino para registrar una actividad (`registrar_evento`), procedencia en cada fila,
rechazo con motivo de lo que no se puede registrar, nada inventado, teléfonos en E.164,
integraciones con secreto, interruptor y límite propios, la bandeja «Sin asociar» y la
minimización: el texto de un mensaje no llega a ninguna tabla.
"""
import datetime
import re
import time
import uuid
from pathlib import Path

import app as paquete_app
import pytest
from app.core.config import settings
from app.core.database import Base, engine
from app.core.rate_limit import limiter
from app.core.scoring_rules import UNKNOWN_INDUSTRY_POINTS, UNKNOWN_SIZE_POINTS
from app.core.telefono import TelefonoInvalido, normalizar_telefono
from app.models.entities import (
    ActivityType,
    AuditLog,
    Lead,
    LeadActivity,
    LeadStatus,
    UnmatchedEvent,
)
from app.repositories.activity_repository import ActivityRepository
from app.services.scoring_service import ScoringService
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from tests.conftest import sign_webhook

TEXTO_DE_MENSAJE = "texto-privado-del-mensaje-7f3a2c"

SECRETOS = {
    "CALENDLY": "secreto-de-pruebas-calendly",
    "WHATSAPP": "secreto-de-pruebas-whatsapp",
    "LINKEDIN_LEAD_GEN": "secreto-de-pruebas-linkedin",
    "FORMULARIO_WEB": "secreto-de-pruebas-formulario",
}
RUTAS = {
    "CALENDLY": "calendly",
    "WHATSAPP": "whatsapp",
    "LINKEDIN_LEAD_GEN": "linkedin-lead-gen",
    "FORMULARIO_WEB": "formulario-web",
}


def _ahora() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _aware(momento: datetime.datetime) -> datetime.datetime:
    return momento if momento.tzinfo else momento.replace(tzinfo=datetime.timezone.utc)


def _texto_en_alguna_fila(texto: str):
    """Nombre de la primera tabla que contiene `texto` en cualquier columna, o None."""
    with engine.connect() as conexion:
        for tabla in Base.metadata.sorted_tables:
            for fila in conexion.execute(select(tabla)):
                if any(texto in str(valor) for valor in fila):
                    return tabla.name
    return None


@pytest.fixture
def integraciones(monkeypatch):
    for prefijo, secreto in SECRETOS.items():
        monkeypatch.setattr(settings, f"INTEGRACION_{prefijo}_ACTIVA", True)
        monkeypatch.setattr(settings, f"INTEGRACION_{prefijo}_SECRETO", secreto)
    return SECRETOS


def _entregar(client, prefijo, carga, secreto=None):
    body, headers = sign_webhook(carga, secret=secreto or SECRETOS[prefijo])
    return client.post(f"/api/v1/integraciones/{RUTAS[prefijo]}/eventos", content=body, headers=headers)


def _calendly(email, uri=None):
    return {
        "event": "invitee.created",
        "payload": {
            "uri": uri or f"https://api.calendly.com/scheduled_events/E{uuid.uuid4().hex}/invitees/I1",
            "email": email,
            "name": "Invitada de Pruebas",
            "created_at": (_ahora() - datetime.timedelta(minutes=10)).isoformat(),
            "scheduled_event": {"start_time": "2026-09-20T16:00:00Z", "name": "Demo"},
            "questions_and_answers": [{"question": "¿Qué necesita?", "answer": TEXTO_DE_MENSAJE}],
        },
    }


def _whatsapp(wa_id, mensaje_id=None):
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA-PRUEBAS",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "contacts": [{"profile": {"name": "Contacto de WhatsApp"}, "wa_id": wa_id}],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": mensaje_id or f"wamid.{uuid.uuid4().hex}",
                                    "timestamp": str(int(time.time()) - 60),
                                    "type": "text",
                                    "text": {"body": TEXTO_DE_MENSAJE},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def _linkedin(email, consentimiento=True):
    return {
        "leadId": f"urn:li:leadFormResponse:{uuid.uuid4().hex}",
        "formId": "urn:li:leadGenForm:42",
        "submittedAt": int((_ahora() - datetime.timedelta(minutes=5)).timestamp() * 1000),
        "answers": {
            "emailAddress": email,
            "firstName": "Lucía",
            "lastName": "Pérez",
            "companyName": "Fintech de Pruebas",
            "jobTitle": "CTO",
            "phoneNumber": "+52 55 8765 4321",
        },
        "consent": {"privacyPolicy": consentimiento},
    }


def _formulario(email, formulario="demo"):
    return {
        "envio_id": f"web-{uuid.uuid4().hex}",
        "formulario": formulario,
        "enviado_en": (_ahora() - datetime.timedelta(minutes=2)).isoformat(),
        "pagina": "/demo",
        "campos": {
            "email": email,
            "nombre": "Diego",
            "apellidos": "Soto",
            "empresa": "Retail de Pruebas",
            "cargo": "Director de Operaciones",
            "telefono": "33 1234 5678",
            "mensaje": TEXTO_DE_MENSAJE,
        },
        "aviso_de_privacidad": {"aceptado": True, "version": "2026-01"},
    }


def _crm(email, **datos):
    base = {"email": email, "first_name": "Carla", "last_name": "Núñez", "activity_type": "FORM_SUBMIT"}
    base.update(datos)
    return {
        "event": "form.submission",
        "crm_platform": "HubSpot",
        "external_lead_id": f"HS-{uuid.uuid4().hex[:8]}",
        "data": base,
    }


def _registrar(client, headers, lead_id, **datos):
    return client.post(f"/api/v1/leads/{lead_id}/activities", json=datos, headers=headers)


def _variables(db_session, lead_id):
    db_session.expire_all()
    return ScoringService(db_session).extract_features_from_lead(db_session.get(Lead, lead_id))


def _correo_nuevo():
    return f"registro.{uuid.uuid4().hex[:10]}@empresa-pruebas.mx"


# ==============================================================================
# Registro manual desde la ficha
# ==============================================================================

def test_registrar_devuelve_el_score_de_antes_y_el_de_despues(client, lead_headers, sample_lead):
    antes = sample_lead.current_score
    respuesta = _registrar(client, lead_headers, sample_lead.id, activity_type="PHONE_CALL", call_outcome="CONECTO")

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["score_anterior"] == antes
    assert cuerpo["source"] == "manual"
    assert cuerpo["verificada"] is False
    assert cuerpo["call_outcome"] == "CONECTO"
    assert "activity_weight" not in cuerpo
    # El score que se enseña es el que quedó guardado, no una estimación.
    ficha = client.get(f"/api/v1/leads/{sample_lead.id}", headers=lead_headers).json()
    assert ficha["current_score"] == cuerpo["score"]


def test_una_llamada_sin_resultado_se_rechaza_con_el_motivo(client, lead_headers, sample_lead, db_session):
    respuesta = _registrar(client, lead_headers, sample_lead.id, activity_type="PHONE_CALL")

    assert respuesta.status_code == 422
    assert respuesta.json()["detail"]["campo"] == "call_outcome"
    assert "CONECTO" in respuesta.json()["detail"]["motivo"]
    assert db_session.query(LeadActivity).count() == 0


@pytest.mark.parametrize("tipo", ["PROPOSAL_SENT", "MEETING_SCHEDULED"])
def test_la_propuesta_y_la_reunion_no_se_declaran_a_mano(client, lead_headers, sample_lead, tipo):
    respuesta = _registrar(client, lead_headers, sample_lead.id, activity_type=tipo)

    assert respuesta.status_code == 422
    assert "etapa" in respuesta.json()["detail"]["motivo"]


def test_un_mensaje_necesita_su_direccion_y_no_lleva_notas(client, lead_headers, sample_lead):
    sin_direccion = _registrar(client, lead_headers, sample_lead.id, activity_type="WHATSAPP_MESSAGE")
    con_texto = _registrar(
        client, lead_headers, sample_lead.id,
        activity_type="LINKEDIN_MESSAGE", direction="SALIENTE", notes="Hola, ¿cómo va el proyecto?",
    )

    assert sin_direccion.status_code == 422
    assert sin_direccion.json()["detail"]["campo"] == "direction"
    assert con_texto.status_code == 422
    assert con_texto.json()["detail"]["campo"] == "notes"


def test_una_actividad_con_fecha_en_el_futuro_se_rechaza(client, lead_headers, sample_lead):
    manana = (_ahora() + datetime.timedelta(days=1)).isoformat()
    respuesta = _registrar(client, lead_headers, sample_lead.id, activity_type="DEMO_REQUEST", occurred_at=manana)

    assert respuesta.status_code == 422
    assert respuesta.json()["detail"]["campo"] == "occurred_at"


def test_cuando_ocurrio_no_es_cuando_se_registro(client, lead_headers, sample_lead, db_session):
    hace_diez_dias = _ahora() - datetime.timedelta(days=10)
    ultima_antes = _aware(sample_lead.last_activity_at)

    cuerpo = _registrar(
        client, lead_headers, sample_lead.id, activity_type="WEBINAR_ATTEND", occurred_at=hace_diez_dias.isoformat()
    ).json()

    ocurrio = _aware(datetime.datetime.fromisoformat(cuerpo["occurred_at"]))
    registrada = _aware(datetime.datetime.fromisoformat(cuerpo["created_at"]))
    assert abs((ocurrio - hace_diez_dias).total_seconds()) < 2
    assert (registrada - ocurrio) > datetime.timedelta(days=9)
    # Un evento que se anota tarde no hace más reciente al prospecto de lo que ya era.
    db_session.expire_all()
    assert abs((_aware(db_session.get(Lead, sample_lead.id).last_activity_at) - ultima_antes).total_seconds()) < 2


def test_el_resultado_de_la_llamada_es_la_variable(client, lead_headers, sample_lead, db_session):
    """Solo la que conectó es conversación; las otras cuentan como intentos, no se pierden."""
    for resultado in ("NO_CONTESTO", "BUZON", "NO_CONTESTO"):
        assert _registrar(client, lead_headers, sample_lead.id, activity_type="PHONE_CALL", call_outcome=resultado).status_code == 201
    variables = _variables(db_session, sample_lead.id)
    assert variables["phone_calls_connected"] == 0
    assert variables["phone_calls_unanswered"] == 3

    _registrar(client, lead_headers, sample_lead.id, activity_type="PHONE_CALL", call_outcome="CONECTO")
    variables = _variables(db_session, sample_lead.id)
    assert variables["phone_calls_connected"] == 1
    assert variables["phone_calls_unanswered"] == 3


def test_whatsapp_y_linkedin_son_variables_distintas(client, lead_headers, sample_lead, db_session):
    _registrar(client, lead_headers, sample_lead.id, activity_type="WHATSAPP_MESSAGE", direction="SALIENTE")
    _registrar(client, lead_headers, sample_lead.id, activity_type="LINKEDIN_MESSAGE", direction="ENTRANTE")
    _registrar(client, lead_headers, sample_lead.id, activity_type="LINKEDIN_MESSAGE", direction="SALIENTE")

    variables = _variables(db_session, sample_lead.id)
    # Hasta el capítulo 24 las tres sumaban en `whatsapp_messages`.
    assert variables["whatsapp_messages"] == 1
    assert variables["linkedin_messages"] == 2


def test_linkedin_es_un_tipo_propio_en_el_historial(client, lead_headers, sample_lead):
    _registrar(client, lead_headers, sample_lead.id, activity_type="LINKEDIN_MESSAGE", direction="SALIENTE")
    ficha = client.get(f"/api/v1/leads/{sample_lead.id}", headers=lead_headers).json()

    assert [a["activity_type"] for a in ficha["activities"]] == ["LINKEDIN_MESSAGE"]
    assert ficha["activities"][0]["channel"] == "LinkedIn"


# ==============================================================================
# El pipeline registra por sí mismo
# ==============================================================================

@pytest.mark.parametrize(("etapa", "tipo"), [("PROPOSAL_SENT", "PROPOSAL_SENT"), ("MEETING_SCHEDULED", "MEETING_SCHEDULED")])
def test_cambiar_de_etapa_registra_la_actividad_una_sola_vez(client, lead_headers, sample_leads, etapa, tipo):
    lead = next(prospecto for prospecto in sample_leads if prospecto.status.value != etapa)

    primera = client.put(f"/api/v1/leads/{lead.id}", json={"status": etapa}, headers=lead_headers)
    segunda = client.put(f"/api/v1/leads/{lead.id}", json={"status": etapa, "city": "Monterrey"}, headers=lead_headers)

    assert primera.status_code == 200, primera.text
    registradas = [a for a in segunda.json()["activities"] if a["activity_type"] == tipo]
    assert len(registradas) == 1
    assert registradas[0]["source"] == "pipeline"
    assert registradas[0]["verificada"] is False


def test_las_demas_etapas_no_registran_actividad(client, lead_headers, sample_lead):
    respuesta = client.put(f"/api/v1/leads/{sample_lead.id}", json={"status": "NEGOTIATION"}, headers=lead_headers)

    assert respuesta.status_code == 200
    assert respuesta.json()["activities"] == []


def test_la_actividad_inicial_invalida_no_deja_una_ficha_creada(client, lead_headers, db_session):
    correo = _correo_nuevo()
    respuesta = client.post(
        "/api/v1/leads",
        json={"first_name": "Ana", "last_name": "Pruebas", "email": correo, "initial_activity_type": "PROPOSAL_SENT"},
        headers=lead_headers,
    )

    assert respuesta.status_code == 422
    assert db_session.query(Lead).filter(Lead.email == correo).count() == 0


# ==============================================================================
# Webhook del CRM
# ==============================================================================

def test_un_tipo_desconocido_en_el_crm_es_422_y_no_crea_nada(client, db_session):
    correo = _correo_nuevo()
    body, headers = sign_webhook(_crm(correo, activity_type="LEAD_MAGICO"))
    respuesta = client.post("/api/v1/crm/webhook", content=body, headers=headers)

    assert respuesta.status_code == 422
    assert respuesta.json()["detail"]["campo"] == "activity_type"
    assert "LEAD_MAGICO" in respuesta.json()["detail"]["motivo"]
    assert db_session.query(Lead).filter(Lead.email == correo).count() == 0
    assert db_session.query(LeadActivity).count() == 0


def test_sin_tipo_de_actividad_el_crm_responde_422_en_lugar_de_suponer_uno(client, db_session):
    correo = _correo_nuevo()
    carga = _crm(correo)
    del carga["data"]["activity_type"]
    body, headers = sign_webhook(carga)
    respuesta = client.post("/api/v1/crm/webhook", content=body, headers=headers)

    assert respuesta.status_code == 422
    assert respuesta.json()["detail"]["campo"] == "activity_type"
    assert db_session.query(Lead).filter(Lead.email == correo).count() == 0


def test_el_crm_no_inventa_industria_tamano_empresa_ni_cargo(client, db_session):
    correo = _correo_nuevo()
    body, headers = sign_webhook(_crm(correo))
    assert client.post("/api/v1/crm/webhook", content=body, headers=headers).status_code == 200

    lead = db_session.query(Lead).filter(Lead.email == correo).one()
    assert (lead.industry, lead.company_size, lead.company, lead.job_title) == (None, None, None, None)
    historial = lead.score_histories[0]
    # Lo que no llegó puntúa neutro: ni los 15 puntos de «Tecnología» ni el tramo «1-10».
    assert historial.rule_breakdown["industry_fit_score"] == UNKNOWN_INDUSTRY_POINTS
    assert historial.rule_breakdown["company_size_fit_score"] == UNKNOWN_SIZE_POINTS
    assert historial.feature_snapshot["company_size"] == ""
    actividad = lead.activities[0]
    assert (actividad.source, actividad.verificada, actividad.channel) == ("crm", True, "HubSpot")


def test_el_mismo_evento_del_crm_no_entra_dos_veces(client, db_session):
    correo = _correo_nuevo()
    for pagina in ("/precios", "/contacto"):
        # Cuerpos distintos —la ventana de idempotencia del webhook no los junta— con el mismo
        # identificador de evento: es el registro el que los reconoce.
        body, headers = sign_webhook(_crm(correo, event_id="evt-001", activity_data={"url": pagina}))
        respuesta = client.post("/api/v1/crm/webhook", content=body, headers=headers)
        assert respuesta.status_code == 200, respuesta.text

    assert "ya estaba registrado" in respuesta.json()["message"]
    assert db_session.query(LeadActivity).count() == 1


def test_el_crm_no_guarda_el_texto_de_los_mensajes(client):
    body, headers = sign_webhook(
        _crm(
            _correo_nuevo(),
            mensaje=TEXTO_DE_MENSAJE,
            activity_data={"form_id": "contacto", "body": TEXTO_DE_MENSAJE, "anidado": {"texto": TEXTO_DE_MENSAJE}},
        )
    )
    assert client.post("/api/v1/crm/webhook", content=body, headers=headers).status_code == 200

    assert _texto_en_alguna_fila(TEXTO_DE_MENSAJE) is None


def test_un_telefono_invalido_del_crm_es_422(client):
    body, headers = sign_webhook(_crm(_correo_nuevo(), phone="123"))
    respuesta = client.post("/api/v1/crm/webhook", content=body, headers=headers)

    assert respuesta.status_code == 422
    assert respuesta.json()["detail"]["campo"] == "phone"


# ==============================================================================
# Teléfonos
# ==============================================================================

@pytest.mark.parametrize(
    ("entrada", "e164"),
    [
        ("55 1234 5678", "+525512345678"),
        ("+52 (55) 1234-5678", "+525512345678"),
        ("+5215512345678", "+525512345678"),  # el «1» de móvil con el que escribe WhatsApp
        ("+1 415 555 2671", "+14155552671"),
        ("   ", None),
    ],
)
def test_normalizar_telefono(entrada, e164):
    assert normalizar_telefono(entrada) == e164


@pytest.mark.parametrize("entrada", ["123", "55 1234 567", "no es un número"])
def test_un_telefono_sin_forma_de_numero_se_rechaza(entrada):
    with pytest.raises(TelefonoInvalido) as error:
        normalizar_telefono(entrada)
    # El mensaje no repite el número: puede acabar en un registro del servidor.
    assert entrada.strip() not in str(error.value)


def test_el_alta_guarda_el_telefono_en_e164_y_rechaza_el_que_no_lo_es(client, lead_headers):
    valido = client.post(
        "/api/v1/leads",
        json={"first_name": "Ana", "last_name": "Pruebas", "email": _correo_nuevo(), "phone": "55 1234 5678"},
        headers=lead_headers,
    )
    invalido = client.post(
        "/api/v1/leads",
        json={"first_name": "Ana", "last_name": "Pruebas", "email": _correo_nuevo(), "phone": "12345"},
        headers=lead_headers,
    )

    assert valido.status_code == 201, valido.text
    assert valido.json()["phone"] == "+525512345678"
    assert invalido.status_code == 422


# ==============================================================================
# Integraciones
# ==============================================================================

def test_calendly_registra_la_reunion_verificada_del_prospecto(client, integraciones, sample_lead, db_session):
    respuesta = _entregar(client, "CALENDLY", _calendly(sample_lead.email))

    assert respuesta.status_code == 200, respuesta.text
    evento = respuesta.json()["eventos"][0]
    assert (evento["estado"], evento["prospecto_id"]) == ("registrada", sample_lead.id)
    actividad = db_session.get(LeadActivity, evento["actividad_id"])
    assert (actividad.activity_type, actividad.source, actividad.verificada) == (
        ActivityType.MEETING_SCHEDULED, "calendly", True,
    )
    assert _variables(db_session, sample_lead.id)["meeting_scheduled"] == 1
    assert _texto_en_alguna_fila(TEXTO_DE_MENSAJE) is None


def test_whatsapp_de_un_numero_desconocido_va_a_la_bandeja_sin_crear_ficha(client, integraciones, db_session):
    fichas_antes = db_session.query(Lead).count()
    respuesta = _entregar(client, "WHATSAPP", _whatsapp("5215598765432"))

    assert respuesta.status_code == 200, respuesta.text
    evento = respuesta.json()["eventos"][0]
    assert evento["estado"] == "sin_asociar"
    assert db_session.query(Lead).count() == fichas_antes
    pendiente = db_session.get(UnmatchedEvent, evento["evento_sin_asociar_id"])
    assert pendiente.contact_phone == "+525598765432"
    assert pendiente.direction == "ENTRANTE"
    assert _texto_en_alguna_fila(TEXTO_DE_MENSAJE) is None


def test_whatsapp_casa_por_telefono_con_la_ficha(client, integraciones, sample_lead, db_session):
    sample_lead.phone = "+525511112222"
    db_session.commit()

    evento = _entregar(client, "WHATSAPP", _whatsapp("5215511112222")).json()["eventos"][0]

    assert (evento["estado"], evento["prospecto_id"]) == ("registrada", sample_lead.id)
    assert db_session.get(LeadActivity, evento["actividad_id"]).direction == "ENTRANTE"


def test_linkedin_lead_gen_crea_la_ficha_y_registra_el_aviso_de_privacidad(client, integraciones, db_session):
    correo = _correo_nuevo()
    carga = _linkedin(correo)
    evento = _entregar(client, "LINKEDIN_LEAD_GEN", carga).json()["eventos"][0]

    assert evento["prospecto_creado"] is True
    lead = db_session.query(Lead).filter(Lead.email == correo).one()
    enviado = datetime.datetime.fromtimestamp(carga["submittedAt"] / 1000, tz=datetime.timezone.utc)
    assert abs((_aware(lead.privacy_notice_accepted_at) - enviado).total_seconds()) < 1
    assert lead.privacy_notice_source == "linkedin_lead_gen"
    assert lead.phone == "+525587654321"
    assert lead.industry is None


def test_sin_consentimiento_no_se_registra_aceptacion(client, integraciones, db_session):
    correo = _correo_nuevo()
    _entregar(client, "LINKEDIN_LEAD_GEN", _linkedin(correo, consentimiento=False))

    assert db_session.query(Lead).filter(Lead.email == correo).one().privacy_notice_accepted_at is None


def test_el_formulario_web_no_copia_el_mensaje_libre(client, integraciones, db_session):
    correo = _correo_nuevo()
    evento = _entregar(client, "FORMULARIO_WEB", _formulario(correo)).json()["eventos"][0]

    assert evento["prospecto_creado"] is True
    actividad = db_session.get(LeadActivity, evento["actividad_id"])
    assert actividad.activity_type == ActivityType.DEMO_REQUEST
    assert db_session.query(Lead).filter(Lead.email == correo).one().phone == "+523312345678"
    assert _texto_en_alguna_fila(TEXTO_DE_MENSAJE) is None


def test_un_formulario_desconocido_se_rechaza_con_el_motivo(client, integraciones):
    respuesta = _entregar(client, "FORMULARIO_WEB", _formulario(_correo_nuevo(), formulario="encuesta"))

    assert respuesta.status_code == 422
    assert respuesta.json()["detail"]["campo"] == "formulario"


def test_un_evento_de_calendly_no_admitido_se_rechaza(client, integraciones, sample_lead):
    carga = _calendly(sample_lead.email)
    carga["event"] = "invitee.canceled"

    assert _entregar(client, "CALENDLY", carga).status_code == 422


def test_una_entrega_repetida_no_vuelve_a_entrar(client, integraciones, sample_lead, db_session):
    carga = _calendly(sample_lead.email)
    primera = _entregar(client, "CALENDLY", carga).json()["eventos"][0]
    segunda = _entregar(client, "CALENDLY", carga).json()["eventos"][0]

    assert primera["estado"] == "registrada"
    assert segunda["estado"] == "duplicada"
    assert segunda["actividad_id"] == primera["actividad_id"]
    assert db_session.query(LeadActivity).filter(LeadActivity.source == "calendly").count() == 1


def test_una_integracion_apagada_responde_igual_que_una_inexistente(client, integraciones, monkeypatch, sample_lead):
    monkeypatch.setattr(settings, "INTEGRACION_CALENDLY_ACTIVA", False)
    apagada = _entregar(client, "CALENDLY", _calendly(sample_lead.email))
    body, headers = sign_webhook({"x": 1}, secret="cualquiera")
    inexistente = client.post("/api/v1/integraciones/slack/eventos", content=body, headers=headers)

    assert apagada.status_code == inexistente.status_code == 404
    assert apagada.json() == inexistente.json()


def test_revocar_una_integracion_no_toca_a_las_demas(client, integraciones, monkeypatch, sample_lead):
    monkeypatch.setattr(settings, "INTEGRACION_CALENDLY_SECRETO", "")

    assert _entregar(client, "CALENDLY", _calendly(sample_lead.email)).status_code == 503
    assert _entregar(client, "WHATSAPP", _whatsapp("5215598765432")).status_code == 200


def test_el_secreto_de_una_integracion_no_firma_las_de_otra(client, integraciones):
    respuesta = _entregar(client, "WHATSAPP", _whatsapp("5215598765432"), secreto=SECRETOS["CALENDLY"])

    assert respuesta.status_code == 401


def test_el_limite_es_de_cada_integracion(client, integraciones, monkeypatch, sample_lead):
    monkeypatch.setattr(settings, "INTEGRACION_CALENDLY_LIMITE", "1/minute")
    limiter.enabled = True
    limiter.reset()

    assert _entregar(client, "CALENDLY", _calendly(sample_lead.email)).status_code == 200
    assert _entregar(client, "CALENDLY", _calendly(sample_lead.email)).status_code == 429
    assert _entregar(client, "WHATSAPP", _whatsapp("5215598765432")).status_code == 200


def test_la_entrega_queda_en_la_bitacora_sin_datos_de_contacto(client, integraciones, db_session):
    _entregar(client, "WHATSAPP", _whatsapp("5215598765432"))

    asiento = db_session.query(AuditLog).filter(AuditLog.action == "integracion.entrega").one()
    assert asiento.entity_id == "whatsapp"
    assert asiento.event_metadata["estados"] == {"sin_asociar": 1}
    assert "5598765432" not in str(asiento.event_metadata)


def test_un_limite_mal_escrito_se_rechaza_al_arrancar():
    from app.core.config import Settings

    with pytest.raises(ValueError):
        Settings(INTEGRACION_WHATSAPP_LIMITE="muchas por minuto")


# ==============================================================================
# Bandeja «Sin asociar»
# ==============================================================================

def _a_la_bandeja(client, numero="5215598765432"):
    return _entregar(client, "WHATSAPP", _whatsapp(numero)).json()["eventos"][0]["evento_sin_asociar_id"]


def test_la_bandeja_la_atiende_quien_dirige_la_cartera(client, integraciones, lead_headers, executive_headers):
    _a_la_bandeja(client)

    lista = client.get("/api/v1/eventos-sin-asociar", headers=lead_headers)
    assert lista.status_code == 200
    assert lista.json()["total"] == 1
    assert lista.json()["items"][0]["contact_phone"] == "+525598765432"
    assert client.get("/api/v1/eventos-sin-asociar", headers=executive_headers).status_code == 403


def test_vincular_convierte_el_aviso_en_actividad_y_lo_retira(client, integraciones, lead_headers, sample_lead, db_session):
    evento_id = _a_la_bandeja(client)

    respuesta = client.post(
        f"/api/v1/eventos-sin-asociar/{evento_id}/vincular", json={"lead_id": sample_lead.id}, headers=lead_headers
    )

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    # Lo decide una persona, pero lo vio WhatsApp: sigue siendo verificada.
    assert (cuerpo["source"], cuerpo["verificada"], cuerpo["lead_id"]) == ("whatsapp", True, sample_lead.id)
    assert "score" in cuerpo
    assert db_session.query(UnmatchedEvent).count() == 0
    asiento = db_session.query(AuditLog).filter(AuditLog.action == "evento.vincular").one()
    assert asiento.event_metadata["lead_id"] == sample_lead.id
    assert "5598765432" not in str(asiento.event_metadata)


def test_descartar_borra_el_aviso(client, integraciones, lead_headers, db_session):
    evento_id = _a_la_bandeja(client)

    assert client.delete(f"/api/v1/eventos-sin-asociar/{evento_id}", headers=lead_headers).status_code == 204
    assert db_session.query(UnmatchedEvent).count() == 0
    assert db_session.query(AuditLog).filter(AuditLog.action == "evento.descartar").count() == 1


def test_la_exportacion_y_la_supresion_alcanzan_la_bandeja(client, integraciones, lead_headers, sample_lead, db_session):
    _a_la_bandeja(client, numero="5215544443333")
    lead_id = sample_lead.id
    sample_lead.phone = "+525544443333"
    db_session.commit()

    exportacion = client.get(f"/api/v1/leads/{lead_id}/exportar", headers=lead_headers).json()
    assert len(exportacion["eventos_sin_asociar"]) == 1

    assert client.delete(f"/api/v1/leads/{lead_id}", headers=lead_headers).status_code == 204
    assert db_session.query(UnmatchedEvent).count() == 0


# ==============================================================================
# Un solo camino
# ==============================================================================

def test_solo_registrar_evento_escribe_actividades():
    """
    Nadie más en la aplicación construye filas de `lead_activities`. Si un endpoint nuevo lo
    hiciera, se saltaría la validación, la deduplicación y la minimización sin que nada
    fallara: esta prueba es lo que falla.
    """
    raiz = Path(paquete_app.__file__).parent
    # Una llamada al constructor; no la definición de la clase ni su `__repr__` («<LeadActivity(»).
    constructor = re.compile(r"(?<!class )(?<!<)\bLeadActivity\(")
    escritores = sorted(
        fichero.relative_to(raiz).as_posix()
        for fichero in raiz.rglob("*.py")
        if constructor.search(fichero.read_text(encoding="utf-8"))
    )

    assert escritores == ["services/registro_de_actividad.py"]
    assert not hasattr(ActivityRepository, "add_activity")


def test_la_procedencia_es_unica_para_siempre(db_session, sample_lead):
    tabla = Base.metadata.tables["lead_activities"]
    indice = next(i for i in tabla.indexes if i.name == "uq_lead_activities_source_external_event")
    assert indice.unique
    assert [columna.name for columna in indice.columns] == ["source", "external_event_id"]
    assert "activity_weight" not in tabla.columns
    assert "timestamp" not in tabla.columns

    for _ in range(2):
        db_session.add(
            LeadActivity(
                lead_id=sample_lead.id,
                activity_type=ActivityType.PAGE_VIEW,
                channel="Web",
                source="crm",
                external_event_id="HubSpot:evt-repetido",
                verificada=True,
                occurred_at=_ahora(),
            )
        )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_el_estado_del_prospecto_es_el_de_la_etapa(sample_lead):
    # Documenta la tabla que usa el pipeline: solo estas dos etapas registran actividad.
    from app.services.registro_de_actividad import ETAPA_A_ACTIVIDAD

    assert set(ETAPA_A_ACTIVIDAD) == {LeadStatus.PROPOSAL_SENT, LeadStatus.MEETING_SCHEDULED}
