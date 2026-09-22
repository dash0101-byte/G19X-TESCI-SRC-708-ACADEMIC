"""
Capítulo 23: autenticación sin excepciones.

Dos huecos que quedaban escritos en §14.7 y §19.9:

* **Un access token sobrevivía a su revocación.** Cerrar sesión, cambiar o restablecer la
  contraseña, cambiar el rol o desactivar la cuenta cortaban la renovación, pero el access
  token ya emitido seguía valiendo hasta sus quince minutos. Ahora lleva `ver` y la
  resolución de identidad la compara con la cuenta, que ya leía en cada petición.
* **Una contraseña filtrada pasaba la política** con tal de medir 12 caracteres y combinar
  tres clases. Ahora se rechaza contra una lista local, sin servicio externo, en las tres
  puertas por las que se fija una: alta, cambio propio y restablecimiento.
"""
import datetime
import gzip
import hashlib
import json

import jwt
import pytest
from app.core import passwords
from app.core.config import settings
from app.core.passwords import (
    ARCHIVO_DE_FILTRADAS,
    LONGITUD_MINIMA,
    MANIFIESTO_DE_FILTRADAS,
    ListaDeFiltradasInvalida,
    contrasenas_filtradas,
    evaluar,
)
from app.core.security import TOKEN_TYPE_ACCESS
from app.models.entities import User
from tests.conftest import TEST_ACCOUNTS, TEST_PASSWORD

LOGIN = "/api/v1/auth/login"
PROTEGIDA = "/api/v1/leads"
USERS = "/api/v1/users"

# Filtradas reales que la política anterior aceptaba: 12 o más caracteres y al menos tres
# clases. Están en la lista generada; la prueba de abajo lo comprueba.
FILTRADA_QUE_CUMPLIA = "Password1234"
OTRA_FILTRADA = "1q2w3e4r5t6y"


def _usuario(db, rol: str) -> User:
    return db.query(User).filter(User.email == TEST_ACCOUNTS[rol][0]).first()


def _entrar(client, rol: str) -> dict:
    email, _ = TEST_ACCOUNTS[rol]
    respuesta = client.post(LOGIN, json={"email": email, "password": TEST_PASSWORD})
    assert respuesta.status_code == 200, respuesta.text
    return {"Authorization": f"Bearer {respuesta.json()['access_token']}"}


# ==============================================================================
# Revocación inmediata del access token
# ==============================================================================

def test_el_access_token_lleva_la_version_de_la_cuenta(client, db_session):
    cabeceras = _entrar(client, "Commercial_Executive")
    claims = jwt.decode(cabeceras["Authorization"].split()[1], options={"verify_signature": False})
    assert claims["ver"] == _usuario(db_session, "Commercial_Executive").token_version


def test_cerrar_sesion_invalida_el_access_token_ya_emitido(client):
    """El caso general de §14.7: el token robado ya no sobrevive al logout de su víctima."""
    cabeceras = _entrar(client, "Commercial_Executive")
    assert client.get(PROTEGIDA, headers=cabeceras).status_code == 200

    assert client.post("/api/v1/auth/logout", headers=cabeceras).status_code == 200

    assert client.get(PROTEGIDA, headers=cabeceras).status_code == 401


def test_cambiar_la_contrasena_invalida_el_access_token_ya_emitido(client):
    cabeceras = _entrar(client, "Commercial_Executive")
    respuesta = client.post(
        "/api/v1/auth/change-password",
        headers=cabeceras,
        json={"contrasena_actual": TEST_PASSWORD, "nueva_contrasena": "Girasol-Nocturno-31"},
    )
    assert respuesta.status_code == 200
    assert client.get(PROTEGIDA, headers=cabeceras).status_code == 401


