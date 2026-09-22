"""
Idempotencia y anti-replay de la ingesta por webhook (N-2).

La firma HMAC autentica el cuerpo; no acredita que la petición sea nueva. Quien capturara
una entrega legítima podía reenviarla tal cual y, mientras la marca de tiempo siguiera
dentro de la ventana de tolerancia, volvía a pasar todas las comprobaciones porque era
exactamente la misma petición que ya había pasado. Cada repetición añadía otra actividad
al prospecto y movía su score.

Se distinguen dos casos que se parecen mucho y no son lo mismo:

* reenviar los **mismos bytes con la misma firma** no lo hace ningún emisor honesto → 409;
* reintentar el **mismo evento con firma nueva** es lo que hace un CRM al que se le perdió
  la respuesta → 200 con la respuesta original, sin volver a ingerir.

`test_reenviar_la_misma_firma_devuelve_409` es la que falla si alguien revierte el arreglo.
"""
import datetime
import uuid

from app.models.entities import Lead, LeadActivity, WebhookDelivery
from app.services.webhook_dedup import (
    clave_de_idempotencia,
    purgar_entregas_caducadas,
    reiniciar_reloj_de_purga,
)
from tests.conftest import sign_webhook

WEBHOOK = "/api/v1/crm/webhook"
CABECERA_REPETICION = "X-PluriOne-Idempotent-Replay"


def _payload(sufijo: str, *, evento: str = "lead.created", empresa: str = "Talento MX") -> dict:
    return {
        "event": evento,
        "crm_platform": "HubSpot",
        "external_lead_id": f"HS-{sufijo}",
        "data": {
            "first_name": "Fernanda",
            "last_name": "Pérez",
            "email": f"repetido.{sufijo}@talentomx.com",
            "company": empresa,
            "job_title": "Gerente de TI",
            "industry": "Software/TI",
            "company_size": "51-200",
            "activity_type": "PAGE_VIEW",
        },
    }


# ==============================================================================
# Reenvío exacto: 409
# ==============================================================================

def test_reenviar_la_misma_firma_devuelve_409(client, db_session):
    """
    El PoC de la vulnerabilidad. Antes, esta segunda llamada devolvía 200 y volvía a
    ingerir el evento entero.
    """
    sufijo = uuid.uuid4().hex[:8]
    body, headers = sign_webhook(_payload(sufijo))

    primera = client.post(WEBHOOK, content=body, headers=headers)
    assert primera.status_code == 200, primera.text

    segunda = client.post(WEBHOOK, content=body, headers=headers)
    assert segunda.status_code == 409, (
        "Reenviar los mismos bytes con la misma marca de tiempo no lo hace ningún emisor "
        "honesto: es un replay."
    )


def test_el_reenvio_no_deja_una_segunda_actividad(client, db_session):
    """
    El 409 tiene que llegar **antes** de tocar nada. Un rechazo que llegara después de
    haber creado la actividad sería un mensaje de error sobre un efecto ya consumado.
    """
    sufijo = uuid.uuid4().hex[:8]
    body, headers = sign_webhook(_payload(sufijo))

    respuesta = client.post(WEBHOOK, content=body, headers=headers)
    lead_id = respuesta.json()["lead_id"]
    actividades_iniciales = (
        db_session.query(LeadActivity).filter(LeadActivity.lead_id == lead_id).count()
    )

    for _ in range(3):
        assert client.post(WEBHOOK, content=body, headers=headers).status_code == 409

    assert (
        db_session.query(LeadActivity).filter(LeadActivity.lead_id == lead_id).count()
        == actividades_iniciales
    ), "Un replay rechazado no puede haber registrado actividad."


# ==============================================================================
# Reintento honesto: se repite la respuesta
# ==============================================================================

