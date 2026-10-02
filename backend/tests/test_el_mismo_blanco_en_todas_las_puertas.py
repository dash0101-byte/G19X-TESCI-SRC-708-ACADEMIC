"""
Capítulo 41: el mismo blanco, la misma respuesta, por cualquier puerta.

`test_un_blanco_no_es_un_dato.py` comprueba la regla sobre los esquemas, que es donde vive.
Esto comprueba lo que se ve desde fuera, que es donde se notaba: una ficha dada de alta y la
misma ficha después de una edición no decían lo mismo en la base, y dos de las tres ediciones
parciales del sistema contestaban **500** a un vacío que la tercera rechazaba con un 422 desde
el capítulo 33.

Lo que aquí se fija no es el número de respuesta por sí mismo. Es que una respuesta de error
del servidor —un 500— se anota como un fallo nuestro y en la pantalla sale como «algo ha ido
mal», así que la persona que acaba de borrar el nombre de una publicación no se entera de que
lo que no se admite es haberlo borrado.
"""
import datetime
import uuid

import pytest
from app.models.entities import Campaign, Lead, LeadActivity, User
from tests.conftest import sign_webhook

LEADS = "/api/v1/leads"
CAMPANAS = "/api/v1/campaigns"
USUARIOS = "/api/v1/users"
WEBHOOK = "/api/v1/crm/webhook"

CLAVE = "Mu3y-L4rga-Clave!x"

# Los diez campos de texto del alta de una ficha, todos en blanco y de tres formas distintas:
# la cadena vacía que manda un `<input>` sin tocar, el espacio que queda al borrar lo escrito y
# el par de espacios de un copiado y pegado. Las tres son lo mismo y hasta el capítulo 41 las
# tres se guardaban tal cual.
BLANCOS = {
    "company": "",
    "job_title": "   ",
    "industry": " ",
    "company_size": "  ",
    "country": "",
    "city": "   ",
    "phone": " ",
    "initial_notes": "  ",
}


# ==============================================================================
# 1. El alta normaliza lo mismo que la edición
# ==============================================================================

def test_el_alta_deja_en_vacio_lo_que_llega_en_blanco(client, lead_headers):
    """
    Los nueve campos que el alta guardaba en blanco, y el país, que ya se normalizaba.

    El país lleva normalizado desde el capítulo 32 porque era el campo del que ese capítulo se
    ocupaba. Los demás no, y nadie lo notó: la ficha que entra por esta puerta queda con `''`
    donde la que pasa por la edición queda con `NULL`, dos formas de decir «no hay dato» en la
    misma columna y por el mismo panel.
    """
    cuerpo = {
        "first_name": "Ana",
        "last_name": "Pérez",
        "email": f"ana.{uuid.uuid4().hex[:8]}@example.com",
        **BLANCOS,
    }

    respuesta = client.post(LEADS, headers=lead_headers, json=cuerpo)

    assert respuesta.status_code == 201, respuesta.text
    ficha = respuesta.json()
    for campo in ("company", "job_title", "industry", "company_size", "country", "city", "phone"):
        assert ficha[campo] is None, f"{campo} entró como {ficha[campo]!r}"


def test_el_alta_y_la_edicion_dejan_la_misma_ficha(client, lead_headers, db_session):
    """
    La prueba que dice por qué este capítulo existe.

    Dos fichas idénticas: una creada con los campos en blanco y otra creada con datos y vaciada
    después. Antes del capítulo 41 la primera tenía `''` en nueve columnas y la segunda `NULL`,
    y cualquier consulta que preguntara «cuántas fichas no tienen empresa» acertaba con una de
    las dos. Ahora las dos filas son iguales, que es lo que significa tener una sola
    representación del vacío.
    """
    sufijo = uuid.uuid4().hex[:8]
    por_el_alta = client.post(
        LEADS,
        headers=lead_headers,
        json={
            "first_name": "Ana", "last_name": "Pérez",
            "email": f"alta.{sufijo}@example.com", **BLANCOS,
        },
    )
    assert por_el_alta.status_code == 201, por_el_alta.text

    por_la_edicion = client.post(
        LEADS,
        headers=lead_headers,
        json={
            "first_name": "Ana", "last_name": "Pérez",
            "email": f"edicion.{sufijo}@example.com",
            "company": "ACME", "job_title": "CTO", "industry": "FinTech",
            "company_size": "11-50", "country": "México", "city": "Monterrey",
        },
    )
    assert por_la_edicion.status_code == 201, por_la_edicion.text
    vaciada = client.put(
        f"{LEADS}/{por_la_edicion.json()['id']}",
        headers=lead_headers,
        json=dict.fromkeys(("company", "job_title", "industry", "company_size", "country", "city"), ""),
    )
    assert vaciada.status_code == 200, vaciada.text

    columnas = ("company", "job_title", "industry", "company_size", "country", "city", "phone")
    una = db_session.query(Lead).filter(Lead.email == f"alta.{sufijo}@example.com").one()
    otra = db_session.query(Lead).filter(Lead.email == f"edicion.{sufijo}@example.com").one()
    assert [getattr(una, c) for c in columnas] == [getattr(otra, c) for c in columnas]
    assert all(getattr(una, c) is None for c in columnas)


