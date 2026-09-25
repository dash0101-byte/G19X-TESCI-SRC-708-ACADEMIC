"""
Capítulo 34: la puerta estrecha, y la dirección que cambia cada vez.

Este archivo comprueba tres cosas que no se parecen entre sí pero fallan juntas:

1. **Qué publica la puerta.** Se lee `frontend/nginx.conf` y se comprueba que el servidor
   del 8080 es una lista **blanca**: lo que no está nombrado devuelve 404. La forma de la
   comprobación importa tanto como el resultado. Comprobar «`/api/v1/leads` no está
   publicado» sería una prueba que pasa hoy y sigue pasando el día que alguien añade
   `/api/v1/nomina`, porque una lista negra solo prohíbe lo que ya se sabía nombrar.
2. **Que la dirección pública tenga un solo dueño.** Pasar de la dirección efímera de un
   túnel a un dominio propio tiene que ser cambiar un ajuste y nada más, así que se busca
   en todo el árbol cualquier dirección escrita a mano que compita con el ajuste.
3. **Que un enlace repartido bajo otra dirección se sepa caducado**, en vez de fallar en
   silencio dentro de un post que ya está publicado.

Qué NO se comprueba aquí, y dónde sí
------------------------------------
Que la puerta responda de verdad lo que dice el archivo. Eso no lo puede saber un `grep`:
lo comprueba `scripts/comprobar_puerta_publica.py` contra el nginx levantado, y el capítulo
lo ejecutó además a través del túnel, desde fuera de la red. Aquí se fija la configuración;
allí, el comportamiento.
"""
import datetime
import pathlib
import re

import pytest
from app.core.config import settings
from app.core.publicaciones import ACTIVA, BORRADOR, PAUSADA, base_publica
from app.models.entities import Campaign
from app.schemas.user import CampanaResponse
from app.services import ciclo_de_publicaciones as ciclo
from app.services import direccion_publica

RAIZ = pathlib.Path(__file__).resolve().parents[2]
NGINX = RAIZ / "frontend" / "nginx.conf"
COMPOSE = RAIZ / "devops" / "docker-compose.yml"


# ==============================================================================
# 1. Lo que publica la puerta
# ==============================================================================

@pytest.fixture(scope="module")
def puerta() -> str:
    """El bloque `server` del 8080, aislado del que sirve el panel en el 80."""
    texto = NGINX.read_text(encoding="utf-8")
    inicio = texto.index("listen 8080;")
    # Desde el `server {` que contiene ese `listen` hasta el final del archivo: la puerta
    # es el último bloque, y así la prueba no depende de contar llaves.
    return texto[texto.rindex("server {", 0, inicio):]


def test_la_puerta_escucha_en_su_propio_puerto(puerta):
    assert "listen 8080;" in puerta
    # Y el panel sigue en el 80, que es otro servidor: si la puerta fuera un `location` más
    # del servidor del panel, cualquier ruta nueva del panel saldría publicada con él.
    assert "listen 80;" not in puerta


def test_lo_que_no_esta_nombrado_devuelve_404(puerta):
    """
    La propiedad que hace que esto siga siendo cierto dentro de un año.

    Con `location / { return 404; }` como red final, un endpoint nuevo del sistema nace
    **fuera**. Sin él, nace publicado y nadie se entera.
    """
    assert re.search(r"location\s*/\s*\{\s*return\s+404;\s*\}", puerta), puerta[-400:]


@pytest.mark.parametrize(
    "ruta",
    [
        "/api/v1/leads",
        "/api/v1/auth/login",
        "/api/v1/users",
        "/api/v1/audit",
        "/api/v1/analytics/kpis",
        "/api/v1/campaigns",
        "/api/v1/publicaciones/comparativa",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/metrics",
        "/health",
        "/index.html",
        "/",
    ],
)
def test_ninguna_ruta_de_gestion_casa_con_lo_publicado(puerta, ruta):
    """
    Ruta por ruta, contra las expresiones que la puerta declara.

    No es una lista de prohibiciones: son ejemplos que se evalúan contra la lista blanca de
    verdad. Si mañana se publicara `/api/` entero, estas catorce se pondrían rojas sin que
    nadie tenga que acordarse de añadirlas.
    """
    assert _publicada(puerta, ruta) is False, f"{ruta} quedó publicada por la puerta"


