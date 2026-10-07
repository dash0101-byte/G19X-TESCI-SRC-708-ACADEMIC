"""
El reparto automático: a quién le toca el prospecto que acaba de llegar (capítulo 46).

Lo que pasaba
-------------
El punto 10 de §6.2 lo decía en una línea: «hay dónde repartir, pero nada reparte solo».
H-6 estaba a medias desde la Fase 15. Existía la cartera, existía el alcance por objeto que
decide qué prospectos ve cada asesor, existía la pantalla del líder con el contador de sin
asignar… y lo único que repartía solo era un `if` dentro del scoring: si la ficha salía
`HOT` y no tenía dueño, se le daba a quien tuviera el número más alto en `capacity`.

Dos cosas de aquello no eran repartir:

* **Solo los `HOT`.** Una ficha `WARM` —la mayoría de las que llegan de una publicación— se
  quedaba sin dueño hasta que el líder abriera la matriz, la viera y eligiera a alguien. Y
  quien no tiene dueño no tiene trabajo: el motor de reglas (capítulo 28) no pregunta «¿hay
  fichas nuevas?», pregunta «¿hay algún prospecto **asignado** al que nadie haya
  contactado?». Una ficha sin asesor no produce ni tarea ni aviso, así que el sistema no se
  callaba por error: es que no había nadie de quien hablar.
* **`ORDER BY capacity DESC`.** `capacity` es la cartera **máxima** que alguien declaró en su
  ficha de cuenta, no la que tiene. Ordenar por ella entrega todos los prospectos a la misma
  persona —la del número más alto— hasta que alguien cambie el número. Con dos asesoras de
  60 y 40, los mil siguientes son de la de 60. Eso no es repartir; es ordenar por un campo.

La regla, y por qué estos dos criterios
---------------------------------------
1. **Menos cartera abierta.** Prospectos asignados de los que **todavía queda algo que
   hacer**, que es la misma definición que usa el motor de reglas (`en_seguimiento`): un
   trato ganado, uno perdido y uno descartado no son trabajo. Contar la cartera entera
   habría premiado a quien más cierra, que es exactamente lo contrario de lo que se quiere.
2. **Más tiempo sin recibir uno**, cuando hay empate en lo anterior. Sin este segundo
   criterio, el empate lo rompería el identificador y la cuenta más antigua recibiría
   siempre el primero de cada tanda.

«Más tiempo sin recibir uno» se mide por la fecha de alta del prospecto más reciente de su
cartera, y eso tiene un límite que conviene escribir: un prospecto **reasignado a mano**
lleva la fecha en que se creó, no la de la reasignación. Para el desempate, a quien el líder
acaba de traspasar una ficha de hace tres meses le sigue constando que no recibe nada desde
hace tres meses. Se acepta a sabiendas: la carga de ese traspaso ya la cuenta el criterio 1,
que es el que decide casi siempre, y la alternativa —una columna `asignado_en` escrita en
los cinco sitios que asignan— es justo la forma de regla que este proyecto lleva un día
entero quitando. Queda anotado en §6.4.

Lo que no se toca nunca
-----------------------
* Un prospecto **con asesor**. El reparto no reasigna: solo reparte lo que no tiene dueño.
* Un prospecto de una **publicación con responsable**. La publicación ya declaró de quién
  son sus prospectos. Cuenta que la publicación **tenga** responsable, no que el responsable
  siga siendo un asesor activo: cuando se dio de baja, `ciclo.asesor_para` deja la ficha sin
  asesor a propósito —«en lugar de caer en una cartera que nadie abre»— y la decisión de a
  quién pasa esa cartera es del líder, que para eso tiene el traspaso. Repartirla sola sería
  deshacer en silencio lo que la publicación declaró.
* Un prospecto que **no es un alta**. La regla corre una vez, cuando la ficha nace, y la
  prueba de que es su primera vez es que todavía no tiene ninguna instantánea en
  `score_histories`: esta misma función escribe una en cada pasada. Es lo que hace que el
  líder pueda reasignar a mano, o dejar algo sin asignar a propósito, sin que el sistema se
  lo deshaga en el siguiente recálculo.

Dónde corre, y por qué ahí
--------------------------
Dentro de `ScoringService.calculate_and_persist_score`, que es el sitio por el que hay que
pasar obligatoriamente: dar de alta ocurre en cuatro sitios —el alta del panel, la página de
interés, las integraciones y el webhook del CRM— y los cuatro acaban puntuando la ficha ahí.
Es el mismo razonamiento del capítulo 28 (una regla solo es segura donde no se puede pasar de
largo) y el mismo del alcance de cartera en el repositorio. El día que aparezca el quinto
camino, repartirá sin que nadie se acuerde de enchufarlo.

El asiento va **sin confirmar**, en la transacción de quien llama. La ingesta del CRM
confirma la ficha, su actividad, su score y su auditoría juntas o no confirma nada; un
`commit` desde aquí dejaría en la bitácora el reparto de un prospecto que el `rollback`
siguiente se llevó.

Dos altas a la vez
------------------
La decisión lee un recuento que la otra transacción está a punto de cambiar: sin nada más,
dos altas simultáneas leen «Ana tiene 0» y las dos se la dan a Ana. Por eso los candidatos se
leen con la fila bloqueada (`FOR UPDATE`) y en orden de identificador: el bloqueo serializa
las dos decisiones —la segunda cuenta después de que la primera haya confirmado— y el orden
fijo impide que dos pasadas se bloqueen entre sí. Son pocas filas y el bloqueo dura lo que
dura el alta.

La suite corre sobre SQLite, que ignora `FOR UPDATE`, así que ahí el bloqueo no se puede
ejercitar: lo que la prueba comprueba es que la sentencia lo pide de verdad, compilándola
contra el dialecto de PostgreSQL, que es el que corre en la pila.

Lo que este módulo NO hace
--------------------------
No mira el score: un prospecto frío ocupa el mismo tiempo de agenda que uno caliente, y
«pesos por score» queda fuera por escrito. No mira `capacity`, ni el sector, ni la zona. No
reasigna. No crea tareas ni avisos: de eso se ocupa el motor de reglas en su pasada, y por
el mismo camino que una asignación hecha a mano, que es justo lo que se quería.
"""
import datetime
import logging
from dataclasses import dataclass
from typing import List, Optional, Sequence

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.audit import ACCION_LEAD_REPARTO_AUTOMATICO, ENTIDAD_LEAD
from app.core.audit import registrar_evento as anotar_en_bitacora
from app.core.config import settings
from app.models.entities import Campaign, Lead, ScoreHistory, User

