"""
Líneas base contra las que medir si el modelo aporta algo.

Un ROC-AUC alto no dice nada por sí solo: hay que saber contra qué compite. Este módulo
calcula tres referencias sobre el **mismo conjunto de prueba** que el clasificador:

1. **Azar.** Un ROC-AUC de 0.50 por definición. Es el suelo absoluto.
2. **Regla trivial.** Ordenar por una sola variable —la más informativa que haya— sin
   modelo ninguno. Responde a «¿hacía falta machine learning o bastaba con ordenar por
   `requested_demo`?».
3. **Heurístico ICP.** El mismo cálculo de reglas que ya ejecuta el backend, sin ninguna
   componente aprendida. Es la línea base que de verdad importa, porque es lo que el
   sistema haría si se retirase el modelo: el delta entre esta y el clasificador es lo
   único que el machine learning está aportando.

La comparación es especialmente pertinente en este proyecto porque el dataset es sintético
y su etiqueta se genera con una fórmula parecida a la del heurístico. Es previsible que el
delta sea modesto, y decirlo es más defendible que exhibir un 0.94 aislado.
"""
import os
import sys
from typing import Dict

import pandas as pd
from sklearn.metrics import roc_auc_score

# El heurístico vive en el backend (fuente única de verdad, compartida con la API).
_AQUI = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.abspath(os.path.join(_AQUI, "..", "..", "backend"))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.core.scoring_rules import calculate_heuristic_score  # noqa: E402


def puntuar_con_heuristico(X: pd.DataFrame) -> pd.Series:
    """
    Aplica el heurístico ICP fila a fila y devuelve la puntuación 0-100.

    Se invoca la MISMA función que usa el servicio de scoring en producción, no una
    reimplementación: si divergieran, la comparación mediría dos cosas distintas y el
    delta que se publique no significaría nada.
    """
    puntuaciones = []
    for fila in X.itertuples(index=False):
        score, _, _ = calculate_heuristic_score(
            # Lo que falta llega vacío y la regla lo trata como desconocido, igual que en
            # producción; rellenarlo con «1-10» aquí mediría otra regla.
            job_title=str(getattr(fila, "job_title", "") or ""),
            industry=str(getattr(fila, "industry", "") or ""),
            company_size=str(getattr(fila, "company_size", "") or ""),
            page_views=int(getattr(fila, "page_views", 0) or 0),
            email_opens=int(getattr(fila, "email_opens", 0) or 0),
            email_clicks=int(getattr(fila, "email_clicks", 0) or 0),
            downloads=int(getattr(fila, "content_downloads", 0) or 0),
            requested_demo=bool(getattr(fila, "requested_demo", 0)),
            attended_webinar=bool(getattr(fila, "attended_webinar", 0)),
            days_inactive=float(getattr(fila, "days_since_last_activity", 0.0) or 0.0),
            proposal_sent=bool(getattr(fila, "proposal_sent", 0)),
            meeting_scheduled=bool(getattr(fila, "meeting_scheduled", 0)),
            # Como en producción: la regla puntúa las llamadas que conectaron y suma los dos
            # canales de mensaje bajo el mismo tope.
            phone_calls=int(getattr(fila, "phone_calls_connected", 0) or 0),
            whatsapp_messages=int(getattr(fila, "whatsapp_messages", 0) or 0),
            linkedin_messages=int(getattr(fila, "linkedin_messages", 0) or 0),
        )
        puntuaciones.append(score)
    return pd.Series(puntuaciones, index=X.index)


def mejor_regla_trivial(X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
    """
    Busca la variable numérica que mejor ordena por sí sola y devuelve su ROC-AUC.

    No es un modelo: es «ordenar la lista por una columna». Si el clasificador no supera
    esto con holgura, no está justificando su complejidad ni el coste de mantenerlo.
    """
    mejor_nombre, mejor_auc = "", 0.5
    for columna in X.select_dtypes(include=["number"]).columns:
        valores = X[columna]
        if valores.isna().any():
            # Los ingresos pueden faltar (vector 2). Una regla trivial no sabe qué hacer con
            # un hueco, así que ordena los ausentes en la mediana: es lo más parecido a «no
            # sé» que admite una ordenación.
            valores = valores.fillna(valores.median())
        if valores.nunique() < 2:
            continue
        auc = roc_auc_score(y, valores)
        # Una variable que ordena al revés es igual de informativa: se mide la separación,
        # no el sentido. `days_since_last_activity` es el caso evidente —a más inactividad,
        # menos conversión— y sin esto aparecería como inútil.
        auc = max(auc, 1.0 - auc)
        if auc > mejor_auc:
            mejor_nombre, mejor_auc = columna, auc
    return {"variable": mejor_nombre, "roc_auc": round(float(mejor_auc), 6)}


def comparar_contra_lineas_base(
    X_test: pd.DataFrame, y_test: pd.Series, probabilidades_modelo, puntuaciones_heuristico=None
) -> Dict[str, object]:
    """
    Calcula las tres referencias y el delta del modelo sobre la más exigente.

    `puntuaciones_heuristico` evita recalcular el heurístico cuando quien llama ya las tiene:
    el intervalo del aporte las necesita, y tienen que ser exactamente las mismas.
    """
    if puntuaciones_heuristico is None:
        puntuaciones_heuristico = puntuar_con_heuristico(X_test)
    auc_modelo = float(roc_auc_score(y_test, probabilidades_modelo))
    auc_heuristico = float(roc_auc_score(y_test, puntuaciones_heuristico))
    trivial = mejor_regla_trivial(X_test, y_test)

    return {
        "azar": 0.5,
        "regla_trivial": trivial,
        "heuristico_icp": round(auc_heuristico, 6),
        "modelo": round(auc_modelo, 6),
        "delta_sobre_heuristico": round(auc_modelo - auc_heuristico, 6),
        "delta_sobre_regla_trivial": round(auc_modelo - trivial["roc_auc"], 6),
    }


def formatear_comparacion(resultado: Dict[str, object]) -> str:
    """Rinde la comparación como tabla de texto para el log de entrenamiento y para CI."""
    trivial = resultado["regla_trivial"]
    lineas = [
        "",
        "-" * 68,
        "COMPARACIÓN CONTRA LÍNEAS BASE (mismo conjunto de prueba)",
        "-" * 68,
        f"  {'Azar':<34} ROC-AUC = 0.5000",
        f"  {'Regla trivial (' + str(trivial['variable'])[:16] + ')':<34} "
        f"ROC-AUC = {trivial['roc_auc']:.4f}",
        f"  {'Heurístico ICP (sin modelo)':<34} ROC-AUC = {resultado['heuristico_icp']:.4f}",
        f"  {'Modelo entrenado':<34} ROC-AUC = {resultado['modelo']:.4f}",
        "-" * 68,
        f"  Aporte del modelo sobre el heurístico: {resultado['delta_sobre_heuristico']:+.4f}",
        "-" * 68,
        "  Estas cifras se calculan sobre datos SINTÉTICOS cuya etiqueta se genera con una",
        "  fórmula conocida. Miden que el pipeline está íntegro —que las variables llegan y",
        "  el preprocesado no las corrompe—, NO el rendimiento esperable en producción.",
        "-" * 68,
    ]
    return "\n".join(lineas)