def test_el_reintento_con_firma_nueva_recibe_la_respuesta_original(client, db_session):
    """
    Un CRM que no recibió la respuesta reintenta, y su reintento va firmado de nuevo: la
    firma cambia aunque el evento sea el mismo. Devolverle un error solo alimentaría el
    bucle de reintentos, así que se le devuelve lo que pedía.
    """
    sufijo = uuid.uuid4().hex[:8]
    payload = _payload(sufijo)

    ahora = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    body_1, headers_1 = sign_webhook(payload, timestamp=ahora)
    body_2, headers_2 = sign_webhook(payload, timestamp=ahora + 1)
    assert headers_1["X-PluriOne-Signature"] != headers_2["X-PluriOne-Signature"]

    primera = client.post(WEBHOOK, content=body_1, headers=headers_1)
    assert primera.status_code == 200, primera.text

    reintento = client.post(WEBHOOK, content=body_2, headers=headers_2)
    assert reintento.status_code == 200, reintento.text
    assert reintento.headers.get(CABECERA_REPETICION) == "true", (
        "El emisor debe poder distinguir una respuesta repetida de un segundo procesamiento."
    )
    assert reintento.json() == primera.json()

    lead_id = primera.json()["lead_id"]
    assert (
        db_session.query(LeadActivity).filter(LeadActivity.lead_id == lead_id).count() == 1
    ), "El reintento no puede haber añadido una segunda actividad."


def test_dos_cambios_reales_seguidos_se_procesan_los_dos(client, db_session):
    """
    La razón por la que la clave lleva la huella del cuerpo.

    Con idempotencia por `external_lead_id` + evento a secas, dos `lead.updated` distintos
    del mismo prospecto dentro de la ventana se colapsarían en uno y la segunda
    actualización —la buena— se descartaría en silencio. Ese sería un fallo peor que el
    que se está arreglando, porque no da error: simplemente pierde el dato.
    """
    sufijo = uuid.uuid4().hex[:8]

    primero = _payload(sufijo, evento="lead.updated", empresa="Talento MX")
    body_1, headers_1 = sign_webhook(primero)
    assert client.post(WEBHOOK, content=body_1, headers=headers_1).status_code == 200

    segundo = _payload(sufijo, evento="lead.updated", empresa="Talento MX Internacional")
    body_2, headers_2 = sign_webhook(segundo)
    respuesta = client.post(WEBHOOK, content=body_2, headers=headers_2)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers.get(CABECERA_REPETICION) is None

    lead = db_session.query(Lead).filter(Lead.email == primero["data"]["email"]).first()
    assert lead.company == "Talento MX Internacional", (
        "La segunda actualización debe haberse aplicado, no descartado como duplicado."
    )


# ==============================================================================
# La reserva vive y cae con la ingesta
# ==============================================================================

def test_una_ingesta_rechazada_no_deja_candado(client, db_session):
    """
    Si la reserva se confirmara por su cuenta, un evento que nunca llegó a ingerirse
    dejaría un candado: el CRM reintentaría, recibiría «duplicado», y el prospecto no
    existiría en ninguna parte. Se comprueba con una carga sin email, que el servicio
    rechaza con 400.
    """
    sufijo = uuid.uuid4().hex[:8]
    invalido = {
        "event": "form.submission",
        "crm_platform": "Salesforce",
        "external_lead_id": f"SF-{sufijo}",
        "data": {"first_name": "Sin correo"},
    }
    body, headers = sign_webhook(invalido)

    assert client.post(WEBHOOK, content=body, headers=headers).status_code == 400
    assert db_session.query(WebhookDelivery).count() == 0, (
        "Una ingesta que no llegó a ocurrir no puede dejar reserva."
    )

    # Y el emisor puede corregir y reenviar sin tropezar con un duplicado fantasma.
    corregido = dict(invalido)
    # Con su tipo de actividad: desde la Fase 15 el webhook no inventa uno.
    corregido["data"] = {
        **invalido["data"],
        "email": f"corregido.{sufijo}@talentomx.com",
        "activity_type": "FORM_SUBMIT",
    }
    body_ok, headers_ok = sign_webhook(corregido)
    assert client.post(WEBHOOK, content=body_ok, headers=headers_ok).status_code == 200


# ==============================================================================
# La clave y la purga
# ==============================================================================

def test_la_clave_distingue_cuerpos_distintos():
    base = {"crm_platform": "HubSpot", "event": "lead.updated", "external_lead_id": "HS-1"}
    uno = clave_de_idempotencia(**base, body=b'{"company":"A"}')
    otro = clave_de_idempotencia(**base, body=b'{"company":"B"}')
    igual = clave_de_idempotencia(**base, body=b'{"company":"A"}')

    assert uno != otro, "Dos cuerpos distintos son dos eventos distintos."
    assert uno == igual, "El mismo cuerpo debe producir siempre la misma clave."
    assert len(uno) <= 255, "La clave tiene que caber en su columna."


