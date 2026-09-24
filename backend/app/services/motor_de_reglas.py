"""
El motor de reglas: qué hay que hacer hoy con cada prospecto (capítulo 28).

Lo que pasaba
-------------
El sistema sabía puntuar y no sabía avisar. Un prospecto llegaba de una publicación, se
puntuaba, se asignaba, y a partir de ahí dependía de que alguien se acordara de mirarlo. La
prueba con personas dejó dos notas sobre exactamente eso: la marca «Nuevo desde LinkedIn»
desaparece justo cuando el asesor va a buscarlo, y el contador de sin asignar vive en una
pestaña que el líder no abre primero. Las dos son el mismo hueco: el sistema no le dice a
nadie lo que le toca.

Dónde corre
-----------
En la **pasada diaria que ya existe** (`scripts/retencion_historial.py`), junto a la
retención del historial y los plazos de conservación. No es un servicio nuevo a propósito, y
es el mismo argumento del capítulo 22: un proceso más que supervisar es un proceso más que
puede quedarse parado sin que nadie lo note. Sin colas, sin planificador, sin n8n y sin
correo.

Por qué todo se resuelve barriendo, y no enganchándose a cada sitio
-------------------------------------------------------------------
«Al asignar, tarea de primer contacto» invita a poner la llamada donde se asigna. El
problema es que asignar ocurre en cinco sitios —el alta con asesor, la edición de la ficha,
el reparto de cartera de una baja, la asignación automática de un HOT y la ficha que nace
con el responsable de su publicación— y el día que aparezca el sexto, nadie recibirá un
error: simplemente esas tareas no se crearán. Es el mismo razonamiento que llevó el alcance
de cartera al repositorio en vez de a cada endpoint (`app/core/autorizacion.py`): el único
sitio seguro para una regla es aquel por el que hay que pasar obligatoriamente.

Aquí ese sitio es una consulta sobre el estado, no un gancho sobre el suceso. El motor no
pregunta «¿se acaba de asignar algo?», pregunta «¿hay algún prospecto asignado al que nadie
haya contactado?». Da igual por dónde se asignara. El precio es la granularidad: la tarea
aparece en la pasada siguiente y no en el mismo segundo. Para trabajo que se mide en días es
un precio justo, y queda escrito en el reporte.

La excepción son los cierres. Una tarea que se cierra sola tiene que cerrarse **cuando pasa
lo que esperaba** y no mañana, porque hasta entonces el asesor la seguiría viendo en su
bandeja. `cerrar_lo_cumplido` la llama `registrar_evento`, que es el único sitio por el que
se escribe una actividad, y la pasada diaria la vuelve a llamar como barrido. La misma
función en los dos caminos: dos criterios de «esto ya está» acabarían discrepando.

Lo cerrado sale de aquí (capítulo 30)
-------------------------------------
Todas las reglas preguntan además si del prospecto queda algo que hacer. Un trato ganado,
uno perdido y un prospecto descartado no reciben tareas ni avisos, y las que tuvieran
abiertas se descartan en el momento del cierre. El filtro está en la **consulta** de cada
regla y no solo en la bandeja: filtrar al pintar habría dejado el motor creando cada
madrugada tareas invisibles sobre tratos cerrados, ocupando el índice único para siempre.

Idempotencia
------------
Ninguna regla comprueba si ya hizo su trabajo: lo intenta y deja que el índice único de la
base lo rechace. Es lo que permite repetir la pasada sin miedo —la misma mañana, tras un
reintento, después de una caída— y lo que hace que dos pasadas simultáneas no dupliquen
nada. Un `SELECT` previo seguido de un `INSERT` no da esa garantía: entre los dos cabe otra
pasada.

Lo que este módulo NO hace
--------------------------
No manda correos ni mensajes: todo vive dentro del panel. No deja escribir reglas al
usuario. No toca el score —una tarea pendiente no puede hacer a nadie más interesante— y no
reentrena nada.
"""
import datetime
import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.agenda import (
    ABIERTA,
    CUMPLIDA,
    DESCARTADA,
    DESENLACES_SUFICIENTES,
    HOT_SIN_CONTACTO,
    HOT_SIN_CONTACTO_LIDER,
    ORDEN_DE_LAS_REGLAS,
    PRIMER_CONTACTO,
    PROSPECTO_DORMIDO,
    RECORDATORIO_DE_REUNION,
    REGLAS,
    VOLVER_A_LLAMAR,
)
from app.core.audit import (
    ACCION_REGLA_EJECUCION,
    ENTIDAD_REGLA,
    RESULTADO_ERROR,
    RESULTADO_OK,
)
from app.core.audit import (
    registrar_evento as anotar_en_bitacora,
)
from app.core.config import settings
from app.core.desenlaces import ETAPAS_SIN_SEGUIMIENTO, MINIMO_DE_CASOS, MINIMO_POR_CLASE
from app.core.security import UserRole
from app.core.vector_del_modelo import VERSION_DEL_VECTOR
from app.models.entities import (
    ActivityType,
    Aviso,
    CallOutcome,
    Desenlace,
    Lead,
    LeadActivity,
    LeadStatus,
    ScoreCategory,
    Tarea,
    User,
    utc_now,
)
from app.services.desenlaces import progreso_del_reentrenamiento

