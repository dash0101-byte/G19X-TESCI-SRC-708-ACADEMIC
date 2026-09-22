"""
Que un mismo evento de CRM no se ingiera dos veces.

El agujero
----------
La firma HMAC demuestra que el cuerpo lo escribió quien conoce el secreto. No demuestra
que la petición sea nueva. Quien capture una entrega legítima —un proxy intermedio, un
log de acceso con el cuerpo, cualquier punto del camino sin TLS— puede reenviarla tal
cual, y mientras la marca de tiempo siga dentro de la ventana de tolerancia vuelve a pasar
todas las comprobaciones, porque es exactamente la misma petición que ya pasó. Cada
repetición añadía otra actividad al prospecto, movía su score y sumaba una fila de
auditoría. La ventana anti-replay acotaba el daño en el tiempo; no lo impedía dentro de
ella, que es donde ocurre.

Dos huellas, dos intenciones
----------------------------
* **La firma exacta.** Reenviar los mismos bytes con la misma marca de tiempo no lo hace
  ningún emisor honesto: un reintento legítimo se firma de nuevo, con hora nueva. Se
  responde 409.
* **La clave de idempotencia** — plataforma, evento, prospecto externo y huella del
  cuerpo. Un CRM que no llegó a recibir la respuesta reintenta, y su reintento trae marca
  de tiempo nueva y por tanto firma distinta. A ese se le devuelve **la respuesta
  original**: es lo que estaba pidiendo, y contestarle con un error solo alimentaría el
  bucle de reintentos.

La huella del cuerpo forma parte de la clave, y esto es una desviación deliberada de
«idempotencia por `external_lead_id` + evento» a secas. Sin ella, dos `lead.updated`
distintos del mismo prospecto dentro de la ventana se colapsarían en uno y la segunda
actualización —la buena— se descartaría en silencio. Con ella, un reintento (cuerpo
idéntico) se detecta y dos cambios reales (cuerpos distintos) se procesan ambos.

Cuándo se reserva
-----------------
La fila se añade a la sesión **antes** de procesar y se confirma con la misma transacción
que el alta del prospecto. Así, si el pipeline de scoring falla y la ingesta se revierte,
la reserva se va con ella y el reintento del CRM encuentra el camino libre. Reservar en
una transacción aparte habría dejado un candado sobre un evento que nunca llegó a
ingerirse: el CRM reintentaría, recibiría «duplicado», y el prospecto no existiría en
ninguna parte.
"""
import datetime
import hashlib
import logging
import threading
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import WebhookDelivery, utc_now

logger = logging.getLogger(__name__)

# Ancho de la columna `idempotency_key`. La clave se recorta si se excediera, cosa que no
# debería ocurrir con los topes de las cabeceras, pero un truncamiento silencioso en la
# base sería peor que uno explícito aquí.
LONGITUD_MAXIMA_CLAVE = 255

# Momento de la última purga, por proceso. La limpieza va colgada del propio flujo de
# ingesta porque esta pila no despliega ningún planificador; el sello evita pagar un
# DELETE en cada webhook. Con varios workers cada uno lleva el suyo, lo que en el peor
# caso significa purgar más veces de la cuenta: es un barrido por índice sobre filas
# caducadas, no algo que merezca coordinación.
_ultima_purga: Optional[datetime.datetime] = None
_cerrojo_purga = threading.Lock()


class EntregaRepetida(Exception):
    """Se reenviaron los mismos bytes con la misma firma. Se traduce a 409."""

    def __init__(self, recibida_en: datetime.datetime):
        self.recibida_en = recibida_en
        super().__init__(f"Entrega ya recibida el {recibida_en.isoformat()}.")


class EntregaYaAtendida(Exception):
    """
    El mismo evento ya se procesó con éxito. Se responde lo mismo que la primera vez.

    Lleva la respuesta guardada precisamente para poder repetirla: un reintento que
    recibe un error distinto del original no puede distinguir «ya estaba hecho» de «falló
    otra vez», y acaba reintentando indefinidamente.
    """

    def __init__(self, response_data: Dict[str, Any], recibida_en: datetime.datetime):
        self.response_data = response_data or {}
        self.recibida_en = recibida_en
        super().__init__("El evento ya fue atendido; se devuelve la respuesta original.")


