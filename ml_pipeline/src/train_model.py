"""
Entrenamiento del modelo de calificación de prospectos.

Hay **dos** conjuntos de datos posibles y un solo camino de entrenamiento:

    python ml_pipeline/src/train_model.py
    python ml_pipeline/src/train_model.py --datos realimentacion

El primero genera datos sintéticos y es el que corre en CI; el segundo entrena contra los
desenlaces comerciales reales que produce `feedback_dataset.py`. Comparten función, no
solo intención: si cada uno tuviera la suya, la comparación entre el modelo sintético y el
real mediría también las diferencias entre los dos códigos, y esa es exactamente la
comparación que hay que poder hacer sin dudas.

Lo que cambia entre ambos no es cómo se entrena sino **qué autoriza a publicar**. Con
datos sintéticos, superar los umbrales basta. Con datos reales, además hay que pedirlo:
`--publicar`. La razón está en el tamaño; véase `_PUBLICACION` más abajo.
"""
import argparse
import hashlib
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, brier_score_loss, classification_report, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

# Asegurar import de módulos locales
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
# El vector del modelo vive en el backend (`app.core.vector_del_modelo`). Se añade aquí y no se
# deja a que lo haga `feature_engineering` al importarse: el orden de los imports no puede
# ser lo que decida si este módulo arranca.
_backend_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "backend"))
if os.path.isdir(_backend_dir) and _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from app.core.vector_del_modelo import COLUMNAS_DEL_MODELO, VERSION_DEL_VECTOR  # noqa: E402
from baselines import (  # noqa: E402  (requiere el sys.path de arriba)
    comparar_contra_lineas_base,
    formatear_comparacion,
    puntuar_con_heuristico,
)
from drift_monitor import construir_perfil  # noqa: E402
from feature_engineering import build_preprocessor  # noqa: E402
from model_registry import huella_de_datos, registrar_modelo  # noqa: E402
from synthetic_generator import generate_synthetic_leads_dataset  # noqa: E402

# Umbral de calidad del modelo. Es el compromiso funcional del sistema: por debajo de
# 0.82 el ordenamiento de prospectos deja de ser mejor que el criterio manual que
# pretende sustituir, y publicar ese artefacto degradaría el producto en silencio.
# Se puede subir por entorno para endurecerlo, nunca conviene bajarlo sin decisión
# explícita: por eso el valor vive aquí y no en el workflow de CI.
AUC_THRESHOLD = float(os.getenv("ML_AUC_THRESHOLD", "0.82"))

# Aporte minimo del modelo sobre el heuristico ICP, medido en ROC-AUC sobre el mismo
# conjunto de prueba.
#
# El umbral anterior, por si solo, no distinguia un modelo util de uno inutil: en este
# dataset una regla trivial —ordenar por `days_since_last_activity`— ya alcanza 0.91, muy
# por encima de 0.82. Un clasificador roto que hubiera aprendido solo esa variable pasaria
# el gate sin problema.
#
# Este segundo umbral mide lo unico que justifica mantener el modelo: cuanto mejora
# respecto de no tenerlo. Es ademas la red que atrapa una regresion como ML-4 —donde el
# adaptador dejo de pasarle al modelo las senales de compra que ya se calculaban—: la
# precision absoluta apenas se movia, pero el aporte se desplomaba.
#
# Medido: +0.0414. Se exige 0.01 para dejar margen a la variabilidad del muestreo sin que
# el gate deje de significar nada.
MIN_DELTA_SOBRE_HEURISTICO = float(os.getenv("ML_MIN_DELTA_HEURISTICO", "0.01"))

# Variables que consume el modelo, en orden. Salen de `app.core.vector_del_modelo`, la
# misma lista que usan el adaptador de producción y `feedback_dataset.COLUMNAS_MODELO`: si
# se separan, el dataset real se entrenaria con un vector distinto del que sirve produccion
# y nada lo diria.
FEATURE_COLS = list(COLUMNAS_DEL_MODELO)

SEMILLA = 42

# Remuestreos para el intervalo de confianza del ROC-AUC. Con 600 ejemplos de prueba el
# intervalo es estrecho y el numero apenas importa; con 12 —que es el orden de magnitud
# del primer dataset real— el intervalo es lo unico que impide leer un 0.71 como un
# hallazgo. Se calcula SIEMPRE, no solo con datos reales: un intervalo que solo aparece
# cuando el resultado es incomodo se lee como excusa.
REMUESTREOS_BOOTSTRAP = int(os.getenv("ML_BOOTSTRAP", "2000"))

