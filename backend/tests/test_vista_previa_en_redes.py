"""
La tarjeta que enseñan las redes al pegar el enlace de una publicación (capítulo 27).

Quien lee estas etiquetas es un programa: pide la dirección, descarga el HTML y se va. **No
ejecuta JavaScript.** Por eso todo lo que se comprueba aquí se comprueba sobre el HTML tal
como sale del servidor, sin montar nada.

Lo que se comprueba:

* **Que están**: Open Graph y X, con el título, el texto, la dirección y la imagen de esa
  publicación, dentro del HTML y no puestas después por el cliente.
* **Que no filtran**: un borrador, una pausada, una cerrada y un enlace inventado dan las
  mismas etiquetas genéricas, el mismo cuerpo y el mismo 200. Ni el título ni el texto salen.
* **Que escapan**: un título con comillas, con `<script>` o con `&` entra como texto y no
  como marcado. Se comprueba analizando el HTML, no buscando cadenas.
* **La imagen**: 1 200 × 630, PNG de verdad, con `ETag` y sin guardarse.
* **Que no cuentan visitas**: pegar un enlace en un chat no es que alguien abra la página.
"""
import html as html_stdlib
import re
import struct
from html.parser import HTMLParser

import pytest
from app.core import tarjeta as tarjeta_png
from app.core.etiquetas_sociales import (
    DESCRIPCION_GENERICA,
    MAX_TITULO,
    TITULO_GENERICO,
    tarjeta_de,
)
from app.core.publicaciones import CANAL_LINKEDIN
from app.models.entities import VisitaDePublicacion

CAMPANAS = "/api/v1/campaigns"

TITULO = "Post · Equipos de TI en 30 días"
TEXTO = "¿Tu equipo de TI tarda meses en cubrir una vacante? Lo hacemos en 30 días."


@pytest.fixture
def publicacion(client, lead_headers):
    return client.post(
        CAMPANAS,
        headers=lead_headers,
        json={"name": TITULO, "channel": CANAL_LINKEDIN, "description": TEXTO},
    ).json()


def _crear(client, lead_headers, **campos):
    cuerpo = {"name": TITULO, "channel": CANAL_LINKEDIN, "description": TEXTO, **campos}
    return client.post(CAMPANAS, headers=lead_headers, json=cuerpo).json()


def _pagina(client, publicacion):
    return client.get(f"/interes/{publicacion['public_slug']}")


