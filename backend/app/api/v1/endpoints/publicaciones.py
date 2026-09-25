"""
Informes de publicaciones: qué trajo cada post y cómo se comparan entre sí.

El alta y la edición de una publicación siguen en `/campaigns`, porque una publicación es
una campaña con canal LinkedIn y no una entidad aparte. Lo que vive aquí es lo que no es
CRUD: un informe por publicación, la comparativa y el contador de lo que llegó sin asesor.

Las tres rutas son de lectura y las tres tienen alcance distinto, a propósito:

* el **informe** lo abre cualquiera, y lo que devuelve depende de quién pregunta;
* la **comparativa** es de dirección, como el rendimiento por campaña;
* el **contador** es del líder: es el aviso de que hay trabajo sin repartir, y repartir
  cartera es cosa suya;
* la **vista previa** de la página la abre cualquiera que pueda ver la publicación.
"""
import datetime
import logging
from typing import Optional

from app.core.audit import (
    ACCION_PUBLICACION_COMPARATIVA,
    ACCION_PUBLICACION_INFORME,
    ENTIDAD_CAMPANA,
    AsientoDeAuditoria,
    auditar,
)
from app.core.autorizacion import AlcanceDeCartera, alcance_actual
from app.core.database import get_db
from app.core.security import CurrentUser, UserRole, get_current_user, require_roles
from app.models.entities import LeadStatus
from app.schemas.interes import PublicacionPublica
from app.schemas.publicaciones import (
    ComparativaDePublicaciones,
    EstadoDeLaDireccionPublica,
    InformeDePublicacion,
    NuevosSinAsesor,
)
from app.services import direccion_publica, informe_de_publicaciones, pagina_de_interes
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter()

DIRECCION = [UserRole.SALES_LEAD, UserRole.SYSTEM_ADMIN]


@router.get("/comparativa", response_model=ComparativaDePublicaciones)
def comparar_publicaciones(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(DIRECCION)),
    auditoria: AsientoDeAuditoria = Depends(
        auditar(ACCION_PUBLICACION_COMPARATIVA, ENTIDAD_CAMPANA)
    ),
):
    """
    Perfiles recibidos, score medio y avances de cada publicación.

    Restringida a quien dirige la cartera completa. Acotada por cartera no compararía
    publicaciones sino asesores: la publicación que más trajo parecería la de quien atiende
    más prospectos, que es otra pregunta y con otra respuesta.
    """
    resultado = informe_de_publicaciones.comparativa(db)
    auditoria.anotar(publicaciones=len(resultado.items))
    return resultado


@router.get("/nuevos-sin-asesor", response_model=NuevosSinAsesor)
def contar_nuevos_sin_asesor(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(DIRECCION)),
):
    """
    Cuántos prospectos de LinkedIn están sin asignar.

    Un número, sin nombres ni identificadores: es un aviso de que hay que repartir, no una
    lista que sortee el alcance de cartera por la puerta de atrás.
    """
    return NuevosSinAsesor(total=informe_de_publicaciones.nuevos_sin_asesor(db))


@router.get("/direccion-publica", response_model=EstadoDeLaDireccionPublica)
def estado_de_la_direccion_publica(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(DIRECCION)),
):
    """
    ¿La dirección pública configurada sigue llevando aquí? (capítulo 34)

    Existe porque el túnel de prueba gratuito da una dirección **distinta en cada arranque**,
    y ese cambio no rompe nada de forma visible: el post sigue en LinkedIn, la publicación
    sigue activa, el informe sigue contando sus visitas —cero— y quien pulsa el enlace no
    llega a ninguna parte. Sin esta pregunta, la avería se descubre cuando alguien comenta
    que el enlace no va, que puede ser semanas.

    Es de **dirección** y no de cualquiera con sesión por una razón práctica: quien puede
    hacer algo con la respuesta es quien reparte los enlaces. Un asesor que viera «la
    dirección pública no responde» no tendría ninguna acción disponible.

    No lleva asiento de auditoría. No lee datos de nadie ni cambia nada: contesta sobre la
    configuración del propio sistema, y un asiento por cada vez que se abre la pantalla de
    publicaciones enterraría los que sí importan.
    """
    estado = direccion_publica.comprobar()
    return EstadoDeLaDireccionPublica(
        **estado.como_dict(),
        publicaciones_con_enlace_caducado=informe_de_publicaciones.contar_enlaces_caducados(db),
    )


@router.get("/{campaign_id}/informe", response_model=InformeDePublicacion)
def informe_de_publicacion(
    campaign_id: int,
    etapa: Optional[LeadStatus] = Query(None, description="Filtra por etapa del prospecto."),
    desde: Optional[datetime.date] = Query(None, description="Perfiles recibidos desde este día."),
    hasta: Optional[datetime.date] = Query(None, description="Hasta este día, incluido."),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    alcance: AlcanceDeCartera = Depends(alcance_actual),
    auditoria: AsientoDeAuditoria = Depends(auditar(ACCION_PUBLICACION_INFORME, ENTIDAD_CAMPANA)),
):
    """
    Los perfiles que trajo una publicación, del score más alto al más bajo.

    Un asesor ve los suyos y cuántos más hay; el líder y el administrador, todos. Una
    campaña que no es una publicación responde 404, igual que una que no existe.

    La consulta queda en la bitácora con los filtros y el número de filas devueltas. Nunca
    con las filas: la bitácora se lee con otro criterio de acceso que la cartera, y copiar
    ahí los nombres y las empresas de quienes respondieron a un post expondría dos veces
    los mismos datos.
    """
    publicacion = informe_de_publicaciones.buscar_publicacion(db, campaign_id)
    resultado = informe_de_publicaciones.informe(
        db,
        alcance,
        publicacion,
        etapa=etapa,
        desde=desde,
        hasta=hasta,
        limit=limit,
        offset=offset,
    )
    auditoria.anotar(
        entidad_id=publicacion.id,
        filtros={
            "etapa": etapa.value if etapa else None,
            "desde": desde.isoformat() if desde else None,
            "hasta": hasta.isoformat() if hasta else None,
        },
        devueltos=len(resultado.filas),
        total=resultado.total,
        alcance_completo=alcance.toda_la_cartera,
    )
    return resultado


@router.get("/{campaign_id}/vista-previa", response_model=PublicacionPublica)
def vista_previa_de_la_pagina(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    La página de interés **tal como la verá el interesado**, con las opciones de esta
    publicación, en cualquier estado: un borrador se revisa precisamente antes de activarlo.

    Es lo mismo que sirve `GET /interes/{slug}` —las mismas funciones, no una copia—, pero con
    sesión, sin límite público y **sin contar una visita**: mirar la propia página desde el
    panel no es una visita de nadie, y si contara, la tasa de visitas a envíos bajaría cada
    vez que el líder la revisa.
    """
    publicacion = informe_de_publicaciones.buscar_publicacion(db, campaign_id)
    return pagina_de_interes.describir(publicacion)
