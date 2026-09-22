"""
Rotación de tokens de refresco con detección de reutilización (N-1).

Lo que se prueba aquí es que la rotación **sirva**, no que ocurra. La versión anterior
rotaba en apariencia: `/auth/refresh` entregaba una cookie nueva, pero la anterior seguía
validando hasta expirar, porque lo único que se comprobaba era `token_version`, que solo
cambia al cerrar sesión. Una prueba que se limitara a comparar «la cookie nueva es
distinta de la vieja» habría pasado en verde sobre aquel código.

La prueba que de verdad separa una implementación de la otra es la de reutilización: si
alguien revierte el arreglo, `test_reutilizar_un_token_consumido_cierra_la_sesion` falla,
porque el token viejo volverá a servir.
"""
import pytest
from app.core.config import settings
from app.core.security import TOKEN_TYPE_REFRESH, create_refresh_token, decode_token
from app.main import app
from app.models.entities import AuditLog, RefreshToken, User
from app.services.session_service import (
    MOTIVO_REUTILIZADO,
    MOTIVO_ROTADO,
    abrir_sesion,
    cerrar_sesiones_del_usuario,
    estado_de_la_familia,
    purgar_tokens_caducados,
)
from fastapi.testclient import TestClient
from tests.conftest import TEST_ACCOUNTS, TEST_PASSWORD

LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"  # noqa: S105  ruta HTTP, no una credencial
LOGOUT = "/api/v1/auth/logout"
COOKIE = settings.REFRESH_COOKIE_NAME


def _iniciar_sesion(rol: str = "Sales_Lead"):
    """Abre una sesión real y devuelve el cliente y su cookie de refresco."""
    email, _ = TEST_ACCOUNTS[rol]
    cliente = TestClient(app)
    respuesta = cliente.post(LOGIN, json={"email": email, "password": TEST_PASSWORD})
    assert respuesta.status_code == 200, respuesta.text
    cookie = cliente.cookies.get(COOKIE)
    assert cookie, "El login debe dejar la cookie de refresco."
    return cliente, cookie


def _cliente_con(cookie: str) -> TestClient:
    """Un cliente que presenta exactamente esta cookie y ninguna otra."""
    return TestClient(app, cookies={COOKIE: cookie})


def _jti(token: str) -> str:
    return decode_token(token, TOKEN_TYPE_REFRESH)["jti"]


def _familia(token: str) -> str:
    return decode_token(token, TOKEN_TYPE_REFRESH)["fid"]


# ==============================================================================
# Emisión y rotación
# ==============================================================================

def test_el_login_registra_el_token_emitido(db_session):
    """
    Un refresh token que no consta en la tabla no se puede consumir.

    Es el cimiento de todo lo demás: sin registro no hay nada que marcar como usado, y sin
    eso la detección de reutilización no tiene sobre qué apoyarse.
    """
    _, cookie = _iniciar_sesion()

    registro = db_session.query(RefreshToken).filter(RefreshToken.jti == _jti(cookie)).first()
    assert registro is not None, "El login debe dejar constancia del token que emitió."
    assert registro.revoked_at is None
    assert registro.family_id == _familia(cookie)


def test_el_refresco_rota_el_token_y_consume_el_anterior(db_session):
    cliente, primera = _iniciar_sesion()

    respuesta = cliente.post(REFRESH)
    assert respuesta.status_code == 200, respuesta.text
    segunda = cliente.cookies.get(COOKIE)

    assert primera != segunda, "El refresco debe entregar un token distinto."
    assert _familia(primera) == _familia(segunda), "La familia se conserva durante la sesión."

    anterior = db_session.query(RefreshToken).filter(RefreshToken.jti == _jti(primera)).first()
    nuevo = db_session.query(RefreshToken).filter(RefreshToken.jti == _jti(segunda)).first()

    # Esta es la aserción que la implementación anterior no pasaba: entregaba un token
    # nuevo sin invalidar el viejo.
    assert anterior.revoked_at is not None, "El token presentado debe quedar consumido."
    assert anterior.revoked_reason == MOTIVO_ROTADO
    assert anterior.replaced_by_jti == nuevo.jti
    assert nuevo.revoked_at is None


