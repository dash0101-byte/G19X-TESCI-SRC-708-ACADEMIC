"""
Lo que los cuatro conectores rechazan de una carga ajena, y lo que contestan al rechazarla.

Un adaptador es la única pieza del sistema que lee un objeto que ha escrito otro: Calendly,
WhatsApp, LinkedIn Lead Gen y el formulario del sitio. La firma HMAC dice que la entrega
viene de quien dice venir; **no** dice que dentro haya lo que se espera. Eso lo deciden
estas funciones, y lo que estaba probado era la carga que sale bien.

Un rechazo sin probar falla hacia el lado peor, y aquí hay dos lados peores distintos:

* **Reventar con un 500.** Un `payload` que llega como lista donde se espera un objeto, o
  una marca de tiempo que es la cadena `"ayer"`, serían un `AttributeError` o un
  `ValueError` sin recoger. Quien manda la entrega lee «error del servidor», la reintenta
  igual y vuelve a fallar; no hay forma de saber desde fuera que el problema es su carga.
* **Entrar a medias.** Un evento sin fecha utilizable o sin número se registraría con lo
  que hubiera, y de la tabla de actividad sale el score, que es lo que se enseña.

Lo que se comprueba de cada rechazo es el **campo** además del motivo, porque el campo es lo
que viaja en el 422 y lo que permite a quien integra saber qué parte de su carga arreglar:
un motivo correcto con el campo de otro manda a mirar donde no es.
"""
import datetime
import hashlib
import hmac
import uuid

import pytest
from app.core.config import settings
from app.models.entities import ActivityType, MessageDirection
from app.services.integraciones import (
    EventoInvalido,
    adaptar_calendly,
    adaptar_formulario_web,
    adaptar_linkedin_lead_gen,
    adaptar_whatsapp,
)
from tests.conftest import SIGNATURE_HEADER, TIMESTAMP_HEADER, sign_webhook

SECRETOS = {
    "CALENDLY": "secreto-calendly-de-pruebas",
    "WHATSAPP": "secreto-whatsapp-de-pruebas",
    "LINKEDIN_LEAD_GEN": "secreto-linkedin-de-pruebas",
    "FORMULARIO_WEB": "secreto-formulario-de-pruebas",
}

RUTAS = {
    "CALENDLY": "calendly",
    "WHATSAPP": "whatsapp",
    "LINKEDIN_LEAD_GEN": "linkedin-lead-gen",
    "FORMULARIO_WEB": "formulario-web",
}


@pytest.fixture
def integraciones(monkeypatch):
    """Las cuatro encendidas con secretos propios, como en la pila."""
    for prefijo, secreto in SECRETOS.items():
        monkeypatch.setattr(settings, f"INTEGRACION_{prefijo}_ACTIVA", True)
        monkeypatch.setattr(settings, f"INTEGRACION_{prefijo}_SECRETO", secreto)
    return SECRETOS


def _entregar(client, prefijo, carga):
    body, headers = sign_webhook(carga, secret=SECRETOS[prefijo])
    return client.post(f"/api/v1/integraciones/{RUTAS[prefijo]}/eventos", content=body, headers=headers)


def _entregar_bytes(client, prefijo, body: bytes):
    """
    Lo mismo pero firmando bytes crudos, que es la única forma de entregar algo que **no**
    sea JSON: `sign_webhook` serializa con `json.dumps` y nunca podría producirlo.
    """
    ts = str(int(datetime.datetime.now(datetime.timezone.utc).timestamp()))
    firma = hmac.new(
        SECRETOS[prefijo].encode("utf-8"), ts.encode("utf-8") + b"." + body, hashlib.sha256
    ).hexdigest()
    return client.post(
        f"/api/v1/integraciones/{RUTAS[prefijo]}/eventos",
        content=body,
        headers={"Content-Type": "application/json", SIGNATURE_HEADER: firma, TIMESTAMP_HEADER: ts},
    )