logger = logging.getLogger(__name__)

# Lo que cuenta como que **nosotros** tocamos a esta persona. Un correo abierto o una visita
# a la web son cosas que hace ella: no son contacto, son interés, y confundirlos haría que
# un prospecto muy interesado y completamente desatendido pareciera atendido.
TIPOS_DE_CONTACTO = (
    ActivityType.PHONE_CALL,
    ActivityType.MEETING_SCHEDULED,
    ActivityType.WHATSAPP_MESSAGE,
    ActivityType.LINKEDIN_MESSAGE,
    ActivityType.PROPOSAL_SENT,
)

# Una llamada que no contestaron **sí** cuenta como primer contacto: el asesor hizo el
# trabajo, y el hecho de que no hubiera nadie al otro lado lo recoge «volver a llamar». La
# alternativa —que no contara— dejaría las dos tareas abiertas a la vez sobre el mismo
# prospecto, que es justo el ruido que una bandeja de trabajo no se puede permitir.
LLAMADAS_SIN_RESPUESTA = (CallOutcome.NO_CONTESTO.value, CallOutcome.BUZON.value)

# El dato con el que Calendly dice cuándo es la reunión, y el que el panel guarda cuando el
# asesor la agenda a mano. `occurred_at` no sirve: es cuándo se agendó, no cuándo es.
CLAVE_INICIO_DE_REUNION = "inicio_de_la_reunion"


@dataclass
class ResultadoDeRegla:
    """Lo que hizo una regla en una pasada. Es lo que se imprime y lo que va a la bitácora."""
    regla: str
    tareas: int = 0
    avisos: int = 0
    cerradas: int = 0
    marcados: int = 0
    error: Optional[str] = None

    def como_dict(self) -> Dict[str, object]:
        return {
            "regla": self.regla,
            "tareas_creadas": self.tareas,
            "avisos_creados": self.avisos,
            "tareas_cerradas": self.cerradas,
            "prospectos_marcados": self.marcados,
            "error": self.error,
        }


@dataclass
class Contexto:
    """Lo que toda regla necesita y nadie debería volver a consultar por su cuenta."""
    db: Session
    ahora: datetime.datetime
    lideres: List[int] = field(default_factory=list)


# ==============================================================================
# Escritura idempotente
# ==============================================================================

def _crear(db: Session, fila) -> bool:
    """
    Intenta escribir la fila; devuelve si era nueva.

    El punto de guardado es lo que permite que una colisión no arrastre a la transacción
    entera: sin él, el `IntegrityError` de la tercera tarea invalidaría las dos anteriores y
    la pasada no crearía nada el día que una sola se repitiera.
    """
    punto = db.begin_nested()
    try:
        db.add(fila)
        punto.commit()
        return True
    except IntegrityError:
        punto.rollback()
        return False


def _tarea(
    ctx: Contexto,
    *,
    lead: Lead,
    asesor_id: int,
    regla: str,
    clave: str,
    vence_el: datetime.datetime,
    motivo: str,
    datos: Optional[Dict[str, object]] = None,
) -> bool:
    return _crear(
        ctx.db,
        Tarea(
            lead_id=lead.id,
            asesor_id=asesor_id,
            regla=regla,
            clave=clave,
            estado=ABIERTA,
            vence_el=vence_el,
            motivo=motivo,
            datos=datos or {},
            creada_en=ctx.ahora,
        ),
    )


def _aviso(
    ctx: Contexto,
    *,
    lead: Lead,
    usuario_id: int,
    regla: str,
    clave: str,
    texto: str,
    datos: Optional[Dict[str, object]] = None,
) -> bool:
    return _crear(
        ctx.db,
        Aviso(
            usuario_id=usuario_id,
            lead_id=lead.id,
            regla=regla,
            clave=clave,
            texto=texto,
            datos=datos or {},
            creado_en=ctx.ahora,
        ),
    )