def test_la_clave_tolera_la_ausencia_de_identificador_externo():
    """`external_lead_id` es opcional en el esquema; la huella del cuerpo sostiene la clave."""
    sin_externo = clave_de_idempotencia(
        crm_platform="Zoho", event="lead.created", external_lead_id=None, body=b"{}"
    )
    vacio = clave_de_idempotencia(
        crm_platform="Zoho", event="lead.created", external_lead_id="   ", body=b"{}"
    )
    assert sin_externo == vacio


def test_la_purga_solo_se_lleva_lo_caducado(db_session):
    ahora = datetime.datetime.now(datetime.timezone.utc)
    db_session.add_all(
        [
            WebhookDelivery(
                signature="a" * 64, idempotency_key="vigente", crm_platform="HubSpot",
                event="lead.created", received_at=ahora,
                expires_at=ahora + datetime.timedelta(minutes=15),
            ),
            WebhookDelivery(
                signature="b" * 64, idempotency_key="caducada", crm_platform="HubSpot",
                event="lead.created", received_at=ahora - datetime.timedelta(hours=2),
                expires_at=ahora - datetime.timedelta(hours=1),
            ),
        ]
    )
    db_session.commit()

    reiniciar_reloj_de_purga()
    assert purgar_entregas_caducadas(db_session) == 1
    restantes = {e.idempotency_key for e in db_session.query(WebhookDelivery).all()}
    assert restantes == {"vigente"}


def test_la_purga_no_se_ejecuta_en_cada_peticion(db_session):
    """
    Sin límite de frecuencia, un CRM con picos de sincronización pagaría un DELETE por
    evento. El segundo intento seguido debe salir sin hacer nada.
    """
    ahora = datetime.datetime.now(datetime.timezone.utc)
    reiniciar_reloj_de_purga()
    assert purgar_entregas_caducadas(db_session) == 0

    db_session.add(
        WebhookDelivery(
            signature="c" * 64, idempotency_key="caducada-2", crm_platform="Zoho",
            event="lead.created", received_at=ahora - datetime.timedelta(hours=2),
            expires_at=ahora - datetime.timedelta(hours=1),
        )
    )
    db_session.commit()

    assert purgar_entregas_caducadas(db_session) == 0, "El reloj todavía no da permiso."
    assert purgar_entregas_caducadas(db_session, forzar=True) == 1


def test_una_entrega_caducada_deja_pasar_el_mismo_evento(client, db_session):
    """
    Pasada la ventana, la marca de tiempo original ya no supera la comprobación
    anti-replay: guardar la huella para siempre solo serviría para bloquear un evento
    legítimo que se repita meses después.
    """
    sufijo = uuid.uuid4().hex[:8]
    body, headers = sign_webhook(_payload(sufijo))

    assert client.post(WEBHOOK, content=body, headers=headers).status_code == 200

    entrega = db_session.query(WebhookDelivery).one()
    entrega.expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
    db_session.commit()

    # Firma nueva sobre el mismo evento: sin la caducidad, esto respondería la copia
    # guardada; con ella, se procesa de verdad.
    reiniciar_reloj_de_purga()
    body_2, headers_2 = sign_webhook(_payload(sufijo))
    respuesta = client.post(WEBHOOK, content=body_2, headers=headers_2)
    assert respuesta.status_code == 200
    assert respuesta.headers.get(CABECERA_REPETICION) is None


def test_la_entrega_atendida_queda_registrada_con_su_respuesta(client, db_session):
    sufijo = uuid.uuid4().hex[:8]
    body, headers = sign_webhook(_payload(sufijo))
    respuesta = client.post(WEBHOOK, content=body, headers=headers)
    assert respuesta.status_code == 200

    entrega = db_session.query(WebhookDelivery).one()
    assert entrega.signature == headers["X-PluriOne-Signature"]
    assert entrega.external_lead_id == f"HS-{sufijo}"
    assert entrega.lead_id == respuesta.json()["lead_id"]
    assert entrega.response_data["calculated_score"] == respuesta.json()["calculated_score"]
    assert entrega.expires_at is not None