def _ahora():
    return datetime.datetime.now(datetime.timezone.utc)


def _calendly(**cambios):
    carga = {
        "event": "invitee.created",
        "payload": {
            "uri": f"https://api.calendly.com/scheduled_events/E{uuid.uuid4().hex}/invitees/I1",
            "email": "invitada@ejemplo.mx",
            "name": "Invitada de Pruebas",
            "created_at": (_ahora() - datetime.timedelta(minutes=10)).isoformat(),
            "scheduled_event": {"start_time": "2026-09-20T16:00:00Z"},
        },
    }
    carga.update(cambios)
    return carga


def _whatsapp(valor):
    return {"entry": [{"changes": [{"value": valor}]}]}


def _mensaje(**cambios):
    mensaje = {
        "id": f"wamid.{uuid.uuid4().hex}",
        "from": "5215512345678",
        "timestamp": str(int(_ahora().timestamp())),
        "type": "text",
    }
    mensaje.update(cambios)
    return mensaje


def _linkedin(**cambios):
    carga = {
        "leadId": f"urn:li:lead:{uuid.uuid4().hex}",
        "formId": "urn:li:form:99",
        "submittedAt": int(_ahora().timestamp() * 1000),
        "answers": {
            "emailAddress": "candidata@ejemplo.mx",
            "firstName": "Candidata",
            "lastName": "De Pruebas",
            "companyName": "Ejemplo SA",
        },
        "consent": {"privacyPolicy": True},
    }
    carga.update(cambios)
    return carga


# ==============================================================================
# La tabla de rechazos: carga de fuera, campo y motivo
# ==============================================================================

RECHAZOS = [
    (
        "calendly sin el objeto de la reserva",
        adaptar_calendly,
        {"event": "invitee.created"},
        "payload",
        "Falta el objeto 'payload'",
    ),
    (
        "calendly con la reserva como lista",
        adaptar_calendly,
        {"event": "invitee.created", "payload": [{"email": "a@b.mx"}]},
        "payload",
        "Falta el objeto 'payload'",
    ),
    (
        "calendly sin la fecha de la reserva",
        adaptar_calendly,
        _calendly(payload={"email": "a@b.mx", "uri": "u"}),
        "payload.created_at",
        "Falta la fecha 'payload.created_at'",
    ),
    (
        "calendly con una fecha que no es una fecha",
        adaptar_calendly,
        _calendly(payload={"email": "a@b.mx", "uri": "u", "created_at": "ayer por la tarde"}),
        "payload.created_at",
        "no es una fecha ISO 8601",
    ),
    (
        "calendly con la fecha dentro de un objeto",
        adaptar_calendly,
        _calendly(payload={"email": "a@b.mx", "uri": "u", "created_at": {"fecha": "2026-01-01"}}),
        "payload.created_at",
        "Falta la fecha 'payload.created_at'",
    ),
    (
        "whatsapp con una marca de tiempo que es texto",
        adaptar_whatsapp,
        _whatsapp({"messages": [_mensaje(timestamp="esta manana")]}),
        "messages.timestamp",
        "no es una marca de tiempo numérica",
    ),
    (
        "whatsapp con una marca de tiempo fuera de rango",
        adaptar_whatsapp,
        _whatsapp({"messages": [_mensaje(timestamp="1e30")]}),
        "messages.timestamp",
        "está fuera de rango",
    ),
    (
        "whatsapp sin mensajes ni envios",
        adaptar_whatsapp,
        _whatsapp({"contacts": [{"wa_id": "5215512345678", "profile": {"name": "Ana"}}]}),
        "entry",
        "no trae mensajes ni envíos",
    ),
    (
        "whatsapp con la entrada como objeto en vez de lista",
        adaptar_whatsapp,
        {"entry": {"changes": []}},
        "entry",
        "no trae mensajes ni envíos",
    ),
    (
        "whatsapp con un envio que solo se entrego",
        adaptar_whatsapp,
        _whatsapp({"statuses": [{"id": "wamid.1", "status": "delivered", "recipient_id": "5215512345678"}]}),
        "entry",
        "no trae mensajes ni envíos",
    ),
    (
        "linkedin sin las respuestas del formulario",
        adaptar_linkedin_lead_gen,
        {"leadId": "urn:li:lead:1", "submittedAt": 1700000000000},
        "answers",
        "Falta el objeto 'answers'",
    ),
    (
        "linkedin sin la fecha del envio",
        adaptar_linkedin_lead_gen,
        _linkedin(submittedAt=None),
        "submittedAt",
        "no es una marca de tiempo numérica",
    ),
    (
        "linkedin con la fecha del envio fuera de rango",
        adaptar_linkedin_lead_gen,
        _linkedin(submittedAt=10 ** 25),
        "submittedAt",
        "está fuera de rango",
    ),
    (
        "un formulario del sitio que no existe",
        adaptar_formulario_web,
        {"formulario": "encuesta", "campos": {"email": "a@b.mx"}},
        "formulario",
        "Formulario desconocido",
    ),
    (
        "un evento de calendly que no es una reserva",
        adaptar_calendly,
        {"event": "invitee.canceled", "payload": {}},
        "event",
        "no admitido",
    ),
]


