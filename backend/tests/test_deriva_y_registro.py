"""
Monitoreo de deriva y registro de modelos (resto de ML-3).

Un modelo no avisa cuando deja de servir: sigue devolviendo probabilidades con la misma
confianza mientras la población que puntúa cambia por debajo. Y sin registro de modelos,
el artefacto que sirve en producción no tiene procedencia: no hay forma de responder con
qué datos se entrenó lo que puntuó a un prospecto hace tres meses.

Las pruebas verifican que el índice detecta lo que dice detectar. Un monitor que nunca se
dispara y otro que se dispara siempre son igual de inútiles, y ambos se ven en verde si
solo se comprueba que la función devuelve un número.
"""
import json

import numpy as np
import pandas as pd
import pytest
from drift_monitor import (
    MINIMO_OBSERVACIONES,
    UMBRAL_DERIVA,
    construir_perfil,
    dictamen,
    evaluar_deriva,
    psi_de_columna,
    reparto_de_motores,
)
from model_registry import (
    ProcedenciaIncompleta,
    artefacto_registrado,
    entrada_de_artefacto,
    huella_de_datos,
    leer_registro,
    registrar_modelo,
)

COLUMNAS = ["annual_revenue", "page_views", "source_channel"]


@pytest.fixture
def referencia():
    """Población de referencia estable y reproducible."""
    generador = np.random.default_rng(20260909)
    return pd.DataFrame(
        {
            "annual_revenue": generador.lognormal(mean=13.0, sigma=1.0, size=2000),
            "page_views": generador.poisson(lam=8, size=2000),
            "source_channel": generador.choice(
                ["Website", "LinkedIn Ads", "Webinar", "Organic Search"],
                size=2000,
                p=[0.4, 0.3, 0.2, 0.1],
            ),
        }
    )


@pytest.fixture
def perfil(referencia):
    return construir_perfil(referencia, COLUMNAS)


# ============================================================================
# El índice distingue una población estable de una que cambió
# ============================================================================

def test_una_muestra_de_la_misma_poblacion_sale_estable(perfil):
    generador = np.random.default_rng(1234)
    produccion = pd.DataFrame(
        {
            "annual_revenue": generador.lognormal(mean=13.0, sigma=1.0, size=1500),
            "page_views": generador.poisson(lam=8, size=1500),
            "source_channel": generador.choice(
                ["Website", "LinkedIn Ads", "Webinar", "Organic Search"],
                size=1500,
                p=[0.4, 0.3, 0.2, 0.1],
            ),
        }
    )
    informe = evaluar_deriva(produccion, perfil)
    assert informe["veredicto"] == "estable", informe["por_columna"]


def test_un_desplazamiento_de_la_distribucion_se_detecta(perfil):
    """
    El caso realista: la prospección se mueve a empresas mucho mayores. Ninguna variable
    falta, ningún valor es inválido, nada falla —y el modelo está puntuando una población
    que no es la que vio al entrenarse.
    """
    generador = np.random.default_rng(555)
    produccion = pd.DataFrame(
        {
            "annual_revenue": generador.lognormal(mean=16.0, sigma=1.0, size=1500),
            "page_views": generador.poisson(lam=8, size=1500),
            "source_channel": generador.choice(
                ["Website", "LinkedIn Ads", "Webinar", "Organic Search"],
                size=1500,
                p=[0.4, 0.3, 0.2, 0.1],
            ),
        }
    )
    informe = evaluar_deriva(produccion, perfil)
    assert informe["veredicto"] == "deriva significativa"
    assert "annual_revenue" in informe["columnas_con_deriva"]
    # Y no arrastra a las columnas que no cambiaron: un monitor que marca todo no orienta.
    assert "page_views" not in informe["columnas_con_deriva"]


def test_un_canal_nuevo_se_detecta(perfil, referencia):
    """
    Una campaña en un canal que no existía cuando se entrenó: el preprocesador lo trata
    como categoría desconocida y el modelo puntúa igualmente, sin señal de ningún tipo.
    """
    produccion = referencia.copy()
    produccion.loc[produccion.index[:900], "source_channel"] = "TikTok Ads"
    psi = psi_de_columna(produccion["source_channel"], perfil["columnas"]["source_channel"])
    assert psi > UMBRAL_DERIVA