def test_la_familia_conserva_un_unico_token_vigente(db_session):
    """
    Sin este invariante la detección no probaría nada: si una familia pudiera tener dos
    tokens vivos, presentar uno consumido dejaría de ser señal de que hay dos copias.
    """
    cliente, primera = _iniciar_sesion()
    for _ in range(3):
        assert cliente.post(REFRESH).status_code == 200

    total, vigentes = estado_de_la_familia(db_session, _familia(primera))
    assert total == 4, "Cada refresco deja su emisión registrada."
    assert vigentes == 1, "Solo el último token de la cadena puede seguir vivo."


# ==============================================================================
# Detección de reutilización
# ==============================================================================

def test_reutilizar_un_token_consumido_cierra_la_sesion(db_session, monkeypatch):
    """
    El caso que motiva toda la fase: dos partes con la misma cookie.

    Si alguien revierte la rotación, el token consumido vuelve a servir y esta prueba
    falla con un 200 donde espera un 401.
    """
    # Sin gracia: aquí no se está simulando la carrera de dos pestañas, sino un robo.
    monkeypatch.setattr(settings, "REFRESH_ROTATION_GRACE_SECONDS", 0)

    victima, robada = _iniciar_sesion()
    assert victima.post(REFRESH).status_code == 200
    vigente = victima.cookies.get(COOKIE)

    atacante = _cliente_con(robada)
    respuesta = atacante.post(REFRESH)

    assert respuesta.status_code == 401, "Un token ya consumido no puede volver a servir."
    assert "seguridad" in respuesta.json()["detail"].lower()

    # Y la sesión legítima cae también: no hay forma de saber cuál de las dos partes es la
    # buena, así que las dos vuelven a autenticarse.
    assert _cliente_con(vigente).post(REFRESH).status_code == 401

    tokens = (
        db_session.query(RefreshToken)
        .filter(RefreshToken.family_id == _familia(robada))
        .all()
    )
    assert tokens, "La familia debe seguir registrada tras revocarse."
    assert all(t.revoked_at is not None for t in tokens)
    assert any(t.revoked_reason == MOTIVO_REUTILIZADO for t in tokens)


def test_la_reutilizacion_no_arrastra_a_las_demas_sesiones(db_session, monkeypatch):
    """
    Revocar la familia comprometida no debe cerrar la sesión del teléfono.

    Se comprueba con el servicio y no con el endpoint a propósito: el `logout` incrementa
    además `token_version`, que sí cierra todo, y eso taparía el comportamiento que aquí
    interesa aislar.
    """
    monkeypatch.setattr(settings, "REFRESH_ROTATION_GRACE_SECONDS", 0)
    usuario = db_session.query(User).filter(User.email == TEST_ACCOUNTS["Sales_Lead"][0]).first()

    portatil = abrir_sesion(db_session, usuario, "10.0.0.1")
    telefono = abrir_sesion(db_session, usuario, "10.0.0.2")
    assert _familia(portatil) != _familia(telefono), "Cada login abre su propia familia."

    # Se compromete la del portátil: se consume y se reutiliza.
    cliente = _cliente_con(portatil)
    assert cliente.post(REFRESH).status_code == 200
    assert _cliente_con(portatil).post(REFRESH).status_code == 401

    _, vigentes_telefono = estado_de_la_familia(db_session, _familia(telefono))
    assert vigentes_telefono == 1, "La sesión del otro dispositivo no debe verse afectada."


def test_dos_pestanas_refrescando_a_la_vez_no_cierran_la_sesion():
    """
    La carrera honesta: el cliente deduplica dentro de una pestaña, no entre pestañas.

    Con detección estricta, la segunda pestaña llegaría con un token que la primera acaba
    de consumir y expulsaría de su sesión a alguien que no hizo nada. La ventana de gracia
    —diez segundos por defecto— es lo que separa una medida que se sostiene de una que se
    acaba desactivando por molesta.
    """
    assert settings.REFRESH_ROTATION_GRACE_SECONDS > 0, (
        "Con la gracia a cero, un usuario con dos pestañas pierde la sesión sin motivo."
    )

    primera_pestana, cookie = _iniciar_sesion()
    assert primera_pestana.post(REFRESH).status_code == 200

    segunda_pestana = _cliente_con(cookie)
    respuesta = segunda_pestana.post(REFRESH)

    assert respuesta.status_code == 200, (
        "Un refresco simultáneo dentro de la ventana de gracia es una carrera del cliente, "
        "no una reutilización."
    )