class _Etiquetas(HTMLParser):
    """
    Lee el HTML como lo leería un rastreador: con un analizador, no con expresiones.

    Buscar `og:title` con una expresión regular diría que la etiqueta está aunque el
    documento estuviera roto; analizarlo dice además que el documento **es** HTML válido y
    que el valor llegó entero al atributo, que es justo lo que el escape tiene que lograr.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.titulo = None
        self.etiquetas = []
        self._en_titulo = False

    def handle_starttag(self, tag, attrs):
        self.etiquetas.append(tag)
        d = dict(attrs)
        if tag == "meta":
            clave = d.get("property") or d.get("name")
            if clave:
                self.meta[clave] = d.get("content", "")
        if tag == "title":
            self._en_titulo = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._en_titulo = False

    def handle_data(self, datos):
        if self._en_titulo:
            self.titulo = (self.titulo or "") + datos


def leer(html: str) -> _Etiquetas:
    p = _Etiquetas()
    p.feed(html)
    return p


def _tamano_del_png(datos: bytes):
    """Ancho y alto leídos de la cabecera IHDR, que es lo que mira cualquier lector."""
    assert datos[:8] == b"\x89PNG\r\n\x1a\n", "no es un PNG"
    ancho, alto = struct.unpack(">II", datos[16:24])
    return ancho, alto


# ==============================================================================
# Las etiquetas están, y sin JavaScript
# ==============================================================================

def test_el_html_trae_las_etiquetas_de_open_graph(client, publicacion):
    respuesta = _pagina(client, publicacion)

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/html")
    etiquetas = leer(respuesta.text).meta
    assert etiquetas["og:title"] == TITULO
    assert etiquetas["og:description"].startswith("¿Tu equipo de TI tarda meses")
    assert etiquetas["og:type"] == "website"
    assert etiquetas["og:site_name"] == "PluriOne"
    assert etiquetas["og:url"] == publicacion["enlace_publico"]


def test_el_html_trae_las_etiquetas_de_x(client, publicacion):
    etiquetas = leer(_pagina(client, publicacion).text).meta

    # Sin `summary_large_image`, X enseña un cuadradito al lado del título en vez de la
    # imagen ancha: la tarjeta existe pero no se ve.
    assert etiquetas["twitter:card"] == "summary_large_image"
    assert etiquetas["twitter:title"] == TITULO
    assert etiquetas["twitter:image"].endswith("/tarjeta.png")


def test_la_imagen_se_anuncia_con_su_tamano(client, publicacion):
    etiquetas = leer(_pagina(client, publicacion).text).meta

    assert etiquetas["og:image"] == f"{publicacion['enlace_publico']}/tarjeta.png"
    assert etiquetas["og:image:width"] == str(tarjeta_png.ANCHO)
    assert etiquetas["og:image:height"] == str(tarjeta_png.ALTO)
    assert etiquetas["og:image:alt"] == TITULO


def test_el_titulo_del_documento_es_el_de_la_publicacion(client, publicacion):
    assert leer(_pagina(client, publicacion).text).titulo == TITULO


def test_las_etiquetas_no_dependen_de_javascript(client, publicacion):
    """
    Están en el HTML servido, no las pone la aplicación.

    Se comprueba quitando todo lo que hay dentro de `<script>`: lo que queda tiene que
    seguir teniendo las etiquetas. Ponerlas con JavaScript no serviría de nada, porque el
    rastreador se va antes de ejecutarlo.
    """
    sin_scripts = re.sub(r"<script\b.*?</script>", "", _pagina(client, publicacion).text, flags=re.S)

    etiquetas = leer(sin_scripts).meta
    assert etiquetas["og:title"] == TITULO
    assert etiquetas["twitter:card"] == "summary_large_image"


def test_la_pagina_arranca_la_aplicacion(client, publicacion):
    """El HTML sigue siendo la página: trae el punto de montaje y el arranque del cliente."""
    texto = _pagina(client, publicacion).text

    assert 'id="root"' in texto
    assert 'src="/assets/app.js"' in texto


def test_los_nombres_del_bundle_coinciden_con_los_que_nombra_el_servidor():
    """
    El HTML nombra `assets/app.js` y `assets/app.css`, y el compilador tiene que emitirlos
    con ese nombre exacto. Son dos archivos distintos del proyecto: si uno cambia y el otro
    no, la página pública se queda sin aplicación y solo se ve al desplegar.
    """
    import pathlib

    from app.core.config import settings

    config = (pathlib.Path(__file__).resolve().parents[2] / "frontend" / "vite.config.js").read_text(
        encoding="utf-8"
    )
    assert f"'{settings.PAGINA_PUBLICA_SCRIPT.lstrip('/')}'" in config
    assert f"'{settings.PAGINA_PUBLICA_HOJA.lstrip('/')}'" in config


# ==============================================================================
# Lo que no está activo no filtra nada
# ==============================================================================

@pytest.mark.parametrize("estado", ["borrador", "pausada", "cerrada"])
def test_una_publicacion_que_no_esta_activa_da_etiquetas_genericas(client, lead_headers, estado):
    creada = _crear(client, lead_headers, estado=estado)

    respuesta = _pagina(client, creada)

    assert respuesta.status_code == 200
    etiquetas = leer(respuesta.text).meta
    assert etiquetas["og:title"] == TITULO_GENERICO
    assert etiquetas["og:description"] == DESCRIPCION_GENERICA
    # Ni una palabra de lo que contiene.
    assert TITULO not in respuesta.text
    assert "cubrir una vacante" not in respuesta.text


def test_un_enlace_inventado_da_lo_mismo_que_un_borrador(client, lead_headers):
    """
    El mismo cuerpo y el mismo código. Con un 404 para unos y un 200 para otros, el código
    de respuesta diría desde fuera qué enlaces existen, que es lo que el capítulo 26 cerró.
    """
    borrador = _crear(client, lead_headers, estado="borrador")

    del_borrador = _pagina(client, borrador)
    inventado = client.get("/interes/estoMeLoInvento00000x")

    assert del_borrador.status_code == inventado.status_code == 200
    # Salvo el propio enlace, que es distinto porque son direcciones distintas, el documento
    # es el mismo hasta el último carácter.
    sin_enlace = lambda texto, slug: texto.replace(slug, "SLUG")  # noqa: E731
    assert sin_enlace(del_borrador.text, borrador["public_slug"]) == sin_enlace(
        inventado.text, "estoMeLoInvento00000x"
    )


def test_una_campana_que_no_es_publicacion_tampoco_filtra(client, lead_headers):
    campana = client.post(
        CAMPANAS, headers=lead_headers, json={"name": "Google Ads Q3", "channel": "Google Ads"}
    ).json()

    respuesta = client.get(f"/interes/{campana['public_slug']}")

    assert leer(respuesta.text).meta["og:title"] == TITULO_GENERICO
    assert "Google Ads Q3" not in respuesta.text


def test_la_imagen_de_una_pausada_es_la_generica(client, lead_headers):
    """El título no se enseña tampoco dibujado: una imagen se lee igual que un texto."""
    pausada = _crear(client, lead_headers, estado="pausada")

    de_la_pausada = client.get(f"/interes/{pausada['public_slug']}/tarjeta.png").content
    inventada = client.get("/interes/estoMeLoInvento00000x/tarjeta.png").content

    assert de_la_pausada == inventada


# ==============================================================================
# El escape
# ==============================================================================

PELIGROSOS = [
    'Post " onmouseover="alerta()',
    "Post <script>alert(1)</script> TI",
    "Post & compañía <b>TI</b>",
    "Post ' con apóstrofo",
    'Post "/><meta property="og:title" content="secuestrado',
]


@pytest.mark.parametrize("titulo", PELIGROSOS)
def test_un_titulo_con_comillas_o_etiquetas_no_rompe_el_html(client, lead_headers, titulo):
    creada = _crear(client, lead_headers, name=titulo)

    respuesta = _pagina(client, creada)

    leido = leer(respuesta.text)
    # El valor llega entero al atributo: ni se corta en la comilla ni arrastra lo de detrás.
    assert leido.meta["og:title"] == titulo
    assert leido.titulo == titulo
    # Y no ha aparecido ninguna etiqueta que no pusiéramos nosotros. El documento lleva
    # **un** `<script>`, el que arranca la aplicación: ni uno más.
    assert leido.etiquetas.count("script") == 1
    assert "b" not in leido.etiquetas
    assert "img" not in leido.etiquetas


@pytest.mark.parametrize("titulo", PELIGROSOS)
def test_no_se_puede_secuestrar_una_etiqueta_desde_el_titulo(client, lead_headers, titulo):
    """
    Un `og:title` de más dejaría que el título eligiera lo que enseña la red.

    El último caso de la lista lo intenta a propósito: cierra el atributo y abre otra
    etiqueta. Si el escape fallara, el documento tendría dos `og:title` y la red leería el
    segundo.
    """
    creada = _crear(client, lead_headers, name=titulo)

    texto = _pagina(client, creada).text

    assert texto.count('property="og:title"') == 1
    assert leer(texto).meta["og:title"] == titulo


def test_un_texto_con_marcado_entra_como_texto(client, lead_headers):
    creada = _crear(client, lead_headers, description='Antes <img src=x onerror="a()"> después')

    leido = leer(_pagina(client, creada).text)

    assert leido.meta["og:description"].startswith("Antes <img")
    assert "img" not in leido.etiquetas


def test_el_escape_es_el_de_la_biblioteca_y_no_uno_propio(client, lead_headers):
    """Lo que sale escapado tiene que volver a ser lo mismo al desescapar."""
    titulo = "Comillas \" y ' y & y < y >"
    creada = _crear(client, lead_headers, name=titulo)

    texto = _pagina(client, creada).text

    crudo = re.search(r'property="og:title" content="([^"]*)"', texto).group(1)
    assert html_stdlib.unescape(crudo) == titulo


# ==============================================================================
# La imagen
# ==============================================================================

def test_la_imagen_es_un_png_de_1200_por_630(client, publicacion):
    respuesta = client.get(f"/interes/{publicacion['public_slug']}/tarjeta.png")

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "image/png"
    assert _tamano_del_png(respuesta.content) == (1200, 630)


def test_la_imagen_no_se_vuelve_a_descargar_si_no_cambio(client, publicacion):
    ruta = f"/interes/{publicacion['public_slug']}/tarjeta.png"
    primera = client.get(ruta)

    segunda = client.get(ruta, headers={"If-None-Match": primera.headers["etag"]})

    assert segunda.status_code == 304
    assert segunda.content == b""


def test_cambiar_el_titulo_cambia_la_imagen(client, lead_headers, publicacion):
    ruta = f"/interes/{publicacion['public_slug']}/tarjeta.png"
    antes = client.get(ruta)

    client.put(f"{CAMPANAS}/{publicacion['id']}", headers=lead_headers, json={"name": "Otro título"})
    despues = client.get(ruta)

    assert antes.content != despues.content
    assert antes.headers["etag"] != despues.headers["etag"]


def test_la_imagen_se_dibuja_con_acentos(client, lead_headers):
    """
    La fuente que trae Pillow por defecto no tiene acentos: «días» salía «d☐as». Se usa la
    Inter del proyecto, y esta prueba falla si alguien vuelve a la de por defecto.
    """
    from PIL import Image, ImageDraw, ImageFont

    # Por `_fuente`, que es lo que usa el dibujo de verdad. Construir la fuente aquí con
    # `truetype(RUTA_FUENTE, ...)` comprobaba el archivo, no el código: volver a la fuente
    # por defecto seguía pasando la prueba.
    fuente = tarjeta_png._fuente(40)
    por_defecto = ImageFont.load_default(size=40)

    def pinta(texto, f):
        im = Image.new("L", (80, 80), 0)
        ImageDraw.Draw(im).text((5, 5), texto, font=f, fill=255)
        return im.tobytes()

    recuadro = pinta("漢", fuente)
    for letra in "áéíóúñ¿":
        assert pinta(letra, fuente) != recuadro, f"«{letra}» sale como recuadro"
    # Y que la comprobación sirve de algo: con la de por defecto, sí sale el recuadro.
    assert pinta("á", por_defecto) == pinta("漢", por_defecto)


# ==============================================================================
# Ni visitas ni cuenta compartida
# ==============================================================================

def test_pedir_el_html_o_la_imagen_no_cuenta_una_visita(client, publicacion, db_session):
    """Pegar un enlace en un chat no es que alguien haya abierto la página."""
    client.get(f"/interes/{publicacion['public_slug']}")
    client.get(f"/interes/{publicacion['public_slug']}/tarjeta.png")

    db_session.expire_all()
    assert db_session.query(VisitaDePublicacion).count() == 0


def test_la_pagina_no_pone_cookies(client, publicacion):
    respuesta = _pagina(client, publicacion)

    assert "set-cookie" not in {k.lower() for k in respuesta.headers}


def test_el_html_no_se_cachea(client, publicacion):
    """Una copia vieja seguiría enseñando el título de antes durante días."""
    assert "no-store" in _pagina(client, publicacion).headers["cache-control"]


# ==============================================================================
# Lo que pasa con un titulo largo, que es lo que no se habia mirado
# ==============================================================================

def test_un_titulo_mas_largo_que_el_tope_se_corta_por_una_palabra():
    """
    El texto de la etiqueta se recorta, y el recorte tiene que caer entre palabras.

    Un corte a la mitad de una palabra -«Equipos de TI en treinta dia…»- se lee como un
    error de la pagina; y sin recorte, LinkedIn y WhatsApp cortan por su cuenta a lo ancho
    que les quepa, que no es el mismo en los dos. Noventa caracteres para el titulo y
    doscientos para el texto son los que caben en las dos.
    """
    largo = "Equipos de tecnologia de la informacion para empresas que necesitan cubrir vacantes criticas"
    assert len(largo) > MAX_TITULO

    tarjeta = tarjeta_de(largo, TEXTO, "https://ejemplo.mx/interes/x", "https://ejemplo.mx/t.png")

    assert len(tarjeta.titulo) <= MAX_TITULO
    assert tarjeta.titulo.endswith("…")
    # Cortado entre palabras: lo que queda delante del puntito es un prefijo entero del
    # titulo, no media palabra.
    assert largo.startswith(tarjeta.titulo[:-1].rstrip())
    assert not tarjeta.titulo[:-2].endswith(" ")


@pytest.mark.parametrize(
    "titulo",
    [
        "A" + "b" * (MAX_TITULO + 20),
        # Un solo espacio, y al principio: el ultimo espacio existe pero cortar ahi dejaria
        # el titulo en una letra. Es el caso que justifica la condicion de la mitad.
        "A " + "b" * (MAX_TITULO + 20),
    ],
    ids=["sin un solo espacio", "con el unico espacio al principio"],
)
def test_una_palabra_mas_larga_que_el_tope_se_corta_donde_toque(titulo):
    """
    La otra salida del recorte: cuando no hay ningun espacio en la segunda mitad.

    Pasa con una direccion pegada en el titulo o con un nombre de producto sin espacios.
    Buscar el ultimo espacio y cortar ahi dejaria el titulo en una palabra, o en nada; por
    eso solo se acepta el espacio si cae pasada la mitad del tope.
    """
    tarjeta = tarjeta_de(titulo, TEXTO, "https://ejemplo.mx/interes/x", "https://ejemplo.mx/t.png")

    assert len(tarjeta.titulo) <= MAX_TITULO
    assert tarjeta.titulo.endswith("…")
    assert len(tarjeta.titulo) > MAX_TITULO // 2, "cortar por el ultimo espacio dejaria casi nada"


def test_una_publicacion_sin_titulo_utilizable_cae_a_la_tarjeta_generica():
    """
    Un titulo de espacios, o de caracteres de control, no es un titulo.

    Lo importante es que no salga una tarjeta con el titulo vacio: en un chat, el enlace se
    veria como una caja sin texto, y lo que se comparte es lo unico que se ve de la pagina.
    """
    for titulo in ("", "   ", "\u0000\u0001"):
        tarjeta = tarjeta_de(titulo, TEXTO, "https://ejemplo.mx/interes/x", "https://ejemplo.mx/t.png")

        assert tarjeta.titulo == TITULO_GENERICO
        assert tarjeta.descripcion == DESCRIPCION_GENERICA


def test_un_titulo_larguisimo_se_dibuja_en_tres_lineas_y_con_puntito():
    """
    La escalera de tamanos de la imagen y su ultimo peldano.

    El titulo se dibuja lo mas grande que quepa en tres lineas, probando siete tamanos de
    mayor a menor. Con un titulo que no cabe ni en el mas pequeno, el ultimo peldano recorta
    a tres lineas y pone el puntito.

    Se comprueban las LINEAS y no el PNG a proposito: la imagen sale valida y de 1200x630
    tambien con cuatro lineas o con cincuenta —se dibujarian encima del pie y fuera del
    lienzo, y el fichero seria igual de correcto—, asi que mirar el PNG no distingue nada.
    """
    from PIL import Image, ImageDraw

    dibujo = ImageDraw.Draw(Image.new("RGB", (tarjeta_png.ANCHO, tarjeta_png.ALTO)))
    larguisimo = " ".join(["palabra"] * 120)

    tamano, lineas = tarjeta_png._tamano_del_titulo(dibujo, larguisimo, 900)

    assert len(lineas) == tarjeta_png.MAX_LINEAS
    assert lineas[-1].endswith("…")
    assert tamano == 40, "con un titulo asi se acaba en el peldano mas pequeno"
    # Y la imagen sigue saliendo, que es lo otro que tiene que seguir siendo verdad.
    datos = tarjeta_png.dibujar(larguisimo, pie="plurione.mx")
    assert datos[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", datos[16:24]) == (tarjeta_png.ANCHO, tarjeta_png.ALTO)


def test_un_titulo_corto_se_dibuja_con_la_letra_mas_grande():
    """
    La otra punta de la escalera, que es la que se ve en la demostracion.

    Si el primer peldano dejara de valer, todos los titulos saldrian pequenos sin que nada
    fallara: la imagen es correcta y nadie la mide.
    """
    from PIL import Image, ImageDraw

    dibujo = ImageDraw.Draw(Image.new("RGB", (tarjeta_png.ANCHO, tarjeta_png.ALTO)))

    tamano, lineas = tarjeta_png._tamano_del_titulo(dibujo, "Equipos de TI", 900)

    assert tamano == 76
    assert lineas == ["Equipos de TI"]


def test_una_sola_palabra_mas_ancha_que_el_lienzo_se_parte_por_letras():
    """
    La vuelta que parte por letras se recorre, y parte UNA letra: deja la linea desbordada.

    Esta prueba se escribio para comprobar lo que el docstring de `_repartir` promete —«una
    palabra mas larga que la linea entera se corta por caracteres en lugar de desbordar el
    lienzo»— y lo que mide es que no lo cumple. El `while` saca `actual[:-1]` como linea y
    se queda con `actual[-1]`: corta un caracter y guarda el ultimo, en vez de sacar un
    trozo que quepa y seguir con el resto. Con 200 letras y el ancho util de verdad (1032
    px), la primera linea mide 14 925 px y se sale de la imagen por la derecha; la segunda
    es una «W» sola.

    Y no hay escalera que lo salve: `_tamano_del_titulo` prueba de 76 a 40 y se detiene en
    cuanto caben tres lineas, y aqui caben dos desde el primer peldano, asi que devuelve el
    tamano MAS GRANDE. Queda anotado en §6.4 y la prueba comprueba lo medido, no lo
    prometido: arreglar `_repartir` cambiaria pixeles de una imagen que hoy se sirve, y eso
    no entra en la congelacion. Lo que esta prueba sujeta es que la vuelta se recorre: si
    alguien la quita, estas dos lineas vuelven a ser una.
    """
    from PIL import Image, ImageDraw

    dibujo = ImageDraw.Draw(Image.new("RGB", (tarjeta_png.ANCHO, tarjeta_png.ALTO)))
    fuente = tarjeta_png._fuente(76)
    ancho_util = tarjeta_png.ANCHO - tarjeta_png.MARGEN * 2

    lineas = tarjeta_png._repartir(dibujo, "W" * 200, fuente, ancho_util)

    assert lineas == ["W" * 199, "W"], "la vuelta corta una letra y guarda la ultima"
    assert tarjeta_png._ancho(dibujo, lineas[0], fuente) > ancho_util, (
        "el defecto: la linea que la vuelta saca sigue sin caber"
    )

    # Y el titulo entero sale al tamano mayor, porque dos lineas ya son menos de tres.
    tamano, del_titulo = tarjeta_png._tamano_del_titulo(dibujo, "W" * 200, ancho_util)
    assert (tamano, del_titulo) == (76, lineas)


def test_un_titulo_que_se_queda_sin_palabras_no_reparte_ninguna_linea():
    """
    `_repartir` de algo sin palabras devuelve la lista vacia, no una linea en blanco.

    `dibujar` nunca le pasa esto -antes cae a la marca-, pero la funcion es la que decide
    cuantas lineas hay y de ella cuelga la escalera de tamanos: una linea vacia contaria
    como linea, y la escalera elegiria un tamano por un renglon que no se ve.
    """
    from PIL import Image, ImageDraw

    dibujo = ImageDraw.Draw(Image.new("RGB", (tarjeta_png.ANCHO, tarjeta_png.ALTO)))
    fuente = tarjeta_png._fuente(76)

    for vacio in ("", "   ", "\n\t "):
        assert tarjeta_png._repartir(dibujo, vacio, fuente, 1032) == []


def test_tres_lineas_o_menos_vuelven_del_recorte_sin_tocar():
    """
    El recorte no toca lo que ya cabe: no le pone puntito a un titulo completo.

    Hoy solo lo llama la salida de emergencia de la escalera, que llega siempre con mas de
    tres lineas, asi que esta es la mitad del contrato que ningun camino del dibujo recorre.
    Se comprueba igual porque es lo que separa «recortado» de «completo»: un puntito en un
    titulo que caben entero le dice a quien lee la tarjeta que falta algo.
    """
    from PIL import Image, ImageDraw

    dibujo = ImageDraw.Draw(Image.new("RGB", (tarjeta_png.ANCHO, tarjeta_png.ALTO)))
    fuente = tarjeta_png._fuente(76)

    for lineas in ([], ["una"], ["una", "dos"], ["una", "dos", "tres"]):
        recortadas = tarjeta_png._recortar_a_tres(dibujo, list(lineas), fuente, 1032)
        assert recortadas == lineas
        assert not any(linea.endswith(tarjeta_png.CORTE) for linea in recortadas)


def test_la_tercera_linea_se_acorta_hasta_que_quepa_con_el_puntito():
    """
    El puntito ocupa, asi que la tercera linea se acorta hasta dejarle sitio.

    Es la vuelta que nadie recorria. Sin ella, `linea + CORTE` se dibujaria mas ancho que
    el lienzo y el puntito -lo unico que avisa de que el titulo sigue- seria justo lo que
    se sale de la imagen: la tarjeta diria un titulo recortado sin decir que lo esta.
    """
    from PIL import Image, ImageDraw

    dibujo = ImageDraw.Draw(Image.new("RGB", (tarjeta_png.ANCHO, tarjeta_png.ALTO)))
    fuente = tarjeta_png._fuente(76)
    ancho_util = tarjeta_png.ANCHO - tarjeta_png.MARGEN * 2
    # Una tercera linea que ocupa el ancho justo: con el puntito detras ya no cabe.
    llena = "W"
    while tarjeta_png._ancho(dibujo, llena + "W", fuente) <= ancho_util:
        llena += "W"
    assert tarjeta_png._ancho(dibujo, llena, fuente) <= ancho_util
    assert tarjeta_png._ancho(dibujo, llena + tarjeta_png.CORTE, fuente) > ancho_util

    recortadas = tarjeta_png._recortar_a_tres(
        dibujo, ["una", "dos", llena, "cuarta"], fuente, ancho_util
    )

    assert len(recortadas) == 3
    ultima = recortadas[-1]
    assert ultima.endswith(tarjeta_png.CORTE)
    assert len(ultima) < len(llena) + 1, "hubo que quitar letras para que quepa el puntito"
    assert tarjeta_png._ancho(dibujo, ultima, fuente) <= ancho_util
