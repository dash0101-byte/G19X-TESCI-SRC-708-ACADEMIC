import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.entities import ActivityType


class EventoSinAsociarResponse(BaseModel):
    id: int
    source: str
    activity_type: ActivityType
    channel: str
    direction: Optional[str] = None
    call_outcome: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_name: Optional[str] = None
    occurred_at: datetime.datetime
    received_at: datetime.datetime

    model_config = {"from_attributes": True}


class BandejaSinAsociarResponse(BaseModel):
    items: List[EventoSinAsociarResponse]
    total: int
    limit: int
    offset: int


class VinculacionRequest(BaseModel):
    lead_id: int = Field(..., ge=1, description="Prospecto al que pertenece el aviso")
