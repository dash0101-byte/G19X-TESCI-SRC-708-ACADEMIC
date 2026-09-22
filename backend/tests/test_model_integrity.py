"""
Integridad del artefacto de ML y caché de las fábricas de adaptadores.

Dos problemas distintos que viven en el mismo módulo:

* **A-10.** `joblib.load` deserializa con pickle, y pickle *ejecuta código* al cargar. La
  ruta del artefacto viene de configuración, así que quien pueda escribir ahí —o cambiar
  `ML_MODEL_PATH`— ejecuta lo que quiera dentro del backend. Fijar `ML_MODEL_SHA256`
  convierte esa sustitución en un fallo ruidoso en vez de en una ejecución silenciosa.

* **Rendimiento.** `ScoringService` se construye en cada petición y con él un adaptador
  nuevo, lo que significaba deserializar el modelo entero por petición.
"""
import asyncio
import hashlib
import time

import pytest
from app.adapters import azure_ml_adapter as modulo_ml
from app.adapters.azure_ml_adapter import (
    AzureMLScoringAdapter,
    NativeMLScoringAdapter,
    get_ml_scoring_adapter,
    reset_ml_adapter_cache,
)
from app.core.config import settings

CONTENIDO_FALSO = b"esto-no-es-un-modelo-serializado"
SHA_DEL_CONTENIDO = hashlib.sha256(CONTENIDO_FALSO).hexdigest()
SHA_QUE_NO_CUADRA = "0" * 64


@pytest.fixture
def artefacto_falso(tmp_path):
    """Un fichero con contenido conocido, para poder razonar sobre su huella."""
    ruta = tmp_path / "lead_scorer_model.joblib"
    ruta.write_bytes(CONTENIDO_FALSO)
    return str(ruta)


@pytest.fixture(autouse=True)
def caches_limpias():
    """
    Vacía la caché de fábricas antes y después de cada test.

    Sin esto, un test que cambia `AI_MODE` dejaría su adaptador en la caché y contaminaría
    a los siguientes; y al revés, un adaptador construido por otro test haría pasar por
    error una comprobación de aquí.
    """
    reset_ml_adapter_cache()
    yield
    reset_ml_adapter_cache()


# ==============================================================================
# A-10: verificación de la huella antes de deserializar
# ==============================================================================

def test_la_huella_se_calcula_al_cargar(artefacto_falso):
    """El adaptador deja constancia de la huella del fichero que ha usado."""
    adaptador = NativeMLScoringAdapter(model_path=artefacto_falso)

    assert adaptador.model_sha256 == SHA_DEL_CONTENIDO


def test_una_huella_que_no_cuadra_impide_la_deserializacion(artefacto_falso, monkeypatch):
    """
    Lo importante no es que el modelo quede a None: es que `joblib.load` NO se llame.

    Si se llamara y solo después se descartara el resultado, el pickle ya habría ejecutado
    su carga útil. Por eso el espía falla la prueba en el momento de ser invocado.
    """
    def no_debe_llamarse(*args, **kwargs):
        pytest.fail("joblib.load fue invocado pese a que la huella no coincidía")

    monkeypatch.setattr(modulo_ml.joblib, "load", no_debe_llamarse)

    adaptador = NativeMLScoringAdapter(
        model_path=artefacto_falso, expected_sha256=SHA_QUE_NO_CUADRA
    )

    assert adaptador.model is None


def test_con_la_huella_correcta_si_se_intenta_cargar(artefacto_falso, monkeypatch):
    """El caso simétrico: cuando la huella cuadra, la carga sigue su curso."""
    llamadas = []
    monkeypatch.setattr(
        modulo_ml.joblib, "load", lambda ruta, *a, **k: llamadas.append(ruta) or "modelo"
    )

    adaptador = NativeMLScoringAdapter(
        model_path=artefacto_falso, expected_sha256=SHA_DEL_CONTENIDO
    )

    assert llamadas == [artefacto_falso]
    assert adaptador.model == "modelo"


def test_la_huella_se_compara_sin_distinguir_mayusculas(artefacto_falso, monkeypatch):
    """Un digest pegado en mayúsculas desde otra herramienta debe seguir valiendo."""
    monkeypatch.setattr(modulo_ml.joblib, "load", lambda *a, **k: "modelo")

    adaptador = NativeMLScoringAdapter(
        model_path=artefacto_falso, expected_sha256=SHA_DEL_CONTENIDO.upper()
    )

    assert adaptador.model == "modelo"


def test_sin_huella_fijada_el_comportamiento_no_cambia(artefacto_falso, monkeypatch):
    """
    No anclar la huella no rompe nada: se carga igual.

    Es deliberado. Negarse a arrancar sin huella dejaría fuera de servicio los despliegues
    ya en marcha, y degradar en silencio al heurístico es exactamente el fallo que costó
    A-5. Lo que sí se hace es registrar la huella encontrada para poder fijarla.
    """
    monkeypatch.setattr(modulo_ml.joblib, "load", lambda *a, **k: "modelo")

    adaptador = NativeMLScoringAdapter(model_path=artefacto_falso, expected_sha256="")

    assert adaptador.model == "modelo"
    assert adaptador.model_sha256 == SHA_DEL_CONTENIDO


def test_un_artefacto_inexistente_no_revienta(tmp_path):
    """Sin fichero se cae al heurístico, sin huella y sin excepción."""
    adaptador = NativeMLScoringAdapter(model_path=str(tmp_path / "no-existe.joblib"))

    assert adaptador.model is None
    assert adaptador.model_sha256 is None


