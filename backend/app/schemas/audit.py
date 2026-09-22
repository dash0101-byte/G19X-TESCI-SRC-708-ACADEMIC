import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AuditEntry(BaseModel):
    """
    Un asiento de la bitácora tal y como se devuelve.

    El actor va desnormalizado —correo y rol tal como eran en ese momento— porque una
    bitácora que resolviera el nombre por clave foránea perdería la autoría en cuanto la
    cuenta se eliminara, justo en el caso en que más falta hace saber quién actuó.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: Optional[int] = None
    actor_email: Optional[str] = None
    actor_role: Optional[str] = None
    action: str
    entity: str
    entity_id: Optional[str] = None
    outcome: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    event_metadata: Optional[Dict[str, Any]] = None
    occurred_at: datetime.datetime


class AuditPage(BaseModel):
    """
    Página de asientos, de más reciente a más antiguo.

    Se devuelve `total` junto a los elementos para que quien consulte sepa si está viendo
    todo o solo el principio: una lista de 200 asientos sin ese dato no distingue «hubo
    200 accesos denegados» de «hubo 40 000 y estos son los últimos».
    """
    total: int = Field(description="Asientos que cumplen el filtro, antes de paginar.")
    limit: int
    offset: int
    items: List[AuditEntry]