def test_un_token_firmado_pero_no_registrado_no_sirve(db_session):
    """
    Firma válida no es lo mismo que emisión válida.

    Sin la tabla, cualquier token con firma correcta y sin expirar servía. Ahora la firma
    es condición necesaria y el registro es la suficiente.
    """
    usuario = db_session.query(User).filter(User.email == TEST_ACCOUNTS["Sales_Lead"][0]).first()
    inventado = create_refresh_token(usuario, jti="0" * 32, family_id="f" * 32)

    respuesta = _cliente_con(inventado).post(REFRESH)
    assert respuesta.status_code == 401


# ==============================================================================
# Cierre de sesión y mantenimiento
# ==============================================================================

def test_el_logout_revoca_las_familias_vivas(db_session):
    cliente, cookie = _iniciar_sesion("Commercial_Executive")
    acceso = cliente.post(
        LOGIN, json={"email": TEST_ACCOUNTS["Commercial_Executive"][0], "password": TEST_PASSWORD}
    ).json()["access_token"]

    respuesta = cliente.post(LOGOUT, headers={"Authorization": f"Bearer {acceso}"})
    assert respuesta.status_code == 200

    vigentes = (
        db_session.query(RefreshToken)
        .filter(RefreshToken.revoked_at.is_(None))
        .count()
    )
    assert vigentes == 0, "Cerrar sesión no puede dejar tokens de refresco vivos."
    assert _cliente_con(cookie).post(REFRESH).status_code == 401


def test_cerrar_sesiones_devuelve_cuantas_cayeron(db_session):
    usuario = db_session.query(User).filter(User.email == TEST_ACCOUNTS["System_Admin"][0]).first()
    abrir_sesion(db_session, usuario)
    abrir_sesion(db_session, usuario)

    assert cerrar_sesiones_del_usuario(db_session, usuario.id) == 2
    db_session.commit()
    assert cerrar_sesiones_del_usuario(db_session, usuario.id) == 0


def test_la_purga_respeta_el_margen_de_conservacion(db_session):
    """
    Un token revocado por reutilización es la prueba de un incidente.

    Borrarlo el día en que caduca destruiría el rastro justo cuando alguien podría estar
    buscándolo; por eso la purga solo alcanza lo vencido hace tiempo.
    """
    import datetime

    usuario = db_session.query(User).filter(User.email == TEST_ACCOUNTS["Sales_Lead"][0]).first()
    ahora = datetime.datetime.now(datetime.timezone.utc)

    reciente = RefreshToken(
        jti="a" * 32, family_id="b" * 32, user_id=usuario.id,
        issued_at=ahora, expires_at=ahora - datetime.timedelta(days=1),
    )
    antiguo = RefreshToken(
        jti="c" * 32, family_id="d" * 32, user_id=usuario.id,
        issued_at=ahora, expires_at=ahora - datetime.timedelta(days=90),
    )
    db_session.add_all([reciente, antiguo])
    db_session.commit()

    assert purgar_tokens_caducados(db_session, margen_dias=30) == 1
    quedan = {t.jti for t in db_session.query(RefreshToken).all()}
    assert "a" * 32 in quedan, "Lo vencido ayer todavía puede hacer falta para investigar."
    assert "c" * 32 not in quedan


# ==============================================================================
# Rastro en la bitácora
# ==============================================================================

def test_la_reutilizacion_queda_en_la_bitacora(db_session, monkeypatch):
    """
    Detectarlo y no dejarlo escrito serviría de poco: el incidente ocurre una vez y quien
    lo investiga llega después.
    """
    monkeypatch.setattr(settings, "REFRESH_ROTATION_GRACE_SECONDS", 0)

    cliente, robada = _iniciar_sesion()
    assert cliente.post(REFRESH).status_code == 200
    assert _cliente_con(robada).post(REFRESH).status_code == 401

    asiento = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "auth.refresh_reutilizado")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert asiento is not None, "La reutilización debe quedar registrada."
    assert asiento.actor_email == TEST_ACCOUNTS["Sales_Lead"][0]
    assert asiento.entity_id == _familia(robada)
    assert asiento.event_metadata.get("tokens_revocados", 0) >= 1


@pytest.mark.parametrize("ruta", [REFRESH, LOGOUT])
def test_sin_cookie_ni_token_no_se_renueva_nada(ruta):
    """Comprobación de que ninguna de las dos rutas es alcanzable sin credencial."""
    respuesta = TestClient(app).post(ruta)
    assert respuesta.status_code == 401
