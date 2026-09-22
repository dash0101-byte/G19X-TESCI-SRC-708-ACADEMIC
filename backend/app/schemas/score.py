import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.entities import ScoreCategory


class RuleBreakdown(BaseModel):
    title_fit_score: float = 0.0
    industry_fit_score: float = 0.0
    company_size_fit_score: float = 0.0
    firmographic_total: float = 0.0
    behavior_raw_total: float = 0.0
    decay_factor: float = 1.0
    behavior_decayed_total: float = 0.0
    heuristic_total: float = 0.0


class AIExplanation(BaseModel):
    summary: str
    strengths: List[str] = Field(default_factory=list)
    recommended_action: str
    engine: str = "Local_Mock"
    model_deployment: Optional[str] = None


class ScoreResult(BaseModel):
    score: float = Field(..., ge=0.0, le=100.0, description="Puntaje final compuesto de 0 a 100")
    score_category: ScoreCategory = Field(..., description="Categoría asignada: HOT, WARM o COLD")
    conversion_probability: float = Field(..., ge=0.0, le=1.0, description="Probabilidad de conversión estimada")
    ml_probability: float = Field(..., description="Salida bruta del modelo de Machine Learning")
    heuristic_score: float = Field(..., description="Puntaje heurístico ponderado con decaimiento")
    decay_factor: float = Field(1.0, description="Factor de atenuación por tiempo de inactividad")
    rule_breakdown: Dict[str, Any] = Field(default_factory=dict)
    ai_explanation: Optional[AIExplanation] = None
    model_version: str = "v1.0.0-hybrid"


class ScoreHistoryResponse(BaseModel):
    id: int
    lead_id: int
    score: float
    score_category: ScoreCategory
    model_version: str
    ml_probability: float
    heuristic_score: float
    decay_factor: float
    rule_breakdown: Optional[Dict[str, Any]] = None
    ai_explanation: Optional[Dict[str, Any]] = None
    calculated_at: datetime.datetime

    model_config = {"from_attributes": True}


class ScorePredictRequest(BaseModel):
    """
    Entrada del simulador de scoring en tiempo real (`POST /api/v1/scoring/predict`).

    Debe declarar TODOS los campos que el heurístico sabe leer. Faltaban
    `proposal_sent`, `meeting_scheduled` y `urgency`, que el simulador ya enviaba: al no
    estar declarados, Pydantic los descartaba en silencio y las tres casillas
    correspondientes de la interfaz no movían el resultado ni un punto, pese a valer
    +25, +20 y +10 en la fórmula.

    Por eso `extra="forbid"`: es preferible un 422 que señale el campo desconocido a
    seguir aceptando peticiones cuyo efecto se pierde sin dejar rastro.
    """
    model_config = ConfigDict(extra="forbid")

    # --- Identificación (solo alimenta el texto explicativo, no la puntuación) ---
    first_name: Optional[str] = Field("Prospecto", max_length=100)
    last_name: Optional[str] = Field("Prueba", max_length=100)
    company: Optional[str] = Field("Empresa TI", max_length=150)

    # --- Firmográficos ---
    job_title: str = Field(..., max_length=100, examples=["CTO"])
    industry: str = Field(..., max_length=100, examples=["FinTech"])
    # Sin valor por defecto: un tamaño que no se envía es desconocido, no «51-200».
    company_size: Optional[str] = Field(None, max_length=50, examples=["51-200"])
    # Sin valor por defecto: el simulador debe poder probar un prospecto que no los declaró.
    annual_revenue: Optional[float] = Field(None, ge=0.0)
    source: Optional[str] = Field("Website", max_length=100)

    # --- Comportamiento digital ---
    # Lo que no se envía no ocurrió: cero y no un ejemplo. Antes, una petición sin estos
    # campos puntuaba cuatro visitas, dos aperturas, un clic, una descarga, un webinar y
    # una demo que nadie había declarado.
    page_views: int = Field(0, ge=0)
    email_opens: int = Field(0, ge=0)
    email_clicks: int = Field(0, ge=0)
    content_downloads: int = Field(0, ge=0)

    # --- Interacción comercial humana ---
    attended_webinar: bool = False
    requested_demo: bool = False
    proposal_sent: bool = Field(False, description="Propuesta o cotización enviada (+25 pts)")
    meeting_scheduled: bool = Field(False, description="Reunión comercial agendada (+20 pts)")
    # El resultado de la llamada es la variable (capítulo 24): solo las conectadas puntúan
    # en la regla; las sin respuesta llegan al modelo.
    phone_calls_connected: int = Field(0, ge=0)
    phone_calls_unanswered: int = Field(0, ge=0)
    whatsapp_messages: int = Field(0, ge=0)
    linkedin_messages: int = Field(0, ge=0)
    custom_events: int = Field(0, ge=0)

    # --- Atenuación temporal ---
    # Cero cuando no se envía. Solo atenúa el comportamiento, y el comportamiento que no se
    # envía también es cero: sin ninguno de los dos, el día no mueve la puntuación.
    days_since_last_activity: float = Field(0.0, ge=0.0)

    # --- Campos personalizados del formulario de captación ---
    # `urgency` sí puntúa (+10 / +5); los otros tres viajan a la explicación de la IA.
    urgency: Optional[str] = Field(None, max_length=50, examples=["INMEDIATA"])
    profiles_needed: Optional[str] = Field(None, max_length=200)
    budget_range: Optional[str] = Field(None, max_length=100)
    work_modality: Optional[str] = Field(None, max_length=50)
    custom_metadata: Optional[Dict[str, Any]] = None
