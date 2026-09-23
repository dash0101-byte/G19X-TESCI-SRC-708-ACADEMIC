import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator

from app.models.entities import ActivityType, CallOutcome, MessageDirection, ScoreCategory


class ActivityCreate(BaseModel):
    """
    Lo que el asesor declara desde el panel.

    Ya no lleva `activity_weight` ni `activity_data` libre: el peso lo mandaba el cliente y
    el scoring nunca lo leyó, y los datos libres eran el sitio por el que un texto de
    mensaje acababa guardado. Las reglas que no caben en un tipo —la llamada necesita su
    resultado, el mensaje su dirección, la propuesta se registra cambiando la etapa— las
    aplica `registrar_evento`, igual que a cualquier otra fuente.
    """
    # Estrictamente el enum: un tipo desconocido es un 422 que lista los admitidos.
    activity_type: ActivityType = Field(..., description="Tipo de actividad del prospecto")
    call_outcome: Optional[CallOutcome] = Field(None, description="Resultado, solo en llamadas")
    direction: Optional[MessageDirection] = Field(None, description="Dirección, solo en mensajes")
    occurred_at: Optional[datetime.datetime] = Field(
        None, description="Cuándo ocurrió; por defecto, ahora. No puede estar en el futuro."
    )
    channel: Optional[str] = Field(None, max_length=50, description="Por defecto, el del tipo")
    notes: Optional[str] = Field(None, max_length=500, description="Nota del asesor; los mensajes no llevan")
    # Capítulo 28. `occurred_at` es cuándo se AGENDÓ la reunión y no puede estar en el
    # futuro; esto es cuándo ES, y por definición está en el futuro. Sin este dato el
    # recordatorio de la víspera no puede existir: recordar sobre la fecha en que se agendó
    # avisaría siempre tarde. Calendly ya lo manda con el mismo nombre.
    inicio_de_la_reunion: Optional[datetime.datetime] = Field(
        None, description="Cuándo es la reunión; solo en reuniones agendadas y siempre en el futuro."
    )

    @model_validator(mode="after")
    def _la_fecha_es_de_la_reunion(self) -> "ActivityCreate":
        if self.inicio_de_la_reunion is None:
            return self
        if self.activity_type != ActivityType.MEETING_SCHEDULED:
            raise ValueError(
                "«inicio_de_la_reunion» solo tiene sentido en una reunión agendada."
            )
        momento = self.inicio_de_la_reunion
        if momento.tzinfo is None:
            momento = momento.replace(tzinfo=datetime.timezone.utc)
        if momento <= datetime.datetime.now(datetime.timezone.utc):
            raise ValueError("La reunión tiene que ser en el futuro; una pasada no se recuerda.")
        return self


class ActivityResponse(BaseModel):
    id: int
    lead_id: int
    activity_type: ActivityType
    channel: str
    source: str
    external_event_id: Optional[str] = None
    verificada: bool
    direction: Optional[str] = None
    call_outcome: Optional[str] = None
    activity_data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    occurred_at: datetime.datetime
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class ActividadRegistradaResponse(ActivityResponse):
    """
    La actividad y lo que le hizo al score.

    El panel prometía «+25 pts» en el selector, un número que no era el que movía el score:
    la parte conductual tiene tope, decae con el tiempo y pesa el 40 % frente al modelo. La
    respuesta trae ahora el cambio real, calculado por el mismo recálculo que ya se hacía.
    """
    score_anterior: Optional[float] = None
    score: float
    score_category: ScoreCategory

    @classmethod
    def desde_registro(cls, resultado) -> "ActividadRegistradaResponse":
        """A partir de lo que devuelve `registrar_evento`."""
        base = ActivityResponse.model_validate(resultado.actividad).model_dump()
        return cls(
            **base,
            score_anterior=resultado.score_anterior,
            score=resultado.score,
            score_category=resultado.categoria,
        )