@pytest.mark.parametrize(
    "nombre,adaptador,carga,campo,motivo",
    RECHAZOS,
    ids=[caso[0].replace(" ", "_") for caso in RECHAZOS],
)
def test_una_carga_que_no_cuadra_se_rechaza_nombrando_su_campo(
    nombre, adaptador, carga, campo, motivo
):
    """
    Cada rechazo, con el campo que viaja en el 422 y el motivo que lo explica.

    El campo se comprueba porque es lo único de este error que sirve para arreglarlo: quien
    integra recibe «'payload.created_at' no es una fecha ISO 8601» y sabe qué mirar. Con el
    campo de otro, no.
    """
    with pytest.raises(EventoInvalido) as fallo:
        adaptador(carga)

    assert fallo.value.campo == campo, nombre
    assert motivo in str(fallo.value), nombre
    # Y lo que de verdad sale por el cable: `como_detalle()` es lo que el endpoint pone en
    # el 422, y tiene que llevar las dos cosas.
    detalle = fallo.value.como_detalle()
    assert detalle["campo"] == campo
    assert motivo in detalle["motivo"]


# ==============================================================================
# Lo que sí entra, y por dónde
# ==============================================================================

def test_una_fecha_sin_zona_de_calendly_se_entiende_en_utc():
    """
    Calendly manda ISO con zona; si alguna vez la manda sin ella, se lee como UTC.

    Sin reponer la zona, el evento saldría *naive* y compararlo con cualquier instante del
    sistema —todos *aware*— sería un `TypeError` en el embudo, no una fecha mal puesta.
    """
    carga = _calendly(
        payload={"email": "a@b.mx", "uri": "u", "created_at": "2026-09-20T16:00:00"}
    )

    evento = adaptar_calendly(carga)[0]

    assert evento.ocurrido_en == datetime.datetime(
        2026, 9, 20, 16, 0, tzinfo=datetime.timezone.utc
    )
    assert evento.ocurrido_en.tzinfo is not None


def test_un_envio_de_whatsapp_entregado_no_cuenta_y_uno_enviado_si():
    """
    De los estados de un envío solo `sent` es un mensaje nuestro; `delivered` y `read` no.

    Son avisos sobre un mensaje que ya se registró. Contarlos sería registrar tres veces el
    mismo envío, y de ahí sale la cuenta de interacciones que alimenta el score.
    """
    carga = _whatsapp({
        "messages": [_mensaje()],
        "statuses": [
            {"id": "wamid.a", "status": "delivered", "recipient_id": "5215512345678",
             "timestamp": str(int(_ahora().timestamp()))},
            {"id": "wamid.b", "status": "read", "recipient_id": "5215512345678",
             "timestamp": str(int(_ahora().timestamp()))},
            {"id": "wamid.c", "status": "sent", "recipient_id": "5215512345678",
             "timestamp": str(int(_ahora().timestamp()))},
        ],
    })

    eventos = adaptar_whatsapp(carga)

    assert len(eventos) == 2, "el mensaje recibido y el envio, no los avisos"
    entrante, saliente = eventos
    assert entrante.direccion == MessageDirection.ENTRANTE
    assert saliente.direccion == MessageDirection.SALIENTE
    assert saliente.identificador_externo == "wamid.c"
    assert all(evento.tipo == ActivityType.WHATSAPP_MESSAGE for evento in eventos)