@pytest.mark.parametrize(
    "ruta",
    [
        "/interes/abcdef",
        "/interes/OGxqLm4tR2VuZXJhZG9y",
        "/interes/OGxqLm4tR2VuZXJhZG9y/tarjeta.png",
        "/api/v1/interes/OGxqLm4tR2VuZXJhZG9y",
        "/assets/app.js",
        "/assets/app.css",
        "/assets/index-a1b2c3d4.js",
    ],
)
def test_lo_que_la_pagina_necesita_si_esta_publicado(puerta, ruta):
    """
    La otra mitad: una puerta que no deja pasar nada también «no publica el panel».

    Sin estas siete, la página de interés no se dibuja: el HTML sale del backend, la imagen
    de la tarjeta también, las listas del formulario vienen de su API y el documento arranca
    la aplicación desde `/assets/`.
    """
    assert _publicada(puerta, ruta) is True, f"{ruta} NO está publicada y la página la necesita"


def _publicada(puerta: str, ruta: str) -> bool:
    """
    ¿Casa esta ruta con alguna de las `location` de la puerta, sin contar el 404 final?

    Traduce las tres clases de `location` que usa nginx en este archivo: regex entre
    comillas (`~ "..."`) y prefijo (`/assets/`). No pretende ser nginx; pretende leer la
    misma lista que lee nginx, que es lo que hace que la prueba valga.
    """
    for expresion in re.findall(r'location\s+~\s+"([^"]+)"', puerta):
        if re.search(expresion, ruta):
            return True
    for prefijo in re.findall(r"location\s+(/[A-Za-z0-9_./-]*)\s*\{", puerta):
        if prefijo != "/" and ruta.startswith(prefijo):
            return True
    return False


def test_la_puerta_no_publica_la_documentacion_aunque_cambie_de_sitio(puerta):
    """
    Las rutas de arriba son direcciones concretas; esta mira el otro lado.

    Ninguna `location` de la puerta puede nombrar `/api/` a secas: es el atajo que alguien
    escribirá el día que la página necesite un endpoint más, y publicaría de paso la gestión
    entera. El endpoint que haga falta se nombra uno a uno, como los tres de ahora.
    """
    for expresion in re.findall(r'location\s+~\s+"([^"]+)"', puerta):
        assert "interes" in expresion, f"la puerta publica una ruta que no es de la página: {expresion}"
    for prefijo in re.findall(r"location\s+(/[A-Za-z0-9_./-]*)\s*\{", puerta):
        assert prefijo in ("/", "/assets/"), f"la puerta publica el prefijo {prefijo}"


def test_el_puerto_de_la_puerta_solo_se_publica_en_loopback():
    """
    La mitad de la defensa que no está en nginx.

    `nginx.conf` se cree `CF-Connecting-IP` para contar el límite por IP, y eso solo es
    legítimo mientras el único que pueda hablar con ese puerto sea el túnel de esta misma
    máquina. Publicarlo en `0.0.0.0` convertiría esa línea en un agujero: cualquiera de la
    oficina podría darse un contador nuevo en cada petición poniendo la cabecera a mano.
    """
    compose = COMPOSE.read_text(encoding="utf-8")
    assert re.search(r'"127\.0\.0\.1:\$\{PUERTA_PUBLICA_PUERTO:-\d+\}:8080"', compose), (
        "el puerto de la puerta dejó de publicarse solo en 127.0.0.1"
    )


# ==============================================================================
# 2. La dirección pública tiene un solo dueño
# ==============================================================================

# Dónde puede aparecer una dirección pública escrita a mano sin que sea un problema.
_PERMITIDOS = {
    # El propio ajuste y su valor por defecto.
    "backend/app/core/config.py",
    # Documentación: ahí las direcciones son ejemplos que hay que poder leer.
    "docs",
    "README.md",
    # Compose declara el valor por defecto del ajuste, que es el mismo sitio.
    "devops/docker-compose.yml",
    # Las pruebas escriben direcciones a propósito para comprobar que se respetan.
    "backend/tests",
    "frontend/src",
}


