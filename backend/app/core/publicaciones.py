"""
Publicaciones: campañas con canal LinkedIn y su enlace público.

Una publicación no es una entidad propia. Es una `Campaign` cuyo canal es `CANAL_LINKEDIN`,
con una descripción, a quién va dirigida y un enlace público. Crear una tabla aparte
habría dado dos sitios donde mirar de dónde vino un prospecto y dos informes que no
cuadran (regla R-2 del guion «Del post de LinkedIn al prospecto puntuado»).

El enlace público
-----------------
El enlace lleva un identificador (`public_slug`) que cumple dos cosas:

* **No se puede adivinar.** Son 16 bytes de `secrets` (128 bits) en base64 URL: 22
  caracteres. No sale del nombre ni del id de la campaña. Si saliera de ellos, cualquiera
  podría recorrer las publicaciones probando números o títulos, y enviar respuestas a una
  que no le enseñaron.
* **No se reutiliza.** Lo genera el servidor al crear la campaña y ninguna edición lo
  cambia: no está en los esquemas de entrada. Las campañas no se borran, solo se desactivan,
  y el índice único `uq_campaigns_public_slug` impide que otra fila lleve el mismo. Un
  enlace ya publicado en LinkedIn apunta siempre a la misma campaña, también después de
  desactivarla.

El ciclo de vida (capítulo 26)
------------------------------
Una publicación pasa por cuatro estados: **borrador** (se está escribiendo; el enlace existe
pero no sirve), **activa** (la página recibe perfiles), **pausada** (se deja de recibir sin
darla por terminada) y **cerrada** (terminó). Solo una activa enseña su página; el resto
responde «no disponible», con el mismo texto que un enlace inventado.

La fecha de fin (`end_date`) es la **fecha de cierre automática**: una publicación activa o
pausada cuya fecha ya pasó se cierra sola. No hay tarea programada que vigilarla: se cierra
la primera vez que alguien mira —la página, la lista, el informe—, antes de contestar. Así
no depende de que un proceso aparte esté vivo, y nunca se sirve una página vencida.

`is_active` sigue existiendo y se mantiene igual a «está activa»: el resto del sistema —el
listado de campañas, la baja lógica— lo lee desde antes de que hubiera estados.
"""
import re
import secrets
import unicodedata
from typing import Dict, List, Optional
from urllib.parse import urlsplit

from app.core.config import settings

CANAL_LINKEDIN = "LinkedIn"

BYTES_DEL_SLUG = 16
# `token_urlsafe(16)` produce siempre 22 caracteres: 16 bytes en base64 sin relleno.
LONGITUD_DEL_SLUG = 22

# El tope de una publicación de LinkedIn es de 3 000 caracteres. La descripción se limita
# por debajo para que el texto copiado —descripción, línea en blanco y enlace— quepa entero
# con cualquier dirección base razonable.
MAX_TEXTO_DE_LINKEDIN = 3000
MAX_DESCRIPCION = 2800
MAX_PUBLICO = 300


def nuevo_slug_publico() -> str:
    return secrets.token_urlsafe(BYTES_DEL_SLUG)


def base_publica() -> str:
    """
    La dirección bajo la que vive todo lo público, leída del ajuste y de ningún otro sitio.

    Existe para que nadie tenga que escribir `settings.PUBLICACIONES_URL_BASE` fuera de
    aquí: es la pieza que el capítulo 34 necesita que tenga **un solo dueño**, porque pasar
    de la dirección efímera de un túnel a un dominio propio tiene que ser cambiar un valor
    y nada más. Cada copia suelta sería un sitio donde ese cambio se olvidaría.
    """
    return settings.PUBLICACIONES_URL_BASE


def enlace_publico(slug: str) -> str:
    return f"{base_publica()}/{slug}"


def texto_para_linkedin(descripcion: str | None, slug: str) -> str:
    """Lo que el botón «Copiar texto para LinkedIn» deja en el portapapeles."""
    enlace = enlace_publico(slug)
    descripcion = (descripcion or "").strip()
    return f"{descripcion}\n\n{enlace}" if descripcion else enlace


# --------------------------------------------------------------------------- estados
BORRADOR = "borrador"
ACTIVA = "activa"
PAUSADA = "pausada"
CERRADA = "cerrada"
ESTADOS = (BORRADOR, ACTIVA, PAUSADA, CERRADA)
# Los que la fecha de cierre puede cerrar. Un borrador no se cierra solo: nunca se abrió.
CIERRAN_POR_FECHA = (ACTIVA, PAUSADA)