def test_con_pocas_observaciones_no_dictamina(perfil, referencia):
    """
    El PSI se infla con muestras pequeñas. Emitir un veredicto de deriva sobre veinte
    prospectos sería ruido presentado como hallazgo, y basta con un par de falsas alarmas
    para que un monitor se empiece a ignorar.
    """
    informe = evaluar_deriva(referencia.head(MINIMO_OBSERVACIONES - 1), perfil)
    assert informe["veredicto"] == "muestra insuficiente"


def test_una_columna_ausente_no_rompe_el_informe(perfil, referencia):
    informe = evaluar_deriva(referencia.drop(columns=["page_views"]), perfil)
    assert informe["por_columna"]["page_views"]["dictamen"] == "ausente en produccion"


def test_los_umbrales_ordenan_los_dictamenes():
    assert dictamen(0.05) == "estable"
    assert dictamen(0.18) == "vigilar"
    assert dictamen(0.40) == "deriva significativa"
    assert dictamen(None) == "no comparable"


def test_el_perfil_guarda_el_resumen_y_no_los_datos(perfil, referencia):
    """
    El perfil viaja a producción; el conjunto de entrenamiento, no. En cuanto el bucle de
    realimentación esté en marcha, ese conjunto contendrá datos de clientes reales.
    """
    serializado = json.dumps(perfil)
    assert len(serializado) < 20000
    # Ningún valor individual de la referencia aparece en el perfil.
    algun_valor = str(referencia["annual_revenue"].iloc[0])
    assert algun_valor not in serializado


# ============================================================================
# El reparto de motores, que el registro honesto de `model_version` hizo posible
# ============================================================================

def test_el_reparto_de_motores_separa_modelo_de_heuristico():
    """
    Esta lectura no existía: `model_version` era una constante y todas las filas decían
    haber usado el modelo. Un salto hacia `heuristico` significa que el artefacto dejó de
    cargarse en algún despliegue —el servicio responde 200 y las puntuaciones cambian sin
    que nadie lo haya pedido—.
    """
    df = pd.DataFrame(
        {
            "_model_version": [
                "v1.0.0-hybrid+ml:0a2632a2",
                "v1.0.0-hybrid+ml:0a2632a2",
                "v1.0.0-hybrid+heuristico",
                None,
            ]
        }
    )
    reparto = reparto_de_motores(df)
    assert reparto["ml:0a2632a2"] == 2
    assert reparto["heuristico"] == 1
    assert reparto["desconocido"] == 1


# ============================================================================
# Registro de modelos
# ============================================================================

@pytest.fixture
def ruta_registro(tmp_path):
    return str(tmp_path / "registry.json")


def _registrar(metricas, filas, columnas, ruta, huella="sha-de-los-datos", origen="sinteticos"):
    """Registra declarando procedencia, que desde N-15 es obligatoria."""
    return registrar_modelo(metricas, filas, columnas, huella_datos=huella, origen=origen, ruta=ruta)


def _metricas(sha, auc=0.95):
    return {
        "model_sha256": sha,
        "roc_auc": auc,
        "passed": True,
        "lineas_base": {"delta_sobre_heuristico": 0.0414},
    }


def test_el_registro_acumula_en_vez_de_sobrescribir(ruta_registro):
    """
    `metrics.json` se sobrescribe en cada entrenamiento, así que solo existe la última
    ejecución. La serie es lo que permite ver que el ROC-AUC lleva tres entrenamientos
    bajando en lugar de descubrirlo cuando ya no se puede reconstruir.
    """
    _registrar(_metricas("aaa", 0.95), 1000, ["a", "b"], ruta_registro)
    _registrar(_metricas("bbb", 0.91), 1000, ["a", "b"], ruta_registro)

    historico = leer_registro(ruta_registro)
    assert [e["model_sha256"] for e in historico] == ["aaa", "bbb"]
    assert [e["roc_auc"] for e in historico] == [0.95, 0.91]


