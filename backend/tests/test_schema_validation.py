"""
Validación de entrada: campos completos, tipos cerrados y longitudes acotadas.

Cubre los defectos M-1 (campos que el simulador enviaba y el schema descartaba),
M-3 (unicidad de correo al actualizar), M-4 (`activity_type` aceptaba texto libre) y
M-5 (esquemas de texto sin `max_length`).

El hilo común de los cuatro es el mismo: la API aceptaba datos que después no podía
honrar. Unos se perdían en silencio, otros llegaban a la base de datos y reventaban
allí como un 500 sin decir qué campo era el culpable.
"""
import uuid

import pytest
from tests.conftest import sign_webhook

PREDICT_URL = "/api/v1/scoring/predict"
LEADS_URL = "/api/v1/leads"

# Perfil deliberadamente mediocre: 7 (Analista) + 8 (Manufactura) + 3 (11-50) = 18
# puntos firmográficos y cero comportamiento. Así cada señal que se active después
# aparece como una diferencia exacta y no queda enmascarada por el tope de 50 puntos.
PERFIL_BASE = {
    "job_title": "Analista de Compras",
    "industry": "Manufactura",
    "company_size": "11-50",
    "page_views": 0,
    "email_opens": 0,
    "email_clicks": 0,
    "content_downloads": 0,
    "attended_webinar": False,
    "requested_demo": False,
    "days_since_last_activity": 0.0,
}
HEURISTICO_BASE = 18.0


