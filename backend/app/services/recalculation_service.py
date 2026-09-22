"""
Recálculo masivo de scores en segundo plano.

El endpoint hacía el trabajo entero dentro de la petición: recorría TODOS los prospectos,
ejecutaba inferencia y persistía, y solo entonces respondía. Con unos pocos miles de
registros eso son minutos con la conexión abierta —el cliente agota su tiempo de espera,
nginx corta a los 60 s, y el trabajo se pierde a medias sin que nadie sepa por dónde iba—.
Además cargaba la tabla completa en memoria de una vez.

Aquí se separa en dos: la petición registra el trabajo y devuelve 202 con su identificador,
y el recorrido ocurre después, por lotes, actualizando su progreso en la base para que
pueda consultarse.

Sobre esa base, este módulo añade lo que faltaba para que el estado sea creíble:

* un **arriendo** (`lease_until`) que el ejecutor renueva en cada lote, de modo que un
  trabajo abandonado caduca solo en lugar de quedar en RUNNING para siempre;
* un **turno exclusivo** impuesto por un índice único, no por una comprobación previa,
  para que dos peticiones simultáneas no lancen dos recorridos sobre la misma tabla;
* un **barrido al arrancar** que cierra como fallidos los trabajos cuyo arriendo venció.
"""
import datetime
import logging
import os
import socket
import uuid
from typing import Callable, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.database import SessionLocal
from app.models.entities import JobStatus, Lead, ScoringJob, utc_now
from app.services.scoring_service import ScoringService

logger = logging.getLogger(__name__)

# Tamaño de lote por defecto. Acota a la vez lo que se trae a memoria y lo que abarca cada
# transacción: más grande reduce viajes a la base pero alarga los bloqueos y hace que un
# fallo tire más trabajo ya hecho.
BATCH_SIZE_POR_DEFECTO = 100
BATCH_SIZE_MAXIMO = 1000

# Valor del turno exclusivo. Es una constante y no el `job_type` para que quede explícito
# que lo que se reserva es «el derecho a recalcular», no una etiqueta descriptiva.
CLAVE_DE_TURNO = "RECALCULATE_ALL"

# Cuánto vale un arriendo desde la última señal de vida.
#
# Es una apuesta entre dos errores. Demasiado corto y un lote lento —mil prospectos con
# inferencia— vence su propio arriendo mientras trabaja, y otro proceso da por muerto a
# uno que está vivo: dos recorridos a la vez, que es justo lo que se quiere evitar.
# Demasiado largo y un contenedor caído bloquea el turno durante todo ese rato. Cinco
# minutos cubren con holgura el lote máximo (1000 prospectos) y no dejan el sistema
# atascado más de lo que tarda alguien en darse cuenta.
DURACION_DEL_ARRIENDO = datetime.timedelta(minutes=5)

# Estados en los que un trabajo ocupa el turno. Los dos terminales lo liberan.
ESTADOS_VIVOS = (JobStatus.PENDING.value, JobStatus.RUNNING.value)

MOTIVO_ARRIENDO_VENCIDO = (
    "Arriendo vencido: el proceso que ejecutaba este recálculo dejó de dar señales de "
    "vida. Se cierra como fallido para liberar el turno; vuelva a lanzarlo."
)


class RecalculoEnCurso(Exception):
    """
    Ya hay un recálculo vivo y con arriendo vigente.

    Lleva consigo el trabajo que ocupa el turno para que quien la atienda pueda decir
    *cuál* es —con su identificador y su avance— en lugar de un «inténtelo más tarde»
    que obliga a ir a buscarlo.
    """

    def __init__(self, trabajo: ScoringJob):
        self.trabajo = trabajo
        super().__init__(
            f"El recálculo {trabajo.id} sigue en curso "
            f"({trabajo.processed_leads}/{trabajo.total_leads})."
        )


