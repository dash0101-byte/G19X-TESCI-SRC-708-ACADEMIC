"""
Gestión de campañas de captación.

Las campañas existían en el modelo desde el principio y solo podían crearse sembrando la
base: el informe de rendimiento por campaña estaba, pero no había forma de dar de alta la
campaña cuyo rendimiento se quería medir.

El reparto de permisos no es el de las cuentas, y es a propósito: una campaña es una
decisión comercial, no de sistemas. Quien dirige la cartera la crea; un asesor la lee
—necesita saber de dónde vino un prospecto— y no la toca, porque el presupuesto es
información de dirección.
"""
import pytest
from app.models.entities import AuditLog, Campaign

CAMPANAS = "/api/v1/campaigns"


def _crear(client, headers, **extra):
    cuerpo = {"name": "Google Ads Q3", "channel": "Google Ads", "budget": 85000.0}
    cuerpo.update(extra)
    return client.post(CAMPANAS, headers=headers, json=cuerpo)


# ==============================================================================
# Permisos
# ==============================================================================

def test_cualquier_rol_lee_las_campanas(client, auth_headers):
    """
    No se acotan por cartera. Una campaña no pertenece a nadie: es el canal por el que
    entró un prospecto, y un asesor necesita poder nombrarlo para entender su trabajo.
    """
    for rol in ("System_Admin", "Sales_Lead", "Commercial_Executive"):
        assert client.get(CAMPANAS, headers=auth_headers(rol)).status_code == 200


def test_el_asesor_no_crea_ni_edita(client, executive_headers, campaigns):
    respuesta = _crear(client, executive_headers)
    assert respuesta.status_code == 403
    assert client.put(
        f"{CAMPANAS}/{campaigns[0].id}", headers=executive_headers, json={"budget": 1.0}
    ).status_code == 403
    assert client.delete(
        f"{CAMPANAS}/{campaigns[0].id}", headers=executive_headers
    ).status_code == 403


@pytest.mark.parametrize("rol", ["Sales_Lead", "System_Admin"])
def test_quien_dirige_la_cartera_si_gestiona(client, auth_headers, rol):
    respuesta = _crear(client, auth_headers(rol), name=f"Campaña de {rol}")
    assert respuesta.status_code == 201


def test_la_denegacion_al_asesor_queda_registrada(client, executive_headers, db_session):
    _crear(client, executive_headers)
    asiento = (
        db_session.query(AuditLog).filter(AuditLog.action == "acceso.denegado").first()
    )
    assert asiento is not None
    assert asiento.outcome == "HTTP_403"


# ==============================================================================
# Alta y edición
# ==============================================================================

def test_alta_de_una_campana(client, lead_headers, db_session):
    respuesta = _crear(client, lead_headers)
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["name"] == "Google Ads Q3"
    assert cuerpo["budget"] == 85000.0
    assert cuerpo["is_active"] is True

    asiento = db_session.query(AuditLog).filter(AuditLog.action == "campana.crear").first()
    assert asiento.event_metadata["presupuesto"] == 85000.0


def test_una_fecha_de_fin_anterior_al_inicio_se_rechaza(client, lead_headers):
    respuesta = _crear(
        client, lead_headers,
        start_date="2026-06-01T00:00:00Z", end_date="2026-03-01T00:00:00Z",
    )
    assert respuesta.status_code == 422


def test_el_cambio_de_presupuesto_registra_el_valor_anterior(client, lead_headers, db_session):
    """
    Aquí sí se guardan los valores, a diferencia de los prospectos, donde solo se anotan
    los nombres de los campos tocados.

    Los datos de un prospecto son personales y duplicarlos en una tabla con otro criterio
    de acceso los expone dos veces; una cifra de presupuesto no es un dato personal y su
    historial de cambios es justo lo que alguien querrá reconstruir cuando el rendimiento
    por campaña no cuadre.
    """
    creada = _crear(client, lead_headers).json()
    client.put(f"{CAMPANAS}/{creada['id']}", headers=lead_headers, json={"budget": 120000.0})

    asiento = (
        db_session.query(AuditLog).filter(AuditLog.action == "campana.actualizar").first()
    )
    assert asiento.event_metadata["presupuesto_anterior"] == 85000.0
    assert asiento.event_metadata["presupuesto_nuevo"] == 120000.0


# ==============================================================================
# Baja lógica
# ==============================================================================

def test_la_campana_se_desactiva_pero_no_se_borra(client, lead_headers, db_session):
    """
    Borrarla pondría a NULL la campaña de cada prospecto que atrajo, y con ella la
    atribución de la inversión: el informe perdería exactamente las campañas terminadas,
    que son las únicas cuyo resultado final se conoce.
    """
    creada = _crear(client, lead_headers).json()
    respuesta = client.delete(f"{CAMPANAS}/{creada['id']}", headers=lead_headers)
    assert respuesta.status_code == 200
    assert respuesta.json()["is_active"] is False

    db_session.expire_all()
    assert db_session.query(Campaign).filter(Campaign.id == creada["id"]).first() is not None


def test_las_desactivadas_no_salen_salvo_que_se_pidan(client, lead_headers):
    creada = _crear(client, lead_headers).json()
    client.delete(f"{CAMPANAS}/{creada['id']}", headers=lead_headers)

    normal = client.get(CAMPANAS, headers=lead_headers).json()
    assert creada["id"] not in {c["id"] for c in normal["items"]}

    con_todas = client.get(
        CAMPANAS, params={"incluir_inactivas": True}, headers=lead_headers
    ).json()
    assert creada["id"] in {c["id"] for c in con_todas["items"]}


def test_la_baja_cuenta_los_prospectos_que_atrajo(
    client, lead_headers, db_session, campaigns, sample_leads
):
    """El asiento debe decir qué atribución queda en juego, no solo que se desactivó."""
    campana = campaigns[0]
    for lead in sample_leads[:3]:
        lead.campaign_id = campana.id
    db_session.commit()

    client.delete(f"{CAMPANAS}/{campana.id}", headers=lead_headers)
    asiento = (
        db_session.query(AuditLog).filter(AuditLog.action == "campana.desactivar").first()
    )
    assert asiento.event_metadata["prospectos_atribuidos"] == 3


def test_una_campana_inexistente_da_404(client, lead_headers):
    assert client.get(f"{CAMPANAS}/99999", headers=lead_headers).status_code == 404
    assert client.put(
        f"{CAMPANAS}/99999", headers=lead_headers, json={"budget": 1.0}
    ).status_code == 404
