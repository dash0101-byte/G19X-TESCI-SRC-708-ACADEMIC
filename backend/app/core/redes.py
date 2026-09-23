"""
Una publicación, varias redes (capítulo 27).

El mismo post se difunde por más de un sitio. Hasta el capítulo 26 la página de interés
tenía un solo enlace y todo el que llegaba se registraba como «LinkedIn», que era verdad
mientras el enlace solo se pegaba en LinkedIn y dejó de serlo en cuanto alguien lo reenvió
por WhatsApp. Aquí cada red tiene **su propio enlace a la misma página**, y por dónde llegó
cada persona queda registrado.

Cómo viaja la red
-----------------
En un parámetro de la dirección: `…/interes/<slug>?r=whatsapp`. No en el `slug` —el enlace
apunta a la misma publicación, y un slug por red multiplicaría los enlaces que hay que
mantener— ni en una cookie, que es justo lo que esta página no pone.

El parámetro lo puede cambiar cualquiera. No es una credencial y no decide nada: solo
etiqueta de dónde vino la visita. Por eso **una red desconocida no rechaza el envío**; se
registra como «sin red» y la persona pasa igual. Rechazar convertiría un adorno de
analítica en una puerta que se puede cerrar desde fuera editando la dirección.

Una red que existe pero que el líder no activó **sí se registra**. El líder activa las redes
para decidir qué botones y qué textos quiere, no para invalidar enlaces: si desactiva
WhatsApp después de haberlo difundido, lo que ya está compartido sigue llegando y sigue
contándose donde toca. Lo contrario reescribiría el origen de gente que llegó de verdad por
ahí.

El canal del prospecto
----------------------
La ficha se guarda con el canal de la red de llegada («WhatsApp», «Facebook»…). El modelo
**no conoce ninguno de estos canales**: sus `source_channel` son «LinkedIn Ads», «Webinar»,
«Demo Request Form», «Organic Search», «Outbound Cold Email» y «Referral». Como el
preprocesador descarta las categorías que no vio al entrenar
(`OneHotEncoder(handle_unknown="ignore")`), un canal nuevo es un canal desconocido, es
decir, **neutro**: no suma ni resta. Es exactamente lo que ya pasaba con «LinkedIn» desde
el capítulo 25. Escribir «LinkedIn Ads» para que puntuara sería declarar publicidad pagada
donde hubo un post orgánico. Reentrenar con estos canales queda fuera de esta fase.

Sin API ni cuentas
------------------
No se publica nada por nosotros. Los botones «Compartir en…» abren los **enlaces oficiales
de compartir** de cada red, que son direcciones públicas y no necesitan clave, aplicación
registrada ni sesión iniciada por el sistema: abre la red en el navegador de quien pulsa,
con su propia sesión, y publica esa persona. Donde la red no acepta el texto por la
dirección (LinkedIn y Facebook solo toman el enlace), al lado va «Copiar texto».
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import quote, urlencode

from app.core.publicaciones import MAX_TEXTO_DE_LINKEDIN, enlace_publico

# --------------------------------------------------------------------------- las redes
LINKEDIN = "linkedin"
WHATSAPP = "whatsapp"
FACEBOOK = "facebook"
CORREO = "correo"
INSTAGRAM = "instagram"
X = "x"

# Cómo se llama en la dirección: `?r=whatsapp`. Corto porque el enlace se pega a mano y se
# lee en voz alta, y se ve entero en la vista previa de la mayoría de las aplicaciones.
PARAMETRO_DE_RED = "r"

# Lo que se registra cuando no hay red, la que viene no existe o alguien la manipuló.
SIN_RED = "sin_red"
ETIQUETA_SIN_RED = "Sin red"
# Canal de la ficha cuando no se sabe por dónde llegó. No se pone «LinkedIn»: el enlace se
# pudo compartir desde cualquier sitio, y escribir una red que no consta sería inventarla.
CANAL_SIN_RED = "Publicación"

# Una clave de red es minúsculas y poco más: lo que llegue con otra forma ni se busca.
CLAVE_DE_RED = re.compile(r"^[a-z][a-z0-9_]{0,19}$")


@dataclass(frozen=True)
class Red:
    clave: str
    etiqueta: str
    # El canal con el que se guarda la ficha de quien llega por aquí.
    canal: str
    # Si viene activada al crear una publicación.
    por_defecto: bool
    # Si su enlace oficial de compartir acepta el texto además del enlace. Cuando no, la
    # página ofrece «Copiar texto» junto al botón.
    admite_texto: bool
    # Cuántos caracteres caben en el texto de esta red, enlace incluido. `None`: los de la
    # publicación entera.
    maximo: Optional[int] = None
    # Aviso para quien va a compartir, cuando la red tiene una pega que hay que saber.
    aviso: Optional[str] = None


# El tope de una publicación de X, contando el enlace. X acorta cualquier dirección a 23
# caracteres con `t.co`, pero aquí se cuentan los caracteres **de verdad** del enlace: si se
# contaran 23 y X cambiara esa regla, el texto se pasaría de largo sin que nada avisara.
# Contando de más el recorte es conservador y nunca se pasa.
MAX_X = 280
# WhatsApp y el correo se leen en una notificación o en una vista previa de bandeja, no en
# un muro. Lo que no entra en las primeras líneas no lo lee nadie.
MAX_WHATSAPP = 400
MAX_CORREO = 600

REDES: Dict[str, Red] = {
    LINKEDIN: Red(
        clave=LINKEDIN,
        etiqueta="LinkedIn",
        canal="LinkedIn",
        por_defecto=True,
        admite_texto=False,
        maximo=MAX_TEXTO_DE_LINKEDIN,
        aviso="LinkedIn solo recibe el enlace: copia el texto y pégalo en el post.",
    ),
    WHATSAPP: Red(
        clave=WHATSAPP,
        etiqueta="WhatsApp",
        canal="WhatsApp",
        por_defecto=True,
        admite_texto=True,
        maximo=MAX_WHATSAPP,
    ),
    FACEBOOK: Red(
        clave=FACEBOOK,
        etiqueta="Facebook",
        canal="Facebook",
        por_defecto=True,
        admite_texto=False,
        maximo=MAX_TEXTO_DE_LINKEDIN,
        aviso="Facebook solo recibe el enlace: copia el texto y pégalo en la publicación.",
    ),
    CORREO: Red(
        clave=CORREO,
        etiqueta="Correo",
        canal="Correo",
        por_defecto=True,
        admite_texto=True,
        maximo=MAX_CORREO,
    ),
    INSTAGRAM: Red(
        clave=INSTAGRAM,
        etiqueta="Instagram",
        canal="Instagram",
        por_defecto=False,
        admite_texto=False,
        maximo=MAX_TEXTO_DE_LINKEDIN,
        aviso=(
            "Instagram no deja enlaces en el pie de una publicación: pon el enlace en la "
            "biografía o en una historia, o comparte el código QR."
        ),
    ),
    X: Red(
        clave=X,
        etiqueta="X",
        canal="X",
        por_defecto=False,
        admite_texto=True,
        maximo=MAX_X,
    ),
}

ORDEN = (LINKEDIN, WHATSAPP, FACEBOOK, CORREO, INSTAGRAM, X)
POR_DEFECTO: List[str] = [c for c in ORDEN if REDES[c].por_defecto]

# Los canales con los que la página de interés guarda una ficha, incluido el de «sin red».
# El contador de prospectos sin asesor los busca por aquí: desde el capítulo 27 una ficha de
# una publicación puede tener seis canales distintos, y buscar solo «LinkedIn» dejaría de
# ver a la mayoría.
CANALES_DE_PUBLICACION: List[str] = [REDES[c].canal for c in ORDEN] + [CANAL_SIN_RED]

MIN_REDES = 1


def etiqueta_de(red: Optional[str]) -> str:
    """Cómo se llama esta red en la pantalla. «Sin red» para lo que no se reconoció."""
    entrada = REDES.get(red or "")
    return entrada.etiqueta if entrada else ETIQUETA_SIN_RED


def canal_de(red: Optional[str]) -> str:
    """El canal con el que se guarda la ficha de quien llegó por esta red."""
    entrada = REDES.get(red or "")
    return entrada.canal if entrada else CANAL_SIN_RED


def redes_de(configuradas: Optional[List[str]]) -> List[str]:
    """Las redes activas de una publicación, en su orden: las suyas o las de siempre."""
    if not configuradas:
        return list(POR_DEFECTO)
    return [c for c in ORDEN if c in set(configuradas)]


def normalizar_redes(claves: List[str]) -> List[str]:
    """
    Valida lo que activa el líder. Lanza `ValueError` con un mensaje para la persona.

    Se guarda en el orden fijo de `ORDEN` y sin repetidas: el orden de los botones no es una
    preferencia que haya que recordar, y dos veces la misma red no significa nada.
    """
    limpias = [str(c).strip().lower() for c in claves]
    desconocidas = [c for c in limpias if c not in REDES]
    if desconocidas:
        raise ValueError(f"Red desconocida: {', '.join(sorted(set(desconocidas)))}.")
    activas = [c for c in ORDEN if c in set(limpias)]
    if len(activas) < MIN_REDES:
        raise ValueError("Hace falta al menos una red de difusión.")
    return activas


def normalizar_red_de_llegada(valor: Optional[str]) -> Optional[str]:
    """
    La red con la que llegó una visita, o `None` si no se reconoce.

    `None` es «sin red» y **nunca** un error: quien llega con el parámetro borrado, cambiado
    o inventado entra igual y se cuenta aparte.

    El recorte a veinte caracteres no decide nada —el patrón ya rechaza cualquier cosa más
    larga—: está para no gastar trabajo normalizando un parámetro de un megabyte que iba a
    caer igual.
    """
    if not valor:
        return None
    limpio = str(valor).strip().lower()[:20]
    return limpio if CLAVE_DE_RED.match(limpio) and limpio in REDES else None


# ------------------------------------------------------------------------- los enlaces
def enlace_de_red(slug: str, red: Optional[str]) -> str:
    """El enlace a la misma página de interés, etiquetado con la red."""
    base = enlace_publico(slug)
    if red is None or red not in REDES:
        return base
    return f"{base}?{PARAMETRO_DE_RED}={red}"


# --------------------------------------------------------------------------- los textos
def _recortar(texto: str, maximo: int) -> str:
    """
    Recorta por palabras y remata con «…». Cortar a mitad de palabra deja textos que
    parecen un error de programa y no un resumen.
    """
    if len(texto) <= maximo:
        return texto
    if maximo <= 1:
        return "…"[:maximo]
    hueco = texto[: maximo - 1].rstrip()
    corte = hueco.rfind(" ")
    if corte > maximo // 2:
        hueco = hueco[:corte].rstrip()
    return f"{hueco.rstrip(',.;:')}…"


def texto_para(red: Optional[str], descripcion: Optional[str], slug: str) -> str:
    """
    El texto de esta red: el de la publicación, recortado a lo que cabe, y su enlace.

    **El enlace nunca se recorta.** Cuando no cabe todo, lo que cede es la descripción: un
    texto cortado sigue diciendo algo y un enlace cortado no lleva a ninguna parte. Si ni
    siquiera el enlace cabe en el tope de la red, se manda el enlace solo: es preferible
    pasarse en una red que repartir un enlace roto.
    """
    entrada = REDES.get(red or "")
    enlace = enlace_de_red(slug, red)
    descripcion = (descripcion or "").strip()
    if not descripcion:
        return enlace
    if entrada is None or entrada.maximo is None:
        return f"{descripcion}\n\n{enlace}"
    # Los dos saltos de línea que separan el texto del enlace también ocupan.
    disponible = entrada.maximo - len(enlace) - 2
    if disponible <= 0:
        return enlace
    return f"{_recortar(descripcion, disponible)}\n\n{enlace}"


def textos_por_red(descripcion: Optional[str], slug: str, activas: List[str]) -> Dict[str, str]:
    return {red: texto_para(red, descripcion, slug) for red in activas}


# ---------------------------------------------------- los enlaces oficiales de compartir
def _compartir_linkedin(texto: str, enlace: str) -> str:
    # Solo acepta la dirección; el texto lo pega quien publica.
    return "https://www.linkedin.com/sharing/share-offsite/?" + urlencode({"url": enlace})


def _compartir_facebook(texto: str, enlace: str) -> str:
    # Igual que LinkedIn: `u` es lo único que lee.
    return "https://www.facebook.com/sharer/sharer.php?" + urlencode({"u": enlace})


def _compartir_x(texto: str, enlace: str) -> str:
    # `text` ya trae el enlace dentro (lo pone `texto_para`), así que no se manda `url`
    # aparte: lo añadiría una segunda vez y el recorte a 280 dejaría de cuadrar.
    return "https://x.com/intent/post?" + urlencode({"text": texto})


def _compartir_whatsapp(texto: str, enlace: str) -> str:
    return "https://wa.me/?" + urlencode({"text": texto})


def _compartir_correo(texto: str, enlace: str, asunto: str = "") -> str:
    # `mailto:` abre el programa de correo de quien pulsa. No manda nada por su cuenta.
    return "mailto:?" + urlencode({"subject": asunto, "body": texto}, quote_via=quote)


COMPARTEN = {
    LINKEDIN: _compartir_linkedin,
    FACEBOOK: _compartir_facebook,
    X: _compartir_x,
    WHATSAPP: _compartir_whatsapp,
    CORREO: _compartir_correo,
}


def enlace_de_compartir(
    red: Optional[str], texto: str, slug: str, asunto: str = ""
) -> Optional[str]:
    """
    La dirección oficial de compartir de esta red, o `None` si no tiene.

    Instagram no tiene: no ofrece ninguna dirección pública para compartir desde la web. Su
    fila lleva «Copiar texto» y el código QR, y el aviso de que el enlace va en la biografía
    o en una historia.
    """
    if red == CORREO:
        return _compartir_correo(texto, enlace_de_red(slug, red), asunto)
    constructor = COMPARTEN.get(red or "")
    return constructor(texto, enlace_de_red(slug, red)) if constructor else None
