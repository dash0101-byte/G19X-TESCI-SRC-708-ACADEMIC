"""
Conectores: Calendly, WhatsApp, LinkedIn Lead Gen y el formulario web.

Cada conector hace una sola cosa: traducir la carga que entrega su sistema a uno o varios
`Evento`. No escribe en la base, no decide si el evento es válido ni a quién pertenece;
eso lo hace `registrar_evento`, igual para todos. Así un conector nuevo no puede saltarse
la validación, la deduplicación ni la minimización, porque no tiene cómo.

Las cargas
----------
Las formas que se aceptan son las que entrega el conector de cada sistema, reducidas a lo
que el registro necesita. Se parecen a las de origen —el `invitee.created` de Calendly,
el `entry[].changes[].value` de la API de WhatsApp Business— pero no pretenden ser sus
esquemas completos: en esta fase no hay cuentas en esos sistemas contra las que
contrastarlas (capítulo 21, «Lo que esta fase no hizo»). La firma tampoco es la de cada
proveedor: todas se firman con el mismo esquema HMAC del webhook CRM, cada una con su
secreto.

Lo que no se copia
------------------
Ningún conector lleva a su `Evento` el texto de un mensaje, las respuestas libres de un
formulario ni las preguntas de una reserva. No hace falta retirarlos después: nunca
entran. `registrar_evento` retira además las claves de contenido de lo poco que sí pasa.
"""
import datetime
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from fastapi import HTTPException, Request, status
from limits import parse

from app.core.config import settings
from app.core.proxy import ip_del_cliente
from app.core.rate_limit import limiter
from app.core.texto import texto_o_nada
from app.models.entities import ActivityType, MessageDirection
from app.services.registro_de_actividad import Contacto, Evento, EventoInvalido

# ==============================================================================
# Utilidades de lectura
# ==============================================================================

# La definición de «vacío» de este módulo era propia hasta el capítulo 41: otro nombre y el
# mismo cuerpo que `_texto_o_vacio` en los esquemas de la ficha. Las dos eran correctas y
# estaban de acuerdo por casualidad, porque quien tocara una no tenía por qué saber de la
# otra. Ahora las dos son `app.core.texto.texto_o_nada`, que conserva el comportamiento de
# **esta** copia —un diccionario o una lista donde se esperaba texto devuelven nada, no su
# `repr`—, por ser la que lee cargas de sistemas ajenos.
_texto = texto_o_nada


def _objeto(carga: Dict[str, Any], clave: str) -> Dict[str, Any]:
    valor = carga.get(clave)
    if not isinstance(valor, dict):
        raise EventoInvalido(f"Falta el objeto '{clave}' en la carga.", clave)
    return valor


def _lista_de_objetos(valor: Any) -> List[Dict[str, Any]]:
    if not isinstance(valor, list):
        return []
    return [elemento for elemento in valor if isinstance(elemento, dict)]


def _fecha_iso(valor: Any, campo: str) -> datetime.datetime:
    texto = _texto(valor)
    if texto is None:
        raise EventoInvalido(f"Falta la fecha '{campo}'.", campo)
    try:
        momento = datetime.datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        raise EventoInvalido(f"'{campo}' no es una fecha ISO 8601.", campo) from None
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=datetime.timezone.utc)
    return momento


def _fecha_epoch(valor: Any, campo: str, *, milisegundos: bool = False) -> datetime.datetime:
    try:
        segundos = float(valor)
    except (TypeError, ValueError):
        raise EventoInvalido(f"'{campo}' no es una marca de tiempo numérica.", campo) from None
    if milisegundos:
        segundos /= 1000.0
    try:
        return datetime.datetime.fromtimestamp(segundos, tz=datetime.timezone.utc)
    except (OverflowError, OSError, ValueError):
        raise EventoInvalido(f"'{campo}' está fuera de rango.", campo) from None


def _numero_de_whatsapp(wa_id: Any) -> Optional[str]:
    """WhatsApp identifica por el número sin «+»; `registrar_evento` lo normaliza a E.164."""
    texto = _texto(wa_id)
    if texto is None:
        return None
    return texto if texto.startswith("+") else f"+{texto}"


# ==============================================================================
# Conectores
# ==============================================================================