_PUBLICACION = """
Por qué entrenar con datos reales no publica el artefacto por defecto.

El primer dataset de realimentación de un sistema como este tiene decenas de filas, no
miles: son los prospectos que han llegado a `WON` o `LOST` desde que el producto está en
marcha. Un modelo entrenado con esa cantidad puede perfectamente dar un ROC-AUC alto
—cuanto menor es el conjunto de prueba, más fácil es que salga alto por azar— y superar
los dos umbrales sin haber aprendido nada generalizable.

Si el mismo comando que mide fuera también el que despliega, ese modelo pasaría a
producción por el camino normal, sin que nadie decidiera nada. Separar las dos cosas hace
que medir sea barato y frecuente —que es lo que se quiere— y que publicar siga siendo un
acto deliberado.

Y pedirlo tampoco basta. Hasta la Fase 13, `--publicar` dependía de que quien lo escribía
hubiera mirado el intervalo de confianza: era una convención. Ahora es una condición del
código —el límite inferior del IC 95 % del ROC-AUC tiene que alcanzar el umbral—, porque el
ensayo del bucle la había dejado a la vista: con 45 desenlaces el ROC-AUC puntual daba
0.8889 y superaba el umbral, con un intervalo [0.571, 1.000] que admite un modelo muy por
debajo de él.

Desde el capítulo 24 lo mismo vale para el aporte sobre el heurístico. Se exigía con la
estimación puntual, y el aporte es una diferencia entre dos ROC-AUC medidos sobre las mismas
filas: más inestable que cualquiera de los dos. Ahora el límite inferior de su IC 95 % tiene
que alcanzar el aporte mínimo.
"""


# ============================================================================
# Datos
# ============================================================================
def cargar_sinteticos(guardar: bool = True) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Genera el dataset sintético reproducible y lo deja en `data/leads_historical.csv`."""
    print("1. Generando dataset de entrenamiento (3,000 registros)...")
    df = generate_synthetic_leads_dataset(num_samples=3000, random_seed=SEMILLA)

    if guardar:
        data_dir = os.path.abspath(os.path.join(current_dir, "..", "data"))
        os.makedirs(data_dir, exist_ok=True)
        dataset_path = os.path.join(data_dir, "leads_historical.csv")
        df.to_csv(dataset_path, index=False)
        print(f"   -> Dataset guardado en: {dataset_path}")

    procedencia = {
        "generador": "synthetic_generator.generate_synthetic_leads_dataset",
        "semilla": SEMILLA,
        "filas_generadas": int(len(df)),
    }
    return df, procedencia


def cargar_realimentacion(ruta: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Carga el dataset etiquetado con desenlaces comerciales reales.

    No lo construye: lo produce `feedback_dataset.py`, que es quien habla con la base. La
    separación no es de estilo. `feedback_dataset` importa `app.core.database` y necesita
    una base viva; entrenar no. Fundirlos haría que CI —que entrena y no tiene base— no
    pudiera ni importar este módulo.
    """
    ruta = os.path.abspath(ruta)
    if not os.path.exists(ruta):
        raise SystemExit(
            f"No existe {ruta}.\n"
            "El dataset de desenlaces reales lo genera:\n"
            "    python ml_pipeline/src/feedback_dataset.py --salida " + ruta
        )
    df = pd.read_csv(ruta)
    faltan = [c for c in FEATURE_COLS + ["converted"] if c not in df.columns]
    if faltan:
        raise SystemExit(f"Al dataset le faltan columnas que el modelo necesita: {faltan}")

    procedencia: Dict[str, Any] = {"dataset": os.path.basename(ruta)}
    ruta_manifiesto = os.path.splitext(ruta)[0] + "_manifiesto.json"
    if os.path.exists(ruta_manifiesto):
        with open(ruta_manifiesto, encoding="utf-8") as fh:
            procedencia["manifiesto"] = json.load(fh)
    else:
        # No es fatal, pero sí digno de decirse: sin manifiesto no se sabe de qué ventana
        # temporal salieron las etiquetas ni cuántos prospectos se excluyeron por seguir
        # en curso, y esas dos cifras son la mitad de la interpretación.
        print("   [aviso] El dataset viene sin manifiesto de procedencia.")

    print(f"1. Dataset de realimentacion: {len(df)} desenlaces reales desde {ruta}")
    return df, procedencia


