"""
Un solo camino para registrar una actividad: `registrar_evento()`.

Hasta la Fase 15 había tres, y cada uno validaba a su manera:

* el formulario del panel escribía por `ActivityRepository` lo que mandara el cliente,
  incluido un «peso» que el scoring nunca leía;
* el webhook del CRM traducía el tipo por su nombre y, si no lo conocía, registraba un
  `FORM_SUBMIT` y lo dejaba anotado en un aviso del registro de texto;
* el alta de un prospecto por webhook inventaba industria «Tecnología» y tamaño «1-10»
  para que la ficha puntuara.

Ahora el panel, el cambio de etapa, el CRM y los conectores construyen un `Evento` y lo
entregan aquí. Lo que no pasa por esta función no llega a `lead_activities`, y la suite lo
comprueba buscando quién más construye filas de esa tabla.

Qué decide
----------
* **Si el evento es válido**: tipo conocido y admitido para su fuente, resultado en las
  llamadas, dirección en los mensajes, fecha que no está en el futuro, teléfono en E.164.
  Lo que no, se rechaza con un motivo (`EventoInvalido`, que los endpoints dan como 422).
* **Si ya estaba**: `(source, external_event_id)` es único para siempre. Un evento repetido
  devuelve lo que se registró la primera vez y no vuelve a puntuar.
* **A quién pertenece**: por correo, y si no hay correo, por teléfono. Si no pertenece a
  nadie, solo las fuentes que generan prospectos crean ficha; el resto va a la bandeja
  «Sin asociar».
* **Qué se guarda**: nunca el texto de un mensaje. Las claves de contenido se retiran de
  los datos antes de escribir nada, también de lo que se guarda del CRM.
"""
import datetime
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Iterable, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.telefono import TelefonoInvalido, normalizar_telefono
from app.models.entities import (
    ActivityType,
    CallOutcome,
    Lead,
    LeadActivity,
    LeadStatus,
    MessageDirection,
    UnmatchedEvent,
    utc_now,
)

logger = logging.getLogger(__name__)

# Un aviso con fecha unos minutos en el futuro es un reloj desajustado; una hora, un error.
TOLERANCIA_AL_FUTURO = datetime.timedelta(minutes=5)
MAX_IDENTIFICADOR_EXTERNO = 200
MAX_CANAL = 50
MAX_NOTAS = 500

ESTADO_REGISTRADA = "registrada"
ESTADO_DUPLICADA = "duplicada"
ESTADO_SIN_ASOCIAR = "sin_asociar"

# «Mensajes directos»: los que llevan dirección y nunca texto. Para el modelo son dos
# variables desde el capítulo 24 —`whatsapp_messages` y `linkedin_messages`—; aquí se
# agrupan solo porque se validan igual.
TIPOS_DE_MENSAJE_DIRECTO: FrozenSet[ActivityType] = frozenset(
    {ActivityType.WHATSAPP_MESSAGE, ActivityType.LINKEDIN_MESSAGE}
)

# Lo que el pipeline registra por sí mismo al cambiar de etapa. El asesor ya no lo declara
# aparte: declararlo dos veces era la forma más corta de inflar un score.
ETAPA_A_ACTIVIDAD: Dict[LeadStatus, ActivityType] = {
    LeadStatus.PROPOSAL_SENT: ActivityType.PROPOSAL_SENT,
    LeadStatus.MEETING_SCHEDULED: ActivityType.MEETING_SCHEDULED,
}
TIPOS_DEL_PIPELINE: FrozenSet[ActivityType] = frozenset(ETAPA_A_ACTIVIDAD.values())

CANAL_POR_TIPO: Dict[ActivityType, str] = {
    ActivityType.PHONE_CALL: "Teléfono",
    ActivityType.WHATSAPP_MESSAGE: "WhatsApp",
    ActivityType.LINKEDIN_MESSAGE: "LinkedIn",
    ActivityType.MEETING_SCHEDULED: "Reunión",
    ActivityType.PROPOSAL_SENT: "Email",
    ActivityType.EMAIL_OPEN: "Email",
    ActivityType.EMAIL_CLICK: "Email",
    ActivityType.WEBINAR_ATTEND: "Webinar",
    ActivityType.CHAT_INTERACTION: "Chat",
}
CANAL_POR_DEFECTO = "Web"