def test_un_numero_de_whatsapp_llega_sin_el_mas_y_se_le_pone():
    """WhatsApp identifica sin «+»; el embudo normaliza a E.164 y necesita el signo."""
    eventos = adaptar_whatsapp(_whatsapp({"messages": [_mensaje(**{"from": "5215512345678"})]}))

    assert eventos[0].contacto.telefono == "+5215512345678"


def test_un_mensaje_de_whatsapp_sin_numero_no_inventa_telefono():
    """
    Un mensaje sin `from` deja el teléfono a nada, no a «+».

    Un «+» suelto sería un teléfono para quien lo lea después: lo normalizaría el embudo, se
    guardaría como contacto y habría una ficha localizable en un número que no existe.
    """
    eventos = adaptar_whatsapp(_whatsapp({"messages": [_mensaje(**{"from": None})]}))

    assert eventos[0].contacto.telefono is None
    assert eventos[0].contacto.nombre is None


def test_un_numero_que_ya_trae_el_mas_no_se_lo_duplica():
    eventos = adaptar_whatsapp(_whatsapp({"messages": [_mensaje(**{"from": "+5215512345678"})]}))

    assert eventos[0].contacto.telefono == "+5215512345678"


def test_el_nombre_del_perfil_de_whatsapp_se_cruza_por_el_numero():
    """El nombre viene en `contacts`, no en el mensaje: se cruza por `wa_id`."""
    carga = _whatsapp({
        "contacts": [{"wa_id": "5215512345678", "profile": {"name": "Ana Prueba"}}],
        "messages": [_mensaje()],
    })

    assert adaptar_whatsapp(carga)[0].contacto.nombre == "Ana Prueba"


def test_un_consentimiento_que_no_es_un_si_no_acepta_el_aviso():
    """
    `privacyPolicy` tiene que ser `True`, no algo que se le parezca.

    La cadena `"false"` y el número `1` son verdaderos en Python; el aviso de privacidad es
    lo último que conviene dar por aceptado porque un valor sea *truthy*.
    """
    for valor in ("false", 1, "true", None, {}):
        evento = adaptar_linkedin_lead_gen(_linkedin(consent={"privacyPolicy": valor}))[0]
        assert evento.aviso_de_privacidad_aceptado_en is None, valor

    aceptado = adaptar_linkedin_lead_gen(_linkedin())[0]
    assert aceptado.aviso_de_privacidad_aceptado_en == aceptado.ocurrido_en


def test_la_fecha_de_linkedin_viene_en_milisegundos():
    """
    `submittedAt` es epoch en MILISEGUNDOS, y dividir o no por mil son cincuenta años.

    Sin la división, un envío de hoy se registraría en el año 58000 y el embudo lo
    rechazaría por venir del futuro; o al revés, una fecha de 1970 envejecería la ficha.
    """
    momento = _ahora().replace(microsecond=0)
    evento = adaptar_linkedin_lead_gen(
        _linkedin(submittedAt=int(momento.timestamp() * 1000))
    )[0]

    assert evento.ocurrido_en == momento


# ==============================================================================
# El endpoint: lo que contesta cuando la carga no es ni un objeto
# ==============================================================================

