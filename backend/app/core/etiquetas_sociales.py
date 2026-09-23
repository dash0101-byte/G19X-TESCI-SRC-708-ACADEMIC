"""
La tarjeta que enseñan las redes al pegar el enlace de una publicación (capítulo 27).

Cuando alguien pega `…/interes/<slug>` en LinkedIn, WhatsApp, Facebook o X, la red pide esa
dirección **como un programa, no como un navegador**: descarga el HTML y lee sus etiquetas.
No ejecuta JavaScript. Hasta aquí la página era la aplicación de React entera, así que lo
que el rastreador leía era el `<title>` genérico del panel y ninguna descripción: el enlace
salía como una tarjeta vacía con el nombre del sistema.

Por eso el HTML de esa ruta lo sirve el **servidor**, ya con las etiquetas dentro. La
aplicación se carga después, igual que antes, para quien sí es un navegador.

Qué se dice y qué no
--------------------
Solo de una publicación **activa** se dicen su título y su texto. Un borrador, una pausada,
una cerrada y un enlace inventado dan las **mismas** etiquetas genéricas, sin una palabra de
lo que contienen. Y el HTML responde 200 en los cuatro casos, con el mismo cuerpo: si
respondiera 404 para unos y 200 para otros, el código de respuesta diría desde fuera qué
enlaces existen, que es justo lo que el capítulo 26 cerró al dar «no disponible» idéntico a
los cuatro. Quien abre la página se entera por la API, que contesta lo mismo para todos.

El escape
---------
Todo lo que viene de la base pasa por `html.escape(..., quote=True)` antes de entrar en el
documento. El título de una publicación lo escribe una persona: unas comillas cierran el
atributo `content="…"` y lo que venga detrás deja de ser texto para pasar a ser marcado. No
es un peligro hipotético —el título ya admite cualquier carácter desde el capítulo 25— y el
único sitio donde importa es este, porque es el único que construye HTML a mano.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Optional

# Lo que se enseña cuando no hay nada que enseñar.
TITULO_GENERICO = "PluriOne · Sistema Inteligente de Lead Scoring"
DESCRIPCION_GENERICA = (
    "Equipos de TI listos en semanas, con perfiles probados y acompañamiento. "
    "Cuéntanos qué necesitas y te escribimos."
)
NOMBRE_DEL_SITIO = "PluriOne"
IDIOMA = "es_MX"

# Las redes recortan la descripción por su cuenta; se manda ya recortada para que el corte
# lo decida este lado y no cada red por separado.
MAX_TITULO = 90
MAX_DESCRIPCION = 200
CORTE = "…"

# Caracteres de control: no se ven, no aportan nada y algunos rompen el análisis del HTML.
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@dataclass(frozen=True)
class Tarjeta:
    """Lo que las redes van a leer. Texto plano: el escape se hace al construir el HTML."""
    titulo: str
    descripcion: str
    url: str
    imagen: str
    # `alt` de la imagen: lo que lee quien no la ve.
    imagen_alt: str


def _limpiar(valor: Optional[str], maximo: int) -> str:
    texto = CONTROL.sub("", " ".join((valor or "").split()))
    if len(texto) <= maximo:
        return texto
    hueco = texto[: maximo - 1].rstrip()
    corte = hueco.rfind(" ")
    if corte > maximo // 2:
        hueco = hueco[:corte].rstrip()
    return f"{hueco.rstrip(',.;:')}{CORTE}"


def tarjeta_generica(url: str, imagen: str) -> Tarjeta:
    return Tarjeta(
        titulo=TITULO_GENERICO,
        descripcion=DESCRIPCION_GENERICA,
        url=url,
        imagen=imagen,
        imagen_alt=NOMBRE_DEL_SITIO,
    )


def tarjeta_de(titulo: Optional[str], descripcion: Optional[str], url: str, imagen: str) -> Tarjeta:
    """La tarjeta de una publicación activa. Sin título utilizable, la genérica."""
    limpio = _limpiar(titulo, MAX_TITULO)
    if not limpio:
        return tarjeta_generica(url, imagen)
    return Tarjeta(
        titulo=limpio,
        descripcion=_limpiar(descripcion, MAX_DESCRIPCION) or DESCRIPCION_GENERICA,
        url=url,
        imagen=imagen,
        imagen_alt=limpio,
    )


# ------------------------------------------------------------------------- el documento
def _e(valor: str) -> str:
    """Escape para meter texto dentro de un atributo HTML."""
    return html.escape(str(valor), quote=True)


def etiquetas(tarjeta: Tarjeta, ancho: int, alto: int) -> str:
    """
    Las etiquetas de la cabecera, en el orden en que se leen.

    Se ponen las de **Open Graph** y las de **X**. Open Graph la leen LinkedIn, WhatsApp y
    Facebook; X tiene las suyas y, sin `twitter:card`, enseña una tarjeta pequeña con la
    imagen recortada a un cuadrado.
    """
    titulo, descripcion = _e(tarjeta.titulo), _e(tarjeta.descripcion)
    url, imagen, alt = _e(tarjeta.url), _e(tarjeta.imagen), _e(tarjeta.imagen_alt)
    return "\n".join([
        f'    <title>{html.escape(tarjeta.titulo)}</title>',
        f'    <meta name="description" content="{descripcion}" />',
        f'    <link rel="canonical" href="{url}" />',
        '',
        '    <meta property="og:type" content="website" />',
        f'    <meta property="og:site_name" content="{_e(NOMBRE_DEL_SITIO)}" />',
        f'    <meta property="og:locale" content="{_e(IDIOMA)}" />',
        f'    <meta property="og:title" content="{titulo}" />',
        f'    <meta property="og:description" content="{descripcion}" />',
        f'    <meta property="og:url" content="{url}" />',
        f'    <meta property="og:image" content="{imagen}" />',
        f'    <meta property="og:image:width" content="{ancho}" />',
        f'    <meta property="og:image:height" content="{alto}" />',
        f'    <meta property="og:image:alt" content="{alt}" />',
        '',
        # `summary_large_image` es lo que hace que X dibuje la imagen ancha en vez de un
        # cuadradito al lado del título.
        '    <meta name="twitter:card" content="summary_large_image" />',
        f'    <meta name="twitter:title" content="{titulo}" />',
        f'    <meta name="twitter:description" content="{descripcion}" />',
        f'    <meta name="twitter:image" content="{imagen}" />',
        f'    <meta name="twitter:image:alt" content="{alt}" />',
    ])


def documento(tarjeta: Tarjeta, ancho: int, alto: int, script: str, hoja: Optional[str]) -> str:
    """
    El HTML completo de `/interes/{slug}`.

    Lleva las etiquetas, un `<h1>` y un párrafo con lo mismo —para quien llegue sin
    JavaScript y para los lectores de pantalla mientras carga la aplicación— y el arranque
    de la SPA. React sustituye el contenido de `#root` en cuanto se monta.
    """
    estilo = f'    <link rel="stylesheet" href="{_e(hoja)}" />\n' if hoja else ""
    return f"""<!DOCTYPE html>
<html lang="es">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
{etiquetas(tarjeta, ancho, alto)}
{estilo}  </head>
  <body>
    <div id="root">
      <noscript>
        <h1>{html.escape(tarjeta.titulo)}</h1>
        <p>{html.escape(tarjeta.descripcion)}</p>
        <p>Para enviar tus datos hace falta activar JavaScript.</p>
      </noscript>
    </div>
    <script type="module" src="{_e(script)}"></script>
  </body>
</html>
"""