# Claves cuyo valor es el contenido de un mensaje. Se retiran a cualquier profundidad de los
# datos que llegan de fuera, antes de escribir nada.
CLAVES_DE_CONTENIDO: FrozenSet[str] = frozenset(
    {
        "text", "texto", "body", "cuerpo", "message", "mensaje", "messages", "mensajes",
        "content", "contenido", "caption", "transcript", "transcripcion", "subject",
        "asunto", "html", "snippet", "preview",
    }
)

# Atributos del prospecto que una fuente puede traer, con el ancho de su columna.
CAMPOS_DEL_PROSPECTO: Dict[str, int] = {
    "first_name": 100,
    "last_name": 100,
    "email": 150,
    "phone": 50,
    "company": 150,
    "job_title": 100,
    "industry": 100,
    "company_size": 50,
    "country": 100,
    "city": 100,
    "source": 100,
}
# Lo que una entrega posterior de una fuente que genera prospectos puede actualizar.
CAMPOS_ACTUALIZABLES = ("job_title", "company", "industry", "company_size", "annual_revenue")

TODOS_LOS_TIPOS: FrozenSet[ActivityType] = frozenset(ActivityType)


@dataclass(frozen=True)
class Fuente:
    nombre: str
    etiqueta: str
    # Si un evento de esta fuente con un correo desconocido crea la ficha.
    crea_prospecto: bool
    # Si lo vio un sistema. Lo declarado por una persona no lo es.
    verificada: bool
    # Si trae identificador y fecha propios, sin los que no hay deduplicación posible.
    externa: bool
    tipos: FrozenSet[ActivityType]
    # Si una entrega posterior puede reescribir los atributos de una ficha que ya existe.
    # La página de interés no: lo que escribió una persona en el panel no lo pisa un
    # formulario rellenado meses después, y quien lo envió no tiene por qué ser quien manda
    # sobre la ficha. Su solicitud se suma al historial y ya.
    actualiza_prospecto: bool = True


FUENTES: Dict[str, Fuente] = {
    fuente.nombre: fuente
    for fuente in (
        Fuente("manual", "Registro manual", False, False, False, TODOS_LOS_TIPOS - TIPOS_DEL_PIPELINE),
        Fuente("pipeline", "Cambio de etapa", False, False, False, TIPOS_DEL_PIPELINE),
        Fuente("crm", "CRM", True, True, True, TODOS_LOS_TIPOS),
        Fuente(
            "formulario_web", "Formulario web", True, True, True,
            frozenset({ActivityType.FORM_SUBMIT, ActivityType.DEMO_REQUEST, ActivityType.CONTENT_DOWNLOAD}),
        ),
        Fuente("linkedin_lead_gen", "LinkedIn Lead Gen", True, True, True, frozenset({ActivityType.FORM_SUBMIT})),
        # La página de interés: nuestro propio formulario público. Genera prospecto y es
        # verificada porque el envío lo registró el sistema al recibirlo, no un asesor
        # contando lo que recuerda; lo que la persona escribió en él sigue siendo declarado
        # por ella, como en cualquier formulario.
        Fuente(
            "pagina_de_interes", "Página de interés", True, True, True,
            frozenset({ActivityType.FORM_SUBMIT, ActivityType.DEMO_REQUEST}),
            actualiza_prospecto=False,
        ),
        Fuente("calendly", "Calendly", False, True, True, frozenset({ActivityType.MEETING_SCHEDULED})),
        Fuente("whatsapp", "WhatsApp", False, True, True, frozenset({ActivityType.WHATSAPP_MESSAGE})),
    )
}


class EventoInvalido(ValueError):
    """El evento no se puede registrar. `motivo` se entrega tal cual a quien lo envió."""

    def __init__(self, motivo: str, campo: Optional[str] = None):
        super().__init__(motivo)
        self.motivo = motivo
        self.campo = campo

    def como_detalle(self) -> Dict[str, Any]:
        return {"motivo": self.motivo, "campo": self.campo}


@dataclass
class Contacto:
    email: Optional[str] = None
    telefono: Optional[str] = None
    nombre: Optional[str] = None


