import datetime
import hashlib
import json
import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.entities import CRMIntegrationLog, Lead, utc_now
from app.schemas.crm import CRMIngestResponse, CRMWebhookPayload
from app.services.registro_de_actividad import (
    CAMPOS_DEL_PROSPECTO,
    ESTADO_DUPLICADA,
    Contacto,
    Evento,
    EventoInvalido,
    minimizar,
    registrar_evento,
)
from app.services.scoring_service import ScoringService

logger = logging.getLogger(__name__)


class CRMIngestionError(Exception):
    """
    La ingesta se revirtió por un fallo del lado del servidor.

    Se distingue de `ValueError` —reservado para cargas útiles inválidas, que el
    endpoint traduce a 400— porque el emisor no puede corregir nada reenviando otra
    cosa: la respuesta correcta es un 500, que invita a reintentar el mismo evento.
    """


def _instante(valor: Any, campo: str) -> Optional[datetime.datetime]:
    if valor in (None, ""):
        return None
    try:
        return datetime.datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        raise EventoInvalido(f"'data.{campo}' no es una fecha ISO 8601.", campo) from None


def identificador_del_evento(payload: CRMWebhookPayload) -> str:
    """
    El identificador con el que el evento del CRM entra en `lead_activities`.

    Si el CRM manda `data.event_id`, es ese, precedido de la plataforma: dos CRM pueden
    numerar sus eventos igual. Si no lo manda, la huella del contenido del evento, que es lo
    mismo que ya identificaba una entrega en la ventana de idempotencia del webhook. La
    diferencia es que aquí dura para siempre: el mismo evento reentregado un mes después
    no vuelve a entrar.
    """
    evento_id = payload.data.get("event_id")
    if evento_id not in (None, ""):
        return f"{payload.crm_platform}:{evento_id}"[:200]
    contenido = json.dumps(
        {"event": payload.event, "external_lead_id": payload.external_lead_id, "data": payload.data},
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return f"{payload.crm_platform}:sha256:{hashlib.sha256(contenido.encode('utf-8')).hexdigest()}"


class CRMService:
    def __init__(self, db: Session, scoring_service: ScoringService):
        self.db = db
        self.scoring_service = scoring_service

    def construir_evento(self, payload: CRMWebhookPayload) -> Evento:
        """
        Traduce la carga del CRM a un `Evento`. No inventa nada: lo que no viene queda vacío.

        Antes, un alta sin industria entraba como «Tecnología» (15 puntos de ajuste
        firmográfico), sin tamaño como «1-10», sin cargo como «No especificado» y sin empresa
        como «Empresa no identificada». Un tipo de actividad desconocido se registraba como
        `FORM_SUBMIT`. Ahora falta el dato o se rechaza el evento con el motivo.
        """
        data = payload.data
        email = str(data.get("email", "") or "").lower().strip()
        if not email:
            raise ValueError("El campo 'email' es obligatorio en la carga útil del CRM.")

        prospecto: Dict[str, Any] = {campo: data.get(campo) for campo in CAMPOS_DEL_PROSPECTO}
        prospecto["email"] = email
        prospecto["annual_revenue"] = data.get("annual_revenue")
        prospecto["source"] = data.get("source") or f"{payload.crm_platform}_Webhook"
        # Lo que el CRM mandó y no tiene columna se conserva, sin el contenido de mensajes.
        prospecto["raw_metadata"] = {"crm_raw": data, "initial_platform": payload.crm_platform}

        datos = data.get("activity_data")
        return Evento(
            fuente="crm",
            tipo=data.get("activity_type"),
            ocurrido_en=_instante(data.get("occurred_at"), "occurred_at") or utc_now(),
            identificador_externo=identificador_del_evento(payload),
            direccion=data.get("direction"),
            resultado_de_llamada=data.get("call_outcome"),
            canal=payload.crm_platform,
            datos=datos if isinstance(datos, dict) else {"event": payload.event},
            contacto=Contacto(email=email, telefono=data.get("phone")),
            prospecto=prospecto,
            aviso_de_privacidad_aceptado_en=_instante(
                data.get("privacy_notice_accepted_at"), "privacy_notice_accepted_at"
            ),
        )

    async def process_webhook(self, payload: CRMWebhookPayload) -> CRMIngestResponse:
        """
        Procesa e ingesta eventos de prospectos desde plataformas CRM externas.

        Toda la ingesta —alta o actualización del prospecto, registro de la actividad,
        cálculo del score y traza de auditoría— se confirma en **una sola transacción**.
        La actividad pasa por `registrar_evento`, como la que se registra desde el panel.

        Si el scoring falla se revierte la ingesta completa y se deja constancia del
        intento en `crm_integration_logs`, en su propia transacción: la trazabilidad no
        debe depender de que el evento que la origina haya salido bien. Un evento inválido
        no llega a escribir nada y se responde con su motivo.
        """
        evento = self.construir_evento(payload)
        email = evento.contacto.email
        existente = self.db.query(Lead.id).filter(Lead.email == email).first()
        # Se guarda antes de cualquier rollback: si el alta se revierte, el prospecto
        # deja de existir y el log de error no puede apuntar a una fila fantasma.
        existing_lead_id: Optional[int] = existente[0] if existente else None

        try:
            resultado = await registrar_evento(
                self.db, evento, scoring=self.scoring_service, commit=False
            )
        except EventoInvalido:
            self.db.rollback()
            raise
        except Exception as exc:
            logger.error(
                "Error al registrar el evento de la ingesta CRM del prospecto %s: %s",
                existing_lead_id if existing_lead_id is not None else "(alta)",
                exc,
                exc_info=True,
            )
            self.db.rollback()
            self._log_failed_ingest(payload, existing_lead_id, str(exc))
            raise CRMIngestionError(
                f"La ingesta se revirtió: el registro o el pipeline de scoring falló ({exc})."
            ) from exc

        lead = resultado.lead
        duplicada = resultado.estado == ESTADO_DUPLICADA
        score = lead.current_score
        categoria = getattr(lead.score_category, "value", lead.score_category)

        self.db.add(
            CRMIntegrationLog(
                lead_id=lead.id,
                external_crm_id=payload.external_lead_id,
                crm_platform=payload.crm_platform,
                event_type=payload.event,
                sync_status="SUCCESS",
                payload=minimizar(payload.model_dump()),
                response_data={
                    "lead_id": lead.id,
                    "score": score,
                    "score_category": categoria,
                    "estado": resultado.estado,
                },
                synced_at=utc_now(),
            )
        )

        assigned_name = lead.assigned_rep.full_name if lead.assigned_rep else "Sin asignar"
        lead_id = lead.id
        self.db.commit()

        if duplicada:
            mensaje = "El evento ya estaba registrado; no se volvió a puntuar."
        elif resultado.prospecto_creado:
            mensaje = "Prospecto creado y calificado exitosamente."
        else:
            mensaje = "Prospecto actualizado y calificado exitosamente."
        # Por identificador, nunca por correo (R-11).
        logger.info(
            "Ingesta CRM %s: prospecto %s, evento %s, score %s.",
            payload.crm_platform, lead_id, resultado.estado, score,
        )

        return CRMIngestResponse(
            status="success",
            message=mensaje,
            lead_id=lead_id,
            external_crm_id=payload.external_lead_id,
            calculated_score=score,
            score_category=categoria,
            assigned_rep=assigned_name,
        )

    def _log_failed_ingest(
        self,
        payload: CRMWebhookPayload,
        lead_id: Optional[int],
        error_message: str,
    ) -> None:
        """
        Deja constancia de una ingesta revertida, en una transacción independiente.

        `lead_id` solo se informa cuando el prospecto ya existía antes del evento: si el
        alta formaba parte de lo revertido, la fila no existe y la clave foránea apuntaría
        al vacío. La columna es anulable justamente para este caso.
        """
        try:
            self.db.add(
                CRMIntegrationLog(
                    lead_id=lead_id,
                    external_crm_id=payload.external_lead_id,
                    crm_platform=payload.crm_platform,
                    event_type=payload.event,
                    sync_status="ERROR",
                    payload=minimizar(payload.model_dump()),
                    response_data={"lead_id": lead_id, "error": error_message},
                    error_message=error_message,
                    synced_at=utc_now(),
                )
            )
            self.db.commit()
        except Exception:
            # Que falle la auditoría no debe enmascarar el error original de la ingesta.
            self.db.rollback()
            logger.exception("No fue posible registrar el log de integración CRM fallida.")