def test_ninguna_direccion_publica_escrita_a_mano_en_el_codigo():
    """
    Pasar a un dominio propio tiene que ser cambiar un valor, no buscar y reemplazar.

    Se busca en el código de la aplicación cualquier `localhost:3000/interes` suelto. El
    día que aparezca uno, «cambiar la dirección» dejará de ser una operación de un paso, y
    el que se quede atrás producirá un enlace roto dentro de un post ya publicado, que es
    de los errores que nadie ve hasta que es tarde.
    """
    sospechosas = []
    for archivo in (RAIZ / "backend" / "app").rglob("*.py"):
        relativa = archivo.relative_to(RAIZ).as_posix()
        if any(relativa.startswith(p) for p in _PERMITIDOS):
            continue
        for numero, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), 1):
            if linea.lstrip().startswith("#"):
                continue
            if re.search(r"https?://[^\s\"']+/interes", linea):
                sospechosas.append(f"{relativa}:{numero}")
    assert not sospechosas, "direcciones públicas escritas a mano: " + ", ".join(sospechosas)


def test_todo_lo_publico_sale_del_mismo_ajuste(monkeypatch):
    """
    Cambiar el ajuste cambia el enlace, la imagen de la tarjeta y el texto que se copia.

    Es la comprobación que convierte «hay un solo ajuste» de afirmación en hecho: se mueve
    el ajuste y se mira que TODO lo que se reparte se mueva con él.
    """
    from app.core.publicaciones import enlace_publico, texto_para_linkedin
    from app.core.redes import texto_para

    monkeypatch.setattr(settings, "PUBLICACIONES_URL_BASE", "https://plurione.example/interes")

    assert base_publica() == "https://plurione.example/interes"
    assert enlace_publico("abc123") == "https://plurione.example/interes/abc123"
    assert "https://plurione.example/interes/abc123" in texto_para_linkedin("Hola", "abc123")
    assert "https://plurione.example/interes/abc123" in texto_para("linkedin", "Hola", "abc123")


def test_el_ajuste_rechaza_una_direccion_mal_escrita():
    """
    Un dedazo en la dirección del túnel se descubre al arrancar y no dentro de un post.

    El validador es del capítulo 26; aquí se fija porque desde el 34 ese valor se cambia a
    mano **cada vez que arranca el túnel**, que es un cambio manual frecuente y por tanto
    una fuente de erratas frecuente.
    """
    from app.core.config import Settings
    from pydantic import ValidationError

    for mala in ("plurione.com/interes", "https:///interes", "https://x.com/interes?r=1"):
        with pytest.raises(ValidationError):
            Settings(PUBLICACIONES_URL_BASE=mala)


# ==============================================================================
# 3. Un enlace repartido bajo otra dirección se sabe caducado
# ==============================================================================

def _campana(**extra) -> Campaign:
    """
    Una publicación en memoria, sin pasar por la base.

    `budget` y `created_at` se dan a mano porque los valores por defecto de una columna los
    pone el INSERT, no el constructor: un objeto que nunca se guardó los tiene a `None` y el
    esquema —que los declara obligatorios, y hace bien— lo rechaza. Aquí no hace falta la
    base para nada: lo que se comprueba es una comparación de dos cadenas.
    """
    campos = {
        "name": "Post de prueba",
        "channel": "LinkedIn",
        "public_slug": "abc123def456",
        "budget": 0.0,
        "created_at": datetime.datetime(2026, 9, 25, tzinfo=datetime.timezone.utc),
    }
    campos.update(extra)
    return Campaign(**campos)


def test_activar_anota_bajo_que_direccion_se_reparte_el_enlace(monkeypatch):
    monkeypatch.setattr(settings, "PUBLICACIONES_URL_BASE", "https://uno.trycloudflare.com/interes")
    campana = _campana(estado=BORRADOR)

    ciclo.fijar_estado(campana, ACTIVA)

    assert campana.url_base_publicada == "https://uno.trycloudflare.com/interes"


def test_un_borrador_no_anota_nada(monkeypatch):
    """Su enlace no se ha repartido: anotarlo diría que salió cuando no salió."""
    monkeypatch.setattr(settings, "PUBLICACIONES_URL_BASE", "https://uno.trycloudflare.com/interes")
    campana = _campana(estado=ACTIVA)

    ciclo.fijar_estado(campana, BORRADOR)

    assert campana.url_base_publicada is None


