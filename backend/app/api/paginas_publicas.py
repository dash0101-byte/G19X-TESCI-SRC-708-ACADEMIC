"""
El HTML de la página de interés, servido por el servidor (capítulo 27).

Estas dos rutas **no** cuelgan de `/api/v1`: son las direcciones que se pegan en una red
social, así que tienen que ser cortas y estables. Son las únicas del sistema que devuelven
HTML y una imagen en lugar de JSON.

    GET /interes/{slug}              el documento, con las etiquetas de la tarjeta dentro
    GET /interes/{slug}/tarjeta.png  la imagen 1200×630 de esa publicación

Por qué aquí y no en el cliente
-------------------------------
LinkedIn, WhatsApp, Facebook y X piden la dirección y **leen el HTML sin ejecutar
JavaScript**. Mientras la ruta la servía el cliente, lo que leían era el `<title>` genérico
del panel: el enlace salía como una tarjeta vacía. Poner las etiquetas con JavaScript no
arregla nada, porque el rastreador se va antes de que se ejecute.

En un despliegue, nginx manda `/interes/` aquí (`frontend/nginx.conf`); en desarrollo el
servidor de Vite sigue sirviendo la ruta y las etiquetas se comprueban pidiéndolas
directamente a este servicio, que es exactamente lo que ve un rastreador.

Lo que estas rutas **no** hacen
-------------------------------
* **No cuentan una visita.** La visita la cuenta `GET /api/v1/interes/{slug}`, que es lo que
  pide la aplicación al montarse. Contar aquí sumaría una visita por cada vez que alguien
  pega el enlace en un chat, y el recuento dejaría de decir cuánta gente abrió la página.
* **No dicen si una publicación existe.** Las cuatro situaciones que no son «activa»
  —borrador, pausada, cerrada y enlace inventado— dan el mismo documento con las mismas
  etiquetas genéricas y el mismo 200. Con un 404 para unas y un 200 para otras, el código de
  respuesta diría desde fuera qué enlaces existen.
"""
import hashlib
import logging
from typing import Optional

from app.core import tarjeta as tarjeta_png
from app.core.config import settings
from app.core.database import get_db
from app.core.etiquetas_sociales import Tarjeta, documento, tarjeta_de, tarjeta_generica
from app.core.proxy import ip_del_cliente
from app.core.publicaciones import ACTIVA, CANAL_LINKEDIN, enlace_publico
from app.core.rate_limit import limiter
from app.models.entities import Campaign
from app.services import ciclo_de_publicaciones as ciclo
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from limits import parse
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter()

# El último segmento del enlace público. Está fijo aquí y en `frontend/src/main.jsx`: es la
# ruta que reconoce la aplicación, y cambiarla en un sitio solo rompería el otro.
RUTA = "/interes"

NOMBRE_DE_LA_IMAGEN = "tarjeta.png"

DEMASIADAS = "Demasiadas peticiones. Inténtalo más tarde."


def _limitar(request: Request) -> None:
    """La cuenta propia de estas dos rutas (véase `INTERES_LIMITE_DE_TARJETAS_POR_IP`)."""
    if not limiter.enabled:
        return
    if not limiter.limiter.hit(
        parse(settings.INTERES_LIMITE_DE_TARJETAS_POR_IP),
        "interes-tarjeta",
        "ip",
        ip_del_cliente(request),
    ):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=DEMASIADAS)


def _publicacion_activa(db: Session, slug: str) -> Optional[Campaign]:
    """
    La publicación si está activa, o `None`. No lanza: aquí «no está» no es un error, es el
    caso en que se sirven etiquetas genéricas.
    """
    ciclo.cerrar_vencidas(db)
    return (
        db.query(Campaign)
        .filter(
            Campaign.public_slug == slug,
            Campaign.estado == ACTIVA,
            Campaign.channel == CANAL_LINKEDIN,
        )
        .first()
    )


def _tarjeta(publicacion: Optional[Campaign], slug: str) -> Tarjeta:
    url = enlace_publico(slug)
    imagen = f"{url}/{NOMBRE_DE_LA_IMAGEN}"
    if publicacion is None:
        return tarjeta_generica(url, imagen)
    return tarjeta_de(publicacion.name, publicacion.description, url, imagen)


@router.get(RUTA + "/{slug}", include_in_schema=False)
def pagina(slug: str, request: Request, db: Session = Depends(get_db)) -> Response:
    """El documento con las etiquetas de la tarjeta y el arranque de la aplicación."""
    _limitar(request)
    ficha = _tarjeta(_publicacion_activa(db, slug), slug)
    html = documento(
        ficha,
        tarjeta_png.ANCHO,
        tarjeta_png.ALTO,
        settings.PAGINA_PUBLICA_SCRIPT,
        settings.PAGINA_PUBLICA_HOJA or None,
    )
    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        # Sin caché: el título de una publicación cambia, y una copia vieja en un
        # intermediario seguiría enseñando la tarjeta de antes durante días.
        headers={"Cache-Control": "no-store, must-revalidate"},
    )


@router.get(RUTA + "/{slug}/" + NOMBRE_DE_LA_IMAGEN, include_in_schema=False)
def imagen_de_la_tarjeta(slug: str, request: Request, db: Session = Depends(get_db)) -> Response:
    """
    La imagen de 1 200 × 630 de esta publicación, dibujada al pedirla.

    No se guarda en ninguna parte: cuesta unas decenas de milisegundos y así nunca enseña un
    título que ya se cambió. Quien la pida otra vez se ahorra la descarga por el `ETag`.
    """
    _limitar(request)
    publicacion = _publicacion_activa(db, slug)
    ficha = _tarjeta(publicacion, slug)
    # Sin publicación activa se dibuja la tarjeta de la marca: el título no se enseña, ni
    # siquiera en una imagen, que es tan legible como el texto.
    png = tarjeta_png.dibujar(ficha.titulo if publicacion is not None else None)

    # Huella estable del contenido. `hash()` de Python cambia en cada proceso, así que un
    # `ETag` hecho con él dejaría de coincidir en cuanto el servicio reiniciara o en cuanto
    # dos workers contestaran a la misma persona.
    etag = 'W/"%s"' % hashlib.blake2b(png, digest_size=8).hexdigest()
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
    return Response(
        content=png,
        media_type="image/png",
        headers={
            "ETag": etag,
            # Un rato de caché en la red social, pero no para siempre: si el líder corrige
            # el título, la tarjeta se pone al día sin tener que volver a compartir nada.
            "Cache-Control": "public, max-age=300",
            "Content-Disposition": f'inline; filename="{NOMBRE_DE_LA_IMAGEN}"',
        },
    )