# ============================================================================
# Medición
# ============================================================================
def motivo_para_no_publicar(
    auc: float,
    delta: float,
    intervalo: Optional[Dict[str, Any]],
    filas_prueba: int,
    *,
    intervalo_aporte: Optional[Dict[str, Any]],
) -> Optional[str]:
    """
    Por qué este modelo no puede publicarse, o `None` si puede.

    Los dos primeros motivos son los umbrales de siempre. El tercero y el cuarto son la
    Fase 13: una estimación puntual que supera el umbral no basta si su intervalo dice que
    el modelo podría estar por debajo. Con miles de ejemplos de prueba ambos criterios
    coinciden y este no cuesta nada —con los datos sintéticos el límite inferior queda en
    0.93—; con decenas, es lo único que separa un modelo útil de uno afortunado.

    El quinto y el sexto son el capítulo 24, y aplican al aporte sobre el heurístico la
    misma exigencia. `intervalo_aporte` es obligatorio y sin valor por defecto: un gate que
    se pudiera llamar sin él volvería a decidir con la estimación puntual sin que se notara.

    Es una función aparte, y pura, para que la guarda de CI pueda preguntarle directamente
    sin entrenar nada.
    """
    if auc < AUC_THRESHOLD:
        return f"ROC-AUC {auc:.4f} por debajo del umbral {AUC_THRESHOLD:.2f}"
    if delta < MIN_DELTA_SOBRE_HEURISTICO:
        return (
            f"el modelo solo aporta {delta:+.4f} sobre el heuristico "
            f"(minimo exigido: {MIN_DELTA_SOBRE_HEURISTICO:+.4f}). Revise si el vector "
            f"de variables que recibe el clasificador sigue completo"
        )
    if not intervalo:
        return (
            f"no hay intervalo de confianza calculable con {filas_prueba} ejemplos de prueba; "
            f"sin el, un ROC-AUC de {auc:.4f} no distingue un modelo util de uno afortunado"
        )
    if intervalo["inferior"] < AUC_THRESHOLD:
        return (
            f"el ROC-AUC puntual ({auc:.4f}) supera el umbral, pero el limite inferior de su "
            f"IC 95 % ({intervalo['inferior']:.4f}) no llega a {AUC_THRESHOLD:.2f}: con "
            f"{filas_prueba} ejemplos de prueba la estimacion es compatible con un modelo "
            f"peor que el umbral"
        )
    if not intervalo_aporte:
        return (
            f"no hay intervalo de confianza calculable para el aporte sobre el heuristico con "
            f"{filas_prueba} ejemplos de prueba; sin el, un aporte de {delta:+.4f} no se "
            f"distingue del ruido del muestreo"
        )
    if intervalo_aporte["inferior"] < MIN_DELTA_SOBRE_HEURISTICO:
        return (
            f"el aporte puntual sobre el heuristico ({delta:+.4f}) supera el minimo, pero el "
            f"limite inferior de su IC 95 % ({intervalo_aporte['inferior']:+.4f}) no llega a "
            f"{MIN_DELTA_SOBRE_HEURISTICO:+.4f}: con {filas_prueba} ejemplos de prueba el "
            f"modelo podria no mejorar lo que ya hace la regla"
        )
    return None