# ==============================================================================
# Consultas compartidas
# ==============================================================================

def _lideres(db: Session) -> List[int]:
    """
    Quién recibe lo que se escala. Las cuentas de líder **activas**.

    Si no hay ninguna, el aviso no se manda a nadie en lugar de mandarse a todo el mundo:
    escalar a quien no corresponde es peor que no escalar.
    """
    return [
        fila.id
        for fila in db.query(User.id)
        .filter(User.role == UserRole.SALES_LEAD.value, User.is_active.is_(True))
        .all()
    ]


# Las etapas en las que el motor deja de proponer trabajo, ya como miembros del tipo
# enumerado: la columna es un `Enum` y comparar contra cadenas sueltas funcionaría en
# SQLite y no en PostgreSQL.
_ETAPAS_SIN_SEGUIMIENTO = [LeadStatus(etapa) for etapa in ETAPAS_SIN_SEGUIMIENTO]


def en_seguimiento():
    """
    Condición: de este prospecto todavía hay algo que hacer (capítulo 30).

    Va en **todas** las reglas y no en la bandeja, que es donde se vería antes. Filtrar
    solo al pintar habría dejado el motor creando cada madrugada tareas invisibles sobre
    tratos cerrados: no molestan a nadie, ocupan el índice único para siempre y, el día
    que alguien reabriera un prospecto, reaparecerían todas con la fecha equivocada.

    Es la misma decisión que el capítulo 28 tomó con las asignaciones: la regla se
    comprueba donde hay que pasar obligatoriamente, y aquí eso es la consulta.
    """
    return Lead.status.notin_(_ETAPAS_SIN_SEGUIMIENTO)


def _sin_contacto(db: Session):
    """Condición: este prospecto no tiene ninguna actividad de contacto nuestra."""
    existe = (
        db.query(LeadActivity.id)
        .filter(LeadActivity.lead_id == Lead.id, LeadActivity.activity_type.in_(TIPOS_DE_CONTACTO))
        .exists()
    )
    return ~existe


def _clave_del_episodio(lead: Lead) -> str:
    """
    Qué silencio es este.

    Un prospecto puede quedarse sin contacto, recibir una llamada y volver a quedarse sin
    contacto meses después: son dos episodios y merecen dos avisos. Con una clave fija, el
    segundo no llegaría nunca; con la fecha del día, llegaría uno cada mañana hasta que
    alguien lo atendiera. La última actividad conocida identifica el episodio sin ninguna de
    las dos cosas.
    """
    momento = lead.last_activity_at or lead.created_at
    return aware(momento).date().isoformat()


def aware(momento: datetime.datetime) -> datetime.datetime:
    """SQLite devuelve las fechas sin zona; compararlas con una que sí la tiene revienta."""
    if momento.tzinfo is None:
        return momento.replace(tzinfo=datetime.timezone.utc)
    return momento


# ==============================================================================
# Las reglas
# ==============================================================================

def regla_primer_contacto(ctx: Contexto) -> ResultadoDeRegla:
    """
    Un prospecto asignado al que nadie ha contactado necesita que alguien lo llame.

    El corte por antigüedad no es un número redondo: pasado el plazo de «dormido», de este
    prospecto se ocupa la regla del dormido, y crear además una tarea de primer contacto
    sería mandar a alguien a estrenar una relación que lleva un mes muerta. Ese corte es
    también lo que impide que la primera pasada tras instalar el capítulo abra una tarea por
    cada prospecto antiguo de la base.
    """
    resultado = ResultadoDeRegla(PRIMER_CONTACTO)
    desde = ctx.ahora - datetime.timedelta(days=settings.REGLA_DORMIDO_DIAS)
    vence = ctx.ahora + datetime.timedelta(hours=settings.REGLA_PRIMER_CONTACTO_HORAS)

    pendientes = (
        ctx.db.query(Lead)
        .filter(
            Lead.assigned_rep_id.isnot(None),
            Lead.created_at >= desde,
            en_seguimiento(),
            _sin_contacto(ctx.db),
        )
        .all()
    )
    for lead in pendientes:
        if _tarea(
            ctx,
            lead=lead,
            asesor_id=lead.assigned_rep_id,
            regla=PRIMER_CONTACTO,
            # El asesor forma parte de la clave: si el prospecto se reasigna, la persona
            # nueva estrena su propia tarea en vez de heredar una que ya se cerró.
            clave=str(lead.assigned_rep_id),
            vence_el=vence,
            motivo="Asignado y todavía sin contactar.",
            datos={"score": lead.current_score},
        ):
            resultado.tareas += 1
    return resultado


