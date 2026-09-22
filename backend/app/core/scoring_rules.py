"""
Reglas de puntuación heurística del Ideal Customer Profile (ICP) de PluriOne.

Única fuente de verdad del heurístico. Antes vivía duplicado literalmente en
`ScoringService.compute_heuristic_score` y en `ml_pipeline/src/feature_engineering.py`:
dos copias que había que editar a la vez y que ya habían divergido en un punto
importante —la del servicio leía la vida media de `settings`, la del pipeline la
tenía fijada a 14.0—, de modo que recalibrar el sistema por configuración movía la
regla con la que se evaluaba a los prospectos pero no la regla con la que se había
entrenado el modelo.

El módulo es deliberadamente puro: no importa `settings` ni SQLAlchemy al cargarse,
para que el pipeline de entrenamiento pueda reutilizarlo sin arrastrar la
configuración del servicio web. `HeuristicParams.from_settings()` construye el
puente cuando la llamada viene del backend.
"""
import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

# Vida media de interés por defecto, en días. El backend la sobrescribe con
# `settings.DECAY_HALF_LIFE_DAYS`; el pipeline de entrenamiento usa este valor.
DEFAULT_HALF_LIFE_DAYS = 14.0

# Topes de cada bloque de la fórmula. Se exponen como constantes porque las pruebas
# de límites y la documentación del algoritmo se refieren a ellos por nombre.
MAX_TITLE_POINTS = 25.0
MAX_INDUSTRY_POINTS = 15.0
MAX_SIZE_POINTS = 10.0
MAX_BEHAVIOR_POINTS = 50.0
MAX_TOTAL_POINTS = 100.0


@dataclass(frozen=True)
class HeuristicParams:
    """
    Parámetros calibrables del algoritmo híbrido.

    Los pesos y umbrales viajan juntos porque cambiar uno sin el otro produce
    resultados incoherentes: subir `hot_threshold` sin revisar los pesos, por
    ejemplo, vacía la categoría HOT sin que ninguna regla lo advierta.
    """
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS
    weight_ml: float = 0.60
    weight_heuristic: float = 0.40
    hot_threshold: float = 75.0
    warm_threshold: float = 45.0

    @classmethod
    def from_settings(cls, settings_obj: Any = None) -> "HeuristicParams":
        """
        Deriva los parámetros de la configuración del backend.

        El import es diferido a propósito: así `ml_pipeline` puede importar este
        módulo sin necesitar `pydantic-settings` ni un `.env` presente.
        """
        if settings_obj is None:
            from app.core.config import settings as settings_obj

        return cls(
            half_life_days=float(settings_obj.DECAY_HALF_LIFE_DAYS),
            weight_ml=float(settings_obj.SCORE_WEIGHT_ML),
            weight_heuristic=float(settings_obj.SCORE_WEIGHT_HEURISTIC),
            hot_threshold=float(settings_obj.HOT_THRESHOLD),
            warm_threshold=float(settings_obj.WARM_THRESHOLD),
        )


DEFAULT_PARAMS = HeuristicParams()


# ============================================================================
# Tablas de reglas firmográficas
# ============================================================================
# El orden importa: se aplica la primera coincidencia, de mayor a menor puntuación.
# "DIRECTOR DE TECNOLOGÍA" debe evaluarse antes que "DIRECTOR" para que un CTO no
# caiga en el tramo de 20 puntos.

TITLE_RULES: Tuple[Tuple[float, Sequence[str]], ...] = (
    (25.0, ("CTO", "CIO", "CHIEF", "VP", "VICEPRESIDENTE", "DIRECTOR DE TECNOLOGÍA",
            "DIRECTOR GENERAL", "CEO", "FOUNDER", "CO-FOUNDER")),
    (20.0, ("DIRECTOR", "HEAD OF", "GERENTE DE TALENTO", "HEAD OF TALENT",
            "TALENT ACQUISITION", "RECLUTAMIENTO", "GERENTE SENIOR", "PEOPLE")),
    (14.0, ("GERENTE", "MANAGER", "LÍDER", "LEAD", "SCRUM", "PRODUCT")),
    (10.0, ("DESARROLLADOR", "DEVELOPER", "INGENIERO", "ENGINEER", "PROGRAMADOR",
            "ARQUITECTO", "DEVOPS", "DATA")),
    # Perfiles fuera de la toma de decisiones TI/staffing: se quedan en la base.
    (5.0, ("PSICÓLOGO", "PSICOLOGO", "DOCENTE", "PROFESOR", "ESTUDIANTE",
           "BECARIO", "ALUMNO", "PRACTICANTE")),
    (7.0, ("CONSULTOR", "ANALISTA", "ASISTENTE", "COORDINADOR")),
)
DEFAULT_TITLE_POINTS = 5.0  # Base neutral para cargos no listados