def test_reactivar_bajo_otra_direccion_no_reescribe_la_primera(monkeypatch):
    """
    La decisión que hace útil el dato.

    Quien tiene el enlace lo copió la **primera** vez. Sobrescribir al reactivar borraría
    justo la prueba de que ese enlace caducó, y la publicación volvería a parecer sana.
    """
    monkeypatch.setattr(settings, "PUBLICACIONES_URL_BASE", "https://uno.trycloudflare.com/interes")
    campana = _campana(estado=BORRADOR)
    ciclo.fijar_estado(campana, ACTIVA)
    ciclo.fijar_estado(campana, PAUSADA)

    monkeypatch.setattr(settings, "PUBLICACIONES_URL_BASE", "https://dos.trycloudflare.com/interes")
    ciclo.fijar_estado(campana, ACTIVA)

    assert campana.url_base_publicada == "https://uno.trycloudflare.com/interes"


def test_el_enlace_se_marca_caducado_cuando_la_direccion_cambia(monkeypatch):
    monkeypatch.setattr(settings, "PUBLICACIONES_URL_BASE", "https://dos.trycloudflare.com/interes")
    campana = _campana(estado=ACTIVA, is_active=True, id=1, url_base_publicada="https://uno.trycloudflare.com/interes")

    ficha = CampanaResponse.model_validate(campana, from_attributes=True)

    assert ficha.enlace_caducado is True
    # Y el enlace que enseña es el de AHORA: lo que caducó está dentro del post, no aquí.
    assert ficha.enlace_publico == "https://dos.trycloudflare.com/interes/abc123def456"


def test_sin_direccion_anotada_no_se_marca_nada(monkeypatch):
    """
    Las publicaciones anteriores al capítulo 34 están a `NULL`: no consta bajo qué dirección
    salieron. Marcarlas inventaría el dato que la columna existe para medir, y una
    advertencia sin fundamento enseña a ignorar las que sí lo tienen.
    """
    monkeypatch.setattr(settings, "PUBLICACIONES_URL_BASE", "https://dos.trycloudflare.com/interes")
    campana = _campana(estado=ACTIVA, is_active=True, id=1, url_base_publicada=None)

    assert CampanaResponse.model_validate(campana, from_attributes=True).enlace_caducado is False


def test_la_direccion_antigua_no_sale_en_la_respuesta(monkeypatch):
    """Al panel le sirve la conclusión, no una dirección de túnel muerta enseñada como dato."""
    monkeypatch.setattr(settings, "PUBLICACIONES_URL_BASE", "https://dos.trycloudflare.com/interes")
    campana = _campana(estado=ACTIVA, is_active=True, id=1, url_base_publicada="https://uno.trycloudflare.com/interes")

    cuerpo = CampanaResponse.model_validate(campana, from_attributes=True).model_dump()

    assert "url_base_publicada" not in cuerpo
    assert "uno.trycloudflare.com" not in str(cuerpo)


# ==============================================================================
# 4. El aviso de que la dirección no responde
# ==============================================================================

@pytest.fixture(autouse=True)
def sin_cache():
    direccion_publica.olvidar_lo_comprobado()
    yield
    direccion_publica.olvidar_lo_comprobado()


def test_apagada_no_sale_a_internet_y_lo_dice(monkeypatch):
    """
    «No comprobada» no es «no responde», y la diferencia es la que hace legible el aviso.

    Con la comprobación apagada —desarrollo, la suite— `responde` es `None` y el panel no
    dibuja nada. Si fuera `False`, la pantalla de publicaciones tendría una alarma encendida
    siempre, y una alarma permanente deja de leerse en dos días.
    """
    monkeypatch.setattr(settings, "COMPROBAR_DIRECCION_PUBLICA", False)

    def explotar(url, timeout):
        raise AssertionError("no debía salir a internet")

    estado = direccion_publica.comprobar(sonda=explotar)

    assert estado.responde is None
    assert estado.comprobada_en is None


def test_una_direccion_que_responde(monkeypatch):
    monkeypatch.setattr(settings, "COMPROBAR_DIRECCION_PUBLICA", True)
    pedidas = []

    def sonda(url, timeout):
        pedidas.append(url)
        return True, "HTTP 200"

    estado = direccion_publica.comprobar(sonda=sonda)

    assert estado.responde is True
    # Pide un slug que no existe a propósito: la ruta pública devuelve 200 con etiquetas
    # genéricas para cualquier slug desconocido (capítulo 27), así que se comprueba el
    # camino entero sin necesidad de que haya ninguna publicación activa.
    assert pedidas == [f"{settings.PUBLICACIONES_URL_BASE}/{direccion_publica.SLUG_DE_COMPROBACION}"]