def regla_volver_a_llamar(ctx: Contexto) -> ResultadoDeRegla:
    """
    La última llamada acabó en el buzón: se vuelve a intentar pasado el plazo.

    Se mira **la última** llamada de cada prospecto y no todas: diez intentos seguidos sin
    respuesta son un solo trabajo pendiente, no diez. Que la tarea venza desde la llamada y
    no desde hoy es lo que hace que la pasada del día siguiente no la aplace otra vez.
    """
    resultado = ResultadoDeRegla(VOLVER_A_LLAMAR)

    llamadas = (
        ctx.db.query(LeadActivity)
        .join(Lead, Lead.id == LeadActivity.lead_id)
        .filter(
            LeadActivity.activity_type == ActivityType.PHONE_CALL,
            Lead.assigned_rep_id.isnot(None),
            en_seguimiento(),
        )
        .order_by(LeadActivity.lead_id, LeadActivity.occurred_at.desc(), LeadActivity.id.desc())
        .all()
    )
    ultima_por_prospecto: Dict[int, LeadActivity] = {}
    for llamada in llamadas:
        ultima_por_prospecto.setdefault(llamada.lead_id, llamada)

    for llamada in ultima_por_prospecto.values():
        if llamada.call_outcome not in LLAMADAS_SIN_RESPUESTA:
            continue
        lead = ctx.db.get(Lead, llamada.lead_id)
        if _tarea(
            ctx,
            lead=lead,
            asesor_id=lead.assigned_rep_id,
            regla=VOLVER_A_LLAMAR,
            # La llamada concreta. Otro intento fallido mañana es otra tarea, y el mismo
            # intento releído por la pasada del jueves no lo es.
            clave=str(llamada.id),
            vence_el=aware(llamada.occurred_at)
            + datetime.timedelta(days=settings.REGLA_VOLVER_A_LLAMAR_DIAS),
            motivo="La última llamada no la contestaron.",
            datos={"resultado": llamada.call_outcome},
        ):
            resultado.tareas += 1
    return resultado


def regla_recordatorio_de_reunion(ctx: Contexto) -> ResultadoDeRegla:
    """
    La víspera de una reunión ya agendada.

    Solo entran las reuniones que dicen **cuándo son**. `occurred_at` es cuándo se agendó, y
    una reunión agendada el martes puede ser el jueves siguiente: recordar sobre esa fecha
    avisaría siempre tarde. Calendly manda `inicio_de_la_reunion` y el panel lo pide al
    asesor cuando registra la reunión a mano; una reunión sin fecha no se recuerda, y eso es
    mejor que recordarla el día equivocado.
    """
    resultado = ResultadoDeRegla(RECORDATORIO_DE_REUNION)
    antelacion = datetime.timedelta(hours=settings.REGLA_RECORDATORIO_DE_REUNION_HORAS)

    reuniones = (
        ctx.db.query(LeadActivity)
        .join(Lead, Lead.id == LeadActivity.lead_id)
        .filter(
            LeadActivity.activity_type == ActivityType.MEETING_SCHEDULED,
            Lead.assigned_rep_id.isnot(None),
            en_seguimiento(),
        )
        .all()
    )
    for reunion in reuniones:
        inicio = _momento_de_la_reunion(reunion)
        if inicio is None or inicio <= ctx.ahora:
            continue
        # Todavía no toca: el recordatorio es la víspera, no el día que se agendó.
        if inicio - antelacion > ctx.ahora:
            continue
        lead = ctx.db.get(Lead, reunion.lead_id)
        if _tarea(
            ctx,
            lead=lead,
            asesor_id=lead.assigned_rep_id,
            regla=RECORDATORIO_DE_REUNION,
            clave=str(reunion.id),
            vence_el=inicio,
            motivo="Reunión agendada; prepárala.",
            datos={CLAVE_INICIO_DE_REUNION: inicio.isoformat()},
        ):
            resultado.tareas += 1
    return resultado


def _momento_de_la_reunion(actividad: LeadActivity) -> Optional[datetime.datetime]:
    """La fecha de la reunión, si la actividad la trae y se puede leer."""
    datos = actividad.activity_data or {}
    crudo = datos.get(CLAVE_INICIO_DE_REUNION)
    if not crudo:
        return None
    try:
        return aware(datetime.datetime.fromisoformat(str(crudo).replace("Z", "+00:00")))
    except ValueError:
        # Un dato ilegible de una integración no puede tumbar la pasada entera.
        logger.warning("Reunión %s con fecha ilegible; no se recuerda.", actividad.id)
        return None


