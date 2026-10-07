"""
Lo que puntúa cuando el modelo no está, que es lo que puntúa un clon limpio.

El artefacto `.joblib` no viaja en el repositorio —`pickle` ejecuta código al cargar— y
fuera del CI nada lo repone. El adaptador no encuentra el fichero, apunta una línea de
nivel `info` y cae al cálculo de contingencia que vive en este mismo módulo: la pila
arranca verde, el panel funciona y lo que se está midiendo es la línea base contra la que
el modelo se compara. Es la segunda mitad de A-5.

Cuatro archivos de la suite construyen el adaptador sin artefacto y ejercitan ese cálculo
de paso, pero ninguno comprobaba nada de él: la única aserción era `0.0 < prob < 1.0`, que
sobrevive a cambiar cualquiera de los tramos. De los cinco que deciden el resultado, dos no
se recorrían nunca —el del cargo intermedio y el del webinar—. Aquí se comprueba cada uno
por su valor, porque un tramo equivocado no se ve en ninguna pantalla: produce un score
plausible y distinto.

Y el tercer caso de lo mismo: el motor remoto de Azure. El README lo da por depurado de la
arquitectura —«se depuraron tecnologías redundantes […] llamadas remotas a endpoints de
Azure ML»— y sigue exportado y seleccionable con `AI_MODE=azure`. Cuando el endpoint no
contesta no cae a ningún heurístico: puntúa 0.50 a todo el mundo y la auditoría sigue
anotando que puntuó el motor remoto.
"""
import logging

import pytest
from app.adapters import azure_ml_adapter as modulo_ml
from app.adapters.azure_ml_adapter import AzureMLScoringAdapter, NativeMLScoringAdapter
from app.core.config import settings

# La tabla de tramos del cálculo, escrita aquí a mano a propósito: importarla del módulo
# convertiría cada comprobación en una tautología. Si una de estas cifras cambia en el
# código, lo que tiene que pasar es que esto se ponga rojo y alguien decida.
BASE = 0.20
CARGO_DE_DIRECCION = 0.35
CARGO_INTERMEDIO = 0.20
DEMO_PEDIDA = 0.30
WEBINAR_ASISTIDO = 0.15
TOPE_DE_ACTIVIDAD = 0.15


@pytest.fixture
def sin_modelo(tmp_path):
    """Un adaptador en el estado en el que arranca un clon limpio: sin artefacto."""
    adaptador = NativeMLScoringAdapter(model_path=str(tmp_path / "no-esta.joblib"))
    assert adaptador.model is None, "la fixture tiene que entregar el motor degradado"
    return adaptador


async def _puntuar(adaptador, **features) -> float:
    return await adaptador.predict_conversion_probability(features)


# ==============================================================================
# El estado degradado, y qué se puede preguntar para saberlo
# ==============================================================================

def test_sin_artefacto_el_motor_se_declara_heuristico_y_la_salud_sigue_diciendo_que_si(sin_modelo):
    """
    Las dos mitades de A-5 en una sola comprobación.

    `version_del_motor()` es lo único que distingue un sistema que puntúa con el modelo de
    uno que puntúa con el cálculo de contingencia, y es lo que queda escrito en cada
    asiento de la auditoría: `v1.0.0-hybrid+heuristico` frente a
    `v1.0.0-hybrid+ml:<huella>`. `is_healthy()` devuelve True en los dos casos —a
    propósito: negarse a servir dejaría el sistema caído por no tener un fichero
    opcional—, así que una comprobación de salud no sirve para responder a la pregunta
    «¿está puntuando el modelo?».
    """
    assert sin_modelo.version_del_motor() == "heuristico"
    assert sin_modelo.is_healthy() is True
    assert sin_modelo.model_sha256 is None


def test_un_artefacto_que_existe_y_no_se_puede_leer_cae_al_calculo_sin_reventar(tmp_path, caplog):
    """
    El hueco entre «no hay fichero» y «el fichero está bien»: hay fichero y no se deja leer.

    Pasa con un montaje sin permisos, con un volumen que llegó a medias o con un artefacto
    que otro proceso está escribiendo. El arranque no debe caerse por eso, pero tampoco
    puede quedarse callado: sin la línea de error, el único síntoma es que los scores son
    los del cálculo de contingencia.

    Se provoca apuntando la ruta a un directorio, que es lo más parecido a un fichero
    ilegible que se puede montar igual en Windows y en Linux: `os.path.exists` dice que
    está y `open(..., "rb")` levanta `OSError` —`PermissionError` en Windows,
    `IsADirectoryError` en Linux, las dos de la misma familia—.
    """
    caplog.set_level(logging.DEBUG)

    adaptador = NativeMLScoringAdapter(model_path=str(tmp_path))

    assert adaptador.model is None
    assert adaptador.model_sha256 is None
    assert adaptador.version_del_motor() == "heuristico"
    errores = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errores, "un artefacto ilegible tiene que dejar constancia de nivel error"
    assert str(tmp_path) in errores[0].getMessage()


