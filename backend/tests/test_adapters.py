import pytest
from app.adapters.azure_ml_adapter import LocalMLScoringAdapter, get_ml_scoring_adapter
from app.adapters.azure_openai_adapter import LocalMockOpenAIAdapter, get_ai_explanation_adapter
from app.adapters.azure_search_adapter import LocalMockSearchAdapter, get_ai_search_adapter


@pytest.mark.asyncio
async def test_local_ml_adapter_inference():
    adapter = LocalMLScoringAdapter()
    assert adapter.is_healthy() is True

    features_hot = {
        "job_title": "CTO",
        "industry": "FinTech",
        "company_size": "1000+",
        "annual_revenue": 10000000.0,
        "source": "Demo Request Form",
        "page_views": 10,
        "email_opens": 5,
        "email_clicks": 3,
        "content_downloads": 2,
        "attended_webinar": 1,
        "requested_demo": 1,
        "days_since_last_activity": 0.0,
    }
    prob_hot = await adapter.predict_conversion_probability(features_hot)
    assert 0.0 <= prob_hot <= 1.0
    assert prob_hot >= 0.50

    features_cold = {
        "job_title": "Trainee",
        "industry": "Educación",
        "company_size": "1-10",
        "annual_revenue": 50000.0,
        "source": "Organic Search",
        "page_views": 1,
        "email_opens": 0,
        "email_clicks": 0,
        "content_downloads": 0,
        "attended_webinar": 0,
        "requested_demo": 0,
        "days_since_last_activity": 35.0,
    }
    prob_cold = await adapter.predict_conversion_probability(features_cold)
    assert 0.0 <= prob_cold <= 1.0
    assert prob_cold < prob_hot


@pytest.mark.asyncio
async def test_local_mock_openai_explanation():
    adapter = LocalMockOpenAIAdapter()
    lead_meta = {
        "first_name": "Carlos",
        "company": "Banco Digital",
        "job_title": "CIO",
        "industry": "Banking",
        "days_since_last_activity": 2,
    }
    breakdown = {
        "title_fit_score": 25.0,
        "industry_fit_score": 15.0,
        "behavior_raw_total": 30.0,
    }
    explanation = await adapter.generate_explanation(lead_meta, 88.5, "HOT", breakdown)
    assert "summary" in explanation
    assert "strengths" in explanation
    assert len(explanation["strengths"]) >= 1
    assert "recommended_action" in explanation
    assert "15 minutos" in explanation["recommended_action"]


@pytest.mark.asyncio
async def test_local_mock_search_adapter():
    adapter = LocalMockSearchAdapter()
    results = await adapter.search_similar_leads("FinTech CTO", top_k=2)
    assert isinstance(results, list)
    assert len(results) <= 2
    if results:
        assert "similarity_score" in results[0]
        assert "outcome" in results[0]


def test_adapter_factories():
    ml_adapter = get_ml_scoring_adapter()
    assert ml_adapter is not None
    assert ml_adapter.is_healthy() is True

    ai_adapter = get_ai_explanation_adapter()
    assert ai_adapter is not None

    search_adapter = get_ai_search_adapter()
    assert search_adapter is not None