def test_una_direccion_que_no_responde(monkeypatch):
    monkeypatch.setattr(settings, "COMPROBAR_DIRECCION_PUBLICA", True)

    estado = direccion_publica.comprobar(sonda=lambda url, timeout: (False, "ConnectError"))

    assert estado.responde is False
    assert estado.detalle == "ConnectError"


def test_se_cachea_para_no_salir_a_internet_en_cada_pantalla(monkeypatch):
    monkeypatch.setattr(settings, "COMPROBAR_DIRECCION_PUBLICA", True)
    monkeypatch.setattr(settings, "DIRECCION_PUBLICA_CACHE_SEGUNDOS", 600)
    veces = []

    def sonda(url, timeout):
        veces.append(url)
        return True, "HTTP 200"

    direccion_publica.comprobar(sonda=sonda)
    direccion_publica.comprobar(sonda=sonda)

    assert len(veces) == 1


def test_cambiar_la_direccion_invalida_la_cache(monkeypatch):
    """
    Es el caso que ocurre de verdad: el túnel se reinicia, alguien pone la dirección nueva y
    reinicia la pila. Una caché por tiempo que no mirara la dirección seguiría contestando
    sobre la anterior durante los dos minutos siguientes, que es justo cuando se está
    comprobando si el cambio quedó bien.
    """
    monkeypatch.setattr(settings, "COMPROBAR_DIRECCION_PUBLICA", True)
    monkeypatch.setattr(settings, "DIRECCION_PUBLICA_CACHE_SEGUNDOS", 600)
    monkeypatch.setattr(settings, "PUBLICACIONES_URL_BASE", "https://uno.example/interes")
    veces = []
    direccion_publica.comprobar(sonda=lambda u, t: (veces.append(u), (True, "HTTP 200"))[1])

    monkeypatch.setattr(settings, "PUBLICACIONES_URL_BASE", "https://dos.example/interes")
    estado = direccion_publica.comprobar(sonda=lambda u, t: (veces.append(u), (True, "HTTP 200"))[1])

    assert len(veces) == 2
    assert estado.base == "https://dos.example/interes"


def test_un_429_cuenta_como_que_la_direccion_funciona(monkeypatch):
    """
    Lo que se comprueba es que la dirección **lleva hasta aquí**, no que deje pasar.

    Un 429 del límite de tasa significa que el túnel, nginx y el backend están los tres en
    pie y contestando. Tratarlo como caída habría encendido el aviso justo durante una
    oleada, que es cuando la pantalla tiene que decir la verdad.
    """
    monkeypatch.setattr(settings, "COMPROBAR_DIRECCION_PUBLICA", True)
    llamadas = {}

    class RespuestaFalsa:
        status_code = 429

    def get_falso(url, timeout, follow_redirects):
        llamadas["url"] = url
        return RespuestaFalsa()

    monkeypatch.setattr(direccion_publica.httpx, "get", get_falso)
    estado = direccion_publica.comprobar()

    assert estado.responde is True
    assert estado.detalle == "HTTP 429"


def test_un_530_del_borde_cuenta_como_caida(monkeypatch):
    """
    El caso que de verdad ocurre cuando el túnel se cae, medido.

    Al parar `cloudflared`, el borde de Cloudflare **sigue contestando** por ese nombre
    durante un rato: resuelve, abre TLS y devuelve **530**, su código de «no llego al
    origen». No es un error de conexión, así que una sonda que solo mirara si hubo respuesta
    daría por viva una dirección que no lleva a ninguna parte, que es exactamente el silencio
    que este capítulo existe para romper.

    Es el compañero de `test_un_429_cuenta_como_que_la_direccion_funciona`: uno fija que un
    error del cliente no es una caída, y este que un error del servidor sí lo es.
    """
    monkeypatch.setattr(settings, "COMPROBAR_DIRECCION_PUBLICA", True)

    class RespuestaFalsa:
        status_code = 530

    monkeypatch.setattr(
        direccion_publica.httpx, "get", lambda url, timeout, follow_redirects: RespuestaFalsa()
    )
    estado = direccion_publica.comprobar()

    assert estado.responde is False
    assert estado.detalle == "HTTP 530"