def intervalo_bootstrap(
    y_real: np.ndarray, y_prob: np.ndarray, remuestreos: int = REMUESTREOS_BOOTSTRAP
) -> Optional[Dict[str, float]]:
    """
    Intervalo de confianza del 95 % para el ROC-AUC, por remuestreo con reemplazo.

    Un ROC-AUC es una estimación puntual y se lee como si fuera una medida. Con 600
    ejemplos de prueba la diferencia es irrelevante; con 12, «0.71» y «entre 0.31 y 1.00»
    son la misma información y solo la segunda es honesta.

    Los remuestreos que se quedan con una sola clase se descartan: el ROC-AUC no está
    definido ahí. Si quedan demasiado pocos válidos, se devuelve `None` en vez de un
    intervalo calculado sobre un puñado de réplicas, que sugeriría una precisión que no hay.
    """
    y_real = np.asarray(y_real)
    y_prob = np.asarray(y_prob)
    if len(np.unique(y_real)) < 2:
        return None

    generador = np.random.default_rng(SEMILLA)
    indices = np.arange(len(y_real))
    valores: List[float] = []
    for _ in range(remuestreos):
        muestra = generador.choice(indices, size=len(indices), replace=True)
        if len(np.unique(y_real[muestra])) < 2:
            continue
        valores.append(float(roc_auc_score(y_real[muestra], y_prob[muestra])))

    if len(valores) < remuestreos * 0.5:
        return None
    return {
        "inferior": round(float(np.percentile(valores, 2.5)), 4),
        "superior": round(float(np.percentile(valores, 97.5)), 4),
        "remuestreos_validos": len(valores),
    }


def intervalo_bootstrap_del_aporte(
    y_real: np.ndarray,
    y_prob: np.ndarray,
    puntuaciones_heuristico: np.ndarray,
    remuestreos: int = REMUESTREOS_BOOTSTRAP,
) -> Optional[Dict[str, float]]:
    """
    IC 95 % del aporte del modelo sobre el heurístico: ROC-AUC del modelo menos el de la regla.

    El remuestreo es **pareado**: en cada réplica se toman las mismas filas para los dos y se
    resta. Remuestrear cada ROC-AUC por su cuenta y restar los percentiles mediría dos
    incertidumbres como si fueran independientes y daría un intervalo más ancho que el real:
    los dos se calculan sobre los mismos prospectos y fallan en los mismos casos difíciles.

    Mismo criterio que `intervalo_bootstrap` para las réplicas con una sola clase y para
    negarse a dar un intervalo con demasiado pocas válidas. Misma semilla, de modo que las
    réplicas son las mismas filas que las del intervalo del ROC-AUC.
    """
    y_real = np.asarray(y_real)
    y_prob = np.asarray(y_prob, dtype=float)
    heuristico = np.asarray(puntuaciones_heuristico, dtype=float)
    if len(np.unique(y_real)) < 2:
        return None

    generador = np.random.default_rng(SEMILLA)
    indices = np.arange(len(y_real))
    valores: List[float] = []
    for _ in range(remuestreos):
        muestra = generador.choice(indices, size=len(indices), replace=True)
        if len(np.unique(y_real[muestra])) < 2:
            continue
        valores.append(
            float(roc_auc_score(y_real[muestra], y_prob[muestra]))
            - float(roc_auc_score(y_real[muestra], heuristico[muestra]))
        )

    if len(valores) < remuestreos * 0.5:
        return None
    return {
        "inferior": round(float(np.percentile(valores, 2.5)), 4),
        "superior": round(float(np.percentile(valores, 97.5)), 4),
        "remuestreos_validos": len(valores),
    }


def _sha256_de_fichero(ruta: str) -> str:
    sha = hashlib.sha256()
    with open(ruta, "rb") as fh:
        for bloque in iter(lambda: fh.read(1024 * 1024), b""):
            sha.update(bloque)
    return sha.hexdigest()


