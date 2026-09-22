"""
Gobierno del modelo: procedencia de los datos, bucle de realimentación y alertas de deriva.

Las tres piezas de esta fase existían a medias, y las tres fallaban del mismo modo: el
mecanismo estaba escrito y nadie lo ejercitaba.

* El registro tenía un campo `huella_datos_sha256` que valía `null` en todas las entradas.
* El extractor de desenlaces reales no tenía ningún camino que entrenara con su salida.
* El monitor de deriva calculaba PSI y no avisaba a nadie ni lo lanzaba nadie.

Lo que se comprueba aquí es que ahora **hacen** lo que dicen: que la huella es real y
recalculable, que entrenar con datos reales no publica sin que se pida, y que una alerta
se emite cuando toca y —sobre todo— **se calla cuando no toca**, que es la mitad de la que
depende que alguien la siga leyendo dentro de tres meses.
"""
import json
import os

import pandas as pd
import pytest
from drift_monitor import (
    SILENCIO_ENTRE_ALERTAS,
    emitir_alerta,
    procesar_alertas,
    toca_alertar,
)
from model_registry import huella_de_datos, leer_registro


# ============================================================================
# Alertas de deriva: cuándo avisar y, sobre todo, cuándo callar
# ============================================================================
def _informe(veredicto="estable", columnas=None):
    columnas = columnas or []
    return {
        "evaluado_en": "2026-09-10T00:00:00+00:00",
        "observaciones": 1200,
        "veredicto": veredicto,
        "columnas_con_deriva": columnas,
        "columnas_a_vigilar": [],
        "por_columna": {c: {"psi": 0.44, "dictamen": "deriva significativa"} for c in columnas},
    }


def test_la_primera_deriva_avisa():
    tipo = toca_alertar(_informe("deriva significativa", ["source_channel"]), {}, ahora=1000.0)
    assert tipo == "deriva"


def test_una_poblacion_estable_no_avisa_de_nada():
    assert toca_alertar(_informe("estable"), {}, ahora=1000.0) is None


def test_la_muestra_insuficiente_no_es_una_alerta():
    """
    Con pocas observaciones el PSI se infla, y el monitor ya lo dice devolviendo «muestra
    insuficiente». Convertir eso en un aviso llenaría el canal justo los primeros días,
    que es cuando hay que ganarse que lo lean.
    """
    assert toca_alertar(_informe("muestra insuficiente"), {}, ahora=1000.0) is None


def test_la_misma_deriva_no_vuelve_a_avisar_dentro_del_periodo_de_silencio():
    """
    Esta es la prueba que sostiene el diseño entero.

    La deriva de población dura semanas. Con el monitor evaluando cada seis horas, avisar
    en cada ciclo produce decenas de mensajes idénticos sobre una condición que no ha
    cambiado. Quien los recibe crea un filtro, y a partir de ahí el sistema tiene
    monitorización y no tiene aviso —que es peor que el punto de partida, porque además
    parece resuelto—.
    """
    estado = {"alertando": True, "columnas": ["source_channel"], "ultima_alerta": 1000.0}
    informe = _informe("deriva significativa", ["source_channel"])

    assert toca_alertar(informe, estado, ahora=1000.0 + SILENCIO_ENTRE_ALERTAS - 1) is None


def test_pasado_el_silencio_se_recuerda():
    """Callar no es olvidar: si la condición sigue viva, vuelve a decirse."""
    estado = {"alertando": True, "columnas": ["source_channel"], "ultima_alerta": 1000.0}
    informe = _informe("deriva significativa", ["source_channel"])

    assert toca_alertar(informe, estado, ahora=1000.0 + SILENCIO_ENTRE_ALERTAS) == "deriva"


def test_si_cambian_las_columnas_afectadas_se_avisa_aunque_no_haya_pasado_el_silencio():
    """
    «Sigue derivando» y «ahora deriva otra cosa» son el mismo veredicto y hallazgos
    distintos.

    Que a la deriva de `source_channel` se le sume `industry` puede ser lo que convierta
    una campaña rara en un cambio de mercado. Silenciarlo por contarse dentro de la misma
    condición sería perder justo la novedad.
    """
    estado = {"alertando": True, "columnas": ["source_channel"], "ultima_alerta": 1000.0}
    informe = _informe("deriva significativa", ["source_channel", "industry"])

    assert toca_alertar(informe, estado, ahora=1001.0) == "deriva"