@pytest.mark.parametrize("campo", ["first_name", "last_name", "source"])
def test_el_alta_rechaza_un_blanco_donde_la_ficha_no_existe_sin_el(client, lead_headers, campo):
    """
    422 y con el campo delante, igual que la edición desde el capítulo 33.

    `source` es el que más tiempo llevaba así: su columna es `NOT NULL` y no tenía mínimo
    declarado, así que el mismo canal en blanco respondía 201 en el alta y 422 en la edición.
    Una ficha con el canal vacío no sale en ningún informe por canal y no se puede buscar por
    el suyo.
    """
    cuerpo = {
        "first_name": "Ana",
        "last_name": "Pérez",
        "email": f"ana.{uuid.uuid4().hex[:8]}@example.com",
        campo: "   ",
    }

    respuesta = client.post(LEADS, headers=lead_headers, json=cuerpo)

    assert respuesta.status_code == 422, respuesta.text
    locs = [renglon["loc"] for renglon in respuesta.json()["detail"]]
    assert any(campo in loc for loc in locs), f"el 422 no nombra {campo}: {locs}"


def test_un_nombre_con_espacios_de_mas_se_guarda_recortado(client, lead_headers):
    """
    Lo que sí se admite: espacios alrededor de un nombre de verdad.

    Es el caso corriente —un copiado y pegado— y no tiene por qué molestar a nadie. Lo que no
    puede pasar es que los espacios cuenten para el mínimo, que es lo que hacía que tres de
    ellos fueran un nombre.
    """
    respuesta = client.post(
        LEADS,
        headers=lead_headers,
        json={
            "first_name": "  Ana  ", "last_name": " Pérez ",
            "email": f"ana.{uuid.uuid4().hex[:8]}@example.com",
        },
    )

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["first_name"] == "Ana"
    assert respuesta.json()["last_name"] == "Pérez"


def test_un_canal_en_blanco_en_una_actividad_deja_el_del_tipo(client, lead_headers, sample_lead):
    """
    `lead_activities.channel` es `NOT NULL`, y `''` lo cumple sin ser un canal.

    El campo existe para poder decir «esta apertura vino por tal herramienta»; cuando no se
    manda, lo pone el tipo de actividad. Un blanco no es ninguna de las dos cosas y acababa en
    la columna, donde el informe por canal lo cuenta como un canal más, sin nombre.
    """
    respuesta = client.post(
        f"{LEADS}/{sample_lead.id}/activities",
        headers=lead_headers,
        json={"activity_type": "EMAIL_OPEN", "channel": "  ", "notes": "   "},
    )

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["channel"].strip(), "el canal quedó en blanco"


# ==============================================================================
# 2. Las otras dos ediciones parciales
# ==============================================================================

def test_vaciar_el_nombre_de_una_publicacion_responde_422_y_no_500(
    client, admin_headers, campaigns, db_session
):
    """
    El hallazgo del capítulo 41 en la segunda puerta.

    `PUT /campaigns/{id}` aplica lo que vino, igual que la edición de una ficha, y la regla que
    el capítulo 33 escribió para que un `null` sobre una columna obligatoria no llegara al
    `commit` **solo existía para `Lead`**: estaba derivada de la tabla, que era lo difícil, y
    escrita dentro del esquema de esa tabla, que era lo que la dejaba sin compartir. Aquí el
    `null` llegaba a la base, el `commit` fallaba y la respuesta era un 500.
    """
    publicacion = campaigns[0]
    nombre = publicacion.name

    respuesta = client.put(
        f"{CAMPANAS}/{publicacion.id}", headers=admin_headers, json={"name": None}
    )

    assert respuesta.status_code == 422, respuesta.text
    assert "name" in respuesta.text
    db_session.expire_all()
    assert db_session.query(Campaign).filter(Campaign.id == publicacion.id).one().name == nombre