@dataclass
class Evento:
    """Lo que una fuente dice que ocurrió, antes de validarlo."""
    fuente: str
    tipo: Any
    ocurrido_en: Optional[datetime.datetime] = None
    identificador_externo: Optional[str] = None
    direccion: Any = None
    resultado_de_llamada: Any = None
    canal: Optional[str] = None
    notas: Optional[str] = None
    datos: Dict[str, Any] = field(default_factory=dict)
    contacto: Contacto = field(default_factory=Contacto)
    # Atributos del prospecto, para las fuentes que crean o actualizan la ficha.
    prospecto: Dict[str, Any] = field(default_factory=dict)
    # Campaña a la que se atribuye la ficha cuando el evento la crea. Solo se aplica al
    # crearla: cambiar la campaña de una ficha que ya existe reescribiría la atribución de
    # una inversión pasada con la de otra.
    campana_id: Optional[int] = None
    aviso_de_privacidad_aceptado_en: Optional[datetime.datetime] = None


@dataclass(frozen=True)
class EventoValidado:
    fuente: Fuente
    tipo: ActivityType
    ocurrido_en: datetime.datetime
    identificador_externo: Optional[str]
    direccion: Optional[str]
    resultado_de_llamada: Optional[str]
    canal: str
    datos: Dict[str, Any]
    contacto: Contacto
    prospecto: Dict[str, Any]
    campana_id: Optional[int]
    aviso_de_privacidad_aceptado_en: Optional[datetime.datetime]


@dataclass
class ResultadoDelRegistro:
    estado: str
    lead: Optional[Lead] = None
    actividad: Optional[LeadActivity] = None
    sin_asociar: Optional[UnmatchedEvent] = None
    prospecto_creado: bool = False
    score_anterior: Optional[float] = None
    score: Optional[float] = None
    categoria: Optional[str] = None
    score_result: Any = None


# ==============================================================================
# Validación
# ==============================================================================

