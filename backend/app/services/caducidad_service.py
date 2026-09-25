"""
Plazo para lo que no lo tenía (capítulo 22).

Lo que pasaba
-------------
La tabla de conservación de §20.5 dejaba escritas cuatro filas sin mecanismo, y el
capítulo 21 añadió una quinta:

* `refresh_tokens` — `purgar_tokens_caducados` existía y nada la llamaba. Cada inicio de
  sesión y cada refresco dejaba una fila, con la IP del empleado, para siempre.
* `scoring_jobs` — cada recálculo masivo, con el correo de quien lo pidió.
* `crm_integration_logs` — cada entrega del CRM. Desde la Fase 15 ya no guarda el texto de
  los mensajes, pero sí correo, nombre y empresa de personas que quizá nunca llegaron a ser
  prospecto.
* `unmatched_events` — la bandeja «Sin asociar»: correo, teléfono y nombre de quien todavía
  no es prospecto. Un aviso que nadie vinculaba ni descartaba se quedaba.

Lo que hace
-----------
Cada tabla tiene un plazo en días (`CONSERVACION_*_DIAS`, con mínimo) y un criterio de qué
cuenta como vencido. Lo aplica la misma pasada diaria que resume el historial, y cada plazo
deja su asiento en la bitácora: cuántas filas, con qué corte, o que falló.

Las dos últimas filas sin plazo (capítulo 32)
----------------------------------------------
El capítulo 22 dejó dos filas de §20.5 fuera, y las dos por el mismo motivo: no eran una
tabla más.

* `audit_log` — la bitácora. Decía «sin plazo en la aplicación; decisión de operación»
  desde el capítulo 14, y crecía sin techo. Ahora tiene `CONSERVACION_AUDITORIA_DIAS`, con
  el mínimo más alto de todos (un año) y un valor por defecto de dos. Sigue siendo una
  decisión de operación: lo que cambia es que hay un mecanismo y un número escrito, en
  lugar de una nota que explicaba por qué no los había.

  Aquí la purga BORRA LA PRUEBA, que es justo lo contrario de lo que hace en las demás
  tablas, y por eso el plazo se protege por tres lados: el mínimo alto, que ningún camino
  de la API la alcanza —la bitácora no expone escritura ni borrado, y esto corre en el
  servicio de purga, no detrás de un endpoint (N-8)— y que la propia purga deja su asiento
  diciendo cuántos asientos se llevó y hasta qué fecha. Lo que se pierde queda acotado por
  escrito.

* El conjunto de realimentación — un CSV y su manifiesto, FUERA de la base. Es la única
  fila de la tabla que no se purga con un `DELETE`, y por eso este módulo tiene desde el
  capítulo 32 dos clases de plazo: `Plazo`, sobre una consulta, y `PlazoDeArchivos`, sobre
  un directorio. Las dos pasan por el mismo bucle, el mismo tratamiento de errores y el
  mismo asiento; lo único que cambia es la unidad, que el asiento nombra.

Tres decisiones que no se ven en la consulta
--------------------------------------------
* **Lo vivo no caduca.** Un token vigente no se borra por antiguo: el plazo corre desde que
  CADUCÓ. Un recálculo en curso tampoco: solo se borran los terminados (`COMPLETED`,
  `FAILED`), y desde que terminaron.
* **Un plazo que falla no detiene a los demás.** Cada uno va en su transacción. Que la
  bandeja no se pueda purgar un día no puede dejar las sesiones creciendo ese día.
* **Simular no escribe ni anota.** Cuenta lo que se borraría. La bitácora dice lo que pasó,
  no lo que se consultó que pasaría; es el mismo criterio que la retención del historial.

Lo que NO resuelve
------------------
Una reentrega del sistema de origen posterior al plazo vuelve a entrar: un aviso de la
bandeja purgado deja libre su `(fuente, identificador externo)`. Con plazos de meses es un
caso raro, y la alternativa —conservar la huella de lo purgado— sería guardar, sin plazo, un
rastro de lo que se decidió no guardar.

Y una copia del conjunto de realimentación que alguien se haya llevado a su portátil no la
alcanza ningún plazo. El que se aplica aquí es el del directorio de la instalación; lo que
sale de la máquina deja de estar bajo este mecanismo, como las copias de seguridad.
"""
import datetime
import logging
import os
import pathlib
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from sqlalchemy.orm import Query, Session

