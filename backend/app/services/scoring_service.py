import datetime
import logging
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.adapters.azure_ml_adapter import get_ml_scoring_adapter
from app.adapters.azure_openai_adapter import get_ai_explanation_adapter
from app.adapters.base import BaseAIExplanationAdapter, BaseMLScoringAdapter
from app.core.config import settings
from app.core.metricas import contar_score
from app.core.scoring_rules import (
    HeuristicParams,
    calculate_heuristic_score,
    calculate_temporal_decay,
    categorize,
    combine_scores,
)
from app.core.vector_del_modelo import CLAVE_DE_VERSION, VERSION_DEL_VECTOR, ingresos_o_ausente
from app.models.entities import (
    CallOutcome,
    Lead,
    ScoreCategory,
    ScoreHistory,
    User,
)
from app.schemas.score import AIExplanation, ScoreResult

logger = logging.getLogger(__name__)

# Resultados de llamada que cuentan como intento sin conversación.
_SIN_RESPUESTA = frozenset({CallOutcome.NO_CONTESTO.value, CallOutcome.BUZON.value})


class ScoringService:
    def __init__(
        self,
        db: Session,
        ml_adapter: Optional[BaseMLScoringAdapter] = None,
        ai_adapter: Optional[BaseAIExplanationAdapter] = None,
    ):
        self.db = db
        self.ml_adapter = ml_adapter or get_ml_scoring_adapter()
        self.ai_adapter = ai_adapter or get_ai_explanation_adapter()

    @property
    def params(self) -> HeuristicParams:
        """
        Parámetros de calibración vigentes.

        Se leen en cada acceso y no se congelan en `__init__`: las pruebas y la
        calibración por entorno ajustan `settings`, y un servicio de vida larga con los
        pesos cacheados seguiría puntuando con la configuración anterior.
        """
        return HeuristicParams.from_settings()

    @property
    def model_version(self) -> str:
        """
        Versión que se registra en la auditoría, con el motor que puntuó de verdad.

        Antes se guardaba `settings.MODEL_VERSION` a secas: una constante. El historial
        afirmaba entonces que cada puntuación venía del modelo híbrido aunque el artefacto
        no se hubiera cargado y quien puntuara fuese el heurístico de contingencia. Ese
        era el segundo tramo de A-5: se corrigió que el modelo llegara a la imagen, pero
        el registro seguía sin poder distinguir un caso del otro. Un historial de
        auditoría que no distingue con qué se calculó no sirve para auditar.

        Queda como `v1.0.0-hybrid+ml:0a2632a2` o `v1.0.0-hybrid+heuristico`. La columna
        admite 50 caracteres y se recorta por si alguien alarga `MODEL_VERSION`.
        """
        try:
            motor = self.ml_adapter.version_del_motor()
        except Exception:  # pragma: no cover - un adaptador ajeno no debe tumbar el scoring
            motor = "desconocido"
        return f"{settings.MODEL_VERSION}+{motor}"[:50]

    def calculate_temporal_decay(self, days_inactive: float) -> float:
        """Factor de atenuación gamma(Δt) con la vida media configurada."""
        return calculate_temporal_decay(days_inactive, half_life_days=self.params.half_life_days)

    def compute_heuristic_score(
        self,
        job_title: str,
        industry: str,
        company_size: str,
        page_views: int = 0,
        email_opens: int = 0,
        email_clicks: int = 0,
        downloads: int = 0,
        requested_demo: bool = False,
        attended_webinar: bool = False,
        proposal_sent: bool = False,
        meeting_scheduled: bool = False,
        phone_calls: int = 0,
        whatsapp_messages: int = 0,
        custom_events: int = 0,
        days_inactive: float = 0.0,
        custom_metadata: Optional[Dict[str, Any]] = None,
        linkedin_messages: int = 0,
    ) -> Tuple[float, Dict[str, Any], float]:
        """
        Componente heurístico del score.

        Delega en `app.core.scoring_rules`, única implementación de las reglas ICP: el
        pipeline de entrenamiento consume exactamente la misma función, de modo que el
        modelo se entrena y se evalúa contra la misma definición de "buen prospecto".
        """
        return calculate_heuristic_score(
            job_title=job_title,
            industry=industry,
            company_size=company_size,
            page_views=page_views,
            email_opens=email_opens,
            email_clicks=email_clicks,
            downloads=downloads,
            requested_demo=requested_demo,
            attended_webinar=attended_webinar,
            days_inactive=days_inactive,
            proposal_sent=proposal_sent,
            meeting_scheduled=meeting_scheduled,
            phone_calls=phone_calls,
            whatsapp_messages=whatsapp_messages,
            linkedin_messages=linkedin_messages,
            custom_events=custom_events,
            custom_metadata=custom_metadata,
            params=self.params,
        )

    def extract_features_from_lead(self, lead: Lead) -> Dict[str, Any]:
        """Extrae el vector de variables desde una entidad Lead y sus actividades."""
        now = datetime.datetime.now(datetime.timezone.utc)

        # Calcular inactividad
        last_act = lead.last_activity_at or lead.created_at or now
        if last_act.tzinfo is None:
            last_act = last_act.replace(tzinfo=datetime.timezone.utc)
        days_inactive = max(0.0, (now - last_act).total_seconds() / 86400.0)

        # Contabilizar actividades
        page_views = 0
        email_opens = 0
        email_clicks = 0
        downloads = 0
        requested_demo = False
        attended_webinar = False
        proposal_sent = False
        meeting_scheduled = False
        llamadas_conectadas = 0
        llamadas_sin_respuesta = 0
        whatsapp_messages = 0
        linkedin_messages = 0
        custom_events = 0

        for act in lead.activities:
            act_type_val = act.activity_type.value if hasattr(act.activity_type, "value") else str(act.activity_type)
            if act_type_val == "PAGE_VIEW":
                page_views += 1
            elif act_type_val == "EMAIL_OPEN":
                email_opens += 1
            elif act_type_val == "EMAIL_CLICK":
                email_clicks += 1
            elif act_type_val == "CONTENT_DOWNLOAD":
                downloads += 1
            elif act_type_val == "DEMO_REQUEST":
                requested_demo = True
            elif act_type_val == "WEBINAR_ATTEND":
                attended_webinar = True
            elif act_type_val == "PROPOSAL_SENT":
                proposal_sent = True
            elif act_type_val == "MEETING_SCHEDULED":
                meeting_scheduled = True
            elif act_type_val == "PHONE_CALL":
                # El resultado de la llamada es la variable (capítulo 24). La que conectó es
                # una conversación; un buzón o un «no contestó» es un intento, y seis intentos
                # sin respuesta dicen algo distinto que ninguna llamada. Las llamadas
                # anteriores a la Fase 15 no tienen resultado y no suman en ninguna de las dos:
                # suponérselo sería inventarlo (véase el capítulo 21).
                if act.call_outcome == CallOutcome.CONECTO.value:
                    llamadas_conectadas += 1
                elif act.call_outcome in _SIN_RESPUESTA:
                    llamadas_sin_respuesta += 1
            elif act_type_val == "WHATSAPP_MESSAGE":
                whatsapp_messages += 1
            elif act_type_val == "LINKEDIN_MESSAGE":
                linkedin_messages += 1
            elif act_type_val == "CUSTOM":
                custom_events += 1

        return {
            "job_title": lead.job_title or "",
            "industry": lead.industry or "",
            # Vacío y no «1-10»: un tamaño que no llegó no es una empresa pequeña. Para el
            # modelo es una categoría desconocida —el codificador la ignora— y para la regla
            # heurística, el punto medio de su bloque (`UNKNOWN_SIZE_POINTS`).
            "company_size": lead.company_size or "",
            # `None` cuando no se declaró: el modelo lo imputa y sabe que faltaba. Antes era
            # 0.0 aquí y 100 000 en el adaptador, y el modelo leía una cifra que nadie dio.
            "annual_revenue": ingresos_o_ausente(lead.annual_revenue),
            "source_channel": lead.source or "Website",
            "page_views": page_views,
            "email_opens": email_opens,
            "email_clicks": email_clicks,
            "content_downloads": downloads,
            "attended_webinar": 1 if attended_webinar else 0,
            "requested_demo": 1 if requested_demo else 0,
            "proposal_sent": 1 if proposal_sent else 0,
            "meeting_scheduled": 1 if meeting_scheduled else 0,
            "phone_calls_connected": llamadas_conectadas,
            "phone_calls_unanswered": llamadas_sin_respuesta,
            "whatsapp_messages": whatsapp_messages,
            "linkedin_messages": linkedin_messages,
            "custom_events": custom_events,
            "days_since_last_activity": days_inactive,
            "custom_metadata": lead.raw_metadata or {},
            # Con qué vector se tomó. Una instantánea de otra versión no se puede traducir a
            # esta sin inventar, y quien la lee —el dataset real, el monitor— la descarta.
            CLAVE_DE_VERSION: VERSION_DEL_VECTOR,
        }

    async def calculate_and_persist_score(
        self,
        lead: Lead,
        generate_ai_text: bool = True,
        commit: bool = True,
    ) -> ScoreResult:
        """
        Ejecuta el pipeline de scoring completo con soporte para campos flexibles.

        Con `commit=False` los cambios se dejan pendientes (solo `flush`) para que el
        llamador cierre una transacción mayor. Lo usa la ingesta del webhook CRM, donde
        el prospecto, su actividad, su score y el registro de auditoría deben confirmarse
        juntos o no confirmarse en absoluto.
        """
        features = self.extract_features_from_lead(lead)
        days_inactive = features["days_since_last_activity"]

        # 1. Inferencia ML (0.0 a 1.0)
        ml_prob = await self.ml_adapter.predict_conversion_probability(features)

        # 2. Cálculo Heurístico con atenuación y campos personalizados
        heur_score, breakdown, decay_factor = self.compute_heuristic_score(
            # Lo que la ficha no tiene llega vacío: la regla lo puntúa como desconocido.
            job_title=lead.job_title,
            industry=lead.industry,
            company_size=lead.company_size,
            page_views=features["page_views"],
            email_opens=features["email_opens"],
            email_clicks=features["email_clicks"],
            downloads=features["content_downloads"],
            requested_demo=bool(features["requested_demo"]),
            attended_webinar=bool(features["attended_webinar"]),
            proposal_sent=bool(features["proposal_sent"]),
            meeting_scheduled=bool(features["meeting_scheduled"]),
            # La regla puntúa conversaciones, no intentos: las llamadas sin respuesta
            # llegan al modelo y no a la mitad heurística, como antes del capítulo 24.
            phone_calls=features["phone_calls_connected"],
            whatsapp_messages=features["whatsapp_messages"],
            linkedin_messages=features["linkedin_messages"],
            custom_events=features["custom_events"],
            days_inactive=days_inactive,
            custom_metadata=lead.raw_metadata or {},
        )

        # 3. Fusión Ponderada Híbrida y 4. Categorización Dinámica
        params = self.params
        final_score = combine_scores(ml_prob, heur_score, params)
        category = ScoreCategory(categorize(final_score, params))

        # 5. Generación de Explicabilidad
        ai_exp_dict = {}
        if generate_ai_text:
            lead_meta = {
                "first_name": lead.first_name,
                "company": lead.company,
                "job_title": lead.job_title,
                "industry": lead.industry,
                "days_since_last_activity": int(days_inactive),
                "custom_metadata": lead.raw_metadata or {},
            }
            ai_exp_dict = await self.ai_adapter.generate_explanation(
                lead_data=lead_meta,
                score=final_score,
                score_category=category.value,
                heuristic_breakdown=breakdown,
            )

        # 6. Auto-asignación inteligente a ejecutivo comercial si es HOT y no tiene asignado
        #
        # El destino es un `User` con `is_sales_rep`, no una fila de una tabla de asesores
        # aparte: asignar a alguien que no puede iniciar sesión producía prospectos con
        # dueño nominal y sin nadie capaz de abrirlos.
        if category == ScoreCategory.HOT and not lead.assigned_rep_id:
            available_rep = (
                self.db.query(User)
                .filter(User.is_sales_rep.is_(True), User.is_active.is_(True))
                .order_by(User.capacity.desc().nullslast(), User.id.asc())
                .first()
            )
            if available_rep:
                lead.assigned_rep_id = available_rep.id
                # Por identificador y no por correo: el registro de texto del contenedor no
                # se puede editar después, y una supresión no lo alcanzaría (R-11).
                logger.info(
                    "Lead %s auto-asignado al ejecutivo %s", lead.id, available_rep.full_name
                )

        # 7. Actualizar entidad Lead
        lead.current_score = final_score
        lead.score_category = category
        lead.conversion_probability = ml_prob
        lead.last_score_update = datetime.datetime.now(datetime.timezone.utc)
        lead.updated_at = datetime.datetime.now(datetime.timezone.utc)

        # 8. Guardar en Historial de Auditoría
        score_history = ScoreHistory(
            lead_id=lead.id,
            score=final_score,
            score_category=category,
            model_version=self.model_version,
            ml_probability=round(ml_prob, 4),
            heuristic_score=heur_score,
            decay_factor=decay_factor,
            rule_breakdown=breakdown,
            ai_explanation=ai_exp_dict,
            # Instantánea del vector de variables EN ESTE INSTANTE. Es lo que permite
            # construir después un dataset de reentrenamiento sin fuga de información: el
            # estado actual de un prospecto ganado ya incluye la propuesta y la reunión que
            # llevaron al cierre, así que etiquetar sobre él enseñaría al modelo la relación
            # invertida. Aquí se guarda lo que se sabía cuando aún no se sabía el resultado.
            feature_snapshot=dict(features),
            calculated_at=datetime.datetime.now(datetime.timezone.utc),
        )
        self.db.add(score_history)
        # El `flush` hace visible la auto-asignación de ejecutivo dentro de la
        # transacción; el `refresh` recarga la entidad para que `lead.assigned_rep`
        # deje de ser el valor obsoleto que tenía antes de fijar la clave foránea.
        self.db.flush()
        if commit:
            self.db.commit()
        self.db.refresh(lead)

        # Un score más calculado y persistido. Se cuenta aquí, después de escribir, y no
        # al empezar: un contador que se incrementa antes de saber si la escritura fue bien
        # mide intenciones. La categoría es la etiqueta —cuántos, no cuánto—; la
        # distribución de valores ya vive en la base y `/metrics` la lee de allí.
        contar_score(category.value)

        ai_exp_obj = None
        if ai_exp_dict:
            ai_exp_obj = AIExplanation(
                summary=ai_exp_dict.get("summary", ""),
                strengths=ai_exp_dict.get("strengths", []),
                recommended_action=ai_exp_dict.get("recommended_action", ""),
                engine=ai_exp_dict.get("engine", "PluriOne_XAI_Engine"),
                model_deployment=ai_exp_dict.get("model_deployment"),
            )

        return ScoreResult(
            score=final_score,
            score_category=category,
            conversion_probability=ml_prob,
            ml_probability=round(ml_prob, 4),
            heuristic_score=heur_score,
            decay_factor=decay_factor,
            rule_breakdown=breakdown,
            ai_explanation=ai_exp_obj,
            model_version=self.model_version,
        )

    async def predict_standalone(self, request_data: Dict[str, Any]) -> ScoreResult:
        """Inferencia en tiempo real sin persistencia en base de datos."""
        days_inactive = float(request_data.get("days_since_last_activity", 0.0))
        ml_prob = await self.ml_adapter.predict_conversion_probability(request_data)

        custom_meta = request_data.get("custom_metadata") or {}
        if not custom_meta:
            # El simulador manda los campos personalizados sueltos, no anidados. Se
            # descartan los que llegan en `None`: el schema los declara opcionales y
            # siempre aparecen en el `model_dump()`, y un `urgency=None` se leería como
            # la cadena "NONE" al evaluar la regla de urgencia.
            custom_meta = {
                key: request_data[key]
                for key in ("urgency", "profiles_needed", "budget_range", "work_modality")
                if request_data.get(key) is not None
            }

        heur_score, breakdown, decay_factor = self.compute_heuristic_score(
            job_title=request_data.get("job_title"),
            industry=request_data.get("industry"),
            company_size=request_data.get("company_size"),
            page_views=request_data.get("page_views", 0),
            email_opens=request_data.get("email_opens", 0),
            email_clicks=request_data.get("email_clicks", 0),
            downloads=request_data.get("content_downloads", 0),
            requested_demo=bool(request_data.get("requested_demo", False)),
            attended_webinar=bool(request_data.get("attended_webinar", False)),
            proposal_sent=bool(request_data.get("proposal_sent", False)),
            meeting_scheduled=bool(request_data.get("meeting_scheduled", False)),
            phone_calls=int(request_data.get("phone_calls_connected", 0)),
            whatsapp_messages=int(request_data.get("whatsapp_messages", 0)),
            linkedin_messages=int(request_data.get("linkedin_messages", 0)),
            custom_events=int(request_data.get("custom_events", 0)),
            days_inactive=days_inactive,
            custom_metadata=custom_meta,
        )

        params = self.params
        final_score = combine_scores(ml_prob, heur_score, params)
        category = ScoreCategory(categorize(final_score, params))

        lead_meta = {
            "first_name": request_data.get("first_name", "Prospecto"),
            "company": request_data.get("company", "Empresa"),
            "job_title": request_data.get("job_title", ""),
            "industry": request_data.get("industry", ""),
            "days_since_last_activity": int(days_inactive),
            "custom_metadata": custom_meta,
        }
        ai_exp_dict = await self.ai_adapter.generate_explanation(
            lead_data=lead_meta,
            score=final_score,
            score_category=category.value,
            heuristic_breakdown=breakdown,
        )

        ai_exp_obj = AIExplanation(
            summary=ai_exp_dict.get("summary", ""),
            strengths=ai_exp_dict.get("strengths", []),
            recommended_action=ai_exp_dict.get("recommended_action", ""),
            engine=ai_exp_dict.get("engine", "PluriOne_XAI_Engine"),
            model_deployment=ai_exp_dict.get("model_deployment"),
        )

        return ScoreResult(
            score=final_score,
            score_category=category,
            conversion_probability=ml_prob,
            ml_probability=round(ml_prob, 4),
            heuristic_score=heur_score,
            decay_factor=decay_factor,
            rule_breakdown=breakdown,
            ai_explanation=ai_exp_obj,
            model_version=self.model_version,
        )
