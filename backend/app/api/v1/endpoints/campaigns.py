"""
Gestión de campañas de captación. Lectura para todo el mundo, escritura para `Sales_Lead`.

Las campañas existían en el modelo desde el principio y solo podían crearse sembrando la
base: el informe de rendimiento por campaña estaba, pero no había forma de dar de alta la
campaña cuyo rendimiento se quería medir. Aquí se cierra ese hueco.

El reparto de permisos no es el mismo que en las cuentas, y es a propósito: una campaña es
una decisión comercial, no de sistemas. Quien dirige la cartera la crea y la ajusta; el
administrador de TI puede hacerlo también, porque puede hacerlo todo, pero no es su
trabajo. Un asesor las lee —necesita saber de dónde vino un prospecto— y no las toca: el
presupuesto de una campaña es información de dirección.

Como en las cuentas, no hay borrado: una campaña se desactiva. Borrarla pondría a NULL la
campaña de todos los prospectos que atrajo y se llevaría por delante la atribución de la
inversión, que es justo el número por el que existe la tabla.
"""
import logging
from typing import Optional

from app.core.audit import (
    ACCION_CAMPANA_ACTUALIZAR,
    ACCION_CAMPANA_CREAR,
    ACCION_CAMPANA_DESACTIVAR,
    ACCION_CAMPANA_DUPLICAR,
    ENTIDAD_CAMPANA,
    AsientoDeAuditoria,
    auditar,
)
from app.core.database import get_db
from app.core.publicaciones import ACTIVA, CERRADA, PAUSADA
from app.core.security import CurrentUser, UserRole, get_current_user, require_roles
from app.models.entities import Campaign, Lead
from app.schemas.user import (
    CampanaCreate,
    CampanaResponse,
    CampanaUpdate,
    ListaDeCampanas,
)
from app.services import ciclo_de_publicaciones as ciclo
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter()

GESTORES = [UserRole.SALES_LEAD, UserRole.SYSTEM_ADMIN]


def _buscar(db: Session, campaign_id: int) -> Campaign:
    campana = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if campana is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe la campaña {campaign_id}.",
        )
    return campana


def _validar_fechas(inicio, fin) -> None:
    if inicio is not None and fin is not None and fin < inicio:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La fecha de fin no puede ser anterior a la de inicio.",
        )


