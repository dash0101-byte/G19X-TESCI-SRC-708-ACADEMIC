"""
Atomicidad de la ingesta del webhook CRM (M-13).

`process_webhook` encadenaba cuatro `commit`. Un fallo a mitad de camino dejaba estados
que ninguna consulta podía distinguir de un alta correcta: un prospecto creado sin
actividad, o con actividad y sin score, contando en las analíticas y en el conteo de
`total_leads` como si la ingesta hubiera terminado bien.

Ahora todo se confirma junto. Si el scoring falla, la ingesta se revierte entera y solo
queda la traza de auditoría, que es precisamente lo que debe sobrevivir.
"""
import uuid

import pytest
from app.models.entities import CRMIntegrationLog, Lead, LeadActivity
from app.services.scoring_service import ScoringService
from tests.conftest import sign_webhook

WEBHOOK_URL = "/api/v1/crm/webhook"


@pytest.fixture
def scoring_roto(monkeypatch):
    """Simula una caída del motor de scoring en mitad de la ingesta."""
    async def _falla(self, lead, generate_ai_text=True, commit=True):
        raise RuntimeError("motor de scoring no disponible")

    monkeypatch.setattr(ScoringService, "calculate_and_persist_score", _falla)


def _payload(email: str, external_id: str, **data_extra):
    data = {
        "first_name": "Atómica",
        "last_name": "Ingesta",
        "email": email,
        "company": "Empresa Transaccional",
        "job_title": "Director de Tecnología",
        "industry": "Software/TI",
        "company_size": "201-1000",
        "activity_type": "DEMO_REQUEST",
    }
    data.update(data_extra)
    return {
        "event": "form.submission",
        "crm_platform": "HubSpot",
        "external_lead_id": external_id,
        "data": data,
    }


def _enviar(client, payload):
    body, headers = sign_webhook(payload)
    return client.post(WEBHOOK_URL, content=body, headers=headers)


def test_un_fallo_de_scoring_no_deja_el_prospecto_a_medias(client, db_session, scoring_roto):
    """
    El caso de alta: si el scoring falla, no debe quedar un prospecto huérfano.

    Con los cuatro commit anteriores el prospecto y su actividad ya estaban confirmados
    cuando el scoring reventaba, así que aparecía en el listado con `current_score` 0.0
    y categoría COLD —indistinguible de un prospecto legítimamente frío—.
    """
    unique = uuid.uuid4().hex[:10]
    email = f"ingesta.rota.{unique}@empresa.mx"
    external_id = f"HS-TX-{unique}"

    response = _enviar(client, _payload(email, external_id))
    assert response.status_code == 500

    assert db_session.query(Lead).filter(Lead.email == email).first() is None

    # La traza de auditoría sí sobrevive: es lo que permite investigar el incidente.
    log = db_session.query(CRMIntegrationLog).filter(
        CRMIntegrationLog.external_crm_id == external_id
    ).one()
    assert log.sync_status == "ERROR"
    assert log.error_message
    # Sin `lead_id`: la fila a la que habría apuntado ya no existe.
    assert log.lead_id is None


def test_un_fallo_de_scoring_no_altera_un_prospecto_existente(client, db_session, monkeypatch):
    """
    El caso de actualización: la deduplicación encuentra el prospecto y le aplica los
    datos nuevos. Si el scoring falla después, esos cambios deben revertirse también.
    """
    unique = uuid.uuid4().hex[:10]
    email = f"ingesta.dedup.{unique}@empresa.mx"

    # 1. Ingesta correcta que crea el prospecto
    primera = _enviar(client, _payload(email, f"HS-OK-{unique}"))
    assert primera.status_code == 200
    lead_id = primera.json()["lead_id"]

    lead = db_session.query(Lead).filter(Lead.id == lead_id).one()
    cargo_original = lead.job_title
    empresa_original = lead.company
    actividades_previas = db_session.query(LeadActivity).filter(LeadActivity.lead_id == lead_id).count()

    # 2. Segunda ingesta con datos nuevos, esta vez con el scoring caído
    async def _falla(self, lead, generate_ai_text=True, commit=True):
        raise RuntimeError("motor de scoring no disponible")

    monkeypatch.setattr(ScoringService, "calculate_and_persist_score", _falla)

    external_id = f"HS-FAIL-{unique}"
    segunda = _enviar(
        client,
        _payload(email, external_id, job_title="CEO", company="Otra Razón Social"),
    )
    assert segunda.status_code == 500

    db_session.expire_all()
    lead = db_session.query(Lead).filter(Lead.id == lead_id).one()
    assert lead.job_title == cargo_original
    assert lead.company == empresa_original

    # Tampoco quedó registrada la actividad de la ingesta revertida
    assert db_session.query(LeadActivity).filter(
        LeadActivity.lead_id == lead_id
    ).count() == actividades_previas

    # El log de error sí apunta al prospecto, porque este ya existía antes del evento
    log = db_session.query(CRMIntegrationLog).filter(
        CRMIntegrationLog.external_crm_id == external_id
    ).one()
    assert log.sync_status == "ERROR"
    assert log.lead_id == lead_id


def test_una_ingesta_correcta_persiste_todo_junto(client, db_session):
    """El camino feliz sigue confirmando prospecto, actividad, score y auditoría."""
    unique = uuid.uuid4().hex[:10]
    email = f"ingesta.ok.{unique}@empresa.mx"
    external_id = f"HS-FULL-{unique}"

    response = _enviar(client, _payload(email, external_id))
    assert response.status_code == 200
    lead_id = response.json()["lead_id"]

    lead = db_session.query(Lead).filter(Lead.id == lead_id).one()
    assert lead.current_score > 0.0
    assert db_session.query(LeadActivity).filter(LeadActivity.lead_id == lead_id).count() == 1
    assert lead.score_histories

    log = db_session.query(CRMIntegrationLog).filter(
        CRMIntegrationLog.external_crm_id == external_id
    ).one()
    assert log.sync_status == "SUCCESS"
    assert log.lead_id == lead_id


def test_el_detalle_del_fallo_interno_no_se_expone_al_emisor(client, scoring_roto):
    """
    Un fallo del servidor devuelve 500 con un mensaje genérico: el emisor del webhook
    no debe ver trazas internas, y un 500 —a diferencia del 400 que se devolvía antes—
    le indica que reintentar el mismo evento tiene sentido.
    """
    unique = uuid.uuid4().hex[:10]
    response = _enviar(
        client,
        _payload(f"ingesta.opaca.{unique}@empresa.mx", f"HS-OPACO-{unique}"),
    )

    assert response.status_code == 500
    detalle = response.json()["detail"]
    assert "motor de scoring no disponible" not in detalle
    assert "RuntimeError" not in detalle
