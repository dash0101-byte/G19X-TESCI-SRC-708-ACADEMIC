"""
Confianza en las cabeceras de proxy (N-6) y bitácora de auditoría (N-8).

Van juntas porque comparten una pregunta: **quién es el cliente**. El limitador cuenta por
cliente y la bitácora registra desde dónde se hizo cada operación; si cada uno resolviera
la IP a su manera, un bloqueo por fuerza bruta quedaría atribuido a una dirección y el
intento que lo provocó a otra, que es exactamente el cruce que se querría hacer al
investigar.

`TRUST_PROXY_HEADERS` venía por defecto en `True`. `X-Forwarded-For` la escribe el cliente,
así que un backend alcanzable directamente —el `ports: 127.0.0.1:8000` de esta misma pila,
un despliegue sin proxy, un puerto abierto por error— aceptaba como identidad lo que le
mandaran, y el tope por IP se esquivaba rotando un valor inventado en cada intento.
`test_rotar_la_cabecera_no_esquiva_el_tope` es el PoC.
"""
import pathlib
import uuid

import pytest
from app.core.config import settings
from app.core.proxy import IP_DESCONOCIDA, ip_del_cliente
from app.core.rate_limit import limiter
from app.models.entities import AuditLog, Lead
from tests.conftest import TEST_ACCOUNTS, TEST_PASSWORD

LOGIN = "/api/v1/auth/login"
LEADS = "/api/v1/leads"
BITACORA = "/api/v1/audit"


class _PeticionFalsa:
    """Lo mínimo que `ip_del_cliente` mira: cabeceras y cliente."""

    class _Cliente:
        def __init__(self, host):
            self.host = host

    def __init__(self, cabeceras=None, host="203.0.113.9"):
        self.headers = cabeceras or {}
        self.client = self._Cliente(host) if host else None


# ==============================================================================
# N-6: de quién viene la petición
# ==============================================================================

def test_el_valor_por_defecto_es_no_fiarse():
    """
    Regresión sobre el ajuste. Es una línea, y es la línea: si alguien la devuelve a
    `True` «para que funcione detrás del proxy», el tope por IP deja de existir en todo
    despliegue que no tenga uno.
    """
    from app.core.config import Settings

    assert Settings.model_fields["TRUST_PROXY_HEADERS"].default is False


def test_sin_confianza_la_cabecera_se_ignora(monkeypatch):
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", False)
    peticion = _PeticionFalsa({"x-forwarded-for": "1.2.3.4"}, host="203.0.113.9")
    assert ip_del_cliente(peticion) == "203.0.113.9"


def test_con_confianza_se_toma_el_primer_salto(monkeypatch):
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", True)
    peticion = _PeticionFalsa(
        {"x-forwarded-for": "1.2.3.4, 10.0.0.1, 10.0.0.2"}, host="203.0.113.9"
    )
    assert ip_del_cliente(peticion) == "1.2.3.4", "El primer valor es el cliente original."


def test_una_cabecera_vacia_no_borra_la_identidad(monkeypatch):
    """Un `X-Forwarded-For:` sin valor no debe dejar la IP en blanco."""
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", True)
    assert ip_del_cliente(_PeticionFalsa({"x-forwarded-for": "  "})) == "203.0.113.9"


def test_sin_cliente_se_devuelve_un_marcador(monkeypatch):
    """
    Starlette no informa el cliente en transportes que no son TCP. Devolver `None` haría
    estallar al limitador, que espera una cadena.
    """
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", False)
    assert ip_del_cliente(_PeticionFalsa(host=None)) == IP_DESCONOCIDA


def test_rotar_la_cabecera_no_esquiva_el_tope(client, monkeypatch):
    """
    El PoC. Con la confianza activada por defecto, cada petición con una
    `X-Forwarded-For` distinta contaba como un cliente nuevo y el límite de login no
    llegaba a aplicarse nunca.
    """
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", False)
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN", "3/minute")
    limiter.enabled = True
    limiter.reset()
    try:
        codigos = []
        for i in range(6):
            respuesta = client.post(
                LOGIN,
                json={"email": "nadie@plurione.com", "password": "ContrasenaFalsa1!"},
                headers={"X-Forwarded-For": f"198.51.100.{i}"},
            )
            codigos.append(respuesta.status_code)
    finally:
        limiter.enabled = False
        limiter.reset()

    assert 429 in codigos, (
        "Rotar X-Forwarded-For no puede multiplicar el número de intentos permitidos."
    )


