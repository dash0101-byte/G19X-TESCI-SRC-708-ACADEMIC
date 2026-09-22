"""
N-24: la contraseña prestada se impone en el servidor (§15.8.3).

Una cuenta recién creada, restablecida o reactivada entra con una contraseña que fijó otra
persona. La marca `must_change_password` se guardaba desde la Fase 9 y la interfaz la
enseñaba, pero el backend dejaba operar igual: se podía trabajar indefinidamente con la
contraseña que conoce el administrador. El capítulo 15 lo dejó dicho y no hecho.

La prueba que sostiene el arreglo no enumera rutas a mano. Recorre las rutas registradas en
la aplicación, se queda con las que dependen de la identidad autenticada y exige que TODAS
rechacen a la cuenta marcada. Así, un endpoint que se añada mañana queda cubierto sin que
nadie se acuerde de añadirlo aquí, que es la misma razón por la que el bloqueo vive en la
dependencia por defecto y no en una lista.
"""
import re

import pytest
from app.core.security import (
    CODIGO_CAMBIO_OBLIGATORIO,
    get_current_user,
    get_current_user_con_contrasena_prestada,
)
from app.main import app
from app.models.entities import User
from fastapi.routing import APIRoute
from tests.conftest import TEST_ACCOUNTS, TEST_PASSWORD

LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"
CAMBIO = "/api/v1/auth/change-password"
SALIR = "/api/v1/auth/logout"
NUEVA = "Rompeolas-Lejano-2026"


def _depende_de(dependant, llamada) -> bool:
    return any(d.call is llamada or _depende_de(d, llamada) for d in dependant.dependencies)


def _recorrer(rutas, prefijo=""):
    """
    Todas las rutas de la aplicación, con su ruta efectiva.

    Hasta FastAPI 0.13x `include_router` copiaba las rutas a `app.routes` con el prefijo ya
    puesto. La versión instalada las deja dentro de un `_IncludedRouter` que guarda el
    router original y el prefijo aparte: recorrer solo `app.routes` devolvía una lista
    VACÍA, y la prueba paramétrica de abajo salía verde sin comprobar nada. Así se detectó.
    Estos atributos son internos; la prueba de la documentación de abajo es la que avisa si
    vuelven a cambiar.
    """
    for ruta in rutas:
        if isinstance(ruta, APIRoute):
            for metodo in sorted(ruta.methods):
                yield metodo, prefijo + ruta.path, ruta
        contexto = getattr(ruta, "include_context", None)
        if contexto is not None:
            yield from _recorrer(ruta.original_router.routes, prefijo + contexto.prefix)


def _rutas_que_dependen_de(llamada):
    return sorted(
        (metodo, ruta) for metodo, ruta, objeto in _recorrer(app.routes)
        if _depende_de(objeto.dependant, llamada)
    )


def _concreta(plantilla: str) -> str:
    return re.sub(r"\{[^}]+\}", "1", plantilla)


RUTAS_CERRADAS = _rutas_que_dependen_de(get_current_user)


@pytest.fixture
def prestada(db_session):
    """El asesor de la suite, con la marca puesta. `conftest` la retira al terminar."""
    usuario = (
        db_session.query(User)
        .filter(User.email == TEST_ACCOUNTS["Commercial_Executive"][0])
        .first()
    )
    usuario.must_change_password = True
    db_session.commit()
    return usuario


# ==============================================================================
# Qué queda cerrado
# ==============================================================================

def test_la_enumeracion_ve_las_mismas_rutas_que_la_documentacion():
    """
    El recorrido de rutas se contrasta con una fuente pública: el esquema OpenAPI.

    Sin esto, la prueba paramétrica de abajo puede quedarse sin casos y salir verde, que es
    exactamente lo que pasó la primera vez (véase `_recorrer`).
    """
    documentadas = {
        (metodo.upper(), ruta)
        for ruta, operaciones in app.openapi()["paths"].items()
        for metodo in operaciones
    }
    recorridas = {
        (metodo, ruta) for metodo, ruta, objeto in _recorrer(app.routes) if objeto.include_in_schema
    }
    assert recorridas == documentadas


def test_la_enumeracion_no_esta_vacia():
    """
    Si alguien desenganchara las rutas de `get_current_user` —o cambiara la forma de
    resolver la identidad—, la lista se vaciaría y nada fallaría. El número es el orden de
    magnitud actual, no un objetivo.
    """
    assert len(RUTAS_CERRADAS) >= 25, RUTAS_CERRADAS


@pytest.mark.parametrize(
    ("metodo", "ruta"), RUTAS_CERRADAS, ids=[f"{m} {r}" for m, r in RUTAS_CERRADAS]
)
def test_ninguna_ruta_opera_con_la_contrasena_prestada(
    client, executive_headers, prestada, metodo, ruta
):
    respuesta = client.request(metodo, _concreta(ruta), headers=executive_headers, json={})

    assert respuesta.status_code == 403, (
        f"{metodo} {ruta} respondió {respuesta.status_code} a una cuenta con contraseña "
        "prestada. Debe rechazarla hasta que la cambie."
    )
    assert respuesta.json()["detail"]["codigo"] == CODIGO_CAMBIO_OBLIGATORIO


