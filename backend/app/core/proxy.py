"""
De dónde viene una petición.

Hay dos consumidores de este dato y conviene que compartan una única respuesta: la
limitación de tasa, que cuenta por cliente, y la bitácora de auditoría, que registra
desde dónde se hizo cada operación sensible. Si cada uno resolviera la IP a su manera,
acabarían discrepando justo cuando hace falta cruzarlos —un bloqueo por fuerza bruta
atribuido a una IP y el intento de login registrado con otra—.

`X-Forwarded-For` la escribe quien quiera. Solo se le hace caso cuando el despliegue
declara que hay un proxy de confianza por delante que la reescribe (`TRUST_PROXY_HEADERS`);
expuesto directamente a internet, creerla significa que basta con rotar la cabecera para
que cada petición cuente como un cliente nuevo y el límite de tasa deje de existir.
"""
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

CABECERA_REENVIO = "x-forwarded-for"

# Valor de reserva cuando Starlette no informa el cliente. Ocurre con transportes que no
# son TCP —el `TestClient` de la suite, un ASGI montado sobre memoria—; devolver None
# haría estallar al limitador, que espera una cadena.
IP_DESCONOCIDA = "desconocida"


def ip_del_cliente(request) -> str:
    """
    IP del solicitante, atendiendo a `X-Forwarded-For` solo si el entorno lo autoriza.

    Del encadenamiento `cliente, proxy1, proxy2` se toma el primer elemento, que es el
    cliente original. Es el que un atacante también controla, y por eso la cabecera entera
    se ignora salvo que `TRUST_PROXY_HEADERS` esté activa: fiarse de ella sin un proxy que
    la reescriba convierte el tope por IP en un adorno.
    """
    if settings.TRUST_PROXY_HEADERS:
        reenviada = request.headers.get(CABECERA_REENVIO)
        if reenviada:
            primera = reenviada.split(",")[0].strip()
            if primera:
                return primera

    cliente = getattr(request, "client", None)
    host: Optional[str] = getattr(cliente, "host", None) if cliente else None
    return host or IP_DESCONOCIDA


def avisar_de_confianza_en_proxy() -> None:
    """
    Deja constancia en el arranque de cómo se está identificando al cliente.

    Se llama desde el `lifespan` y no al importar: la configuración de logging se
    establece en `main`, así que un aviso emitido en tiempo de importación se pierde.
    """
    if settings.TRUST_PROXY_HEADERS:
        logger.info(
            "TRUST_PROXY_HEADERS activa: la IP del cliente se toma de X-Forwarded-For. "
            "Esto SOLO es correcto si todo el tráfico entra por un proxy de confianza que "
            "reescriba esa cabecera; si el backend es alcanzable directamente, cualquiera "
            "puede falsearla y esquivar la limitación de tasa."
        )
    else:
        logger.info(
            "TRUST_PROXY_HEADERS desactivada: la IP del cliente se toma de la conexión. "
            "Detrás de un proxy (el nginx de la pila de compose) esto hace que todo el "
            "tráfico cuente como un único cliente; actívela en ese despliegue."
        )