def test_se_puede_saber_si_un_artefacto_tiene_procedencia(ruta_registro):
    """
    La pregunta que conviene poder responder antes de desplegar: un `.joblib` cuya huella
    no aparece en el registro es un fichero de origen desconocido, y `joblib.load`
    deserializa con pickle (A-10).
    """
    _registrar(_metricas("huella-conocida"), 1000, ["a"], ruta_registro)
    assert artefacto_registrado("huella-conocida", ruta_registro) is True
    assert artefacto_registrado("huella-que-nadie-entreno", ruta_registro) is False
    assert artefacto_registrado("", ruta_registro) is False


def test_la_procedencia_de_los_datos_queda_anotada(ruta_registro):
    sinteticos = _registrar(_metricas("aaa"), 1000, ["a"], ruta_registro, huella="sha-sintetico")
    reales = _registrar(
        _metricas("bbb"), 1000, ["a"], ruta_registro,
        huella="sha-del-dataset", origen="realimentacion",
    )
    assert sinteticos["origen_de_los_datos"] == "sinteticos"
    assert reales["origen_de_los_datos"] == "realimentacion"
    assert sinteticos["huella_datos_sha256"] == "sha-sintetico"


def test_no_se_registra_un_modelo_sin_huella_de_sus_datos(ruta_registro):
    """
    El nucleo de N-15.

    El campo `huella_datos_sha256` existia desde la fase 8 y valia `null` en TODAS las
    entradas, porque `train_model.py` llamaba sin el —el parametro era opcional y nadie
    se lo pasaba—. El registro declaraba una trazabilidad que no tenia: la pregunta «¿con
    que datos se entreno el modelo que puntuo a este prospecto?» seguia sin respuesta y
    ahora ademas parecia contestada.

    Que la llamada falle es la unica forma de que el hueco no se pueda volver a dejar sin
    querer. Un aviso en el registro lo leeria quien ya sabe que hay que mirarlo.
    """
    for huella in (None, "", "   "):
        with pytest.raises(ProcedenciaIncompleta):
            registrar_modelo(_metricas("aaa"), 10, ["a"], huella_datos=huella,
                             origen="sinteticos", ruta=ruta_registro)
    assert leer_registro(ruta_registro) == []


def test_el_origen_se_declara_y_no_se_deduce(ruta_registro):
    """
    Antes `origen_de_los_datos` se deducia de `huella_datos is None`.

    Esa regla era inofensiva mientras la huella no se pasaba nunca, y se vuelve falsa
    exactamente al arreglar lo anterior: con huella obligatoria, TODO entrenamiento
    —incluido el sintetico— habria quedado anotado como «realimentacion», y el registro
    afirmaria que el modelo desplegado se entreno con desenlaces de clientes reales.

    Una deduccion que rellena un hueco deja de ser inofensiva justo cuando el hueco se
    llena.
    """
    entrada = _registrar(_metricas("aaa"), 10, ["a"], ruta_registro,
                         huella="una-huella-de-verdad", origen="sinteticos")
    assert entrada["origen_de_los_datos"] == "sinteticos"

    with pytest.raises(ProcedenciaIncompleta):
        registrar_modelo(_metricas("bbb"), 10, ["a"], huella_datos="x",
                         origen="lo-que-sea", ruta=ruta_registro)


def test_la_huella_no_depende_del_orden_de_filas_ni_de_columnas():
    """
    Sin esta propiedad la huella no serviria para comparar nada.

    Dos extracciones de los MISMOS desenlaces pueden llegar en distinto orden —la base no
    garantiza ninguno sin `ORDER BY`, y el `DataFrame` coloca las columnas segun el dict
    que las construyo—. Si eso cambiara la huella, cada ejecucion daria una distinta y el
    campo solo diria «se entreno alguna vez».
    """
    a = pd.DataFrame({"x": [1, 2, 3], "y": ["a", "b", "c"], "converted": [0, 1, 0]})
    b = a.iloc[::-1][["converted", "y", "x"]].reset_index(drop=True)

    assert huella_de_datos(a) == huella_de_datos(b)