# ==============================================================================
# El cálculo de contingencia, tramo por tramo
# ==============================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cargo", ["CTO", "CIO", "Chief Revenue Officer", "VP de Ventas", "Director General"]
)
async def test_un_cargo_de_direccion_suma_su_tramo(sin_modelo, cargo):
    """Las cinco palabras de la lista de dirección, cada una por separado."""
    assert await _puntuar(sin_modelo, job_title=cargo) == pytest.approx(BASE + CARGO_DE_DIRECCION)


@pytest.mark.asyncio
@pytest.mark.parametrize("cargo", ["Gerente de Compras", "Sales Manager", "Team Lead"])
async def test_un_cargo_intermedio_suma_menos_que_uno_de_direccion(sin_modelo, cargo):
    """
    El tramo que no se recorría nunca.

    Con la aserción «entre cero y uno» que había, este tramo podía valer lo mismo que el de
    dirección y nadie lo habría visto: los dos dan un número entre cero y uno.
    """
    puntuado = await _puntuar(sin_modelo, job_title=cargo)

    assert puntuado == pytest.approx(BASE + CARGO_INTERMEDIO)
    assert puntuado < BASE + CARGO_DE_DIRECCION


@pytest.mark.asyncio
@pytest.mark.parametrize("cargo", ["Trainee", "Becario", "Analista", ""])
async def test_un_cargo_que_no_esta_en_ninguna_de_las_dos_listas_no_suma_nada(sin_modelo, cargo):
    """Un cargo desconocido se queda en la base, y un cargo vacío también."""
    assert await _puntuar(sin_modelo, job_title=cargo) == pytest.approx(BASE)


@pytest.mark.asyncio
async def test_un_cargo_que_cae_en_las_dos_listas_cobra_solo_el_tramo_alto(sin_modelo):
    """
    Un `elif` y no un segundo `if`, que es lo que separa 0.55 de 0.75.

    «Director y Gerente de Operaciones» está en las dos listas. Con dos condiciones
    independientes sumaría los dos tramos, y un solo cargo valdría más que el mejor
    prospecto posible del resto de la tabla sin que ninguna pantalla lo delatara.
    """
    puntuado = await _puntuar(sin_modelo, job_title="Director y Gerente de Operaciones")

    assert puntuado == pytest.approx(BASE + CARGO_DE_DIRECCION)
    assert puntuado != pytest.approx(BASE + CARGO_DE_DIRECCION + CARGO_INTERMEDIO)


@pytest.mark.asyncio
async def test_el_cargo_se_compara_sin_distinguir_mayusculas(sin_modelo):
    """La lista está en mayúsculas y los cargos llegan como los escribió una persona."""
    assert await _puntuar(sin_modelo, job_title="cto de la nube") == pytest.approx(
        BASE + CARGO_DE_DIRECCION
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "senales, esperado",
    [
        ({"requested_demo": 1}, BASE + DEMO_PEDIDA),
        ({"attended_webinar": 1}, BASE + WEBINAR_ASISTIDO),
        ({"requested_demo": 1, "attended_webinar": 1}, BASE + DEMO_PEDIDA + WEBINAR_ASISTIDO),
    ],
)
async def test_la_demo_pedida_y_el_webinar_suman_cada_uno_lo_suyo(sin_modelo, senales, esperado):
    """
    Los dos se suman, y no valen lo mismo: pedir una demostración pesa el doble que ver un
    webinar.

    El tramo del webinar es el otro que no se recorría. Que una señal que el embudo
    considera fuerte pese cero no se nota en el panel: el score sigue saliendo.
    """
    assert await _puntuar(sin_modelo, **senales) == pytest.approx(esperado)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "visitas, clics, sumado",
    [
        (2, 0, 0.04),
        (0, 2, 0.06),
        (1, 1, 0.05),
        (100, 100, TOPE_DE_ACTIVIDAD),
    ],
)
async def test_las_visitas_y_los_clics_suman_con_tope(sin_modelo, visitas, clics, sumado):
    """
    El tope es lo que impide que la navegación sola decida el score.

    Sin él, cien visitas valen 2.00 y cualquier robot de rastreo se convierte en el mejor
    prospecto de la cartera.
    """
    puntuado = await _puntuar(sin_modelo, page_views=visitas, email_clicks=clics)

    assert puntuado == pytest.approx(BASE + sumado)


@pytest.mark.asyncio
async def test_el_resultado_nunca_pasa_de_0_99(sin_modelo):
    """
    Sumando todo se pasa de uno, y lo que sale de aquí es una probabilidad.

    0.20 + 0.35 + 0.30 + 0.15 + 0.15 son 1.15. Un valor por encima de uno viajaría al score
    híbrido, de ahí a la categoría y al panel, donde se lee como un porcentaje.
    """
    puntuado = await _puntuar(
        sin_modelo,
        job_title="CTO",
        requested_demo=1,
        attended_webinar=1,
        page_views=50,
        email_clicks=50,
    )

    assert puntuado == pytest.approx(0.99)


# ==============================================================================
# El motor remoto, que el README da por depurado y sigue seleccionable
# ==============================================================================

