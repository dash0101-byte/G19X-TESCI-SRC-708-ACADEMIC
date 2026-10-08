"""
Los brazos del motor nativo de explicación, y el arranque que nadie mira.

Dos piezas que comparten una propiedad incómoda: **se leen, no se consultan**. El motor
nativo XAI escribe el párrafo que un asesor lee en la ficha —fortalezas, diagnóstico y
recomendación— y el arranque de `main.py` escribe los renglones que alguien lee cuando algo
ya va mal. Ninguna de las dos devuelve un número que otra prueba compare, así que un brazo
equivocado no rompe nada: produce un texto que dice lo que no es.

Qué se cubre aquí
-----------------
1. **Los brazos del motor nativo.** Es determinista y es una cadena de `if/elif`, de modo que
   cada brazo escribe una frase distinta sobre la misma ficha. Lo que estaba probado era el
   camino de un prospecto corriente; lo que no, los tres que el capítulo 24 escribió a
   propósito: el rol atípico —un estudiante que rellena el formulario—, el interlocutor de
   recursos humanos y el sector académico. Esos tres existen para que el equipo comercial no
   persiga a quien no compra, y si su brazo no se recorre nadie sabe si dicen lo que creen
   decir.
2. **La fábrica de adaptadores**, que con `AI_MODE=azure` y credenciales entrega el remoto.
3. **Los renglones del arranque**: los recálculos huérfanos cerrados, el motor de inferencia
   que no se pudo inicializar, y los tres estados en los que puede quedar `/metrics`.

Lo que NO se prueba, y por qué
------------------------------
El texto exacto de cada frase. Lo que se comprueba de cada brazo es que **se eligió el
brazo**, por un fragmento que solo ese brazo escribe. Comparar el párrafo entero con una
copia escrita a mano aquí convertiría cualquier mejora de redacción en una prueba roja, y no
comprobaría nada que no comprueben estas líneas.
"""
import logging

import pytest
from app.adapters.azure_openai_adapter import (
    AzureOpenAIAdapter,
    NativeXAIExplanationAdapter,
    get_ai_explanation_adapter,
    reset_explanation_adapter_cache,
)
from app.core.config import settings


@pytest.fixture(autouse=True)
def sin_cache_de_adaptadores():
    """La fábrica está memoizada: sin vaciarla, la primera prueba decide para todas."""
    reset_explanation_adapter_cache()
    yield
    reset_explanation_adapter_cache()


def _ficha(**cambios):
    base = {
        "first_name": "Ana",
        "company": "Ejemplo SA",
        "job_title": "Directora de Tecnología",
        "industry": "FinTech",
        "days_since_last_activity": 0,
        "custom_metadata": {},
    }
    base.update(cambios)
    return base


def _desglose(**cambios):
    base = {"title_fit_score": 20, "industry_fit_score": 14, "behavior_raw_total": 25}
    base.update(cambios)
    return base


async def _explicar(ficha, score=80.0, categoria="HOT", desglose=None):
    return await NativeXAIExplanationAdapter().generate_explanation(
        ficha, score, categoria, desglose or _desglose()
    )


# ==============================================================================
# Los tres brazos que el capítulo 24 escribió para no perseguir a quien no compra
# ==============================================================================

@pytest.mark.asyncio
async def test_un_rol_atipico_se_diagnostica_como_tal_y_no_como_prospecto_caliente():
    """
    Un estudiante con score alto no es un comprador: el diagnóstico lo dice y lo deriva.

    Es el brazo que gana sobre la categoría —se evalúa ANTES que `HOT`— y por eso importa
    que se recorra: una ficha de un practicante con mucha interacción digital sale con score
    de prospecto caliente, y sin este brazo el párrafo le diría al asesor que lo llame hoy.
    La recomendación no lo descarta, pide verificar si actúa por el área de selección, que es
    lo que de verdad pasa cuando una universidad pregunta por convenios.
    """
    resultado = await _explicar(_ficha(job_title="Estudiante de Ingeniería"))

    assert "No corresponde al perfil típico" in resultado["summary"]
    assert "recursos humanos o selección" in resultado["recommended_action"]
    # Y entre las fortalezas, la que nombra el desajuste en lugar de callarlo.
    assert any("fuera del núcleo de toma de decisiones" in f for f in resultado["strengths"])


