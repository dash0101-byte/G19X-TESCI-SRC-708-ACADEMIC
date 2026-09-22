"""
Consulta de la bitácora de auditoría. Solo `System_Admin`.

La restricción no es una formalidad. La bitácora concentra, en un solo sitio y ya
correlacionado, quién trabaja con qué cartera, desde qué direcciones se conecta cada
persona y a qué horas: es el resumen más útil que existe del comportamiento interno de la
empresa. Un `Sales_Lead` no la necesita para su trabajo, y dársela «porque es responsable
del equipo» convertiría la medida de control en una herramienta de vigilancia entre
compañeros.

Es de solo lectura por diseño: no hay endpoint que borre ni edite asientos. Una bitácora
que la aplicación puede reescribir no prueba nada, porque el primer objetivo de quien
abusa de sus permisos es precisamente el registro de que lo hizo. La retención se aplica
desde fuera, con las herramientas de la base de datos.
"""
import datetime
import logging
from typing import Optional

from app.core.audit import (
    ACCION_AUDITORIA_CONSULTA,
    ENTIDAD_AUDITORIA,
    AsientoDeAuditoria,
    auditar,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.security import CurrentUser, UserRole, require_roles
from app.models.entities import AuditLog
from app.schemas.audit import AuditPage
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=AuditPage)
def consultar_bitacora(
    actor_email: Optional[str] = Query(None, max_length=150, description="Filtra por la cuenta que actuó."),
    action: Optional[str] = Query(None, max_length=60, description="Filtra por acción (p. ej. 'lead.eliminar')."),
    entity: Optional[str] = Query(None, max_length=60, description="Filtra por tipo de entidad."),
    entity_id: Optional[str] = Query(None, max_length=64, description="Filtra por identificador de entidad."),
    outcome: Optional[str] = Query(None, max_length=20, description="Filtra por resultado ('OK', 'HTTP_403'...)."),
    desde: Optional[datetime.datetime] = Query(None, description="Solo asientos posteriores a este instante."),
    hasta: Optional[datetime.datetime] = Query(None, description="Solo asientos anteriores a este instante."),
    limit: int = Query(50, ge=1, description="Asientos por página."),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles([UserRole.SYSTEM_ADMIN])),
    auditoria: AsientoDeAuditoria = Depends(auditar(ACCION_AUDITORIA_CONSULTA, ENTIDAD_AUDITORIA)),
):
    """
    Devuelve asientos de la bitácora, del más reciente al más antiguo.

    Consultar la bitácora queda a su vez registrado en la bitácora. Es deliberado: el
    administrador es el único rol que puede leer aquí, y por tanto el único cuyo acceso
    nadie más vería si no quedara escrito.
    """
    # El tope se aplica por encima de lo que pida el cliente: sin él, un `limit` desmedido
    # sobre una tabla que crece con cada operación sería la forma más cómoda de tumbar la
    # API, y encima desde una cuenta autorizada.
    limite_efectivo = min(limit, settings.AUDIT_LOG_MAX_PAGE_SIZE)

    consulta = db.query(AuditLog)
    if actor_email:
        consulta = consulta.filter(AuditLog.actor_email == actor_email.strip().lower())
    if action:
        consulta = consulta.filter(AuditLog.action == action)
    if entity:
        consulta = consulta.filter(AuditLog.entity == entity)
    if entity_id:
        consulta = consulta.filter(AuditLog.entity_id == entity_id)
    if outcome:
        consulta = consulta.filter(AuditLog.outcome == outcome)
    if desde:
        consulta = consulta.filter(AuditLog.occurred_at >= desde)
    if hasta:
        consulta = consulta.filter(AuditLog.occurred_at <= hasta)

    total = consulta.count()
    items = (
        consulta.order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
        .offset(offset)
        .limit(limite_efectivo)
        .all()
    )

    auditoria.anotar(
        filtros={
            "actor_email": actor_email,
            "action": action,
            "entity": entity,
            "entity_id": entity_id,
            "outcome": outcome,
        },
        devueltos=len(items),
        total=total,
    )

    return AuditPage(total=total, limit=limite_efectivo, offset=offset, items=items)