# La definición de «de este prospecto todavía queda algo que hacer» y la de «esta fecha
# puede compararse» salen del motor de reglas y no se copian aquí. Son la misma regla, y una
# segunda copia de ella es la clase de defecto que no falla: las dos pantallas siguen
# funcionando y dicen cosas distintas.
from app.services.motor_de_reglas import aware, en_seguimiento

logger = logging.getLogger(__name__)

# --- Qué criterio decidió. Va a la bitácora, para que el reparto se pueda discutir ---------
# Una sola cuenta donde repartir: no hubo elección que hacer.
UNICO_CANDIDATO = "unico_candidato"
# El primer criterio bastó: nadie más tenía tan poca cartera abierta.
MENOS_CARTERA_ABIERTA = "menos_cartera_abierta"
# Hubo empate en la cartera y lo rompió el tiempo sin recibir un prospecto.
MAS_TIEMPO_SIN_RECIBIR = "mas_tiempo_sin_recibir"
# Empate en las dos: dos cuentas con la misma cartera abierta y sin haber recibido nunca
# nada. Decide el identificador, que es estable. No es un criterio; es la ausencia de uno, y
# se escribe con su propio nombre para que en la bitácora se distinga de los demás.
ORDEN_ESTABLE = "orden_estable"

REGLAS_DEL_REPARTO = (
    UNICO_CANDIDATO,
    MENOS_CARTERA_ABIERTA,
    MAS_TIEMPO_SIN_RECIBIR,
    ORDEN_ESTABLE,
)