# ==============================================================================
# N-8: qué queda escrito
# ==============================================================================

def test_crear_un_prospecto_deja_asiento(client, lead_headers, db_session):
    correo = f"auditado.{uuid.uuid4().hex[:8]}@empresa.mx"
    respuesta = client.post(
        LEADS,
        headers=lead_headers,
        json={
            "first_name": "Auditada", "last_name": "Alta", "email": correo,
            "company": "Empresa MX", "job_title": "CTO", "industry": "FinTech",
            "company_size": "1000+", "source": "Website",
        },
    )
    assert respuesta.status_code == 201, respuesta.text

    asiento = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "lead.crear")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert asiento is not None
    assert asiento.entity_id == str(respuesta.json()["id"])
    assert asiento.actor_email == TEST_ACCOUNTS["Sales_Lead"][0]
    assert asiento.actor_role == "Sales_Lead"
    assert asiento.outcome == "OK"
    assert asiento.event_metadata["email"] == correo
    assert asiento.ip_address, "El asiento debe decir desde dónde se hizo la operación."


def test_eliminar_un_prospecto_permite_comprobar_a_quien_se_borro_sin_guardarlo(
    client, admin_headers, db_session, sample_lead
):
    """
    El identificador de una fila borrada no resuelve a nada, y hasta la Fase 14 el asiento
    guardaba el correo para no ser «solo un número». Pero guardar el correo de quien pidió
    ser borrado es no borrarlo (R-11). El asiento guarda ahora una huella con clave: quien
    ya conoce el correo puede comprobar que se suprimió; quien lee la bitácora no lo averigua.
    """
    from app.services.derechos_del_titular import huella_del_titular

    correo = sample_lead.email
    respuesta = client.delete(f"{LEADS}/{sample_lead.id}", headers=admin_headers)
    assert respuesta.status_code == 204

    asiento = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "lead.eliminar")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert asiento is not None
    assert asiento.outcome == "OK"
    assert correo.lower() not in str(asiento.event_metadata).lower()
    assert asiento.event_metadata["huella_del_titular"] == huella_del_titular(correo)
    assert asiento.event_metadata["supresion"]["leads"] == 1


def test_una_operacion_fallida_queda_con_su_codigo(client, admin_headers, db_session):
    """
    Un borrado que devolvió 404 es información: dice que alguien intentó borrar algo que
    ya no estaba. Registrar solo los éxitos convertiría la bitácora en un historial de
    cambios, que ya existe en otras tablas.
    """
    assert client.delete(f"{LEADS}/999999", headers=admin_headers).status_code == 404

    asiento = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "lead.eliminar")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert asiento is not None
    assert asiento.outcome == "HTTP_404"
    assert asiento.entity_id == "999999"


def test_una_denegacion_por_rol_queda_registrada(client, executive_headers, db_session, sample_lead):
    """
    Una sola denegación es ruido; una tanda seguida de la misma cuenta es alguien
    tanteando los límites de su rol. Eso solo se ve si queda escrito.
    """
    respuesta = client.delete(f"{LEADS}/{sample_lead.id}", headers=executive_headers)
    assert respuesta.status_code == 403

    asiento = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "acceso.denegado")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert asiento is not None
    assert asiento.actor_email == TEST_ACCOUNTS["Commercial_Executive"][0]
    assert asiento.outcome == "HTTP_403"
    assert asiento.entity_id == f"{LEADS}/{sample_lead.id}"
    assert "System_Admin" in asiento.event_metadata["roles_requeridos"]


def test_un_login_fallido_no_inventa_un_usuario(client, db_session):
    """
    El correo tecleado va en los metadatos, no en `actor_email`: esa columna identifica a
    una cuenta del sistema, y un barrido de correos inventados no debe quedar registrado
    como si fueran usuarios reales.
    """
    respuesta = client.post(
        LOGIN, json={"email": "inexistente@plurione.com", "password": "LoQueSea2026!"}
    )
    assert respuesta.status_code == 401

    asiento = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "auth.login_fallido")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert asiento is not None
    assert asiento.actor_email is None
    assert asiento.actor_id is None
    assert asiento.event_metadata["email_intentado"] == "inexistente@plurione.com"
    assert asiento.event_metadata["motivo"] == "email_no_registrado"


