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
"""
import datetime
import logging
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from sqlalchemy.orm import Query, Session

from app.core.audit import (
    ACCION_CONSERVACION_PURGA,
    ENTIDAD_EVENTO_SIN_ASOCIAR,
    ENTIDAD_REGISTRO_CRM,
    ENTIDAD_SESION,
    ENTIDAD_TRABAJO,
    RESULTADO_ERROR,
    RESULTADO_OK,
    registrar_evento,
)
from app.core.config import settings
from app.models.entities import CRMIntegrationLog, JobStatus, ScoringJob, UnmatchedEvent, utc_now
from app.services.session_service import consulta_tokens_caducados, purgar_tokens_caducados

logger = logging.getLogger(__name__)

ESTADOS_TERMINALES = (JobStatus.COMPLETED.value, JobStatus.FAILED.value)


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
]


@dataclass
class ResultadoDeCaducidad:
    plazo: str
    tabla: str
    dias: int
    corte: datetime.datetime
    simulado: bool
    filas: int = 0
    error: Optional[str] = None

    def como_dict(self) -> Dict[str, object]:
        return {
            "plazo": self.plazo,
            "tabla": self.tabla,
            "dias": self.dias,
            "corte": self.corte.isoformat(),
            "simulado": self.simulado,
            "filas_borradas": self.filas,
            "error": self.error,
        }


def aplicar_caducidad(
    db: Session,
    *,
    ahora: Optional[datetime.datetime] = None,
    simular: bool = False,
    plazos: Optional[List[Plazo]] = None,
) -> List[ResultadoDeCaducidad]:
    """
    Aplica cada plazo en su propia transacción y devuelve lo que pasó con cada uno.

    No lanza: un plazo que falla queda en su resultado con `error` y en la bitácora con
    `ERROR`, y los demás se aplican igual. Quien llama decide qué hacer con el fallo.
    """
    ahora = ahora or utc_now()
    resultados: List[ResultadoDeCaducidad] = []

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

        resultados.append(resultado)
        if not simular:
            registrar_evento(
                db,
                accion=ACCION_CONSERVACION_PURGA,
                entidad=plazo.entidad,
                resultado=RESULTADO_ERROR if resultado.error else RESULTADO_OK,
                metadatos=resultado.como_dict(),
            )

    return resultados