def hot_desatendidos(ctx: Contexto, horas: int) -> List[Lead]:
    corte = ctx.ahora - datetime.timedelta(hours=horas)
    return (
        ctx.db.query(Lead)
        .filter(
            Lead.score_category == ScoreCategory.HOT,
            Lead.created_at <= corte,
            en_seguimiento(),
            _sin_contacto(ctx.db),
        )
        .all()
    )


def regla_hot_sin_contacto(ctx: Contexto) -> ResultadoDeRegla:
    """
    Un HOT que lleva horas sin que nadie lo toque, avisado a su asesor.

    Sin asesor no hay a quién avisar, y ese caso ya tiene su sitio: el contador de «nuevos
    sin asesor» del líder (capítulo 25). Avisar aquí además sería contar lo mismo dos veces
    en dos pantallas distintas.
    """
    resultado = ResultadoDeRegla(HOT_SIN_CONTACTO)
    for lead in hot_desatendidos(ctx, settings.REGLA_HOT_SIN_CONTACTO_HORAS):
        if lead.assigned_rep_id is None:
            continue
        if _aviso(
            ctx,
            lead=lead,
            usuario_id=lead.assigned_rep_id,
            regla=HOT_SIN_CONTACTO,
            clave=_clave_del_episodio(lead),
            texto=f"Prospecto HOT sin contactar desde hace {settings.REGLA_HOT_SIN_CONTACTO_HORAS} h.",
            datos={"score": lead.current_score, "horas": settings.REGLA_HOT_SIN_CONTACTO_HORAS},
        ):
            resultado.avisos += 1
    return resultado


def regla_hot_sin_contacto_lider(ctx: Contexto) -> ResultadoDeRegla:
    """
    Lo mismo, más tarde, al líder. Escalar y no repetir.

    Solo sube lo que **ya se avisó** al asesor y sigue igual. La comprobación es explícita y
    no se deja en manos de que los plazos estén bien ordenados: si alguien configura 48 y 24
    al revés, el validador de `config.py` lo impide al arrancar, pero si algún día ese
    validador se cae, esto seguiría sin avisar al líder de algo que el asesor no ha visto.
    """
    resultado = ResultadoDeRegla(HOT_SIN_CONTACTO_LIDER)
    if not ctx.lideres:
        return resultado

    for lead in hot_desatendidos(ctx, settings.REGLA_HOT_LIDER_HORAS):
        clave = _clave_del_episodio(lead)
        ya_avisado = (
            ctx.db.query(Aviso.id)
            .filter(Aviso.lead_id == lead.id, Aviso.regla == HOT_SIN_CONTACTO, Aviso.clave == clave)
            .first()
        )
        if ya_avisado is None:
            continue
        for lider_id in ctx.lideres:
            if _aviso(
                ctx,
                lead=lead,
                usuario_id=lider_id,
                regla=HOT_SIN_CONTACTO_LIDER,
                clave=clave,
                texto=(
                    f"Prospecto HOT sin contactar desde hace {settings.REGLA_HOT_LIDER_HORAS} h; "
                    "el aviso a su asesor no lo resolvió."
                ),
                datos={"score": lead.current_score, "asesor_id": lead.assigned_rep_id},
            ):
                resultado.avisos += 1
    return resultado


def regla_prospecto_dormido(ctx: Contexto) -> ResultadoDeRegla:
    """
    Tantos días sin nada y el prospecto queda marcado como dormido.

    La marca es lo que hace que esto avise **una vez** y no cada mañana. La quita la primera
    actividad que llegue (`despertar`), así que un prospecto que revive y vuelve a quedarse
    quieto se marca otra vez, y con razón.

    Se marcan todos, tengan asesor o no. El aviso, en cambio, necesita destinatario: va a su
    asesor, y si no tiene, a los líderes, que son quienes pueden hacer algo al respecto.
    """
    resultado = ResultadoDeRegla(PROSPECTO_DORMIDO)
    corte = ctx.ahora - datetime.timedelta(days=settings.REGLA_DORMIDO_DIAS)

    dormidos = (
        ctx.db.query(Lead)
        .filter(
            Lead.dormido_desde.is_(None), Lead.last_activity_at < corte, en_seguimiento()
        )
        .all()
    )
    for lead in dormidos:
        clave = _clave_del_episodio(lead)
        lead.dormido_desde = ctx.ahora
        resultado.marcados += 1
        destinatarios = [lead.assigned_rep_id] if lead.assigned_rep_id else ctx.lideres
        for usuario_id in destinatarios:
            if _aviso(
                ctx,
                lead=lead,
                usuario_id=usuario_id,
                regla=PROSPECTO_DORMIDO,
                clave=clave,
                texto=f"Sin ninguna actividad desde hace {settings.REGLA_DORMIDO_DIAS} días.",
                datos={"score": lead.current_score},
            ):
                resultado.avisos += 1
    return resultado