def _aware(momento: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
    """SQLite devuelve los instantes sin zona; compararlos con uno *aware* es un TypeError."""
    if momento is None:
        return None
    if momento.tzinfo is None:
        return momento.replace(tzinfo=datetime.timezone.utc)
    return momento


def huella_del_cuerpo(body: bytes) -> str:
    """SHA-256 del cuerpo crudo, en hexadecimal."""
    return hashlib.sha256(body).hexdigest()


def clave_de_idempotencia(
    *, crm_platform: str, event: str, external_lead_id: Optional[str], body: bytes
) -> str:
    """
    Identifica un evento con independencia de cuándo se envíe.

    `external_lead_id` es opcional en el esquema del webhook; cuando no viene se marca con
    un guion. La huella del cuerpo sostiene la clave igualmente: dos entregas sin
    identificador externo pero con el mismo contenido siguen siendo la misma entrega.
    """
    externo = (external_lead_id or "-").strip() or "-"
    clave = f"{crm_platform}:{event}:{externo}:{huella_del_cuerpo(body)}"
    return clave[:LONGITUD_MAXIMA_CLAVE]


def verificar_entrega(db: Session, *, signature: str, idempotency_key: str) -> None:
    """
    Comprueba que esta entrega no se haya atendido ya.

    Lanza `EntregaRepetida` si la firma exacta consta, o `EntregaYaAtendida` si consta el
    evento. Las entradas caducadas no cuentan: pasada la ventana, la marca de tiempo
    original ya no supera la comprobación anti-replay y un reintento honesto ha dejado de
    tener sentido.
    """
    ahora = utc_now()

    por_firma = (
        db.query(WebhookDelivery).filter(WebhookDelivery.signature == signature).first()
    )
    if por_firma is not None and _aware(por_firma.expires_at) > ahora:
        logger.warning(
            "Webhook CRM reenviado con firma idéntica (evento '%s', recibido originalmente el %s).",
            por_firma.event,
            por_firma.received_at,
        )
        raise EntregaRepetida(_aware(por_firma.received_at))

    por_clave = (
        db.query(WebhookDelivery)
        .filter(WebhookDelivery.idempotency_key == idempotency_key)
        .first()
    )
    if por_clave is not None and _aware(por_clave.expires_at) > ahora:
        logger.info(
            "Webhook CRM repetido (evento '%s', prospecto externo '%s'): se devuelve la "
            "respuesta original en lugar de volver a ingerir.",
            por_clave.event,
            por_clave.external_lead_id,
        )
        raise EntregaYaAtendida(por_clave.response_data, _aware(por_clave.received_at))

    # Entradas vencidas con la misma huella: se retiran ahora para dejar sitio, porque las
    # dos columnas son únicas y una fila muerta impediría registrar la entrega nueva.
    for caducada in (por_firma, por_clave):
        if caducada is not None:
            db.delete(caducada)
    if por_firma is not None or por_clave is not None:
        db.flush()


def reservar_entrega(
    db: Session,
    *,
    signature: str,
    idempotency_key: str,
    crm_platform: str,
    event: str,
    external_lead_id: Optional[str],
) -> WebhookDelivery:
    """
    Anota la entrega en la sesión, sin confirmarla.

    Se confirma con el mismo `commit` que la ingesta, de modo que reserva y alta viven o
    caen juntas. Si dos entregas idénticas llegan a la vez, el índice único decide: la
    segunda falla al confirmar y el endpoint la traduce a 409, que es la respuesta
    correcta —la primera ya hizo el trabajo—.
    """
    ahora = utc_now()
    entrega = WebhookDelivery(
        signature=signature,
        idempotency_key=idempotency_key,
        crm_platform=crm_platform,
        event=event,
        external_lead_id=external_lead_id,
        received_at=ahora,
        expires_at=ahora + datetime.timedelta(seconds=settings.CRM_IDEMPOTENCY_WINDOW_SECONDS),
        response_data={},
    )
    db.add(entrega)
    db.flush()
    return entrega


def confirmar_entrega(
    db: Session, entrega: WebhookDelivery, *, response_data: Dict[str, Any], lead_id: Optional[int]
) -> None:
    """
    Guarda la respuesta que se dio, para poder repetirla ante un reintento.

    Se hace después de que la ingesta haya confirmado: la reserva ya está persistida y
    esto solo la completa. Si fallara, la entrega seguiría detectándose como repetida —la
    fila existe— y el reintento recibiría un 409 en vez de la respuesta original; molesto,
    pero nunca una doble ingesta.
    """
    entrega.response_data = response_data
    entrega.lead_id = lead_id
    db.commit()


def purgar_entregas_caducadas(db: Session, forzar: bool = False) -> int:
    """
    Borra las entregas cuya ventana ya venció. Devuelve cuántas filas cayeron.

    Se llama desde el propio flujo de ingesta, como mucho una vez cada
    `CRM_DEDUP_PURGE_INTERVAL_SECONDS`. Sin límite de frecuencia, un CRM con picos de
    sincronización pagaría un DELETE por evento; sin purga, la tabla crecería para
    siempre guardando filas que ya no protegen de nada.
    """
    global _ultima_purga

    ahora = utc_now()
    if not forzar:
        with _cerrojo_purga:
            if (
                _ultima_purga is not None
                and (ahora - _ultima_purga).total_seconds() < settings.CRM_DEDUP_PURGE_INTERVAL_SECONDS
            ):
                return 0
            _ultima_purga = ahora

    try:
        borradas = (
            db.query(WebhookDelivery)
            .filter(WebhookDelivery.expires_at < ahora)
            .delete(synchronize_session=False)
        )
        db.commit()
    except Exception:
        # La limpieza es housekeeping: que falle no puede tumbar la ingesta que la disparó.
        db.rollback()
        logger.exception("No fue posible purgar las entregas de webhook caducadas.")
        return 0

    if borradas:
        logger.info("Purga de entregas de webhook: %s fila(s) caducadas eliminadas.", borradas)
    return borradas


def reiniciar_reloj_de_purga() -> None:
    """Olvida cuándo fue la última purga. Solo lo usan las pruebas."""
    global _ultima_purga
    with _cerrojo_purga:
        _ultima_purga = None
