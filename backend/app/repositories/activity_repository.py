from typing import List

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.entities import LeadActivity


class ActivityRepository:
    """
    Solo lectura. Hasta la Fase 15 este repositorio también escribía actividades, con lo
    que mandara el cliente; hoy las escribe `registro_de_actividad.registrar_evento` y
    nadie más.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_lead_activities(self, lead_id: int) -> List[LeadActivity]:
        return (
            self.db.query(LeadActivity)
            .filter(LeadActivity.lead_id == lead_id)
            .order_by(desc(LeadActivity.occurred_at), desc(LeadActivity.id))
            .all()
        )
