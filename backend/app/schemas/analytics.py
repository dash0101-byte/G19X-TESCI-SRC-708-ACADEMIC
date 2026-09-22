from typing import Any, Dict, List

from pydantic import BaseModel


class AnalyticsSummary(BaseModel):
    total_leads: int
    hot_leads_count: int
    warm_leads_count: int
    cold_leads_count: int
    average_score: float
    mql_to_sql_conversion_rate: float
    pipeline_distribution: Dict[str, int]
    top_industries: List[Dict[str, Any]]
    leads_by_source: List[Dict[str, Any]]


class CampaignPerformance(BaseModel):
    campaign_id: int
    campaign_name: str
    channel: str
    budget: float
    total_leads: int
    hot_leads: int
    avg_score: float
    conversion_rate: float