@pytest.mark.asyncio
async def test_un_interlocutor_de_talento_se_reconoce_como_clave_y_no_como_atipico():
    """
    El brazo de al lado, y la razón de que sean dos y no uno.

    Quien lleva atracción de talento **sí** es el interlocutor de una empresa de staffing
    TI: es exactamente quien contrata perfiles. Si cayera en el brazo del rol atípico —son
    `elif`, así que el orden decide— el sistema derivaría al equipo comercial lejos de su
    mejor contacto.
    """
    resultado = await _explicar(_ficha(job_title="Head of Talent Acquisition"))

    assert any("atracción de talento" in f for f in resultado["strengths"])
    assert "No corresponde al perfil típico" not in resultado["summary"]


@pytest.mark.asyncio
async def test_el_sector_academico_se_nombra_por_su_potencial_y_no_por_su_score():
    """
    Una universidad no es industria prioritaria, y tampoco es nada: son convenios.

    El brazo cuelga de un `elif` sobre el ajuste de industria, así que solo se recorre cuando
    el sector NO puntúa alto. Sin él, una universidad se queda sin ninguna fortaleza de
    sector y el párrafo no menciona la única vía por la que esa ficha vale algo.
    """
    resultado = await _explicar(
        _ficha(industry="Educación Superior"), desglose=_desglose(industry_fit_score=4)
    )

    assert any("semilleros de talento" in f for f in resultado["strengths"])


# ==============================================================================
# Lo que el formulario trae y el párrafo tiene que recoger
# ==============================================================================

@pytest.mark.asyncio
async def test_el_presupuesto_informado_entra_en_las_fortalezas():
    """
    Lo dijo en el formulario; que no aparezca en el párrafo es perderlo.

    `budget_range` es el único de los tres campos del formulario cuyo brazo no se ejercitaba.
    Un rango presupuestal informado es el dato que decide si una conversación avanza, y si no
    sale en las fortalezas el asesor lo descubre preguntándolo otra vez.
    """
    resultado = await _explicar(
        _ficha(custom_metadata={"budget_range": "USD 50k-100k"})
    )

    assert any("Rango presupuestal informado: USD 50k-100k" in f for f in resultado["strengths"])


@pytest.mark.asyncio
async def test_un_prospecto_templado_con_perfiles_pedidos_recibe_otra_recomendacion():
    """
    Los dos caminos de la recomendación templada, que no son matices: son acciones distintas.

    Con perfiles pedidos, la recomendación es mandar casos de éxito de ESOS perfiles y
    proponer una sesión de sondeo. Sin ellos, entrar en el flujo de nutrición y el webinar.
    Lo primero es trabajo de una persona; lo segundo, una lista de correo. Elegir el brazo
    equivocado no falla: manda un correo genérico a quien había dicho qué necesitaba.
    """
    con_perfiles = await _explicar(
        _ficha(custom_metadata={"profiles_needed": "3 desarrolladores Java"}),
        score=55.0, categoria="WARM",
    )
    sin_perfiles = await _explicar(_ficha(), score=55.0, categoria="WARM")

    assert "3 desarrolladores Java" in con_perfiles["recommended_action"]
    assert "sondeo de requerimientos" in con_perfiles["recommended_action"]
    assert "flujo de nutrición" in sin_perfiles["recommended_action"]
    assert "3 desarrolladores" not in sin_perfiles["recommended_action"]


@pytest.mark.asyncio
async def test_la_inactividad_se_avisa_en_la_recomendacion_y_dice_cuantos_dias():
    """
    El score ya se atenuó por inactividad; el párrafo tiene que decir que se atenuó.

    Sin el aviso, un asesor ve un score bajo y no sabe si es que la ficha no vale o es que
    llevan un mes sin tocarla —que son dos acciones opuestas—. Se comprueba también el borde:
    a diez días justos todavía no se avisa, porque la condición es estricta.
    """
    avisado = await _explicar(_ficha(days_since_last_activity=45))
    justo_en_el_borde = await _explicar(_ficha(days_since_last_activity=10))

    assert "45 días de inactividad" in avisado["recommended_action"]
    assert "factor de atenuación temporal" in avisado["recommended_action"]
    assert "inactividad" not in justo_en_el_borde["recommended_action"]


