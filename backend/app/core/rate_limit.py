"""
Limitación de tasa por IP para los tres endpoints que un atacante puede abusar sin
tener credenciales válidas.

* `POST /auth/login` — fuerza bruta de contraseñas. bcrypt ya encarece cada intento;
  esto acota además cuántos puede encadenar una misma IP.
* `POST /crm/webhook` — aunque exige firma HMAC, un secreto filtrado permitiría inundar
  la base de datos con prospectos falsos, y cada evento dispara el pipeline de scoring.
* `POST /scoring/predict` — cada llamada ejecuta inferencia y generación de texto; es la
  ruta más cara del sistema y basta un token válido para invocarla en bucle.

Los límites se resuelven **en cada petición** (slowapi acepta un invocable como valor),
no al declarar el endpoint. Así se recalibran por variable de entorno sin reconstruir la
imagen, y las pruebas pueden estrecharlos para comprobar que el corte existe de verdad.
"""
import logging

from app.core.config import settings
from app.core.proxy import ip_del_cliente
from slowapi import Limiter

logger = logging.getLogger(__name__)


def _client_key(request) -> str:
    """
    Identifica al cliente por IP.

    La resolución vive en `app.core.proxy` y no aquí porque la bitácora de auditoría
    necesita exactamente la misma respuesta: si el limitador y la bitácora discreparan,
    un bloqueo por fuerza bruta quedaría atribuido a una IP y el intento de login que lo
    provocó a otra, que es justo el cruce que se querría hacer al investigarlo.
    """
    return ip_del_cliente(request)


limiter = Limiter(
    key_func=_client_key,
    # `enabled` se apaga en las pruebas que no ejercitan el límite y se puede desactivar
    # por completo en entornos donde el corte lo aplique un balanceador por delante.
    enabled=settings.RATE_LIMIT_ENABLED,
    headers_enabled=True,
    # Con el almacén en memoria (el de por defecto) cada worker de uvicorn lleva su propia
    # cuenta, de modo que el tope efectivo es el declarado por el número de workers. Basta
    # para frenar la fuerza bruta, pero no es un límite exacto: apuntando
    # `RATE_LIMIT_STORAGE_URI` a Redis, la cuenta pasa a ser común a todos los procesos y
    # a todas las instancias.
    storage_uri=settings.RATE_LIMIT_STORAGE_URI,
)

def avisar_de_almacen_en_memoria() -> None:
    """
    Deja constancia en el arranque de que el tope no es exacto con varios workers.

    Se llama desde el `lifespan` y no al importar el módulo: la configuración de logging
    se establece en `main`, así que un aviso emitido en tiempo de importación se pierde
    —comprobado: no aparecía en los logs del contenedor—.
    """
    if not settings.RATE_LIMIT_ENABLED:
        logger.warning("Limitación de tasa DESACTIVADA (RATE_LIMIT_ENABLED=false).")
        return

    if settings.RATE_LIMIT_STORAGE_URI.startswith("memory://"):
        logger.warning(
            "Limitación de tasa con almacén en memoria: cada worker lleva su propia cuenta, "
            "de modo que el tope que percibe un cliente es el declarado multiplicado por el "
            "número de workers. Defina RATE_LIMIT_STORAGE_URI (por ejemplo redis://host:6379/0) "
            "para un límite exacto y compartido entre procesos e instancias."
        )


def login_limit() -> str:
    return settings.RATE_LIMIT_LOGIN


def predict_limit() -> str:
    return settings.RATE_LIMIT_PREDICT


def webhook_limit() -> str:
    return settings.RATE_LIMIT_WEBHOOK