from app.core.agenda import ESTADOS_CERRADOS
from app.core.audit import (
    ACCION_CONSERVACION_PURGA,
    ENTIDAD_AUDITORIA,
    ENTIDAD_AVISO,
    ENTIDAD_EVENTO_SIN_ASOCIAR,
    ENTIDAD_REALIMENTACION,
    ENTIDAD_REGISTRO_CRM,
    ENTIDAD_SESION,
    ENTIDAD_TAREA,
    ENTIDAD_TRABAJO,
    RESULTADO_ERROR,
    RESULTADO_OK,
    registrar_evento,
)
from app.core.config import settings
from app.models.entities import (
    AuditLog,
    Aviso,
    CRMIntegrationLog,
    JobStatus,
    ScoringJob,
    Tarea,
    UnmatchedEvent,
    utc_now,
)
from app.services.session_service import consulta_tokens_caducados, purgar_tokens_caducados

logger = logging.getLogger(__name__)

ESTADOS_TERMINALES = (JobStatus.COMPLETED.value, JobStatus.FAILED.value)

# Dónde deja el extractor el conjunto de realimentación cuando se lanza desde el árbol del
# repositorio, que es el valor por defecto de su `--salida`. Se resuelve desde este archivo
# y no desde el directorio de trabajo: la purga corre como servicio, y «relativo a donde se
# lance» ya produjo una vez una base vacía en lugar de un fallo (véase `feedback_dataset`).
DIRECTORIO_DE_REALIMENTACION_POR_DEFECTO = (
    pathlib.Path(__file__).resolve().parents[3] / "ml_pipeline" / "data"
)

# Exactamente lo que nombra la fila de §20.5 —`ml_pipeline/data/leads_reales*`—, y nada
# más. El directorio se purga por PATRÓN y no entero, y el patrón es estrecho y no `*.csv`,
# por una razón concreta: en ese mismo directorio vive `leads_historical.csv`, el conjunto
# SINTÉTICO con el que se entrena el artefacto que hoy sirve. No lleva datos de nadie, es
# la entrada reproducible del modelo y no tiene plazo; un `*.csv` se lo habría llevado a los
# treinta días y habría dejado el entrenamiento sin poder repetirse.
#
# Un conjunto exportado con otro nombre (`--salida` admite cualquiera) queda fuera de este
# plazo. Es la contrapartida de no barrer el directorio entero, y se dice en §20.5.
PATRONES_DE_REALIMENTACION = ("leads_reales*.csv", "leads_reales*_manifiesto.json")


def _trabajos_vencidos(db: Session, corte: datetime.datetime) -> Query:
    # `lease_key` nulo además del estado: un trabajo que ocupa el turno no se borra aunque su
    # estado diga otra cosa. Las dos condiciones van juntas en el cierre normal; si algún día
    # dejaran de ir juntas, la duda se resuelve conservando.
    return db.query(ScoringJob).filter(
        ScoringJob.status.in_(ESTADOS_TERMINALES),
        ScoringJob.lease_key.is_(None),
        ScoringJob.finished_at.isnot(None),
        ScoringJob.finished_at < corte,
    )


def _registros_crm_vencidos(db: Session, corte: datetime.datetime) -> Query:
    return db.query(CRMIntegrationLog).filter(CRMIntegrationLog.synced_at < corte)


def _avisos_sin_asociar_vencidos(db: Session, corte: datetime.datetime) -> Query:
    # Desde que el aviso LLEGÓ, no desde que ocurrió: lo que se conserva es lo que el sistema
    # recogió, y un evento de hace un año entregado ayer tiene que dar tiempo a vincularlo.
    return db.query(UnmatchedEvent).filter(UnmatchedEvent.received_at < corte)


def _tareas_vencidas(db: Session, corte: datetime.datetime) -> Query:
    """
    Solo las **cerradas**, y desde que se cerraron.

    Una tarea abierta no caduca por vieja. Sigue siendo trabajo que nadie hizo, y borrarla
    sería hacerla desaparecer en lugar de hacerla: la bandeja quedaría limpia sin que nada
    hubiera ocurrido, que es exactamente lo contrario de lo que este capítulo existe para
    conseguir. Si una tarea de hace un año molesta, se marca hecha.
    """
    return db.query(Tarea).filter(
        Tarea.estado.in_(ESTADOS_CERRADOS),
        Tarea.cerrada_en.isnot(None),
        Tarea.cerrada_en < corte,
    )


