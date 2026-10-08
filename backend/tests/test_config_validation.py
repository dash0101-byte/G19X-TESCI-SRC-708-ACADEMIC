"""
Coherencia de la configuración al arrancar (M-2 y M-12).

Ambos defectos comparten forma: configuraciones inválidas que el sistema aceptaba sin
protestar y que solo se manifestaban más tarde, lejos de su causa —una como
`AttributeError` en mitad de una petición, la otra como puntuaciones sesgadas que
nunca disparaban ningún error.
"""
import logging

import pytest
from app.adapters.azure_search_adapter import AzureAISearchAdapter
from app.core.config import MIN_SECRET_KEY_LENGTH, Settings
from pydantic import ValidationError

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


# ============================================================================
# Las tres formas de tener una SECRET_KEY que no sirve, y lo que pasa con cada una
# ============================================================================
#
# El validador distingue tres problemas -comprometida, ausente, corta- y luego dos
# tratamientos segun el entorno: en uno endurecido no arranca, y en desarrollo genera una
# clave efimera y lo avisa. De las tres solo la comprometida estaba probada, y las dos que
# faltaban son las que se dan de verdad: un `.env` sin la variable, y una clave que alguien
# escribio a mano «para probar».
#
# Importa el MOTIVO y no solo que falle: el mensaje es lo unico que tiene quien arranca la
# pila y no entiende por que no arranca, y los tres motivos piden remedios distintos.

@pytest.mark.parametrize(
    "clave,motivo",
    [
        ("", "no está definida"),
        ("corta", f"tiene menos de {MIN_SECRET_KEY_LENGTH} caracteres"),
    ],
    ids=["ausente", "demasiado_corta"],
)
def test_una_clave_que_no_sirve_impide_arrancar_un_entorno_endurecido_diciendo_por_que(
    clave, motivo
):
    """
    En produccion no se arranca con una clave invalida, y el error dice cual de los tres es.

    Sin el motivo, el mensaje seria «SECRET_KEY invalida» y quien despliega no sabria si
    tiene que definirla, alargarla o cambiarla por no estar publicada. Los tres remedios son
    distintos y el mensaje lleva ademas la orden para generarla.
    """
    with pytest.raises(ValidationError) as fallo:
        Settings(SECRET_KEY=clave, ENVIRONMENT="production")

    texto = str(fallo.value)
    assert motivo in texto
    assert "secrets.token_urlsafe(64)" in texto, "el mensaje trae el remedio, no solo la queja"


@pytest.mark.parametrize(
    "clave,motivo",
    [
        ("", "no está definida"),
        ("corta", f"tiene menos de {MIN_SECRET_KEY_LENGTH} caracteres"),
    ],
    ids=["ausente", "demasiado_corta"],
)
def test_en_desarrollo_la_clave_que_no_sirve_se_sustituye_por_una_efimera_y_se_avisa(
    clave, motivo, caplog
):
    """
    En desarrollo arranca, con una clave aleatoria de verdad y un aviso que dice que lo es.

    Es el camino que recorre cualquiera que clone el repositorio y levante la pila sin
    configurar nada, asi que tiene que funcionar; y la clave generada tiene que ser
    utilizable -lo bastante larga- o el sistema arrancaria para fallar al firmar el primer
    testigo. El aviso dice ademas que esto NO vale en produccion, que es la unica cosa que
    impide que alguien lo deje asi.

    Lo que se comprueba es que la clave CAMBIO: que el valor efectivo no sea el que se paso.
    Comprobar solo que arranca no distingue «se genero una clave» de «se acepto la mala».
    """
    with caplog.at_level(logging.WARNING):
        ajustes = Settings(SECRET_KEY=clave, ENVIRONMENT="development")

    assert ajustes.SECRET_KEY != clave
    assert len(ajustes.SECRET_KEY) >= MIN_SECRET_KEY_LENGTH
    renglones = " | ".join(r.getMessage() for r in caplog.records)
    assert motivo in renglones
    assert "NO es válido en producción" in renglones


def test_una_clave_buena_no_se_toca_ni_deja_aviso(caplog):
    """La cuarta salida del validador, que es la normal: se devuelve tal cual y en silencio."""
    with caplog.at_level(logging.WARNING):
        ajustes = Settings(SECRET_KEY=CLAVE_VALIDA, ENVIRONMENT="development")

    assert ajustes.SECRET_KEY == CLAVE_VALIDA
    assert not [r for r in caplog.records if "SECRET_KEY" in r.getMessage()]


# ============================================================================
# «Ninguno» escrito de las tres formas en que se escribe
# ============================================================================

def test_unos_origenes_de_cors_sin_definir_son_ninguno_y_no_un_error():
    """
    `CORS_ORIGINS` ausente -que es `None`- significa ninguno, igual que la cadena vacia.

    De las tres formas de decir «ninguno» -no poner la variable, ponerla vacia, o poner `[]`-
    la primera no se probaba. Y es la que hace cualquiera: no escribir la linea. Sin el
    `if valor is None`, pydantic revienta antes de llegar a ningun validador con un
    `SettingsError` que no menciona ni la causa ni el remedio, y el arranque muere por una
    variable que nadie escribio.
    """
    assert Settings(SECRET_KEY=CLAVE_VALIDA, CORS_ORIGINS=None).CORS_ORIGINS == []
    # Y las otras dos, al lado, para que las tres se lean juntas.
    assert Settings(SECRET_KEY=CLAVE_VALIDA, CORS_ORIGINS="").CORS_ORIGINS == []
    assert Settings(SECRET_KEY=CLAVE_VALIDA, CORS_ORIGINS="   ").CORS_ORIGINS == []


def test_un_entorno_endurecido_deja_escritos_los_origenes_que_autorizo(caplog):
    """
    El renglon del arranque que evita que un diagnostico de CORS acabe en «pongamos asterisco».

    En un entorno endurecido se apunta la lista exacta de origenes autorizados. Es un
    renglon y no una pantalla porque CORS falla de la forma mas confusa que existe: el
    frontend se despliega en otro dominio, el navegador empieza a bloquear peticiones, y en
    el servidor no hay ningun error. Tener la lista escrita en el arranque es la diferencia
    entre leerla y adivinarla.
    """
    with caplog.at_level(logging.INFO):
        ajustes = Settings(
            SECRET_KEY=CLAVE_VALIDA,
            ENVIRONMENT="production",
            CORS_ORIGINS="https://panel.plurione.com,https://www.plurione.com",
        )

    assert ajustes.CORS_ORIGINS == ["https://panel.plurione.com", "https://www.plurione.com"]
    renglones = " | ".join(r.getMessage() for r in caplog.records)
    assert "orígenes autorizados" in renglones
    assert "https://panel.plurione.com, https://www.plurione.com" in renglones
