"""
Lo que el servidor tiene que cumplir para que la pantalla de derechos sea cierta (cap. 38).

La pantalla no añade lógica de supresión: pide las dos cosas que existen desde la Fase 14 y
están comprobadas tabla por tabla en `test_derechos_del_titular.py`. Lo que se prueba aquí
es distinto, y es lo que esa suite no cubría porque nadie dependía de ello todavía:

* **Que buscar por correo funcione y que traiga de más.** La pantalla resuelve el correo a
  una ficha con el listado, que busca con un `LIKE` sobre cinco columnas. Pedir
  «ana@x.com» trae también a «diana@x.com», y de eso depende una decisión del cliente: la
  igualdad la comprueba él. Si algún día el listado deja de encontrar un correo entero, la
  pantalla contestaría «no consta» sobre alguien que está, y ninguna prueba del cliente lo
  vería: allí el listado está simulado.
* **Que el alcance de cartera también se aplique a esa búsqueda.** Un asesor que escriba el
  correo de un prospecto ajeno no debe encontrarlo, igual que no puede abrir su ficha.
* **Que los dos asientos digan quién y cuándo.** La pantalla se lo promete por escrito a
  quien la usa: «queda en la bitácora con quién la pidió y cuándo». La suite comprobaba el
  rol y los recuentos; el correo del actor y el instante, no.
* **Que la casilla del aviso de privacidad del alta haga lo que la pantalla dice.** Marcada,
  anota la fecha y la fuente «manual»; sin marcar, deja los dos campos vacíos y no supone
  nada. Era API desde la Fase 15 y no la ejercitaba ninguna prueba del alta.
"""
import datetime

import pytest
from app.models.entities import AuditLog, Lead

LEADS = "/api/v1/leads"
UTC = datetime.timezone.utc


@pytest.fixture
def ana_y_diana(db_session):
    """
    Dos personas cuyos correos se contienen: «ana@…» es subcadena de «diana@…».

    Es el escenario que el servicio de derechos ya usaba para rastrear el correo dentro de
    las cargas del CRM, aquí sobre el listado. Sin él, la búsqueda por correo parece exacta
    porque con una sola persona en la base lo es.
    """
    ana = Lead(first_name="Ana", last_name="Titular", email="ana@ejemplo.com", company="Ana SA")
    diana = Lead(first_name="Diana", last_name="Otra", email="diana@ejemplo.com", company="Diana SA")
    db_session.add_all([ana, diana])
    db_session.commit()
    for lead in (ana, diana):
        db_session.refresh(lead)
    return ana, diana


# ==============================================================================
# Encontrar a la persona por su correo
# ==============================================================================

def test_el_listado_encuentra_una_ficha_por_su_correo_entero(client, lead_headers, ana_y_diana):
    ana, _ = ana_y_diana

    respuesta = client.get(LEADS, headers=lead_headers, params={"search": ana.email})

    assert respuesta.status_code == 200, respuesta.text
    assert ana.id in [f["id"] for f in respuesta.json()["items"]]


def test_la_busqueda_por_correo_trae_tambien_a_quien_solo_se_parece(client, lead_headers, ana_y_diana):
    """
    Esta prueba fija un comportamiento del servidor del que depende una decisión del cliente.

    El `search` del listado es un `LIKE`, y está bien que lo sea: es el buscador de la
    matriz de prospectos, donde escribir media palabra tiene que encontrar. Lo que no puede
    es usarse tal cual para exportar o borrar, porque la primera fila de la respuesta puede
    ser de otra persona. Por eso `buscarTitularPorCorreo` compara la igualdad en el cliente,
    y por eso esta prueba existe: deja escrito aquí, en el servidor, el motivo.
    """
    ana, diana = ana_y_diana

    items = client.get(LEADS, headers=lead_headers, params={"search": ana.email}).json()["items"]

    correos = sorted(f["email"] for f in items)
    assert correos == [ana.email, diana.email], (
        "El listado busca por coincidencia parcial; si dejara de hacerlo, la igualdad "
        "exacta del cliente seguiría siendo correcta, pero este aviso ya no haría falta."
    )


def test_un_asesor_no_encuentra_por_correo_a_quien_no_atiende(client, executive_headers, ana_y_diana):
    """
    El alcance de cartera también acota la búsqueda, y no es obvio: el correo es un dato que
    quien pregunta ya tiene en la mano, así que podría parecer que buscarlo no revela nada.
    Revela dos cosas —que esa persona está en el sistema y toda su ficha—, y las dos son de
    la cartera de otro. El filtro vive en el repositorio y no en el endpoint, que es lo que
    hace que valga también para esta búsqueda sin que nadie se acordara de ella.
    """
    ana, _ = ana_y_diana

    items = client.get(LEADS, headers=executive_headers, params={"search": ana.email}).json()["items"]

    assert items == []


# ==============================================================================
# Quién la pidió y cuándo
# ==============================================================================

def test_el_asiento_de_la_exportacion_dice_quien_la_pidio_y_cuando(
    client, lead_headers, db_session, ana_y_diana
):
    """
    Es lo que la pantalla promete con todas sus letras antes de que nadie pulse nada. Si el
    asiento no llevara el actor o el instante, la frase de la pantalla sería falsa y nada
    fallaría: la exportación saldría igual.
    """
    ana, _ = ana_y_diana
    antes = datetime.datetime.now(UTC)

    assert client.get(f"{LEADS}/{ana.id}/exportar", headers=lead_headers).status_code == 200

    asiento = db_session.query(AuditLog).filter(AuditLog.action == "lead.exportar").one()
    assert asiento.actor_email
    assert asiento.actor_role == "Sales_Lead"
    assert asiento.entity_id == str(ana.id)
    assert asiento.outcome == "OK"
    ocurrido = asiento.occurred_at
    if ocurrido.tzinfo is None:
        ocurrido = ocurrido.replace(tzinfo=UTC)
    assert ocurrido >= antes - datetime.timedelta(seconds=5)