@pytest.mark.asyncio
async def test_una_ficha_sin_nada_que_destacar_no_se_queda_sin_fortalezas():
    """
    La salida de último recurso de la lista: «interés inicial capturado».

    Una lista de fortalezas vacía en la ficha se lee como un error de la pantalla, no como
    «no hay nada que destacar». Y es alcanzable de verdad: una ficha que llega por el
    formulario con lo mínimo y sin interacción todavía.
    """
    resultado = await _explicar(
        _ficha(job_title="Analista", industry="Otros"),
        score=20.0, categoria="COLD",
        desglose=_desglose(title_fit_score=2, industry_fit_score=0, behavior_raw_total=0),
    )

    assert resultado["strengths"] == ["Interés inicial capturado a través de canales de prospección."]


# ==============================================================================
# La fábrica
# ==============================================================================

def test_sin_credenciales_la_fabrica_entrega_el_motor_nativo(monkeypatch):
    """Por defecto, y en un clon: el nativo. Es la mitad que ya se usaba."""
    monkeypatch.setattr(settings, "AI_MODE", "native")
    assert isinstance(get_ai_explanation_adapter(), NativeXAIExplanationAdapter)


def test_con_azure_y_credenciales_la_fabrica_entrega_el_remoto(monkeypatch):
    """
    El camino que elige el adaptador remoto, que no lo recorría nadie.

    Hacen falta las tres cosas —modo `azure`, extremo y clave— y por eso la fábrica recibe
    las tres como argumentos: son la clave de la caché, de modo que cambiar `AI_MODE` o las
    credenciales produce una entrada nueva en lugar de devolver el adaptador anterior. Sin
    probar esto, nadie sabe si un despliegue con credenciales acaba usando el remoto o
    siguió con el nativo en silencio, que es la clase de cosa que no se nota.
    """
    monkeypatch.setattr(settings, "AI_MODE", "AZURE")
    monkeypatch.setattr(settings, "AZURE_OPENAI_ENDPOINT", "https://ejemplo.openai.azure.com")
    monkeypatch.setattr(settings, "AZURE_OPENAI_API_KEY", "clave-de-prueba")

    assert isinstance(get_ai_explanation_adapter(), AzureOpenAIAdapter)


@pytest.mark.parametrize(
    "modo,extremo,clave",
    [
        ("azure", "", True),
        ("azure", "https://ejemplo.openai.azure.com", False),
        ("native", "https://ejemplo.openai.azure.com", True),
    ],
    ids=["sin_extremo", "sin_clave", "modo_nativo"],
)
def test_le_falta_una_de_las_tres_y_se_queda_en_el_nativo(monkeypatch, modo, extremo, clave):
    """
    Las tres formas de no llegar al remoto, que son lo que impide un arranque a medias.

    Un extremo configurado sin clave —o al revés— es el estado normal de un despliegue a
    medio configurar. Caer al nativo ahí es lo correcto: el nativo contesta, y contestar con
    el motor local es mejor que contestar con un error o con un adaptador que no puede
    hablar con nadie.
    """
    monkeypatch.setattr(settings, "AI_MODE", modo)
    monkeypatch.setattr(settings, "AZURE_OPENAI_ENDPOINT", extremo)
    monkeypatch.setattr(settings, "AZURE_OPENAI_API_KEY", "clave" if clave else "")

    assert isinstance(get_ai_explanation_adapter(), NativeXAIExplanationAdapter)


# ==============================================================================
# El arranque: los renglones que alguien lee cuando algo ya va mal
# ==============================================================================

def test_el_arranque_dice_que_recalculos_huerfanos_cerro(monkeypatch, caplog):
    """
    Si el barrido cerró algo, el arranque lo nombra. Si no, no dice nada.

    El renglón existe porque un recálculo huérfano es la única cosa que impide empezar otro:
    quien reinicia el servicio porque «el recálculo se quedó colgado» necesita ver en el
    arranque que efectivamente había uno y que se cerró. Sin el `if`, cada arranque normal
    escribiría una advertencia con una lista vacía, y una advertencia que sale siempre deja
    de leerse.

    Se entra al ciclo de vida de verdad —`with TestClient(app)`, que es el idioma que el
    `conftest` ya usa— porque este trozo vive dentro de `lifespan` y no en una función
    propia, y extraerla sería tocar `backend/app` por una razón de prueba.
    """
    from app.main import app
    from fastapi.testclient import TestClient

    monkeypatch.setattr(
        "app.main.recuperar_trabajos_huerfanos", lambda: ["trabajo-a", "trabajo-b"]
    )
    with caplog.at_level(logging.WARNING, logger="app.main"):
        with TestClient(app):
            pass

    avisos = [r.getMessage() for r in caplog.records if "huérfanos" in r.getMessage()]
    assert avisos and "trabajo-a, trabajo-b" in avisos[0]


