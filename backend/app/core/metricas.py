"""
Métricas en formato de exposición de Prometheus.

Qué se publica y de dónde sale cada cosa, porque no todo tiene la misma fiabilidad:

* **Del proceso** (peticiones, latencia, scores calculados): contadores en memoria de
  ESTE worker. La imagen arranca uvicorn con `--workers 2`, así que una recogida contra
  `/metrics` la atiende uno de los dos y devuelve *su* mitad. Es el mismo defecto que
  tenía la limitación de tasa con `memory://`, y aquí no se puede resolver igual —un
  contador en Redis por petición sería más caro que la petición—. Se hace tres cosas en
  su lugar: se etiqueta cada recogida con el worker que la atendió (`plurione_worker_info`),
  se documenta, y se explica cómo tener números exactos: una réplica por contenedor, o
  `--workers 1` con varias réplicas y que Prometheus recoja de todas.
* **De la base** (recálculos vivos, prospectos por categoría): se consultan en el momento
  de la recogida. Son exactos venga la respuesta del worker que venga, porque la base es
  común. Todo lo que puede leerse de la base se lee de la base, precisamente por eso.

No se usa `prometheus_client`. No por evitar una dependencia, sino porque su modo
multiproceso exige un directorio compartido en el que cada worker escribe sus ficheros
—incompatible con el `read_only: true` del contenedor— y hay que limpiarlo cuando un
worker muere. Para lo que aquí se publica, el formato de texto es una decena de líneas y
no compensa arrastrar ese aparato.
"""
import threading
from typing import Dict, Iterable, List, Optional, Tuple

from app.models.entities import JobStatus, Lead, ScoringJob
from sqlalchemy import func
from sqlalchemy.orm import Session

# Cortes del histograma de latencia, en segundos. Cubren desde una respuesta servida de
# memoria (5 ms) hasta el `proxy_read_timeout` de nginx (60 s): un cubo por encima del
# corte del proxy no aportaría nada, porque esa petición ya la cortó el proxy.
CUBOS_DE_LATENCIA: Tuple[float, ...] = (
    0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0
)

# Tope de combinaciones distintas de etiquetas que se guardan. La instrumentación usa la
# plantilla de la ruta, así que en condiciones normales esto no se acerca ni de lejos;
# está para que un error futuro —alguien etiquetando por identificador— degrade a una
# serie agregada en lugar de consumir la memoria del proceso.
MAXIMO_DE_SERIES = 500
ETIQUETA_DESBORDE = "<otras>"

_candado = threading.Lock()

_peticiones: Dict[Tuple[str, str, int], int] = {}
_latencia_cubos: Dict[Tuple[str, str], List[int]] = {}
_latencia_suma: Dict[Tuple[str, str], float] = {}
_latencia_total: Dict[Tuple[str, str], int] = {}
_scores: Dict[str, int] = {}


def reiniciar() -> None:
    """Vacía los contadores del proceso. Existe para que la suite parta de cero."""
    with _candado:
        _peticiones.clear()
        _latencia_cubos.clear()
        _latencia_suma.clear()
        _latencia_total.clear()
        _scores.clear()


def observar_peticion(metodo: str, ruta: str, estado: int, segundos: float) -> None:
    """Registra una petición atendida: la cuenta y la sitúa en el histograma."""
    with _candado:
        if len(_latencia_total) >= MAXIMO_DE_SERIES and (metodo, ruta) not in _latencia_total:
            ruta = ETIQUETA_DESBORDE

        clave_conteo = (metodo, ruta, int(estado))
        _peticiones[clave_conteo] = _peticiones.get(clave_conteo, 0) + 1

        clave_latencia = (metodo, ruta)
        cubos = _latencia_cubos.setdefault(clave_latencia, [0] * len(CUBOS_DE_LATENCIA))
        for indice, corte in enumerate(CUBOS_DE_LATENCIA):
            if segundos <= corte:
                cubos[indice] += 1
        _latencia_suma[clave_latencia] = _latencia_suma.get(clave_latencia, 0.0) + segundos
        _latencia_total[clave_latencia] = _latencia_total.get(clave_latencia, 0) + 1


def contar_score(categoria: str) -> None:
    """
    Un score más calculado y persistido, por categoría resultante.

    Se cuenta la categoría y no el valor: un contador guarda cuántos, no cuánto. La
    distribución de scores ya vive en la base y se publica desde ahí.
    """
    with _candado:
        if len(_scores) >= MAXIMO_DE_SERIES and categoria not in _scores:
            categoria = ETIQUETA_DESBORDE
        _scores[categoria] = _scores.get(categoria, 0) + 1


# ==============================================================================
# Exposición
# ==============================================================================

def _escapar(valor: str) -> str:
    """
    Escapa un valor de etiqueta según el formato de exposición.

    Sin esto, una ruta con una comilla rompe el renglón y Prometheus descarta la recogida
    ENTERA, no solo esa línea: se perderían también las métricas correctas del mismo
    volcado.
    """
    return valor.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _etiquetas(pares: Iterable[Tuple[str, str]]) -> str:
    dentro = ",".join(f'{nombre}="{_escapar(str(valor))}"' for nombre, valor in pares)
    return f"{{{dentro}}}" if dentro else ""


def _cabecera(lineas: List[str], nombre: str, ayuda: str, tipo: str) -> None:
    lineas.append(f"# HELP {nombre} {ayuda}")
    lineas.append(f"# TYPE {nombre} {tipo}")


