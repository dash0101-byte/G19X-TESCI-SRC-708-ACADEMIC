"""
La agenda del día: la bandeja «Hoy», la campana y los HOT que se enfrían (capítulo 28).

Cinco rutas, y el alcance de cada una dice para quién es:

* **la bandeja** es de quien pregunta; el líder puede pedir la de alguien de su cartera;
* **la campana** es siempre y solo la propia: un aviso tiene un destinatario, y leer los de
  otro no es una vista, es abrir su correo;
* **marcar hecha** la cierra su dueño, aunque el líder la vea. «Ya la hice» es una
  afirmación sobre el trabajo de una persona concreta;
* **los HOT que se enfrían** es de dirección, como la comparativa de publicaciones: un
  prospecto caliente enfriándose deja de ser trabajo de alguien para ser problema del
  equipo.

Ninguna crea nada. Quien decide qué hay que hacer es el motor, en la pasada diaria: una
pantalla que creara tareas al mirarla haría que «cuántas hay» dependiera de cuánta gente
hubiera entrado esa mañana.
"""
import logging
from typing import List, Optional

from app.core.agenda import ETIQUETAS_DE_ESTADO
from app.core.audit import ACCION_TAREA_HECHA, ENTIDAD_TAREA, AsientoDeAuditoria, auditar
from app.core.autorizacion import AlcanceDeCartera, alcance_actual
from app.core.database import get_db
from app.core.security import CurrentUser, UserRole, get_current_user, require_roles
from app.schemas.agenda import (
    AvisosLeidos,
    BandejaDeHoy,
    Campana,
    HotQueSeEnfrian,
    TareaCerrada,
)
from app.services import agenda_del_dia
from app.services.agenda_del_dia import TareaFueraDeAlcance
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter()

DIRECCION = [UserRole.SALES_LEAD, UserRole.SYSTEM_ADMIN]


def _no_encontrada(tarea_id: int) -> HTTPException:
    """
    Una tarea ajena responde exactamente igual que una que no existe.

    Es el mismo criterio que los prospectos (`endpoints/leads.py`): con un 403 para lo ajeno
    y un 404 para lo inexistente, recorrer identificadores diría cuánto trabajo tiene el
    resto del equipo sin llegar a ver ni una línea.
    """
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Tarea con ID {tarea_id} no encontrada.",
    )


@router.get("/hoy", response_model=BandejaDeHoy)
def bandeja_de_hoy(
    asesor_id: Optional[int] = Query(
        None, description="Solo para quien dirige la cartera: la bandeja de esa persona."
    ),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    alcance: AlcanceDeCartera = Depends(alcance_actual),
):
    """
    Lo que hay que hacer hoy, ordenado por score.

    Trae lo vencido y lo que vence hoy; lo de más adelante se cuenta y no se enseña. Saber
    que hay trabajo después tranquiliza; verlo hoy convierte la bandeja en otra lista larga
    que nadie termina.
    """
    try:
        return agenda_del_dia.bandeja_de_hoy(db, alcance, asesor_id=asesor_id)
    except TareaFueraDeAlcance as exc:
        logger.info(
            "Bandeja fuera de alcance: %s pidió la de %s.", current_user.email, asesor_id
        )
        raise _no_encontrada(exc.tarea_id) from exc


@router.post("/tareas/{tarea_id}/hecha", response_model=TareaCerrada)
def marcar_hecha(
    tarea_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    alcance: AlcanceDeCartera = Depends(alcance_actual),
    auditoria: AsientoDeAuditoria = Depends(auditar(ACCION_TAREA_HECHA, ENTIDAD_TAREA)),
):
    """
    Su dueño dice que ya la hizo.

    Lleva actor en la bitácora, a diferencia de lo que cierra el sistema solo: cerrar a mano
    es una afirmación de alguien sobre su propio trabajo, y tiene que poder atribuirse.
    """
    try:
        tarea = agenda_del_dia.marcar_hecha(db, alcance, tarea_id)
    except TareaFueraDeAlcance as exc:
        raise _no_encontrada(tarea_id) from exc

    auditoria.anotar(entidad_id=tarea.id, regla=tarea.regla, prospecto_id=tarea.lead_id)
    return TareaCerrada(id=tarea.id, estado=tarea.estado, cerrada_en=tarea.cerrada_en)


@router.get("/avisos", response_model=Campana)
def avisos(
    solo_sin_leer: bool = Query(False, description="Solo los que todavía no se han leído."),
    db: Session = Depends(get_db),
    alcance: AlcanceDeCartera = Depends(alcance_actual),
):
    """La campana: cuántos sin leer y los últimos. Siempre los propios, sea cual sea el rol."""
    return agenda_del_dia.campana(db, alcance, solo_sin_leer=solo_sin_leer)


@router.post("/avisos/leidos", response_model=AvisosLeidos)
def marcar_leidos(
    ids: Optional[List[int]] = Body(
        None, embed=True, description="Los avisos a marcar; sin lista, todos los propios."
    ),
    db: Session = Depends(get_db),
    alcance: AlcanceDeCartera = Depends(alcance_actual),
):
    """
    Marca avisos como leídos.

    Sin bitácora a propósito: leer un aviso propio es lo más parecido a mirar la pantalla, y
    anotarlo llenaría la bitácora de ruido que taparía lo que sí importa mirar. Lo que se
    hace con el prospecto después —abrir su ficha, llamarlo— sí queda anotado donde toca.
    """
    return AvisosLeidos(leidos=agenda_del_dia.marcar_leidos(db, alcance, ids))


@router.get("/enfriandose", response_model=HotQueSeEnfrian)
def hot_que_se_enfrian(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(DIRECCION)),
):
    """
    Los HOT desatendidos y con qué asesor están.

    La única vista del capítulo que cruza carteras. Usa la misma consulta que la regla que
    avisa, no una copia: si fueran dos, el líder acabaría viendo una lista distinta de la
    que generó los avisos que está recibiendo.
    """
    return agenda_del_dia.hot_que_se_enfrian(db)


@router.get("/estados", response_model=dict)
def estados_de_tarea():
    """Las etiquetas de los estados, para que el cliente no se las invente."""
    return ETIQUETAS_DE_ESTADO
