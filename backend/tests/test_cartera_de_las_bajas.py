"""
N-25: la cartera de quien se va (§15.8.4).

Dar de baja una cuenta conserva sus prospectos a su nombre, y eso es deliberado: repartirlos
solos sería decidir sin nadie que decida. Pero la decisión tenía una segunda mitad que no
existía. No había forma de repartirlos salvo editando prospecto a prospecto, y la vista por
defecto del equipo oculta las bajas, así que la cartera de quien se fue desaparecía de la
pantalla justo donde había que verla. Un prospecto caliente asignado a una cuenta que ya no
entra no lo atiende nadie, y la autoasignación no lo rescata: solo reparte los que no tienen
dueño.
"""
import pytest
from app.models.entities import AuditLog, Lead, User
from tests.conftest import TEST_ACCOUNTS

ASESORES = "/api/v1/sales-reps"
USERS = "/api/v1/users"


def _dar_de_baja(client, admin_headers, user_id):
    respuesta = client.delete(f"{USERS}/{user_id}", headers=admin_headers)
    assert respuesta.status_code == 200, respuesta.text


def _repartir(client, headers, origen_id, destino_id):
    return client.post(
        f"{ASESORES}/{origen_id}/cartera", headers=headers, json={"destino_id": destino_id}
    )


def _asignados(db, user_id) -> int:
    db.expire_all()
    return db.query(Lead).filter(Lead.assigned_rep_id == user_id).count()


# ==============================================================================
# Verla
# ==============================================================================

def test_la_cartera_de_las_bajas_se_cuenta_aunque_el_listado_las_oculte(
    client, admin_headers, lead_headers, cartera_repartida
):
    _, ajenos = cartera_repartida
    dueno = ajenos[0].assigned_rep_id

    assert client.get(ASESORES, headers=lead_headers).json()["prospectos_en_cuentas_de_baja"] == 0

    _dar_de_baja(client, admin_headers, dueno)
    cuerpo = client.get(ASESORES, headers=lead_headers).json()

    assert dueno not in [a["id"] for a in cuerpo["items"]], "la vista por defecto oculta las bajas"
    assert cuerpo["prospectos_en_cuentas_de_baja"] == len(ajenos)


# ==============================================================================
# Repartirla
# ==============================================================================

def test_el_lider_reparte_la_cartera_de_una_baja(
    client, admin_headers, lead_headers, cartera_repartida, sales_reps, db_session
):
    _, ajenos = cartera_repartida
    dueno = ajenos[0].assigned_rep_id
    destino = sales_reps[0]
    _dar_de_baja(client, admin_headers, dueno)

    respuesta = _repartir(client, lead_headers, dueno, destino.id)

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["movidos"] == len(ajenos)
    assert cuerpo["carga_del_destino"] == len(ajenos)
    assert cuerpo["supera_capacidad"] is False

    assert _asignados(db_session, dueno) == 0
    assert _asignados(db_session, destino.id) == len(ajenos)
    assert client.get(ASESORES, headers=lead_headers).json()["prospectos_en_cuentas_de_baja"] == 0


def test_solo_se_mueve_la_cartera_de_esa_cuenta(
    client, lead_headers, cartera_repartida, sales_reps, db_session
):
    propios, ajenos = cartera_repartida
    asesor = propios[0].assigned_rep_id

    assert _repartir(client, lead_headers, ajenos[0].assigned_rep_id, sales_reps[1].id).status_code == 200
    assert _asignados(db_session, asesor) == len(propios)


def test_el_reparto_queda_en_la_bitacora(
    client, lead_headers, cartera_repartida, sales_reps, db_session
):
    _, ajenos = cartera_repartida
    destino = sales_reps[0]
    assert _repartir(client, lead_headers, ajenos[0].assigned_rep_id, destino.id).status_code == 200

    db_session.expire_all()
    asiento = (
        db_session.query(AuditLog).filter(AuditLog.action == "usuario.reparto_de_cartera").one()
    )
    assert asiento.event_metadata["movidos"] == len(ajenos)
    assert asiento.event_metadata["destino_email"] == destino.email


def test_avisa_si_el_destino_queda_por_encima_de_su_capacidad(
    client, lead_headers, cartera_repartida, sales_reps, db_session
):
    """
    No se bloquea: cargar de más a alguien durante una semana puede ser la decisión
    correcta. Se dice, para que sea una decisión y no un descuido.
    """
    _, ajenos = cartera_repartida
    destino = sales_reps[1]
    destino.capacity = 2
    db_session.commit()

    respuesta = _repartir(client, lead_headers, ajenos[0].assigned_rep_id, destino.id)

    assert respuesta.status_code == 200
    assert respuesta.json()["supera_capacidad"] is True


# ==============================================================================
# A quién no
# ==============================================================================

def test_no_se_reparte_a_otra_baja(
    client, admin_headers, lead_headers, cartera_repartida, sales_reps, db_session
):
    """Traspasar a otra cuenta de baja movería el problema en vez de resolverlo."""
    _, ajenos = cartera_repartida
    dueno = ajenos[0].assigned_rep_id
    _dar_de_baja(client, admin_headers, sales_reps[0].id)

    assert _repartir(client, lead_headers, dueno, sales_reps[0].id).status_code == 422
    assert _asignados(db_session, dueno) == len(ajenos)


def test_no_se_reparte_a_quien_no_atiende_cartera(
    client, lead_headers, cartera_repartida, db_session
):
    """Los prospectos quedarían fuera de toda vista de asesor."""
    _, ajenos = cartera_repartida
    dueno = ajenos[0].assigned_rep_id
    lider = (
        db_session.query(User).filter(User.email == TEST_ACCOUNTS["Sales_Lead"][0]).first()
    )
    assert lider.is_sales_rep is False

    assert _repartir(client, lead_headers, dueno, lider.id).status_code == 422
    assert _asignados(db_session, dueno) == len(ajenos)


@pytest.mark.parametrize(("destino", "codigo"), [("misma", 422), ("inexistente", 404)])
def test_destinos_que_no_existen_como_tales(
    client, lead_headers, cartera_repartida, db_session, destino, codigo
):
    _, ajenos = cartera_repartida
    dueno = ajenos[0].assigned_rep_id
    destino_id = dueno if destino == "misma" else 999_999

    assert _repartir(client, lead_headers, dueno, destino_id).status_code == codigo
    assert _asignados(db_session, dueno) == len(ajenos)


def test_un_asesor_no_reparte_carteras(client, executive_headers, cartera_repartida, sales_reps):
    """Repartir trabajo es de quien dirige el equipo, no de quien lo recibe."""
    _, ajenos = cartera_repartida
    respuesta = _repartir(client, executive_headers, ajenos[0].assigned_rep_id, sales_reps[0].id)
    assert respuesta.status_code == 403