def test_el_asiento_del_borrado_dice_quien_y_cuando_y_no_el_correo(
    client, admin_headers, db_session, ana_y_diana
):
    ana, _ = ana_y_diana
    correo = ana.email

    assert client.delete(f"{LEADS}/{ana.id}", headers=admin_headers).status_code == 204

    asiento = db_session.query(AuditLog).filter(AuditLog.action == "lead.eliminar").one()
    assert asiento.actor_email
    assert asiento.occurred_at is not None
    assert correo not in str(asiento.event_metadata).lower()


def test_consultar_un_correo_que_no_consta_no_escribe_nada_en_la_bitacora(
    client, lead_headers, db_session
):
    """
    La pantalla dice que cada petición de derechos queda registrada, y una búsqueda en vacío
    no lo está. Es deliberado y la pantalla lo explica: el único dato personal que habría que
    anotar para dejar el asiento es el correo de alguien de quien el sistema **no guarda
    nada**. Registrarlo sería crear el dato en vez de contestar sobre él.
    """
    client.get(LEADS, headers=lead_headers, params={"search": "nadie@ejemplo.com"})

    assert db_session.query(AuditLog).filter(AuditLog.action == "lead.exportar").count() == 0
    assert db_session.query(AuditLog).count() == 0


# ==============================================================================
# La casilla del aviso de privacidad en el alta manual
# ==============================================================================

def _alta(correo, **extra):
    return {
        "first_name": "Ana",
        "last_name": "Titular",
        "email": correo,
        "source": "Llamada Directa",
        **extra,
    }


def test_el_alta_marcada_anota_la_fecha_y_la_fuente_manual(client, lead_headers, db_session):
    antes = datetime.datetime.now(UTC)

    respuesta = client.post(
        LEADS, headers=lead_headers, json=_alta("marcada@ejemplo.com", privacy_notice_accepted=True)
    )

    assert respuesta.status_code == 201, respuesta.text
    lead = db_session.query(Lead).filter(Lead.email == "marcada@ejemplo.com").one()
    assert lead.privacy_notice_source == "manual"
    aceptado = lead.privacy_notice_accepted_at
    if aceptado.tzinfo is None:
        aceptado = aceptado.replace(tzinfo=UTC)
    assert aceptado >= antes - datetime.timedelta(seconds=5)
    # Y sale en la respuesta, que es de donde la pantalla de derechos lo lee después.
    assert respuesta.json()["privacy_notice_source"] == "manual"


def test_el_alta_sin_marcar_deja_los_dos_campos_vacios(client, lead_headers, db_session):
    """
    «No consta» y «no aceptó» no son lo mismo, y la ficha no supone ninguno de los dos. Es
    el mismo criterio que el país que ya no es «México» y los ingresos que no son cero: lo
    que nadie dijo no se escribe.
    """
    respuesta = client.post(
        LEADS, headers=lead_headers, json=_alta("sin_marcar@ejemplo.com", privacy_notice_accepted=False)
    )

    assert respuesta.status_code == 201, respuesta.text
    lead = db_session.query(Lead).filter(Lead.email == "sin_marcar@ejemplo.com").one()
    assert lead.privacy_notice_accepted_at is None
    assert lead.privacy_notice_source is None


def test_un_alta_que_no_manda_el_campo_tampoco_supone_que_acepto(client, lead_headers, db_session):
    """El valor por omisión del esquema es `False`, no «lo que diga el cliente»."""
    respuesta = client.post(LEADS, headers=lead_headers, json=_alta("omitido@ejemplo.com"))

    assert respuesta.status_code == 201, respuesta.text
    lead = db_session.query(Lead).filter(Lead.email == "omitido@ejemplo.com").one()
    assert lead.privacy_notice_accepted_at is None
    assert lead.privacy_notice_source is None


def test_la_constancia_del_alta_manual_se_distingue_de_la_de_la_pagina_publica(
    client, lead_headers, db_session
):
    """
    La fuente dice **quién** marcó la casilla, y eso cambia lo que la aceptación vale: en la
    página la marcó la persona, y en el alta del panel la marcó un asesor por ella. Si las
    dos escribieran lo mismo, la respuesta de acceso no podría decir la diferencia.
    """
    client.post(
        LEADS, headers=lead_headers, json=_alta("fuente@ejemplo.com", privacy_notice_accepted=True)
    )

    lead = db_session.query(Lead).filter(Lead.email == "fuente@ejemplo.com").one()
    assert lead.privacy_notice_source == "manual"
    assert lead.privacy_notice_source != "pagina_de_interes"


def test_la_exportacion_lleva_la_constancia_del_aviso(client, lead_headers, db_session):
    """Lo que la pantalla de derechos enseña en «De dónde llegaron» sale de aquí."""
    client.post(
        LEADS, headers=lead_headers, json=_alta("exporta@ejemplo.com", privacy_notice_accepted=True)
    )
    lead = db_session.query(Lead).filter(Lead.email == "exporta@ejemplo.com").one()

    documento = client.get(f"{LEADS}/{lead.id}/exportar", headers=lead_headers).json()

    assert documento["datos_del_prospecto"]["privacy_notice_source"] == "manual"
    assert documento["datos_del_prospecto"]["privacy_notice_accepted_at"]
    assert documento["datos_del_prospecto"]["source"] == "Llamada Directa"
