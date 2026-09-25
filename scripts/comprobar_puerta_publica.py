#!/usr/bin/env python3
"""
Comprueba, ruta por ruta, qué deja pasar la puerta estrecha (capítulo 34).

    python scripts/comprobar_puerta_publica.py https://algo.trycloudflare.com
    python scripts/comprobar_puerta_publica.py http://127.0.0.1:8080

`tests/test_puerta_estrecha.py` lee `nginx.conf` y comprueba que la lista blanca está bien
escrita. Esto es lo otro: le pregunta al servidor de verdad. Son dos comprobaciones y hacen
falta las dos, porque un archivo correcto que no se ha recargado, un contenedor que arrancó
con la imagen anterior o un túnel apuntando al puerto equivocado producen exactamente el
mismo archivo y un comportamiento distinto.

Lo que más importa de este guion es **desde dónde se ejecuta**. Pasándole la dirección del
túnel se ejecuta desde fuera de la red: sale a internet, entra por Cloudflare y llega por el
mismo camino que haría cualquiera. Cualquier atajo —preguntarle a `localhost`, o al
contenedor por su nombre de red— comprobaría otra cosa, y la pregunta de este capítulo es
justamente qué se ve desde fuera.

Devuelve 0 si la puerta se comporta como debe, y 1 nombrando cada desviación.
"""
import argparse
import ssl
import sys
from typing import List, Tuple

import httpx

# Un slug con la forma de los de verdad (`[A-Za-z0-9_-]{6,64}`) que no es de nadie. La ruta
# pública responde 200 con etiquetas genéricas a cualquier slug desconocido —decisión del
# capítulo 27, para que el código de respuesta no diga desde fuera qué enlaces existen—, así
# que se puede comprobar el camino entero sin tocar ninguna publicación real.
SLUG = "comprobacion-de-la-puerta"

# Los dos 404 que hay que saber distinguir
# --------------------------------------
# Un 404 puede venir de dos sitios y significan cosas opuestas:
#
#   * de **nginx**, que no reconoce la ruta. Es «esto no está publicado». Cuerpo HTML.
#   * del **backend**, que sí la atendió y contesta que esa publicación no existe. Es
#     «esto está publicado y funciona». Cuerpo JSON, con su `detail`.
#
# La ruta HTML no da el caso: devuelve 200 con etiquetas genéricas para cualquier slug
# desconocido (capítulo 27, para que el código de respuesta no revele qué enlaces existen).
# La API sí, y con un slug inventado contesta 404 legítimamente. Mirar solo el número daría
# por caída una ruta que está perfectamente publicada, así que se mira de quién es el 404.
JSON = "json"

# (método, ruta, ¿basta con que llegue al backend?, por qué está en la lista)
PUBLICAS: List[Tuple[str, str, bool, str]] = [
    ("GET", f"/interes/{SLUG}", False, "el HTML de la página, con las etiquetas de la tarjeta dentro"),
    ("GET", f"/interes/{SLUG}/tarjeta.png", False, "la imagen 1200x630 de la vista previa"),
    ("GET", f"/api/v1/interes/{SLUG}", True, "la publicación y las listas del formulario"),
    ("GET", "/assets/app.js", False, "el arranque de la aplicación, que el HTML nombra"),
    ("GET", "/assets/app.css", False, "la hoja de estilos de la página"),
]

# Todo lo que NO puede existir desde fuera. La lista blanca de nginx ya lo garantiza; esto
# lo comprueba una por una, porque «garantizado por construcción» es exactamente el tipo de
# afirmación que hay que poder enseñar.
PRIVADAS: List[Tuple[str, str, str]] = [
    ("GET", "/", "la pantalla de acceso del panel"),
    ("GET", "/index.html", "el documento de la SPA"),
    ("GET", "/api/v1/leads", "la cartera de prospectos"),
    ("GET", "/api/v1/leads/1", "una ficha concreta"),
    ("POST", "/api/v1/auth/login", "el inicio de sesión"),
    ("GET", "/api/v1/auth/me", "la sesión actual"),
    ("GET", "/api/v1/users", "las cuentas"),
    ("GET", "/api/v1/sales-reps", "los asesores"),
    ("GET", "/api/v1/audit", "la bitácora de auditoría"),
    ("GET", "/api/v1/analytics/kpis", "los indicadores"),
    ("GET", "/api/v1/campaigns", "el alta y edición de publicaciones"),
    ("GET", "/api/v1/publicaciones/comparativa", "la comparativa entre publicaciones"),
    ("GET", "/api/v1/publicaciones/direccion-publica", "el estado de la dirección pública"),
    ("GET", "/api/v1/agenda/hoy", "la bandeja del día"),
    ("GET", "/api/v1/desenlaces/panel", "el panel de desenlaces"),
    ("GET", "/api/v1/scoring/recalculate-all", "el recálculo masivo"),
    ("POST", "/api/v1/crm/webhook", "la ingesta del CRM"),
    ("GET", "/api/v1/integraciones", "las integraciones y sus secretos"),
    ("GET", "/docs", "la documentación interactiva de la API"),
    ("GET", "/redoc", "la otra documentación"),
    ("GET", "/openapi.json", "el esquema completo de la API"),
    ("GET", "/metrics", "las métricas de Prometheus"),
    ("GET", "/health", "el estado interno del servicio"),
    ("GET", "/api/v1/interes", "la ruta de interés SIN slug, que no es de nadie"),
    ("GET", "/assets/../index.html", "un intento de salirse del directorio de recursos"),
]