def regla_desenlaces_suficientes(ctx: Contexto) -> ResultadoDeRegla:
    """
    Ya hay cierres registrados de sobra para plantear un reentrenamiento (capítulo 30).

    Es la única regla que no habla de un prospecto: habla del conjunto. Avisa **una vez** y
    no cada mañana, y eso lo consigue la clave, que son los mínimos exigidos y no la cuenta
    del día: con la cuenta, cada cierre nuevo dispararía otro aviso a partir del doscientos.
    Si algún día se suben los mínimos, la clave cambia y el aviso vuelve a llegar, que es lo
    correcto: el umbral que se alcanzó es otro.

    El aviso cuelga del **cierre que inclinó la balanza**: el que hizo número
    `MINIMO_DE_CASOS` entre los utilizables, por orden de registro. Un aviso necesita un
    prospecto del que hablar —es la forma de la tabla desde el capítulo 28— y colgarlo del
    *último* cerrado habría sido un error sutil: el último cambia con cada cierre nuevo, el
    índice único incluye al prospecto, y la pasada de mañana habría escrito otro aviso
    idéntico sobre otra persona. El que hizo el número doscientos, en cambio, es siempre el
    mismo.

    Queda un caso raro y asumido: si esa persona ejerce su derecho de supresión, el aviso se
    va con ella, el puesto lo ocupa el siguiente y la pasada vuelve a avisar. Un aviso
    repetido cada varios meses es un precio menor que una tabla de avisos con filas que no
    cuelgan de nadie.

    No reentrena. No genera el CSV, no toca el artefacto y no escribe en el registro de
    modelos: dice que se puede, y quien decide es una persona.
    """
    resultado = ResultadoDeRegla(DESENLACES_SUFICIENTES)
    if not ctx.lideres:
        return resultado

    progreso = progreso_del_reentrenamiento(ctx.db)
    if not progreso.alcanzado:
        return resultado

    el_que_inclino = (
        ctx.db.query(Desenlace)
        .filter(
            Desenlace.score_history_id.isnot(None),
            Desenlace.version_del_vector == VERSION_DEL_VECTOR,
        )
        .order_by(Desenlace.registrado_en.asc(), Desenlace.id.asc())
        .offset(MINIMO_DE_CASOS - 1)
        .first()
    )
    if el_que_inclino is None:
        return resultado
    lead = ctx.db.get(Lead, el_que_inclino.lead_id)
    if lead is None:
        return resultado

    clave = f"{MINIMO_DE_CASOS}-{MINIMO_POR_CLASE}"
    for lider_id in ctx.lideres:
        if _aviso(
            ctx,
            lead=lead,
            usuario_id=lider_id,
            regla=DESENLACES_SUFICIENTES,
            clave=clave,
            texto=(
                f"Ya hay {progreso.utilizables} desenlaces utilizables "
                f"({progreso.ganados_utilizables} ganados y {progreso.perdidos_utilizables} "
                f"perdidos): se puede plantear el reentrenamiento. No se ha reentrenado nada."
            ),
            datos={
                "utilizables": progreso.utilizables,
                "ganados": progreso.ganados_utilizables,
                "perdidos": progreso.perdidos_utilizables,
                "minimo_de_casos": progreso.minimo_de_casos,
                "minimo_por_clase": progreso.minimo_por_clase,
            },
        ):
            resultado.avisos += 1
    return resultado


REGLA_POR_CLAVE: Dict[str, Callable[[Contexto], ResultadoDeRegla]] = {
    PRIMER_CONTACTO: regla_primer_contacto,
    VOLVER_A_LLAMAR: regla_volver_a_llamar,
    RECORDATORIO_DE_REUNION: regla_recordatorio_de_reunion,
    HOT_SIN_CONTACTO: regla_hot_sin_contacto,
    HOT_SIN_CONTACTO_LIDER: regla_hot_sin_contacto_lider,
    PROSPECTO_DORMIDO: regla_prospecto_dormido,
    DESENLACES_SUFICIENTES: regla_desenlaces_suficientes,
}


# ==============================================================================
# Cerrar lo que ya ocurrió
# ==============================================================================