@pytest.mark.parametrize(
    "operacion",
    ["cambio_de_rol", "desactivacion", "restablecimiento"],
)
def test_las_operaciones_del_administrador_invalidan_el_access_token_ya_emitido(
    client, db_session, admin_headers, operacion
):
    """
    Degradar, desactivar o restablecer se hace casi siempre porque se desconfía de quien
    tiene la sesión. Antes, esa sesión seguía operando hasta quince minutos.
    """
    cabeceras = _entrar(client, "Sales_Lead")
    victima = _usuario(db_session, "Sales_Lead")
    assert client.get(PROTEGIDA, headers=cabeceras).status_code == 200

    if operacion == "cambio_de_rol":
        respuesta = client.post(f"{USERS}/{victima.id}/role", params={"rol": "Commercial_Executive"}, headers=admin_headers)
    elif operacion == "desactivacion":
        respuesta = client.delete(f"{USERS}/{victima.id}", headers=admin_headers)
    else:
        respuesta = client.post(
            f"{USERS}/{victima.id}/reset-password", headers=admin_headers,
            json={"nueva_contrasena": "Bicicleta-Turquesa-2026"},
        )
    assert respuesta.status_code == 200, respuesta.text

    assert client.get(PROTEGIDA, headers=cabeceras).status_code == 401


