"""
¿La dirección pública configurada sigue llevando aquí? (capítulo 34)

Un túnel de prueba gratuito da una dirección **distinta en cada arranque**. Esa es la
propiedad que lo hace gratis y la que lo hace peligroso para lo que este sistema produce:
un enlace de publicación no se queda en el panel, se pega en un post de LinkedIn. Cuando la
dirección cambia, el post sigue publicado, la publicación sigue activa, el informe sigue
contando visitas —cero— y quien pulsa no llega a ninguna parte. Nada falla; simplemente
deja de funcionar, que es la forma de avería más cara de descubrir.

Hay dos preguntas distintas y este módulo contesta la primera:

1. **¿La dirección que hay configurada responde?** Es este archivo. Se pregunta saliendo a
   internet y volviendo a entrar por el túnel, porque es el camino que hace un visitante y
   cualquier atajo comprobaría otra cosa —desde dentro, el backend siempre se responde a sí
   mismo—.
2. **¿Los enlaces ya repartidos siguen apuntando a la dirección de ahora?** Esa vive en la
   publicación: `Campaign.url_base_publicada` guarda bajo qué dirección se activó, y
   `CampanaResponse.enlace_caducado` compara. No hace falta salir a ningún sitio para
   saberlo, y por eso son dos mecanismos y no uno.

Por qué la sonda pide un enlace que no existe
---------------------------------------------
`GET /interes/<slug>` devuelve **200 con etiquetas genéricas** para cualquier slug que no
sea de una publicación activa: es una decisión del capítulo 27, para que el código de
respuesta no diga desde fuera qué enlaces existen. Aquí sale gratis: se puede comprobar el
camino entero sin necesidad de que haya ninguna publicación activa, y sin tocar la de nadie.
"""
import datetime
import logging
import threading
from dataclasses import dataclass
from typing import Callable, Optional

import httpx

from app.core.config import settings
from app.models.entities import utc_now

logger = logging.getLogger(__name__)

# El slug de la sonda. Cumple la forma que aceptan la ruta pública y `main.jsx`
# (`[A-Za-z0-9_-]{6,64}`) y no puede chocar con uno real: los de verdad son 22 caracteres
# de `token_urlsafe`, aleatorios.
SLUG_DE_COMPROBACION = "comprobacion-de-la-direccion"

NO_COMPROBADA = "La comprobación está apagada (COMPROBAR_DIRECCION_PUBLICA)."


@dataclass(frozen=True)
class EstadoDeLaDireccion:
    """
    Qué se sabe de la dirección pública ahora mismo.

    `responde` es de tres valores a propósito: `True`, `False` y **`None`**. El tercero es
    «no se ha preguntado», y no es lo mismo que «no responde». Colapsarlos en un booleano
    haría que un despliegue con la comprobación apagada —el de desarrollo, el de la suite—
    enseñara una alarma permanente, y una alarma que está siempre encendida deja de leerse.
    """

    base: str
    responde: Optional[bool]
    comprobada_en: Optional[datetime.datetime]
    detalle: Optional[str] = None

    def como_dict(self) -> dict:
        return {
            "base": self.base,
            "responde": self.responde,
            "comprobada_en": self.comprobada_en.isoformat() if self.comprobada_en else None,
            "detalle": self.detalle,
        }


_candado = threading.Lock()
_ultimo: Optional[EstadoDeLaDireccion] = None


def _sonda_http(url: str, timeout: float) -> tuple[bool, str]:
    """
    Pide la dirección como la pediría un visitante y dice si llegó.

    Se acepta cualquier respuesta del propio sitio, no solo un 200: lo que se comprueba es
    que la dirección **lleva hasta aquí**, no que la publicación exista. Un 429 del límite
    de tasa significa que el camino funciona perfectamente.
    """
    try:
        respuesta = httpx.get(url, timeout=timeout, follow_redirects=True)
    except httpx.HTTPError as exc:
        # El mensaje de httpx lleva la URL y poco más; se guarda el tipo, que es lo que
        # distingue «no resuelve el nombre» de «resuelve y nadie contesta».
        return False, exc.__class__.__name__
    if respuesta.status_code >= 500:
        return False, f"HTTP {respuesta.status_code}"
    return True, f"HTTP {respuesta.status_code}"


def comprobar(
    *,
    ahora: Optional[datetime.datetime] = None,
    sonda: Optional[Callable[[str, float], tuple[bool, str]]] = None,
    forzar: bool = False,
) -> EstadoDeLaDireccion:
    """
    El estado de la dirección pública, con caché.

    `sonda` se inyecta en las pruebas. No hay ninguna versión de esta función que salga a
    internet sin que alguien lo haya pedido: con `COMPROBAR_DIRECCION_PUBLICA` apagada
    devuelve «no comprobada» sin abrir un socket.
    """
    global _ultimo
    ahora = ahora or utc_now()
    base = settings.PUBLICACIONES_URL_BASE

    if not settings.COMPROBAR_DIRECCION_PUBLICA:
        return EstadoDeLaDireccion(base=base, responde=None, comprobada_en=None, detalle=NO_COMPROBADA)

    with _candado:
        vigente = _ultimo
        if (
            not forzar
            and vigente is not None
            and vigente.base == base
            and vigente.comprobada_en is not None
            and (ahora - vigente.comprobada_en).total_seconds() < settings.DIRECCION_PUBLICA_CACHE_SEGUNDOS
        ):
            return vigente

    responde, detalle = (sonda or _sonda_http)(
        f"{base}/{SLUG_DE_COMPROBACION}", settings.DIRECCION_PUBLICA_TIMEOUT_SEGUNDOS
    )
    estado = EstadoDeLaDireccion(base=base, responde=responde, comprobada_en=ahora, detalle=detalle)

    if not responde:
        # A nivel de aviso y no de error: que el túnel esté caído es una condición de
        # operación normal en este despliegue —se apaga al apagar la PC—, no una avería del
        # servicio. El panel lo enseña; el registro deja constancia de desde cuándo.
        logger.warning(
            "La dirección pública configurada no responde: %s (%s). Los enlaces ya "
            "repartidos no llevan a ninguna parte hasta que se actualice "
            "PUBLICACIONES_URL_BASE o se vuelva a levantar el túnel.",
            base,
            detalle,
        )

    with _candado:
        _ultimo = estado
    return estado


def olvidar_lo_comprobado() -> None:
    """Vacía la caché. La usan las pruebas y el arranque; no hay ruta que la exponga."""
    global _ultimo
    with _candado:
        _ultimo = None