def _avisos_vencidos(db: Session, corte: datetime.datetime) -> Query:
    """Solo los **leídos**, y desde que se leyeron: uno sin leer no ha cumplido todavía."""
    return db.query(Aviso).filter(Aviso.leido_en.isnot(None), Aviso.leido_en < corte)


def _asientos_vencidos(db: Session, corte: datetime.datetime) -> Query:
    """
    La bitácora, desde que ocurrió el asiento (capítulo 32).

    Sin excepciones y sin condición: un asiento es un hecho terminado en el momento en que
    se escribe, así que no hay aquí el equivalente de «lo vivo no caduca». La protección de
    esta tabla no está en la consulta sino en el plazo —mínimo de un año, dos por defecto— y
    en que esto no es alcanzable desde ningún endpoint.

    Tampoco se excluyen los asientos de la propia purga. Serían los únicos que no caducarían
    nunca, y acabarían siendo lo único que quedara en la tabla: un registro de que hubo
    purgas y de nada más.
    """
    return db.query(AuditLog).filter(AuditLog.occurred_at < corte)


def _borrar(consulta: Callable[[Session, datetime.datetime], Query]):
    def borrar(db: Session, dias: int, ahora: datetime.datetime) -> int:
        borradas = consulta(db, ahora - datetime.timedelta(days=dias)).delete(synchronize_session=False)
        db.commit()
        return borradas

    return borrar


@dataclass(frozen=True)
class Plazo:
    # Clave estable: la que aparece en la bitácora y en la salida del servicio.
    nombre: str
    tabla: str
    # Ajuste de `settings` que da los días.
    ajuste: str
    entidad: str
    consulta: Callable[[Session, datetime.datetime], Query]
    borrar: Callable[[Session, int, datetime.datetime], int]

    @property
    def dias(self) -> int:
        return int(getattr(settings, self.ajuste))


PLAZOS: List[Plazo] = [
    Plazo(
        "sesiones", "refresh_tokens", "CONSERVACION_SESIONES_DIAS", ENTIDAD_SESION,
        consulta_tokens_caducados,
        # La función que ya existía, no una consulta nueva: el defecto era que nadie la
        # llamaba, y reescribirla al lado habría dejado dos criterios de qué es caducado.
        lambda db, dias, ahora: purgar_tokens_caducados(db, margen_dias=dias, ahora=ahora),
    ),
    Plazo(
        "trabajos_de_recalculo", "scoring_jobs", "CONSERVACION_TRABAJOS_DIAS", ENTIDAD_TRABAJO,
        _trabajos_vencidos, _borrar(_trabajos_vencidos),
    ),
    Plazo(
        "registros_crm", "crm_integration_logs", "CONSERVACION_REGISTROS_CRM_DIAS", ENTIDAD_REGISTRO_CRM,
        _registros_crm_vencidos, _borrar(_registros_crm_vencidos),
    ),
    Plazo(
        "bandeja_sin_asociar", "unmatched_events", "CONSERVACION_SIN_ASOCIAR_DIAS", ENTIDAD_EVENTO_SIN_ASOCIAR,
        _avisos_sin_asociar_vencidos, _borrar(_avisos_sin_asociar_vencidos),
    ),
    # Capítulo 28. Las tareas y los avisos hablan de una persona concreta —cuelgan de
    # `leads`—, así que entran en la tabla de conservación como todo lo demás y no quedan
    # sin plazo, que es el defecto que el capítulo 22 existió para cerrar.
    Plazo(
        "tareas", "tareas", "CONSERVACION_TAREAS_DIAS", ENTIDAD_TAREA,
        _tareas_vencidas, _borrar(_tareas_vencidas),
    ),
    Plazo(
        "avisos", "avisos", "CONSERVACION_AVISOS_DIAS", ENTIDAD_AVISO,
        _avisos_vencidos, _borrar(_avisos_vencidos),
    ),
    # Capítulo 32. Va la última de la lista a propósito: si un plazo anterior falla, su
    # asiento de ERROR ya está escrito cuando le toca el turno a la purga de la bitácora, y
    # no se lo puede llevar por delante en la misma pasada.
    Plazo(
        "bitacora", "audit_log", "CONSERVACION_AUDITORIA_DIAS", ENTIDAD_AUDITORIA,
        _asientos_vencidos, _borrar(_asientos_vencidos),
    ),
]


