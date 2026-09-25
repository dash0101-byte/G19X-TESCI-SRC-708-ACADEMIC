"""
La página de interés: de una solicitud del navegador a un evento del registro.

Por qué no vale el conector firmado
-----------------------------------
Las integraciones (`/api/v1/integraciones/...`) exigen una firma HMAC con un secreto
compartido. Eso sirve entre servidores. Un navegador no puede firmar: el secreto viajaría
dentro de la página y cualquiera lo leería, así que sería un secreto público, es decir,
ninguno. Esta ruta es abierta a propósito y se defiende con lo que sí se puede usar en
público: límite de envíos por IP y por publicación, campo trampa, validación estricta y la
misma respuesta pase lo que pase.

Lo que no hace
--------------
No crea `LeadActivity` ni toca la ficha: arma un `Evento` y se lo da a `registrar_evento`,
como cualquier otra fuente. Así hereda la deduplicación, la minimización y el aviso de
privacidad sin repetirlos.
"""
import logging
import uuid
from typing import Optional

from fastapi import HTTPException, Request, status
from limits import parse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.proxy import ip_del_cliente
from app.core.publicaciones import ACTIVA, CANAL_LINKEDIN, necesidades_de
from app.core.rate_limit import limiter
from app.core.redes import SIN_RED, canal_de, etiqueta_de
from app.core.vector_del_modelo import CATEGORIAS_DEL_MODELO
from app.models.entities import ActivityType, Campaign, utc_now
from app.schemas.interes import (
    OpcionesDelFormulario,
    PublicacionPublica,
    SolicitudDeInteres,
)
from app.services import ciclo_de_publicaciones as ciclo
from app.services.registro_de_actividad import Contacto, Evento

logger = logging.getLogger(__name__)

FUENTE = "pagina_de_interes"

# El canal con el que se guarda la ficha sale de la **red de llegada** (`app/core/redes.py`):
# «LinkedIn», «WhatsApp», «Facebook», «Correo», «Instagram», «X», o «Publicación» cuando no
# consta. Ninguno es «LinkedIn Ads» ni ninguna otra categoría del modelo: una persona que
# llegó por un post orgánico no vino por publicidad pagada, y el modelo trata todos estos
# canales como desconocidos, es decir, neutros.

# El tipo de toda solicitud, sea cual sea la necesidad. Elegir «Ver una demostración» en un
# botón no es una demo pedida: registrarla como `DEMO_REQUEST` le sumaba 25 puntos en la
# regla y encendía `requested_demo` en el modelo. La necesidad viaja en los datos de la
# actividad, para el asesor, y no toca la puntuación.
TIPO_DE_SOLICITUD = ActivityType.FORM_SUBMIT

# La misma frase para todos los casos: alta nueva, correo ya conocido o campo trampa
# relleno. Una respuesta distinta convertiría la página en una forma de comprobar qué
# correos están en la base.
MENSAJE = "Gracias por tu interés. Un asesor de PluriOne se pondrá en contacto contigo."

# «No disponible» cuando la publicación no existe, está desactivada o no es de LinkedIn. El
# mismo texto para los tres: decir cuál de los tres es ayuda a recorrer enlaces ajenos.
NO_DISPONIBLE = "Esta publicación no está disponible."

DEMASIADAS = "Hemos recibido demasiadas solicitudes. Inténtalo más tarde."


def buscar_publicacion(db: Session, slug: str) -> Campaign:
    """
    La publicación, solo si está **activa**. Un borrador, una pausada, una cerrada —también
    la que se acaba de cerrar por fecha— y un enlace inventado responden lo mismo.
    """
    ciclo.cerrar_vencidas(db)
    publicacion = (
        db.query(Campaign)
        .filter(
            Campaign.public_slug == slug,
            Campaign.estado == ACTIVA,
            Campaign.channel == CANAL_LINKEDIN,
        )
        .first()
    )
    if publicacion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NO_DISPONIBLE)
    return publicacion


def describir(publicacion: Campaign) -> PublicacionPublica:
    """
    Lo que ve cualquiera: el título y el texto de la publicación, y las listas del
    formulario. El presupuesto, a quién va dirigida y el identificador no salen de casa.
    """
    return PublicacionPublica(
        titulo=publicacion.name,
        descripcion=publicacion.description,
        opciones=OpcionesDelFormulario(
            cargos=list(CATEGORIAS_DEL_MODELO["job_title"]),
            sectores=list(CATEGORIAS_DEL_MODELO["industry"]),
            tamanos=list(CATEGORIAS_DEL_MODELO["company_size"]),
            necesidades=necesidades_de(publicacion.necesidades),
        ),
    )


def aplicar_limites(request: Request, slug: str) -> None:
    """
    Los límites de **envío**. Dos, y los dos hacen falta.

    El de IP frena a quien envía en bucle desde un sitio. El de publicación frena al mismo
    envío repartido entre muchas IP: sin él, un enlace difundido puede llenar la base de
    fichas basura aunque ninguna IP pase de su cuenta.
    """
    if not limiter.enabled:
        return
    ip = ip_del_cliente(request)
    for limite, ambito, clave in (
        (settings.INTERES_LIMITE_POR_IP, "ip", ip),
        (settings.INTERES_LIMITE_POR_PUBLICACION, "publicacion", slug),
    ):
        if not limiter.limiter.hit(parse(limite), "interes", ambito, clave):
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=DEMASIADAS)


