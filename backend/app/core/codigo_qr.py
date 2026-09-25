"""
El código QR del alta del segundo factor (capítulo 35).

Es lo único de este capítulo que entra al lock como dependencia nueva, y conviene decir por
qué se aceptó aquí y no para las otras dos piezas.

El TOTP está escrito a mano (`app/core/totp.py`) porque es un HMAC truncado y la norma
publica vectores de prueba con los que se puede **demostrar** que está bien. El secreto no
se cifra porque no se guarda. Un codificador de QR, en cambio, no es cuarenta líneas: son
los polinomios de Reed-Solomon, ocho patrones de enmascaramiento con sus penalizaciones, y
la tabla de versiones. Escribirlo sería el único sitio de este capítulo donde el código
propio saldría peor que una biblioteca.

`segno` es Python puro, **sin dependencias**, y pesa unos 76 KB: no arrastra nada al lock
ni añade extensiones compiladas, que era la objeción de fondo a `cryptography`.

Se devuelve **SVG y no PNG** a propósito. Un QR es geometría: en SVG se ve nítido en
cualquier pantalla y en cualquier impresión, ocupa menos que el PNG equivalente, y se puede
incrustar en el documento sin pasar por base64 ni por una ruta que sirva imágenes. Además
evita traer Pillow a este camino, que está en el proyecto para dibujar la tarjeta de las
publicaciones y no para esto.
"""
import io

import segno

# Corrección de errores media: aguanta un 15 % del código dañado o tapado. Es lo que
# recomienda la convención `otpauth://` y sobra para una pantalla; la alta (30 %) haría el
# dibujo más denso sin ninguna ganancia leyéndolo de un monitor.
CORRECCION = "m"

# Tamaño del módulo (cada cuadradito) en unidades del SVG, y el margen en módulos. Cuatro
# módulos de margen es lo que exige la norma ISO/IEC 18004: sin esa «zona tranquila» hay
# lectores que no encuentran el código, y es un fallo que solo aparece en algunos teléfonos.
ESCALA = 4
BORDE = 4


def svg(contenido: str) -> str:
    """
    El QR de ese texto, como un `<svg>` suelto listo para incrustar.

    Sin declaración XML ni `<!DOCTYPE>`: el destino es el interior de un documento HTML, y
    esas dos líneas allí no pintan nada y estorban al incrustarlo.
    """
    codigo = segno.make(contenido, error=CORRECCION)
    salida = io.BytesIO()
    codigo.save(
        salida,
        kind="svg",
        scale=ESCALA,
        border=BORDE,
        xmldecl=False,
        svgns=True,
        # Sin color de fondo: así el QR hereda el del panel y se ve igual de bien en el
        # tema claro y en el oscuro. Los módulos van en negro porque los lectores esperan
        # el patrón oscuro sobre fondo claro, y el panel usa fondo claro en la tarjeta.
        dark="#000000",
        light=None,
    )
    return salida.getvalue().decode("utf-8")