INDUSTRY_RULES: Tuple[Tuple[float, Sequence[str]], ...] = (
    (15.0, ("FINTECH", "SOFTWARE", "TI", "TECNOLOGÍA", "BANKING", "BANCA",
            "TELECOM", "CIBERSEGURIDAD", "AI", "INTELIGENCIA ARTIFICIAL")),
    (11.0, ("E-COMMERCE", "HEALTHCARE", "SALUD", "LOGISTICS", "LOGÍSTICA",
            "RETAIL", "AUTOMOTRIZ", "ENERGÍA")),
    (8.0, ("CONSULTING", "CONSULTORÍA", "MANUFACTURA", "SEGUROS", "MEDIOS", "SERVICIOS")),
    (6.0, ("EDUCACIÓN", "EDUCACION", "UNIVERSIDAD", "ESCUELA", "INSTITUTO",
           "GOBIERNO", "PÚBLICO", "ONG")),
)
DEFAULT_INDUSTRY_POINTS = 7.0  # Base neutral y justa para industrias de entrada libre

# El tamaño llega como texto libre desde el CRM: se compara por igualdad exacta
# contra las etiquetas que emiten el formulario y las plataformas integradas.
SIZE_POINTS: Dict[str, float] = {
    "1000+": 10.0,
    "1000 o más": 10.0,
    "201-1000": 8.0,
    "501-1000": 8.0,
    "201-500": 8.0,
    "51-200": 5.0,
    "11-50": 3.0,
    "1-10": 2.0,
}
# Una etiqueta de tamaño que no es ninguna de las anteriores no dice cuántas personas hay:
# se trata igual que un tamaño que falta (véase `_desconocido`).
DEFAULT_SIZE_POINTS = 2.0  # Solo el tramo «1-10»; se conserva el nombre por compatibilidad.


def _punto_medio(rules: Sequence[float]) -> float:
    return (min(rules) + max(rules)) / 2.0


# ============================================================================
# Lo que no se sabe
# ============================================================================
# Hasta el capítulo 25, un tamaño que no llegaba se leía como «1-10» —el tramo más bajo— y
# un cargo que no llegaba recibía la base de los cargos no listados, la misma que un
# estudiante. Las dos cosas son suponer: un hueco no es una empresa pequeña ni alguien sin
# poder de decisión. Lo que falta puntúa en el punto medio de su bloque —ni el mejor ni el
# peor tramo—, calculado desde las propias tablas para que no se desalinee si cambian.
#
# «Falta» es `None`, cadena vacía o solo espacios. Un cargo o un sector escritos que no
# coinciden con ninguna regla sí son un dato —la persona dijo a qué se dedica— y conservan
# su base; un tamaño escrito que no es ninguna etiqueta conocida no lo es, y cuenta como
# desconocido.
UNKNOWN_TITLE_POINTS = _punto_medio([p for p, _ in TITLE_RULES] + [DEFAULT_TITLE_POINTS])
UNKNOWN_INDUSTRY_POINTS = _punto_medio([p for p, _ in INDUSTRY_RULES] + [DEFAULT_INDUSTRY_POINTS])
UNKNOWN_SIZE_POINTS = _punto_medio(list(SIZE_POINTS.values()))


def _desconocido(valor: Optional[str]) -> bool:
    return valor is None or not str(valor).strip()

# Señales de urgencia declaradas en los campos personalizados del formulario.
URGENCY_HIGH_KEYWORDS = ("INMEDIATA", "IMMEDIATE", "ALTA", "URGENTE", "<15")
URGENCY_HIGH_POINTS = 10.0
URGENCY_MEDIUM_KEYWORDS = ("MEDIA", "1-3", "1 A 3")
URGENCY_MEDIUM_POINTS = 5.0


def _match_points(text: str, rules: Tuple[Tuple[float, Sequence[str]], ...], default: float) -> float:
    """Devuelve la puntuación de la primera regla cuyo texto aparezca en `text`."""
    upper = (text or "").upper()
    for points, keywords in rules:
        if any(keyword in upper for keyword in keywords):
            return points
    return default


def calculate_temporal_decay(
    days_inactive: float,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
) -> float:
    """
    Calcula el factor de atenuación exponencial continuo gamma(Δt) = (0.5)^(Δt / vida_media).

    Retorna un valor en (0.0, 1.0]. Un prospecto activo hoy no sufre atenuación.
    """
    if days_inactive <= 0:
        return 1.0
    return float(math.pow(0.5, days_inactive / half_life_days))