def aplicar_limite_de_lectura(request: Request) -> None:
    """
    Abrir la página tiene su propia cuenta, separada de la de envíos. Si ver el formulario
    gastara el cupo de enviarlo, unas cuantas visitas desde la misma oficina dejarían sin
    poder enviar a quien de verdad quería hacerlo.
    """
    if not limiter.enabled:
        return
    if not limiter.limiter.hit(
        parse(settings.INTERES_LIMITE_DE_LECTURAS_POR_IP), "interes-lectura", "ip", ip_del_cliente(request)
    ):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=DEMASIADAS)


def comprobar_necesidad(solicitud: SolicitudDeInteres, publicacion: Campaign) -> str:
    """
    La necesidad tiene que ser una de las opciones de **esta** publicación. Devuelve su
    etiqueta. El error tiene la misma forma que los del esquema, para que la página lo
    ponga junto al campo.
    """
    opciones = necesidades_de(publicacion.necesidades)
    if solicitud.necesidad not in opciones:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[{
                "loc": ["body", "necesidad"],
                "msg": "Elige un motivo de la lista.",
                "type": "value_error",
            }],
        )
    return opciones[solicitud.necesidad]


def es_robot(solicitud: SolicitudDeInteres) -> bool:
    """El campo trampa está oculto en la página: si viene relleno, no lo rellenó una persona."""
    return bool(solicitud.sitio_web.strip())


def construir_evento(
    solicitud: SolicitudDeInteres,
    publicacion: Campaign,
    etiqueta_de_necesidad: str,
    asesor_id: Optional[int] = None,
    red: Optional[str] = None,
) -> Evento:
    """
    El evento que se registra. Lo que la persona no indicó no viaja, y por tanto queda
    vacío en la ficha: ni ingresos, ni teléfono, ni perfil, ni tamaño «1-10» por defecto.
    El país tampoco. Hasta el capítulo 32 lo rellenaba la ficha —«México» era el valor por
    defecto de la columna—, de modo que este formulario, que no pregunta el país, producía
    fichas con país. Ya no: la columna admite vacío y lo que nadie indicó queda vacío. No
    puntúa ni en la regla ni en el modelo, así que lo único que se pierde es una suposición.

    La necesidad va en los datos de la actividad y no en la ficha: es de este envío, no de
    la persona, y la ficha 360 y el informe la leen de ahí. Fuera de `raw_metadata`, que la
    regla heurística y la explicación sí leen, no puede acabar puntuando por un descuido.
    Va con su **etiqueta**, tal como la vio la persona: si el líder cambia después las
    opciones de la publicación, lo que eligió quien ya escribió no cambia con ellas.

    `asesor_id` es el responsable de la publicación: una ficha **nueva** nace asignada a él.
    Una que ya existía no se reasigna, porque esta fuente no toca fichas existentes.

    `red` es por dónde llegó (capítulo 27). Decide el **canal** de la ficha —«WhatsApp»,
    «Facebook»…— y se guarda también en la actividad, con su etiqueta, para que la ficha 360
    pueda decir «Llegó por la publicación X, vía WhatsApp». Ninguno de esos canales lo
    conoce el modelo, así que todos cuentan como desconocido, es decir, neutro: igual que
    «LinkedIn» desde el capítulo 25. Cuando no consta la red, el canal es «Publicación»: la
    página se pudo compartir desde cualquier sitio y escribir «LinkedIn» sería inventarlo.
    """
    ahora = utc_now()
    extra = {"perfil_de_linkedin": solicitud.linkedin} if solicitud.linkedin else {}
    canal = canal_de(red)

    return Evento(
        fuente=FUENTE,
        tipo=TIPO_DE_SOLICITUD,
        ocurrido_en=ahora,
        # Propio de cada envío: dos envíos de la misma persona son dos hechos distintos y
        # los dos cuentan, pero una entrega repetida del mismo (un reintento de la página)
        # no se registra dos veces.
        identificador_externo=f"{publicacion.public_slug}:{uuid.uuid4().hex}",
        canal=canal,
        # Lo que la ficha 360 enseña de cada solicitud. El aviso se guarda **en el envío**
        # y no solo en la ficha: la ficha conserva el primero —no se pisa nunca—, y quien
        # llama necesita saber cuándo consintió esta persona esta publicación en concreto.
        datos={
            "publicacion": publicacion.public_slug,
            "necesidad": solicitud.necesidad,
            "necesidad_etiqueta": etiqueta_de_necesidad,
            # La red de llegada, con su etiqueta, igual que la necesidad: la clave es lo que
            # se cuenta y la etiqueta lo que se enseña. `sin_red` cuando no consta.
            "red": red or SIN_RED,
            "red_etiqueta": etiqueta_de(red),
            "aviso_aceptado_en": ahora.isoformat(),
        },
        contacto=Contacto(
            email=solicitud.correo,
            telefono=solicitud.telefono,
            nombre=solicitud.nombre,
        ),
        prospecto={
            # Entero en `first_name`: partirlo sería adivinar dónde empiezan los apellidos.
            "first_name": solicitud.nombre,
            "last_name": "",
            "email": solicitud.correo,
            "phone": solicitud.telefono,
            "company": solicitud.empresa,
            "job_title": solicitud.cargo,
            "industry": solicitud.sector,
            "company_size": solicitud.tamano_de_empresa,
            "source": canal,
            "raw_metadata": extra,
            "assigned_rep_id": asesor_id,
        },
        campana_id=publicacion.id,
        aviso_de_privacidad_aceptado_en=ahora,
    )


def anotar(publicacion: Campaign, estado: str, ip: Optional[str]) -> None:
    """Deja rastro del envío sin el correo ni el nombre de quien lo mandó."""
    logger.info(
        "Página de interés: solicitud %s para la publicación %s (campaña %s) desde %s.",
        estado, publicacion.public_slug, publicacion.id, ip,
    )