def test_el_nombre_de_una_publicacion_en_blanco_tambien_se_rechaza(
    client, admin_headers, campaigns
):
    """Y el blanco, que no es `None` y llegaba igual de lejos."""
    respuesta = client.put(
        f"{CAMPANAS}/{campaigns[0].id}", headers=admin_headers, json={"name": "   "}
    )

    assert respuesta.status_code == 422, respuesta.text
    assert "name" in respuesta.text


def test_los_textos_opcionales_de_una_publicacion_se_vacian_a_nulo(
    client, admin_headers, campaigns, db_session
):
    """La otra mitad: lo que la publicación sí admite vaciar queda en nulo, no en `''`."""
    publicacion = campaigns[0]
    respuesta = client.put(
        f"{CAMPANAS}/{publicacion.id}",
        headers=admin_headers,
        json={"description": "  ", "target_audience": "", "utm_source": " "},
    )

    assert respuesta.status_code == 200, respuesta.text
    db_session.expire_all()
    guardada = db_session.query(Campaign).filter(Campaign.id == publicacion.id).one()
    assert guardada.description is None
    assert guardada.target_audience is None
    assert guardada.utm_source is None


def test_vaciar_el_nombre_de_una_cuenta_responde_422_y_no_500(
    client, admin_headers, sales_reps, db_session
):
    """
    La tercera puerta, y la que más se nota: una cuenta sin nombre no identifica a nadie.

    El nombre de la cuenta es lo que aparece en la bitácora de quién hizo qué, en el reparto de
    cartera y en la ficha de cada prospecto que atiende. `{"full_name": null}` escribía `None`
    en una columna `NOT NULL` y salía como 500.
    """
    cuenta = sales_reps[0]
    nombre = cuenta.full_name

    respuesta = client.put(
        f"{USUARIOS}/{cuenta.id}", headers=admin_headers, json={"full_name": None}
    )

    assert respuesta.status_code == 422, respuesta.text
    assert "full_name" in respuesta.text
    db_session.expire_all()
    assert db_session.query(User).filter(User.id == cuenta.id).one().full_name == nombre


def test_el_nombre_de_una_cuenta_en_blanco_tambien_se_rechaza(client, admin_headers, sales_reps):
    """El mismo caso con dos espacios, que es el que pasaba el mínimo de dos caracteres."""
    respuesta = client.put(
        f"{USUARIOS}/{sales_reps[0].id}", headers=admin_headers, json={"full_name": "  "}
    )

    assert respuesta.status_code == 422, respuesta.text


def test_dar_de_alta_una_cuenta_con_un_nombre_de_espacios_responde_422(client, admin_headers):
    """
    El defecto exacto del capítulo 41, visto desde fuera.

    Dos espacios son dos caracteres, así que cumplían el `min_length=2`; el recorte venía
    después y dejaba la cadena vacía. La cuenta se creaba, con contraseña y rol, y sin nombre.
    """
    respuesta = client.post(
        USUARIOS,
        headers=admin_headers,
        json={
            "email": f"sin.nombre.{uuid.uuid4().hex[:8]}@plurione.mx",
            "full_name": "  ",
            "role": "Commercial_Executive",
            "password": CLAVE,
        },
    )

    assert respuesta.status_code == 422, respuesta.text
    assert "full_name" in respuesta.text


def test_una_sola_letra_entre_espacios_no_cumple_el_minimo_de_dos(client, admin_headers):
    """
    El caso que demuestra que lo que falla es el orden y no el mínimo.

    `' A '` son tres caracteres y pasaba; lo que se guardaba era uno. El mínimo no estaba mal
    elegido: se estaba aplicando a otra cadena.
    """
    respuesta = client.post(
        USUARIOS,
        headers=admin_headers,
        json={
            "email": f"una.letra.{uuid.uuid4().hex[:8]}@plurione.mx",
            "full_name": " A ",
            "role": "Commercial_Executive",
            "password": CLAVE,
        },
    )

    assert respuesta.status_code == 422, respuesta.text