# ----------------------------------------------------------------- «¿Qué necesitas?»
# Las opciones de siempre. Una publicación sin opciones propias usa estas.
NECESIDADES_POR_DEFECTO: Dict[str, str] = {
    "vacantes": "Cubrir vacantes de TI",
    "equipo": "Formar un equipo completo",
    "demo": "Ver una demostración",
    "explorando": "Solo estoy explorando",
}
MIN_NECESIDADES = 2
MAX_NECESIDADES = 5
# Botones de un toque, dos por fila en un teléfono de 375 px: una etiqueta más larga no
# cabe en dos líneas.
MAX_ETIQUETA_DE_NECESIDAD = 40
MIN_ETIQUETA_DE_NECESIDAD = 2
MAX_CLAVE_DE_NECESIDAD = 40
CLAVE_DE_NECESIDAD = re.compile(r"^[a-z0-9_]{1,40}$")


def clave_de_necesidad(etiqueta: str) -> str:
    """
    «Ver una demostración» → `ver_una_demostracion`. La clave es lo que viaja y se guarda;
    se deriva de la etiqueta para que el líder solo escriba la etiqueta.
    """
    plano = unicodedata.normalize("NFKD", etiqueta).encode("ascii", "ignore").decode("ascii")
    clave = re.sub(r"[^a-z0-9]+", "_", plano.lower()).strip("_")
    return clave[:MAX_CLAVE_DE_NECESIDAD].strip("_")


def necesidades_de(configuradas: Optional[List[dict]]) -> Dict[str, str]:
    """Las opciones de una publicación, en su orden: las suyas o las de siempre."""
    if not configuradas:
        return dict(NECESIDADES_POR_DEFECTO)
    return {o["clave"]: o["etiqueta"] for o in configuradas}


def normalizar_necesidades(etiquetas: List[str]) -> List[dict]:
    """
    Valida y convierte las etiquetas que escribe el líder en `[{clave, etiqueta}]`.

    Lanza `ValueError` con un mensaje para la persona. Son de 2 a 5: con una sola no hay
    nada que elegir, y con más de cinco los botones ya no caben en la pantalla del teléfono
    sin desplazarse.
    """
    limpias = [" ".join(str(e).split()) for e in etiquetas]
    if not MIN_NECESIDADES <= len(limpias) <= MAX_NECESIDADES:
        raise ValueError(f"Hacen falta entre {MIN_NECESIDADES} y {MAX_NECESIDADES} opciones.")
    opciones, claves = [], set()
    for etiqueta in limpias:
        if not MIN_ETIQUETA_DE_NECESIDAD <= len(etiqueta) <= MAX_ETIQUETA_DE_NECESIDAD:
            raise ValueError(
                f"Cada opción tiene entre {MIN_ETIQUETA_DE_NECESIDAD} y "
                f"{MAX_ETIQUETA_DE_NECESIDAD} caracteres: «{etiqueta}» no."
            )
        clave = clave_de_necesidad(etiqueta)
        if not clave:
            raise ValueError(f"«{etiqueta}» necesita al menos una letra o un número.")
        if clave in claves:
            raise ValueError(f"«{etiqueta}» está repetida.")
        claves.add(clave)
        opciones.append({"clave": clave, "etiqueta": etiqueta})
    return opciones


# ---------------------------------------------------------------------- el post real
MAX_URL_DEL_POST = 300


def normalizar_url_del_post(valor: Optional[str]) -> Optional[str]:
    """
    La dirección del post ya publicado, o `None`. Tiene que ser de LinkedIn de verdad.

    Se comprueba el **nombre de la máquina**, no que el texto contenga «linkedin.com»:
    `https://linkedin.com.ejemplo.net/…` o `https://ejemplo.net/?linkedin.com` lo contienen y
    llevan a otra parte, y este enlace lo abre el líder desde el informe. Solo `https`, sin
    usuario ni contraseña en la dirección, y se quitan los parámetros de campaña que añade
    el botón «compartir».
    """
    if valor is None:
        return None
    limpio = valor.strip()
    if not limpio:
        return None
    if "://" not in limpio:
        limpio = f"https://{limpio}"
    partes = urlsplit(limpio)
    maquina = (partes.hostname or "").lower()
    if (
        partes.scheme != "https"
        or partes.username is not None
        or partes.password is not None
        or partes.port not in (None, 443)
        or not (maquina == "linkedin.com" or maquina.endswith(".linkedin.com"))
        or len(partes.path) <= 1
    ):
        raise ValueError(
            "La dirección del post tiene que ser de LinkedIn, como "
            "https://www.linkedin.com/posts/..."
        )
    normalizada = f"https://{maquina}{partes.path}"
    if len(normalizada) > MAX_URL_DEL_POST:
        raise ValueError(f"La dirección del post no puede pasar de {MAX_URL_DEL_POST} caracteres.")
    return normalizada
