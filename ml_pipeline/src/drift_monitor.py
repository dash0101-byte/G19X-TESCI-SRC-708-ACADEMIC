"""
Monitoreo de deriva: ¿siguen pareciéndose los prospectos de hoy a los del entrenamiento?

Un modelo no avisa cuando deja de servir. Sigue devolviendo probabilidades con la misma
confianza mientras la población cambia por debajo: una campaña nueva trae otro canal, el
equipo empieza a prospectar otro sector, el CRM cambia el catálogo de cargos. El ROC-AUC
del entrenamiento no se entera de nada de eso, porque se calculó una vez y no vuelve a
calcularse. Era la parte de ML-3 que quedaba sin cubrir.

Lo que se mide aquí es **deriva de las variables de entrada** (`data drift`), no deriva
del rendimiento. Es la única medible ahora: para lo segundo hacen falta conversiones
reales, y el bucle de realimentación tarda un ciclo comercial completo en dar su primer
dataset. Detectar que la población cambió no demuestra que el modelo haya empeorado, pero
sí dice cuándo la pregunta merece hacerse.

El índice usado es el **PSI** (*Population Stability Index*):

    PSI = Σ (observado_i − esperado_i) · ln(observado_i / esperado_i)

sobre las proporciones de cada tramo. Convención habitual en riesgo crediticio, que es
de donde viene:

    PSI < 0.10   población estable
    0.10 – 0.25  cambio apreciable, conviene mirar
    PSI > 0.25   deriva significativa

Dos cautelas que conviene decir en voz alta:

* Con pocas observaciones el PSI es ruidoso y tiende a inflarse. Por eso se exige un
  mínimo de muestras y, por debajo, se informa en vez de dictaminar.
* El perfil de referencia de este proyecto se construye sobre **datos sintéticos**, así
  que un PSI alto frente a él significa «los prospectos reales no se parecen a los datos
  con los que se entrenó», que es una afirmación cierta y esperable desde el primer día.
  No es un fallo del monitor: es la consecuencia de entrenar con datos generados, y
  medirlo lo hace explícito en vez de dejarlo como suposición.

## Que lo ejecute alguien (N-23)

Un monitor que hay que acordarse de lanzar no es un monitor: es un guion. Hasta ahora este
modulo solo se documentaba como orden manual —`docker compose exec backend python
/app/observabilidad/drift_monitor.py`—, de modo que la deriva se detectaba el dia que a
alguien se le ocurria mirar, que suele ser el dia despues de que importara.

Con `--cada` el monitor se queda corriendo y vuelve a evaluar cada tantos segundos. Es un
bucle propio y no `cron` porque la imagen del backend no lleva demonio de tareas, y meter
uno significaria un proceso mas que supervisar, un formato de registro distinto del resto
del sistema y una via de ejecucion que nadie mira. El servicio `monitor-deriva` del
`docker-compose.yml` es este bucle.

Con `--alertar` la deriva significativa deja de ser una linea mas en la salida:

* se emite un evento `[ALERTA-DERIVA]` en una linea, con las columnas y su PSI;
* se entrega a `ML_DRIFT_WEBHOOK` si esa variable esta definida;
* el proceso termina con codigo 2, para que un supervisor externo pueda enterarse.

Y se **repite lo justo**. Una alerta que se emite cada hora mientras dura una condicion que
tarda semanas en resolverse acaba filtrada por quien la recibe, y a partir de ese momento
el sistema tiene monitorizacion y no tiene aviso. Por eso hay estado: se reavisa cuando
cambia el conjunto de columnas afectadas o cuando pasa el periodo de silencio, y se avisa
tambien de la vuelta a la normalidad, que si no nadie sabe cuando termino.

## Cuando no evalua, tambien avisa (§19.9, capitulo 22)

El monitor se niega a evaluar si falta el perfil, si no se puede leer o si salio de otro
artefacto, y una evaluacion puede fallar dentro del bucle —la base caida—. Hasta el capitulo
22 eso solo quedaba en su salida: el sistema aparentaba vigilancia sin tenerla. Con
`--alertar`, la negativa sale por `ML_DRIFT_WEBHOOK` como `[DERIVA-SIN-EVALUAR]`, con la
misma regla de silencio que la deriva —un reinicio en bucle no repite el aviso— y con
`[DERIVA-EVALUA-DE-NUEVO]` cuando vuelve a evaluar. Al webhook no llega el mensaje de una
excepcion, solo su clase: el de un fallo de conexion nombra host y usuario de la base.

Uso:
    python ml_pipeline/src/drift_monitor.py --perfil ml_pipeline/models/reference_profile.json
    python ml_pipeline/src/drift_monitor.py --alertar --cada 21600
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

_AQUI = os.path.dirname(os.path.abspath(__file__))

# Este módulo se ejecuta en dos disposiciones distintas: el árbol del repositorio, donde
# el paquete `app` vive en `../../backend`, y la imagen del backend, donde vive en `/app`
# y ya está en el PYTHONPATH. La ruta relativa solo se añade si existe de verdad; en el
# contenedor no existe y añadirla dejaría una entrada muerta en `sys.path`.
_BACKEND = os.path.abspath(os.path.join(_AQUI, "..", "..", "backend"))
if os.path.isdir(_BACKEND) and _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

UMBRAL_VIGILANCIA = 0.10
UMBRAL_DERIVA = 0.25

# Por debajo de esto el PSI dice más del tamaño de la muestra que de la población.
MINIMO_OBSERVACIONES = 100

# Se reparte en deciles: suficiente resolución para ver un desplazamiento, sin tramos tan
# finos que un puñado de casos los vacíe.
TRAMOS = 10

# Evita el logaritmo de cero cuando un tramo se queda sin observaciones. El valor es el
# habitual en la literatura de PSI; cambiarlo altera la escala del índice.
EPSILON = 1e-4

# Cuanto callar antes de repetir una alerta que sigue vigente. Seis horas no es un numero
# redondo elegido al azar: es menos que una jornada —de modo que quien entra por la manana
# ve el aviso vivo— y bastante mas que el intervalo de evaluacion, que es lo que evita que
# la misma condicion produzca un aviso por ciclo. Una alerta repetida sin novedad se
# aprende a ignorar, y entonces la siguiente, la que si era nueva, tambien se ignora.
SILENCIO_ENTRE_ALERTAS = int(os.getenv("ML_DRIFT_SILENCIO_S", str(6 * 3600)))

# A donde se entrega la alerta, si hay a donde. Sin esto el aviso vive en la salida del
# contenedor, que es donde vive todo lo demas del sistema y por tanto no es un mal sitio;
# pero no despierta a nadie.
WEBHOOK = os.getenv("ML_DRIFT_WEBHOOK", "").strip()

# Cada cuanto reevaluar en modo bucle. Seis horas: la deriva de poblacion se mueve en
# semanas, y evaluarla cada minuto solo gasta base de datos.
INTERVALO_POR_DEFECTO = int(os.getenv("ML_DRIFT_INTERVALO_S", str(6 * 3600)))

def _ruta_perfil_por_defecto() -> str:
    """
    Dónde buscar el perfil de referencia sin que haya que indicarlo cada vez.

    `ML_REFERENCE_PROFILE` manda cuando está definida: dentro del contenedor los
    artefactos no están junto al código, sino en la ruta fija donde los deja la imagen.
    Es el mismo criterio que sigue `ML_MODEL_PATH` para el `.joblib`, y por la misma
    razón: una ruta relativa al árbol del repositorio no se cumple en el despliegue.
    """
    del_entorno = os.getenv("ML_REFERENCE_PROFILE", "").strip()
    if del_entorno:
        return del_entorno

    junto_al_modelo = os.getenv("ML_MODEL_PATH", "").strip()
    if junto_al_modelo:
        candidato = os.path.join(os.path.dirname(junto_al_modelo), "reference_profile.json")
        if os.path.exists(candidato):
            return candidato

    return os.path.abspath(os.path.join(_AQUI, "..", "models", "reference_profile.json"))


RUTA_PERFIL_POR_DEFECTO = _ruta_perfil_por_defecto()


def _ruta_modelo_por_defecto() -> str:
    """El artefacto que está puntuando: `ML_MODEL_PATH` en el contenedor, el del árbol fuera."""
    del_entorno = os.getenv("ML_MODEL_PATH", "").strip()
    if del_entorno:
        return del_entorno
    return os.path.abspath(os.path.join(_AQUI, "..", "models", "lead_scorer_model.joblib"))


def _sha256_de_fichero(ruta: str) -> str:
    sha = hashlib.sha256()
    with open(ruta, "rb") as fh:
        for bloque in iter(lambda: fh.read(1024 * 1024), b""):
            sha.update(bloque)
    return sha.hexdigest()


def verificar_vinculo(perfil: Dict[str, Any], ruta_modelo: str) -> Optional[str]:
    """
    Comprueba que el perfil de referencia salió del artefacto que está puntuando.

    Devuelve el problema, o `None` si corresponden. El PSI mide cuánto se aleja producción
    de la población con la que se entrenó ESTE modelo; contra el perfil de otro
    entrenamiento el número sigue saliendo, con el mismo aspecto, y deja de significar lo
    que dice. Es la clase de fallo que nadie ve, así que el monitor se niega a evaluar.

    Un perfil sin huella se rechaza también, en lugar de aceptarse por no poder comprobarlo:
    es exactamente el caso que hay que forzar a regenerar.
    """
    esperado = perfil.get("model_sha256")
    if not esperado:
        return (
            "El perfil de referencia no dice de que artefacto salio (le falta `model_sha256`). "
            "Es anterior a la Fase 13 o no lo escribio train_model.py: reentrene para "
            "regenerarlo junto al modelo."
        )
    if not os.path.exists(ruta_modelo):
        return (
            f"No existe el artefacto en {ruta_modelo}; sin el no se puede comprobar que el "
            "perfil le corresponda."
        )
    real = _sha256_de_fichero(ruta_modelo)
    if real != esperado:
        return (
            f"El perfil de referencia salio del artefacto {esperado[:12]} y el que esta "
            f"desplegado es {real[:12]}. Se compararia produccion contra la poblacion de otro "
            "modelo, y los PSI no significarian lo que dicen."
        )
    return None


def _es_numerica(serie: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(serie) and not pd.api.types.is_bool_dtype(serie)


def construir_perfil(df: pd.DataFrame, columnas: List[str]) -> Dict[str, Any]:
    """
    Resume la distribución de referencia: cortes y proporciones por columna.

    Se guarda el resumen y no los datos. Así el monitor puede ejecutarse en producción sin
    llevar consigo el conjunto de entrenamiento —que en cuanto el bucle de realimentación
    esté en marcha contendrá datos de clientes reales—.
    """
    perfil: Dict[str, Any] = {
        "generado_en": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "filas_de_referencia": int(len(df)),
        "columnas": {},
    }

    for columna in columnas:
        if columna not in df.columns:
            continue
        serie = df[columna].dropna()
        if serie.empty:
            continue

        if _es_numerica(serie):
            # Cortes por cuantiles y no por anchura fija: con variables muy asimétricas
            # —`annual_revenue`, `page_views`— la anchura fija mete casi todo en un tramo
            # y el índice deja de distinguir nada.
            cortes = sorted(set(serie.quantile([i / TRAMOS for i in range(TRAMOS + 1)]).tolist()))
            if len(cortes) < 3:
                # Variable prácticamente constante: se trata como categórica.
                conteo = serie.astype(str).value_counts(normalize=True)
                perfil["columnas"][columna] = {
                    "tipo": "categorica",
                    "proporciones": {str(k): float(v) for k, v in conteo.items()},
                }
                continue
            cortes[0] = -math.inf
            cortes[-1] = math.inf
            tramos = pd.cut(serie, bins=cortes, include_lowest=True)
            proporciones = tramos.value_counts(normalize=True, sort=False).tolist()
            perfil["columnas"][columna] = {
                "tipo": "numerica",
                "cortes": [None if math.isinf(c) else float(c) for c in cortes],
                "proporciones": [float(p) for p in proporciones],
            }
        else:
            conteo = serie.astype(str).value_counts(normalize=True)
            perfil["columnas"][columna] = {
                "tipo": "categorica",
                "proporciones": {str(k): float(v) for k, v in conteo.items()},
            }

    return perfil


def _psi(esperadas: List[float], observadas: List[float]) -> float:
    total = 0.0
    # `strict`: las dos listas deben tener el mismo numero de tramos. Si no lo tienen,
    # el indice se calcularia sobre un emparejamiento arbitrario y saldria un numero
    # plausible pero sin significado, que es peor que un error.
    for esperada, observada in zip(esperadas, observadas, strict=True):
        e = max(float(esperada), EPSILON)
        o = max(float(observada), EPSILON)
        total += (o - e) * math.log(o / e)
    return round(total, 6)


def _cortes_desde_perfil(cortes: List[Optional[float]]) -> List[float]:
    return [-math.inf if c is None and i == 0 else (math.inf if c is None else float(c))
            for i, c in enumerate(cortes)]


def psi_de_columna(serie: pd.Series, descriptor: Dict[str, Any]) -> Optional[float]:
    """PSI de una columna contra su descriptor de referencia, o None si no es comparable."""
    serie = serie.dropna()
    if serie.empty:
        return None

    if descriptor["tipo"] == "numerica":
        cortes = _cortes_desde_perfil(descriptor["cortes"])
        try:
            tramos = pd.cut(pd.to_numeric(serie, errors="coerce").dropna(), bins=cortes)
        except ValueError:
            return None
        observadas = tramos.value_counts(normalize=True, sort=False).tolist()
        esperadas = descriptor["proporciones"]
        if len(observadas) != len(esperadas):
            return None
        return _psi(esperadas, observadas)

    esperadas_mapa: Dict[str, float] = descriptor["proporciones"]
    observadas_mapa = serie.astype(str).value_counts(normalize=True).to_dict()
    # Las categorías nuevas cuentan: que aparezca un canal que no existía en el
    # entrenamiento es justo el tipo de cambio que interesa detectar.
    categorias = sorted(set(esperadas_mapa) | set(observadas_mapa))
    esperadas = [esperadas_mapa.get(c, 0.0) for c in categorias]
    observadas = [observadas_mapa.get(c, 0.0) for c in categorias]
    return _psi(esperadas, observadas)


def dictamen(psi: Optional[float]) -> str:
    if psi is None:
        return "no comparable"
    if psi > UMBRAL_DERIVA:
        return "deriva significativa"
    if psi > UMBRAL_VIGILANCIA:
        return "vigilar"
    return "estable"


def evaluar_deriva(df_produccion: pd.DataFrame, perfil: Dict[str, Any]) -> Dict[str, Any]:
    """Compara las observaciones de producción contra el perfil de referencia."""
    observaciones = int(len(df_produccion))
    por_columna: Dict[str, Any] = {}

    for columna, descriptor in perfil.get("columnas", {}).items():
        if columna not in df_produccion.columns:
            por_columna[columna] = {"psi": None, "dictamen": "ausente en produccion"}
            continue
        valor = psi_de_columna(df_produccion[columna], descriptor)
        por_columna[columna] = {"psi": valor, "dictamen": dictamen(valor)}

    con_deriva = [c for c, r in por_columna.items() if r["dictamen"] == "deriva significativa"]
    a_vigilar = [c for c, r in por_columna.items() if r["dictamen"] == "vigilar"]

    if observaciones < MINIMO_OBSERVACIONES:
        veredicto = "muestra insuficiente"
    elif con_deriva:
        veredicto = "deriva significativa"
    elif a_vigilar:
        veredicto = "vigilar"
    else:
        veredicto = "estable"

    return {
        "evaluado_en": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "observaciones": observaciones,
        "minimo_para_dictaminar": MINIMO_OBSERVACIONES,
        "filas_de_referencia": perfil.get("filas_de_referencia"),
        "veredicto": veredicto,
        "columnas_con_deriva": con_deriva,
        "columnas_a_vigilar": a_vigilar,
        "por_columna": por_columna,
        "nota": (
            "El perfil de referencia se construyo sobre datos sinteticos. Un PSI alto "
            "significa que los prospectos reales no se parecen a los datos de "
            "entrenamiento, que es cierto por construccion y no un fallo del monitor."
        ),
    }


def instantaneas_de_produccion(db=None, limite: int = 5000) -> pd.DataFrame:
    """
    Vectores de variables tal como se puntuaron, tomados de `ScoreHistory`.

    Se leen las instantáneas y no el estado actual de los prospectos por la misma razón
    que en el bucle de realimentación: el estado actual ya incorpora el avance comercial
    posterior, así que compararlo contra el entrenamiento mediría el paso del embudo, no
    la deriva de la población que entra.
    """
    from app.core.database import SessionLocal
    from app.models.entities import ScoreHistory

    propia = db is None
    db = db or SessionLocal()
    try:
        filas = (
            db.query(ScoreHistory.feature_snapshot, ScoreHistory.model_version)
            .filter(ScoreHistory.feature_snapshot.isnot(None))
            .order_by(ScoreHistory.calculated_at.desc())
            .limit(limite)
            .all()
        )
    finally:
        if propia:
            db.close()

    registros: List[Dict[str, Any]] = []
    for instantanea, version in filas:
        if not isinstance(instantanea, dict):
            continue
        registro = dict(instantanea)
        registro["_model_version"] = version
        registros.append(registro)
    return pd.DataFrame(registros)


def del_mismo_vector(df: pd.DataFrame, perfil: Dict[str, Any]) -> Tuple[pd.DataFrame, int]:
    """
    Las instantáneas tomadas con el vector del perfil, y cuántas se dejaron fuera.

    Desde el capítulo 24 `whatsapp_messages` ya no incluye LinkedIn. Una instantánea de la
    versión 1 lleva la misma columna con otro significado, y compararla contra el perfil
    nuevo daría un PSI con aspecto de deriva que solo sería un cambio de definición. Se
    descartan, y se dice cuántas: tras reentrenar, el monitor dice «muestra insuficiente»
    hasta que se acumulan puntuaciones nuevas, que es la respuesta verdadera.

    Un perfil sin versión es anterior a esta distinción y se compara con todo, como antes.
    """
    version = perfil.get("version_del_vector")
    if version is None or df.empty:
        return df, 0
    if "version_del_vector" not in df.columns:
        return df.iloc[0:0], int(len(df))
    vigentes = df["version_del_vector"] == version
    return df[vigentes], int((~vigentes).sum())


def reparto_de_motores(df: pd.DataFrame) -> Dict[str, int]:
    """
    Cuántas puntuaciones salieron de cada motor.

    Esta lectura solo es posible desde que `model_version` registra el motor real y no una
    constante de configuración: antes, todas las filas decían haber usado el modelo aunque
    el artefacto no se hubiera cargado. Un salto repentino hacia `heuristico` significa que
    el artefacto dejó de cargarse en algún despliegue, y es un incidente silencioso —el
    servicio responde 200 y las puntuaciones cambian sin que nadie lo pida—.
    """
    if "_model_version" not in df.columns or df.empty:
        return {}
    motores = df["_model_version"].fillna("desconocido").astype(str)
    motores = motores.map(lambda v: v.split("+", 1)[1] if "+" in v else v)
    return {str(k): int(v) for k, v in motores.value_counts().items()}


def formatear(informe: Dict[str, Any], motores: Dict[str, int]) -> str:
    lineas = [
        "",
        "=" * 68,
        "MONITOREO DE DERIVA DE VARIABLES",
        "=" * 68,
        f"Observaciones de produccion : {informe['observaciones']}",
        f"Filas de referencia         : {informe['filas_de_referencia']}",
        f"Veredicto                   : {informe['veredicto'].upper()}",
        "",
        f"{'Variable':<32}{'PSI':>10}   Dictamen",
        "-" * 68,
    ]
    for columna, resultado in sorted(
        informe["por_columna"].items(),
        key=lambda par: (par[1]["psi"] is None, -(par[1]["psi"] or 0.0)),
    ):
        psi = resultado["psi"]
        lineas.append(
            f"{columna:<32}{('n/d' if psi is None else f'{psi:.4f}'):>10}   {resultado['dictamen']}"
        )

    if motores:
        lineas += ["", "Motor que produjo cada puntuacion:"]
        for motor, cantidad in sorted(motores.items(), key=lambda p: -p[1]):
            lineas.append(f"  {motor:<30} {cantidad}")

    lineas += ["", f"Umbrales: vigilar > {UMBRAL_VIGILANCIA}, deriva > {UMBRAL_DERIVA}", "=" * 68, ""]
    return "\n".join(lineas)


# ============================================================================
# Alertas
# ============================================================================
def _ruta_estado_por_defecto() -> str:
    """Junto al perfil, que es el directorio que el despliegue ya monta como escribible."""
    del_entorno = os.getenv("ML_DRIFT_ESTADO", "").strip()
    if del_entorno:
        return del_entorno
    return os.path.join(os.path.dirname(_ruta_perfil_por_defecto()), "estado_deriva.json")


def _leer_estado(ruta: str) -> Dict[str, Any]:
    try:
        with open(ruta, encoding="utf-8") as fh:
            datos = json.load(fh)
        return datos if isinstance(datos, dict) else {}
    except (OSError, json.JSONDecodeError):
        # Perder el estado significa, como mucho, un aviso repetido. Impedir la evaluacion
        # por no poder leerlo seria cambiar un ruido por una ceguera.
        return {}


def _escribir_estado(ruta: str, estado: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as fh:
            json.dump(estado, fh, indent=2, ensure_ascii=False)
    except OSError as exc:
        # Se dice en voz alta: sin estado, el silencio entre alertas deja de aplicarse y
        # el aviso pasa a repetirse en cada ciclo. Callarlo convertiria una alerta util en
        # ruido sin que nadie supiera por que.
        print(f"[DERIVA] No se pudo guardar el estado en {ruta}: {exc}. "
              "Las alertas se repetiran en cada evaluacion.")


def toca_alertar(informe: Dict[str, Any], estado: Dict[str, Any], ahora: float) -> Optional[str]:
    """
    ¿Hay que emitir algo, y de qué tipo? Devuelve "deriva", "recuperacion" o None.

    Tres reglas, y las tres salen de la misma idea: avisar cuando hay novedad.

    * Si la poblacion deriva y antes no derivaba, se avisa.
    * Si sigue derivando pero **cambio el conjunto de columnas**, se avisa: no es la misma
      condicion, aunque el veredicto se llame igual.
    * Si sigue derivando con las mismas columnas, se calla hasta que pase el periodo de
      silencio.

    Y cuando vuelve a estar estable despues de haber avisado, se avisa de la vuelta. Sin
    eso, quien recibio la alerta no tiene forma de saber si la condicion sigue viva, y
    acaba teniendo que consultar el panel —que es justo lo que la alerta venia a evitar—.
    """
    derivando = informe["veredicto"] == "deriva significativa"
    columnas = sorted(informe.get("columnas_con_deriva") or [])
    antes_derivando = bool(estado.get("alertando"))

    if not derivando:
        return "recuperacion" if antes_derivando else None

    if not antes_derivando:
        return "deriva"
    if columnas != sorted(estado.get("columnas") or []):
        return "deriva"
    if ahora - float(estado.get("ultima_alerta", 0.0)) >= SILENCIO_ENTRE_ALERTAS:
        return "deriva"
    return None


def _entregar_a_webhook(evento: Dict[str, Any]) -> None:
    """
    Entrega la alerta al webhook, si lo hay.

    Un fallo de entrega NO tumba el monitor —la deriva sigue mereciendo evaluarse aunque
    el receptor este caido— pero SI se imprime. Una alerta que no llega y no dice que no
    llego es peor que no tener alertas: el sistema aparenta estar vigilado.

    La URL nunca se imprime. Suele llevar un token en la ruta, y un registro que la
    reproduce convierte el canal de avisos en una credencial filtrada.
    """
    if not WEBHOOK:
        return

    # La URL viene de una variable de entorno, asi que su esquema es entrada y no
    # constante. `urlopen` atiende tambien `file:` —y `ftp:`—, de modo que un
    # `ML_DRIFT_WEBHOOK=file:///etc/passwd` convertiria el canal de avisos en una lectura
    # del sistema de archivos del contenedor. Se restringe a los dos esquemas que un
    # receptor de alertas puede tener.
    esquema = urllib.parse.urlparse(WEBHOOK).scheme.lower()
    if esquema not in ("http", "https"):
        print(f"[DERIVA] ML_DRIFT_WEBHOOK usa el esquema {esquema!r}, que no se entrega. "
              "Solo http y https.")
        return

    cuerpo = json.dumps(evento, ensure_ascii=False).encode("utf-8")
    peticion = urllib.request.Request(  # noqa: S310  (el esquema se valida arriba)
        WEBHOOK, data=cuerpo, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(peticion, timeout=10) as respuesta:  # noqa: S310  (esquema validado arriba)
            print(f"[DERIVA] Alerta entregada al webhook (HTTP {respuesta.status}).")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"[DERIVA] NO se pudo entregar la alerta al webhook: {exc.__class__.__name__}. "
              "El aviso queda solo en esta salida.")


def emitir_alerta(informe: Dict[str, Any], tipo: str) -> Dict[str, Any]:
    """
    Emite el evento en una linea y lo entrega. Devuelve el evento.

    El formato es un objeto JSON en una linea, igual que el resto del registro del sistema
    (`app.core.observabilidad`): asi `jq` lo filtra y el agregador de turno lo entiende sin
    un analizador propio.
    """
    evento = {
        "evento": "deriva_de_variables",
        "tipo": tipo,
        "veredicto": informe["veredicto"],
        "observaciones": informe["observaciones"],
        "columnas_con_deriva": informe.get("columnas_con_deriva") or [],
        "psi": {
            c: informe["por_columna"][c]["psi"]
            for c in (informe.get("columnas_con_deriva") or [])
            if c in informe.get("por_columna", {})
        },
        "umbral_deriva": UMBRAL_DERIVA,
        "evaluado_en": informe["evaluado_en"],
    }
    etiqueta = "ALERTA-DERIVA" if tipo == "deriva" else "DERIVA-RESUELTA"
    print(f"[{etiqueta}] " + json.dumps(evento, ensure_ascii=False))
    _entregar_a_webhook(evento)
    return evento


def procesar_alertas(informe: Dict[str, Any], ruta_estado: str, ahora: Optional[float] = None) -> Optional[str]:
    """Decide, emite y persiste. Devuelve el tipo emitido, o None si no tocaba."""
    ahora = time.time() if ahora is None else ahora
    estado = _leer_estado(ruta_estado)
    tipo = toca_alertar(informe, estado, ahora)

    # Si antes se nego a evaluar, se dice que ha vuelto a hacerlo. `nuevo` no arrastra la
    # marca, de modo que el aviso de vuelta sale una sola vez.
    negativa = estado.get("sin_evaluar")
    if isinstance(negativa, dict):
        emitir_reanudacion(negativa)

    if tipo:
        emitir_alerta(informe, tipo)

    derivando = informe["veredicto"] == "deriva significativa"
    nuevo = {
        "alertando": derivando,
        "columnas": sorted(informe.get("columnas_con_deriva") or []),
        "ultima_evaluacion": ahora,
        "ultima_alerta": ahora if tipo == "deriva" else estado.get("ultima_alerta", 0.0),
        "ultimo_veredicto": informe["veredicto"],
    }
    _escribir_estado(ruta_estado, nuevo)
    return tipo


# ============================================================================
# Cuando el monitor no evalua (§19.9)
# ============================================================================
# Negarse a evaluar con un perfil ajeno es lo correcto; hacerlo en silencio, no. Un monitor
# que no vigila y solo lo dice en su propia salida deja al sistema aparentando vigilancia:
# nadie mira la salida de un contenedor del que no ha llegado ningun aviso. Por eso la
# negativa sale por el MISMO canal que la alerta de deriva, con la misma regla de silencio,
# y con aviso de vuelta cuando el monitor evalua otra vez.
MOTIVO_PERFIL_AUSENTE = "perfil_ausente"
MOTIVO_PERFIL_ILEGIBLE = "perfil_ilegible"
MOTIVO_PERFIL_AJENO = "perfil_ajeno"
MOTIVO_EVALUACION_FALLIDA = "evaluacion_fallida"


def _iso(instante: float) -> str:
    return datetime.datetime.fromtimestamp(instante, datetime.timezone.utc).isoformat()


def toca_avisar_negativa(estado: Dict[str, Any], motivo: str, ahora: float) -> bool:
    """
    Misma idea que `toca_alertar`: avisar cuando hay novedad.

    Un motivo nuevo se avisa; el mismo motivo, solo cuando ha pasado el periodo de silencio.
    El caso que lo exige es el del perfil ajeno: el proceso sale con 1, Docker lo reinicia, y
    sin memoria cada reinicio mandaria el mismo aviso hasta que alguien filtrara el canal.
    """
    previa = estado.get("sin_evaluar")
    if not isinstance(previa, dict) or previa.get("motivo") != motivo:
        return True
    return ahora - float(previa.get("ultimo_aviso", 0.0)) >= SILENCIO_ENTRE_ALERTAS


def emitir_negativa(motivo: str, detalle: str, desde: float) -> Dict[str, Any]:
    evento = {
        "evento": "monitor_de_deriva",
        "tipo": "sin_evaluar",
        "motivo": motivo,
        "detalle": detalle,
        "sin_evaluar_desde": _iso(desde),
    }
    print("[DERIVA-SIN-EVALUAR] " + json.dumps(evento, ensure_ascii=False))
    _entregar_a_webhook(evento)
    return evento


def emitir_reanudacion(negativa: Dict[str, Any]) -> Dict[str, Any]:
    evento = {
        "evento": "monitor_de_deriva",
        "tipo": "evalua_de_nuevo",
        "motivo_anterior": negativa.get("motivo"),
        "sin_evaluar_desde": _iso(float(negativa.get("desde", 0.0))),
    }
    print("[DERIVA-EVALUA-DE-NUEVO] " + json.dumps(evento, ensure_ascii=False))
    _entregar_a_webhook(evento)
    return evento


def procesar_negativa(ruta_estado: str, motivo: str, detalle: str, ahora: Optional[float] = None) -> bool:
    """Decide, emite y persiste la negativa. Devuelve si se aviso."""
    ahora = time.time() if ahora is None else ahora
    estado = _leer_estado(ruta_estado)
    previa = estado.get("sin_evaluar") if isinstance(estado.get("sin_evaluar"), dict) else {}
    # «Sin evaluar desde» cuenta desde la primera negativa seguida, aunque cambie el motivo:
    # a quien recibe el aviso le importa cuanto lleva el sistema sin vigilancia.
    desde = float(previa.get("desde", ahora)) if previa else ahora
    avisar = toca_avisar_negativa(estado, motivo, ahora)
    if avisar:
        emitir_negativa(motivo, detalle, desde)
    estado["sin_evaluar"] = {
        "motivo": motivo,
        "desde": desde,
        "ultimo_aviso": ahora if avisar else float(previa.get("ultimo_aviso", ahora)),
    }
    _escribir_estado(ruta_estado, estado)
    return avisar


# ============================================================================
# Linea de ordenes
# ============================================================================
def _una_evaluacion(args, perfil) -> int:
    df = instantaneas_de_produccion(limite=args.limite)
    if df.empty:
        print(
            "[DERIVA] No hay instantaneas de variables registradas todavia. Se acumulan a "
            "medida que se puntuan prospectos."
        )
        return 1

    motores = reparto_de_motores(df)
    df, de_otro_vector = del_mismo_vector(df, perfil)
    informe = evaluar_deriva(df, perfil)
    informe["instantaneas_de_otro_vector"] = de_otro_vector
    if de_otro_vector:
        print(f"[DERIVA] {de_otro_vector} instantaneas de otra version del vector quedan fuera.")
    informe["reparto_de_motores"] = motores
    informe["model_sha256"] = perfil.get("model_sha256")
    print(formatear(informe, motores))

    if args.salida:
        os.makedirs(os.path.dirname(os.path.abspath(args.salida)), exist_ok=True)
        with open(args.salida, "w", encoding="utf-8") as fh:
            json.dump(informe, fh, indent=2, ensure_ascii=False)
        print(f"Informe guardado en: {args.salida}")

    if not args.alertar:
        # Sin `--alertar` se informa y no se falla. La deriva es una senal para
        # investigar, no un defecto del codigo, y convertirla en un fallo de proceso solo
        # consigue que se desactive.
        return 0

    procesar_alertas(informe, args.estado)
    # Codigo 2, distinguible del 1 de «no se pudo evaluar». Un supervisor que no distinga
    # «hay deriva» de «el monitor esta roto» reacciona igual a las dos, y son cosas
    # opuestas: una pide mirar el negocio, la otra pide arreglar el monitor.
    return 2 if informe["veredicto"] == "deriva significativa" else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--perfil", default=_ruta_perfil_por_defecto(), help="Perfil de referencia.")
    parser.add_argument(
        "--modelo",
        default=_ruta_modelo_por_defecto(),
        help="Artefacto al que tiene que corresponder el perfil.",
    )
    parser.add_argument("--limite", type=int, default=5000, help="Instantáneas a leer.")
    parser.add_argument("--salida", default=None, help="Ruta donde escribir el informe JSON.")
    parser.add_argument(
        "--alertar",
        action="store_true",
        help="Emitir alerta y salir con codigo 2 cuando haya deriva significativa.",
    )
    parser.add_argument(
        "--estado",
        default=_ruta_estado_por_defecto(),
        help="Donde recordar la ultima alerta, para no repetirla en cada evaluacion.",
    )
    parser.add_argument(
        "--cada",
        type=int,
        default=0,
        help=f"Reevaluar cada N segundos en vez de una sola vez (sugerido: {INTERVALO_POR_DEFECTO}).",
    )
    args = parser.parse_args(argv)

    def _negarse(motivo: str, detalle: str) -> int:
        # Sin `--alertar` se informa y no se avisa, igual que con la deriva: una consulta
        # manual no tiene por que despertar a nadie. Con `--alertar`, que es como corre el
        # servicio de la pila, la negativa sale por el mismo canal que la alerta (§19.9).
        if args.alertar:
            procesar_negativa(args.estado, motivo, detalle)
        return 1

    if not os.path.exists(args.perfil):
        mensaje = (
            f"No existe el perfil de referencia en {args.perfil}. "
            "Se genera al entrenar: ejecute `python ml_pipeline/src/train_model.py`."
        )
        print(f"[DERIVA] {mensaje}")
        return _negarse(MOTIVO_PERFIL_AUSENTE, mensaje)

    try:
        with open(args.perfil, encoding="utf-8") as fh:
            perfil = json.load(fh)
        if not isinstance(perfil, dict):
            raise ValueError("el perfil no es un objeto JSON")
    except (OSError, ValueError) as exc:
        # Antes, un perfil truncado terminaba en una traza de Python y un reinicio en bucle
        # sin aviso. `JSONDecodeError` es un `ValueError`.
        mensaje = f"No se puede leer el perfil de referencia {args.perfil} ({exc.__class__.__name__})."
        print(f"[DERIVA] {mensaje}")
        return _negarse(MOTIVO_PERFIL_ILEGIBLE, mensaje)

    # Antes de leer una sola instantánea. En modo bucle se comprueba una vez, al arrancar:
    # el artefacto viaja en la imagen y no cambia mientras el contenedor vive. Salir con 1
    # —«no se pudo evaluar»— y no con 2: no es deriva del negocio, es un despliegue roto.
    problema = verificar_vinculo(perfil, args.modelo)
    if problema:
        print(f"[DERIVA] No se evalua. {problema}")
        return _negarse(MOTIVO_PERFIL_AJENO, problema)
    print(f"[DERIVA] Perfil y artefacto corresponden ({perfil['model_sha256'][:12]}).")

    if args.cada <= 0:
        return _una_evaluacion(args, perfil)

    # Modo bucle: es lo que hace del monitor un servicio y no un guion que hay que
    # acordarse de lanzar. Un fallo en una evaluacion no puede matar el bucle —una caida
    # momentanea de la base dejaria el sistema sin vigilancia hasta el siguiente
    # despliegue—, asi que se informa, se avisa y se espera al proximo ciclo.
    print(f"[DERIVA] Vigilando cada {args.cada} s. Perfil: {args.perfil}")
    while True:
        try:
            _una_evaluacion(args, perfil)
        except Exception as exc:  # noqa: BLE001
            print(f"[DERIVA] La evaluacion fallo ({exc.__class__.__name__}: {exc}). "
                  "Se reintenta en el proximo ciclo.")
            if args.alertar:
                # Al webhook va solo la clase de la excepcion. El mensaje de un fallo de
                # conexion nombra host, puerto y usuario de la base, y el receptor de avisos
                # suele ser un servicio de fuera; el mensaje completo queda en la salida.
                procesar_negativa(args.estado, MOTIVO_EVALUACION_FALLIDA, exc.__class__.__name__)
        time.sleep(args.cada)


if __name__ == "__main__":
    sys.exit(main())
