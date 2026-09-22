"""
La página de interés, abierta a cualquiera: `/api/v1/interes/{slug}`.

Es la única parte del sistema sin sesión, y por eso el orden de las comprobaciones importa:

1. **Límite**, antes de mirar nada más: de envíos por IP y por publicación en el `POST`, y de
   lecturas por IP en el `GET`, cada uno con su propia cuenta.
2. **¿Existe la publicación, está activa y es de LinkedIn?** Si no, 404 con el mismo texto
   en los tres casos.
3. **Validación estricta** del formulario (esquema `SolicitudDeInteres`): listas cerradas,
   perfil de LinkedIn con forma de perfil, aviso aceptado y ningún campo de más.
4. **Campo trampa**: si viene relleno, no se registra nada y se responde lo mismo que a un
   envío bueno. Un robot no debe poder distinguir si su envío sirvió.
5. **Registro** por `registrar_evento`, igual que cualquier otra fuente.

La respuesta es siempre la misma: exista o no el correo, sea la primera vez o la quinta.
"""
import logging

from app.core.database import get_db
from app.core.proxy import ip_del_cliente
from app.models.entities import utc_now
from app.schemas.interes import PublicacionPublica, RespuestaDeInteres, SolicitudDeInteres
from app.services import ciclo_de_publicaciones, pagina_de_interes
from app.services.registro_de_actividad import registrar_evento
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{slug}", response_model=PublicacionPublica)
def ver_publicacion(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """La publicación y las listas del formulario. Sin sesión."""
    pagina_de_interes.aplicar_limite_de_lectura(request)
    publicacion = pagina_de_interes.buscar_publicacion(db, slug)
    # Una visita más en el recuento del día. Solo el número: ni IP, ni navegador, ni cookie.
    ciclo_de_publicaciones.registrar_visita(db, publicacion)
    return pagina_de_interes.describir(publicacion)


@router.post("/{slug}", response_model=RespuestaDeInteres, status_code=status.HTTP_202_ACCEPTED)
async def registrar_interes(
    slug: str,
    solicitud: SolicitudDeInteres,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Recibe una solicitud de contacto y la registra.

    Responde 202: la solicitud queda aceptada y lo que pase después —si crea ficha, si se
    suma a una que ya existía, qué score sale— no es asunto de quien la envía.
    """
    pagina_de_interes.aplicar_limites(request, slug)
    publicacion = pagina_de_interes.buscar_publicacion(db, slug)
    ip = ip_del_cliente(request)

    if pagina_de_interes.es_robot(solicitud):
        pagina_de_interes.anotar(publicacion, "descartada (campo trampa)", ip)
        return RespuestaDeInteres(mensaje=pagina_de_interes.MENSAJE, recibido_en=utc_now())

    etiqueta = pagina_de_interes.comprobar_necesidad(solicitud, publicacion)
    resultado = await registrar_evento(
        db,
        pagina_de_interes.construir_evento(
            solicitud, publicacion, etiqueta, ciclo_de_publicaciones.asesor_para(db, publicacion)
        ),
    )
    pagina_de_interes.anotar(
        publicacion,
        "registrada (ficha nueva)" if resultado.prospecto_creado else f"registrada ({resultado.estado})",
        ip,
    )
    return RespuestaDeInteres(mensaje=pagina_de_interes.MENSAJE, recibido_en=utc_now())
