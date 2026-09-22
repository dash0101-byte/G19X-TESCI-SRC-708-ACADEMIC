from typing import List

from sqlalchemy import and_, case, false, func
from sqlalchemy.orm import Session

from app.core.autorizacion import AlcanceDeCartera
from app.models.entities import Campaign, Lead, LeadStatus, QualificationStatus, ScoreCategory
from app.schemas.analytics import AnalyticsSummary, CampaignPerformance


class AnalyticsService:
    """
    KPIs del pipeline, acotados al alcance de quien pregunta.

    El alcance es obligatorio por la misma razón que en el repositorio: un agregado sobre
    la cartera completa revela su tamaño, su calidad y su tasa de conversión aunque
    ninguna ficha llegue a abrirse. Un total es un dato.
    """

    def __init__(self, db: Session, alcance: AlcanceDeCartera):
        self.db = db
        self.alcance = alcance

    def _condicion_de_alcance(self):
        """Predicado reutilizable, para poder meterlo también en un `ON` de JOIN."""
        if self.alcance.toda_la_cartera:
            return None
        if self.alcance.usuario_id is None:
            return false()
        return Lead.assigned_rep_id == self.alcance.usuario_id

    def _acotar(self, query):
        condicion = self._condicion_de_alcance()
        return query if condicion is None else query.filter(condicion)

    def get_summary(self) -> AnalyticsSummary:
        """Calcula el resumen de KPIs ejecutivos para el dashboard."""
        total = self._acotar(self.db.query(Lead)).count()
        hot = self._acotar(self.db.query(Lead).filter(Lead.score_category == ScoreCategory.HOT)).count()
        warm = self._acotar(self.db.query(Lead).filter(Lead.score_category == ScoreCategory.WARM)).count()
        cold = self._acotar(self.db.query(Lead).filter(Lead.score_category == ScoreCategory.COLD)).count()

        avg_score_res = self._acotar(self.db.query(func.avg(Lead.current_score))).scalar() or 0.0
        avg_score = round(float(avg_score_res), 1)

        # MQL to SQL conversion
        mql_count = self._acotar(self.db.query(Lead).filter(Lead.qualification_status.in_([QualificationStatus.MQL, QualificationStatus.SQL]))).count()
        sql_count = self._acotar(self.db.query(Lead).filter(Lead.qualification_status == QualificationStatus.SQL)).count()
        mql_sql_rate = round((sql_count / mql_count * 100.0), 1) if mql_count > 0 else 0.0

        # Pipeline distribution
        statuses = self._acotar(self.db.query(Lead.status, func.count(Lead.id))).group_by(Lead.status).all()
        pipeline_dist = {status.value: count for status, count in statuses}

        # Top Industries
        top_ind_res = (
            self._acotar(self.db.query(Lead.industry, func.count(Lead.id), func.avg(Lead.current_score)))
            .group_by(Lead.industry)
            .order_by(func.count(Lead.id).desc())
            .limit(5)
            .all()
        )
        top_industries = [
            {"industry": ind or "Otro", "count": count, "avg_score": round(float(avg_s or 0.0), 1)}
            for ind, count, avg_s in top_ind_res
        ]

        # Leads by source
        by_source_res = (
            self._acotar(
                self.db.query(
                    Lead.source,
                    func.count(Lead.id),
                    func.sum(case((Lead.score_category == ScoreCategory.HOT, 1), else_=0)),
                )
            )
            .group_by(Lead.source)
            .order_by(func.count(Lead.id).desc())
            .all()
        )
        leads_by_source = [
            {"source": src or "Directo", "total_leads": total_s, "hot_leads": int(hot_s or 0)}
            for src, total_s, hot_s in by_source_res
        ]

        return AnalyticsSummary(
            total_leads=total,
            hot_leads_count=hot,
            warm_leads_count=warm,
            cold_leads_count=cold,
            average_score=avg_score,
            mql_to_sql_conversion_rate=mql_sql_rate,
            pipeline_distribution=pipeline_dist,
            top_industries=top_industries,
            leads_by_source=leads_by_source,
        )

    def get_campaigns_performance(self) -> List[CampaignPerformance]:
        """
        Rendimiento por campaña, resuelto en una sola consulta agregada.

        Antes se traían todas las campañas y, al tocar `camp.leads`, SQLAlchemy emitía una
        consulta más por campaña y materializaba en memoria cada prospecto entero solo para
        contarlos: N+1 consultas y todo el volumen de la tabla `leads` cruzando el proceso
        para producir cuatro números por fila. Con 40 campañas y 50.000 prospectos eso son
        41 viajes a la base y 50.000 objetos ORM construidos y descartados.

        El `LEFT JOIN` es deliberado: una campaña recién creada, o una que no captó nada,
        debe seguir apareciendo con ceros. Con un `JOIN` interno desaparecería del informe,
        que es justo cuando más interesa verla.

        Este informe **no se acota** por cartera, y por eso el endpoint que lo expone está
        restringido a quien dirige la cartera completa. Acotarlo habría producido una
        rentabilidad falsa —los prospectos de una sola persona divididos por el
        presupuesto entero de la campaña—, y un número de negocio mal calculado hace más
        daño que un informe que no se ofrece. El alcance se sigue respetando por si algún
        día se llama desde otro sitio: si no es completo, el JOIN no trae nada.
        """
        total_leads = func.count(Lead.id)
        hot_leads = func.sum(case((Lead.score_category == ScoreCategory.HOT, 1), else_=0))
        won_leads = func.sum(case((Lead.status == LeadStatus.WON, 1), else_=0))

        filas = (
            self.db.query(
                Campaign.id,
                Campaign.name,
                Campaign.channel,
                Campaign.budget,
                total_leads.label("total_leads"),
                hot_leads.label("hot_leads"),
                won_leads.label("won_leads"),
                func.avg(Lead.current_score).label("avg_score"),
            )
            # La condición de alcance va en el `ON`, no en un `WHERE`: en un `WHERE`
            # descartaría las filas donde el LEFT JOIN no encontró prospectos, y las
            # campañas sin captación —las que más interesa mirar— desaparecerían.
            .outerjoin(
                Lead,
                and_(Lead.campaign_id == Campaign.id, *(
                    [] if self._condicion_de_alcance() is None else [self._condicion_de_alcance()]
                )),
            )
            .group_by(Campaign.id, Campaign.name, Campaign.channel, Campaign.budget)
            .order_by(Campaign.id)
            .all()
        )

        rendimiento = []
        for camp_id, nombre, canal, presupuesto, total, calientes, ganados, media in filas:
            total = int(total or 0)
            ganados = int(ganados or 0)
            # La división se hace aquí y no en SQL: cada motor trata de forma distinta la
            # división por cero y la aritmética entera, y el resultado tiene que ser el
            # mismo en PostgreSQL y en el SQLite de las pruebas.
            conv_rate = round(ganados / total * 100.0, 1) if total > 0 else 0.0

            rendimiento.append(
                CampaignPerformance(
                    campaign_id=camp_id,
                    campaign_name=nombre,
                    channel=canal,
                    budget=presupuesto,
                    total_leads=total,
                    hot_leads=int(calientes or 0),
                    avg_score=round(float(media or 0.0), 1),
                    conversion_rate=conv_rate,
                )
            )

        return rendimiento
