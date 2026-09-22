"""
Retención del historial de puntuación (R-3).

Lo que pasaba
-------------
`score_histories` recibe una fila por cada recálculo: al crear el prospecto, con cada
actividad, con cada recálculo masivo. Cada fila lleva el vector de variables y la
explicación generada. Nada la recortaba: el crecimiento era lineal con la actividad
comercial y sin techo, y los datos de una persona que dejó de interesar hace tres años
seguían ahí con el mismo detalle que el primer día.

Lo que hace
-----------
Conserva el detalle de los últimos `SCORE_HISTORY_RETENTION_MONTHS` meses completos más el
mes en curso. Lo anterior se agrega a `score_history_monthly` —una fila por prospecto y
mes— y se borra, en la misma transacción.

Dos filas no se purgan nunca, por antiguas que sean
---------------------------------------------------
* **La instantánea de entrada** —la más antigua con vector de variables—. Es el ejemplo de
  entrenamiento que `feedback_dataset.py` extrae cuando el prospecto llega a un desenlace.
  Borrarla no produciría un error: el extractor tomaría como «de entrada» la siguiente
  instantánea, que ya refleja el avance comercial, y el reentrenamiento aprendería con
  fuga de información sin que nada lo señalara. Para que las dos piezas no puedan
  discrepar, el criterio es UNA función, `consulta_instantanea_de_entrada`, y el extractor
  la importa de aquí.
* **La puntuación vigente** —la más reciente—. La ficha del prospecto muestra su
  explicación; un prospecto sin actividad en un año sigue teniendo un score, y ese score
  tiene que poder explicarse.

Concurrencia
------------
La pila despliega un solo servicio de purga, pero eso es una convención, no una garantía.
Si dos purgas agregaran el mismo lote, el resumen contaría dos veces las mismas filas. Por
eso se borra ANTES de sumar y se compara cuántas filas se borraron con cuántas se leyeron:
si otra purga se llevó alguna entre medias, el lote se deshace entero y se deja para la
próxima pasada. Se agrega exactamente lo que esta transacción borró.
"""
import datetime
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

from sqlalchemy import and_, func
from sqlalchemy.orm import Query, Session

from app.core.config import RETENCION_MINIMA_DEL_HISTORIAL_MESES, settings
from app.models.entities import ScoreHistory, ScoreHistoryMonthly

logger = logging.getLogger(__name__)

LOTE_POR_DEFECTO = 200

_UTC = datetime.timezone.utc


def _utc(instante: datetime.datetime) -> datetime.datetime:
    """SQLite devuelve las marcas sin zona; todas se guardaron en UTC."""
    if instante.tzinfo is None:
        return instante.replace(tzinfo=_UTC)
    return instante.astimezone(_UTC)


def primer_dia_del_mes(instante: datetime.datetime) -> datetime.date:
    momento = _utc(instante)
    return datetime.date(momento.year, momento.month, 1)