def _metricas_del_proceso(lineas: List[str]) -> None:
    with _candado:
        peticiones = dict(_peticiones)
        cubos = {clave: list(valor) for clave, valor in _latencia_cubos.items()}
        suma = dict(_latencia_suma)
        total = dict(_latencia_total)
        scores = dict(_scores)

    _cabecera(
        lineas,
        "plurione_http_peticiones_total",
        "Peticiones HTTP atendidas por este worker, por metodo, ruta y codigo.",
        "counter",
    )
    for (metodo, ruta, estado), cuenta in sorted(peticiones.items()):
        etiquetas = _etiquetas(
            [("metodo", metodo), ("ruta", ruta), ("estado", str(estado))]
        )
        lineas.append(f"plurione_http_peticiones_total{etiquetas} {cuenta}")

    _cabecera(
        lineas,
        "plurione_http_duracion_segundos",
        "Latencia de las peticiones HTTP atendidas por este worker.",
        "histogram",
    )
    for clave in sorted(total):
        metodo, ruta = clave
        base = [("metodo", metodo), ("ruta", ruta)]
        acumulado = cubos.get(clave, [0] * len(CUBOS_DE_LATENCIA))
        for indice, corte in enumerate(CUBOS_DE_LATENCIA):
            etiquetas = _etiquetas(base + [("le", _formato_corte(corte))])
            lineas.append(f"plurione_http_duracion_segundos_bucket{etiquetas} {acumulado[indice]}")
        # El cubo `+Inf` es obligatorio y debe valer lo mismo que `_count`: es la
        # definición de histograma acumulado, y sin él Prometheus rechaza la métrica.
        etiquetas_inf = _etiquetas(base + [("le", "+Inf")])
        lineas.append(f"plurione_http_duracion_segundos_bucket{etiquetas_inf} {total[clave]}")
        etiquetas_base = _etiquetas(base)
        lineas.append(
            f"plurione_http_duracion_segundos_sum{etiquetas_base} {suma.get(clave, 0.0):.6f}"
        )
        lineas.append(f"plurione_http_duracion_segundos_count{etiquetas_base} {total[clave]}")

    _cabecera(
        lineas,
        "plurione_scores_calculados_total",
        "Scores calculados y persistidos por este worker, por categoria resultante.",
        "counter",
    )
    for categoria, cuenta in sorted(scores.items()):
        lineas.append(
            f"plurione_scores_calculados_total{_etiquetas([('categoria', categoria)])} {cuenta}"
        )


def _formato_corte(corte: float) -> str:
    """Prometheus compara `le` como texto: `0.005` y `0.0050` serían series distintas."""
    return repr(corte)


def _metricas_de_la_base(lineas: List[str], db: Session) -> None:
    """
    Lo que se puede leer de la base se lee de la base: sale exacto en cualquier worker.

    Si la consulta falla no se rompe la recogida entera. Un `/metrics` que devuelve 500
    porque la base está caída borra también la única señal que diría *desde cuándo* lo
    está, justo en el momento en que hace falta.
    """
    try:
        por_estado = dict(
            db.query(ScoringJob.status, func.count(ScoringJob.id))
            .group_by(ScoringJob.status)
            .all()
        )
        vivos = db.query(func.count(ScoringJob.id)).filter(
            ScoringJob.lease_key.isnot(None)
        ).scalar()
        prospectos = dict(
            db.query(Lead.score_category, func.count(Lead.id))
            .group_by(Lead.score_category)
            .all()
        )
    except Exception:
        lineas.append("# La base de datos no respondio; las metricas derivadas se omiten.")
        _cabecera(
            lineas,
            "plurione_base_de_datos_accesible",
            "1 si la consulta de metricas contra la base funciono; 0 si no.",
            "gauge",
        )
        lineas.append("plurione_base_de_datos_accesible 0")
        return

    _cabecera(
        lineas,
        "plurione_base_de_datos_accesible",
        "1 si la consulta de metricas contra la base funciono; 0 si no.",
        "gauge",
    )
    lineas.append("plurione_base_de_datos_accesible 1")

    _cabecera(
        lineas,
        "plurione_recalculos_en_curso",
        "Recalculos masivos con turno tomado ahora mismo. Vale 0 o 1 por diseno.",
        "gauge",
    )
    lineas.append(f"plurione_recalculos_en_curso {int(vivos or 0)}")

    _cabecera(
        lineas,
        "plurione_recalculos_total",
        "Trabajos de recalculo registrados, por estado.",
        "gauge",
    )
    for estado in JobStatus:
        cuenta = por_estado.get(estado.value, 0)
        lineas.append(
            f"plurione_recalculos_total{_etiquetas([('estado', estado.value)])} {cuenta}"
        )

    _cabecera(
        lineas,
        "plurione_prospectos_total",
        "Prospectos en cartera, por categoria de score.",
        "gauge",
    )
    for categoria, cuenta in sorted(prospectos.items(), key=lambda par: str(par[0])):
        nombre = getattr(categoria, "value", categoria)
        lineas.append(
            f"plurione_prospectos_total{_etiquetas([('categoria', str(nombre))])} {cuenta}"
        )


def render(db: Optional[Session] = None, worker: str = "") -> str:
    """
    Volcado completo en formato de exposición.

    Termina en salto de línea: el formato lo exige y algunos recolectores descartan la
    última muestra sin él.
    """
    lineas: List[str] = []

    _cabecera(
        lineas,
        "plurione_worker_info",
        "Que worker atendio esta recogida. Con varios workers, los contadores de proceso "
        "de arriba son SOLO los de este.",
        "gauge",
    )
    lineas.append(f"plurione_worker_info{_etiquetas([('worker', worker)])} 1")

    _metricas_del_proceso(lineas)
    if db is not None:
        _metricas_de_la_base(lineas, db)

    return "\n".join(lineas) + "\n"