def test_un_login_correcto_queda_registrado(client, db_session):
    email, _ = TEST_ACCOUNTS["Commercial_Executive"]
    assert client.post(LOGIN, json={"email": email, "password": TEST_PASSWORD}).status_code == 200

    asiento = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "auth.login")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert asiento is not None
    assert asiento.actor_email == email
    assert asiento.outcome == "OK"


def test_la_auditoria_no_tumba_la_operacion(client, lead_headers, db_session, monkeypatch):
    """
    Que la bitácora falle no puede convertir una operación correcta en un 500. Se pierde
    el asiento —y el fallo queda en el log del servidor, donde alguien puede verlo— pero
    la operación se respeta. Al revés sería peor de lo que se intenta arreglar.
    """
    import app.core.audit as modulo

    def _explota(*_args, **_kwargs):
        raise RuntimeError("la bitácora no está disponible")

    monkeypatch.setattr(modulo.AsientoDeAuditoria, "persistir", _explota)

    respuesta = client.post(
        LEADS,
        headers=lead_headers,
        json={
            "first_name": "Sin", "last_name": "Bitácora",
            "email": f"sinbitacora.{uuid.uuid4().hex[:8]}@empresa.mx",
            "company": "Empresa MX", "job_title": "CTO", "industry": "FinTech",
            "company_size": "1000+", "source": "Website",
        },
    )
    assert respuesta.status_code == 201, "El alta debe completarse aunque la bitácora falle."


# ==============================================================================
# N-8: quién puede leerla
# ==============================================================================

@pytest.mark.parametrize("rol", ["Sales_Lead", "Commercial_Executive"])
def test_solo_el_administrador_lee_la_bitacora(client, auth_headers, rol):
    """
    La bitácora concentra, ya correlacionado, quién trabaja con qué cartera y desde dónde
    se conecta cada persona. Dársela a un `Sales_Lead` «porque es responsable del equipo»
    convertiría una medida de control en vigilancia entre compañeros.
    """
    assert client.get(BITACORA, headers=auth_headers(rol)).status_code == 403


def test_el_administrador_consulta_y_filtra(client, admin_headers, lead_headers, db_session, sample_lead):
    client.delete(f"{LEADS}/{sample_lead.id}", headers=lead_headers)

    respuesta = client.get(BITACORA, headers=admin_headers, params={"action": "lead.eliminar"})
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["total"] >= 1
    assert all(item["action"] == "lead.eliminar" for item in cuerpo["items"])
    assert cuerpo["items"][0]["entity_id"] == str(sample_lead.id)


def test_la_consulta_de_la_bitacora_se_audita_a_si_misma(client, admin_headers, db_session):
    """
    El administrador es el único rol que puede leer aquí, y por tanto el único cuyo acceso
    nadie más vería si no quedara escrito.
    """
    assert client.get(BITACORA, headers=admin_headers).status_code == 200

    asiento = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "auditoria.consulta")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert asiento is not None
    assert asiento.actor_email == TEST_ACCOUNTS["System_Admin"][0]


def test_el_tope_de_pagina_manda_sobre_lo_que_pida_el_cliente(client, admin_headers, monkeypatch):
    """
    Sin tope, un `limit` desmedido sobre una tabla que crece con cada operación sería la
    forma más cómoda de tumbar la API, y encima desde una cuenta autorizada.
    """
    monkeypatch.setattr(settings, "AUDIT_LOG_MAX_PAGE_SIZE", 5)
    respuesta = client.get(BITACORA, headers=admin_headers, params={"limit": 10_000})
    assert respuesta.status_code == 200
    assert respuesta.json()["limit"] == 5