def test_un_access_token_sin_version_no_vale(client, db_session):
    """Un token anterior al cambio, o fabricado sin `ver`, no se acepta como «versión 0»."""
    usuario = _usuario(db_session, "Commercial_Executive")
    ahora = datetime.datetime.now(datetime.timezone.utc)
    claims = {
        "sub": str(usuario.id), "typ": TOKEN_TYPE_ACCESS, "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE, "iat": int(ahora.timestamp()), "nbf": int(ahora.timestamp()),
        "exp": int((ahora + datetime.timedelta(minutes=10)).timestamp()), "jti": "a" * 32,
    }
    sin_version = jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    assert client.get(PROTEGIDA, headers={"Authorization": f"Bearer {sin_version}"}).status_code == 401

    con_version = jwt.encode({**claims, "ver": usuario.token_version}, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    assert client.get(PROTEGIDA, headers={"Authorization": f"Bearer {con_version}"}).status_code == 200


@pytest.mark.parametrize("falta", ["exp", "iat", "nbf", "jti"])
def test_un_token_sin_un_claim_obligatorio_no_vale(client, db_session, falta):
    """PyJWT solo comprueba un claim si viene: sin `require`, un token sin `exp` valdría siempre."""
    usuario = _usuario(db_session, "Commercial_Executive")
    ahora = datetime.datetime.now(datetime.timezone.utc)
    claims = {
        "sub": str(usuario.id), "typ": TOKEN_TYPE_ACCESS, "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE, "iat": int(ahora.timestamp()), "nbf": int(ahora.timestamp()),
        "exp": int((ahora + datetime.timedelta(minutes=10)).timestamp()), "jti": "b" * 32,
        "ver": usuario.token_version,
    }
    del claims[falta]
    token = jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    assert client.get(PROTEGIDA, headers={"Authorization": f"Bearer {token}"}).status_code == 401


# ==============================================================================
# Contraseñas filtradas
# ==============================================================================

def test_una_filtrada_que_cumplia_la_politica_se_rechaza():
    motivos = evaluar(FILTRADA_QUE_CUMPLIA)
    assert any("filtraciones" in m for m in motivos), motivos
    assert any("filtraciones" in m for m in evaluar(FILTRADA_QUE_CUMPLIA.upper()))
    assert evaluar("Rinoceronte-Marino-77") == []


@pytest.mark.parametrize("puerta", ["alta", "cambio_propio", "restablecimiento"])
def test_las_tres_puertas_rechazan_una_filtrada(client, db_session, admin_headers, auth_headers, puerta):
    if puerta == "alta":
        respuesta = client.post(USERS, headers=admin_headers, json={
            "email": "nueva.persona@plurione.com", "full_name": "Nueva Persona",
            "role": "Commercial_Executive", "password": OTRA_FILTRADA,
        })
    elif puerta == "cambio_propio":
        respuesta = client.post("/api/v1/auth/change-password", headers=auth_headers("Commercial_Executive"), json={
            "contrasena_actual": TEST_PASSWORD, "nueva_contrasena": FILTRADA_QUE_CUMPLIA,
        })
    else:
        victima = _usuario(db_session, "Commercial_Executive")
        respuesta = client.post(f"{USERS}/{victima.id}/reset-password", headers=admin_headers, json={
            "nueva_contrasena": FILTRADA_QUE_CUMPLIA,
        })
    assert respuesta.status_code == 422, respuesta.text
    assert any("filtraciones" in m for m in respuesta.json()["detail"]["motivos"])


def test_la_lista_es_la_del_manifiesto_y_no_lleva_lo_que_la_longitud_ya_rechaza():
    manifiesto = json.loads(MANIFIESTO_DE_FILTRADAS.read_text(encoding="utf-8"))
    datos = ARCHIVO_DE_FILTRADAS.read_bytes()
    assert hashlib.sha256(datos).hexdigest() == manifiesto["sha256"]

    entradas = contrasenas_filtradas()
    assert len(entradas) == manifiesto["entradas"] > 40000
    assert manifiesto["longitud_minima"] == LONGITUD_MINIMA, (
        "La lista se generó para otro mínimo: regenérela con scripts/generar_lista_de_contrasenas.py"
    )
    assert min(len(e) for e in entradas) >= LONGITUD_MINIMA
    assert all(e == passwords._normalizar(e) for e in entradas)
    assert {FILTRADA_QUE_CUMPLIA.lower(), OTRA_FILTRADA} <= entradas


def test_ninguna_contrasena_de_la_suite_esta_filtrada():
    """Si una lo estuviera, las pruebas que la usan fallarían por una razón que no es la suya."""
    for contrasena in (TEST_PASSWORD, "Rinoceronte-Marino-77", "Bicicleta-Turquesa-2026", "Girasol-Nocturno-31"):
        assert passwords._normalizar(contrasena) not in contrasenas_filtradas()


@pytest.mark.parametrize("manipulacion", ["vaciada", "sustituida_del_mismo_tamano"])
def test_una_lista_manipulada_no_se_usa_en_silencio(tmp_path, monkeypatch, manipulacion):
    """
    Vaciar o sustituir el archivo haría aceptar lo que se quisiera. Las dos formas, porque
    las detectan comprobaciones distintas: la vaciada, el recuento de entradas; la sustituida
    por otra del mismo tamaño —una entrada cambiada—, solo la huella.
    """
    entradas = sorted(contrasenas_filtradas())
    if manipulacion == "vaciada":
        contenido = b"\n"
    else:
        entradas[entradas.index(FILTRADA_QUE_CUMPLIA.lower())] = "otra-cualquiera-que-nadie-uso"
        contenido = ("\n".join(sorted(entradas)) + "\n").encode("utf-8")
    manipulada = tmp_path / "filtradas.txt.gz"
    manipulada.write_bytes(gzip.compress(contenido))
    monkeypatch.setattr(passwords, "ARCHIVO_DE_FILTRADAS", manipulada)
    contrasenas_filtradas.cache_clear()
    try:
        with pytest.raises(ListaDeFiltradasInvalida):
            contrasenas_filtradas()
        with pytest.raises(ListaDeFiltradasInvalida):
            evaluar("Rinoceronte-Marino-77")
    finally:
        monkeypatch.undo()
        contrasenas_filtradas.cache_clear()


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("ℌola-Mundo-2026", "hola-mundo-2026"),
        ("ＰＡＳＳＷＯＲＤ１２３４", "password1234"),
        ("Contraseña-Segura", "contrasena-segura"),
    ],
)
def test_normalizar_descompone_antes_de_pasar_a_minusculas(texto, esperado):
    """
    NFKD convierte algunos signos en mayúsculas (`ℌ` → `H`, la `Ｐ` de ancho completo → `P`).
    Pasando a minúsculas antes, la normalización no sería idempotente y una filtrada escrita
    con esos caracteres esquivaría la lista.
    """
    assert passwords._normalizar(texto) == esperado
    assert passwords._normalizar(passwords._normalizar(texto)) == esperado


def test_una_filtrada_escrita_en_ancho_completo_tambien_se_rechaza():
    assert any("filtraciones" in m for m in evaluar("ＰＡＳＳＷＯＲＤ１２３４"))