def test_un_nombre_de_verdad_entre_espacios_se_admite_y_se_recorta(client, admin_headers, db_session):
    """Y el caso corriente sigue funcionando, ahora con el mínimo midiendo lo que se guarda."""
    correo = f"ana.{uuid.uuid4().hex[:8]}@plurione.mx"
    respuesta = client.post(
        USUARIOS,
        headers=admin_headers,
        json={
            "email": correo, "full_name": "  Ana Pérez  ",
            "role": "Commercial_Executive", "password": CLAVE,
        },
    )

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["full_name"] == "Ana Pérez"
    assert db_session.query(User).filter(User.email == correo).one().full_name == "Ana Pérez"


def test_un_cero_y_un_falso_siguen_pasando_por_las_dos_ediciones(
    client, admin_headers, campaigns, sales_reps, db_session
):
    """
    La regla nueva no puede comerse un valor que es falso sin ser vacío.

    Las dos ediciones que este capítulo gana —cuentas y publicaciones— rechazan un vacío sobre
    una columna obligatoria, y `is_active` y `budget` son obligatorias las dos. Desactivar una
    cuenta es `false` y un presupuesto de cero es una cifra: si «vacío» se hubiera escrito como
    un `not valor`, las dos operaciones responderían «este campo no puede quedar vacío», con un
    mensaje convincente y un comportamiento equivocado.
    """
    cuenta = sales_reps[0]
    baja = client.put(f"{USUARIOS}/{cuenta.id}", headers=admin_headers, json={"is_active": False})
    assert baja.status_code == 200, baja.text
    db_session.expire_all()
    assert db_session.query(User).filter(User.id == cuenta.id).one().is_active is False

    sin_presupuesto = client.put(
        f"{CAMPANAS}/{campaigns[0].id}", headers=admin_headers, json={"budget": 0}
    )
    assert sin_presupuesto.status_code == 200, sin_presupuesto.text
    assert sin_presupuesto.json()["budget"] == 0


def test_una_integracion_que_manda_blancos_no_los_escribe():
    """
    La cuarta puerta, probada donde se puede probar: el adaptador.

    `integraciones.py` tenía su propia definición de «vacío» con otro nombre, `_texto`, y ahora
    es la compartida. Esto comprueba lo que esa función garantiza —un campo en blanco de un
    formulario de LinkedIn no acaba en la columna— llamando al adaptador, porque el endpoint
    exige una firma con el secreto de cada integración y lo que hay que fijar aquí es la
    traducción, no el transporte.

    Se eligió este adaptador y no el otro por un motivo: su formulario lo rellenan personas en
    un teléfono, que es donde más blancos se producen.
    """
    from app.services.integraciones import adaptar_linkedin_lead_gen

    eventos = adaptar_linkedin_lead_gen({
        "leadId": "li-1",
        "formId": "f-1",
        "submittedAt": 1_767_225_600_000,
        "consent": {"privacyPolicy": True},
        "answers": {
            "emailAddress": " ana@example.com ",
            "firstName": "Ana",
            "lastName": "   ",
            "companyName": "",
            "jobTitle": "  ",
            "industry": " ",
            "companySize": "",
            "country": "   ",
            "city": "  ",
            "phoneNumber": " ",
        },
    })

    prospecto = eventos[0].prospecto
    assert prospecto["email"] == "ana@example.com", "el correo se recorta, no se guarda con espacios"
    for campo in ("last_name", "company", "job_title", "industry", "company_size", "country",
                  "city", "phone"):
        assert prospecto[campo] is None, f"{campo} llegó como {prospecto[campo]!r}"


# ==============================================================================
# 3. El sobre del webhook, que es lo que deduplica
# ==============================================================================

def _carga(sufijo: str, plataforma: str) -> dict:
    return {
        "event": "lead.created",
        "crm_platform": plataforma,
        "external_lead_id": f"HS-{sufijo}",
        "data": {
            "event_id": f"evt-{sufijo}",
            "first_name": "Fernanda",
            "last_name": "Ruiz",
            "email": f"fernanda.{sufijo}@example.com",
            "activity_type": "FORM_SUBMIT",
        },
    }


