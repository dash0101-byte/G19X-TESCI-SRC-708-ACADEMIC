"""
Pruebas funcionales de la API.

Cada prueba declara los datos que necesita mediante fixtures. Antes operaban sobre lo que
`seed_data.py` hubiera dejado en la base real, así que las aserciones tenían que ser
vagas (`total_leads > 0`) y la suite fallaba entera si el sembrado no se había ejecutado
—que es justo lo que ocurría en el CI cuando el orden de los pasos se invertía—. Con
datos propios y deterministas se pueden afirmar cifras exactas.
"""
import uuid


def test_health_endpoints(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "PluriOne" in data["app"]

    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "healthy"


# ==============================================================================
# Listado paginado
# ==============================================================================

def test_list_leads(client, lead_headers, sample_leads):
    """
    El endpoint devuelve una página, no una lista suelta.

    La prueba afirmaba `isinstance(data, list)` sobre una respuesta que ya era
    `{items, total, limit, offset}`; sobrevivía solo porque nadie la ejecutaba contra
    datos conocidos. Ahora se comprueba el contrato completo que consume el frontend.
    """
    response = client.get("/api/v1/leads?limit=10", headers=lead_headers)
    assert response.status_code == 200
    payload = response.json()

    assert set(payload) == {"items", "total", "limit", "offset"}
    assert payload["total"] == len(sample_leads)
    assert payload["limit"] == 10
    assert payload["offset"] == 0
    assert len(payload["items"]) == len(sample_leads)

    scores = [lead["current_score"] for lead in payload["items"]]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == 92.4


def test_list_leads_pagina_de_verdad(client, lead_headers, sample_leads):
    """`limit` y `offset` recortan la página pero `total` sigue contando el universo."""
    primera = client.get("/api/v1/leads?limit=2&offset=0", headers=lead_headers).json()
    segunda = client.get("/api/v1/leads?limit=2&offset=2", headers=lead_headers).json()

    assert primera["total"] == segunda["total"] == len(sample_leads)
    assert len(primera["items"]) == len(segunda["items"]) == 2
    assert primera["offset"] == 0
    assert segunda["offset"] == 2

    ids_primera = {lead["id"] for lead in primera["items"]}
    ids_segunda = {lead["id"] for lead in segunda["items"]}
    assert ids_primera.isdisjoint(ids_segunda)

    # El orden global por score se mantiene entre páginas
    assert min(lead["current_score"] for lead in primera["items"]) >= max(
        lead["current_score"] for lead in segunda["items"]
    )


def test_list_leads_filtra_por_categoria(client, lead_headers, sample_leads):
    response = client.get("/api/v1/leads?score_category=HOT", headers=lead_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert all(lead["score_category"] == "HOT" for lead in payload["items"])


def test_list_leads_busca_por_texto(client, lead_headers, sample_leads):
    response = client.get("/api/v1/leads?search=fintech", headers=lead_headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["email"] == "elena.ruiz@fintechmx.com"


# ==============================================================================
# Alta y scoring
# ==============================================================================

def test_create_and_score_lead(client, lead_headers):
    unique_id = uuid.uuid4().hex[:8]
    test_email = f"valeria.soto.{unique_id}@fintechcorp.mx"
    payload = {
        "first_name": "Valeria",
        "last_name": "Soto",
        "email": test_email,
        "phone": "+52 55 9876 5432",
        "company": "FinTech Corp México",
        "job_title": "CTO",
        "industry": "FinTech",
        "company_size": "201-1000",
        "annual_revenue": 4500000.0,
        "country": "México",
        "city": "CDMX",
        "source": "LinkedIn Ads",
        "initial_activity_type": "DEMO_REQUEST",
        "initial_notes": "Solicitud prioritaria de demo para Squad de Backend Python",
    }
    response = client.post("/api/v1/leads", json=payload, headers=lead_headers)
    assert response.status_code == 201
    lead = response.json()
    assert lead["id"] > 0
    assert lead["email"] == test_email
    # Dado que es CTO de FinTech y pidió Demo, el score entra en categoría WARM / HOT
    assert lead["current_score"] >= 50.0
    assert lead["score_category"] in ["HOT", "WARM"]

    # Consultar detalle 360
    detail_resp = client.get(f"/api/v1/leads/{lead['id']}", headers=lead_headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert len(detail["activities"]) >= 1
    assert len(detail["score_histories"]) >= 1
    assert detail["latest_explanation"] is not None
    assert "summary" in detail["latest_explanation"]


def test_no_se_puede_dar_de_alta_dos_veces_el_mismo_correo(client, lead_headers):
    payload = {
        "first_name": "Duplicado",
        "last_name": "Alta",
        "email": f"duplicado.alta.{uuid.uuid4().hex[:8]}@empresa.mx",
        "job_title": "Gerente de TI",
        "industry": "Software/TI",
    }
    assert client.post("/api/v1/leads", json=payload, headers=lead_headers).status_code == 201
    repetido = client.post("/api/v1/leads", json=payload, headers=lead_headers)
    assert repetido.status_code == 400
    assert "Ya existe" in repetido.json()["detail"]


def test_add_activity_and_dynamic_rescoring(client, lead_headers, sample_lead):
    """Registrar una actividad de alto valor recalcula el score del prospecto."""
    lead_id = sample_lead.id

    act_payload = {
        "activity_type": "WEBINAR_ATTEND",
        "channel": "Zoom",
        "activity_weight": 6.0,
        "activity_data": {"webinar_name": "IA para Headhunting 2026", "duration_min": 60},
    }
    act_resp = client.post(f"/api/v1/leads/{lead_id}/activities", json=act_payload, headers=lead_headers)
    assert act_resp.status_code == 201
    assert act_resp.json()["activity_type"] == "WEBINAR_ATTEND"

    updated_lead = client.get(f"/api/v1/leads/{lead_id}", headers=lead_headers).json()
    assert len(updated_lead["activities"]) == 1
    # El alta de la actividad dispara el pipeline y deja traza en el historial
    assert len(updated_lead["score_histories"]) >= 1


def test_standalone_scoring_prediction(client, lead_headers):
    payload = {
        "first_name": "Mauricio",
        "company": "Banca Digital MX",
        "job_title": "VP of Engineering",
        "industry": "Banking",
        "company_size": "1000+",
        "annual_revenue": 20000000.0,
        "source": "Demo Request Form",
        "page_views": 8,
        "email_opens": 4,
        "email_clicks": 3,
        "content_downloads": 2,
        "attended_webinar": True,
        "requested_demo": True,
        "days_since_last_activity": 1.0,
    }
    response = client.post("/api/v1/scoring/predict", json=payload, headers=lead_headers)
    assert response.status_code == 200
    res = response.json()
    assert res["score"] >= 75.0
    assert res["score_category"] == "HOT"
    assert res["ai_explanation"] is not None
    assert "recommended_action" in res["ai_explanation"]


# ==============================================================================
# Analítica y operaciones por lotes
# ==============================================================================

def test_analytics_summary(client, lead_headers, sample_leads):
    """Los KPIs se contrastan contra la composición exacta del conjunto de prueba."""
    response = client.get("/api/v1/analytics/summary", headers=lead_headers)
    assert response.status_code == 200
    summary = response.json()

    assert summary["total_leads"] == len(sample_leads)
    assert summary["hot_leads_count"] == 2
    assert summary["warm_leads_count"] == 2
    assert summary["cold_leads_count"] == 2

    esperado = round(sum(lead.current_score for lead in sample_leads) / len(sample_leads), 1)
    assert summary["average_score"] == esperado

    industrias = {fila["industry"] for fila in summary["top_industries"]}
    assert "FinTech" in industrias
    assert len(summary["leads_by_source"]) >= 1


def test_analytics_summary_sin_datos_no_falla(client, lead_headers):
    """
    Una base vacía debe devolver ceros, no una división por cero.

    Con la suite corriendo sobre datos sembrados este caso no era comprobable: nunca
    había cero prospectos.
    """
    response = client.get("/api/v1/analytics/summary", headers=lead_headers)
    assert response.status_code == 200
    summary = response.json()
    assert summary["total_leads"] == 0
    assert summary["average_score"] == 0.0
    assert summary["mql_to_sql_conversion_rate"] == 0.0


def test_batch_recalculation(client, lead_headers, sample_leads):
    """
    El recálculo masivo se acepta y se ejecuta; ya no responde con el resultado.

    El detalle del ciclo de vida del trabajo se prueba en `test_recalculation_jobs.py`;
    aquí solo se comprueba que el endpoint sigue siendo utilizable desde el frontend.
    """
    response = client.post("/api/v1/leads/batch/recalculate-all", headers=lead_headers)
    assert response.status_code == 202

    trabajo = response.json()
    assert trabajo["total_leads"] == len(sample_leads)

    estado = client.get(f"/api/v1/leads/batch/jobs/{trabajo['id']}", headers=lead_headers)
    assert estado.status_code == 200
    assert estado.json()["processed_leads"] == len(sample_leads)