def test_un_arranque_sin_huerfanos_no_escribe_ninguna_advertencia(monkeypatch, caplog):
    """La otra mitad: lo normal es que no haya ninguno, y entonces no se dice nada."""
    from app.main import app
    from fastapi.testclient import TestClient

    monkeypatch.setattr("app.main.recuperar_trabajos_huerfanos", lambda: [])
    with caplog.at_level(logging.WARNING, logger="app.main"):
        with TestClient(app):
            pass

    assert not [r for r in caplog.records if "huérfanos" in r.getMessage()]


def test_si_el_motor_de_inferencia_no_arranca_se_avisa_y_la_aplicacion_levanta(
    monkeypatch, caplog
):
    """
    El arranque comprueba el motor ML para que el problema se vea temprano, no al puntuar.

    Y lo que importa es que **no impide levantar**: el sistema sabe operar sin modelo —cae
    al heurístico, que es la línea base contra la que el modelo se compara— así que
    propagar este error cambiaría «todo verde puntuando con el heurístico» por «la pila no
    arranca». En un clon limpio, que es donde el artefacto no está, eso dejaría el sistema
    sin enseñar.

    El aviso dice además qué hacer, y eso se comprueba: un renglón de advertencia que no
    nombra `train_model.py` deja a quien clona el repositorio sin el siguiente paso.
    """
    from app.main import app
    from fastapi.testclient import TestClient

    def no_arranca():
        raise RuntimeError("el artefacto .joblib no está donde se esperaba")

    monkeypatch.setattr(
        "app.adapters.azure_ml_adapter.get_ml_scoring_adapter", no_arranca
    )

    with caplog.at_level(logging.WARNING, logger="app.main"):
        with TestClient(app) as cliente:
            # Levanta igual: la comprobación que de verdad importa.
            assert cliente.get("/health").status_code == 200

    criticos = [r.getMessage() for r in caplog.records if "ADVERTENCIA CRÍTICA" in r.getMessage()]
    assert criticos, [r.getMessage() for r in caplog.records]
    assert "no está donde se esperaba" in criticos[0]
    assert "train_model.py" in criticos[0]


@pytest.mark.parametrize(
    "activa,testigo,entorno,fragmento",
    [
        (False, "", "development", "desactivada"),
        (True, "un-testigo", "development", "protegida con METRICS_TOKEN"),
        (True, "", "production", "NO se publica"),
        (True, "", "development", "SIN testigo"),
    ],
    ids=["desactivada", "con_testigo", "endurecida_sin_testigo", "desarrollo_sin_testigo"],
)
def test_el_arranque_dice_en_que_estado_quedo_metrics(
    monkeypatch, caplog, activa, testigo, entorno, fragmento
):
    """
    Los cuatro estados de `/metrics`, cada uno con su renglón, y ninguno probado.

    `/metrics` no está protegida por sesión: la lee el recolector. Las combinaciones de
    ajustes la dejan publicada, publicada y protegida, o no publicada, y la diferencia entre
    la primera y la segunda es si cualquiera puede leer las métricas del sistema. El renglón
    del arranque es lo único que lo dice, porque desde fuera «no responde» y «responde sin
    pedir testigo» se parecen demasiado a un error de red.
    """
    from app.main import _avisar_de_la_ruta_de_metricas

    monkeypatch.setattr(settings, "METRICS_ENABLED", activa)
    monkeypatch.setattr(settings, "METRICS_TOKEN", testigo)
    monkeypatch.setattr(settings, "ENVIRONMENT", entorno)

    with caplog.at_level(logging.INFO, logger="app.main"):
        _avisar_de_la_ruta_de_metricas()

    renglones = " | ".join(r.getMessage() for r in caplog.records)
    assert fragmento in renglones, renglones