def test_un_espacio_en_la_plataforma_no_duplica_el_mismo_evento(client, db_session):
    """
    El sobre del webhook decidía si un evento ya había entrado, y nadie lo normalizaba.

    `crm_platform` es el prefijo del identificador con el que el evento queda marcado **para
    siempre** —`HubSpot:evt-7`—, así que «HubSpot» y «HubSpot » producían dos identificadores
    distintos para el mismo evento del mismo CRM. La segunda entrega volvía a entrar: una
    actividad repetida en la ficha y un score recalculado sobre un hecho que ocurrió una vez.
    Un espacio de más en una plantilla de integración basta, y nadie lo habría buscado ahí.
    """
    sufijo = uuid.uuid4().hex[:8]

    cuerpo, cabeceras = sign_webhook(_carga(sufijo, "HubSpot"))
    primera = client.post(WEBHOOK, content=cuerpo, headers=cabeceras)
    assert primera.status_code == 200, primera.text
    lead_id = primera.json()["lead_id"]
    actividades = db_session.query(LeadActivity).filter(LeadActivity.lead_id == lead_id).count()

    cuerpo, cabeceras = sign_webhook(
        _carga(sufijo, "HubSpot "),
        timestamp=int(datetime.datetime.now(datetime.timezone.utc).timestamp()) + 1,
    )
    segunda = client.post(WEBHOOK, content=cuerpo, headers=cabeceras)

    assert segunda.status_code == 200, segunda.text
    assert segunda.json()["lead_id"] == lead_id
    db_session.expire_all()
    assert (
        db_session.query(LeadActivity).filter(LeadActivity.lead_id == lead_id).count()
        == actividades
    ), "el mismo evento entró dos veces por un espacio en el nombre de la plataforma"


def test_el_canal_de_la_actividad_del_crm_no_lleva_el_espacio(client, db_session):
    """
    Y lo que se guarda tampoco lo lleva.

    `crm_platform` acaba en cuatro columnas `NOT NULL`, y una de ellas es el canal de la
    actividad: «HubSpot » y «HubSpot» serían dos canales en el informe por canal, con el mismo
    nombre a la vista y distintos para cualquier agrupación.
    """
    sufijo = uuid.uuid4().hex[:8]
    cuerpo, cabeceras = sign_webhook(_carga(sufijo, "  HubSpot  "))

    respuesta = client.post(WEBHOOK, content=cuerpo, headers=cabeceras)

    assert respuesta.status_code == 200, respuesta.text
    actividad = (
        db_session.query(LeadActivity)
        .filter(LeadActivity.lead_id == respuesta.json()["lead_id"])
        .first()
    )
    assert actividad.channel == "HubSpot"


def test_un_sobre_sin_plataforma_se_rechaza_con_422(client):
    """
    Un webhook sin plataforma no identifica a su emisor, y su canal sería una columna vacía.

    Es un 422 y no un apaño porque al otro lado hay un sistema que puede corregirlo: el emisor
    recibe el motivo y el campo. Es la diferencia con el alta por webhook de una ficha sin
    nombre, que se admite vacía a propósito desde el capítulo 25 —ahí no hay nadie a quien
    decírselo y perder el prospecto sería peor que no saber cómo se llama.
    """
    cuerpo, cabeceras = sign_webhook(_carga(uuid.uuid4().hex[:8], "   "))

    respuesta = client.post(WEBHOOK, content=cuerpo, headers=cabeceras)

    assert respuesta.status_code == 422, respuesta.text
    assert "crm_platform" in respuesta.text


def test_el_webhook_sigue_admitiendo_una_ficha_sin_nombre(client, db_session):
    """
    La asimetría que **no** se corrige, y que conviene fijar para que no se corrija por error.

    Donde hay una persona delante —el alta del panel, la edición— un campo indispensable en
    blanco es un 422: puede corregirlo ahora. Donde no hay nadie —un CRM que entrega lo que
    tiene— rechazar el evento perdería el prospecto entero, y el capítulo 25 ya decidió que un
    nombre vacío es mejor que un «Prospecto» inventado. La regla de este capítulo es que el
    blanco signifique una sola cosa, no que se responda lo mismo a todo el mundo.
    """
    sufijo = uuid.uuid4().hex[:8]
    carga = _carga(sufijo, "HubSpot")
    carga["data"]["first_name"] = "   "
    carga["data"]["last_name"] = ""
    cuerpo, cabeceras = sign_webhook(carga)

    respuesta = client.post(WEBHOOK, content=cuerpo, headers=cabeceras)

    assert respuesta.status_code == 200, respuesta.text
    ficha = db_session.query(Lead).filter(Lead.id == respuesta.json()["lead_id"]).one()
    assert ficha.first_name == ""
    assert ficha.last_name == ""
    assert ficha.email == f"fernanda.{sufijo}@example.com"