def cerrar_lo_cumplido(
    db: Session,
    lead: Lead,
    actividad: Optional[LeadActivity] = None,
    *,
    ahora: Optional[datetime.datetime] = None,
    commit: bool = False,
) -> int:
    """
    Cierra las tareas de este prospecto que ya no hay que hacer, y lo despierta.

    Es la función que llama `registrar_evento` en cuanto se escribe una actividad, para que
    el asesor no vea en su bandeja algo que acaba de hacer. La pasada diaria la vuelve a
    llamar como barrido: una actividad escrita por un camino que no pase por ahí —o antes de
    que este capítulo existiera— también tiene que cerrar lo suyo.

    Qué cierra cada cosa:

    * cualquier contacto nuestro cierra «primer contacto»: ya hubo primer contacto;
    * una llamada **contestada** cierra «volver a llamar», y una que no se contesta no, que
      es justo lo que esa tarea está esperando;
    * pasada la hora de la reunión, su recordatorio deja de tener sentido.

    Devuelve cuántas cerró. No confirma la transacción salvo que se le pida: cuando la llama
    el registro de actividad, lo que cierra tiene que confirmarse —o descartarse— junto con
    la actividad que lo provocó.
    """
    ahora = ahora or utc_now()
    tipo = actividad.activity_type if actividad is not None else None

    condiciones = []
    if tipo is None or tipo in TIPOS_DE_CONTACTO:
        condiciones.append(Tarea.regla == PRIMER_CONTACTO)
    if tipo is None or (tipo == ActivityType.PHONE_CALL and actividad.call_outcome == CallOutcome.CONECTO.value):
        condiciones.append(Tarea.regla == VOLVER_A_LLAMAR)

    cerradas = 0
    if condiciones:
        abiertas = (
            db.query(Tarea)
            .filter(Tarea.lead_id == lead.id, Tarea.estado == ABIERTA, or_(*condiciones))
            .all()
        )
        # En el barrido diario (`actividad is None`) no vale cerrar «primer contacto» de un
        # prospecto que nunca ha sido contactado: la condición de arriba lo deja pasar
        # porque no hay actividad que mirar, y hay que volver a preguntarlo aquí.
        if actividad is None:
            tiene_contacto = _tiene_contacto(db, lead)
            llamada_contestada = _llamada_contestada(db, lead)
            abiertas = [
                tarea
                for tarea in abiertas
                if (tarea.regla == PRIMER_CONTACTO and tiene_contacto)
                or (tarea.regla == VOLVER_A_LLAMAR and llamada_contestada)
            ]
        for tarea in abiertas:
            _cerrar(tarea, ahora)
            cerradas += 1

    cerradas += _cerrar_recordatorios_pasados(db, lead, ahora)

    # Cualquier actividad lo despierta: la marca dice «nadie lo toca», y acaban de tocarlo.
    if actividad is not None and lead.dormido_desde is not None:
        lead.dormido_desde = None

    if commit:
        db.commit()
    return cerradas


def _cerrar(tarea: Tarea, ahora: datetime.datetime) -> None:
    tarea.estado = CUMPLIDA
    tarea.cerrada_en = ahora
    # `cerrada_por_id` se queda nulo: no la cerró nadie, ocurrió lo que esperaba.


def _tiene_contacto(db: Session, lead: Lead) -> bool:
    return (
        db.query(LeadActivity.id)
        .filter(LeadActivity.lead_id == lead.id, LeadActivity.activity_type.in_(TIPOS_DE_CONTACTO))
        .first()
        is not None
    )


def _llamada_contestada(db: Session, lead: Lead) -> bool:
    return (
        db.query(LeadActivity.id)
        .filter(
            LeadActivity.lead_id == lead.id,
            LeadActivity.activity_type == ActivityType.PHONE_CALL,
            LeadActivity.call_outcome == CallOutcome.CONECTO.value,
        )
        .first()
        is not None
    )


def _cerrar_recordatorios_pasados(db: Session, lead: Lead, ahora: datetime.datetime) -> int:
    """Un recordatorio de una reunión que ya pasó no es trabajo pendiente."""
    cerradas = 0
    abiertos = (
        db.query(Tarea)
        .filter(
            Tarea.lead_id == lead.id,
            Tarea.estado == ABIERTA,
            Tarea.regla == RECORDATORIO_DE_REUNION,
            Tarea.vence_el < ahora,
        )
        .all()
    )
    for tarea in abiertos:
        _cerrar(tarea, ahora)
        cerradas += 1
    return cerradas