def test_la_bitacora_es_de_solo_lectura(client, admin_headers, db_session, sample_leads):
    """
    Una bitácora que la aplicación puede reescribir no prueba nada: lo primero que
    borraría quien abusa de sus permisos es el registro de que lo hizo.
    """
    for metodo in (client.post, client.put, client.patch, client.delete):
        respuesta = metodo(BITACORA, headers=admin_headers)
        assert respuesta.status_code in (404, 405), (
            f"{metodo.__name__.upper()} sobre la bitácora no debe existir."
        )

    # Y borrar un prospecto no borra su rastro.
    victima = sample_leads[0]
    client.delete(f"{LEADS}/{victima.id}", headers=admin_headers)
    assert db_session.query(Lead).filter(Lead.id == victima.id).first() is None
    assert (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_id == str(victima.id), AuditLog.action == "lead.eliminar")
        .count()
        == 1
    )


# ==============================================================================
# La otra mitad de N-6: el proxy que hace cierta la confianza
# ==============================================================================

RAIZ_DEL_REPOSITORIO = pathlib.Path(__file__).resolve().parents[2]
NGINX_CONF = RAIZ_DEL_REPOSITORIO / "frontend" / "nginx.conf"
COMPOSE = RAIZ_DEL_REPOSITORIO / "devops" / "docker-compose.yml"


def test_el_proxy_sobrescribe_la_cabecera_en_vez_de_anadirla():
    """
    `TRUST_PROXY_HEADERS=true` solo es seguro si el proxy SOBRESCRIBE X-Forwarded-For.

    Esta prueba mira el despliegue, no el código, porque el agujero vivía justo en la
    junta entre los dos. El backend estaba bien —lee el primer elemento de la cadena, que
    es lo que escribe el salto más externo— y nginx estaba mal: con
    `$proxy_add_x_forwarded_for` AÑADE la IP real al final de lo que mandara el cliente,
    de modo que el primer elemento seguía siendo el inventado. Cada valor falsificado
    abría su propio contador y el tope por IP no se aplicaba nunca.

    Se midió contra la pila levantada: seis peticiones con `X-Forwarded-For` distinto
    produjeron seis contadores en Redis antes del arreglo y uno solo después.

    Si algún día se pone un balanceador delante de nginx habrá que volver a
    `$proxy_add_x_forwarded_for` **y** cambiar a la vez qué elemento lee el backend.
    Cambiar solo una de las dos cosas reabre el agujero, y por eso esta prueba falla
    ante el cambio aislado.
    """
    # Se miran las DIRECTIVAS, no el archivo entero: el propio comentario que explica el
    # arreglo nombra `$proxy_add_x_forwarded_for`, y una prueba que no distinga la
    # configuración de la prosa que la documenta obliga a no explicar los arreglos.
    directivas = [
        linea.strip()
        for linea in NGINX_CONF.read_text(encoding="utf-8").splitlines()
        if linea.strip() and not linea.strip().startswith("#")
    ]
    reenvio = [d for d in directivas if "X-Forwarded-For" in d]

    assert reenvio, "nginx no reenvía X-Forwarded-For al backend."
    for directiva in reenvio:
        assert "$remote_addr" in directiva, (
            f"nginx debe SOBRESCRIBIR X-Forwarded-For con $remote_addr y hace: {directiva!r}. "
            "Si lo añade a la cadena del cliente, el primer elemento —el que lee el "
            "backend— lo sigue escribiendo quien llama, y el tope por IP se esquiva "
            "rotando la cabecera."
        )
        assert "$proxy_add_x_forwarded_for" not in directiva, (
            "`$proxy_add_x_forwarded_for` conserva delante lo que mandó el cliente."
        )


def test_la_pila_solo_confia_en_el_proxy_teniendo_ese_proxy_delante():
    """
    La pila activa `TRUST_PROXY_HEADERS`; que eso sea legítimo depende del nginx anterior.

    No se puede comprobar la topología desde una prueba unitaria, así que se comprueba lo
    que sí se puede: que la pila que enciende la confianza es la misma que incluye el
    frontend que hace de proxy. Una pila que activara la variable sin ese servicio estaría
    declarando una garantía que nadie cumple.
    """
    compose = COMPOSE.read_text(encoding="utf-8")
    if 'TRUST_PROXY_HEADERS: "true"' in compose:
        assert "\n  frontend:" in compose, (
            "La pila activa TRUST_PROXY_HEADERS pero no incluye el nginx que sobrescribe "
            "la cabecera; sin él la confianza no está justificada."
        )