def test_la_vuelta_a_la_normalidad_tambien_se_avisa():
    """
    Sin esto, quien recibió la alerta no sabe nunca si la condición sigue viva y acaba
    teniendo que abrir el panel para averiguarlo, que es exactamente lo que la alerta
    venía a evitar.
    """
    estado = {"alertando": True, "columnas": ["source_channel"], "ultima_alerta": 1000.0}

    assert toca_alertar(_informe("estable"), estado, ahora=1001.0) == "recuperacion"
    # Y solo una vez: la segunda evaluación estable ya no tiene nada que contar.
    assert toca_alertar(_informe("estable"), {"alertando": False}, ahora=1002.0) is None


def test_el_estado_persiste_entre_evaluaciones(tmp_path, capsys):
    """El silencio entre alertas solo funciona si la evaluación siguiente recuerda."""
    ruta = str(tmp_path / "estado.json")
    informe = _informe("deriva significativa", ["source_channel"])

    assert procesar_alertas(informe, ruta, ahora=1000.0) == "deriva"
    assert procesar_alertas(informe, ruta, ahora=1001.0) is None

    estado = json.load(open(ruta, encoding="utf-8"))
    assert estado["alertando"] is True
    assert estado["columnas"] == ["source_channel"]

    salida = capsys.readouterr().out
    assert salida.count("[ALERTA-DERIVA]") == 1


def test_un_estado_corrupto_no_impide_evaluar(tmp_path, capsys):
    """
    Perder el estado cuesta, como mucho, un aviso repetido. Dejar de vigilar por no poder
    leer un JSON sería cambiar un ruido por una ceguera.
    """
    ruta = str(tmp_path / "estado.json")
    open(ruta, "w", encoding="utf-8").write("{esto no es json")

    assert procesar_alertas(_informe("deriva significativa", ["industry"]), ruta, ahora=1.0) == "deriva"
    assert "[ALERTA-DERIVA]" in capsys.readouterr().out


def test_la_alerta_sale_como_un_objeto_json_en_una_linea(capsys):
    """
    El resto del registro del sistema es un objeto JSON por línea (`observabilidad.py`).
    Una alerta con otro formato obliga a un analizador propio en el agregador, y lo que
    necesita un analizador propio termina sin recogerse.
    """
    informe = _informe("deriva significativa", ["source_channel", "industry"])
    evento = emitir_alerta(informe, "deriva")

    linea = capsys.readouterr().out.strip()
    assert linea.startswith("[ALERTA-DERIVA] ")
    assert len(linea.splitlines()) == 1

    reconstruido = json.loads(linea[len("[ALERTA-DERIVA] "):])
    assert reconstruido == evento
    assert reconstruido["columnas_con_deriva"] == ["source_channel", "industry"]
    assert reconstruido["psi"]["industry"] == 0.44


def test_un_webhook_caido_no_tumba_el_monitor_pero_se_nota(monkeypatch, capsys):
    """
    Dos exigencias a la vez, y la segunda importa más.

    La deriva sigue mereciendo evaluarse aunque el receptor esté caído, así que el fallo
    de entrega no puede propagarse. Pero tiene que **verse**: una alerta que no llega y no
    dice que no llegó deja al sistema aparentando vigilancia.
    """
    import drift_monitor

    monkeypatch.setattr(drift_monitor, "WEBHOOK", "http://receptor-inexistente.invalid/hook")

    def _explota(*_args, **_kwargs):
        raise OSError("conexion rechazada")

    monkeypatch.setattr(drift_monitor.urllib.request, "urlopen", _explota)

    emitir_alerta(_informe("deriva significativa", ["industry"]), "deriva")

    salida = capsys.readouterr().out
    assert "[ALERTA-DERIVA]" in salida
    assert "NO se pudo entregar" in salida


def test_la_url_del_webhook_no_aparece_en_la_salida(monkeypatch, capsys):
    """
    Suele llevar un testigo en la ruta. Un registro que la reproduce convierte el canal de
    avisos en una credencial filtrada, y los registros se comparten en cuanto hay un
    incidente —que es justo cuando estas líneas se leen—.
    """
    import drift_monitor

    secreta = "https://hooks.example.invalid/servicios/T000/B000/testigo-secreto"
    monkeypatch.setattr(drift_monitor, "WEBHOOK", secreta)
    monkeypatch.setattr(drift_monitor.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("nope")))

    emitir_alerta(_informe("deriva significativa", ["industry"]), "deriva")

    salida = capsys.readouterr().out
    assert "testigo-secreto" not in salida
    assert secreta not in salida


