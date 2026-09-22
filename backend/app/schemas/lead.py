import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.telefono import TelefonoInvalido, normalizar_telefono
from app.models.entities import ActivityType, LeadStatus, QualificationStatus, ScoreCategory
from app.schemas.activity import ActivityResponse
from app.schemas.publicaciones import LlegoPor
from app.schemas.score import ScoreHistoryResponse

# Los límites replican el ancho de las columnas de `Lead` en `models/entities.py`.
# Sin ellos, un texto largo pasaba la validación y fallaba en el INSERT (PostgreSQL) o
# se guardaba entero rompiendo el contrato declarado del esquema (SQLite, que ignora
# el ancho de VARCHAR): en ambos casos, un 500 en vez de un 422 que señale el campo.
MAX_NAME = 100
MAX_EMAIL = 150
MAX_PHONE = 50
MAX_COMPANY = 150
MAX_JOB_TITLE = 100
MAX_INDUSTRY = 100
MAX_COMPANY_SIZE = 50
MAX_COUNTRY = 100
MAX_CITY = 100
MAX_SOURCE = 100
# `initial_notes` no es una columna: viaja dentro del JSON `activity_data`, con el mismo
# tope que las notas de cualquier actividad registrada a mano.
MAX_NOTES = 500


def _telefono_e164(valor: Optional[str]) -> Optional[str]:
    """
    Valida y normaliza al guardar. Se aplica a la entrada —alta y edición— y no a
    `LeadBase`: la respuesta hereda de ella, y un teléfono anterior a la Fase 15 que la
    migración no pudo normalizar convertiría la lectura de su ficha en un error.
    """
    try:
        return normalizar_telefono(valor)
    except TelefonoInvalido as exc:
        raise ValueError(str(exc)) from None


class LeadBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=MAX_NAME)
    last_name: str = Field(..., min_length=1, max_length=MAX_NAME)
    email: EmailStr = Field(..., max_length=MAX_EMAIL)
    phone: Optional[str] = Field(None, max_length=MAX_PHONE)
    company: Optional[str] = Field(None, max_length=MAX_COMPANY)
    job_title: Optional[str] = Field(None, max_length=MAX_JOB_TITLE)
    industry: Optional[str] = Field(None, max_length=MAX_INDUSTRY)
    # Sin valor por defecto: un tamaño que no se indicó no es «1-10».
    company_size: Optional[str] = Field(None, max_length=MAX_COMPANY_SIZE)
    # Tampoco aquí: unos ingresos que no se indicaron no son cero (capítulo 24).
    annual_revenue: Optional[float] = Field(None, ge=0.0)
    country: str = Field("México", max_length=MAX_COUNTRY)
    city: Optional[str] = Field(None, max_length=MAX_CITY)
    source: str = Field("Website", max_length=MAX_SOURCE)
    assigned_rep_id: Optional[int] = None
    campaign_id: Optional[int] = None
    raw_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class LeadCreate(LeadBase):
    initial_activity_type: Optional[ActivityType] = None
    initial_notes: Optional[str] = Field(None, max_length=MAX_NOTES)
    # El asesor que da de alta a la persona deja constancia de que aceptó el aviso de
    # privacidad. Se guarda cuándo y con fuente `manual`.
    privacy_notice_accepted: bool = False

    _phone = field_validator("phone")(_telefono_e164)


class LeadUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=MAX_NAME)
    last_name: Optional[str] = Field(None, min_length=1, max_length=MAX_NAME)
    email: Optional[EmailStr] = Field(None, max_length=MAX_EMAIL)
    phone: Optional[str] = Field(None, max_length=MAX_PHONE)
    company: Optional[str] = Field(None, max_length=MAX_COMPANY)
    job_title: Optional[str] = Field(None, max_length=MAX_JOB_TITLE)
    industry: Optional[str] = Field(None, max_length=MAX_INDUSTRY)
    company_size: Optional[str] = Field(None, max_length=MAX_COMPANY_SIZE)
    annual_revenue: Optional[float] = Field(None, ge=0.0)
    country: Optional[str] = Field(None, max_length=MAX_COUNTRY)
    city: Optional[str] = Field(None, max_length=MAX_CITY)
    source: Optional[str] = Field(None, max_length=MAX_SOURCE)
    status: Optional[LeadStatus] = None
    qualification_status: Optional[QualificationStatus] = None
    assigned_rep_id: Optional[int] = None
    raw_metadata: Optional[Dict[str, Any]] = None

    _phone = field_validator("phone")(_telefono_e164)


class LeadResponse(LeadBase):
    # Sin mínimo de longitud en la respuesta. Una ficha creada por el CRM o un formulario que
    # no mandó el nombre lo tiene vacío —antes era «Prospecto» / «Sin Apellido», inventado—,
    # y un mínimo heredado de la entrada convertiría el listado entero en un error.
    first_name: str = Field(..., max_length=MAX_NAME)
    last_name: str = Field(..., max_length=MAX_NAME)
    id: int
    status: LeadStatus
    qualification_status: QualificationStatus
    current_score: float
    score_category: ScoreCategory
    conversion_probability: float
    last_score_update: datetime.datetime
    last_activity_at: datetime.datetime
    privacy_notice_accepted_at: Optional[datetime.datetime] = None
    privacy_notice_source: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class LeadDetailResponse(LeadResponse):
    activities: List[ActivityResponse] = Field(default_factory=list)
    score_histories: List[ScoreHistoryResponse] = Field(default_factory=list)
    latest_explanation: Optional[Dict[str, Any]] = None
    # De qué publicación llegó esta persona. `None` cuando no llegó de ninguna: la ficha no
    # pinta la tarjeta en vez de enseñarla vacía, que sugeriría un dato perdido.
    llego_por: Optional[LlegoPor] = None


class LeadListResponse(BaseModel):
    """Respuesta paginada de la lista de prospectos con total para soporte de paginación en el frontend."""
    items: List[LeadResponse]
    total: int
    limit: int
    offset: int


class LeadListFilter(BaseModel):
    score_category: Optional[ScoreCategory] = None
    status: Optional[LeadStatus] = None
    industry: Optional[str] = Field(None, max_length=MAX_INDUSTRY)
    search: Optional[str] = Field(None, max_length=200)
    assigned_rep_id: Optional[int] = None
    min_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    max_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)