@pytest.mark.asyncio
async def test_el_heuristico_de_respaldo_responde_sin_modelo(tmp_path):
    """Rechazar el artefacto no deja el scoring inservible: hay respaldo analítico."""
    adaptador = NativeMLScoringAdapter(model_path=str(tmp_path / "no-existe.joblib"))

    prob = await adaptador.predict_conversion_probability(
        {"job_title": "CTO", "requested_demo": 1, "page_views": 8}
    )

    assert 0.0 < prob < 1.0


# ==============================================================================
# Caché de las fábricas
# ==============================================================================

def test_la_fabrica_devuelve_siempre_el_mismo_adaptador():
    """
    Sin caché, cada petición de scoring deserializaba el artefacto de nuevo.

    `ScoringService` se instancia por petición y pedía aquí su adaptador; medido en local,
    construirlo cuesta unos 335 ms, que se pagaban íntegros en cada llamada.
    """
    assert get_ml_scoring_adapter() is get_ml_scoring_adapter()


def test_vaciar_la_cache_fuerza_una_construccion_nueva():
    primero = get_ml_scoring_adapter()
    reset_ml_adapter_cache()

    assert get_ml_scoring_adapter() is not primero


def test_la_cache_no_ignora_un_cambio_de_configuracion(monkeypatch):
    """
    La clave de la caché son los ajustes que deciden el adaptador, no nada.

    Cacheando una función sin argumentos, cambiar `AI_MODE` a azure habría seguido
    devolviendo el adaptador nativo construido antes: el sistema ignoraría su propia
    configuración hasta el siguiente reinicio.
    """
    assert isinstance(get_ml_scoring_adapter(), NativeMLScoringAdapter)

    monkeypatch.setattr(settings, "AI_MODE", "azure")
    monkeypatch.setattr(settings, "AZURE_ML_ENDPOINT", "https://ml.ejemplo.invalid/score")

    assert isinstance(get_ml_scoring_adapter(), AzureMLScoringAdapter)


def test_la_cache_distingue_tambien_la_ruta_del_modelo(monkeypatch, artefacto_falso):
    """Apuntar a otro artefacto debe producir otro adaptador, no reutilizar el anterior."""
    primero = get_ml_scoring_adapter()

    monkeypatch.setattr(settings, "ML_MODEL_PATH", artefacto_falso)
    segundo = get_ml_scoring_adapter()

    assert segundo is not primero
    assert segundo.model_path == artefacto_falso


# ==============================================================================
# La inferencia no debe bloquear el bucle de eventos
# ==============================================================================

class _ModeloLento:
    """Modelo de mentira cuya predicción tarda, para poder medir el bloqueo."""

    RETARDO = 0.30

    def predict_proba(self, df):
        time.sleep(self.RETARDO)
        return [[0.3, 0.7]]


@pytest.mark.asyncio
async def test_la_inferencia_no_congela_el_bucle_de_eventos(tmp_path, monkeypatch):
    """
    Mientras se infiere, el resto de peticiones deben seguir avanzando.

    `predict_proba` es CPU pura y síncrona. Llamada directamente desde la corrutina, retiene
    el hilo del bucle y **todas** las peticiones en vuelo se quedan paradas, no solo la que
    está puntuando. Con el modelo real son milisegundos y cuesta verlo; aquí se exagera el
    retardo para que la diferencia sea inequívoca.

    El contador de referencia avanza cada milisegundo: si la inferencia bloqueara, se
    quedaría cerca de cero durante los 300 ms.
    """
    monkeypatch.setattr(modulo_ml.joblib, "load", lambda *a, **k: _ModeloLento())
    artefacto = tmp_path / "modelo.joblib"
    artefacto.write_bytes(b"da-igual-el-contenido-lo-carga-el-doble")
    adaptador = NativeMLScoringAdapter(model_path=str(artefacto))
    assert isinstance(adaptador.model, _ModeloLento)

    latidos = 0

    async def marcapasos():
        nonlocal latidos
        while True:
            await asyncio.sleep(0.001)
            latidos += 1

    tarea = asyncio.create_task(marcapasos())
    try:
        await adaptador.predict_conversion_probability({"job_title": "CTO"})
    finally:
        tarea.cancel()

    # Con el bucle libre caben decenas de latidos en 300 ms; bloqueado no cabría casi ninguno.
    assert latidos > 10, f"el bucle quedó bloqueado durante la inferencia (latidos={latidos})"


@pytest.mark.asyncio
async def test_dos_inferencias_lentas_se_solapan(tmp_path, monkeypatch):
    """
    Dos inferencias concurrentes no deben costar la suma de sus tiempos.

    Es lo que decide si el recálculo masivo y el simulador pueden convivir con el resto del
    tráfico. `time.sleep` libera el GIL, de modo que en el pool de hilos se solapan; en el
    bucle se habrían encolado una detrás de otra.
    """
    monkeypatch.setattr(modulo_ml.joblib, "load", lambda *a, **k: _ModeloLento())
    artefacto = tmp_path / "modelo.joblib"
    artefacto.write_bytes(b"da-igual-el-contenido-lo-carga-el-doble")
    adaptador = NativeMLScoringAdapter(model_path=str(artefacto))

    inicio = time.perf_counter()
    await asyncio.gather(
        adaptador.predict_conversion_probability({"job_title": "CTO"}),
        adaptador.predict_conversion_probability({"job_title": "CIO"}),
    )
    transcurrido = time.perf_counter() - inicio

    assert transcurrido < _ModeloLento.RETARDO * 1.8, (
        f"las dos inferencias se serializaron ({transcurrido:.2f} s)"
    )
