"""
Registro de modelos: qué artefacto se entrenó, cuándo, con qué datos y con qué resultado.

ML-3 señalaba que el `.joblib` está en `.gitignore` mientras el código depende de él. La
consecuencia práctica es que el artefacto que sirve en producción no tiene procedencia:
no hay forma de responder *«¿con qué datos se entrenó el modelo que puntuó a este
prospecto en marzo?»* más allá de la memoria de quien lo lanzó.

`metrics.json` ya guarda las métricas de la última ejecución, pero se sobrescribe. Este
registro **añade**, de modo que queda la serie: es lo que permite ver que el ROC-AUC
lleva tres entrenamientos bajando, o que el artefacto que hay desplegado no corresponde a
ninguna ejecución registrada —que es exactamente la situación que precede a un incidente
difícil de explicar—.

Se guarda en JSON y no en una base de datos a propósito: el registro tiene que poder
leerse desde el repositorio, desde el contenedor y desde el CI sin depender de que haya
una base levantada.

## La mitad que faltaba (N-15)

La versión anterior aceptaba `huella_datos` como parámetro **opcional** y nadie se lo
pasaba nunca: `train_model.py` llamaba con tres argumentos y el campo quedaba en `null`
en todas las entradas del registro. El registro declaraba una trazabilidad que no tenía.
Es la misma forma de fallo que este proyecto ya se encontró cuatro veces en las guardas
de CI —lo que documenta el arreglo se confunde con el arreglo—, aquí en su versión de
esquema: un campo previsto vale por el dato que no contiene.

Ahora la huella es **obligatoria** y el origen es **declarado**, no inferido:

* `registrar_modelo` sin huella levanta `ProcedenciaIncompleta`. Un modelo que no se
  puede rastrear hasta sus datos no llega a registrarse, igual que un modelo que no
  supera el umbral no llega a escribirse en disco.
* `origen_de_los_datos` es un argumento. Antes se deducía de `huella_datos is None`, y
  esa deducción se vuelve falsa precisamente al cumplir lo anterior: con huella
  obligatoria, un entrenamiento sintético habría quedado anotado como «realimentacion».
  La regla que rellena un hueco adivinando deja de ser inofensiva justo cuando el hueco
  se llena.
"""
import datetime
import hashlib
import json
import os
from typing import Any, Dict, Iterable, List, Optional

# Se limita el histórico para que el fichero siga siendo legible y versionable. Cien
# entrenamientos son mucho más de lo que se hace en la vida de un proyecto como este.
MAXIMO_ENTRADAS = 100

# De dónde salieron las etiquetas. No es una anotación cosmética: decide cómo se lee la
# métrica de la fila. Un ROC-AUC de 0.95 sobre `sinteticos` dice que el pipeline está
# entero; el mismo número sobre `realimentacion` diría algo sobre el negocio.
ORIGENES = ("sinteticos", "realimentacion", "mixto")


class ProcedenciaIncompleta(ValueError):
    """Se intentó registrar un modelo sin poder decir con qué datos se entrenó."""


def ruta_por_defecto() -> str:
    aqui = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(aqui, "..", "models", "registry.json"))


def huella_de_datos(df, columnas: Optional[Iterable[str]] = None) -> str:
    """
    SHA-256 del conjunto de entrenamiento: qué datos exactos produjeron este modelo.

    Dos propiedades, y las dos importan:

    * **Reproducible.** Se serializa en forma canónica —columnas ordenadas, filas
      ordenadas— para que la huella no dependa del orden en que la base devolvió las filas
      ni del orden en que el `DataFrame` colocó las columnas. Sin esto, dos ejecuciones
      sobre los mismos datos darían huellas distintas y el campo no serviría para comparar.
    * **Recalculable por terceros.** Es lo que permite que la guarda de CI la recompute
      desde el CSV y la contraste con lo registrado. Una huella que solo sabe producir
      quien la escribe no distingue un valor real de una constante.

    `columnas` acota a las variables que de verdad entraron al modelo. Incluir un
    `lead_id` o una marca de tiempo cambiaría la huella entre dos extracciones de los
    mismos datos.
    """
    if columnas is not None:
        presentes = [c for c in columnas if c in df.columns]
        df = df[presentes]
    if len(df) == 0:
        return hashlib.sha256(b"").hexdigest()
    ordenadas = sorted(df.columns)
    canonico = df[ordenadas].sort_values(ordenadas).to_csv(index=False)
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def leer_registro(ruta: Optional[str] = None) -> List[Dict[str, Any]]:
    ruta = ruta or ruta_por_defecto()
    if not os.path.exists(ruta):
        return []
    try:
        with open(ruta, encoding="utf-8") as fh:
            contenido = json.load(fh)
    except (json.JSONDecodeError, OSError):
        # Un registro corrupto no puede impedir un entrenamiento: se empieza uno nuevo.
        return []
    return contenido if isinstance(contenido, list) else []


