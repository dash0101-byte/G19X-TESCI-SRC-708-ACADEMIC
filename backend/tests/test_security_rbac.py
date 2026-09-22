"""
Pruebas de autenticación y RBAC.

Antes, el rol llegaba en la cabecera `X-User-Role` y el backend se la creía: la suite
"probaba" el RBAC enviándose a sí misma el rol que quería. Estas pruebas verifican lo
contrario: que esas cabeceras ya no valen nada y que solo un JWT que este backend firmó
concede acceso.
"""
import base64
import datetime
import json

import jwt
import pytest
from app.core.config import settings
from app.core.security import TOKEN_TYPE_ACCESS
from tests.conftest import TEST_ACCOUNTS, TEST_PASSWORD

# Endpoints de datos que no deben responder jamás sin un token válido.
PROTECTED_ENDPOINTS = [
    ("get", "/api/v1/leads"),
    ("get", "/api/v1/leads/1"),
    ("get", "/api/v1/analytics/summary"),
    ("get", "/api/v1/analytics/campaigns"),
    ("post", "/api/v1/scoring/predict"),
    ("post", "/api/v1/leads/batch/recalculate-all"),
    ("post", "/api/v1/leads/1/recalculate-score"),
    ("delete", "/api/v1/leads/999999"),
]

# Cabeceras que el sistema aceptaba como identidad antes de la Fase 1.
SPOOFED_IDENTITY_HEADERS = {
    "X-User-Email": "atacante@evil.com",
    "X-User-Role": "System_Admin",
    "X-User-Name": "Administrador Falso",
    "X-Entra-User-Email": "atacante@evil.com",
    "X-Entra-User-Role": "System_Admin",
    "X-Entra-User-Name": "Administrador Falso",
    "X-Entra-Tenant-Id": "tenant-del-atacante",
}


def _call(client, method: str, path: str, headers: dict = None):
    """Invoca un endpoint; solo los POST llevan cuerpo, que GET y DELETE no admiten."""
    kwargs = {"headers": headers} if headers else {}
    if method == "post":
        kwargs["json"] = {}
    return client.request(method.upper(), path, **kwargs)


def _forge(claims: dict, key: str = None, algorithm: str = "HS256") -> str:
    """Fabrica un JWT arbitrario, por defecto con una clave que no es la del servidor."""
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": "1",
        "typ": TOKEN_TYPE_ACCESS,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int((now + datetime.timedelta(minutes=30)).timestamp()),
        "role": "System_Admin",
    }
    payload.update(claims)
    return jwt.encode(payload, key or "clave-que-el-atacante-eligio", algorithm=algorithm)


# ==============================================================================
# 1. Sin credenciales
# ==============================================================================

@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
def test_endpoints_protegidos_rechazan_peticion_anonima(client, method, path):
    """Ningún endpoint de datos responde sin autenticación."""
    response = _call(client, method, path)
    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"


# ==============================================================================
# 2. Cabeceras de identidad manipuladas
# ==============================================================================

@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
def test_cabeceras_de_identidad_falsificadas_no_conceden_acceso(client, method, path):
    """
    Declararse `System_Admin` por cabecera no autentica: es exactamente el vector que
    permitía a cualquiera operar como administrador antes de la Fase 1.
    """
    response = _call(client, method, path, headers=SPOOFED_IDENTITY_HEADERS)
    assert response.status_code == 401


def test_cabeceras_falsificadas_no_elevan_el_rol_de_un_usuario_autenticado(client, executive_headers):
    """
    Un asesor con token legítimo no gana privilegios adjuntando cabeceras de administrador:
    el rol se relee de la base de datos, no se toma de lo que diga el cliente.
    """
    headers = {**executive_headers, **SPOOFED_IDENTITY_HEADERS}
    response = client.post("/api/v1/leads/batch/recalculate-all", headers=headers)
    assert response.status_code == 403
    assert "no tiene privilegios suficientes" in response.json()["detail"]


# ==============================================================================
# 3. Tokens forjados o manipulados
# ==============================================================================

