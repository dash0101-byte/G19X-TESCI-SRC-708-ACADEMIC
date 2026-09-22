"""
Ciclo de vida de la identidad: el token no es la última palabra.

`get_current_user` recarga el usuario desde la base de datos en cada petición en vez de
confiar en el claim `role` del JWT. Hasta ahora esa afirmación solo se podía comprobar
leyendo el código: verificarla exige modificar cuentas —desactivarlas, degradarlas,
borrarlas— y la suite corría sobre la base de datos real, donde hacerlo habría dejado
usuarios rotos para el desarrollo local.

Con SQLite en memoria, estas pruebas son posibles y baratas. Cubren el escenario que de
verdad importa en producción: revocar privilegios a alguien que ya tiene un token válido
en la mano y que no caduca hasta dentro de quince minutos.
"""
import pytest
from app.models.entities import User
from tests.conftest import TEST_ACCOUNTS

BATCH_URL = "/api/v1/leads/batch/recalculate-all"
ME_URL = "/api/v1/auth/me"
LEADS_URL = "/api/v1/leads"


@pytest.fixture
def cuenta_del_lider(db_session):
    """
    Entrega la fila del Líder Comercial y restaura sus campos al terminar.

    Las cuentas sobreviven al vaciado entre pruebas —crearlas cuesta un hash bcrypt—, así
    que una prueba que las degrade debe dejarlas como estaban o contaminará a las demás.
    """
    email, _ = TEST_ACCOUNTS["Sales_Lead"]
    user = db_session.query(User).filter(User.email == email).one()
    original = {"role": user.role, "is_active": user.is_active, "full_name": user.full_name}

    yield user

    db_session.query(User).filter(User.email == email).update(original)
    db_session.commit()


def test_desactivar_la_cuenta_invalida_el_token_en_uso(client, lead_headers, cuenta_del_lider, db_session):
    """
    Dar de baja a alguien surte efecto en la siguiente petición, no cuando expire su token.

    Si la autorización se resolviera solo con la firma, un empleado que sale de la empresa
    conservaría acceso completo durante los quince minutos de vida del access token.
    """
    assert client.get(ME_URL, headers=lead_headers).status_code == 200

    cuenta_del_lider.is_active = False
    db_session.commit()

    assert client.get(ME_URL, headers=lead_headers).status_code == 401
    assert client.get(LEADS_URL, headers=lead_headers).status_code == 401


def test_reactivar_la_cuenta_devuelve_el_acceso(client, lead_headers, cuenta_del_lider, db_session):
    cuenta_del_lider.is_active = False
    db_session.commit()
    assert client.get(ME_URL, headers=lead_headers).status_code == 401

    cuenta_del_lider.is_active = True
    db_session.commit()
    assert client.get(ME_URL, headers=lead_headers).status_code == 200


def test_degradar_el_rol_retira_los_privilegios_del_token_ya_emitido(
    client, lead_headers, cuenta_del_lider, db_session
):
    """
    El token del Líder Comercial lleva `role: Sales_Lead` firmado por este backend.

    Aun así, degradarlo a Asesor le quita el recálculo masivo de inmediato: el rol que se
    evalúa es el de la base de datos, no el que viaja dentro del JWT.
    """
    assert client.post(BATCH_URL, headers=lead_headers).status_code == 202

    cuenta_del_lider.role = "Commercial_Executive"
    db_session.commit()

    respuesta = client.post(BATCH_URL, headers=lead_headers)
    assert respuesta.status_code == 403
    assert "no tiene privilegios suficientes" in respuesta.json()["detail"]


def test_promover_el_rol_concede_privilegios_sin_reiniciar_sesion(
    client, executive_headers, db_session
):
    """El caso simétrico: ascender a alguien no debería obligarle a volver a entrar."""
    email, _ = TEST_ACCOUNTS["Commercial_Executive"]
    usuario = db_session.query(User).filter(User.email == email).one()
    original = usuario.role
    try:
        assert client.post(BATCH_URL, headers=executive_headers).status_code == 403

        usuario.role = "Sales_Lead"
        db_session.commit()

        assert client.post(BATCH_URL, headers=executive_headers).status_code == 202
    finally:
        db_session.query(User).filter(User.email == email).update({"role": original})
        db_session.commit()


def test_borrar_la_cuenta_invalida_el_token(client, auth_headers, db_session):
    """
    Un token cuyo `sub` ya no existe se rechaza.

    Es el mismo control que la prueba del `sub` inventado, pero sobre el caso real: una
    cuenta que existía cuando se emitió el token y se eliminó después.
    """
    email, full_name = TEST_ACCOUNTS["System_Admin"]
    headers = auth_headers("System_Admin")
    assert client.get(ME_URL, headers=headers).status_code == 200

    usuario = db_session.query(User).filter(User.email == email).one()
    datos = {
        "email": usuario.email,
        "full_name": usuario.full_name,
        "role": usuario.role,
        "hashed_password": usuario.hashed_password,
        "is_active": usuario.is_active,
    }
    identificador = usuario.id
    db_session.delete(usuario)
    db_session.commit()
    try:
        assert client.get(ME_URL, headers=headers).status_code == 401
    finally:
        # Se restaura con el MISMO id: el `sub` del token cacheado apunta a él.
        db_session.add(User(id=identificador, **datos))
        db_session.commit()

    assert client.get(ME_URL, headers=headers).status_code == 200
    assert full_name


def test_los_datos_de_la_identidad_se_leen_de_la_base_no_del_token(
    client, lead_headers, cuenta_del_lider, db_session
):
    """`/auth/me` refleja el nombre actual de la cuenta, no el que había al firmar el token."""
    cuenta_del_lider.full_name = "Nombre Cambiado Después del Login"
    db_session.commit()

    respuesta = client.get(ME_URL, headers=lead_headers)
    assert respuesta.status_code == 200
    assert respuesta.json()["full_name"] == "Nombre Cambiado Después del Login"
