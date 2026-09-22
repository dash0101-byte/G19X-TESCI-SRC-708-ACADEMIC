import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

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
