import json
import logging

from app.core.database import get_db
from app.core.rate_limit import limiter, webhook_limit
from app.core.security import SIGNATURE_HEADER, verify_crm_webhook
from app.schemas.crm import CRMIngestResponse, CRMWebhookPayload
from app.services.crm_service import CRMService
from app.services.registro_de_actividad import EventoInvalido
from app.services.scoring_service import ScoringService
from app.services.webhook_dedup import (
    EntregaRepetida,
    EntregaYaAtendida,
    clave_de_idempotencia,
    confirmar_entrega,
    purgar_entregas_caducadas,
    reservar_entrega,
    verificar_entrega,
)
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter()

# Se informa al emisor de que su reintento no volvió a ingerir nada. Un CRM que reintenta
# a ciegas no lo necesita, pero quien depure una integración sí: sin esta cabecera, una
# respuesta idéntica a la anterior es indistinguible de un segundo procesamiento.
CABECERA_REPETICION = "X-PluriOne-Idempotent-Replay"


@router.post("/webhook", response_model=CRMIngestResponse, status_code=status.HTTP_200_OK)
@limiter.limit(webhook_limit)
async def crm_webhook_receiver(
    request: Request,
    response: Response,
    raw_body: bytes = Depends(verify_crm_webhook),
    db: Session = Depends(get_db),
):
    """
    Punto de entrada de Webhooks para sistemas CRM (HubSpot, Salesforce, Zoho, CustomCRM).
    Ingesta, actualiza, deduce duplicados y califica prospectos de manera automática.

    Requiere firma HMAC-SHA256 sobre `<timestamp>.<cuerpo>` en `X-PluriOne-Signature`, con
    la marca de tiempo en `X-PluriOne-Timestamp`. El cuerpo se toma en crudo —y se valida
    después de comprobar la firma— porque el HMAC se calcula sobre los bytes exactos que
    envió el emisor: dejar que Pydantic los reserialice rompería la comprobación.

    La firma autentica pero no acredita novedad: la misma petición reenviada dentro de la
    ventana de tolerancia vuelve a pasar todas las comprobaciones. Por eso cada entrega
    atendida queda registrada, y una repetición se distingue de un reintento:

    * misma firma exacta → **409**, porque ningún emisor honesto reenvía los mismos bytes
      con la misma marca de tiempo;
    * mismo evento con firma nueva → **200 con la respuesta original**, que es lo que
      pedía un CRM al que se le perdió la respuesta.
    """
    try:
        payload = CRMWebhookPayload.model_validate(json.loads(raw_body))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El cuerpo del webhook no es JSON válido.",
        ) from exc
    except ValidationError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=json.loads(ve.json()),
        ) from ve

    firma = request.headers.get(SIGNATURE_HEADER, "")
    clave = clave_de_idempotencia(
        crm_platform=payload.crm_platform,
        event=payload.event,
        external_lead_id=payload.external_lead_id,
        body=raw_body,
    )

    # Housekeeping antes de consultar: una entrada caducada no debe contar como duplicado.
    # Se autolimita en el tiempo, así que la mayoría de las llamadas no ejecutan nada.
    purgar_entregas_caducadas(db)

    duplicado = HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Esta entrega ya fue recibida. El evento no se procesó por segunda vez.",
    )

    try:
        verificar_entrega(db, signature=firma, idempotency_key=clave)
    except EntregaRepetida:
        raise duplicado from None
    except EntregaYaAtendida as atendida:
        try:
            repetida = CRMIngestResponse.model_validate(atendida.response_data)
        except ValidationError:
            # La reserva existe pero su respuesta no llegó a guardarse (la confirmación
            # falló después de la ingesta). No se puede repetir lo que no se guardó, y
            # volver a procesar sería la doble ingesta que esto evita: se responde 409.
            logger.warning(
                "Entrega repetida sin respuesta almacenada (clave '%s'); se responde 409.", clave
            )
            raise duplicado from None
        response.headers[CABECERA_REPETICION] = "true"
        return repetida

    entrega = reservar_entrega(
        db,
        signature=firma,
        idempotency_key=clave,
        crm_platform=payload.crm_platform,
        event=payload.event,
        external_lead_id=payload.external_lead_id,
    )

    scoring_svc = ScoringService(db)
    crm_svc = CRMService(db, scoring_svc)
    try:
        resultado = await crm_svc.process_webhook(payload)
    except EventoInvalido as invalido:
        # Un tipo desconocido, una llamada sin resultado, un teléfono que no es un número:
        # el emisor puede corregirlo y el motivo le dice qué. Antes un tipo desconocido se
        # registraba como FORM_SUBMIT y solo lo contaba un aviso del registro de texto.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=invalido.como_detalle()
        ) from invalido
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve)) from ve
    except IntegrityError:
        # Dos entregas idénticas confirmando a la vez: el índice único deja pasar una y
        # rechaza la otra. La primera ya hizo el trabajo, así que esta es un duplicado.
        db.rollback()
        logger.warning("Entrega concurrente rechazada por el índice único (clave '%s').", clave)
        raise duplicado from None
    except Exception as exc:
        # El detalle va solo al log: el mensaje de una excepción interna puede contener
        # SQL, rutas o fragmentos del payload, y el emisor del webhook no debe verlos.
        logger.error("Error procesando webhook CRM: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error durante el procesamiento del Webhook CRM.",
        ) from exc

    # La reserva se confirmó con el mismo commit que la ingesta; aquí solo se le añade la
    # respuesta que se dio, para poder repetirla si el emisor no llega a recibirla.
    confirmar_entrega(
        db, entrega, response_data=resultado.model_dump(), lead_id=resultado.lead_id
    )
    return resultado