def limite_de_retencion(ahora: datetime.datetime, meses: int) -> datetime.datetime:
    """
    Primer instante que se conserva en detalle.

    Se alinea al primer día del mes y no a «hoy menos N meses»: con un corte a mitad de mes,
    cada pasada diaria agregaría un día más del mismo mes y el resumen se reescribiría
    treinta veces. Alineado, un mes se agrega de una vez, cuando vence entero.
    """
    if meses < RETENCION_MINIMA_DEL_HISTORIAL_MESES:
        raise ValueError(
            f"La retención mínima es de {RETENCION_MINIMA_DEL_HISTORIAL_MESES} meses; se pidieron {meses}."
        )
    momento = _utc(ahora)
    indice = momento.year * 12 + (momento.month - 1) - meses
    return datetime.datetime(indice // 12, indice % 12 + 1, 1, tzinfo=_UTC)


def consulta_instantanea_de_entrada(db: Session, lead_id: int) -> Query:
    """
    La instantánea con la que el prospecto entró al embudo.

    Es el criterio del bucle de realimentación, y vive aquí para que la purga y el extractor
    no puedan discrepar sobre qué fila es. El desempate por `id` hace la elección
    determinista cuando dos puntuaciones comparten instante, que ocurre en un alta con
    actividad inicial.
    """
    return (
        db.query(ScoreHistory)
        .filter(ScoreHistory.lead_id == lead_id)
        .filter(ScoreHistory.feature_snapshot.isnot(None))
        .order_by(ScoreHistory.calculated_at.asc(), ScoreHistory.id.asc())
    )


def filas_protegidas(db: Session, lead_ids: Iterable[int]) -> Set[int]:
    """
    Identificadores de las filas que la purga no toca: entrada y vigente de cada prospecto.

    Es la versión por lotes de `consulta_instantanea_de_entrada` —dos consultas para
    doscientos prospectos en lugar de cuatrocientas— y la suite comprueba que elige las
    mismas filas que la versión de uno en uno.
    """
    ids = list(lead_ids)
    if not ids:
        return set()

    primera = (
        db.query(ScoreHistory.lead_id, func.min(ScoreHistory.calculated_at).label("instante"))
        .filter(ScoreHistory.lead_id.in_(ids), ScoreHistory.feature_snapshot.isnot(None))
        .group_by(ScoreHistory.lead_id)
        .subquery()
    )
    entradas = (
        db.query(func.min(ScoreHistory.id))
        .join(
            primera,
            and_(
                ScoreHistory.lead_id == primera.c.lead_id,
                ScoreHistory.calculated_at == primera.c.instante,
            ),
        )
        .filter(ScoreHistory.feature_snapshot.isnot(None))
        .group_by(ScoreHistory.lead_id)
    )

    ultima = (
        db.query(ScoreHistory.lead_id, func.max(ScoreHistory.calculated_at).label("instante"))
        .filter(ScoreHistory.lead_id.in_(ids))
        .group_by(ScoreHistory.lead_id)
        .subquery()
    )
    vigentes = (
        db.query(func.max(ScoreHistory.id))
        .join(
            ultima,
            and_(
                ScoreHistory.lead_id == ultima.c.lead_id,
                ScoreHistory.calculated_at == ultima.c.instante,
            ),
        )
        .group_by(ScoreHistory.lead_id)
    )
    return {fila[0] for fila in entradas} | {fila[0] for fila in vigentes}


@dataclass
class ResultadoDeRetencion:
    limite: datetime.datetime
    meses: int
    simulado: bool
    prospectos: int = 0
    filas_resumidas: int = 0
    filas_protegidas: int = 0
    resumenes_nuevos: int = 0
    resumenes_fusionados: int = 0
    lotes_descartados: int = 0

    def como_dict(self) -> Dict[str, object]:
        datos = asdict(self)
        datos["limite"] = self.limite.isoformat()
        return datos


def _nuevo_resumen(lead_id: int, mes: datetime.date, filas: List) -> ScoreHistoryMonthly:
    resumen = ScoreHistoryMonthly(
        lead_id=lead_id,
        month=mes,
        scores_count=0,
        score_sum=0.0,
        score_min=filas[0].score,
        score_max=filas[0].score,
        first_score=filas[0].score,
        first_calculated_at=_utc(filas[0].calculated_at),
        last_score=filas[-1].score,
        last_category=filas[-1].score_category,
        last_calculated_at=_utc(filas[-1].calculated_at),
        category_counts={},
        model_versions=[],
    )
    _sumar(resumen, filas)
    return resumen


def _sumar(resumen: ScoreHistoryMonthly, filas: List) -> None:
    """
    Añade filas a un resumen. Vale para uno recién creado y para uno que ya existía.

    Los campos JSON se reasignan con objetos nuevos en lugar de mutarse: SQLAlchemy no
    detecta un cambio dentro de un diccionario que ya tenía cargado, y el UPDATE no saldría.
    """
    resumen.scores_count = (resumen.scores_count or 0) + len(filas)
    resumen.score_sum = (resumen.score_sum or 0.0) + sum(f.score for f in filas)
    resumen.score_min = min([resumen.score_min, *(f.score for f in filas)])
    resumen.score_max = max([resumen.score_max, *(f.score for f in filas)])

    primera, ultima = filas[0], filas[-1]
    if _utc(primera.calculated_at) < _utc(resumen.first_calculated_at):
        resumen.first_score = primera.score
        resumen.first_calculated_at = _utc(primera.calculated_at)
    if _utc(ultima.calculated_at) >= _utc(resumen.last_calculated_at):
        resumen.last_score = ultima.score
        resumen.last_category = ultima.score_category
        resumen.last_calculated_at = _utc(ultima.calculated_at)

    recuento = dict(resumen.category_counts or {})
    for fila in filas:
        clave = getattr(fila.score_category, "value", fila.score_category)
        recuento[clave] = recuento.get(clave, 0) + 1
    resumen.category_counts = recuento
    resumen.model_versions = sorted(set(resumen.model_versions or []) | {f.model_version for f in filas})


def _procesar_lote(
    db: Session,
    lead_ids: List[int],
    limite: datetime.datetime,
    resultado: ResultadoDeRetencion,
) -> None:
    protegidas = filas_protegidas(db, lead_ids)
    vencidas = (
        db.query(
            ScoreHistory.id,
            ScoreHistory.lead_id,
            ScoreHistory.score,
            ScoreHistory.score_category,
            ScoreHistory.model_version,
            ScoreHistory.calculated_at,
        )
        .filter(ScoreHistory.lead_id.in_(lead_ids), ScoreHistory.calculated_at < limite)
        .order_by(ScoreHistory.lead_id, ScoreHistory.calculated_at, ScoreHistory.id)
        .all()
    )
    candidatas = [fila for fila in vencidas if fila.id not in protegidas]
    resultado.filas_protegidas += len(vencidas) - len(candidatas)
    if not candidatas:
        return

    grupos: Dict[Tuple[int, datetime.date], List] = defaultdict(list)
    for fila in candidatas:
        grupos[(fila.lead_id, primer_dia_del_mes(fila.calculated_at))].append(fila)

    existentes = {
        (resumen.lead_id, resumen.month): resumen
        for resumen in db.query(ScoreHistoryMonthly).filter(ScoreHistoryMonthly.lead_id.in_(lead_ids))
    }

    if resultado.simulado:
        resultado.prospectos += len({fila.lead_id for fila in candidatas})
        resultado.filas_resumidas += len(candidatas)
        resultado.resumenes_fusionados += sum(1 for clave in grupos if clave in existentes)
        resultado.resumenes_nuevos += sum(1 for clave in grupos if clave not in existentes)
        return

    try:
        # Se borra por el mismo criterio con el que se leyó —y no por una lista de ids,
        # que con miles de filas rebasaría el límite de parámetros de SQLite—, excluyendo
        # las protegidas, que son a lo sumo dos por prospecto.
        consulta = db.query(ScoreHistory).filter(
            ScoreHistory.lead_id.in_(lead_ids), ScoreHistory.calculated_at < limite
        )
        if protegidas:
            consulta = consulta.filter(ScoreHistory.id.notin_(protegidas))
        borradas = consulta.delete(synchronize_session=False)

        if borradas != len(candidatas):
            db.rollback()
            resultado.lotes_descartados += 1
            logger.warning(
                "Lote de retención descartado: se leyeron %s filas vencidas y se habrían borrado %s. "
                "Otra purga o un alta tardía cambió el lote; se reintenta en la próxima pasada.",
                len(candidatas),
                borradas,
            )
            return

        for (lead_id, mes), filas in grupos.items():
            resumen = existentes.get((lead_id, mes))
            if resumen is None:
                db.add(_nuevo_resumen(lead_id, mes, filas))
                resultado.resumenes_nuevos += 1
            else:
                _sumar(resumen, filas)
                resultado.resumenes_fusionados += 1
        db.commit()
    except Exception:
        db.rollback()
        raise

    resultado.prospectos += len({fila.lead_id for fila in candidatas})
    resultado.filas_resumidas += len(candidatas)


def aplicar_retencion(
    db: Session,
    *,
    meses: Optional[int] = None,
    ahora: Optional[datetime.datetime] = None,
    lote: int = LOTE_POR_DEFECTO,
    simular: bool = False,
) -> ResultadoDeRetencion:
    """
    Resume y borra el detalle vencido. Con `simular=True` cuenta lo que haría y no escribe.

    Recorre los prospectos con filas vencidas en lotes por `lead_id` creciente. La
    paginación es por clave y no por desplazamiento: al borrar, un OFFSET se saltaría
    prospectos, porque la página siguiente se calcula sobre un conjunto que ya encogió.
    """
    meses = settings.SCORE_HISTORY_RETENTION_MONTHS if meses is None else meses
    limite = limite_de_retencion(ahora or datetime.datetime.now(_UTC), meses)
    resultado = ResultadoDeRetencion(limite=limite, meses=meses, simulado=simular)

    ultimo = 0
    while True:
        lead_ids = [
            fila[0]
            for fila in db.query(ScoreHistory.lead_id)
            .filter(ScoreHistory.calculated_at < limite, ScoreHistory.lead_id > ultimo)
            .group_by(ScoreHistory.lead_id)
            .order_by(ScoreHistory.lead_id)
            .limit(lote)
        ]
        if not lead_ids:
            break
        ultimo = lead_ids[-1]
        _procesar_lote(db, lead_ids, limite, resultado)

    return resultado
