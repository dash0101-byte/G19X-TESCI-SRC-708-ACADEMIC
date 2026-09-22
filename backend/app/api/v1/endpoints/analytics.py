from typing import List

from app.core.autorizacion import AlcanceDeCartera
from app.core.database import get_db
from app.core.security import CurrentUser, UserRole, get_current_user, require_roles
from app.schemas.analytics import AnalyticsSummary, CampaignPerformance
from app.services.analytics_service import AnalyticsService
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/summary", response_model=AnalyticsSummary)
def get_analytics_summary(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    KPIs del pipeline para el tablero, **acotados a la cartera de quien pregunta**.

    Un asesor comercial ve sus propios números. Antes veía los de la empresa entera: sin
    abrir una sola ficha ajena, un total y una media revelan el tamaño y la salud del
    pipeline completo, así que dejar el resumen sin acotar habría vaciado de contenido el
    filtro del listado.
    """
    svc = AnalyticsService(db, AlcanceDeCartera.de(current_user))
    return svc.get_summary()


@router.get("/campaigns", response_model=List[CampaignPerformance])
def get_campaigns_performance(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles([UserRole.SALES_LEAD, UserRole.SYSTEM_ADMIN])
    ),
):
    """
    Rendimiento por campaña. Restringido a quien dirige la cartera completa.

    No se acota por cartera como el resumen: los prospectos de una sola persona divididos
    por el presupuesto entero de la campaña dan una rentabilidad que no significa nada, y
    publicar un número de negocio mal calculado hace más daño que no publicarlo. Es un
    informe de dirección, y se trata como tal.
    """
    svc = AnalyticsService(db, AlcanceDeCartera.de(current_user))
    return svc.get_campaigns_performance()