# ============================================================================
# Entrenamiento
# ============================================================================
def entrenar(
    df: pd.DataFrame,
    origen: str,
    procedencia: Dict[str, Any],
    publicar: bool = True,
    directorio_modelos: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Entrena, evalúa y —si procede— publica. Devuelve las métricas.

    `publicar=False` mide sin tocar el artefacto ni el perfil de referencia. Es el modo en
    que se estrena el bucle de realimentación mientras el volumen es pequeño.

    `directorio_modelos` desvía las métricas Y EL REGISTRO a otro sitio. Existe por un
    error concreto: la primera versión del ensayo del bucle —que entrena sobre una base
    desechable con etiquetas inventadas— dejó en el registro de producción una entrada
    `origen_de_los_datos: "realimentacion"` con 36 filas, indistinguible de un
    entrenamiento real contra desenlaces de clientes. `publicar=False` protegía el
    artefacto y el perfil, pero no el registro, y el registro es justamente la respuesta a
    «¿con qué datos se entrenó esto?» que N-15 vino a arreglar. Un ensayo que ensucia la
    procedencia hace daño en el mismo sitio que el defecto que arregla.
    """
    print("=" * 65)
    print(f"ENTRENAMIENTO DEL MODELO DE LEAD SCORING - PLURIONE  [{origen}]")
    print("=" * 65)

    X = df[FEATURE_COLS]
    y = df["converted"].astype(int)

    if y.nunique() < 2:
        raise SystemExit("El dataset tiene una sola clase; no hay nada que aprender.")

    # `stratify` mantiene la proporción de conversiones en ambas particiones. Con datos
    # reales y pocas decenas de filas, sin él una partición puede quedarse sin positivos y
    # el ROC-AUC no llega ni a calcularse.
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=SEMILLA, stratify=y
    )
    print(f"   -> Conjunto de Entrenamiento: {len(X_train)} ejemplos")
    print(f"   -> Conjunto de Prueba:        {len(X_test)} ejemplos")

    print("2. Configurando pipeline de preprocesamiento y clasificador GradientBoosting...")
    preprocessor = build_preprocessor()

    base_model = GradientBoostingClassifier(
        n_estimators=120,
        learning_rate=0.08,
        max_depth=4,
        subsample=0.85,
        random_state=SEMILLA,
    )

    # Envolver clasificador base en CalibratedClassifierCV para probabilidades bien
    # calibradas. `cv=3` exige al menos 3 ejemplos de la clase minoritaria en el
    # entrenamiento; con datasets reales pequeños se baja a 2 antes que fallar, y se dice.
    pliegues = 3
    minoritaria = int(y_train.value_counts().min())
    if minoritaria < pliegues:
        pliegues = max(2, minoritaria)
        print(f"   [aviso] Clase minoritaria con {minoritaria} ejemplos: calibrando con cv={pliegues}.")

    calibrated_model = CalibratedClassifierCV(
        estimator=base_model,
        method="isotonic",
        cv=pliegues,
    )

    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", calibrated_model),
    ])

    print("3. Entrenando modelo con calibración de probabilidades...")
    pipeline.fit(X_train, y_train)

    print("4. Evaluando métricas en conjunto de prueba...")
    y_pred = pipeline.predict(X_test)
    y_prob = pipeline.predict_proba(X_test)[:, 1]

    auc_score = roc_auc_score(y_test, y_prob)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    acc = accuracy_score(y_test, y_pred)
    brier = brier_score_loss(y_test, y_prob)
    intervalo = intervalo_bootstrap(y_test.to_numpy(), y_prob)

    print("\n" + "-" * 50)
    print("RESULTADOS DE EVALUACIÓN DEL MODELO:")
    print("-" * 50)
    cumple_auc = auc_score >= AUC_THRESHOLD
    veredicto = 'CUMPLIDA' if cumple_auc else 'NO CUMPLIDA'
    print(f"  ROC-AUC Score:      {auc_score:.4f}  (Meta >= {AUC_THRESHOLD:.2f}: {veredicto})")
    if intervalo:
        print(f"  IC 95 % (bootstrap):[{intervalo['inferior']:.4f}, {intervalo['superior']:.4f}]"
              f"  sobre {len(y_test)} ejemplos de prueba")
    else:
        print("  IC 95 % (bootstrap):no calculable (muy pocos ejemplos o una sola clase)")
    print(f"  F1-Score:           {f1:.4f}")
    print(f"  Exactitud (Acc):    {acc * 100:.2f}%")
    print(f"  Brier Score (Calib):{brier:.4f}")
    print("-" * 50)
    print("\nReporte de Clasificación Detallado:")
    print(classification_report(y_test, y_pred, target_names=["No Convirtió", "Convirtió (SQL)"],
                                zero_division=0))

    # Comparación contra líneas base. Un ROC-AUC alto no significa nada sin saber contra
    # qué compite: lo que hay que poder responder es «¿cuánto mejora esto respecto de no
    # tener modelo?». La referencia relevante es el heurístico ICP, porque es exactamente
    # lo que el sistema haría si se retirase el clasificador.
    puntuaciones_heuristico = puntuar_con_heuristico(X_test)
    comparacion = comparar_contra_lineas_base(X_test, y_test, y_prob, puntuaciones_heuristico)
    print(formatear_comparacion(comparacion))

    delta = float(comparacion["delta_sobre_heuristico"])
    cumple_delta = delta >= MIN_DELTA_SOBRE_HEURISTICO
    intervalo_aporte = intervalo_bootstrap_del_aporte(
        y_test.to_numpy(), y_prob, puntuaciones_heuristico.to_numpy()
    )
    print(
        f"  Umbral de aporte minimo: {MIN_DELTA_SOBRE_HEURISTICO:+.4f}  ->  "
        f"{'CUMPLIDO' if cumple_delta else 'NO CUMPLIDO'}"
    )
    if intervalo_aporte:
        print(f"  IC 95 % del aporte (bootstrap pareado): "
              f"[{intervalo_aporte['inferior']:+.4f}, {intervalo_aporte['superior']:+.4f}]\n")
    else:
        print("  IC 95 % del aporte: no calculable (muy pocos ejemplos o una sola clase)\n")
    cumple = cumple_auc and cumple_delta
    motivo_publicacion = motivo_para_no_publicar(
        float(auc_score), delta, intervalo, int(len(X_test)), intervalo_aporte=intervalo_aporte
    )

    # La huella de los datos, sobre las columnas que de verdad entraron al modelo más la
    # etiqueta. Es lo que ata el artefacto al conjunto que lo produjo (N-15), y se calcula
    # aquí —no en quien llama— para que ningún camino de entrenamiento pueda saltárselo.
    huella_datos = huella_de_datos(df, FEATURE_COLS + ["converted"])
    print(f"   Huella SHA-256 de los datos de entrenamiento:\n   -> {huella_datos}")

    models_dir = os.path.abspath(
        directorio_modelos or os.path.join(current_dir, "..", "models")
    )
    os.makedirs(models_dir, exist_ok=True)
    ruta_registro = os.path.join(models_dir, "registry.json")

    naturaleza = {
        "sinteticos": (
            "sinteticos: la etiqueta `converted` se genera con una formula conocida a "
            "partir de las propias variables mas ruido gaussiano. Estas metricas verifican "
            "la INTEGRIDAD DEL PIPELINE (que las variables llegan, que el preprocesado no "
            "las corrompe, que la calibracion funciona), no el rendimiento esperable en "
            "produccion, que solo puede medirse con conversiones reales."
        ),
        "realimentacion": (
            "reales: la etiqueta viene del estado terminal (WON / LOST / UNQUALIFIED) de "
            "prospectos concretos, tomada sobre la instantanea de variables del momento en "
            "que entraron al embudo. Estas metricas SI hablan del negocio, pero leanse con "
            "el intervalo de confianza al lado: con pocas decenas de ejemplos la estimacion "
            "puntual del ROC-AUC es compatible con casi cualquier valor."
        ),
    }

    # Las métricas se escriben antes de decidir si el modelo pasa: cuando el gate falla,
    # este archivo es la evidencia de *por cuánto* falló, y CI lo publica como artefacto
    # para poder compararlo con la ejecución anterior sin repetir el entrenamiento.
    metrics: Dict[str, Any] = {
        "roc_auc": round(float(auc_score), 6),
        "roc_auc_ic95": intervalo,
        "delta_sobre_heuristico_ic95": intervalo_aporte,
        "f1": round(float(f1), 6),
        "accuracy": round(float(acc), 6),
        "brier": round(float(brier), 6),
        "auc_threshold": AUC_THRESHOLD,
        "min_delta_sobre_heuristico": MIN_DELTA_SOBRE_HEURISTICO,
        "passed_auc": bool(cumple_auc),
        "passed_delta": bool(cumple_delta),
        "passed": bool(cumple),
        # «Pasa» es superar los umbrales con la estimación puntual; «publicable» exige además
        # que el intervalo no los contradiga. Van por separado porque dicen cosas distintas:
        # con una docena de ejemplos de prueba un modelo pasa y no es publicable.
        "publicable": motivo_publicacion is None,
        "motivo_no_publicable": motivo_publicacion,
        "publicado": False,
        "lineas_base": comparacion,
        # Con qué vector se entrenó. El monitor de deriva y el dataset real descartan las
        # instantáneas de otra versión en vez de traducirlas inventando.
        "version_del_vector": VERSION_DEL_VECTOR,
        "origen_de_los_datos": origen,
        "huella_datos_sha256": huella_datos,
        "filas_totales": int(len(df)),
        "filas_entrenamiento": int(len(X_train)),
        "filas_prueba": int(len(X_test)),
        "procedencia": procedencia,
        # Encuadre de la cifra, guardado junto a ella para que no viaje sola. Un 0.94 sin
        # esta nota invita a leerse como rendimiento de negocio, y no lo es.
        "naturaleza_de_los_datos": naturaleza[origen],
        # Con qué bibliotecas se entrenó (R-2). El `.joblib` es un pickle de objetos de
        # scikit-learn: cargarlo con otra versión da un aviso y, entre versiones menores,
        # puede dar predicciones distintas sin error. La suite exige que el artefacto
        # versionado se haya entrenado con las versiones que fija el lock.
        "entorno": _entorno_de_entrenamiento(),
    }

    sufijo = "" if origen == "sinteticos" else f"_{origen}"
    metrics_path = os.path.join(models_dir, f"metrics{sufijo}.json")
    with open(metrics_path, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2, ensure_ascii=False)
    print(f"5. Métricas registradas en:\n   -> {metrics_path}")

    # Serialización del artefacto — solo si supera el umbral y si se pidió publicarlo.
    # El orden importa: si un cambio degrada el modelo, sobrescribir el .joblib dejaría al
    # backend sirviendo el modelo malo mientras CI apenas está pintando el fallo en rojo.
    # Un artefacto que no pasa el gate no llega a existir.
    if motivo_publicacion is not None:
        if publicar:
            print(
                f"\n[GATE ML] {motivo_publicacion}.\n"
                "          El artefacto NO se ha guardado; se conserva el modelo anterior.\n"
            )
        else:
            print(
                f"\n[MEDICION] No seria publicable: {motivo_publicacion}.\n"
                "           El artefacto y el perfil de referencia desplegados quedan intactos.\n"
            )
        _registrar(metrics, X_train, huella_datos, origen, procedencia, False, ruta_registro)
        return metrics

    if not publicar:
        print(
            "\n[MEDICION] El modelo supera los umbrales y su intervalo, pero no se publica: "
            "este entrenamiento\n"
            "           se pidio en modo medicion. El artefacto y el perfil de referencia\n"
            "           que hay desplegados quedan intactos.\n"
            "           Para publicarlo: anada --publicar.\n"
        )
        _registrar(metrics, X_train, huella_datos, origen, procedencia, False, ruta_registro)
        return metrics

    model_artifact_path = os.path.join(models_dir, "lead_scorer_model.joblib")
    joblib.dump(pipeline, model_artifact_path)
    print(f"6. Artefacto del modelo guardado exitosamente en:\n   -> {model_artifact_path}")

    # Huella del artefacto recién escrito. El backend puede exigirla mediante
    # `ML_MODEL_SHA256` y negarse a deserializar un fichero sustituido (A-10): joblib carga
    # con pickle, y pickle ejecuta código. Se añade a metrics.json para que quien despliega
    # tenga el valor a mano sin recalcularlo, y se imprime en claro para poder copiarlo.
    metrics["model_sha256"] = _sha256_de_fichero(model_artifact_path)
    metrics["publicado"] = True
    with open(metrics_path, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2, ensure_ascii=False)

    print(f"7. Huella SHA-256 del artefacto:\n   -> {metrics['model_sha256']}")
    print(f"   Fíjela en producción con:  ML_MODEL_SHA256={metrics['model_sha256']}\n")

    # Perfil de referencia para el monitoreo de deriva.
    # Se guarda el resumen de la distribución, no los datos: así el monitor puede correr
    # en producción sin llevar consigo el conjunto de entrenamiento, que en cuanto el
    # bucle de realimentación esté en marcha contendrá datos de clientes reales.
    #
    # Solo se reescribe al publicar. Un entrenamiento de medición que dejara aquí el perfil
    # de cuarenta filas cambiaría la referencia del monitor de deriva sin cambiar el modelo
    # desplegado: a partir de ahí el monitor compararía produccion contra un perfil que no
    # corresponde al artefacto que puntua, y sus PSI dejarian de significar lo que dicen.
    perfil = construir_perfil(X_train, FEATURE_COLS)
    # El vínculo con el artefacto. Hasta la Fase 13 el perfil y el `.joblib` salían del
    # mismo entrenamiento, pero nada lo dejaba escrito ni lo comprobaba: un perfil de una
    # ejecución y un modelo de otra —una imagen construida a medias, un `.joblib` copiado a
    # mano— hacían que el monitor comparase producción contra la población de otro modelo.
    # Con la huella dentro, el monitor se niega a evaluar si no corresponden.
    perfil["model_sha256"] = metrics["model_sha256"]
    perfil["huella_datos_sha256"] = huella_datos
    perfil["version_del_vector"] = VERSION_DEL_VECTOR
    perfil_path = os.path.join(models_dir, "reference_profile.json")
    with open(perfil_path, "w", encoding="utf-8") as fh:
        json.dump(perfil, fh, indent=2, ensure_ascii=False)
    print(f"8. Perfil de referencia para deriva:\n   -> {perfil_path}")

    entrada = _registrar(metrics, X_train, huella_datos, origen, procedencia, True, ruta_registro)
    print(f"9. Registrado en el histórico de modelos ({entrada['registrado_en']}).\n")
    return metrics


def _registrar(metrics, X_train, huella_datos, origen, procedencia, publicado, ruta):
    """
    Anota la ejecución en el registro de modelos, se haya publicado o no.

    Se registran también las que no publican. Un histórico que solo contiene los éxitos no
    permite ver que se lleva un mes midiendo el dataset real y el aporte no sube.
    """
    return registrar_modelo(
        metricas=metrics,
        filas_entrenamiento=int(len(X_train)),
        columnas=list(FEATURE_COLS),
        huella_datos=huella_datos,
        origen=origen,
        ruta=ruta,
        extra={
            "publicado": bool(publicado),
            "roc_auc_ic95": metrics.get("roc_auc_ic95"),
            "delta_sobre_heuristico_ic95": metrics.get("delta_sobre_heuristico_ic95"),
            "version_del_vector": metrics.get("version_del_vector"),
            "procedencia": procedencia,
            "entorno": metrics.get("entorno"),
        },
    )


def _entorno_de_entrenamiento() -> Dict[str, str]:
    """Versiones de lo que determina el contenido del artefacto."""
    import platform

    import sklearn

    return {
        "python": platform.python_version(),
        "scikit-learn": sklearn.__version__,
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "joblib": joblib.__version__,
    }


def train_lead_scoring_model() -> Dict[str, Any]:
    """Camino histórico: datos sintéticos, publicando si pasa los umbrales."""
    df, procedencia = cargar_sinteticos()
    return entrenar(df, origen="sinteticos", procedencia=procedencia, publicar=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--datos",
        choices=["sinteticos", "realimentacion"],
        default="sinteticos",
        help="Fuente de las etiquetas. `realimentacion` usa los desenlaces comerciales reales.",
    )
    parser.add_argument(
        "--dataset",
        default=os.path.join(current_dir, "..", "data", "leads_reales.csv"),
        help="CSV de realimentacion, generado por feedback_dataset.py.",
    )
    parser.add_argument(
        "--publicar",
        action="store_true",
        help=_PUBLICACION.strip().splitlines()[0],
    )
    args = parser.parse_args(argv)

    if args.datos == "sinteticos":
        df, procedencia = cargar_sinteticos()
        publicar = True
    else:
        df, procedencia = cargar_realimentacion(args.dataset)
        publicar = args.publicar

    resultado = entrenar(df, origen=args.datos, procedencia=procedencia, publicar=publicar)

    # Un código de salida distinto de cero es lo que convierte el umbral en un gate real.
    # Antes se imprimía "REVISAR" y el proceso terminaba en 0, así que una regresión del
    # modelo atravesaba CI sin que nadie la viera.
    #
    # Con datos de realimentación el criterio es otro: la ejecución sirve para medir, y un
    # aporte bajo sobre cuarenta ejemplos es un dato, no un fallo de proceso. Falla solo si
    # se pidió publicar y no se pudo.
    if args.datos == "realimentacion" and not args.publicar:
        return 0
    # «Pasó» ya no equivale a «se publicó»: un modelo puede superar los umbrales con la
    # estimación puntual y quedarse fuera por su intervalo. Lo que se pidió fue publicar.
    return 0 if resultado["publicado"] else 1


if __name__ == "__main__":
    sys.exit(main())