def registrar_modelo(
    metricas: Dict[str, Any],
    filas_entrenamiento: int,
    columnas: List[str],
    huella_datos: str,
    origen: str,
    ruta: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Añade una entrada al registro y la devuelve.

    `huella_datos` y `origen` son obligatorios **por lo que costó que no lo fueran**: con
    `huella_datos` opcional, ninguna de las entradas registradas hasta hoy la llevaba.

    `extra` recoge lo propio de cada camino —la semilla del generador sintético, el
    manifiesto del dataset de realimentación— sin que el registro tenga que conocer de
    antemano todos los campos posibles.
    """
    if not huella_datos or not str(huella_datos).strip():
        raise ProcedenciaIncompleta(
            "No se registra un modelo sin la huella de sus datos de entrenamiento. Un "
            "artefacto que no se puede rastrear hasta el conjunto que lo produjo convierte "
            "cualquier metrica sorprendente en una anecdota (N-15)."
        )
    if origen not in ORIGENES:
        raise ProcedenciaIncompleta(
            f"Origen de datos desconocido: {origen!r}. Debe ser uno de {ORIGENES}. "
            "Antes se deducia de si habia huella o no, y esa deduccion pasa a ser falsa "
            "en cuanto la huella es obligatoria."
        )

    entrada = {
        "registrado_en": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "model_sha256": metricas.get("model_sha256"),
        "roc_auc": metricas.get("roc_auc"),
        "delta_sobre_heuristico": (metricas.get("lineas_base") or {}).get("delta_sobre_heuristico"),
        "passed": metricas.get("passed"),
        "filas_entrenamiento": int(filas_entrenamiento),
        "columnas": list(columnas),
        "huella_datos_sha256": str(huella_datos),
        "origen_de_los_datos": origen,
    }
    if extra:
        entrada.update(extra)

    ruta = ruta or ruta_por_defecto()
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    historico = leer_registro(ruta)
    historico.append(entrada)
    historico = historico[-MAXIMO_ENTRADAS:]
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(historico, fh, indent=2, ensure_ascii=False)
    return entrada


def entrada_de_artefacto(sha256: str, ruta: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    La entrada del registro que produjo este artefacto, o None.

    Esta es la que responde de verdad la pregunta de N-15 —«¿con qué datos se entrenó lo
    que puntuó a este prospecto?»—: `artefacto_registrado` solo dice sí o no, y saber que
    el artefacto tiene procedencia no es lo mismo que poder consultarla. Se devuelve la
    entrada más reciente: reentrenar puede dar el mismo `.joblib` bit a bit si nada
    relevante cambió, y en ese caso la última es la que describe el estado actual.
    """
    if not sha256:
        return None
    coincidencias = [e for e in leer_registro(ruta) if e.get("model_sha256") == sha256]
    return coincidencias[-1] if coincidencias else None


def artefacto_registrado(sha256: str, ruta: Optional[str] = None) -> bool:
    """
    ¿Este artefacto salió de algún entrenamiento registrado?

    Es la pregunta que conviene poder responder antes de un despliegue: un `.joblib` cuya
    huella no aparece en el registro es un fichero de procedencia desconocida, y
    `joblib.load` deserializa con pickle (A-10).
    """
    return entrada_de_artefacto(sha256, ruta) is not None