# --------------------------------------------------------------------------------------
# El plazo que no es una tabla (capítulo 32)
# --------------------------------------------------------------------------------------
def directorio_de_realimentacion() -> pathlib.Path:
    """
    Dónde vive el conjunto de realimentación, según la configuración.

    `REALIMENTACION_DIR` vacío significa «donde lo deja el extractor desde el árbol del
    repositorio». En la pila el valor lo pone el volumen compartido entre el backend —que
    extrae— y el servicio que purga.
    """
    configurado = (settings.REALIMENTACION_DIR or "").strip()
    if configurado:
        return pathlib.Path(configurado)
    return DIRECTORIO_DE_REALIMENTACION_POR_DEFECTO


def archivos_vencidos(
    directorio: pathlib.Path,
    corte: datetime.datetime,
    patrones: Tuple[str, ...] = PATRONES_DE_REALIMENTACION,
) -> List[pathlib.Path]:
    """
    Los archivos del conjunto que superaron el plazo, por su fecha de modificación.

    Un directorio que no existe devuelve lista vacía y NO es un error: la instalación que
    todavía no ha extraído ningún conjunto es la normal durante los primeros meses, y un
    plazo que falla todos los días enseña a no leer el registro.

    Solo archivos regulares y solo del primer nivel. El extractor no crea subdirectorios, y
    un enlace simbólico que apuntara fuera convertiría esta purga en una forma de borrar
    cualquier cosa de la máquina escribiendo un nombre en un directorio.
    """
    if not directorio.is_dir():
        return []
    limite = corte.timestamp()
    vencidos: Dict[str, pathlib.Path] = {}
    for patron in patrones:
        for ruta in directorio.glob(patron):
            if ruta.is_symlink() or not ruta.is_file():
                continue
            if ruta.stat().st_mtime < limite:
                vencidos[ruta.name] = ruta
    return [vencidos[nombre] for nombre in sorted(vencidos)]


@dataclass(frozen=True)
class PlazoDeArchivos:
    """
    Un plazo sobre un directorio en lugar de sobre una consulta.

    Comparte con `Plazo` el nombre, el ajuste y la entidad —y por tanto el asiento y el
    tratamiento de errores— y cambia lo único que tenía que cambiar: qué se cuenta.
    """

    nombre: str
    ajuste: str
    entidad: str
    localizar: Callable[[], pathlib.Path]
    patrones: Tuple[str, ...] = PATRONES_DE_REALIMENTACION

    @property
    def dias(self) -> int:
        return int(getattr(settings, self.ajuste))


PLAZOS_DE_ARCHIVOS: List[PlazoDeArchivos] = [
    PlazoDeArchivos(
        "conjunto_de_realimentacion",
        "CONSERVACION_REALIMENTACION_DIAS",
        ENTIDAD_REALIMENTACION,
        directorio_de_realimentacion,
    ),
]


@dataclass
class ResultadoDeCaducidad:
    plazo: str
    # La tabla de la base o, cuando el plazo es de archivos, el directorio que se purgó.
    tabla: str
    dias: int
    corte: datetime.datetime
    simulado: bool
    filas: int = 0
    error: Optional[str] = None
    # «filas» o «archivos». El asiento nombra lo que contó: un `filas_borradas: 3` sobre un
    # directorio sería una cifra correcta con la etiqueta equivocada, y la bitácora se lee
    # meses después por alguien que no tiene este archivo delante.
    unidad: str = "filas"

    @property
    def es_de_archivos(self) -> bool:
        return self.unidad == "archivos"

    def como_dict(self) -> Dict[str, object]:
        return {
            "plazo": self.plazo,
            "tabla": self.tabla,
            "dias": self.dias,
            "corte": self.corte.isoformat(),
            "simulado": self.simulado,
            ("archivos_borrados" if self.es_de_archivos else "filas_borradas"): self.filas,
            "error": self.error,
        }