def test_la_huella_cambia_cuando_cambian_los_datos():
    """Una huella que no distingue dos conjuntos distintos no es una huella."""
    a = pd.DataFrame({"x": [1, 2, 3], "converted": [0, 1, 0]})
    b = pd.DataFrame({"x": [1, 2, 4], "converted": [0, 1, 0]})
    c = pd.DataFrame({"x": [1, 2, 3], "converted": [0, 1, 1]})

    assert len({huella_de_datos(a), huella_de_datos(b), huella_de_datos(c)}) == 3


def test_la_huella_ignora_las_columnas_que_no_entran_al_modelo():
    """
    `lead_id` y las marcas de tiempo viajan en el dataset y NO entran al modelo.

    Incluirlas en la huella haria que dos extracciones de los mismos desenlaces, hechas
    con un dia de diferencia, parecieran conjuntos distintos.
    """
    base = {"x": [1, 2], "converted": [0, 1]}
    a = pd.DataFrame({**base, "lead_id": [7, 8], "etiquetado_en": ["ayer", "hoy"]})
    b = pd.DataFrame({**base, "lead_id": [90, 91], "etiquetado_en": ["hoy", "manana"]})

    assert huella_de_datos(a, ["x", "converted"]) == huella_de_datos(b, ["x", "converted"])


def test_se_puede_consultar_con_que_datos_se_entreno_un_artefacto(ruta_registro):
    """
    `artefacto_registrado` responde si o no; N-15 pregunta otra cosa.

    Saber que un `.joblib` tiene procedencia no es lo mismo que poder consultarla, y la
    pregunta que hay que responder ante una puntuacion rara de hace tres meses es la
    segunda.
    """
    _registrar(_metricas("sha-del-joblib"), 2400, ["a"], ruta_registro,
               huella="sha-del-dataset", origen="realimentacion")

    entrada = entrada_de_artefacto("sha-del-joblib", ruta_registro)
    assert entrada["huella_datos_sha256"] == "sha-del-dataset"
    assert entrada["origen_de_los_datos"] == "realimentacion"
    assert entrada["filas_entrenamiento"] == 2400
    assert entrada_de_artefacto("un-joblib-que-nadie-entreno", ruta_registro) is None


def test_un_registro_corrupto_no_impide_entrenar(ruta_registro):
    """Perder el histórico es malo; no poder reentrenar por ello sería peor."""
    with open(ruta_registro, "w", encoding="utf-8") as fh:
        fh.write("{esto no es json")
    entrada = _registrar(_metricas("ccc"), 500, ["a"], ruta_registro)
    assert entrada["model_sha256"] == "ccc"
    assert len(leer_registro(ruta_registro)) == 1


def test_el_registro_no_crece_sin_limite(ruta_registro):
    from model_registry import MAXIMO_ENTRADAS

    for i in range(MAXIMO_ENTRADAS + 15):
        _registrar(_metricas(f"sha-{i}"), 10, ["a"], ruta_registro)
    historico = leer_registro(ruta_registro)
    assert len(historico) == MAXIMO_ENTRADAS
    # Se conservan las más recientes, que son las que sirven para comparar.
    assert historico[-1]["model_sha256"] == f"sha-{MAXIMO_ENTRADAS + 14}"


# ============================================================================
# El artefacto que hay ahora mismo en el repositorio
# ============================================================================

def test_el_modelo_desplegado_esta_registrado():
    """
    Cierra el círculo: el `.joblib` presente debe corresponder a un entrenamiento anotado.
    Si alguien lo sustituye a mano, esto lo dice.
    """
    import os

    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    metrics_path = os.path.join(raiz, "ml_pipeline", "models", "metrics.json")
    if not os.path.exists(metrics_path):
        pytest.skip("No hay métricas: el modelo no se ha entrenado en este entorno.")

    with open(metrics_path, encoding="utf-8") as fh:
        metricas = json.load(fh)
    sha = metricas.get("model_sha256")
    if not sha:
        pytest.skip("El último entrenamiento no superó el gate; no hay artefacto que registrar.")

    ruta = os.path.join(raiz, "ml_pipeline", "models", "registry.json")
    if not os.path.exists(ruta):
        pytest.skip("El registro se crea al entrenar; no existe en este entorno.")
    assert artefacto_registrado(sha, ruta), (
        "El artefacto presente no corresponde a ningún entrenamiento registrado."
    )