@router.get("", response_model=ListaDeCampanas)
def listar_campanas(
    incluir_inactivas: bool = Query(False),
    canal: Optional[str] = Query(None, max_length=100),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Campañas de captación. Cualquier rol autenticado puede leerlas.

    No se acotan por cartera. Una campaña no pertenece a nadie: es el canal por el que
    entró un prospecto, y un asesor necesita poder nombrarlo para entender su propio
    trabajo.
    """
    # Antes de contar: una publicación vencida se enseña ya cerrada.
    ciclo.cerrar_vencidas(db)
    consulta = db.query(Campaign)
    if not incluir_inactivas:
        consulta = consulta.filter(Campaign.is_active.is_(True))
    if canal:
        consulta = consulta.filter(func.lower(Campaign.channel) == canal.lower().strip())

    total = consulta.count()
    filas = consulta.order_by(Campaign.name.asc()).offset(offset).limit(limit).all()
    return ListaDeCampanas(total=total, items=filas)


@router.get("/{campaign_id}", response_model=CampanaResponse)
def obtener_campana(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    ciclo.cerrar_vencidas(db)
    return _buscar(db, campaign_id)


@router.post("", response_model=CampanaResponse, status_code=status.HTTP_201_CREATED)
def crear_campana(
    datos: CampanaCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(GESTORES)),
    auditoria: AsientoDeAuditoria = Depends(auditar(ACCION_CAMPANA_CREAR, ENTIDAD_CAMPANA)),
):
    """Crea una campaña. Requiere Sales_Lead o System_Admin."""
    _validar_fechas(datos.start_date, datos.end_date)
    ciclo.comprobar_responsable(db, datos.responsable_id)

    valores = datos.model_dump()
    estado = valores.pop("estado")
    if estado is None:
        # Sin estado, como antes de que los hubiera: `is_active` decide.
        estado = ACTIVA if datos.is_active else PAUSADA
    ciclo.comprobar_transicion(None, estado, datos.end_date)
    campana = Campaign(**valores)
    ciclo.fijar_estado(campana, estado)
    db.add(campana)
    db.commit()
    db.refresh(campana)

    auditoria.anotar(
        entidad_id=campana.id,
        nombre=campana.name,
        canal=campana.channel,
        presupuesto=campana.budget,
        estado=campana.estado,
        responsable_id=campana.responsable_id,
    )
    logger.info("Campaña '%s' creada por %s", campana.name, current_user.email)
    return campana


@router.put("/{campaign_id}", response_model=CampanaResponse)
def actualizar_campana(
    campaign_id: int,
    cambios: CampanaUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(GESTORES)),
    auditoria: AsientoDeAuditoria = Depends(auditar(ACCION_CAMPANA_ACTUALIZAR, ENTIDAD_CAMPANA)),
):
    """
    Ajusta una campaña.

    El presupuesto se registra en la bitácora **con su valor anterior y el nuevo**, a
    diferencia de los prospectos, donde solo se anotan los nombres de los campos tocados.
    La diferencia es deliberada: los datos de un prospecto son personales y duplicarlos en
    una tabla con otro criterio de acceso los expone dos veces; una cifra de presupuesto no
    es un dato personal y su historial de cambios es justo lo que alguien querrá reconstruir
    cuando el rendimiento por campaña no cuadre.
    """
    campana = _buscar(db, campaign_id)
    auditoria.anotar(entidad_id=campaign_id, nombre=campana.name)

    datos = cambios.model_dump(exclude_unset=True)
    if not datos:
        return campana

    _validar_fechas(
        datos.get("start_date", campana.start_date),
        datos.get("end_date", campana.end_date),
    )
    if "responsable_id" in datos:
        ciclo.comprobar_responsable(db, datos["responsable_id"])

    # El estado se decide aparte: `is_active` suelto es la forma de antes de reactivar
    # (verdadero → activa) o de parar (falso → pausada), y nunca se escribe por su cuenta.
    estado = datos.pop("estado", None)
    activa = datos.pop("is_active", None)
    if estado is None and activa is not None:
        estado = ACTIVA if activa else PAUSADA
    estado_final = estado or campana.estado
    if estado is not None or "end_date" in datos:
        ciclo.comprobar_transicion(campana, estado_final, datos.get("end_date", campana.end_date))

    if "budget" in datos and datos["budget"] != campana.budget:
        auditoria.anotar(presupuesto_anterior=campana.budget, presupuesto_nuevo=datos["budget"])
    if estado is not None and estado != campana.estado:
        auditoria.anotar(estado_anterior=campana.estado, estado_nuevo=estado)
    if "responsable_id" in datos and datos["responsable_id"] != campana.responsable_id:
        auditoria.anotar(
            responsable_anterior=campana.responsable_id, responsable_nuevo=datos["responsable_id"]
        )

    for campo, valor in datos.items():
        setattr(campana, campo, valor)
    if estado is not None:
        ciclo.fijar_estado(campana, estado)
        datos["estado"] = estado
    db.commit()
    db.refresh(campana)

    auditoria.anotar(campos=sorted(datos.keys()))
    logger.info("Campaña %s actualizada por %s", campaign_id, current_user.email)
    return campana


@router.delete("/{campaign_id}", response_model=CampanaResponse)
def desactivar_campana(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(GESTORES)),
    auditoria: AsientoDeAuditoria = Depends(auditar(ACCION_CAMPANA_DESACTIVAR, ENTIDAD_CAMPANA)),
):
    """
    Desactiva una campaña. No la borra, por la misma razón que con las cuentas.

    Borrarla pondría a NULL la campaña de cada prospecto que atrajo, y con ella la
    atribución de la inversión: el informe de rendimiento perdería exactamente las
    campañas terminadas, que son las únicas cuyo resultado final se conoce.
    """
    campana = _buscar(db, campaign_id)
    atraidos = (
        db.query(func.count(Lead.id)).filter(Lead.campaign_id == campana.id).scalar() or 0
    )
    auditoria.anotar(entidad_id=campaign_id, nombre=campana.name, prospectos_atribuidos=atraidos)

    # «Desactivar» es cerrar: deja de recibir perfiles y se da por terminada. Pausar es un
    # cambio de estado en la edición.
    ciclo.fijar_estado(campana, CERRADA)
    db.commit()
    db.refresh(campana)

    logger.info(
        "Campaña %s desactivada por %s; conserva %s prospectos atribuidos",
        campaign_id, current_user.email, atraidos,
    )
    return campana


@router.post("/{campaign_id}/duplicar", response_model=CampanaResponse, status_code=status.HTTP_201_CREATED)
def duplicar_campana(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(GESTORES)),
    auditoria: AsientoDeAuditoria = Depends(auditar(ACCION_CAMPANA_DUPLICAR, ENTIDAD_CAMPANA)),
):
    """
    Una campaña nueva con el texto, el público, las opciones y el responsable de otra.

    Sale en borrador y con enlace propio: el enlace del original ya está publicado y apunta
    al original para siempre. No copia la dirección del post, las fechas ni las visitas.
    """
    original = _buscar(db, campaign_id)
    copia = ciclo.duplicar(db, original)
    auditoria.anotar(entidad_id=copia.id, nombre=copia.name, duplicada_de=original.id)
    logger.info("Campaña %s duplicada en %s por %s", original.id, copia.id, current_user.email)
    return copia