def _aware(momento: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
    if momento is None:
        return None
    if momento.tzinfo is None:
        return momento.replace(tzinfo=datetime.timezone.utc)
    return momento


def tipo_de_actividad(valor: Any) -> ActivityType:
    """
    El tipo, estrictamente. Un tipo desconocido es un error con motivo, nunca un
    `FORM_SUBMIT` por defecto: registrar otra cosa que la que ocurrió es peor que no
    registrar nada, porque además puntúa.
    """
    if isinstance(valor, ActivityType):
        return valor
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        raise EventoInvalido("Falta el tipo de actividad.", "activity_type")
    try:
        return ActivityType(str(valor))
    except ValueError:
        admitidos = ", ".join(tipo.value for tipo in ActivityType)
        raise EventoInvalido(
            f"Tipo de actividad desconocido: '{valor}'. Tipos admitidos: {admitidos}.",
            "activity_type",
        ) from None


def minimizar(valor: Any) -> Any:
    """Retira, a cualquier profundidad, las claves que llevan el contenido de un mensaje."""
    if isinstance(valor, dict):
        return {
            clave: minimizar(contenido)
            for clave, contenido in valor.items()
            if str(clave).strip().lower() not in CLAVES_DE_CONTENIDO
        }
    if isinstance(valor, list):
        return [minimizar(contenido) for contenido in valor]
    return valor


def _enum(valor: Any, tipo, campo: str, nombre: str) -> str:
    # `str()` de un miembro de un enum con mezcla de `str` da «Clase.MIEMBRO» desde Python
    # 3.11, no su valor: si ya es un miembro, se toma su valor.
    valor = getattr(valor, "value", valor)
    try:
        return tipo(str(valor)).value
    except ValueError:
        admitidos = ", ".join(opcion.value for opcion in tipo)
        raise EventoInvalido(f"{nombre} desconocido: '{valor}'. Admitidos: {admitidos}.", campo) from None


def _prospecto_normalizado(datos: Dict[str, Any]) -> Dict[str, Any]:
    limpio: Dict[str, Any] = {}
    for campo, ancho in CAMPOS_DEL_PROSPECTO.items():
        valor = datos.get(campo)
        if valor is None:
            continue
        texto = str(valor).strip()
        if not texto:
            continue
        if len(texto) > ancho:
            raise EventoInvalido(f"El campo '{campo}' excede el máximo de {ancho} caracteres.", campo)
        limpio[campo] = texto
    if "email" in limpio:
        limpio["email"] = limpio["email"].lower()
    if "phone" in limpio:
        try:
            limpio["phone"] = normalizar_telefono(limpio["phone"])
        except TelefonoInvalido as exc:
            raise EventoInvalido(str(exc), "phone") from None
    ingresos = datos.get("annual_revenue")
    if ingresos not in (None, ""):
        try:
            limpio["annual_revenue"] = float(ingresos)
        except (TypeError, ValueError):
            raise EventoInvalido("'annual_revenue' tiene que ser un número.", "annual_revenue") from None
        if limpio["annual_revenue"] < 0:
            raise EventoInvalido("'annual_revenue' no puede ser negativo.", "annual_revenue")
    if isinstance(datos.get("raw_metadata"), dict):
        limpio["raw_metadata"] = minimizar(datos["raw_metadata"])
    # El asesor con el que nace la ficha. Lo pone el código de la fuente —hoy solo la página
    # de interés, con el responsable ya comprobado de la publicación—, nunca un dato que
    # llegue de fuera: ningún conector lo copia de lo que recibe. Solo un entero.
    asesor = datos.get("assigned_rep_id")
    if isinstance(asesor, int) and not isinstance(asesor, bool):
        limpio["assigned_rep_id"] = asesor
    return limpio


def validar_evento(evento: Evento, *, ahora: Optional[datetime.datetime] = None) -> EventoValidado:
    """Comprueba el evento sin tocar la base. Lanza `EventoInvalido` con el motivo."""
    ahora = ahora or utc_now()

    fuente = FUENTES.get(evento.fuente)
    if fuente is None:
        raise EventoInvalido(f"Fuente desconocida: '{evento.fuente}'.", "source")

    tipo = tipo_de_actividad(evento.tipo)
    if tipo not in fuente.tipos:
        if fuente.nombre == "manual" and tipo in TIPOS_DEL_PIPELINE:
            raise EventoInvalido(
                "La propuesta enviada y la reunión agendada se registran al cambiar la etapa "
                "del prospecto; no se declaran aparte.",
                "activity_type",
            )
        raise EventoInvalido(
            f"La fuente '{fuente.etiqueta}' no registra actividades de tipo {tipo.value}.",
            "activity_type",
        )

    resultado = None
    if tipo == ActivityType.PHONE_CALL:
        if evento.resultado_de_llamada in (None, ""):
            raise EventoInvalido(
                "Una llamada necesita su resultado: CONECTO, NO_CONTESTO o BUZON. Solo la que "
                "conectó cuenta como conversación.",
                "call_outcome",
            )
        resultado = _enum(evento.resultado_de_llamada, CallOutcome, "call_outcome", "Resultado de llamada")
    elif evento.resultado_de_llamada not in (None, ""):
        raise EventoInvalido("El resultado solo se registra en las llamadas.", "call_outcome")

    direccion = None
    if tipo in TIPOS_DE_MENSAJE_DIRECTO:
        if evento.direccion in (None, ""):
            raise EventoInvalido("Un mensaje necesita su dirección: ENTRANTE o SALIENTE.", "direction")
        direccion = _enum(evento.direccion, MessageDirection, "direction", "Dirección")
        if evento.notas and evento.notas.strip():
            raise EventoInvalido(
                "Los mensajes no llevan notas: del mensaje se guarda el tipo, la dirección, la "
                "fecha y el identificador, nunca su texto.",
                "notes",
            )
    elif evento.direccion not in (None, ""):
        raise EventoInvalido("La dirección solo se registra en los mensajes.", "direction")

    identificador = (evento.identificador_externo or "").strip() or None
    if fuente.externa and identificador is None:
        raise EventoInvalido(
            f"Los eventos de '{fuente.etiqueta}' necesitan el identificador que les dio el sistema de origen.",
            "external_event_id",
        )
    if not fuente.externa and identificador is not None:
        raise EventoInvalido(
            "Lo que registra una persona no lleva identificador externo.", "external_event_id"
        )
    if identificador is not None and len(identificador) > MAX_IDENTIFICADOR_EXTERNO:
        raise EventoInvalido(
            f"El identificador externo excede {MAX_IDENTIFICADOR_EXTERNO} caracteres.", "external_event_id"
        )

    ocurrido_en = _aware(evento.ocurrido_en)
    if ocurrido_en is None:
        if fuente.externa:
            raise EventoInvalido(
                f"Los eventos de '{fuente.etiqueta}' necesitan la fecha en que ocurrieron.", "occurred_at"
            )
        ocurrido_en = ahora
    if ocurrido_en > ahora + TOLERANCIA_AL_FUTURO:
        raise EventoInvalido("La fecha del evento está en el futuro.", "occurred_at")

    canal = (evento.canal or "").strip() or CANAL_POR_TIPO.get(tipo, CANAL_POR_DEFECTO)
    if len(canal) > MAX_CANAL:
        raise EventoInvalido(f"El canal excede {MAX_CANAL} caracteres.", "channel")

    notas = (evento.notas or "").strip() or None
    if notas is not None:
        if fuente.externa:
            raise EventoInvalido("Las notas son del asesor; una integración no las envía.", "notes")
        if len(notas) > MAX_NOTAS:
            raise EventoInvalido(f"Las notas exceden {MAX_NOTAS} caracteres.", "notes")

    campana_id = evento.campana_id
    if campana_id is not None:
        if not isinstance(campana_id, int) or isinstance(campana_id, bool) or campana_id <= 0:
            raise EventoInvalido("La campaña tiene que ser un identificador válido.", "campaign_id")

    datos = minimizar(dict(evento.datos or {}))
    if notas is not None:
        datos["notes"] = notas

    telefono = None
    try:
        telefono = normalizar_telefono(evento.contacto.telefono)
    except TelefonoInvalido as exc:
        raise EventoInvalido(str(exc), "phone") from None
    email = (evento.contacto.email or "").strip().lower() or None
    nombre = (evento.contacto.nombre or "").strip()[:150] or None

    return EventoValidado(
        fuente=fuente,
        tipo=tipo,
        ocurrido_en=ocurrido_en,
        identificador_externo=identificador,
        direccion=direccion,
        resultado_de_llamada=resultado,
        canal=canal,
        datos=datos,
        contacto=Contacto(email=email, telefono=telefono, nombre=nombre),
        prospecto=_prospecto_normalizado(evento.prospecto or {}),
        campana_id=campana_id,
        aviso_de_privacidad_aceptado_en=_aware(evento.aviso_de_privacidad_aceptado_en),
    )


# ==============================================================================
# Registro
# ==============================================================================

def _ya_registrado(db: Session, v: EventoValidado) -> Optional[ResultadoDelRegistro]:
    if v.identificador_externo is None:
        return None
    actividad = (
        db.query(LeadActivity)
        .filter(
            LeadActivity.source == v.fuente.nombre,
            LeadActivity.external_event_id == v.identificador_externo,
        )
        .first()
    )
    if actividad is not None:
        lead = actividad.lead
        return ResultadoDelRegistro(
            estado=ESTADO_DUPLICADA,
            lead=lead,
            actividad=actividad,
            score_anterior=lead.current_score,
            score=lead.current_score,
            categoria=getattr(lead.score_category, "value", lead.score_category),
        )
    pendiente = (
        db.query(UnmatchedEvent)
        .filter(
            UnmatchedEvent.source == v.fuente.nombre,
            UnmatchedEvent.external_event_id == v.identificador_externo,
        )
        .first()
    )
    if pendiente is not None:
        return ResultadoDelRegistro(estado=ESTADO_DUPLICADA, sin_asociar=pendiente)
    return None


def _buscar_prospecto(db: Session, v: EventoValidado) -> Optional[Lead]:
    email = v.contacto.email or v.prospecto.get("email")
    if email:
        lead = db.query(Lead).filter(Lead.email == email).first()
        if lead is not None:
            return lead
    telefono = v.contacto.telefono or v.prospecto.get("phone")
    if telefono:
        return db.query(Lead).filter(Lead.phone == telefono).order_by(Lead.id).first()
    return None


def _crear_prospecto(db: Session, v: EventoValidado) -> Lead:
    """
    La ficha con lo que llegó y nada más. Lo que no llega queda vacío y puntúa neutro:
    una industria vacía no suma los 15 puntos de «Tecnología» ni resta nada.
    """
    datos = v.prospecto
    email = v.contacto.email or datos.get("email")
    if not email:
        raise EventoInvalido("Para crear la ficha hace falta el correo de la persona.", "email")
    ahora = utc_now()
    lead = Lead(
        first_name=datos.get("first_name", ""),
        last_name=datos.get("last_name", ""),
        email=email,
        phone=datos.get("phone") or v.contacto.telefono,
        company=datos.get("company"),
        job_title=datos.get("job_title"),
        industry=datos.get("industry"),
        company_size=datos.get("company_size"),
        # Sin cifra declarada queda vacío, no a cero: un cero se lee como dato (capítulo 24).
        annual_revenue=datos.get("annual_revenue"),
        # Sin país declarado queda vacío, no «México» (capítulo 32). Es el mismo criterio
        # que la línea de arriba: lo que no llega no se rellena.
        country=datos.get("country"),
        city=datos.get("city"),
        source=datos.get("source", v.fuente.etiqueta),
        campaign_id=v.campana_id,
        # Solo lo trae la página de interés, con el responsable de la publicación. El resto
        # de fuentes no lo mandan y la ficha nace sin asesor, como siempre.
        assigned_rep_id=datos.get("assigned_rep_id"),
        status=LeadStatus.NEW,
        raw_metadata=datos.get("raw_metadata", {}),
        created_at=ahora,
        updated_at=ahora,
    )
    db.add(lead)
    db.flush()
    return lead


def _actualizar_prospecto(lead: Lead, v: EventoValidado) -> None:
    for campo in CAMPOS_ACTUALIZABLES:
        if campo in v.prospecto:
            setattr(lead, campo, v.prospecto[campo])
    if v.prospecto:
        lead.updated_at = utc_now()


def _anotar_aviso_de_privacidad(lead: Lead, v: EventoValidado) -> None:
    if v.aviso_de_privacidad_aceptado_en is not None and lead.privacy_notice_accepted_at is None:
        lead.privacy_notice_accepted_at = v.aviso_de_privacidad_aceptado_en
        lead.privacy_notice_source = v.fuente.nombre


def _a_la_bandeja(db: Session, v: EventoValidado, commit: bool) -> ResultadoDelRegistro:
    if not (v.contacto.email or v.contacto.telefono):
        raise EventoInvalido(
            "El evento no identifica a nadie: hace falta un correo o un teléfono para poder "
            "vincularlo después.",
            "contacto",
        )
    pendiente = UnmatchedEvent(
        source=v.fuente.nombre,
        external_event_id=v.identificador_externo,
        activity_type=v.tipo,
        channel=v.canal,
        direction=v.direccion,
        call_outcome=v.resultado_de_llamada,
        contact_email=v.contacto.email,
        contact_phone=v.contacto.telefono,
        contact_name=v.contacto.nombre,
        occurred_at=v.ocurrido_en,
        received_at=utc_now(),
    )
    db.add(pendiente)
    db.flush()
    if commit:
        db.commit()
    logger.info(
        "Evento %s de '%s' sin prospecto: queda en la bandeja «Sin asociar» (id %s).",
        v.tipo.value, v.fuente.nombre, pendiente.id,
    )
    return ResultadoDelRegistro(estado=ESTADO_SIN_ASOCIAR, sin_asociar=pendiente)


async def registrar_evento(
    db: Session,
    evento: Evento,
    *,
    lead: Optional[Lead] = None,
    scoring=None,
    commit: bool = True,
    generar_explicacion: bool = True,
) -> ResultadoDelRegistro:
    """
    Valida, deduplica, asocia, registra y puntúa.

    Con `lead` el evento va a esa ficha sin buscarla (el panel, el cambio de etapa, la
    vinculación desde la bandeja). Con `commit=False` todo queda en la transacción del
    llamador: el webhook del CRM confirma la actividad junto con su registro de integración.
    """
    v = validar_evento(evento)

    repetido = _ya_registrado(db, v)
    if repetido is not None:
        return repetido

    creado = False
    if lead is None:
        lead = _buscar_prospecto(db, v)
        if lead is None:
            if not v.fuente.crea_prospecto:
                return _a_la_bandeja(db, v, commit)
            lead = _crear_prospecto(db, v)
            creado = True
        elif v.fuente.crea_prospecto and v.fuente.actualiza_prospecto:
            _actualizar_prospecto(lead, v)

    _anotar_aviso_de_privacidad(lead, v)
    score_anterior = None if creado else lead.current_score

    actividad = LeadActivity(
        lead=lead,
        activity_type=v.tipo,
        channel=v.canal,
        source=v.fuente.nombre,
        external_event_id=v.identificador_externo,
        verificada=v.fuente.verificada,
        direction=v.direccion,
        call_outcome=v.resultado_de_llamada,
        activity_data=v.datos,
        occurred_at=v.ocurrido_en,
        created_at=utc_now(),
    )
    db.add(actividad)
    # Un evento que llega tarde no hace más reciente al prospecto de lo que ya era.
    ultima = _aware(lead.last_activity_at)
    if ultima is None or v.ocurrido_en > ultima:
        lead.last_activity_at = v.ocurrido_en
    try:
        db.flush()
    except IntegrityError:
        # Dos entregas del mismo evento a la vez: el índice único deja pasar una.
        db.rollback()
        repetido = _ya_registrado(db, v)
        if repetido is not None:
            return repetido
        raise

    # Capítulo 28. Lo que esta actividad deja de tener sentido se cierra AQUÍ y no en la
    # pasada de mañana: el asesor no puede ver en su bandeja una llamada que acaba de hacer.
    # Va sin confirmar, dentro de la transacción de la actividad: si la actividad se
    # descarta, la tarea que cerró vuelve a estar abierta.
    from app.services.motor_de_reglas import cerrar_lo_cumplido

    cerrar_lo_cumplido(db, lead, actividad, commit=False)

    if scoring is None:
        from app.services.scoring_service import ScoringService

        scoring = ScoringService(db)
    resultado = await scoring.calculate_and_persist_score(
        lead, generate_ai_text=generar_explicacion, commit=commit
    )
    return ResultadoDelRegistro(
        estado=ESTADO_REGISTRADA,
        lead=lead,
        actividad=actividad,
        prospecto_creado=creado,
        score_anterior=score_anterior,
        score=resultado.score,
        categoria=resultado.score_category.value,
        score_result=resultado,
    )


async def registrar_cambio_de_etapa(
    db: Session,
    lead: Lead,
    etapa_anterior: Optional[LeadStatus],
    *,
    scoring=None,
) -> Optional[ResultadoDelRegistro]:
    """
    Si el prospecto acaba de entrar en «Propuesta enviada» o «Reunión agendada», registra
    la actividad correspondiente. Devuelve `None` si la etapa no registra nada o no cambió.
    """
    etapa = lead.status if isinstance(lead.status, LeadStatus) else LeadStatus(lead.status)
    tipo = ETAPA_A_ACTIVIDAD.get(etapa)
    if tipo is None or etapa == etapa_anterior:
        return None
    return await registrar_evento(
        db, Evento(fuente="pipeline", tipo=tipo), lead=lead, scoring=scoring
    )


async def vincular_evento_sin_asociar(
    db: Session, pendiente: UnmatchedEvent, lead: Lead, *, scoring=None
) -> ResultadoDelRegistro:
    """
    Convierte un aviso de la bandeja en actividad del prospecto elegido.

    La fila de la bandeja se retira antes de registrar —si no, el propio aviso contaría
    como duplicado de sí mismo— y todo va en la misma transacción: si el registro falla,
    el aviso vuelve a la bandeja.
    """
    evento = Evento(
        fuente=pendiente.source,
        tipo=pendiente.activity_type,
        ocurrido_en=pendiente.occurred_at,
        identificador_externo=pendiente.external_event_id,
        direccion=pendiente.direction,
        resultado_de_llamada=pendiente.call_outcome,
        canal=pendiente.channel,
    )
    try:
        db.delete(pendiente)
        db.flush()
        return await registrar_evento(db, evento, lead=lead, scoring=scoring)
    except Exception:
        db.rollback()
        raise


def nombres_de_fuentes(nombres: Iterable[str]) -> Dict[str, str]:
    """Etiqueta legible de cada fuente, para las respuestas de la API."""
    return {nombre: FUENTES[nombre].etiqueta for nombre in nombres if nombre in FUENTES}