def test_el_webhook_solo_admite_http_y_https(monkeypatch, capsys):
    """
    La URL viene de una variable de entorno, así que su esquema es entrada, no constante.

    `urlopen` atiende también `file:`, de modo que `ML_DRIFT_WEBHOOK=file:///etc/passwd`
    convertiría el canal de avisos en una lectura del sistema de archivos del contenedor.
    Lo señaló el análisis estático (S310) y no era ruido.
    """
    import drift_monitor

    llamadas = []
    monkeypatch.setattr(drift_monitor.urllib.request, "urlopen",
                        lambda *a, **k: llamadas.append(a))

    for url in ("file:///etc/passwd", "ftp://servidor.invalid/x", "gopher://x"):
        monkeypatch.setattr(drift_monitor, "WEBHOOK", url)
        emitir_alerta(_informe("deriva significativa", ["industry"]), "deriva")

    assert llamadas == [], "se intento entregar la alerta por un esquema que no es http(s)"
    assert capsys.readouterr().out.count("que no se entrega") == 3


# ============================================================================
# Procedencia de los datos de entrenamiento (N-15)
# ============================================================================
@pytest.fixture(scope="module")
def cohorte():
    """
    Una cohorte pequeña pero con señal: entrenar sobre ruido no probaría nada.

    1500 y no 400. Con el vector 2 (capítulo 24), 400 filas dejan 80 de prueba y un aporte
    sobre el heurístico de +0.0065 con IC [-0.024, +0.040]: ruido. Con 1500, +0.049 con IC
    [+0.019, +0.080]. Es la misma lección que el intervalo del aporte hace cumplir.
    """
    from synthetic_generator import generate_synthetic_leads_dataset

    return generate_synthetic_leads_dataset(num_samples=1500, random_seed=7)


def test_entrenar_deja_en_el_registro_la_huella_de_sus_datos(tmp_path, cohorte):
    """
    La prueba que hubiera hecho fallar el defecto original.

    `registrar_modelo` aceptaba `huella_datos` desde la fase 8; `train_model.py` llamaba
    sin él. Nada fallaba: el registro se escribía, el CI comprobaba que el artefacto
    aparecía en él, y el campo quedaba en `null` ejecución tras ejecución.

    Se exige además que la huella coincida con la que recalcula un tercero desde el mismo
    conjunto. Un valor cualquiera —una constante, la fecha— también dejaría el campo
    distinto de `null`.
    """
    from train_model import FEATURE_COLS, entrenar

    entrenar(cohorte, origen="sinteticos", procedencia={"semilla": 7},
             publicar=False, directorio_modelos=str(tmp_path))

    entrada = leer_registro(str(tmp_path / "registry.json"))[-1]
    esperada = huella_de_datos(cohorte, FEATURE_COLS + ["converted"])

    assert entrada["huella_datos_sha256"] == esperada
    assert entrada["origen_de_los_datos"] == "sinteticos"
    assert entrada["publicado"] is False


def test_medir_con_datos_reales_no_publica_el_artefacto(tmp_path, cohorte):
    """
    El artefacto y el perfil de referencia desplegados no se tocan al medir.

    Con las decenas de filas del primer dataset real, un modelo puede superar los dos
    umbrales sin haber aprendido nada generalizable —cuanto menor es el conjunto de
    prueba, más fácil es que el ROC-AUC salga alto por azar—. Si el mismo comando que mide
    fuera el que despliega, ese modelo llegaría a producción sin que nadie lo decidiera.
    """
    from train_model import entrenar

    metricas = entrenar(cohorte, origen="realimentacion", procedencia={},
                        publicar=False, directorio_modelos=str(tmp_path))

    assert metricas["passed"] is True, "la cohorte deberia superar los umbrales"
    assert not os.path.exists(tmp_path / "lead_scorer_model.joblib")
    assert not os.path.exists(tmp_path / "reference_profile.json")
    assert "model_sha256" not in metricas


