from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseMLScoringAdapter(ABC):
    """
    Puerto / Interfaz abstracta para la inferencia del modelo predictivo de Machine Learning.
    Permite alternar entre inferencia local (Scikit-Learn / XGBoost) y Azure Machine Learning Endpoint.
    """

    @abstractmethod
    async def predict_conversion_probability(self, features: Dict[str, Any]) -> float:
        """Calcula la probabilidad de conversión de un prospecto (0.0 a 1.0)."""
        pass

    @abstractmethod
    def is_healthy(self) -> bool:
        """Verifica la disponibilidad del servicio o modelo de inferencia."""
        pass

    def version_del_motor(self) -> str:
        """
        Identifica qué motor produjo la probabilidad, para el registro de auditoría.

        No es metadato decorativo. `ScoreHistory` guardaba `settings.MODEL_VERSION`, una
        constante de configuración, de modo que el historial afirmaba haber usado el
        modelo híbrido incluso cuando el artefacto no había llegado a cargarse y quien
        puntuó fue el heurístico de contingencia. Con eso, el registro que existe para
        poder explicar por qué se priorizó un prospecto afirmaba algo falso, y la
        degradación —el fallo real de A-5— quedaba invisible precisamente en el sitio
        donde se habría detectado.

        El valor por defecto es deliberadamente poco halagüeño: un adaptador que no
        declare su motor no debe heredar el nombre del bueno.
        """
        return "desconocido"


class BaseAIExplanationAdapter(ABC):
    """
    Puerto / Interfaz abstracta para la generación de explicaciones en lenguaje natural y recomendaciones comerciales.
    Permite alternar entre generación local basada en reglas/plantillas heurísticas y Azure OpenAI Service.
    """

    @abstractmethod
    async def generate_explanation(
        self,
        lead_data: Dict[str, Any],
        score: float,
        score_category: str,
        heuristic_breakdown: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Genera resumen ejecutivo, fortalezas del prospecto y recomendación táctica."""
        pass


class BaseAISearchAdapter(ABC):
    """
    Puerto / Interfaz abstracta para búsqueda semántica e indexación de interacciones de prospectos.
    Permite alternar entre búsqueda en base de datos local y Azure AI Search.
    """

    @abstractmethod
    async def search_similar_leads(self, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Busca prospectos con perfiles o comportamientos similares."""
        pass