def adaptar_calendly(carga: Dict[str, Any]) -> List[Evento]:
    """
    `invitee.created`: alguien reservó una reunión. Es la reunión agendada verificada, la
    que el pipeline solo puede declarar. Las respuestas del formulario de reserva no se
    leen: son texto libre de la persona.
    """
    evento = carga.get("event")
    if evento != "invitee.created":
        raise EventoInvalido(
            f"Evento de Calendly no admitido: '{evento}'. Se registra 'invitee.created'.", "event"
        )
    invitado = _objeto(carga, "payload")
    reunion = invitado.get("scheduled_event") if isinstance(invitado.get("scheduled_event"), dict) else {}
    return [
        Evento(
            fuente="calendly",
            tipo=ActivityType.MEETING_SCHEDULED,
            ocurrido_en=_fecha_iso(invitado.get("created_at"), "payload.created_at"),
            identificador_externo=_texto(invitado.get("uri")),
            canal="Calendly",
            datos={"inicio_de_la_reunion": _texto(reunion.get("start_time"))},
            contacto=Contacto(
                email=_texto(invitado.get("email")),
                telefono=_texto(invitado.get("text_reminder_number")),
                nombre=_texto(invitado.get("name")),
            ),
        )
    ]


def adaptar_whatsapp(carga: Dict[str, Any]) -> List[Evento]:
    """
    Mensajes recibidos (`messages`) y enviados (`statuses` con `status: sent`).

    De un mensaje se toma su identificador, su fecha, el número y si fue de entrada o de
    salida. `text.body`, `caption` y cualquier otro contenido no se leen. Los estados
    `delivered` y `read` de un envío no son mensajes nuevos y no se registran.
    """
    eventos: List[Evento] = []
    for entrada in _lista_de_objetos(carga.get("entry")):
        for cambio in _lista_de_objetos(entrada.get("changes")):
            valor = cambio.get("value") if isinstance(cambio.get("value"), dict) else {}
            nombres = {
                _texto(contacto.get("wa_id")): _texto((contacto.get("profile") or {}).get("name"))
                for contacto in _lista_de_objetos(valor.get("contacts"))
                if isinstance(contacto.get("profile") or {}, dict)
            }
            for mensaje in _lista_de_objetos(valor.get("messages")):
                eventos.append(
                    Evento(
                        fuente="whatsapp",
                        tipo=ActivityType.WHATSAPP_MESSAGE,
                        direccion=MessageDirection.ENTRANTE,
                        ocurrido_en=_fecha_epoch(mensaje.get("timestamp"), "messages.timestamp"),
                        identificador_externo=_texto(mensaje.get("id")),
                        canal="WhatsApp",
                        datos={"tipo_de_contenido": _texto(mensaje.get("type"))},
                        contacto=Contacto(
                            telefono=_numero_de_whatsapp(mensaje.get("from")),
                            nombre=nombres.get(_texto(mensaje.get("from"))),
                        ),
                    )
                )
            for estado in _lista_de_objetos(valor.get("statuses")):
                if estado.get("status") != "sent":
                    continue
                eventos.append(
                    Evento(
                        fuente="whatsapp",
                        tipo=ActivityType.WHATSAPP_MESSAGE,
                        direccion=MessageDirection.SALIENTE,
                        ocurrido_en=_fecha_epoch(estado.get("timestamp"), "statuses.timestamp"),
                        identificador_externo=_texto(estado.get("id")),
                        canal="WhatsApp",
                        contacto=Contacto(telefono=_numero_de_whatsapp(estado.get("recipient_id"))),
                    )
                )
    if not eventos:
        raise EventoInvalido("La entrega de WhatsApp no trae mensajes ni envíos que registrar.", "entry")
    return eventos


def adaptar_linkedin_lead_gen(carga: Dict[str, Any]) -> List[Evento]:
    """
    Una respuesta a un formulario de LinkedIn Lead Gen: genera prospecto.

    El consentimiento se lee de `consent.privacyPolicy`; si es verdadero, se registra la
    aceptación del aviso de privacidad con la fecha del envío.
    """
    respuestas = _objeto(carga, "answers")
    enviado = _fecha_epoch(carga.get("submittedAt"), "submittedAt", milisegundos=True)
    consentimiento = carga.get("consent") if isinstance(carga.get("consent"), dict) else {}
    email = _texto(respuestas.get("emailAddress"))
    telefono = _texto(respuestas.get("phoneNumber"))
    nombre = _texto(respuestas.get("firstName"))
    apellido = _texto(respuestas.get("lastName"))
    return [
        Evento(
            fuente="linkedin_lead_gen",
            tipo=ActivityType.FORM_SUBMIT,
            ocurrido_en=enviado,
            identificador_externo=_texto(carga.get("leadId")),
            canal="LinkedIn",
            datos={"formulario": _texto(carga.get("formId"))},
            contacto=Contacto(email=email, telefono=telefono, nombre=" ".join(filter(None, (nombre, apellido))) or None),
            prospecto={
                "email": email,
                "first_name": nombre,
                "last_name": apellido,
                "company": _texto(respuestas.get("companyName")),
                "job_title": _texto(respuestas.get("jobTitle")),
                "phone": telefono,
                "industry": _texto(respuestas.get("industry")),
                "company_size": _texto(respuestas.get("companySize")),
                "country": _texto(respuestas.get("country")),
                "city": _texto(respuestas.get("city")),
                "source": "LinkedIn Lead Gen",
            },
            aviso_de_privacidad_aceptado_en=enviado if consentimiento.get("privacyPolicy") is True else None,
        )
    ]


