import uuid

from app.models.entities import CRMIntegrationLog, Lead
from tests.conftest import sign_webhook


def test_crm_webhook_missing_email_error(client):
    payload = {
        "event": "form.submission",
        "crm_platform": "Salesforce",
        "data": {
            "first_name": "Incompleto",
            # Sin email
        },
    }
    body, headers = sign_webhook(payload)
    response = client.post("/api/v1/crm/webhook", content=body, headers=headers)
    assert response.status_code == 400
    assert "email" in response.json()["detail"]


def test_crm_webhook_deduplication_and_audit(client, db_session):
    unique_id = uuid.uuid4().hex[:8]
    test_email = f"lead.dedup.{unique_id}@talentomx.com"

    # 1. Primera ingesta: Prospecto se crea
    payload_1 = {
        "event": "lead.created",
        "crm_platform": "Zoho",
        "external_lead_id": f"ZH-{unique_id}",
        "data": {
            "first_name": "Fernanda",
            "last_name": "Pérez",
            "email": test_email,
            "company": "Talento MX",
            "job_title": "Gerente de TI",
            "industry": "Software/TI",
            "company_size": "51-200",
            "activity_type": "PAGE_VIEW",
        },
    }
    body_1, headers_1 = sign_webhook(payload_1)
    resp1 = client.post("/api/v1/crm/webhook", content=body_1, headers=headers_1)
    assert resp1.status_code == 200
    lead_id_1 = resp1.json()["lead_id"]

    # 2. Segunda ingesta con el mismo correo: Deduplicación y actualización
    payload_2 = {
        "event": "form.submission",
        "crm_platform": "HubSpot",
        "external_lead_id": f"HS-{unique_id}",
        "data": {
            "first_name": "Fernanda",
            "last_name": "Pérez",
            "email": test_email,
            "company": "Talento MX Internacional",
            "job_title": "Director de Tecnología",  # Promoción de cargo
            "industry": "Software/TI",
            "company_size": "201-1000",
            "activity_type": "DEMO_REQUEST",  # Actividad de alta intención
        },
    }
    body_2, headers_2 = sign_webhook(payload_2)
    resp2 = client.post("/api/v1/crm/webhook", content=body_2, headers=headers_2)
    assert resp2.status_code == 200
    lead_id_2 = resp2.json()["lead_id"]

    # El ID debe ser idéntico (deduplicación exitosa)
    assert lead_id_1 == lead_id_2

    # Verificar en base de datos que se actualizaron los campos y se registraron ambos logs
    lead = db_session.query(Lead).filter(Lead.id == lead_id_1).first()
    assert lead.job_title == "Director de Tecnología"
    assert lead.company == "Talento MX Internacional"

    logs = db_session.query(CRMIntegrationLog).filter(CRMIntegrationLog.lead_id == lead_id_1).all()
    assert len(logs) == 2
    platforms = [registro.crm_platform for registro in logs]
    assert "Zoho" in platforms
    assert "HubSpot" in platforms