def _aware(momento: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
    """
    SQLite no tiene tipo con zona y devuelve los instantes *naive*.

    Compararlos con uno *aware* es un `TypeError`, no una comparación que salga mal: el
    barrido reventaría en la suite y funcionaría en PostgreSQL, que es la peor forma de
    tener un fallo. Todo lo que se guarda está en UTC, así que reponer la zona es exacto.
    """
    if momento is None:
        return None
    if momento.tzinfo is None:
        return momento.replace(tzinfo=datetime.timezone.utc)
    return momento


def identificador_de_worker() -> str:
    """
    Quién dice tener el arriendo: host y PID.

    No sirve para decidir nada —el que decide es el plazo—, pero sin él, un trabajo
    atascado en una pila de varias instancias no dice en qué contenedor mirar.
    """
    return f"{socket.gethostname()}:{os.getpid()}"


def _arriendo_vigente(trabajo: ScoringJob, ahora: datetime.datetime) -> bool:
    """
    Un trabajo vivo cuyo plazo aún no ha vencido.

    Sin `lease_until` se considera vencido: la columna es nueva y las filas anteriores a
    la migración la tienen a NULL. Tratar el NULL como «vigente para siempre» habría hecho
    que un trabajo viejo colgado bloqueara el turno de forma permanente, que es
    exactamente el defecto que este arriendo viene a cerrar.
    """
    limite = _aware(trabajo.lease_until)
    return limite is not None and limite > ahora


def liberar_arriendos_vencidos(db: Session) -> List[str]:
    """
    Cierra como FAILED los trabajos vivos cuyo arriendo venció y libera su turno.

    Se llama en dos sitios, y los dos hacen falta:

    * al arrancar la aplicación, para que un reinicio tras una caída no deje trabajos
      fantasma en RUNNING;
    * antes de crear uno nuevo, porque si nadie reinicia nada, el barrido del arranque no
      vuelve a ocurrir y el turno quedaría ocupado por un muerto hasta la próxima vez que
      alguien reiniciara la pila.

    Devuelve los identificadores cerrados, para que quien llame pueda registrarlos.

    El filtro por plazo se hace en Python y no en la cláusula WHERE a propósito: en SQLite
    la columna es texto sin zona y el parámetro enlazado viaja con ella, de modo que la
    comparación pasa a ser lexicográfica entre formatos distintos. Son, como mucho, un
    puñado de filas: no compensa arriesgar una comparación que se porte distinto en cada
    motor por ahorrar un recorrido.
    """
    ahora = utc_now()
    candidatos = db.query(ScoringJob).filter(ScoringJob.status.in_(ESTADOS_VIVOS)).all()

    cerrados: List[str] = []
    for trabajo in candidatos:
        if _arriendo_vigente(trabajo, ahora):
            continue
        trabajo.status = JobStatus.FAILED.value
        trabajo.finished_at = ahora
        trabajo.error_message = MOTIVO_ARRIENDO_VENCIDO
        trabajo.lease_key = None
        trabajo.lease_until = None
        cerrados.append(trabajo.id)

    if cerrados:
        db.commit()
        logger.warning(
            "Recálculos cerrados por arriendo vencido (%d): %s",
            len(cerrados),
            ", ".join(cerrados),
        )
    return cerrados


def trabajo_en_curso(db: Session) -> Optional[ScoringJob]:
    """El trabajo que ocupa el turno ahora mismo, si lo hay."""
    return db.query(ScoringJob).filter(ScoringJob.lease_key == CLAVE_DE_TURNO).first()


def recuperar_trabajos_huerfanos(
    session_factory: Callable[[], Session] = SessionLocal,
) -> List[str]:
    """
    Barrido de arranque. Abre y cierra su propia sesión.

    Se ejecuta en cada worker de uvicorn, y eso está bien: la operación es idempotente
    —un trabajo ya cerrado deja de cumplir el filtro— y el coste es una consulta sobre
    una tabla que rara vez pasa de unas decenas de filas.

    Lo que NO hace es cerrar los trabajos con arriendo vigente. Reiniciar un worker no
    autoriza a dar por muerto lo que otra instancia pueda estar ejecutando; si de verdad
    murió, su plazo vencerá solo en unos minutos y lo recogerá el siguiente barrido o la
    siguiente petición.
    """
    db = session_factory()
    try:
        return liberar_arriendos_vencidos(db)
    except Exception:
        logger.exception("No se pudo barrer los recálculos huérfanos al arrancar.")
        db.rollback()
        return []
    finally:
        db.close()


def crear_trabajo_de_recalculo(
    db: Session,
    solicitado_por: Optional[str] = None,
    batch_size: int = BATCH_SIZE_POR_DEFECTO,
) -> ScoringJob:
    """
    Registra el trabajo en estado PENDING, reserva el turno y lo confirma.

    El `commit` aquí no es opcional: la respuesta 202 entrega un identificador y el cliente
    puede consultarlo de inmediato, quizá contra otro worker. Si la fila no estuviera
    confirmada, esa consulta devolvería 404 sobre un trabajo que sí se aceptó.

    Levanta `RecalculoEnCurso` si el turno está ocupado. La exclusión la impone el índice
    único sobre `lease_key`, no una consulta previa: entre «no hay ninguno activo» y el
    INSERT caben dos peticiones simultáneas, y con dos workers eso no es una hipótesis
    remota sino lo que pasa cuando alguien pulsa dos veces el botón. Comprobar antes sirve
    para dar un mensaje útil; el que impide de verdad el segundo recorrido es el motor.
    """
    batch_size = max(1, min(int(batch_size), BATCH_SIZE_MAXIMO))

    # Primero se recogen los muertos: si el turno lo ocupa un trabajo cuyo proceso ya no
    # existe, lo correcto es cerrarlo y seguir, no devolver 409 hasta que alguien reinicie.
    liberar_arriendos_vencidos(db)

    ocupado = trabajo_en_curso(db)
    if ocupado is not None:
        raise RecalculoEnCurso(ocupado)

    ahora = utc_now()
    total = db.query(Lead.id).count()

    trabajo = ScoringJob(
        id=str(uuid.uuid4()),
        job_type="RECALCULATE_ALL",
        status=JobStatus.PENDING.value,
        total_leads=total,
        processed_leads=0,
        failed_leads=0,
        batch_size=batch_size,
        requested_by=solicitado_por,
        lease_key=CLAVE_DE_TURNO,
        lease_until=ahora + DURACION_DEL_ARRIENDO,
        heartbeat_at=ahora,
        worker_id=identificador_de_worker(),
    )
    db.add(trabajo)
    try:
        db.commit()
    except IntegrityError:
        # El índice único rechazó la reserva: otro proceso ganó la carrera entre la
        # comprobación de arriba y este INSERT.
        db.rollback()
        ganador = trabajo_en_curso(db)
        if ganador is None:
            # Terminó entre el rechazo y esta consulta. Es raro pero posible, y no hay nada
            # que informar salvo que no se pudo reservar; se propaga como conflicto
            # igualmente, porque reintentar sigue siendo la respuesta correcta.
            raise RecalculoEnCurso(trabajo) from None
        raise RecalculoEnCurso(ganador) from None

    db.refresh(trabajo)
    return trabajo


def _renovar_arriendo(trabajo: ScoringJob) -> None:
    """Señal de vida: el plazo se prolonga porque hubo progreso real, no por un temporizador."""
    ahora = utc_now()
    trabajo.heartbeat_at = ahora
    trabajo.lease_until = ahora + DURACION_DEL_ARRIENDO


def _cerrar(trabajo: ScoringJob, estado: JobStatus) -> None:
    """
    Marca el final y libera el turno.

    Poner `lease_key` a NULL es lo que devuelve el turno; sin eso, un trabajo COMPLETED
    seguiría ocupándolo y el siguiente recálculo recibiría 409 para siempre. Se hace aquí,
    en un solo sitio, y no en cada rama de salida.
    """
    trabajo.status = estado.value
    trabajo.finished_at = utc_now()
    trabajo.lease_key = None
    trabajo.lease_until = None


async def ejecutar_recalculo(
    job_id: str,
    session_factory: Callable[[], Session] = SessionLocal,
) -> None:
    """
    Recorre los prospectos por lotes y actualiza el progreso del trabajo.

    Abre su PROPIA sesión y no recibe la de la petición: FastAPI cierra esa dependencia al
    devolver la respuesta, y esta función corre después, así que usarla daría un
    `DetachedInstanceError` o, peor, trabajaría sobre una conexión ya devuelta al pool.

    La paginación es por clave (`id > último`) y no por `OFFSET`: con desplazamiento, el
    motor recorre y descarta las filas anteriores en cada lote —coste cuadrático— y, si
    alguien inserta o borra mientras tanto, se saltan o repiten registros.
    """
    db = session_factory()
    try:
        trabajo = db.query(ScoringJob).filter(ScoringJob.id == job_id).first()
        if trabajo is None:
            logger.error(f"Trabajo de recálculo {job_id} no encontrado; no se ejecuta nada.")
            return

        trabajo.status = JobStatus.RUNNING.value
        trabajo.started_at = utc_now()
        trabajo.worker_id = identificador_de_worker()
        _renovar_arriendo(trabajo)
        db.commit()

        servicio = ScoringService(db)
        ultimo_id = 0
        procesados = 0
        fallidos = 0

        while True:
            lote = (
                db.query(Lead)
                .options(selectinload(Lead.activities))
                .filter(Lead.id > ultimo_id)
                .order_by(Lead.id)
                .limit(trabajo.batch_size)
                .all()
            )
            if not lote:
                break

            ultimo_id = lote[-1].id

            for lead in lote:
                try:
                    # `generate_ai_text=False`: la explicación en lenguaje natural es lo más
                    # caro del pipeline y nadie la va a leer para miles de prospectos a la vez.
                    # `commit=False`: el lote entero se confirma junto, más abajo.
                    await servicio.calculate_and_persist_score(
                        lead, generate_ai_text=False, commit=False
                    )
                    procesados += 1
                except Exception as exc:
                    # Un prospecto con datos corruptos no debe tumbar el recálculo de los
                    # otros diez mil. Se cuenta y se sigue.
                    fallidos += 1
                    logger.warning(f"Recálculo fallido para el prospecto {lead.id}: {exc}")

            trabajo.processed_leads = procesados
            trabajo.failed_leads = fallidos
            # La señal de vida viaja en el mismo commit que el progreso, y no en un hilo
            # aparte con un temporizador. Un latido independiente seguiría diciendo «vivo»
            # aunque el bucle llevara media hora bloqueado en una consulta: mediría que el
            # proceso existe, no que el trabajo avanza, que es lo que interesa saber.
            _renovar_arriendo(trabajo)
            db.commit()

        _cerrar(trabajo, JobStatus.COMPLETED)
        db.commit()
        logger.info(
            f"Recálculo {job_id} terminado: {procesados} procesados, {fallidos} fallidos."
        )

    except Exception as exc:
        logger.exception(f"El recálculo {job_id} se interrumpió: {exc}")
        try:
            db.rollback()
            trabajo = db.query(ScoringJob).filter(ScoringJob.id == job_id).first()
            if trabajo is not None:
                _cerrar(trabajo, JobStatus.FAILED)
                # Se guarda el texto de la excepción recortado: el estado del trabajo lo lee
                # quien lo lanzó, no un anónimo, pero tampoco hace falta volcar un traceback.
                trabajo.error_message = str(exc)[:2000]
                db.commit()
        except Exception:
            logger.exception(f"Además, no se pudo marcar como fallido el trabajo {job_id}.")
    finally:
        db.close()
