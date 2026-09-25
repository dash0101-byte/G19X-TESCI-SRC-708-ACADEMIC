import datetime
import enum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import expression

from app.core.agenda import ABIERTA
from app.core.database import Base
from app.core.publicaciones import ACTIVA, nuevo_slug_publico
from app.core.redes import SIN_RED


class ScoreCategory(str, enum.Enum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"


class LeadStatus(str, enum.Enum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    ENGAGED = "ENGAGED"
    QUALIFIED = "QUALIFIED"
    MEETING_SCHEDULED = "MEETING_SCHEDULED"
    PROPOSAL_SENT = "PROPOSAL_SENT"
    NEGOTIATION = "NEGOTIATION"
    UNQUALIFIED = "UNQUALIFIED"
    WON = "WON"
    LOST = "LOST"


class QualificationStatus(str, enum.Enum):
    INCOMING = "INCOMING"
    MQL = "MQL"  # Marketing Qualified Lead
    SAL = "SAL"  # Sales Accepted Lead
    SQL = "SQL"  # Sales Qualified Lead
    DISQUALIFIED = "DISQUALIFIED"


class ActivityType(str, enum.Enum):
    PAGE_VIEW = "PAGE_VIEW"
    FORM_SUBMIT = "FORM_SUBMIT"
    EMAIL_OPEN = "EMAIL_OPEN"
    EMAIL_CLICK = "EMAIL_CLICK"
    DEMO_REQUEST = "DEMO_REQUEST"
    WEBINAR_ATTEND = "WEBINAR_ATTEND"
    CONTENT_DOWNLOAD = "CONTENT_DOWNLOAD"
    CHAT_INTERACTION = "CHAT_INTERACTION"
    PHONE_CALL = "PHONE_CALL"
    MEETING_SCHEDULED = "MEETING_SCHEDULED"
    WHATSAPP_MESSAGE = "WHATSAPP_MESSAGE"
    # Separado de WhatsApp desde la Fase 15. Antes el panel ofrecía «Mensaje de WhatsApp /
    # LinkedIn» como un único tipo, y lo que se registraba era WHATSAPP_MESSAGE: el
    # historial afirmaba un canal que no siempre era el de verdad.
    LINKEDIN_MESSAGE = "LINKEDIN_MESSAGE"
    PROPOSAL_SENT = "PROPOSAL_SENT"
    CUSTOM = "CUSTOM"


class CallOutcome(str, enum.Enum):
    """
    Cómo terminó una llamada. Solo `CONECTO` es una conversación.

    Sin este dato, diez intentos que acabaron en el buzón puntuaban como diez
    conversaciones: el tope de la regla —16 puntos a partir de la segunda— se alcanzaba
    marcando dos veces a alguien que no contesta.
    """
    CONECTO = "CONECTO"
    NO_CONTESTO = "NO_CONTESTO"
    BUZON = "BUZON"


class MessageDirection(str, enum.Enum):
    """Quién escribió a quién. Del mensaje se guarda esto, nunca su texto."""
    ENTRANTE = "ENTRANTE"
    SALIENTE = "SALIENTE"


def utc_now() -> datetime.datetime:
    """
    Instante actual en UTC, con zona horaria explícita.

    Todas las columnas temporales se declaran `DateTime(timezone=True)`. La función ya
    devolvía un valor *aware*, pero las columnas lo descartaban al persistir: lo que
    entraba como «14:03 UTC» se leía después como «14:03 sin zona», y el consumidor tenía
    que adivinar. El cálculo de inactividad —del que depende el decaimiento temporal del
    score— restaba entonces un instante con zona de otro sin ella, y en Python eso es un
    `TypeError` o, peor, una diferencia desplazada por el huso del servidor.

    En PostgreSQL esto se traduce a `TIMESTAMP WITH TIME ZONE`. SQLite no tiene tipo con
    zona, así que allí sigue guardándose el texto plano; por eso el código que compara
    fechas mantiene la normalización defensiva a UTC.
    """
    return datetime.datetime.now(datetime.timezone.utc)


class User(Base):
    """
    Identidad autenticable del sistema. Sustituye por completo la confianza en cabeceras:
    la única fuente de verdad sobre quién es el usuario y qué rol tiene es esta tabla,
    alcanzada a través de la firma de un JWT emitido por `POST /api/v1/auth/login`.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(150), unique=True, nullable=False, index=True)
    # Hash bcrypt; la contraseña en claro nunca se persiste ni se registra en logs.
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(150), nullable=False)
    role = Column(String(50), default="Commercial_Executive", nullable=False)
    # Baja lógica. Una cuenta desactivada no autentica y deja de recibir prospectos, pero
    # su rastro en `audit_log` y los prospectos que atendió siguen apuntando a ella:
    # borrarla de verdad convertiría su historial en huérfano justo cuando más interesa
    # poder reconstruirlo.
    is_active = Column(Boolean, default=True, nullable=False)
    # Se incrementa al cerrar sesión o rotar credenciales: invalida de golpe todos los
    # refresh tokens ya emitidos para este usuario sin necesidad de una lista negra.
    token_version = Column(Integer, default=0, nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # --- Atributos de asesor comercial (antes, la tabla `sales_reps`) ---
    # Marca si esta persona atiende cartera. No es un rol: `Sales_Lead` describe qué
    # puede hacer en el sistema, esto describe si además se le asignan prospectos. Un
    # administrador de TI tiene permisos sobre todo y no atiende a nadie.
    is_sales_rep = Column(Boolean, default=False, nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    # Cartera máxima. NULL cuando la persona no es asesora: un número ahí significaría
    # una capacidad que nadie va a usar.
    capacity = Column(Integer, nullable=True)

    # --- Ciclo de vida de la contraseña ---
    password_changed_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    # Lo pone a True un restablecimiento hecho por un administrador. Mientras esté
    # activo, la sesión solo sirve para cambiar la contraseña: una credencial que conoce
    # otra persona no es una credencial.
    must_change_password = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Prospectos que atiende. Antes esta relación colgaba de `sales_reps`, una tabla de
    # personas distinta y sin conexión con las cuentas que inician sesión.
    assigned_leads = relationship("Lead", back_populates="assigned_rep")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"


class Campaign(Base):
    """
    Campañas de marketing digital y canales de captación para atribución comercial.

    Una publicación de LinkedIn es una campaña con canal `LinkedIn`, no una tabla aparte
    (`app/core/publicaciones.py`).
    """
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    channel = Column(String(100), nullable=False)  # LinkedIn, Google Ads, Organic, Email Marketing
    # Texto de la publicación y a quién va dirigida. Vacíos en las campañas que no son posts.
    description = Column(Text, nullable=True)
    target_audience = Column(String(300), nullable=True)
    # Identificador del enlace público. Aleatorio, fijo desde el alta y único para siempre.
    public_slug = Column(String(32), nullable=False, default=nuevo_slug_publico)
    budget = Column(Float, default=0.0, nullable=False)
    utm_source = Column(String(100), nullable=True)
    utm_medium = Column(String(100), nullable=True)
    utm_campaign = Column(String(100), nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # --- Capítulo 26: publicaciones completas -------------------------------------------
    # borrador, activa, pausada o cerrada (`app/core/publicaciones.py`). `is_active` se
    # mantiene igual a «está activa» para lo que lo leía antes de que hubiera estados.
    estado = Column(String(20), nullable=False, default=ACTIVA, server_default=ACTIVA)
    # Opciones de «¿Qué necesitas?»: `[{"clave", "etiqueta"}]`, de 2 a 5. Vacío: las de siempre.
    necesidades = Column(JSON, nullable=True)
    # Quien recibe los prospectos que llegan por esta publicación. Vacío: llegan sin asesor.
    responsable_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # La dirección del post ya publicado en LinkedIn, comprobada como de linkedin.com.
    url_del_post = Column(String(300), nullable=True)

    # --- Capítulo 27: una publicación, varias redes ------------------------------------
    # Redes de difusión activas: `["linkedin", "whatsapp", ...]` (`app/core/redes.py`).
    # Vacío: las de siempre. Decide qué botones y qué textos ofrece el panel, no qué
    # enlaces valen: un enlace ya repartido sigue contando aunque su red se desactive.
    redes = Column(JSON, nullable=True)

    # --- Capítulo 34: bajo qué dirección se repartió el enlace de esta publicación ------
    # Se escribe al **activarla**, que es el instante en que su enlace se vuelve repartible,
    # y no se vuelve a tocar. Guarda el valor de `PUBLICACIONES_URL_BASE` de ese momento.
    #
    # Existe porque un túnel de prueba gratuito da una dirección distinta en cada arranque.
    # Comparar esto con la dirección de ahora es lo que permite decir «el enlace que está
    # en ese post ya no lleva aquí» en lugar de dejar que el post falle en silencio durante
    # semanas. `NULL` en las publicaciones anteriores a este capítulo: de ellas no consta
    # bajo qué dirección salieron, y suponerlo sería inventar el dato que se quiere medir.
    url_base_publicada = Column(String(300), nullable=True)

    # Relaciones
    leads = relationship("Lead", back_populates="campaign")
    responsable = relationship("User", foreign_keys=[responsable_id])

    __table_args__ = (
        # Un enlace ya publicado no puede acabar apuntando a otra campaña.
        Index("uq_campaigns_public_slug", "public_slug", unique=True),
    )

    def __repr__(self) -> str:
        return f"<Campaign(id={self.id}, name='{self.name}', channel='{self.channel}')>"


class VisitaDePublicacion(Base):
    """
    Cuántas veces se abrió la página de una publicación, por día. Nada más.

    Es un contador agregado a propósito: ni IP, ni navegador, ni cookie, ni hora. Una fila
    por publicación, día y red con un número. Así la tasa de visitas a envíos se puede
    calcular sin guardar nada de quien solo miró y no dejó sus datos —que no ha aceptado
    ningún aviso de privacidad—, y no hay nada que suprimir ni que proteger.

    Desde el capítulo 27 la red de llegada forma parte de la clave. Sigue sin ser un dato de
    nadie: es por dónde se repartió el enlace, no quién lo abrió. Las visitas anteriores, y
    las que llegan con el parámetro borrado o manipulado, se quedan en «sin red».
    """
    __tablename__ = "visitas_de_publicacion"

    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), primary_key=True)
    dia = Column(Date, primary_key=True)
    red = Column(String(20), primary_key=True, nullable=False, default=SIN_RED, server_default=SIN_RED)
    visitas = Column(Integer, nullable=False, default=0)


class Lead(Base):
    """
    Entidad principal de Prospecto Comercial (Lead) en el Sistema Inteligente de Scoring.
    """
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)

    # Datos de Contacto y Demográficos
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    phone = Column(String(50), nullable=True)

    # Datos Firmográficos (B2B / Corporativo)
    company = Column(String(150), nullable=True, index=True)
    job_title = Column(String(100), nullable=True)
    industry = Column(String(100), nullable=True, index=True)
    company_size = Column(String(50), nullable=True)  # '1-10', '11-50', '51-200', '201-1000', '1000+'
    annual_revenue = Column(Float, nullable=True)
    # Sin valor por defecto y admitiendo vacío desde el capítulo 32. Escribía «México» a
    # cualquier ficha que llegara sin país —la de la página de interés, que no lo pregunta;
    # la de una integración que no lo manda—, y eso no es un dato: es una suposición con
    # aspecto de dato, indistinguible después de la de quien sí lo eligió. No puntúa ni en
    # la regla ni en el modelo, así que lo único que hacía era volver falsa la ficha.
    country = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    source = Column(String(100), default="Website", nullable=False)  # Form, Chat, Referral, LinkedIn

    # Estado de Negocio y Clasificación
    status = Column(SQLEnum(LeadStatus), default=LeadStatus.NEW, nullable=False, index=True)
    qualification_status = Column(SQLEnum(QualificationStatus), default=QualificationStatus.INCOMING, nullable=False, index=True)

    # Puntuación Inteligente y Clasificación Dinámica
    current_score = Column(Float, default=0.0, nullable=False, index=True)
    score_category = Column(SQLEnum(ScoreCategory), default=ScoreCategory.COLD, nullable=False, index=True)
    conversion_probability = Column(Float, default=0.0, nullable=False)  # Probabilidad estimada (0.0 a 1.0)
    last_score_update = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_activity_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Desde cuándo nadie lo toca (capítulo 28). Lo pone la regla «prospecto dormido» de la
    # pasada diaria y lo quita la primera actividad que llegue. Es una marca y no un cálculo
    # sobre `last_activity_at` a propósito: el motor necesita saber si YA avisó, y una
    # consulta por fecha volvería a avisar cada día mientras el prospecto siguiera quieto.
    dormido_desde = Column(DateTime(timezone=True), nullable=True, index=True)

    # Llaves Foráneas
    # Apunta a `users`, no a una tabla de asesores aparte. Es lo que permite comparar
    # "de quién es este prospecto" con "quién está pidiendo verlo" (N-3): mientras fueron
    # dos tablas sin relación, esa comparación no se podía escribir.
    assigned_rep_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True)

    # Metadatos flexibles en JSON
    raw_metadata = Column(JSON, nullable=True, default=dict)

    # Aviso de privacidad (LFPDPPP): cuándo lo aceptó la persona y por qué vía llegó esa
    # aceptación —el formulario web, LinkedIn Lead Gen, el CRM—. Se guarda la PRIMERA
    # aceptación registrada: una entrega posterior del mismo CRM no la mueve, porque lo que
    # hay que poder demostrar es desde cuándo había consentimiento, no cuándo se repitió.
    privacy_notice_accepted_at = Column(DateTime(timezone=True), nullable=True)
    privacy_notice_source = Column(String(40), nullable=True)

    # Marcas temporales
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relaciones
    assigned_rep = relationship("User", back_populates="assigned_leads")
    campaign = relationship("Campaign", back_populates="leads")
    activities = relationship("LeadActivity", back_populates="lead", cascade="all, delete-orphan")
    score_histories = relationship("ScoreHistory", back_populates="lead", cascade="all, delete-orphan", order_by="desc(ScoreHistory.calculated_at)")
    score_monthly = relationship("ScoreHistoryMonthly", back_populates="lead", cascade="all, delete-orphan", order_by="ScoreHistoryMonthly.month")
    crm_logs = relationship("CRMIntegrationLog", back_populates="lead", cascade="all, delete-orphan")
    # Cómo acabó, si acabó (capítulo 30). `uselist=False`: un prospecto se cierra una vez.
    desenlace = relationship("Desenlace", back_populates="lead", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Lead(id={self.id}, email='{self.email}', score={self.current_score}, category='{self.score_category}')>"


class LeadActivity(Base):
    """
    Una interacción del prospecto, con su procedencia.

    Hasta la Fase 15 una actividad era un tipo, un canal, un «peso» y una marca de tiempo.
    No decía de dónde venía: una reunión agendada que confirmó Calendly y una que el asesor
    declaró a mano eran la misma fila, y un mismo aviso del CRM entregado dos veces fuera de
    la ventana de idempotencia eran dos filas. El peso tampoco significaba nada: lo mandaba
    el cliente y el scoring nunca lo leyó.

    Ahora cada fila dice su fuente, si la vio un sistema (`verificada`) o la declaró una
    persona, y el identificador que le dio el sistema de origen. Las filas se escriben en un
    solo sitio, `app.services.registro_de_actividad.registrar_evento`.
    """
    __tablename__ = "lead_activities"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)

    activity_type = Column(SQLEnum(ActivityType), nullable=False, index=True)
    channel = Column(String(50), default="Web", nullable=False)

    # --- Procedencia ---
    # `manual`, `pipeline`, `crm`, `formulario_web`, `linkedin_lead_gen`, `calendly`,
    # `whatsapp`. Texto y no un tipo enumerado de la base: añadir una integración no debe
    # exigir una migración con `ALTER TYPE`. La lista válida vive en `registro_de_actividad`.
    source = Column(String(40), nullable=False, server_default="manual")
    # Lo que el sistema de origen llama a este evento. Nulo en lo que registra una persona.
    external_event_id = Column(String(200), nullable=True)
    # Un sistema lo vio ocurrir (verdadero) o una persona lo declaró (falso).
    verificada = Column(Boolean, nullable=False, server_default=expression.false())

    # Del mensaje, quién escribió a quién; de la llamada, cómo terminó. Nunca el texto.
    direction = Column(String(10), nullable=True)
    call_outcome = Column(String(20), nullable=True)

    activity_data = Column(JSON, nullable=True, default=dict)  # url, formulario, notas del asesor
    # Cuándo ocurrió, que no es cuándo se registró: una reunión de ayer anotada hoy, o un
    # aviso que el CRM reintentó durante una hora. Antes era `timestamp` y valía para las dos
    # cosas; el decaimiento temporal del score se medía desde la hora de registro.
    occurred_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relaciones
    lead = relationship("Lead", back_populates="activities")

    __table_args__ = (
        # Permanente, a diferencia de la ventana de idempotencia del webhook (15 minutos): un
        # mismo evento de origen entra una vez aunque se reentregue un mes después. Los NULL
        # de lo registrado a mano no chocan entre sí, ni en PostgreSQL ni en SQLite.
        Index("uq_lead_activities_source_external_event", "source", "external_event_id", unique=True),
    )

    def __repr__(self) -> str:
        return (
            f"<LeadActivity(id={self.id}, lead_id={self.lead_id}, type='{self.activity_type}', "
            f"source='{self.source}', occurred_at={self.occurred_at})>"
        )


class Tarea(Base):
    """
    Lo que hay que hacer con un prospecto, y para cuándo.

    Por qué una tabla y no una actividad más
    ----------------------------------------
    `lead_activities` guarda lo que YA pasó: una llamada, un formulario, una reunión
    agendada. Una tarea es lo contrario, algo que todavía no ha pasado y que alguien tiene
    que hacer. Meterla en la misma tabla habría obligado a que el scoring, el decaimiento
    temporal y la ficha 360 —que leen esa tabla entera— aprendieran a ignorar filas que no
    son hechos. Una tarea pendiente no puede puntuar: nadie se vuelve más interesante
    porque a su asesor le quede trabajo por hacer.

    Idempotencia
    ------------
    `(regla, lead_id, clave)` es único. La pasada diaria puede repetirse cuantas veces
    haga falta —la misma mañana, dos veces tras un reintento— sin duplicar nada: la
    segunda inserción choca con el índice y se descarta. La `clave` es lo que distingue
    dos tareas de la misma regla sobre el mismo prospecto: para «volver a llamar» es la
    llamada que no contestaron, y para «primer contacto», el asesor al que se le asignó.
    Reasignar a otra persona crea su propia tarea; volver a pasar el motor, no.

    El índice cubre también las **cerradas**, y eso es deliberado: una tarea que ya se hizo
    no debe volver a aparecer mañana por el mismo motivo.
    """
    __tablename__ = "tareas"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    # De quién es el trabajo. Si la cuenta desaparece, su lista de tareas se va con ella:
    # una tarea sin dueño no la ve nadie y no la puede hacer nadie.
    asesor_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # La regla que la creó (`app/core/agenda.py`). Texto y no un tipo enumerado de la base:
    # añadir una regla no debe exigir un `ALTER TYPE`, igual que con la procedencia de las
    # actividades.
    regla = Column(String(40), nullable=False, index=True)
    clave = Column(String(80), nullable=False)

    estado = Column(String(20), nullable=False, default=ABIERTA, server_default=ABIERTA, index=True)
    # Para cuándo. La bandeja «Hoy» enseña lo vencido y lo de hoy; lo de pasado mañana
    # espera su turno.
    vence_el = Column(DateTime(timezone=True), nullable=False, index=True)

    # Por qué existe esta tarea, en una frase y sin datos de nadie: el nombre y la empresa
    # salen del prospecto al pintarla. Lo que se guarda aquí viaja a la bitácora y a los
    # respaldos, y no tiene por qué llevar a una persona dentro.
    motivo = Column(String(200), nullable=False)
    datos = Column(JSON, nullable=True, default=dict)

    creada_en = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    cerrada_en = Column(DateTime(timezone=True), nullable=True)
    # Quién la cerró. Nulo cuando la cerró el sistema porque ocurrió lo que esperaba.
    cerrada_por_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    lead = relationship("Lead")
    asesor = relationship("User", foreign_keys=[asesor_id])

    __table_args__ = (
        Index("uq_tareas_regla_lead_clave", "regla", "lead_id", "clave", unique=True),
        # La consulta de la bandeja: las mías, abiertas, por fecha de vencimiento.
        Index("idx_tareas_asesor_estado_vence", "asesor_id", "estado", "vence_el"),
    )

    def __repr__(self) -> str:
        return (
            f"<Tarea(id={self.id}, lead_id={self.lead_id}, regla='{self.regla}', "
            f"estado='{self.estado}', vence_el={self.vence_el})>"
        )


class Aviso(Base):
    """
    Algo que alguien tiene que enterarse de que pasó. Dentro del panel y en ningún otro sitio.

    Por qué no es una tarea
    -----------------------
    Una tarea se hace; un aviso se lee. «Volver a llamar» pide trabajo y se cierra cuando el
    trabajo ocurre. «Este HOT lleva 24 horas sin que nadie lo toque» no pide un trabajo
    concreto —puede resolverse llamando, delegando o decidiendo que no vale la pena—: pide
    que alguien se entere. Juntarlos habría obligado a inventar un estado «leída pero no
    hecha» y a decidir si un aviso sin leer cuenta como trabajo pendiente en la bandeja.

    Por qué no sale del panel
    -------------------------
    Ni correo ni WhatsApp. Un aviso que sale del sistema necesita una cuenta externa, una
    dirección de envío verificada y una política de qué hacer cuando rebota; y, sobre todo,
    saca de la aplicación el nombre de una persona que aceptó un aviso de privacidad para
    otra cosa. Queda explícitamente fuera del capítulo 28.
    """
    __tablename__ = "avisos"

    id = Column(Integer, primary_key=True, index=True)
    # Para quién es. Si la cuenta desaparece, sus avisos también.
    usuario_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)

    regla = Column(String(40), nullable=False, index=True)
    clave = Column(String(80), nullable=False)

    texto = Column(String(300), nullable=False)
    datos = Column(JSON, nullable=True, default=dict)

    creado_en = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    # Nulo mientras no se haya leído: es lo que cuenta la campana.
    leido_en = Column(DateTime(timezone=True), nullable=True)

    lead = relationship("Lead")
    usuario = relationship("User", foreign_keys=[usuario_id])

    __table_args__ = (
        # Mismo criterio que en las tareas: la pasada puede repetirse sin llenar la campana
        # del mismo aviso. Incluye al destinatario porque el mismo hecho sí puede avisar a
        # dos personas distintas —al asesor primero y al líder después—, y esos son dos
        # avisos, no uno repetido.
        Index("uq_avisos_usuario_regla_lead_clave", "usuario_id", "regla", "lead_id", "clave", unique=True),
        # La consulta de la campana: los míos, sin leer, los más nuevos primero.
        Index("idx_avisos_usuario_leido_creado", "usuario_id", "leido_en", "creado_en"),
    )

    def __repr__(self) -> str:
        return (
            f"<Aviso(id={self.id}, usuario_id={self.usuario_id}, lead_id={self.lead_id}, "
            f"regla='{self.regla}', leido={self.leido_en is not None})>"
        )


class UnmatchedEvent(Base):
    """
    Bandeja «Sin asociar»: avisos que llegaron sin un prospecto al que pertenecer.

    Un mensaje de WhatsApp de un número que no está en ninguna ficha, o una reunión agendada
    en Calendly con un correo desconocido. Antes, cualquier correo desconocido creaba una
    ficha, con industria «Tecnología» y tamaño «1-10» inventados para que puntuara. Ahora
    solo crean ficha las fuentes que generan prospectos —formularios, Lead Gen, CRM—; el
    resto espera aquí a que alguien lo vincule a mano o lo descarte.

    Guarda lo mínimo para reconocer a quién pertenece: correo, teléfono y nombre si llegaron.
    Sin clave foránea a `leads`: al vincularse, el aviso se convierte en actividad y la fila
    se borra. La supresión de un prospecto busca aquí por correo y teléfono.
    """
    __tablename__ = "unmatched_events"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(40), nullable=False)
    external_event_id = Column(String(200), nullable=False)
    activity_type = Column(SQLEnum(ActivityType), nullable=False)
    channel = Column(String(50), nullable=False)
    direction = Column(String(10), nullable=True)
    call_outcome = Column(String(20), nullable=True)

    contact_email = Column(String(150), nullable=True, index=True)
    contact_phone = Column(String(50), nullable=True, index=True)
    contact_name = Column(String(150), nullable=True)

    occurred_at = Column(DateTime(timezone=True), nullable=False)
    received_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    __table_args__ = (
        Index("uq_unmatched_events_source_external_event", "source", "external_event_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<UnmatchedEvent(id={self.id}, source='{self.source}', type='{self.activity_type}')>"


class ScoreHistory(Base):
    """
    Auditoría y trazabilidad histórica del scoring de cada prospecto.
    """
    __tablename__ = "score_histories"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)

    score = Column(Float, nullable=False)
    score_category = Column(SQLEnum(ScoreCategory), nullable=False)
    model_version = Column(String(50), default="v1.0.0-hybrid", nullable=False)

    # Desglose de componentes del algoritmo híbrido
    ml_probability = Column(Float, default=0.0, nullable=False)
    heuristic_score = Column(Float, default=0.0, nullable=False)
    decay_factor = Column(Float, default=1.0, nullable=False)
    rule_breakdown = Column(JSON, nullable=True, default=dict)
    ai_explanation = Column(JSON, nullable=True, default=dict)  # Explicación en lenguaje natural (Azure OpenAI / Mock)

    # Vector de variables tal como estaba EN EL MOMENTO de puntuar. Es lo que convierte
    # esta tabla en algo reentrenable: sin la instantánea, un dataset construido a partir
    # del estado actual del prospecto tendría fuga de información, porque un prospecto
    # ganado lleva por definición propuesta enviada y reunión agendada. El modelo
    # aprendería que enviar propuestas causa cierres, que es la conclusión al revés.
    feature_snapshot = Column(JSON, nullable=True, default=dict)

    calculated_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    # Relaciones
    lead = relationship("Lead", back_populates="score_histories")

    def __repr__(self) -> str:
        return f"<ScoreHistory(id={self.id}, lead_id={self.lead_id}, score={self.score}, date={self.calculated_at})>"


class ScoreHistoryMonthly(Base):
    """
    Lo que queda del detalle de puntuación una vez vencida su retención: una fila por
    prospecto y mes.

    `score_histories` crece con cada recálculo —uno por actividad, más los masivos— y
    guarda en cada fila el vector de variables y la explicación generada. Nada lo recortaba.
    Pasado el plazo de retención, `retencion_service` agrega el detalle a esta tabla y lo
    borra; el resumen conserva la trayectoria (cuántas veces, entre qué valores, en qué
    categoría acabó el mes) sin el vector ni el texto de cada instante.

    La media no se guarda: se guarda la SUMA. Si un mes se agrega en dos pasadas —una fila
    que llegó tarde, una purga interrumpida—, dos medias no se pueden combinar sin saber
    cuántas filas había detrás de cada una, y dos sumas sí.
    """
    __tablename__ = "score_history_monthly"

    id = Column(Integer, primary_key=True, index=True)
    # Sin índice propio: el único de (lead_id, month) empieza por `lead_id` y ya sirve para
    # «los meses de este prospecto».
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    # Primer día del mes, en UTC. `Date` y no `DateTime`: un mes no tiene hora ni zona.
    month = Column(Date, nullable=False)

    scores_count = Column(Integer, nullable=False)
    score_sum = Column(Float, nullable=False)
    score_min = Column(Float, nullable=False)
    score_max = Column(Float, nullable=False)

    first_score = Column(Float, nullable=False)
    first_calculated_at = Column(DateTime(timezone=True), nullable=False)
    last_score = Column(Float, nullable=False)
    last_category = Column(SQLEnum(ScoreCategory), nullable=False)
    last_calculated_at = Column(DateTime(timezone=True), nullable=False)

    # {"HOT": 2, "WARM": 5} y ["v1.0.0-hybrid", ...]: cuánto tiempo pasó en cada categoría y
    # con qué modelos se puntuó, que es lo que se pregunta de un mes ya cerrado.
    category_counts = Column(JSON, nullable=False, default=dict)
    model_versions = Column(JSON, nullable=False, default=list)

    aggregated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    lead = relationship("Lead", back_populates="score_monthly")

    __table_args__ = (
        # Un mes por prospecto. Es lo que permite que una segunda pasada FUSIONE con el
        # resumen existente en lugar de duplicarlo.
        Index("uq_score_history_monthly_lead_month", "lead_id", "month", unique=True),
    )

    def __repr__(self) -> str:
        return f"<ScoreHistoryMonthly(lead_id={self.lead_id}, month={self.month}, n={self.scores_count})>"


class Desenlace(Base):
    """
    Cómo acabó un prospecto, por qué, cuándo y —si se ganó— de qué tamaño (capítulo 30).

    Por qué una tabla y no cuatro columnas en `leads`
    -------------------------------------------------
    `leads` describe a una persona y su situación **actual**: su teléfono, su empresa, su
    score, la etapa en la que está. El desenlace es un hecho fechado que ocurrió una vez, y
    que después no cambia porque la ficha cambie. Separarlo tiene tres consecuencias
    prácticas: la mitad de las fichas —las que siguen en curso— no arrastran cuatro
    columnas vacías; la exportación y la supresión del titular lo recogen por el mismo
    camino que todo lo demás que cuelga de `leads`; y el extractor del dataset puede
    preguntar «¿cuáles están cerrados con motivo?» con un `JOIN` en lugar de recorrer la
    cartera entera mirando un estado.

    Una fila por prospecto
    ----------------------
    `lead_id` es único. Un prospecto se cierra una vez; corregir un cierre —se marcó ganado
    y era perdido— reescribe esta fila en lugar de añadir otra. La alternativa, guardar el
    historial de cierres, sonaba más completa y habría obligado a decidir cuál de las filas
    es «el» desenlace cada vez que el panel o el extractor preguntan, que es justo la clase
    de ambigüedad que produce dos números distintos para la misma pregunta.

    Lo que se copia y por qué no se recalcula
    -----------------------------------------
    `score_al_cierre` y `categoria_al_cierre` se guardan aquí en lugar de leerse de la
    ficha. El score se mueve con cada actividad y con cada recálculo masivo: preguntado
    seis meses después diría lo que el prospecto vale hoy —cuando ya está cerrado y ninguna
    regla lo toca—, no lo que valía el día en que se decidió. La pregunta del panel es «¿el
    score acertaba?», y solo se puede responder con el valor que había al cerrarse.

    `version_del_vector` se copia de la instantánea de entrada, no de la constante de hoy.
    Es lo que permite que una instantánea de la versión 1 siga diciendo que lo es cuando la
    vigente sea la 3, y que el extractor la descarte en lugar de traducirla inventando.
    """
    __tablename__ = "desenlaces"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)

    # `ganado` o `perdido` (`app/core/desenlaces.py`). Texto y no un tipo enumerado de la
    # base, por lo mismo que la procedencia de las actividades y las reglas de la agenda:
    # tocar la lista no debe exigir un `ALTER TYPE`.
    resultado = Column(String(20), nullable=False, index=True)
    # La clave del motivo, de la lista cerrada de ese resultado. Nunca texto libre.
    motivo = Column(String(40), nullable=False, index=True)

    # El día en que se cerró, que no es el día en que alguien lo registró. Un trato que se
    # firmó el viernes y se anotó el lunes tiene que contar en su semana: el panel agrupa
    # por esta fecha, y `registrado_en` queda aparte para poder distinguir las dos cosas.
    # `Date` y no `DateTime`: un cierre no tiene hora, y fingir una obligaría a elegir un
    # huso para una fecha que la persona escribió en un calendario.
    cerrado_el = Column(Date, nullable=False, index=True)

    # Tramo del acuerdo. Solo en los ganados: un trato perdido no tiene tamaño, y pedirlo
    # invitaría a anotar «lo que habríamos facturado», que es una previsión de ingresos
    # inventada y queda explícitamente fuera del capítulo.
    tramo = Column(String(30), nullable=True)

    score_al_cierre = Column(Float, nullable=False)
    categoria_al_cierre = Column(SQLEnum(ScoreCategory), nullable=False, index=True)

    # La instantánea de entrada que este desenlace etiqueta, y con qué versión del vector
    # se tomó. Nulas cuando el prospecto se cerró sin ninguna instantánea aprovechable
    # —los anteriores al capítulo 18—: el desenlace se registra igual, y el contador del
    # reentrenamiento lo cuenta como cerrado pero no como utilizable, que es la verdad.
    score_history_id = Column(
        Integer, ForeignKey("score_histories.id", ondelete="SET NULL"), nullable=True
    )
    version_del_vector = Column(Integer, nullable=True)

    registrado_en = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    # Quién lo registró. Nulo si esa cuenta desaparece: el hecho sigue siendo cierto.
    registrado_por_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    lead = relationship("Lead", back_populates="desenlace")
    instantanea = relationship("ScoreHistory")

    __table_args__ = (
        Index("uq_desenlaces_lead", "lead_id", unique=True),
        # La consulta del panel: los de un periodo, agrupados por resultado y motivo.
        Index("idx_desenlaces_cerrado_resultado", "cerrado_el", "resultado"),
    )

    def __repr__(self) -> str:
        return (
            f"<Desenlace(lead_id={self.lead_id}, resultado='{self.resultado}', "
            f"motivo='{self.motivo}', cerrado_el={self.cerrado_el})>"
        )


class CRMIntegrationLog(Base):
    """
    Trazabilidad de sincronización e ingesta de prospectos con sistemas CRM externos.
    """
    __tablename__ = "crm_integration_logs"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True)

    external_crm_id = Column(String(100), nullable=True, index=True)
    crm_platform = Column(String(50), default="PluriOne_CRM", nullable=False)  # HubSpot, Salesforce, Zoho, PluriOne_CRM
    event_type = Column(String(50), nullable=False)  # INGEST, SCORE_UPDATE, STATUS_CHANGE
    sync_status = Column(String(20), default="SUCCESS", nullable=False)  # SUCCESS, FAILED, PENDING
    payload = Column(JSON, nullable=True, default=dict)
    response_data = Column(JSON, nullable=True, default=dict)
    error_message = Column(Text, nullable=True)
    synced_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    # Relaciones
    lead = relationship("Lead", back_populates="crm_logs")

    def __repr__(self) -> str:
        return f"<CRMIntegrationLog(id={self.id}, lead_id={self.lead_id}, platform='{self.crm_platform}', status='{self.sync_status}')>"



class JobStatus(str, enum.Enum):
    """Estados por los que pasa un trabajo en segundo plano."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ScoringJob(Base):
    """
    Trabajos de recálculo masivo lanzados en segundo plano.

    El estado vive en la base y no en un diccionario del proceso a propósito: la imagen
    arranca uvicorn con varios workers, así que un trabajo iniciado por uno de ellos sería
    invisible para el que atendiera después la consulta de estado, y el cliente recibiría
    un 404 por un trabajo que sí existe. Guardarlo aquí también hace que un reinicio deje
    rastro de lo que quedó a medias en lugar de perderlo.
    """
    __tablename__ = "scoring_jobs"

    # UUID en texto y no un autoincremental: el identificador viaja al cliente en la
    # respuesta 202 y no debe revelar cuántos recálculos se han lanzado.
    id = Column(String(36), primary_key=True, index=True)
    job_type = Column(String(50), default="RECALCULATE_ALL", nullable=False)
    status = Column(String(20), default=JobStatus.PENDING.value, nullable=False, index=True)

    total_leads = Column(Integer, default=0, nullable=False)
    processed_leads = Column(Integer, default=0, nullable=False)
    failed_leads = Column(Integer, default=0, nullable=False)
    batch_size = Column(Integer, default=100, nullable=False)

    requested_by = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    # --- Arriendo del trabajo (lease) y señal de vida ---
    #
    # Un trabajo en RUNNING no demuestra que nadie lo esté ejecutando. Si el contenedor
    # muere a mitad del recorrido, la fila se queda en RUNNING para siempre: quien
    # consulta ve "34 % y subiendo" de algo que lleva parado desde el martes, y como el
    # sistema cree que hay un recálculo en curso, ninguno nuevo puede empezar. El estado
    # solo dice qué se pretendía; hace falta algo que caduque por sí solo.
    #
    # `lease_until` es ese algo: el instante hasta el que el proceso que lo tomó afirma
    # seguir vivo. Lo renueva en cada lote. Pasado ese instante sin renovar, el trabajo se
    # considera abandonado y cualquiera puede reclamarlo —marcarlo FAILED y liberar el
    # turno—. La distinción entre "murió" y "sigue trabajando" no la da un ping a nadie:
    # la da un plazo que solo se prolonga mientras haya progreso real.
    lease_until = Column(DateTime(timezone=True), nullable=True)
    # Última señal de vida. Es informativa —quien decide es `lease_until`—, pero permite
    # ver desde fuera cuánto hace que el trabajo avanzó por última vez.
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    # Quién lo tomó: host y PID del proceso. Con varios workers y varias instancias, es la
    # única forma de saber en qué contenedor mirar cuando un trabajo se queda atascado.
    worker_id = Column(String(120), nullable=True)

    # Turno exclusivo, impuesto por la base y no por una comprobación previa.
    #
    # "Mira si hay uno activo y, si no, crea el tuyo" es una carrera: dos peticiones
    # simultáneas leen "no hay ninguno" y ambas insertan. Aquí el turno es una columna con
    # índice único que vale `RECALCULATE_ALL` mientras el trabajo está vivo y `NULL` en
    # cuanto termina. NULL no colisiona consigo mismo ni en PostgreSQL ni en SQLite, así
    # que los trabajos terminados no estorban, y el segundo INSERT simultáneo no se decide
    # por quién leyó antes: falla en el motor.
    lease_key = Column(String(40), nullable=True)

    __table_args__ = (
        # El índice se declara aquí, con nombre, y no como `unique=True` en la columna:
        # así lo que dice el modelo y lo que hace la migración son el mismo objeto del
        # catálogo, y `alembic check` no encuentra diferencia entre ambos.
        Index("uq_scoring_jobs_lease_key", "lease_key", unique=True),
    )

    def __repr__(self) -> str:
        return (
            f"<ScoringJob(id='{self.id}', status='{self.status}', "
            f"{self.processed_leads}/{self.total_leads})>"
        )


class RefreshToken(Base):
    """
    Un refresh token emitido, con su familia y su estado de revocación.

    Hasta ahora la rotación era nominal: `/auth/refresh` entregaba una cookie nueva pero
    la anterior seguía validando hasta su expiración, porque lo único que se comprobaba
    era `token_version`, que solo cambia al cerrar sesión. Una cookie robada servía siete
    días completos, y nada delataba el robo: víctima y atacante refrescaban en paralelo,
    cada uno con su cadena de tokens, sin interferirse.

    Con esta tabla el token pasa a tener identidad propia (`jti`) y pertenencia
    (`family_id`, constante durante toda la sesión). Al refrescar se marca el usado y se
    emite otro de la misma familia; presentar uno ya marcado solo puede significar que dos
    partes tienen la misma cookie, y como no hay forma de saber cuál es la legítima se
    revoca la familia entera y ambas vuelven a autenticarse. El robo deja de ser
    silencioso: cuesta una sesión, no siete días de acceso.
    """
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    # `jti` es el claim homónimo del JWT: identifica esta emisión concreta.
    jti = Column(String(32), unique=True, nullable=False, index=True)
    # Constante en toda la cadena de refrescos nacida de un mismo login.
    family_id = Column(String(32), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    issued_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    # Sello del momento en que dejó de servir, por consumo normal o por revocación.
    revoked_at = Column(DateTime(timezone=True), nullable=True, index=True)
    # ROTATED, REUSE_DETECTED, LOGOUT o FAMILY_REVOKED: sin esto, una familia revocada en
    # bloque y un token simplemente consumido serían indistinguibles al investigar.
    revoked_reason = Column(String(30), nullable=True)
    replaced_by_jti = Column(String(32), nullable=True)
    issued_ip = Column(String(64), nullable=True)

    user = relationship("User")

    def __repr__(self) -> str:
        estado = "revocado" if self.revoked_at else "vigente"
        return f"<RefreshToken(jti={self.jti}, familia={self.family_id}, {estado})>"


class WebhookDelivery(Base):
    """
    Entregas de webhook ya atendidas, para no atender dos veces la misma.

    La firma HMAC demuestra que el cuerpo lo escribió quien conoce el secreto; no
    demuestra que la petición sea nueva. Quien capture una entrega legítima puede
    reenviarla tal cual, y dentro de la ventana de tolerancia de la marca de tiempo
    —cinco minutos por defecto— vuelve a pasar todas las comprobaciones, porque es
    literalmente la misma petición. Cada repetición creaba otra actividad, movía el score
    y sumaba una fila de auditoría.

    Se registran dos huellas con propósitos distintos:

    * `signature` — el HMAC exacto. Repetirlo es reenviar los mismos bytes con la misma
      marca de tiempo: no hay emisor honesto que haga eso, así que se responde 409.
    * `idempotency_key` — evento, prospecto externo y huella del cuerpo. Un CRM que no
      recibió la respuesta reintenta con marca de tiempo nueva, de modo que la firma
      cambia aunque el evento sea el mismo. A ese se le devuelve la respuesta original,
      que es lo que pedía; contestarle con un error solo alimentaría el bucle de
      reintentos.
    """
    __tablename__ = "webhook_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    signature = Column(String(64), unique=True, nullable=False, index=True)
    idempotency_key = Column(String(255), unique=True, nullable=False, index=True)

    crm_platform = Column(String(50), nullable=False)
    event = Column(String(50), nullable=False)
    external_lead_id = Column(String(100), nullable=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True)
    # Respuesta que se dio la primera vez, para poder repetirla ante un reintento.
    response_data = Column(JSON, nullable=True, default=dict)

    received_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    # A partir de aquí la entrada ya no protege de nada: la marca de tiempo original cae
    # fuera de la ventana anti-replay y el reintento honesto ha dejado de tener sentido.
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<WebhookDelivery(event={self.event}, externo={self.external_lead_id})>"


class AuditLog(Base):
    """
    Quién hizo qué, sobre qué, desde dónde y con qué resultado.

    El sistema registraba la sincronización con el CRM y el historial de scoring, es decir
    lo que le pasaba a los datos, pero no lo que hacían las personas. Un prospecto borrado
    no dejaba rastro de quién lo borró, y un intento de acceso denegado por rol solo vivía
    en el log de texto del contenedor, que rota y se pierde.

    Los intentos fallidos se anotan igual que los correctos, y a propósito: una sola
    denegación es ruido, pero una tanda de 403 seguidos de la misma cuenta es alguien
    tanteando los límites de su rol, y eso solo se ve si queda escrito.
    """
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)

    # El actor se guarda desnormalizado —id, correo y rol— en lugar de por clave foránea.
    # Una bitácora que dependiera de la fila del usuario perdería el nombre de quien actuó
    # en cuanto la cuenta se eliminara, justo en el caso en que más falta hace. Y el rol
    # es el que tenía *en ese momento*, no el que tenga hoy.
    actor_id = Column(Integer, nullable=True, index=True)
    actor_email = Column(String(150), nullable=True, index=True)
    actor_role = Column(String(50), nullable=True)

    action = Column(String(60), nullable=False, index=True)
    entity = Column(String(60), nullable=False, index=True)
    entity_id = Column(String(64), nullable=True, index=True)
    # OK, o el estado con el que terminó: HTTP_403, HTTP_404, ERROR...
    outcome = Column(String(20), default="OK", nullable=False, index=True)

    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(255), nullable=True)
    # `metadata` es un atributo reservado por la base declarativa de SQLAlchemy.
    event_metadata = Column(JSON, nullable=True, default=dict)

    occurred_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    def __repr__(self) -> str:
        return (
            f"<AuditLog(actor={self.actor_email}, action={self.action}, "
            f"entity={self.entity}:{self.entity_id}, outcome={self.outcome})>"
        )


# Índices compuestos para optimización analítica de alta concurrencia
Index("idx_leads_score_status", Lead.score_category, Lead.status)
Index("idx_leads_created_score", Lead.created_at, Lead.current_score)
Index("idx_activity_lead_time", LeadActivity.lead_id, LeadActivity.occurred_at)
Index("idx_score_history_lead_time", ScoreHistory.lead_id, ScoreHistory.calculated_at)

# La consulta más frecuente tras N-3 es "los prospectos de esta persona, por puntuación":
# el filtro por dueño deja de ser opcional para un asesor, así que entra en el índice.
Index("idx_leads_rep_score", Lead.assigned_rep_id, Lead.current_score)

# Un token se busca siempre por su `jti`, pero la revocación en cadena recorre la familia
# entera del usuario: sin este índice, detectar una reutilización obligaría a un barrido.
Index("idx_refresh_family_user", RefreshToken.family_id, RefreshToken.user_id)
# La consulta natural de la bitácora es "qué hizo esta cuenta últimamente".
Index("idx_audit_actor_time", AuditLog.actor_email, AuditLog.occurred_at)
Index("idx_audit_entity_time", AuditLog.entity, AuditLog.entity_id, AuditLog.occurred_at)