FORMULARIOS_WEB: Dict[str, ActivityType] = {
    "contacto": ActivityType.FORM_SUBMIT,
    "demo": ActivityType.DEMO_REQUEST,
    "descarga": ActivityType.CONTENT_DOWNLOAD,
}


def adaptar_formulario_web(carga: Dict[str, Any]) -> List[Evento]:
    """
    Un envío del formulario del sitio: genera prospecto.

    El formulario dice cuál es (`contacto`, `demo`, `descarga`); uno desconocido se
    rechaza. `campos.mensaje` —la caja de texto libre— no se copia a ninguna parte.
    """
    formulario = _texto(carga.get("formulario"))
    tipo = FORMULARIOS_WEB.get(formulario or "")
    if tipo is None:
        admitidos = ", ".join(FORMULARIOS_WEB)
        raise EventoInvalido(
            f"Formulario desconocido: '{formulario}'. Admitidos: {admitidos}.", "formulario"
        )
    campos = _objeto(carga, "campos")
    enviado = _fecha_iso(carga.get("enviado_en"), "enviado_en")
    aviso = carga.get("aviso_de_privacidad") if isinstance(carga.get("aviso_de_privacidad"), dict) else {}
    email = _texto(campos.get("email"))
    telefono = _texto(campos.get("telefono"))
    nombre = _texto(campos.get("nombre"))
    apellidos = _texto(campos.get("apellidos"))
    return [
        Evento(
            fuente="formulario_web",
            tipo=tipo,
            ocurrido_en=enviado,
            identificador_externo=_texto(carga.get("envio_id")),
            canal="Web",
            datos={
                "formulario": formulario,
                "pagina": _texto(carga.get("pagina")),
                "version_del_aviso": _texto(aviso.get("version")),
            },
            contacto=Contacto(email=email, telefono=telefono, nombre=" ".join(filter(None, (nombre, apellidos))) or None),
            prospecto={
                "email": email,
                "first_name": nombre,
                "last_name": apellidos,
                "company": _texto(campos.get("empresa")),
                "job_title": _texto(campos.get("cargo")),
                "phone": telefono,
                "industry": _texto(campos.get("industria")),
                "company_size": _texto(campos.get("tamano_empresa")),
                "city": _texto(campos.get("ciudad")),
                "source": "Formulario web",
            },
            aviso_de_privacidad_aceptado_en=enviado if aviso.get("aceptado") is True else None,
        )
    ]


# ==============================================================================
# Registro de integraciones
# ==============================================================================

@dataclass(frozen=True)
class Integracion:
    # Segmento de la ruta: `/api/v1/integraciones/{nombre}/eventos`.
    nombre: str
    # `INTEGRACION_<prefijo>_ACTIVA`, `_SECRETO` y `_LIMITE`.
    prefijo: str
    adaptar: Callable[[Dict[str, Any]], List[Evento]]

    @property
    def activa(self) -> bool:
        return bool(getattr(settings, f"INTEGRACION_{self.prefijo}_ACTIVA"))

    @property
    def secreto(self) -> str:
        return getattr(settings, f"INTEGRACION_{self.prefijo}_SECRETO")

    @property
    def limite(self) -> str:
        return getattr(settings, f"INTEGRACION_{self.prefijo}_LIMITE")


INTEGRACIONES: Dict[str, Integracion] = {
    integracion.nombre: integracion
    for integracion in (
        Integracion("calendly", "CALENDLY", adaptar_calendly),
        Integracion("whatsapp", "WHATSAPP", adaptar_whatsapp),
        Integracion("linkedin-lead-gen", "LINKEDIN_LEAD_GEN", adaptar_linkedin_lead_gen),
        Integracion("formulario-web", "FORMULARIO_WEB", adaptar_formulario_web),
    )
}


def aplicar_limite(integracion: Integracion, request: Request) -> None:
    """
    El límite es de la integración, no de la ruta: la cuenta de Calendly no consume la de
    WhatsApp aunque compartan endpoint. Usa el mismo almacén que el resto de límites, así
    que `RATE_LIMIT_STORAGE_URI` y `RATE_LIMIT_ENABLED` valen también aquí.
    """
    if not limiter.enabled:
        return
    if not limiter.limiter.hit(parse(integracion.limite), "integracion", integracion.nombre, ip_del_cliente(request)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas entregas de esta integración. Reintente más tarde.",
        )
