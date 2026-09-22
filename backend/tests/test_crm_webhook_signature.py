"""
Pruebas de autenticación del webhook CRM (HMAC-SHA256 + anti-replay + tope de tamaño).

El endpoint era completamente anónimo: cualquiera en la red podía inyectar prospectos
falsos, envenenar el scoring y llenar la base de datos. Ahora exige una firma sobre
`<timestamp>.<cuerpo>` con el secreto compartido.
"""
import datetime
import json
import uuid

import pytest
from app.core.config import settings
from app.core.security import SIGNATURE_HEADER, TIMESTAMP_HEADER
from tests.conftest import TEST_WEBHOOK_SECRET, sign_webhook

WEBHOOK_URL = "/api/v1/crm/webhook"


def _payload():
    unique = uuid.uuid4().hex[:8]
    return {
        "event": "form.submission",
        "crm_platform": "HubSpot",
        "external_lead_id": f"HS-SIG-{unique}",
        "data": {
            "first_name": "Firma",
            "last_name": "Válida",
            "email": f"firma.valida.{unique}@empresa.mx",
            "company": "Empresa Firmante",
            "job_title": "Director de TI",
            "industry": "Software/TI",
            "company_size": "51-200",
            "activity_type": "FORM_SUBMIT",
        },
    }