class _RespuestaFalsa:
    """Lo que devuelve el cliente falso, con la forma de una respuesta de httpx."""

    def __init__(self, cuerpo):
        self._cuerpo = cuerpo

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._cuerpo


class _ClienteFalso:
    """Sustituye a `httpx.AsyncClient` para devolver lo que decida cada prueba."""

    respuesta = None
    ultima_llamada = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None, headers=None):
        type(self).ultima_llamada = {"url": url, "json": json, "headers": headers}
        return self.respuesta


@pytest.fixture
def motor_remoto(monkeypatch):
    """El adaptador de Azure con su configuración puesta y sin red."""
    monkeypatch.setattr(settings, "AZURE_ML_ENDPOINT", "https://ml.ejemplo.invalid/score")
    monkeypatch.setattr(settings, "AZURE_ML_API_KEY", "clave-de-prueba")
    monkeypatch.setattr(modulo_ml.httpx, "AsyncClient", _ClienteFalso)
    _ClienteFalso.respuesta = None
    _ClienteFalso.ultima_llamada = None
    return AzureMLScoringAdapter()


@pytest.mark.parametrize(
    "endpoint, clave, puede",
    [
        ("https://ml.ejemplo.invalid/score", "clave", True),
        ("https://ml.ejemplo.invalid/score", "", False),
        ("", "clave", False),
        ("", "", False),
    ],
)
def test_el_motor_remoto_necesita_las_dos_cosas_para_declararse_sano(
    monkeypatch, endpoint, clave, puede
):
    """
    Endpoint **y** clave. Con una sola de las dos, las peticiones salen y vuelven 401.

    Es la única comprobación de salud del repositorio que puede decir «no»: la del motor
    nativo devuelve True siempre.
    """
    monkeypatch.setattr(settings, "AZURE_ML_ENDPOINT", endpoint)
    monkeypatch.setattr(settings, "AZURE_ML_API_KEY", clave)

    assert AzureMLScoringAdapter().is_healthy() is puede


def test_la_version_del_motor_remoto_es_la_que_queda_escrita_en_la_auditoria(motor_remoto):
    """
    No es una cadena decorativa: viaja a cada asiento como parte de la versión del scoring,
    y es lo que permite saber meses después con qué motor se calculó un score.
    """
    assert motor_remoto.version_del_motor() == "azure-endpoint"


@pytest.mark.asyncio
async def test_el_motor_remoto_manda_el_vector_en_el_cuerpo_y_la_clave_en_la_cabecera(motor_remoto):
    """Se comprueba lo que sale por el cable, no lo que devuelve la función."""
    _ClienteFalso.respuesta = _RespuestaFalsa({"predictions": [0.73, 0.27]})

    puntuado = await motor_remoto.predict_conversion_probability({"job_title": "CTO"})

    assert puntuado == pytest.approx(0.73)
    llamada = _ClienteFalso.ultima_llamada
    assert llamada["url"] == "https://ml.ejemplo.invalid/score"
    assert llamada["json"] == {"data": [{"job_title": "CTO"}]}
    assert llamada["headers"]["Authorization"] == "Bearer clave-de-prueba"
    assert llamada["headers"]["Content-Type"] == "application/json"


@pytest.mark.asyncio
async def test_una_respuesta_sin_predicciones_puntua_a_la_mitad(motor_remoto):
    """El valor por omisión del propio `get`: una respuesta con otra forma no revienta."""
    _ClienteFalso.respuesta = _RespuestaFalsa({"otra_cosa": 1})

    assert await motor_remoto.predict_conversion_probability({}) == pytest.approx(0.50)


@pytest.mark.asyncio
async def test_si_el_motor_remoto_no_contesta_todo_el_mundo_puntua_lo_mismo(monkeypatch, caplog):
    """
    El fallo del motor remoto no cae a ningún heurístico: devuelve 0.50 y punto.

    Dos prospectos opuestos reciben el mismo número, la categoría sale de ahí y la
    auditoría sigue anotando `azure-endpoint`, así que el historial dice que puntuó el
    modelo remoto. Comparado con el motor nativo —que al menos cae a un cálculo que
    distingue cargos— esto es la forma más completa de A-5, y queda anotado en vez de
    corregido: cambiar lo que devuelve es cambiar lo que la API contesta.

    Sin cliente falso aquí a propósito: el puerto 1 de la interfaz local rechaza la
    conexión en el acto, así que el fallo que se ejercita es uno de verdad.
    """
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(settings, "AZURE_ML_ENDPOINT", "http://127.0.0.1:1/score")
    monkeypatch.setattr(settings, "AZURE_ML_API_KEY", "clave-de-prueba")
    adaptador = AzureMLScoringAdapter()

    director = await adaptador.predict_conversion_probability(
        {"job_title": "CTO", "requested_demo": 1, "page_views": 40}
    )
    becario = await adaptador.predict_conversion_probability({"job_title": "Becario"})

    assert director == pytest.approx(0.50)
    assert becario == pytest.approx(0.50)
    assert adaptador.version_del_motor() == "azure-endpoint"
    errores = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errores, "un endpoint que no contesta tiene que dejar constancia"
    assert "127.0.0.1:1" in errores[0].getMessage()