def _predict(client, headers, **overrides):
    payload = {**PERFIL_BASE, **overrides}
    response = client.post(PREDICT_URL, json=payload, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _nuevo_lead(client, headers, **overrides):
    unique = uuid.uuid4().hex[:10]
    payload = {
        "first_name": "Prueba",
        "last_name": "Esquemas",
        "email": f"prueba.esquemas.{unique}@empresa.mx",
        "company": "Empresa de Prueba",
        "job_title": "Gerente de TI",
        "industry": "Software/TI",
        "company_size": "51-200",
    }
    payload.update(overrides)
    return payload


# ============================================================================
# M-1: campos que el simulador ya enviaba y el schema no declaraba
# ============================================================================

def test_el_perfil_base_puntua_solo_lo_firmografico(client, lead_headers):
    assert _predict(client, lead_headers)["heuristic_score"] == HEURISTICO_BASE


@pytest.mark.parametrize(
    "campo, valor, puntos_esperados",
    [
        ("proposal_sent", True, 25.0),
        ("meeting_scheduled", True, 20.0),
        ("urgency", "INMEDIATA", 10.0),
    ],
)
def test_los_campos_del_simulador_si_mueven_el_score(client, lead_headers, campo, valor, puntos_esperados):
    """
    Antes de M-1 estos tres campos no estaban declarados en `ScorePredictRequest`.

    Pydantic los descartaba sin avisar, de modo que marcar "Propuesta enviada" o
    "Reunión agendada" en el simulador devolvía exactamente el mismo número que no
    marcarlas: la interfaz prometía +25 y +20 puntos que nunca llegaban al cálculo.
    """
    resultado = _predict(client, lead_headers, **{campo: valor})
    assert resultado["heuristic_score"] == HEURISTICO_BASE + puntos_esperados


def test_las_senales_comerciales_se_acumulan(client, lead_headers):
    resultado = _predict(
        client, lead_headers,
        proposal_sent=True, meeting_scheduled=True, urgency="INMEDIATA",
    )
    # 25 + 20 + 10 = 55, recortado al tope de 50 puntos de comportamiento
    assert resultado["rule_breakdown"]["behavior_raw_total"] == 50.0
    assert resultado["heuristic_score"] == HEURISTICO_BASE + 50.0


def test_un_campo_desconocido_se_rechaza_en_vez_de_ignorarse(client, lead_headers):
    """
    `extra="forbid"` cierra el agujero de raíz: un campo mal escrito o no implementado
    devuelve 422 en lugar de desaparecer sin dejar rastro, que es como M-1 pasó
    inadvertido tanto tiempo.
    """
    response = client.post(
        PREDICT_URL,
        json={**PERFIL_BASE, "requsted_demo": True},  # typo deliberado
        headers=lead_headers,
    )
    assert response.status_code == 422


@pytest.mark.parametrize("campo, valor", [("page_views", -5), ("days_since_last_activity", -1.0)])
def test_los_contadores_negativos_se_rechazan(client, lead_headers, campo, valor):
    response = client.post(PREDICT_URL, json={**PERFIL_BASE, campo: valor}, headers=lead_headers)
    assert response.status_code == 422


# ============================================================================
# M-4: `activity_type` restringido al enum
# ============================================================================

@pytest.mark.parametrize(
    "tipo_invalido",
    [
        "ME_LO_ACABO_DE_INVENTAR",
        "page_view",          # el enum distingue mayúsculas
        "PAGE VIEW",
        "DROP TABLE leads",
        "",
        123,
        None,
    ],
)
def test_un_tipo_de_actividad_invalido_se_rechaza(client, lead_headers, sample_lead, tipo_invalido):
    """
    El schema aceptaba `Union[ActivityType, str]`, así que cualquier cadena entraba y
    acababa escrita en una columna Enum. En SQLite se guardaba tal cual y el motor de
    scoring luego no la reconocía —la actividad no sumaba nada—; en PostgreSQL el
    INSERT fallaba dentro del servicio y salía como 500.
    """
    response = client.post(
        f"{LEADS_URL}/{sample_lead.id}/activities",
        json={"activity_type": tipo_invalido, "channel": "Web"},
        headers=lead_headers,
    )
    assert response.status_code == 422


def test_un_tipo_de_actividad_invalido_no_deja_rastro(client, lead_headers, sample_lead, db_session):
    """El rechazo es previo al servicio: no se persiste ninguna actividad."""
    from app.models.entities import LeadActivity

    client.post(
        f"{LEADS_URL}/{sample_lead.id}/activities",
        json={"activity_type": "TIPO_FANTASMA", "channel": "Web"},
        headers=lead_headers,
    )
    assert db_session.query(LeadActivity).filter(LeadActivity.lead_id == sample_lead.id).count() == 0


@pytest.mark.parametrize(
    ("tipo_valido", "complemento"),
    [
        ("WEBINAR_ATTEND", {}),
        ("DEMO_REQUEST", {}),
        # Desde la Fase 15 la llamada lleva su resultado y el mensaje su dirección: sin ellos
        # el tipo sigue siendo válido, pero el evento no (test_registro_de_actividad.py).
        ("PHONE_CALL", {"call_outcome": "CONECTO"}),
        ("LINKEDIN_MESSAGE", {"direction": "SALIENTE"}),
        ("CUSTOM", {}),
    ],
)
def test_los_tipos_de_actividad_del_enum_se_aceptan(client, lead_headers, sample_lead, tipo_valido, complemento):
    response = client.post(
        f"{LEADS_URL}/{sample_lead.id}/activities",
        json={"activity_type": tipo_valido, "channel": "Zoom", **complemento},
        headers=lead_headers,
    )
    assert response.status_code == 201
    assert response.json()["activity_type"] == tipo_valido


def test_una_actividad_inicial_inventada_se_rechaza_en_el_alta(client, lead_headers):
    payload = _nuevo_lead(client, lead_headers, initial_activity_type="EVENTO_FANTASMA")
    response = client.post(LEADS_URL, json=payload, headers=lead_headers)
    assert response.status_code == 422


# ============================================================================
# M-5: longitudes acotadas en todos los esquemas de texto
# ============================================================================

@pytest.mark.parametrize(
    "campo, maximo",
    [("first_name", 100), ("last_name", 100), ("company", 150), ("job_title", 100),
     ("industry", 100), ("city", 100), ("source", 100), ("phone", 50)],
)
def test_el_alta_rechaza_textos_mas_largos_que_la_columna(client, lead_headers, campo, maximo):
    payload = _nuevo_lead(client, lead_headers, **{campo: "A" * (maximo + 1)})
    response = client.post(LEADS_URL, json=payload, headers=lead_headers)
    assert response.status_code == 422


def test_el_alta_acepta_un_texto_justo_en_el_limite(client, lead_headers):
    payload = _nuevo_lead(client, lead_headers, company="A" * 150)
    response = client.post(LEADS_URL, json=payload, headers=lead_headers)
    assert response.status_code == 201


def test_la_actualizacion_tambien_acota_las_longitudes(client, lead_headers):
    creado = client.post(LEADS_URL, json=_nuevo_lead(client, lead_headers), headers=lead_headers).json()
    response = client.put(
        f"{LEADS_URL}/{creado['id']}",
        json={"job_title": "B" * 101},
        headers=lead_headers,
    )
    assert response.status_code == 422


def test_el_webhook_crm_acota_los_campos_que_copia_a_columnas(client):
    """
    El webhook es la única entrada que no pasa por `LeadCreate`. Su `data` sigue siendo
    abierto —los campos desconocidos se conservan en `raw_metadata`—, pero los que
    aterrizan en columnas se validan aquí.
    """
    payload = {
        "event": "form.submission",
        "crm_platform": "HubSpot",
        "external_lead_id": f"HS-LEN-{uuid.uuid4().hex[:8]}",
        "data": {
            "first_name": "Nombre",
            "email": f"largo.{uuid.uuid4().hex[:8]}@empresa.mx",
            "company": "C" * 200,
        },
    }
    body, headers = sign_webhook(payload)
    response = client.post("/api/v1/crm/webhook", content=body, headers=headers)
    assert response.status_code == 422


def test_el_webhook_crm_conserva_los_campos_desconocidos(client):
    """Acotar los campos conocidos no debe cerrar la extensibilidad del payload."""
    unique = uuid.uuid4().hex[:8]
    payload = {
        "event": "form.submission",
        "crm_platform": "Zoho",
        "external_lead_id": f"ZH-EXT-{unique}",
        "data": {
            "first_name": "Campos",
            "last_name": "Extra",
            "email": f"campos.extra.{unique}@empresa.mx",
            "company": "Empresa Extensible",
            "campo_propio_del_crm": "valor que solo entiende el emisor",
            # Obligatorio desde la Fase 15: sin él el webhook no inventa un FORM_SUBMIT.
            "activity_type": "FORM_SUBMIT",
        },
    }
    body, headers = sign_webhook(payload)
    response = client.post("/api/v1/crm/webhook", content=body, headers=headers)
    assert response.status_code == 200


# ============================================================================
# M-3: unicidad de correo al actualizar
# ============================================================================

def test_no_se_puede_reasignar_el_correo_de_otro_prospecto(client, lead_headers):
    """
    `update` escribía el correo sin comprobar nada. La columna es ÚNICA, así que el
    conflicto salía como IntegrityError convertido en 500 genérico, sin decirle al
    usuario que el problema era un correo repetido.
    """
    primero = client.post(LEADS_URL, json=_nuevo_lead(client, lead_headers), headers=lead_headers).json()
    segundo = client.post(LEADS_URL, json=_nuevo_lead(client, lead_headers), headers=lead_headers).json()

    response = client.put(
        f"{LEADS_URL}/{segundo['id']}",
        json={"email": primero["email"]},
        headers=lead_headers,
    )
    assert response.status_code == 409
    assert primero["email"] in response.json()["detail"]

    # El prospecto conserva su correo original: el rechazo no dejó nada a medias.
    sin_cambios = client.get(f"{LEADS_URL}/{segundo['id']}", headers=lead_headers).json()
    assert sin_cambios["email"] == segundo["email"]


def test_el_conflicto_de_correo_no_distingue_mayusculas(client, lead_headers):
    """
    La deduplicación del webhook CRM busca por el correo en minúsculas. Si la
    comprobación fuese sensible a mayúsculas, `OTRO@X.COM` entraría como un prospecto
    distinto de `otro@x.com` y luego ninguna de las dos filas se encontraría.
    """
    primero = client.post(LEADS_URL, json=_nuevo_lead(client, lead_headers), headers=lead_headers).json()
    segundo = client.post(LEADS_URL, json=_nuevo_lead(client, lead_headers), headers=lead_headers).json()

    response = client.put(
        f"{LEADS_URL}/{segundo['id']}",
        json={"email": primero["email"].upper()},
        headers=lead_headers,
    )
    assert response.status_code == 409


def test_reenviar_el_propio_correo_no_es_conflicto(client, lead_headers):
    """Guardar el formulario sin tocar el correo debe seguir funcionando."""
    lead = client.post(LEADS_URL, json=_nuevo_lead(client, lead_headers), headers=lead_headers).json()

    response = client.put(
        f"{LEADS_URL}/{lead['id']}",
        json={"email": lead["email"], "city": "Monterrey"},
        headers=lead_headers,
    )
    assert response.status_code == 200
    assert response.json()["city"] == "Monterrey"


def test_cambiar_el_correo_a_uno_libre_se_normaliza_a_minusculas(client, lead_headers):
    lead = client.post(LEADS_URL, json=_nuevo_lead(client, lead_headers), headers=lead_headers).json()
    nuevo = f"NUEVO.CORREO.{uuid.uuid4().hex[:8]}@EMPRESA.MX"

    response = client.put(f"{LEADS_URL}/{lead['id']}", json={"email": nuevo}, headers=lead_headers)
    assert response.status_code == 200
    assert response.json()["email"] == nuevo.lower()


def test_el_webhook_crm_deduplica_contra_un_prospecto_dado_de_alta_por_la_api(client, lead_headers):
    """
    Las dos vías de entrada comparten la misma clave de deduplicación.

    El alta por API normaliza el correo a minúsculas y el webhook busca en minúsculas. Si
    una de las dos dejara de hacerlo, el mismo prospecto entraría dos veces con
    puntuaciones distintas y el equipo comercial lo trabajaría por duplicado.
    """
    unique = uuid.uuid4().hex[:10]
    correo = f"Doble.Entrada.{unique}@Empresa.MX"

    creado = client.post(
        LEADS_URL,
        json=_nuevo_lead(client, lead_headers, email=correo),
        headers=lead_headers,
    ).json()
    assert creado["email"] == correo.lower()

    payload = {
        "event": "form.submission",
        "crm_platform": "Salesforce",
        "external_lead_id": f"SF-DEDUP-{unique}",
        "data": {
            "first_name": "Doble",
            "last_name": "Entrada",
            "email": correo.upper(),
            "job_title": "CTO",
            "activity_type": "DEMO_REQUEST",
        },
    }
    body, headers = sign_webhook(payload)
    respuesta = client.post("/api/v1/crm/webhook", content=body, headers=headers)
    assert respuesta.status_code == 200
    # Mismo identificador: el webhook actualizó el prospecto existente en vez de crear otro
    assert respuesta.json()["lead_id"] == creado["id"]

    listado = client.get(f"{LEADS_URL}?search=doble.entrada", headers=lead_headers).json()
    assert listado["total"] == 1