# --- Por qué un prospecto no entra en el reparto -------------------------------------------
YA_TIENE_ASESOR = "ya_tiene_asesor"
PUBLICACION_CON_RESPONSABLE = "publicacion_con_responsable"
NO_ES_UN_ALTA = "no_es_un_alta"

# Quien no ha recibido nunca un prospecto va primero en el desempate. Se le da una fecha
# anterior a cualquiera que la base pueda devolver en vez de tratar el `None` aparte: así la
# ordenación es una sola tupla y no hay dos caminos que puedan discrepar.
_NUNCA = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)


@dataclass(frozen=True)
class Reparto:
    """
    A quién le tocó, con qué criterio y entre cuántos se eligió.

    `candidatos` es lo que convierte el asiento en algo que se puede discutir: «se le dio a
    Ana» no dice nada, «se le dio a Ana entre cuatro porque tenía la cartera abierta más
    pequeña» se puede comprobar al día siguiente.
    """
    asesor_id: int
    regla: str
    candidatos: int
    cartera_abierta: int


@dataclass(frozen=True)
class _Candidato:
    asesor_id: int
    cartera_abierta: int
    ultimo_recibido: datetime.datetime


def _candidatos_bloqueados(db: Session) -> List[int]:
    """
    Las cuentas activas que atienden cartera, con la fila tomada hasta el final del alta.

    `is_sales_rep` y no el rol: `Sales_Lead` describe lo que alguien puede hacer en el
    sistema y esto describe si además se le asignan prospectos. Un administrador de TI tiene
    permisos sobre todo y no atiende a nadie; un líder comercial que además lleva cartera
    sí entra, porque la lleva.

    El bloqueo no se puede pedir en la consulta que agrupa —PostgreSQL no admite `FOR UPDATE`
    con `GROUP BY`—, así que son dos: esta toma las filas y la siguiente cuenta sobre ellas.
    """
    return [fila.id for fila in consulta_de_candidatos(db).all()]


def consulta_de_candidatos(db: Session):
    """
    La consulta que toma las filas de los candidatos, **sin ejecutarla**.

    Está separada porque el bloqueo es lo único de este módulo que la suite no puede
    ejercitar: SQLite ignora `FOR UPDATE` en silencio. Que la sentencia lo pida de verdad se
    comprueba compilándola contra el dialecto de PostgreSQL, y para eso hace falta la
    consulta y no sus resultados. La usa el reparto, de modo que lo que la prueba compila es
    exactamente lo que corre y no una copia parecida.
    """
    return (
        db.query(User.id)
        .filter(User.is_sales_rep.is_(True), User.is_active.is_(True))
        .order_by(User.id.asc())
        .with_for_update()
    )


def _carga(db: Session, asesores: Sequence[int]) -> List[_Candidato]:
    """
    Cuánta cartera abierta tiene cada candidato y cuándo recibió su último prospecto.

    Una sola consulta con `LEFT JOIN`: quien no tiene ni un prospecto tiene que salir en la
    lista con cero, y es además quien más derecho tiene al siguiente. Con un `JOIN` normal
    desaparecería justo la cuenta que hay que elegir.
    """
    abierta = func.coalesce(func.sum(case((en_seguimiento(), 1), else_=0)), 0)
    filas = (
        db.query(User.id, abierta.label("abierta"), func.max(Lead.created_at).label("ultimo"))
        .outerjoin(Lead, Lead.assigned_rep_id == User.id)
        .filter(User.id.in_(asesores))
        .group_by(User.id)
        .all()
    )
    return [
        _Candidato(
            asesor_id=fila.id,
            cartera_abierta=int(fila.abierta or 0),
            ultimo_recibido=_NUNCA if fila.ultimo is None else aware(fila.ultimo),
        )
        for fila in filas
    ]


def _orden(candidato: _Candidato) -> tuple:
    """Menos cartera abierta; a igualdad, quien lleva más tiempo sin recibir; luego el id."""
    return (candidato.cartera_abierta, candidato.ultimo_recibido, candidato.asesor_id)