def test_la_excepcion_la_piden_exactamente_tres_rutas():
    """
    La lista de lo que una cuenta marcada SÍ puede hacer: saber quién es, cambiarla y salir.

    Una cuarta ruta aquí es una puerta abierta que nadie ha decidido abrir, y tiene que
    romper esta prueba para que alguien lo decida.
    """
    assert _rutas_que_dependen_de(get_current_user_con_contrasena_prestada) == sorted(
        [("GET", ME), ("POST", CAMBIO), ("POST", SALIR)]
    )


def test_el_rechazo_no_distingue_de_roles(client, admin_headers, db_session):
    """Tampoco el administrador opera con una contraseña que conoce otra persona."""
    admin = (
        db_session.query(User).filter(User.email == TEST_ACCOUNTS["System_Admin"][0]).first()
    )
    admin.must_change_password = True
    db_session.commit()

    respuesta = client.get("/api/v1/users", headers=admin_headers)
    assert respuesta.status_code == 403
    assert respuesta.json()["detail"]["codigo"] == CODIGO_CAMBIO_OBLIGATORIO


def test_restablecer_la_contrasena_deja_sin_uso_los_tokens_ya_emitidos(
    client, admin_headers, executive_headers, db_session
):
    """
    Restablecer la contraseña deja sin uso los tokens que ya circulaban.

    En §19.2 era una consecuencia que no se buscaba: la cuenta quedaba marcada como
    prestada y la resolución de identidad devolvía 403 «cambie la contraseña» a esos tokens.
    Desde el capítulo 23 es más estricto y más directo: el restablecimiento sube
    `token_version`, el access token lleva la versión con la que se emitió, y la resolución
    de identidad lo rechaza con 401 antes de mirar la marca. Ni siquiera sirve ya para
    llegar a la pantalla de cambio.
    """
    victima = (
        db_session.query(User)
        .filter(User.email == TEST_ACCOUNTS["Commercial_Executive"][0])
        .first()
    )
    assert client.get("/api/v1/leads", headers=executive_headers).status_code == 200

    restablecimiento = client.post(
        f"/api/v1/users/{victima.id}/reset-password",
        headers=admin_headers,
        json={"nueva_contrasena": "Fijada-Por-Administracion-77"},
    )
    assert restablecimiento.status_code == 200, restablecimiento.text

    despues = client.get("/api/v1/leads", headers=executive_headers)
    assert despues.status_code == 401
    assert client.get("/api/v1/auth/me", headers=executive_headers).status_code == 401

    intento = client.post(
        CAMBIO,
        headers=executive_headers,
        json={"contrasena_actual": TEST_PASSWORD, "nueva_contrasena": NUEVA},
    )
    assert intento.status_code == 401


# ==============================================================================
# Qué puede hacer mientras tanto, y cómo sale de ahí
# ==============================================================================

def test_el_login_avisa_de_la_contrasena_prestada(client, prestada):
    """El cliente necesita saberlo al entrar, no al recibir el primer 403."""
    respuesta = client.post(LOGIN, json={"email": prestada.email, "password": TEST_PASSWORD})
    assert respuesta.status_code == 200
    assert respuesta.json()["user"]["must_change_password"] is True


def test_puede_consultar_quien_es(client, executive_headers, prestada):
    respuesta = client.get(ME, headers=executive_headers)
    assert respuesta.status_code == 200
    assert respuesta.json()["must_change_password"] is True


def test_puede_cerrar_la_sesion(client, executive_headers, prestada):
    assert client.post(SALIR, headers=executive_headers).status_code == 200


def test_al_cambiarla_recupera_el_acceso(client, executive_headers, prestada):
    cambio = client.post(
        CAMBIO,
        headers=executive_headers,
        json={"contrasena_actual": TEST_PASSWORD, "nueva_contrasena": NUEVA},
    )
    assert cambio.status_code == 200, cambio.text

    entrada = client.post(LOGIN, json={"email": prestada.email, "password": NUEVA})
    assert entrada.status_code == 200
    assert entrada.json()["user"]["must_change_password"] is False

    token = {"Authorization": f"Bearer {entrada.json()['access_token']}"}
    assert client.get("/api/v1/leads", headers=token).status_code == 200


def test_una_cuenta_recien_creada_no_opera_hasta_cambiarla(client, admin_headers):
    """
    El origen real de la marca, de punta a punta: el administrador da de alta a alguien
    con una contraseña que él conoce, y esa persona entra con ella.
    """
    prestada = "Prestada-Por-Otro-2026"
    alta = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "email": "recien.llegada@plurione.com",
            "full_name": "Persona Recién Incorporada",
            "role": "Sales_Lead",
            "password": prestada,
        },
    )
    assert alta.status_code == 201, alta.text

    entrada = client.post(
        LOGIN, json={"email": "recien.llegada@plurione.com", "password": prestada}
    )
    assert entrada.status_code == 200
    token = {"Authorization": f"Bearer {entrada.json()['access_token']}"}

    bloqueo = client.get("/api/v1/leads", headers=token)
    assert bloqueo.status_code == 403
    assert bloqueo.json()["detail"]["codigo"] == CODIGO_CAMBIO_OBLIGATORIO
