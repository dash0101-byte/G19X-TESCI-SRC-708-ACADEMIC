"""
Lo que dicen los cierres: las opciones del formulario y el panel del líder (capítulo 30).

Dos rutas, y el alcance de cada una dice para quién es:

* **las opciones** las ve cualquiera que haya iniciado sesión. Son las listas cerradas de
  motivos y tramos, sin un solo dato de nadie, y quien va a cerrar un prospecto es quien
  lo atiende. Servirlas desde el servidor —en lugar de que el cliente las lleve escritas—
  es lo que impide que añadir un motivo exija tocar dos sitios y que olvidarse de uno no
  rompa nada, que es como el panel acabaría sin ver esa opción;
* **el panel** es de dirección, como la comparativa de publicaciones y por la misma razón:
  los cierres de un solo asesor comparados entre publicaciones dan un orden que no es el
  real, y un número de negocio mal calculado hace más daño que no publicarlo.

**Cerrar no se hace aquí.** El cierre vive en `POST /leads/{id}/desenlace`, junto al resto
de lo que se le hace a un prospecto, porque necesita el alcance de cartera —un asesor cierra
los suyos— y ese alcance se resuelve en el repositorio de prospectos. Aquí solo se lee.

Ninguna de las dos rutas reentrena nada, genera ningún CSV ni toca el artefacto del modelo.
El contador que devuelve el panel dice cuánto falta; quien decide es una persona.
"""
import datetime
import logging
from typing import Optional

from app.core.audit import (
    ACCION_DESENLACE_PANEL,
    ENTIDAD_DESENLACE,
    AsientoDeAuditoria,
    auditar,
)
from app.core.database import get_db
from app.core.security import CurrentUser, UserRole, get_current_user, require_roles
from app.schemas.desenlaces import OpcionesDeCierre, PanelDeDesenlaces
from app.services import desenlaces as servicio
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter()

DIRECCION = [UserRole.SALES_LEAD, UserRole.SYSTEM_ADMIN]


@router.get("/opciones", response_model=OpcionesDeCierre)
def opciones_de_cierre(current_user: CurrentUser = Depends(get_current_user)):
    """Los motivos de cada desenlace y los tramos del acuerdo. Nada de texto libre."""
    return servicio.opciones()


@router.get("/panel", response_model=PanelDeDesenlaces)
def panel_de_desenlaces(
    desde: Optional[datetime.date] = Query(None, description="Primer día de cierre incluido."),
    hasta: Optional[datetime.date] = Query(None, description="Último día de cierre incluido."),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(DIRECCION)),
    auditoria: AsientoDeAuditoria = Depends(auditar(ACCION_DESENLACE_PANEL, ENTIDAD_DESENLACE)),
):
    """
    Ganados y perdidos por motivo, por publicación, por red y por el score que tenían.

    El periodo acota los cierres, **no** el contador del reentrenamiento: ese cuenta todo
    lo que hay, porque el modelo se entrena con todo lo que hay. Son dos preguntas y por eso
    llevan dos alcances; mezclarlas haría que filtrar un trimestre dijera que faltan ciento
    noventa ejemplos cuando en la base hay trescientos.
    """
    if desde is not None and hasta is not None and desde > hasta:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El primer día del periodo es posterior al último.",
        )

    resultado = servicio.panel(db, desde=desde, hasta=hasta)
    # Cuántos, con qué filtros; nunca quiénes. Es lo mismo que anota la comparativa de
    # publicaciones, y por lo mismo: la bitácora cuenta accesos, no los reproduce.
    auditoria.anotar(
        desde=desde.isoformat() if desde else None,
        hasta=hasta.isoformat() if hasta else None,
        cerrados=resultado.resumen.cerrados,
    )
    return resultado
