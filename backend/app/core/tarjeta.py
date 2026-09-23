"""
La imagen de vista previa de una publicación: 1 200 × 630, generada aquí (capítulo 27).

Cuando alguien pega el enlace de una publicación en LinkedIn, WhatsApp o X, la red pide la
página, lee sus etiquetas y dibuja una tarjeta. Sin imagen, la tarjeta sale con un hueco
gris; con ella, el enlace se reconoce de un vistazo.

Por qué se dibuja aquí y no se pide a un servicio
-------------------------------------------------
Los generadores de tarjetas se usan mandándoles el título por una dirección. Eso significa
contarle a un tercero qué publica esta empresa y cuándo, que es justo lo que el resto de
esta parte del sistema evita. Se dibuja en el servidor, con Pillow, y no sale nada.

**Pillow solo escribe.** No se abre aquí ninguna imagen que venga de fuera, que es donde
está históricamente la superficie de esta biblioteca: se crea un lienzo en blanco, se pintan
rectángulos y texto, y se serializa a PNG.

La tipografía
-------------
La misma **Inter** que usa el cliente, copiada a `app/recursos/`. No es una fuente nueva en
el proyecto: es el mismo archivo que ya viaja en el bundle del navegador (OFL, la licencia
está al lado). La que trae Pillow por defecto no tiene acentos —«días» salía «d☐as»—, que
para un producto en español no sirve.

Se genera al pedirla y no se guarda: cuesta unas decenas de milisegundos y así la tarjeta
nunca se queda con un título viejo. La respuesta lleva su `ETag`, de modo que quien la pida
otra vez no la vuelve a descargar.
"""
from __future__ import annotations

import io
import os
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

ANCHO, ALTO = 1200, 630

# Los mismos colores del panel: la tarjeta tiene que parecerse a la página que abre.
FONDO = (15, 23, 42)          # slate-900
TEXTO = (248, 250, 252)       # slate-50
APAGADO = (148, 163, 184)     # slate-400
ACENTO = (99, 102, 241)       # indigo-500

MARCA = "PluriOne"
PIE = "Sistema Inteligente de Lead Scoring"

MARGEN = 84
# Tres líneas de título como mucho. Con cuatro, el cuerpo se come el pie y la tarjeta deja
# de leerse de un vistazo, que es lo único que tiene que hacer.
MAX_LINEAS = 3
CORTE = "…"

RUTA_FUENTE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "recursos", "inter-latin-wght-normal.woff2")


def _fuente(tamano: int) -> ImageFont.FreeTypeFont:
    """
    Inter al tamaño pedido.

    Es un `woff2` y no un `ttf` porque es exactamente el archivo que ya está en el
    proyecto; FreeType lo lee igual. Duplicarlo en otro formato sería tener dos copias de
    la misma fuente que pueden separarse.
    """
    return ImageFont.truetype(RUTA_FUENTE, tamano)


def _ancho(dibujo: ImageDraw.ImageDraw, texto: str, fuente) -> int:
    izquierda, _, derecha, _ = dibujo.textbbox((0, 0), texto, font=fuente)
    return derecha - izquierda


def _repartir(dibujo: ImageDraw.ImageDraw, texto: str, fuente, ancho_util: int) -> List[str]:
    """
    Parte el título en líneas que quepan, por palabras.

    Una palabra más larga que la línea entera —una dirección pegada en el título— se corta
    por caracteres en lugar de desbordar el lienzo: es feo, pero salirse del borde lo es
    más y además no se ve hasta que la red dibuja la tarjeta.
    """
    lineas: List[str] = []
    actual = ""
    for palabra in texto.split():
        prueba = f"{actual} {palabra}".strip()
        if _ancho(dibujo, prueba, fuente) <= ancho_util or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
        while _ancho(dibujo, actual, fuente) > ancho_util and len(actual) > 1:
            lineas.append(actual[:-1])
            actual = actual[-1]
    if actual:
        lineas.append(actual)
    return lineas


def _recortar_a_tres(dibujo: ImageDraw.ImageDraw, lineas: List[str], fuente, ancho_util: int) -> List[str]:
    if len(lineas) <= MAX_LINEAS:
        return lineas
    visibles = lineas[:MAX_LINEAS]
    ultima = visibles[-1]
    while ultima and _ancho(dibujo, ultima + CORTE, fuente) > ancho_util:
        ultima = ultima[:-1]
    visibles[-1] = ultima.rstrip() + CORTE
    return visibles


def _tamano_del_titulo(dibujo: ImageDraw.ImageDraw, titulo: str, ancho_util: int) -> Tuple[int, List[str]]:
    """
    El título, lo más grande que quepa en tres líneas.

    Se prueba de mayor a menor en lugar de calcular: el ancho de un texto depende de la
    fuente y de qué letras lleva, y despejarlo daría un número que solo vale para un caso.
    """
    for tamano in (76, 68, 60, 54, 48, 44, 40):
        fuente = _fuente(tamano)
        lineas = _repartir(dibujo, titulo, fuente, ancho_util)
        if len(lineas) <= MAX_LINEAS:
            return tamano, lineas
    fuente = _fuente(40)
    return 40, _recortar_a_tres(dibujo, _repartir(dibujo, titulo, fuente, ancho_util), fuente, ancho_util)


def dibujar(titulo: str, pie: Optional[str] = None) -> bytes:
    """
    El PNG de la tarjeta, en memoria.

    `titulo` es lo que se lee en grande. `pie` es la línea de abajo; sin él va el nombre
    del sistema. Nada de esto se escapa ni se interpreta: aquí el texto son píxeles, no
    marcado, así que unas comillas o un `<script>` en el título son letras y nada más.
    """
    imagen = Image.new("RGB", (ANCHO, ALTO), FONDO)
    dibujo = ImageDraw.Draw(imagen)

    # Barra de acento arriba: da color sin competir con el texto.
    dibujo.rectangle([(0, 0), (ANCHO, 12)], fill=ACENTO)

    ancho_util = ANCHO - MARGEN * 2

    # La marca, arriba, con su punto.
    fuente_marca = _fuente(34)
    dibujo.ellipse([(MARGEN, 92), (MARGEN + 22, 114)], fill=ACENTO)
    dibujo.text((MARGEN + 38, 88), MARCA, font=fuente_marca, fill=TEXTO)

    # El título, centrado verticalmente en el hueco que queda.
    limpio = " ".join((titulo or "").split()) or MARCA
    tamano, lineas = _tamano_del_titulo(dibujo, limpio, ancho_util)
    fuente_titulo = _fuente(tamano)
    interlineado = int(tamano * 1.22)
    alto_bloque = interlineado * len(lineas)
    y = (ALTO - alto_bloque) // 2
    for linea in lineas:
        dibujo.text((MARGEN, y), linea, font=fuente_titulo, fill=TEXTO)
        y += interlineado

    # El pie, abajo, con una regla fina encima.
    fuente_pie = _fuente(28)
    dibujo.rectangle([(MARGEN, ALTO - 118), (MARGEN + 96, ALTO - 114)], fill=ACENTO)
    dibujo.text((MARGEN, ALTO - 96), pie or PIE, font=fuente_pie, fill=APAGADO)

    memoria = io.BytesIO()
    # `optimize` recorta unos kilobytes sin tocar los píxeles; las redes descargan esto
    # cada vez que alguien pega el enlace.
    imagen.save(memoria, format="PNG", optimize=True)
    return memoria.getvalue()
