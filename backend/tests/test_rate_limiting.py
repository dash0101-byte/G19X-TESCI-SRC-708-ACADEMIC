"""
Limitación de tasa en los tres endpoints abusables sin credenciales válidas.

`POST /auth/login` es el que más importa: sin tope, bcrypt encarece cada intento pero
nada impide encadenar miles contra un diccionario. `POST /crm/webhook` y
`POST /scoring/predict` protegen recursos —la base de datos y el pipeline de inferencia—
que una sola IP podía consumir en bucle.

El resto de la suite corre con el limitador apagado (ver `conftest.limitador_desactivado`);
aquí se reactiva y se estrechan los límites para comprobar que el corte existe de verdad
y no es solo un decorador puesto.
"""
import uuid

import pytest
from app.core.config import settings
from app.core.rate_limit import limiter
from tests.conftest import TEST_ACCOUNTS, TEST_PASSWORD, sign_webhook

LOGIN_URL = "/api/v1/auth/login"
PREDICT_URL = "/api/v1/scoring/predict"
WEBHOOK_URL = "/api/v1/crm/webhook"


@pytest.fixture
def limitador_estricto(monkeypatch):
    """
    Reactiva el limitador con topes mínimos.

    Los límites se resuelven por petición mediante un invocable, no al declarar el
    endpoint, así que basta con mover `settings` para estrecharlos. Es justamente la razón
    de haberlos hecho dinámicos: con la cadena fijada en el decorador, comprobar el corte
    exigiría lanzar sesenta inferencias reales.
    """
    limiter.enabled = True
    limiter.reset()
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN", "3/minute")
    monkeypatch.setattr(settings, "RATE_LIMIT_PREDICT", "2/minute")
    monkeypatch.setattr(settings, "RATE_LIMIT_WEBHOOK", "2/minute")
    yield
    limiter.enabled = False
    limiter.reset()


PERFIL = {
    "job_title": "CTO",
    "industry": "FinTech",
    "company_size": "1000+",
}


def _payload_webhook():
    unique = uuid.uuid4().hex[:8]
    return {
        "event": "form.submission",
        "crm_platform": "HubSpot",
        "external_lead_id": f"HS-RL-{unique}",
        "data": {
            "first_name": "Ráfaga",
            "last_name": "Webhook",
            "email": f"rafaga.{unique}@empresa.mx",
            "activity_type": "FORM_SUBMIT",
        },
    }


# ==============================================================================
# Login: fuerza bruta de contraseñas
# ==============================================================================

def test_el_login_corta_una_rafaga_de_intentos(client, limitador_estricto):
    """
    Con tope de 3/minuto, el cuarto intento recibe 429 en vez de otra comprobación bcrypt.

    Se usan contraseñas incorrectas a propósito: lo que se limita es el *intento*, no el
    acierto, que es lo que distingue un tope útil de uno que solo estorba a los usuarios
    legítimos.
    """
    email, _ = TEST_ACCOUNTS["Sales_Lead"]
    credenciales = {"email": email, "password": "PasswordEquivocada1"}

    codigos = [client.post(LOGIN_URL, json=credenciales).status_code for _ in range(4)]

    assert codigos[:3] == [401, 401, 401]
    assert codigos[3] == 429


def test_el_corte_del_login_no_depende_de_acertar_la_contrasena(client, limitador_estricto):
    """Agotar el cupo con credenciales válidas también bloquea: el límite es por IP."""
    email, _ = TEST_ACCOUNTS["Commercial_Executive"]
    validas = {"email": email, "password": TEST_PASSWORD}

    for _ in range(3):
        assert client.post(LOGIN_URL, json=validas).status_code == 200

    bloqueado = client.post(LOGIN_URL, json=validas)
    assert bloqueado.status_code == 429


def test_la_respuesta_de_bloqueo_informa_del_limite(client, limitador_estricto):
    """El 429 lleva las cabeceras estándar para que un cliente correcto sepa reintentar."""
    email, _ = TEST_ACCOUNTS["Sales_Lead"]
    credenciales = {"email": email, "password": "PasswordEquivocada1"}

    for _ in range(3):
        client.post(LOGIN_URL, json=credenciales)
    respuesta = client.post(LOGIN_URL, json=credenciales)

    assert respuesta.status_code == 429
    cabeceras = {clave.lower() for clave in respuesta.headers}
    assert "retry-after" in cabeceras or "x-ratelimit-limit" in cabeceras


# ==============================================================================
# Scoring: la ruta más cara del sistema
# ==============================================================================

def test_el_simulador_de_scoring_se_limita(client, lead_headers, limitador_estricto):
    """Un token válido no da derecho a consumir el pipeline de inferencia sin freno."""
    codigos = [
        client.post(PREDICT_URL, json=PERFIL, headers=lead_headers).status_code
        for _ in range(3)
    ]
    assert codigos[:2] == [200, 200]
    assert codigos[2] == 429


# ==============================================================================
# Webhook CRM: firma válida, volumen acotado
# ==============================================================================

def test_el_webhook_se_limita_aunque_la_firma_sea_valida(client, limitador_estricto):
    """
    Un secreto filtrado no debe traducirse en ingesta ilimitada.

    Cada evento crea un prospecto y dispara el scoring completo, así que el volumen es el
    recurso a proteger, no la autenticidad —que la firma ya garantiza—.
    """
    codigos = []
    for _ in range(3):
        body, headers = sign_webhook(_payload_webhook())
        codigos.append(client.post(WEBHOOK_URL, content=body, headers=headers).status_code)

    assert codigos[:2] == [200, 200]
    assert codigos[2] == 429


def test_el_webhook_bloqueado_no_ingesta_el_prospecto(client, db_session, limitador_estricto):
    """El corte ocurre antes del servicio: el evento rechazado no llega a la base."""
    from app.models.entities import Lead

    for _ in range(2):
        body, headers = sign_webhook(_payload_webhook())
        assert client.post(WEBHOOK_URL, content=body, headers=headers).status_code == 200

    payload_bloqueado = _payload_webhook()
    body, headers = sign_webhook(payload_bloqueado)
    assert client.post(WEBHOOK_URL, content=body, headers=headers).status_code == 429

    correo = payload_bloqueado["data"]["email"]
    assert db_session.query(Lead).filter(Lead.email == correo).first() is None


# ==============================================================================
# El límite no debe estorbar a la operación normal
# ==============================================================================

def test_los_endpoints_no_limitados_siguen_libres(client, lead_headers, limitador_estricto):
    """
    Solo se limita lo que se declaró. El listado de prospectos, que un asesor consulta
    continuamente durante su jornada, no debe recibir 429 por uso normal.
    """
    for _ in range(12):
        assert client.get("/api/v1/leads?limit=5", headers=lead_headers).status_code == 200


def test_con_el_limitador_desactivado_no_hay_cortes(client):
    """
    `RATE_LIMIT_ENABLED=false` permite delegar el corte en un balanceador por delante sin
    tocar el código. Este test corre con el limitador apagado por el fixture de conftest.
    """
    email, _ = TEST_ACCOUNTS["Sales_Lead"]
    credenciales = {"email": email, "password": "PasswordEquivocada1"}

    codigos = [client.post(LOGIN_URL, json=credenciales).status_code for _ in range(6)]
    assert set(codigos) == {401}