def _pedir(cliente: httpx.Client, metodo: str, ruta: str) -> Tuple[int, str]:
    """
    Devuelve `(código, tipo)`, o `(0, motivo)` si no se pudo ni conectar.

    El 0 es un tercer estado y **no puede confundirse con ninguno de los otros dos**. Si un
    fallo de conexión se contara como «no respondió», este guion daría por segura una puerta
    que ni siquiera se comprobó: bastaría con que el túnel estuviera caído para que las
    veinticinco rutas privadas salieran en verde. Se trata aparte y se dice.
    """
    try:
        respuesta = cliente.request(metodo, ruta)
    except httpx.HTTPError as exc:
        return 0, exc.__class__.__name__
    return respuesta.status_code, respuesta.headers.get("content-type", "")


def _contexto_tls(sin_verificar: bool):
    """
    Con qué se verifica el certificado del túnel.

    Por defecto, el **almacén de certificados del sistema** en lugar del paquete `certifi`
    que trae httpx. En una máquina con la salida TLS interceptada —un antivirus, un proxy de
    empresa— el certificado que llega está firmado por una autoridad que solo está en el
    almacén del sistema, y `certifi` la rechaza: el guion decía «no se pudo conectar» sobre
    un túnel que funcionaba perfectamente. Es un fallo de la herramienta que se parece mucho
    a un fallo del sistema comprobado, que es la peor clase de falso negativo.
    """
    if sin_verificar:
        return False
    return ssl.create_default_context()


def main(argv=None) -> int:
    partes = argparse.ArgumentParser(description=__doc__)
    partes.add_argument("base", help="La dirección de la puerta, sin barra final.")
    partes.add_argument("--timeout", type=float, default=15.0)
    partes.add_argument(
        "--sin-verificar-tls",
        action="store_true",
        help=(
            "Ultimo recurso: no verifica el certificado. Solo si el almacen del sistema "
            "tampoco sirve. Lo que se comprueba aqui es el ENCAMINAMIENTO, no el cifrado, "
            "pero una comprobacion sin verificar no puede presentarse como prueba de que la "
            "puerta esta bien cerrada frente a un intermediario."
        ),
    )
    args = partes.parse_args(argv)
    base = args.base.rstrip("/")

    fallos: List[str] = []
    with httpx.Client(
        base_url=base,
        timeout=args.timeout,
        follow_redirects=False,
        verify=_contexto_tls(args.sin_verificar_tls),
    ) as cliente:
        print(f"Puerta: {base}")
        if args.sin_verificar_tls:
            print("AVISO: sin verificar el certificado; comprueba encaminamiento, no cifrado.")
        print()

        print("Lo que la página necesita (tiene que llegar al backend):")
        for metodo, ruta, basta_con_llegar, para_que in PUBLICAS:
            codigo, tipo = _pedir(cliente, metodo, ruta)
            # Se acepta cualquier respuesta del propio sitio menos un 5xx: un 429 del límite
            # de tasa significa que el camino funciona, que es lo que se comprueba.
            bien = codigo != 0 and codigo < 500
            if codigo == 404:
                # Solo vale si lo contestó el backend. El 404 de nginx no lleva cuerpo JSON.
                bien = basta_con_llegar and JSON in tipo
            de_quien = " del backend" if codigo == 404 and bien else ""
            print(
                f"  [{'ok ' if bien else 'MAL'}] {metodo:4} {ruta:46} -> "
                f"{codigo or tipo}{de_quien}  ({para_que})"
            )
            if not bien:
                fallos.append(f"{metodo} {ruta} debería llegar al backend y dio {codigo or tipo}")

        print("\nLo que NO puede existir desde fuera (tiene que dar 404):")
        for metodo, ruta, que_es in PRIVADAS:
            codigo, motivo = _pedir(cliente, metodo, ruta)
            bien = codigo == 404
            visto = codigo if codigo else f"sin conexión ({motivo})"
            print(f"  [{'ok ' if bien else 'MAL'}] {metodo:4} {ruta:46} -> {visto}  ({que_es})")
            if codigo == 0:
                # Ni publicada ni negada: NO COMPROBADA. Decir «está publicada» sería
                # inventar un hallazgo; decir «ok» sería peor, porque daría por cerrada una
                # puerta que no se llegó a mirar.
                fallos.append(f"{metodo} {ruta} ({que_es}) no se pudo comprobar: {motivo}")
            elif not bien:
                fallos.append(
                    f"{metodo} {ruta} ({que_es}) respondió {codigo} en lugar de 404: ESTÁ PUBLICADA"
                )

    print()
    if fallos:
        print(f"FALLO: {len(fallos)} desviación(es).")
        for f in fallos:
            print(f"  - {f}")
        # El caso que se dio de verdad al seguir la guía: comprobar antes de que el backend
        # terminara de arrancar. Las tres rutas que pasan por él dan 502 y el resto está
        # perfecto, que es un patrón muy reconocible y no tiene nada que ver con la puerta.
        # Decirlo aquí evita que alguien salga corriendo a apagar el túnel por nada.
        if all("502" in f for f in fallos) and len(fallos) <= len(PUBLICAS):
            print()
            print("Todos los fallos son 502 y solo en las rutas que pasan por el servidor:")
            print("probablemente todavía estaba arrancando. Espere a que")
            print('`docker ps` diga "(healthy)" y vuelva a ejecutar esto.')
        return 1
    print(
        f"La puerta publica {len(PUBLICAS)} rutas y niega las {len(PRIVADAS)} comprobadas. "
        "Desde fuera, el panel y la API de gestión no existen."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
