import logging
from functools import lru_cache
from typing import Any, Dict, List

from app.adapters.base import BaseAISearchAdapter
from app.core.config import settings

logger = logging.getLogger(__name__)


class LocalMockSearchAdapter(BaseAISearchAdapter):
    """
    Adaptador Local de Búsqueda ($0 USD).
    Simula la indexación y recuperación semántica de prospectos convertidos similares.
    """

    async def search_similar_leads(self, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        # Simular coincidencias contextuales
        return [
            {
                "lead_id": 1,
                "company": "FinTech Avanzada S.A.P.I.",
                "industry": "FinTech",
                "job_title": "CTO",
                "similarity_score": 0.94,
                "outcome": "WON",
                "key_insight": "Conversión exitosa tras demo personalizada de contratación de Squads TI.",
            },
            {
                "lead_id": 8,
                "company": "Banco Regional del Centro",
                "industry": "Banking",
                "job_title": "CIO",
                "similarity_score": 0.89,
                "outcome": "WON",
                "key_insight": "Interés en staffing especializado de desarrolladores Java y Arquitectos Cloud.",
            },
        ][:top_k]


class AzureAISearchAdapter(BaseAISearchAdapter):
    """
    Adaptador de producción para Azure AI Search.
    """

    def __init__(self):
        self.endpoint = settings.AZURE_AI_SEARCH_ENDPOINT
        self.api_key = settings.AZURE_AI_SEARCH_KEY
        self.index_name = settings.AZURE_AI_SEARCH_INDEX

    async def search_similar_leads(self, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        # En producción consumiría la API REST de Azure Search
        return []


@lru_cache(maxsize=4)
def _construir_adaptador_busqueda(modo: str, endpoint: str, indice: str) -> BaseAISearchAdapter:
    """Los argumentos son la clave de la caché: si cambia la configuración, cambia el adaptador."""
    if modo == "azure":
        return AzureAISearchAdapter()
    return LocalMockSearchAdapter()


def get_ai_search_adapter() -> BaseAISearchAdapter:
    return _construir_adaptador_busqueda(
        settings.AI_MODE.lower(),
        settings.AZURE_AI_SEARCH_ENDPOINT or "",
        settings.AZURE_AI_SEARCH_INDEX or "",
    )


def reset_search_adapter_cache() -> None:
    """Vacía la caché de adaptadores de búsqueda."""
    _construir_adaptador_busqueda.cache_clear()
