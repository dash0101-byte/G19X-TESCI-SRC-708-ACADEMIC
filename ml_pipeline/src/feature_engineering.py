"""
Ingeniería de características del pipeline de entrenamiento.

Las reglas heurísticas del ICP ya no se definen aquí. Vivían duplicadas palabra por
palabra en `backend/app/core/scoring_rules.py`, y las dos copias habían empezado a
divergir: esta fijaba la vida media del decaimiento en 14 días mientras el backend la
leía de `settings`, así que recalibrar el sistema cambiaba la regla con la que se
evalúa a los prospectos pero no aquella con la que se entrenó el modelo.

Ahora se importan de ese módulo único y se reexportan para no romper a quien ya
llamaba `calculate_heuristic_score` desde el pipeline.
"""
import os
import sys

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# El backend no forma parte del contexto de build de su imagen Docker, de modo que la
# dependencia solo puede ir en esta dirección: el pipeline de entrenamiento —que se
# ejecuta desde la raíz del repositorio— alcanza el módulo de reglas del backend.
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.core.scoring_rules import (  # noqa: E402  (requiere el sys.path de arriba)
    DEFAULT_HALF_LIFE_DAYS,
    HeuristicParams,
    calculate_heuristic_score,
    calculate_temporal_decay,
)
from app.core.vector_del_modelo import (  # noqa: E402
    CATEGORICAS,
    NUMERICAS_COMPLETAS,
    NUMERICAS_CON_AUSENTES,
)

__all__ = [
    "DEFAULT_HALF_LIFE_DAYS",
    "HeuristicParams",
    "calculate_heuristic_score",
    "calculate_temporal_decay",
    "build_preprocessor",
]


def build_preprocessor() -> ColumnTransformer:
    """
    Construye un pipeline de preprocesamiento Scikit-Learn reproducible.

    Las columnas salen de `app.core.vector_del_modelo`, la misma lista que usa el adaptador
    de producción. Tenerlas escritas aquí otra vez es lo que permitió ML-4.

    Los ingresos anuales pasan por su propio tramo: se imputan con la mediana del
    entrenamiento y `add_indicator` añade una columna que vale 1 cuando faltaban. Sin ese
    indicador, un prospecto sin ingresos declarados sería indistinguible de uno que factura
    exactamente la mediana, y el modelo volvería a leer una cifra donde hay un hueco —solo
    que más verosímil que el 100 000 de antes—.
    """
    ingresos = Pipeline(
        steps=[
            ("imputar", SimpleImputer(strategy="median", add_indicator=True)),
            ("escalar", StandardScaler()),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAS),
            ("ingresos", ingresos, NUMERICAS_CON_AUSENTES),
            ("num", StandardScaler(), NUMERICAS_COMPLETAS),
        ]
    )