def test_webhook_con_firma_valida_es_aceptado(client):
    body, headers = sign_webhook(_payload())
    response = client.post(WEBHOOK_URL, content=body, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_webhook_sin_firma_es_rechazado(client):
    """Es el estado anterior a la Fase 1: petición anónima, sin ninguna credencial."""
    response = client.post(WEBHOOK_URL, json=_payload())
    assert response.status_code == 401
    assert "Firma" in response.json()["detail"]


def test_webhook_sin_timestamp_es_rechazado(client):
    body, headers = sign_webhook(_payload())
    del headers[TIMESTAMP_HEADER]
    response = client.post(WEBHOOK_URL, content=body, headers=headers)
    assert response.status_code == 401


def test_webhook_con_firma_de_otro_secreto_es_rechazado(client):
    """Quien no conoce el secreto compartido no puede producir una firma aceptable."""
    body, headers = sign_webhook(_payload(), secret="secreto-que-el-atacante-invento")
    response = client.post(WEBHOOK_URL, content=body, headers=headers)
    assert response.status_code == 401


def test_webhook_con_cuerpo_alterado_tras_firmar_es_rechazado(client):
    """
    Interceptar un webhook legítimo y cambiar su contenido invalida la firma: el HMAC
    cubre los bytes exactos del cuerpo.
    """
    payload = _payload()
    body, headers = sign_webhook(payload)

    payload["data"]["email"] = "inyectado.por.atacante@evil.com"
    tampered = json.dumps(payload).encode("utf-8")

    response = client.post(WEBHOOK_URL, content=tampered, headers=headers)
    assert response.status_code == 401


@pytest.mark.parametrize("desfase_segundos", [-3600, -600, 600, 3600])
def test_webhook_fuera_de_la_ventana_antireplay_es_rechazado(client, desfase_segundos):
    """
    Reenviar una captura antigua —o adelantar la marca de tiempo— cae fuera de la
    ventana de tolerancia, aunque la firma sea criptográficamente correcta.
    """
    now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    body, headers = sign_webhook(_payload(), timestamp=now + desfase_segundos)
    response = client.post(WEBHOOK_URL, content=body, headers=headers)
    assert response.status_code == 401
    assert "ventana" in response.json()["detail"]


def test_webhook_dentro_de_la_ventana_antireplay_es_aceptado(client):
    """Un desfase pequeño (relojes no perfectamente sincronizados) sigue siendo válido."""
    now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    body, headers = sign_webhook(_payload(), timestamp=now - 30)
    response = client.post(WEBHOOK_URL, content=body, headers=headers)
    assert response.status_code == 200


def test_webhook_con_timestamp_no_numerico_es_rechazado(client):
    body, headers = sign_webhook(_payload())
    headers[TIMESTAMP_HEADER] = "no-es-un-numero"
    response = client.post(WEBHOOK_URL, content=body, headers=headers)
    assert response.status_code == 401


def test_webhook_con_cuerpo_excesivo_es_rechazado(client):
    """
    Un cuerpo por encima del tope se corta por tamaño antes de intentar parsearlo,
    para que nadie pueda forzar la reserva de memoria arbitraria sin autenticarse.
    """
    payload = _payload()
    payload["data"]["notes"] = "A" * (settings.CRM_WEBHOOK_MAX_BODY_BYTES + 1024)
    body, headers = sign_webhook(payload)
    response = client.post(WEBHOOK_URL, content=body, headers=headers)
    assert response.status_code == 413


def test_webhook_deshabilitado_si_no_hay_secreto_configurado(client, monkeypatch):
    """Sin `CRM_WEBHOOK_SECRET`, el endpoint se cierra en lugar de aceptar tráfico anónimo."""
    monkeypatch.setattr(settings, "CRM_WEBHOOK_SECRET", "")
    body, headers = sign_webhook(_payload())
    response = client.post(WEBHOOK_URL, content=body, headers=headers)
    assert response.status_code == 503


def test_webhook_firmado_pero_con_json_invalido_devuelve_400(client):
    """Autenticado pero con un cuerpo ilegible: error de formato, no un 500."""
    body = b"{esto no es json valido"
    ts = str(int(datetime.datetime.now(datetime.timezone.utc).timestamp()))
    import hashlib
    import hmac

    signature = hmac.new(
        TEST_WEBHOOK_SECRET.encode("utf-8"), ts.encode("utf-8") + b"." + body, hashlib.sha256
    ).hexdigest()
    response = client.post(
        WEBHOOK_URL,
        content=body,
        headers={"Content-Type": "application/json", SIGNATURE_HEADER: signature, TIMESTAMP_HEADER: ts},
    )
    assert response.status_code == 400


def test_una_firma_que_no_cubre_el_timestamp_es_rechazada(client):
    """
    El HMAC se calcula sobre `<timestamp>.<cuerpo>`, no sobre el cuerpo a secas.

    Es la diferencia entre tener y no tener protección anti-replay: si la firma cubriera
    solo el cuerpo, cualquiera podría reenviar una captura antigua cambiando únicamente la
    cabecera del timestamp, porque la firma seguiría siendo válida.
    """
    import hashlib
    import hmac as hmac_mod

    payload = _payload()
    body = json.dumps(payload).encode("utf-8")
    ts = str(int(datetime.datetime.now(datetime.timezone.utc).timestamp()))

    # Firma sobre el cuerpo solo, omitiendo el prefijo del timestamp
    firma_sin_timestamp = hmac_mod.new(
        TEST_WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()

    response = client.post(
        WEBHOOK_URL,
        content=body,
        headers={
            "Content-Type": "application/json",
            SIGNATURE_HEADER: firma_sin_timestamp,
            TIMESTAMP_HEADER: ts,
        },
    )
    assert response.status_code == 401


def test_reenviar_una_peticion_valida_con_otro_timestamp_es_rechazado(client):
    """
    Simula el replay real: se captura una petición legítima y se actualiza su marca de
    tiempo para que caiga dentro de la ventana. La firma deja de cuadrar.
    """
    payload = _payload()
    body, headers = sign_webhook(payload)
    assert client.post(WEBHOOK_URL, content=body, headers=headers).status_code == 200

    nuevo_ts = str(int(datetime.datetime.now(datetime.timezone.utc).timestamp()) + 5)
    headers_replay = {**headers, TIMESTAMP_HEADER: nuevo_ts}
    assert client.post(WEBHOOK_URL, content=body, headers=headers_replay).status_code == 401