def _regla_que_decidio(primero: _Candidato, segundo: Optional[_Candidato]) -> str:
    """Qué criterio rompió la elección, que es lo que hay que poder leer en la bitácora."""
    if segundo is None:
        return UNICO_CANDIDATO
    if primero.cartera_abierta != segundo.cartera_abierta:
        return MENOS_CARTERA_ABIERTA
    if primero.ultimo_recibido != segundo.ultimo_recibido:
        return MAS_TIEMPO_SIN_RECIBIR
    return ORDEN_ESTABLE


def elegir(db: Session) -> Optional[Reparto]:
    """
    A quién le toca el siguiente prospecto, o `None` si no hay ninguna cuenta donde repartir.

    `None` no es un error. Una instalación recién puesta en marcha, o un día en que la última
    asesora está de baja, deja los prospectos sin asesor y el líder los ve en la matriz y en
    su contador de sin asignar, exactamente como antes de este capítulo. Lo contrario
    —inventar un destino— los metería en la cartera de alguien que no puede atenderlos.
    """
    asesores = _candidatos_bloqueados(db)
    if not asesores:
        return None

    candidatos = sorted(_carga(db, asesores), key=_orden)
    elegido = candidatos[0]
    siguiente = candidatos[1] if len(candidatos) > 1 else None
    return Reparto(
        asesor_id=elegido.asesor_id,
        regla=_regla_que_decidio(elegido, siguiente),
        candidatos=len(candidatos),
        cartera_abierta=elegido.cartera_abierta,
    )


def por_que_no_se_reparte(db: Session, lead: Lead) -> Optional[str]:
    """Por qué este prospecto queda fuera del reparto, o `None` si entra."""
    if lead.assigned_rep_id is not None:
        return YA_TIENE_ASESOR
    if lead.campaign_id is not None:
        responsable = (
            db.query(Campaign.responsable_id).filter(Campaign.id == lead.campaign_id).scalar()
        )
        if responsable is not None:
            return PUBLICACION_CON_RESPONSABLE
    # Sin identificador todavía no hay nada en la base a su nombre: es un alta por
    # definición. Con identificador, la prueba de que no es la primera vez es que ya tiene
    # una instantánea escrita.
    if lead.id is not None:
        ya_puntuado = (
            db.query(ScoreHistory.id).filter(ScoreHistory.lead_id == lead.id).first() is not None
        )
        if ya_puntuado:
            return NO_ES_UN_ALTA
    return None


def repartir(db: Session, lead: Lead) -> Optional[Reparto]:
    """
    Asigna el prospecto si le toca, lo anota en la bitácora y devuelve lo que decidió.

    No confirma: el asiento y la asignación viven en la transacción de quien llama, que es
    quien sabe si la ficha entera se va a quedar.
    """
    if not settings.REPARTO_AUTOMATICO_ACTIVO:
        return None

    motivo = por_que_no_se_reparte(db, lead)
    if motivo is not None:
        return None

    reparto = elegir(db)
    if reparto is None:
        # Por identificador y no por correo: lo que se escribe en el registro de texto del
        # contenedor no se puede editar después, y una supresión no lo alcanzaría (R-11).
        logger.warning(
            "El prospecto %s no se pudo repartir: no hay ninguna cuenta activa que atienda "
            "cartera. Queda sin asesor, a la vista del líder.", lead.id,
        )
        return None

    lead.assigned_rep_id = reparto.asesor_id
    anotar_en_bitacora(
        db,
        accion=ACCION_LEAD_REPARTO_AUTOMATICO,
        entidad=ENTIDAD_LEAD,
        entidad_id=str(lead.id),
        # Sin actor, como la purga del historial y como el motor de reglas. El alta la pudo
        # pedir una persona, pero a quién le tocaba no lo decidió ella: un asiento con su
        # correo dentro se leería como que eligió, y eso es lo que no hay que poder confundir
        # el día que alguien discuta un reparto.
        metadatos={
            "asesor_id": reparto.asesor_id,
            "regla": reparto.regla,
            "candidatos": reparto.candidatos,
            "cartera_abierta_del_elegido": reparto.cartera_abierta,
        },
        commit=False,
    )
    logger.info(
        "Prospecto %s repartido al asesor %s entre %s candidatos (%s).",
        lead.id, reparto.asesor_id, reparto.candidatos, reparto.regla,
    )
    return reparto