def _aplicar_a_archivos(
    plazo: PlazoDeArchivos, corte: datetime.datetime, simular: bool
) -> ResultadoDeCaducidad:
    """Cuenta o borra los archivos vencidos de un directorio. No toca la base."""
    directorio = plazo.localizar()
    resultado = ResultadoDeCaducidad(
        plazo.nombre, str(directorio), plazo.dias, corte, simular, unidad="archivos"
    )
    vencidos = archivos_vencidos(directorio, corte, plazo.patrones)
    if simular:
        resultado.filas = len(vencidos)
        return resultado
    for ruta in vencidos:
        # Un archivo que ya no está —otra pasada, o alguien que lo borró a mano— no es un
        # fallo del plazo: el estado al que se quería llegar es el que hay.
        try:
            os.remove(ruta)
        except FileNotFoundError:
            continue
        resultado.filas += 1
    return resultado


def aplicar_caducidad(
    db: Session,
    *,
    ahora: Optional[datetime.datetime] = None,
    simular: bool = False,
    plazos: Optional[List[Plazo]] = None,
    plazos_de_archivos: Optional[List[PlazoDeArchivos]] = None,
) -> List[ResultadoDeCaducidad]:
    """
    Aplica cada plazo en su propia transacción y devuelve lo que pasó con cada uno.

    No lanza: un plazo que falla queda en su resultado con `error` y en la bitácora con
    `ERROR`, y los demás se aplican igual. Quien llama decide qué hacer con el fallo.

    Los plazos de archivos (capítulo 32) van después de los de la base y por el mismo
    bucle, pero **solo cuando la pasada es la completa**: quien pide `plazos=[...]` está
    pidiendo esos plazos y ninguno más. Esa regla no es una comodidad de firma, es lo que
    impide que una prueba o una guarda que solo quería purgar `tareas` borre de paso los
    CSV del directorio de realimentación de quien la ejecuta. Para incluirlos hay que
    nombrarlos en `plazos_de_archivos`.
    """
    ahora = ahora or utc_now()
    if plazos_de_archivos is None:
        plazos_de_archivos = [] if plazos is not None else PLAZOS_DE_ARCHIVOS
    resultados: List[ResultadoDeCaducidad] = []

    def anotar(resultado: ResultadoDeCaducidad, entidad: str) -> None:
        resultados.append(resultado)
        if simular:
            return
        registrar_evento(
            db,
            accion=ACCION_CONSERVACION_PURGA,
            entidad=entidad,
            resultado=RESULTADO_ERROR if resultado.error else RESULTADO_OK,
            metadatos=resultado.como_dict(),
        )

    for plazo in PLAZOS if plazos is None else plazos:
        dias = plazo.dias
        corte = ahora - datetime.timedelta(days=dias)
        resultado = ResultadoDeCaducidad(plazo.nombre, plazo.tabla, dias, corte, simular)
        try:
            if simular:
                resultado.filas = plazo.consulta(db, corte).count()
            else:
                resultado.filas = plazo.borrar(db, dias, ahora)
        except Exception as exc:  # noqa: BLE001  (se informa y se sigue con el siguiente plazo)
            db.rollback()
            resultado.error = exc.__class__.__name__
            logger.exception("La purga de %s falló; los demás plazos se aplican igual.", plazo.tabla)

        anotar(resultado, plazo.entidad)

    for plazo_de_archivos in plazos_de_archivos:
        dias = plazo_de_archivos.dias
        corte = ahora - datetime.timedelta(days=dias)
        try:
            resultado = _aplicar_a_archivos(plazo_de_archivos, corte, simular)
        except OSError as exc:
            # Permisos, un volumen que no montó, un disco lleno. Se informa como cualquier
            # otro plazo y la pasada sigue; lo que ya se hubiera borrado, borrado queda.
            resultado = ResultadoDeCaducidad(
                plazo_de_archivos.nombre,
                str(plazo_de_archivos.localizar()),
                dias,
                corte,
                simular,
                unidad="archivos",
            )
            resultado.error = exc.__class__.__name__
            logger.exception(
                "La purga del conjunto de realimentación falló; los demás plazos se aplican igual."
            )

        anotar(resultado, plazo_de_archivos.entidad)

    return resultados