def calculate_heuristic_score(
    job_title: Optional[str],
    industry: Optional[str],
    company_size: Optional[str],
    page_views: int = 0,
    email_opens: int = 0,
    email_clicks: int = 0,
    downloads: int = 0,
    requested_demo: bool = False,
    attended_webinar: bool = False,
    days_inactive: float = 0.0,
    proposal_sent: bool = False,
    meeting_scheduled: bool = False,
    phone_calls: int = 0,
    whatsapp_messages: int = 0,
    custom_events: int = 0,
    custom_metadata: Optional[Dict[str, Any]] = None,
    params: HeuristicParams = DEFAULT_PARAMS,
    linkedin_messages: int = 0,
) -> Tuple[float, Dict[str, float], float]:
    """
    Calcula la puntuación heurística ICP con atenuación temporal sobre la parte conductual.

    Retorna `(score_heurístico, desglose_de_reglas, factor_de_decaimiento)`.

    El decaimiento se aplica solo al comportamiento: los datos firmográficos —cargo,
    industria, tamaño— no envejecen porque un CTO de FinTech sigue siéndolo aunque
    lleve un mes sin abrir un correo.

    Ninguna variable supone un valor cuando falta. Los firmográficos que faltan puntúan en
    el punto medio de su bloque (`UNKNOWN_*_POINTS`). Los recuentos y las marcas de
    comportamiento valen cero cuando no hay evento, que no es una suposición: es lo que el
    registro dice que pasó. La urgencia que no se declaró no suma, y los días sin actividad
    solo atenúan comportamiento, así que sin comportamiento no mueven nada.
    """
    # 1. Ajuste de cargo / nivel de decisión (máx. 25 pts)
    title_pts = (
        UNKNOWN_TITLE_POINTS if _desconocido(job_title)
        else _match_points(job_title, TITLE_RULES, DEFAULT_TITLE_POINTS)
    )

    # 2. Ajuste de industria (máx. 15 pts) — admite entrada libre
    ind_pts = (
        UNKNOWN_INDUSTRY_POINTS if _desconocido(industry)
        else _match_points(industry, INDUSTRY_RULES, DEFAULT_INDUSTRY_POINTS)
    )

    # 3. Ajuste de tamaño de empresa (máx. 10 pts). Sin tamaño, desconocido; nunca «1-10».
    size_pts = UNKNOWN_SIZE_POINTS
    if not _desconocido(company_size):
        size_pts = SIZE_POINTS.get(str(company_size).strip(), UNKNOWN_SIZE_POINTS)

    firmographic_subtotal = title_pts + ind_pts + size_pts

    # 4. Comportamiento digital y comercial (máx. 50 pts tras el tope)
    behavior_raw = 0.0
    if requested_demo:
        behavior_raw += 25.0
    if proposal_sent:
        behavior_raw += 25.0
    if meeting_scheduled:
        behavior_raw += 20.0
    if attended_webinar:
        behavior_raw += 15.0
    behavior_raw += min(16.0, phone_calls * 8.0)
    # WhatsApp y LinkedIn son dos variables del modelo desde el capítulo 24, pero la regla
    # los sigue sumando bajo el mismo tope: separar los canales no puede cambiar lo que la
    # mitad heurística del score ya decía de cada prospecto.
    behavior_raw += min(10.0, (whatsapp_messages + linkedin_messages) * 5.0)
    behavior_raw += min(10.0, custom_events * 5.0)
    behavior_raw += min(10.0, downloads * 5.0)
    behavior_raw += min(8.0, email_clicks * 3.0)
    behavior_raw += min(5.0, email_opens * 1.0)
    behavior_raw += min(5.0, page_views * 0.5)

    # Urgencia declarada en los campos personalizados del formulario
    if custom_metadata:
        urgency = str(custom_metadata.get("urgency", "")).upper()
        if any(u in urgency for u in URGENCY_HIGH_KEYWORDS):
            behavior_raw += URGENCY_HIGH_POINTS
        elif any(u in urgency for u in URGENCY_MEDIUM_KEYWORDS):
            behavior_raw += URGENCY_MEDIUM_POINTS

    behavior_subtotal = min(MAX_BEHAVIOR_POINTS, behavior_raw)

    # 5. Decaimiento temporal sobre la fracción conductual
    decay = calculate_temporal_decay(days_inactive, half_life_days=params.half_life_days)
    decayed_behavior = behavior_subtotal * decay

    heuristic_total = min(MAX_TOTAL_POINTS, firmographic_subtotal + decayed_behavior)

    breakdown = {
        "title_fit_score": title_pts,
        "industry_fit_score": ind_pts,
        "company_size_fit_score": size_pts,
        "firmographic_total": firmographic_subtotal,
        "behavior_raw_total": behavior_subtotal,
        "decay_factor": round(decay, 4),
        "behavior_decayed_total": round(decayed_behavior, 2),
        "heuristic_total": round(heuristic_total, 2),
    }

    return round(heuristic_total, 2), breakdown, round(decay, 4)


def combine_scores(
    ml_probability: float,
    heuristic_score: float,
    params: HeuristicParams = DEFAULT_PARAMS,
) -> float:
    """
    Funde la salida del modelo (probabilidad 0–1) con el heurístico (0–100).

    `settings` garantiza que los pesos suman 1.0, así que el resultado ya vive en la
    escala 0–100; el recorte final solo cubre el redondeo en coma flotante.
    """
    ml_score = ml_probability * 100.0
    fused = (params.weight_ml * ml_score) + (params.weight_heuristic * heuristic_score)
    return round(min(MAX_TOTAL_POINTS, max(0.0, fused)), 1)


def categorize(score: float, params: HeuristicParams = DEFAULT_PARAMS) -> str:
    """Clasifica un score en HOT / WARM / COLD según los umbrales configurados."""
    if score >= params.hot_threshold:
        return "HOT"
    if score >= params.warm_threshold:
        return "WARM"
    return "COLD"