def test_token_firmado_con_otra_clave_es_rechazado(client):
    """Un token con los claims correctos pero firmado con otra clave no vale."""
    token = _forge({"role": "System_Admin"})
    response = client.post(
        "/api/v1/leads/batch/recalculate-all", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


def test_token_con_algoritmo_none_es_rechazado(client):
    """
    El ataque `alg: none`: un token sin firma que muchas implementaciones laxas aceptan.
    """
    # Se construye a mano, sin la biblioteca de JWT: es exactamente lo que haría un atacante
    # partiendo de un token capturado, y no depende de lo que la biblioteca deje emitir.
    def b64(data: dict) -> str:
        raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")

    header = b64({"alg": "none", "typ": "JWT"})
    claims = b64(
        {
            "sub": "1",
            "typ": TOKEN_TYPE_ACCESS,
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "role": "System_Admin",
            "exp": int(
                (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30)).timestamp()
            ),
        }
    )
    # Firma vacía, tal y como exige el formato `alg: none`
    token = f"{header}.{claims}."
    response = client.get("/api/v1/leads", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_token_con_firma_alterada_es_rechazado(client, executive_headers):
    """Modificar un solo carácter de la firma de un token legítimo lo invalida."""
    valid = executive_headers["Authorization"].split(" ", 1)[1]
    head, payload, signature = valid.split(".")
    tampered_sig = ("A" if signature[0] != "A" else "B") + signature[1:]
    response = client.get(
        "/api/v1/leads", headers={"Authorization": f"Bearer {head}.{payload}.{tampered_sig}"}
    )
    assert response.status_code == 401


def test_payload_alterado_para_escalar_rol_es_rechazado(client, executive_headers):
    """
    Reescribir el claim `role` a `System_Admin` conservando la firma original rompe la
    verificación: el payload y la firma dejan de corresponderse.
    """
    valid = executive_headers["Authorization"].split(" ", 1)[1]
    claims = jwt.decode(valid, options={"verify_signature": False})
    claims["role"] = "System_Admin"
    signature = valid.split(".")[2]
    forged_body = jwt.encode(claims, "otra-clave", algorithm="HS256").rsplit(".", 1)[0]
    response = client.post(
        "/api/v1/leads/batch/recalculate-all",
        headers={"Authorization": f"Bearer {forged_body}.{signature}"},
    )
    assert response.status_code == 401


def test_token_expirado_es_rechazado(client):
    """Un token caducado, aun firmado con la clave correcta, no da acceso."""
    now = datetime.datetime.now(datetime.timezone.utc)
    token = jwt.encode(
        {
            "sub": "1",
            "typ": TOKEN_TYPE_ACCESS,
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "iat": int((now - datetime.timedelta(hours=2)).timestamp()),
            "exp": int((now - datetime.timedelta(hours=1)).timestamp()),
        },
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    response = client.get("/api/v1/leads", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_token_de_otro_emisor_o_audiencia_es_rechazado(client):
    """Un token firmado con nuestra clave pero emitido para otro servicio no se acepta."""
    for wrong in ({"iss": "otro-emisor"}, {"aud": "otra-audiencia"}):
        claims = {
            "sub": "1",
            "typ": TOKEN_TYPE_ACCESS,
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "exp": int(
                (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30)).timestamp()
            ),
        }
        claims.update(wrong)
        token = jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        response = client.get("/api/v1/leads", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401, f"aceptó un token con {wrong}"


def test_refresh_token_no_sirve_como_access_token(client):
    """
    La cookie de refresco es de vida larga; si valiera como credencial de API, ampliaría
    enormemente la ventana de un robo. El claim `typ` lo impide.
    """
    email, _ = TEST_ACCOUNTS["Sales_Lead"]
    login = client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert login.status_code == 200
    refresh_cookie = login.cookies.get(settings.REFRESH_COOKIE_NAME)
    assert refresh_cookie

    response = client.get("/api/v1/leads", headers={"Authorization": f"Bearer {refresh_cookie}"})
    assert response.status_code == 401


def test_token_de_usuario_inexistente_es_rechazado(client):
    """
    Un token perfectamente firmado cuyo `sub` no corresponde a ninguna cuenta se rechaza:
    la identidad se confirma contra la base de datos, no solo contra la firma.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    token = jwt.encode(
        {
            "sub": "99999999",
            "typ": TOKEN_TYPE_ACCESS,
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "role": "System_Admin",
            "exp": int((now + datetime.timedelta(minutes=30)).timestamp()),
        },
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    response = client.get("/api/v1/leads", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


@pytest.mark.parametrize(
    "header_value",
    ["", "Bearer", "Bearer ", "Basic dXNlcjpwYXNz", "no-es-un-token", "Bearer a.b.c"],
)
def test_cabecera_authorization_malformada_es_rechazada(client, header_value):
    """Cabeceras de autorización mal formadas producen 401, nunca un 500."""
    response = client.get("/api/v1/leads", headers={"Authorization": header_value})
    assert response.status_code == 401


# ==============================================================================
# 4. RBAC con credenciales legítimas
# ==============================================================================

def test_asesor_comercial_no_puede_recalcular_en_lote(client, executive_headers):
    """Un Asesor Comercial autenticado sigue sin poder disparar el recálculo masivo."""
    response = client.post("/api/v1/leads/batch/recalculate-all", headers=executive_headers)
    assert response.status_code == 403
    assert "no tiene privilegios suficientes" in response.json()["detail"]


def test_asesor_comercial_no_puede_eliminar(client, executive_headers, sample_lead):
    """
    El borrado sigue reservado a Líder Comercial y Administrador TI.

    La edición **ya no**: un asesor edita los prospectos que atiende, y esa asimetría es
    deliberada. Editar es reversible y queda en el historial de scores; borrar se lleva por
    delante actividades e historial en cascada, y eso no vuelve.
    """
    respuesta = client.delete(f"/api/v1/leads/{sample_lead.id}", headers=executive_headers)
    assert respuesta.status_code == 403
    assert "no tiene privilegios suficientes" in respuesta.json()["detail"]


def test_un_asesor_no_ve_un_prospecto_ajeno_y_recibe_404(client, executive_headers, sample_lead):
    """
    Un prospecto que no es suyo responde 404, no 403.

    Un 403 confirmaría que ese identificador corresponde a un prospecto real, y recorrer
    identificadores es barato: distinguir «no existe» de «no es tuyo» permite dibujar el
    tamaño y la forma de la cartera ajena sin ver un solo dato.
    """
    assert client.get(f"/api/v1/leads/{sample_lead.id}", headers=executive_headers).status_code == 404
    assert client.put(
        f"/api/v1/leads/{sample_lead.id}", headers=executive_headers, json={"job_title": "X"}
    ).status_code == 404


def test_lider_y_admin_pueden_recalcular_en_lote(client, lead_headers, admin_headers):
    """
    Líder Comercial y Administrador TI sí lanzan el recálculo masivo.

    El endpoint responde 202 y no 200: el recorrido ocurre en segundo plano y lo que se
    devuelve es el trabajo encolado, no su resultado.
    """
    for headers in (lead_headers, admin_headers):
        response = client.post("/api/v1/leads/batch/recalculate-all", headers=headers)
        assert response.status_code == 202
        assert response.json()["id"]


def test_el_recalculo_registra_al_usuario_real_no_al_declarado(client, lead_headers):
    """
    Quién pidió el trabajo sale del token, no de lo que el cliente afirme por cabecera.

    El campo pasó a llamarse `requested_by` y ahora se persiste en la fila del trabajo, así
    que la atribución sobrevive a la petición y sigue ahí para auditarla después.
    """
    headers = {**lead_headers, "X-User-Email": "atacante@evil.com"}
    response = client.post("/api/v1/leads/batch/recalculate-all", headers=headers)
    assert response.status_code == 202
    assert response.json()["requested_by"] == TEST_ACCOUNTS["Sales_Lead"][0]


def test_asesor_comercial_conserva_sus_permisos_de_lectura(client, executive_headers):
    """El endurecimiento no rompe la operación diaria del rol de menor privilegio."""
    assert client.get("/api/v1/leads?limit=5", headers=executive_headers).status_code == 200
    assert client.get("/api/v1/analytics/summary", headers=executive_headers).status_code == 200


# ==============================================================================
# 5. Login y ciclo de sesión
# ==============================================================================

def test_login_con_password_incorrecta_no_revela_si_el_email_existe(client):
    """El mensaje es idéntico para email inexistente y contraseña incorrecta."""
    email, _ = TEST_ACCOUNTS["Sales_Lead"]
    existing = client.post("/api/v1/auth/login", json={"email": email, "password": "PasswordIncorrecta1"})
    unknown = client.post(
        "/api/v1/auth/login", json={"email": "nadie@plurione.com", "password": "PasswordIncorrecta1"}
    )
    assert existing.status_code == unknown.status_code == 401
    assert existing.json()["detail"] == unknown.json()["detail"]


def test_login_no_expone_el_hash_ni_el_refresh_token_en_el_cuerpo(client):
    """
    El refresh token solo viaja en cookie HttpOnly: si apareciera en el JSON, cualquier
    XSS podría leerlo y quedarse con una sesión de larga duración.
    """
    email, _ = TEST_ACCOUNTS["Sales_Lead"]
    response = client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert "refresh_token" not in body
    assert "hashed_password" not in response.text
    assert "password" not in body["user"]

    cookie_header = response.headers.get("set-cookie", "")
    assert "httponly" in cookie_header.lower()
    assert "samesite=strict" in cookie_header.lower()


def test_logout_invalida_los_refresh_tokens_emitidos(client):
    """Tras cerrar sesión, la cookie de refresco previa deja de servir."""
    email, _ = TEST_ACCOUNTS["Commercial_Executive"]
    with client as session:
        login = session.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
        assert login.status_code == 200
        token = login.json()["access_token"]

        assert session.post("/api/v1/auth/refresh").status_code == 200
        assert session.post(
            "/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"}
        ).status_code == 200
        assert session.post("/api/v1/auth/refresh").status_code == 401


def test_me_devuelve_la_identidad_del_token(client, lead_headers):
    response = client.get("/api/v1/auth/me", headers=lead_headers)
    assert response.status_code == 200
    assert response.json()["email"] == TEST_ACCOUNTS["Sales_Lead"][0]
    assert response.json()["role"] == "Sales_Lead"
    assert "hashed_password" not in response.text