def test_un_cuerpo_que_no_es_json_se_contesta_400_y_no_500(client, integraciones):
    """
    La firma cuadra y el cuerpo no es JSON: es un 400 de quien manda, no un error nuestro.

    Se firman los bytes crudos a mano porque `sign_webhook` serializa con `json.dumps` y
    nunca podría producir esto. Sin el `try`, `json.loads` saldría como 500 y quien integra
    reintentaría una carga que nunca va a entrar.
    """
    respuesta = _entregar_bytes(client, "CALENDLY", b'{"event": "invitee.created"')

    assert respuesta.status_code == 400, respuesta.text
    assert "no es JSON" in respuesta.json()["detail"]


def test_un_cuerpo_json_que_no_es_un_objeto_se_contesta_400(client, integraciones):
    """
    Una lista es JSON válido y no es una carga: `carga.get(...)` sería un `AttributeError`.

    Es el rechazo que separa «JSON mal escrito» de «JSON que no es lo que se espera», y los
    dos tienen que decir cuál de los dos fue.
    """
    respuesta = _entregar(client, "CALENDLY", [{"event": "invitee.created"}])

    assert respuesta.status_code == 400, respuesta.text
    assert "objeto JSON" in respuesta.json()["detail"]


def test_un_cuerpo_que_es_una_cadena_json_tambien_se_rechaza(client, integraciones):
    respuesta = _entregar(client, "CALENDLY", "invitee.created")

    assert respuesta.status_code == 400, respuesta.text
    assert "objeto JSON" in respuesta.json()["detail"]


def test_lo_que_el_adaptador_rechaza_sale_como_422_con_su_campo(client, integraciones):
    """
    El rechazo del adaptador llega al cliente completo: el 422, el campo y el motivo.

    Es la mitad que une la tabla de arriba con el cable. Un 422 sin campo obliga a quien
    integra a adivinar qué parte de su carga arreglar.
    """
    respuesta = _entregar(
        client, "CALENDLY",
        _calendly(payload={"email": "a@b.mx", "uri": "u", "created_at": "ayer"}),
    )

    assert respuesta.status_code == 422, respuesta.text
    detalle = respuesta.json()["detail"]
    assert detalle["campo"] == "payload.created_at"
    assert "no es una fecha ISO 8601" in detalle["motivo"]


def test_un_evento_que_solo_la_base_puede_rechazar_sale_como_422(client, integraciones, db_session):
    """
    Lo que no se sabe hasta mirar la base: no hay ficha y el evento no trae con qué crearla.

    Un formulario de LinkedIn Lead Gen **sin correo** es una carga perfectamente formada: el
    adaptador la acepta y `validar_evento` también, porque ninguno de los dos sabe si esa
    persona ya tiene ficha. El rechazo aparece dentro de `registrar_evento`, al intentar
    abrirla: el correo es la identidad, y sin él no hay a quién atribuir nada. Tiene que
    salir con la misma forma que los de arriba —422, campo y motivo— y no con un 500.

    No vale cualquier fuente para provocarlo: un mensaje de WhatsApp de un número
    desconocido **no** se rechaza, se va a la bandeja de sin asociar, porque esa fuente no
    crea fichas. Solo las dos que sí las crean —LinkedIn Lead Gen y el formulario del
    sitio— pueden llegar a este rechazo.
    """
    from app.models.entities import Lead, LeadActivity

    antes = (db_session.query(LeadActivity).count(), db_session.query(Lead).count())

    respuesta = _entregar(
        client, "LINKEDIN_LEAD_GEN",
        _linkedin(answers={"firstName": "Sin", "lastName": "Correo", "companyName": "Ejemplo SA"}),
    )

    assert respuesta.status_code == 422, respuesta.text
    detalle = respuesta.json()["detail"]
    assert detalle["campo"] == "email"
    assert "correo" in detalle["motivo"]
    # Y no quedó nada a medias: ni la actividad ni la ficha.
    db_session.expire_all()
    assert (db_session.query(LeadActivity).count(), db_session.query(Lead).count()) == antes