def descartar_por_desenlace(
    db: Session, lead: Lead, *, ahora: Optional[datetime.datetime] = None
) -> int:
    """
    Cierra como **descartadas** las tareas abiertas de un prospecto que acaba de cerrarse.

    No es `hecha` —nadie la hizo— ni `cumplida` —no ocurrió lo que la tarea esperaba—. El
    trato terminó y el trabajo dejó de tener sentido, que es una tercera cosa y merece su
    propio estado: juntarla con «hecha» convertiría la primera métrica de cumplimiento que
    alguien calcule en un número inflado por los tratos que se cerraron solos.

    Lo llama el servicio que registra el desenlace, dentro de su transacción. La bandeja
    filtra además por etapa, así que un prospecto cerrado por cualquier otro camino —una
    migración, un arreglo a mano en la base— tampoco aparece; las dos defensas existen
    porque la barata (filtrar al leer) no limpia y la que limpia no cubre lo que no pasó
    por aquí.
    """
    ahora = ahora or utc_now()
    abiertas = (
        db.query(Tarea).filter(Tarea.lead_id == lead.id, Tarea.estado == ABIERTA).all()
    )
    for tarea in abiertas:
        tarea.estado = DESCARTADA
        tarea.cerrada_en = ahora
        # `cerrada_por_id` nulo: no la cerró una persona, la cerró el desenlace.
    return len(abiertas)


def regla_cerrar_lo_cumplido(ctx: Contexto) -> ResultadoDeRegla:
    """
    El barrido: repasa los prospectos con alguna tarea abierta y cierra lo que ya está.

    Desde el capítulo 30 barre también lo que quedó abierto sobre prospectos ya cerrados:
    los que se cerraron antes de que existiera el desenlace, y cualquiera que llegue a esa
    etapa por un camino que no pase por el servicio de cierre.
    """
    resultado = ResultadoDeRegla("cerrar_lo_cumplido")
    ids = [fila.lead_id for fila in ctx.db.query(Tarea.lead_id).filter(Tarea.estado == ABIERTA).distinct()]
    for lead_id in ids:
        lead = ctx.db.get(Lead, lead_id)
        if lead is None:
            continue
        if lead.status in _ETAPAS_SIN_SEGUIMIENTO:
            resultado.cerradas += descartar_por_desenlace(ctx.db, lead, ahora=ctx.ahora)
            continue
        resultado.cerradas += cerrar_lo_cumplido(ctx.db, lead, None, ahora=ctx.ahora)
    return resultado


# ==============================================================================
# La pasada
# ==============================================================================

# El cierre va **primero**: una tarea que ya no hay que hacer no debe contarse como abierta
# cuando las demás reglas deciden qué falta.
ORDEN_DE_LA_PASADA: Sequence[str] = ("cerrar_lo_cumplido", *ORDEN_DE_LAS_REGLAS)

_FUNCIONES: Dict[str, Callable[[Contexto], ResultadoDeRegla]] = {
    "cerrar_lo_cumplido": regla_cerrar_lo_cumplido,
    **REGLA_POR_CLAVE,
}


def ejecutar(
    db: Session,
    *,
    ahora: Optional[datetime.datetime] = None,
    reglas: Optional[Iterable[str]] = None,
) -> List[ResultadoDeRegla]:
    """
    Una pasada del motor. Cada regla en su propia transacción y con su asiento.

    No lanza: una regla que falla queda con su `error` y en la bitácora con `ERROR`, y las
    demás se aplican igual. Es el mismo criterio que los plazos de conservación, y por el
    mismo motivo: que el recordatorio de las reuniones falle un martes no puede dejar sin
    avisar a nadie de los HOT desatendidos de ese martes.
    """
    ahora = ahora or utc_now()
    ctx = Contexto(db=db, ahora=ahora, lideres=_lideres(db))
    resultados: List[ResultadoDeRegla] = []

    for clave in (ORDEN_DE_LA_PASADA if reglas is None else reglas):
        funcion = _FUNCIONES[clave]
        try:
            resultado = funcion(ctx)
            db.commit()
        except Exception as exc:  # noqa: BLE001  (se informa y sigue la siguiente regla)
            db.rollback()
            resultado = ResultadoDeRegla(clave, error=exc.__class__.__name__)
            logger.exception("La regla %s falló; las demás se aplican igual.", clave)

        resultados.append(resultado)
        anotar_en_bitacora(
            db,
            accion=ACCION_REGLA_EJECUCION,
            entidad=ENTIDAD_REGLA,
            entidad_id=clave,
            resultado=RESULTADO_ERROR if resultado.error else RESULTADO_OK,
            metadatos={**resultado.como_dict(), "etiqueta": REGLAS[clave].etiqueta if clave in REGLAS else clave},
        )

    return resultados
