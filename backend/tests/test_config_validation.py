"""
Coherencia de la configuración al arrancar (M-2 y M-12).

Ambos defectos comparten forma: configuraciones inválidas que el sistema aceptaba sin
protestar y que solo se manifestaban más tarde, lejos de su causa —una como
`AttributeError` en mitad de una petición, la otra como puntuaciones sesgadas que
nunca disparaban ningún error.
"""
import pytest
from app.adapters.azure_search_adapter import AzureAISearchAdapter
from app.core.config import Settings

# Cualquier valor lo bastante largo y no comprometido: estas pruebas no evalúan la
# validación de SECRET_KEY, pero `Settings` la exige para construirse.
CLAVE_VALIDA = "clave-de-pruebas-suficientemente-larga-para-pasar-el-minimo"


def _settings(**overrides) -> Settings:
    return Settings(SECRET_KEY=CLAVE_VALIDA, **overrides)


# ============================================================================
# M-2: las credenciales de Azure AI Search faltaban en Settings
# ============================================================================

def test_settings_declara_las_variables_de_azure_ai_search():
    """
    `AzureAISearchAdapter` leía `settings.AZURE_AI_SEARCH_*` en su constructor, pero
    esas variables no existían: arrancar con AI_MODE=azure moría con un AttributeError
    en tiempo de petición en vez de con un error de configuración legible.
    """
    settings = _settings()
    assert settings.AZURE_AI_SEARCH_ENDPOINT == ""
    assert settings.AZURE_AI_SEARCH_KEY == ""
    assert settings.AZURE_AI_SEARCH_INDEX


def test_el_adaptador_de_busqueda_azure_se_construye_sin_error():
    """Es la comprobación que importa: el adaptador se instancia sin reventar."""
    adaptador = AzureAISearchAdapter()
    assert adaptador.index_name


def test_las_variables_de_azure_ai_search_se_leen_del_entorno():
    settings = _settings(
        AZURE_AI_SEARCH_ENDPOINT="https://busqueda.search.windows.net",
        AZURE_AI_SEARCH_KEY="clave-de-busqueda",
        AZURE_AI_SEARCH_INDEX="indice-personalizado",
    )
    assert settings.AZURE_AI_SEARCH_ENDPOINT == "https://busqueda.search.windows.net"
    assert settings.AZURE_AI_SEARCH_INDEX == "indice-personalizado"


# ============================================================================
# M-12: los pesos del score compuesto deben sumar 1.0
# ============================================================================

def test_los_pesos_por_defecto_suman_uno():
    settings = _settings()
    assert settings.SCORE_WEIGHT_ML + settings.SCORE_WEIGHT_HEURISTIC == pytest.approx(1.0)


@pytest.mark.parametrize(
    "peso_ml, peso_heuristico",
    [
        (0.60, 0.50),  # suman 1.10: todos los prospectos se desplazan hacia arriba
        (0.30, 0.30),  # suman 0.60: nadie alcanza nunca el umbral HOT
        (1.00, 1.00),
        (0.00, 0.00),
    ],
)
def test_unos_pesos_que_no_suman_uno_abortan_el_arranque(peso_ml, peso_heuristico):
    """
    La fórmula `peso_ml * ml + peso_heur * heur` solo produce una escala 0-100 si los
    pesos suman uno. Con cualquier otra combinación los umbrales HOT/WARM dejan de
    significar lo que dice la documentación, y no falla nada visible: los scores
    simplemente salen mal. Por eso el arranque se detiene en todos los entornos.
    """
    with pytest.raises(ValueError) as error:
        _settings(SCORE_WEIGHT_ML=peso_ml, SCORE_WEIGHT_HEURISTIC=peso_heuristico)

    mensaje = str(error.value)
    assert "SCORE_WEIGHT_ML" in mensaje
    assert "1.0" in mensaje


def test_una_recalibracion_valida_se_acepta():
    """Redistribuir el peso entre las dos componentes es legítimo mientras sume uno."""
    settings = _settings(SCORE_WEIGHT_ML=0.75, SCORE_WEIGHT_HEURISTIC=0.25)
    assert settings.SCORE_WEIGHT_ML == 0.75


def test_la_tolerancia_admite_el_ruido_de_coma_flotante():
    """0.1 + 0.2 + 0.7 no da exactamente 1.0 en binario, y aun así es una calibración válida."""
    settings = _settings(SCORE_WEIGHT_ML=0.1 + 0.2, SCORE_WEIGHT_HEURISTIC=0.7)
    assert settings.SCORE_WEIGHT_HEURISTIC == 0.7