def test_una_medicion_no_ensucia_el_registro_de_produccion(tmp_path, cohorte):
    """
    `publicar=False` protegía el artefacto y el perfil, y NO el registro.

    La primera versión del ensayo del bucle dejó en el registro real una entrada de origen
    `realimentacion` con 36 filas, indistinguible de un entrenamiento contra desenlaces de
    clientes de verdad. Ensuciar la procedencia es hacer daño exactamente en el sitio que
    N-15 vino a arreglar.
    """
    from model_registry import ruta_por_defecto
    from train_model import entrenar

    antes = len(leer_registro(ruta_por_defecto()))
    entrenar(cohorte, origen="realimentacion", procedencia={},
             publicar=False, directorio_modelos=str(tmp_path))

    assert len(leer_registro(ruta_por_defecto())) == antes
    assert len(leer_registro(str(tmp_path / "registry.json"))) == 1


def test_la_lista_de_variables_es_la_misma_en_las_dos_mitades():
    """
    `train_model.FEATURE_COLS` y `feedback_dataset.COLUMNAS_MODELO` describen el mismo
    vector desde archivos distintos.

    Si se separan, el dataset real se construiría con un vector y el modelo se entrenaría
    con otro: el reentrenamiento fallaría por columnas ausentes o —peor— las tomaría en
    otro orden y aprendería asociaciones cruzadas sin que nada lo dijera.
    """
    from feedback_dataset import COLUMNAS_MODELO
    from train_model import FEATURE_COLS

    assert FEATURE_COLS == COLUMNAS_MODELO


# ============================================================================
# El intervalo de confianza, que es lo que hace legible un ROC-AUC pequeño
# ============================================================================
def test_el_intervalo_contiene_la_estimacion_puntual():
    from sklearn.metrics import roc_auc_score
    from train_model import intervalo_bootstrap

    generador = pd.Series(range(200))
    y = (generador % 2).to_numpy()
    prob = (generador / 200 + y * 0.3).to_numpy()

    puntual = roc_auc_score(y, prob)
    ic = intervalo_bootstrap(y, prob, remuestreos=400)

    assert ic["inferior"] <= puntual <= ic["superior"]


def test_con_menos_ejemplos_el_intervalo_se_ensancha():
    """
    Es la razón por la que el intervalo se calcula siempre.

    Con nueve ejemplos de prueba —el orden de magnitud del primer dataset real— el ROC-AUC
    puede salir en 0.89 y ser compatible con casi cualquier valor. La estimación puntual y
    el intervalo dicen cosas distintas, y solo el segundo permite decidir si publicar.
    """
    from train_model import intervalo_bootstrap

    muchos = pd.Series(range(400))
    y_muchos = (muchos % 2).to_numpy()
    p_muchos = (muchos / 400 + y_muchos * 0.25).to_numpy()

    pocos = pd.Series(range(12))
    y_pocos = (pocos % 2).to_numpy()
    p_pocos = (pocos / 12 + y_pocos * 0.25).to_numpy()

    ancho_muchos = lambda ic: ic["superior"] - ic["inferior"]  # noqa: E731
    estrecho = ancho_muchos(intervalo_bootstrap(y_muchos, p_muchos, remuestreos=400))
    ancho = ancho_muchos(intervalo_bootstrap(y_pocos, p_pocos, remuestreos=400))

    assert ancho > estrecho * 2


def test_sin_las_dos_clases_no_hay_intervalo_que_calcular():
    """Devolver un número aquí sugeriría una precisión que no existe."""
    from train_model import intervalo_bootstrap

    assert intervalo_bootstrap([1, 1, 1, 1], [0.2, 0.4, 0.6, 0.8]) is None


# ============================================================================
# El bucle de realimentación sin datos todavía
# ============================================================================
def test_sin_desenlaces_el_extractor_lo_dice_en_vez_de_reventar(capsys, tmp_path):
    """
    `--sin-minimos` es justo la opción a la que se recurre el primer día, para mirar qué
    hay. Con cero desenlaces terminaba en un `KeyError` de pandas contra columnas que un
    DataFrame vacío no tiene: una traza en lugar de la respuesta, que es «todavía no ha
    cerrado ningún prospecto».
    """
    from feedback_dataset import main

    codigo = main(["--sin-minimos", "--salida", str(tmp_path / "no-deberia-escribirse.csv")])

    assert codigo == 1
    assert "[REALIMENTACION]" in capsys.readouterr().out
    assert not os.path.exists(tmp_path / "no-deberia-escribirse.csv"), (
        "un CSV vacio se entrena igual de mal que uno malo, y ademas sin avisar"
    )
