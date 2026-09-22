from app.adapters.azure_ml_adapter import (
    AzureMLScoringAdapter,
    LocalMLScoringAdapter,
    NativeMLScoringAdapter,
    get_ml_scoring_adapter,
    reset_ml_adapter_cache,
)
from app.adapters.azure_openai_adapter import (
    AzureOpenAIAdapter,
    LocalMockOpenAIAdapter,
    NativeXAIExplanationAdapter,
    get_ai_explanation_adapter,
    reset_explanation_adapter_cache,
)
from app.adapters.azure_search_adapter import (
    AzureAISearchAdapter,
    LocalMockSearchAdapter,
    get_ai_search_adapter,
    reset_search_adapter_cache,
)
from app.adapters.base import (
    BaseAIExplanationAdapter,
    BaseAISearchAdapter,
    BaseMLScoringAdapter,
)

__all__ = [
    "BaseMLScoringAdapter",
    "BaseAIExplanationAdapter",
    "BaseAISearchAdapter",
    "get_ml_scoring_adapter",
    "NativeMLScoringAdapter",
    "LocalMLScoringAdapter",
    "AzureMLScoringAdapter",
    "get_ai_explanation_adapter",
    "NativeXAIExplanationAdapter",
    "LocalMockOpenAIAdapter",
    "AzureOpenAIAdapter",
    "get_ai_search_adapter",
    "LocalMockSearchAdapter",
    "AzureAISearchAdapter",
    # Vaciado de las cachés de fábrica: las pruebas mueven `settings` y necesitan
    # descartar el adaptador construido con la configuración anterior.
    "reset_ml_adapter_cache",
    "reset_explanation_adapter_cache",
    "reset_search_adapter_cache",
]
