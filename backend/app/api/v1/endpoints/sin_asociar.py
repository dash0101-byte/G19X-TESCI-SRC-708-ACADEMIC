"""
Bandeja «Sin asociar»: avisos que llegaron sin prospecto, a la espera de una persona.

Un mensaje de WhatsApp de un número que no está en ninguna ficha, o una reunión de
Calendly con un correo desconocido. Quien dirige la cartera los vincula al prospecto que
corresponde —y entonces se registran como cualquier otra actividad y puntúan— o los
descarta.

La atienden `Sales_Lead` y `System_Admin`. Un asesor no: la bandeja enseña el correo y el
teléfono de personas que todavía no son cartera de nadie, y vincular es decidir de quién es
un dato, que es repartir.
"""
from app.core.audit import (
    ACCION_EVENTO_DESCARTAR,
    ACCION_EVENTO_VINCULAR,
    ENTIDAD_EVENTO_SIN_ASOCIAR,
    AsientoDeAuditoria,
    auditar,
)
from app.core.autorizacion import AlcanceDeCartera, alcance_actual
from app.core.database import get_db
from app.core.security import CurrentUser, UserRole, require_roles
from app.models.entities import UnmatchedEvent
from app.repositories.lead_repository import LeadRepository
from app.schemas.activity import ActividadRegistradaResponse
from app.schemas.sin_asociar import BandejaSinAsociarResponse, VinculacionRequest
from app.services.registro_de_actividad import EventoInvalido, vincular_evento_sin_asociar
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

router = APIRouter()

QUIEN_ATIENDE_LA_BANDEJA = [UserRole.SYSTEM_ADMIN, UserRole.SALES_LEAD]


def _no_encontrado(evento_id: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Evento sin asociar {evento_id} no encontrado.",
    )


@router.get("", response_model=BandejaSinAsociarResponse)
def listar_eventos_sin_asociar(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(QUIEN_ATIENDE_LA_BANDEJA)),
):
    """Lo más reciente primero."""
    consulta = db.query(UnmatchedEvent)
    total = consulta.count()
    items = (
        consulta.order_by(UnmatchedEvent.received_at.desc(), UnmatchedEvent.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return BandejaSinAsociarResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/{evento_id}/vincular", response_model=ActividadRegistradaResponse)
async def vincular_evento(
    evento_id: int,
    cuerpo: VinculacionRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(QUIEN_ATIENDE_LA_BANDEJA)),
    alcance: AlcanceDeCartera = Depends(alcance_actual),
    auditoria: AsientoDeAuditoria = Depends(auditar(ACCION_EVENTO_VINCULAR, ENTIDAD_EVENTO_SIN_ASOCIAR)),
):
    """
    Convierte el aviso en actividad del prospecto elegido y lo retira de la bandeja.

    La actividad conserva la fuente y la verificación de origen: un mensaje que confirmó
    WhatsApp sigue siendo verificado aunque lo haya vinculado una persona. Lo que decide la
    persona es a quién pertenece, no si ocurrió.
    """
    auditoria.anotar(entidad_id=evento_id)
    pendiente = db.get(UnmatchedEvent, evento_id)
    if pendiente is None:
        raise _no_encontrado(evento_id)
    lead = LeadRepository(db, alcance).get_by_id(cuerpo.lead_id)
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prospecto con ID {cuerpo.lead_id} no encontrado.",
        )

    fuente = pendiente.source
    tipo = pendiente.activity_type.value
    try:
        resultado = await vincular_evento_sin_asociar(db, pendiente, lead)
    except EventoInvalido as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.como_detalle()
        ) from exc

    # En el asiento, a qué prospecto y de qué fuente; nunca el correo o el teléfono del aviso.
    auditoria.anotar(
        lead_id=lead.id,
        fuente=fuente,
        tipo_de_actividad=tipo,
        actividad_id=resultado.actividad.id if resultado.actividad is not None else None,
    )
    return ActividadRegistradaResponse.desde_registro(resultado)


@router.delete("/{evento_id}", status_code=status.HTTP_204_NO_CONTENT)
def descartar_evento(
    evento_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(QUIEN_ATIENDE_LA_BANDEJA)),
    auditoria: AsientoDeAuditoria = Depends(auditar(ACCION_EVENTO_DESCARTAR, ENTIDAD_EVENTO_SIN_ASOCIAR)),
):
    """
    Borra el aviso. No queda nada de él salvo el asiento, que dice su fuente y su tipo.

    Si el sistema de origen lo reentrega, vuelve a la bandeja: descartar no es bloquear.
    """
    auditoria.anotar(entidad_id=evento_id)
    pendiente = db.get(UnmatchedEvent, evento_id)
    if pendiente is None:
        raise _no_encontrado(evento_id)
    auditoria.anotar(fuente=pendiente.source, tipo_de_actividad=pendiente.activity_type.value)
    db.delete(pendiente)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
