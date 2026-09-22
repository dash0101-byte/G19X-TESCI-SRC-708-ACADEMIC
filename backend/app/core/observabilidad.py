"""
Registro estructurado y correlación de peticiones.

El formato anterior era una línea de texto por evento:

    2026-09-09 11:04:22,731 - [ERROR] - app.api.v1.endpoints.leads: falló algo

Sirve mientras se lee con los ojos. Deja de servir en cuanto hay dos workers escribiendo
sobre el mismo descriptor y una traza multilínea partida entre ambos: `grep` devuelve
fragmentos, el nivel se busca por subcadena —«ERROR» aparece también dentro de los
mensajes—, y no hay forma de reunir las cinco líneas que produjo *una* petición. El
`request_id` que ya se devolvía al cliente en los 500 no estaba en ningún otro renglón,
así que el identificador que soporte recibía no llevaba a ninguna parte.

Aquí se cambian dos cosas:

* cada evento es **un objeto JSON en una línea**, con nivel, logger, módulo y, cuando
  existe, la excepción; una línea es un registro completo y `jq` puede filtrarlo;
* cada petición lleva un **`request_id`** que viaja por `contextvars`, sale en la
  cabecera `X-Request-ID` de la respuesta y aparece en **todos** los renglones que esa
  petición genere, incluidos los de librerías que no saben nada de esto.

El identificador se toma de la cabecera entrante si el cliente la manda —así se encadena
con el `request_id` de un balanceador o de otro servicio—, pero **saneado**: aceptarlo tal
cual es inyección en el registro. Un cliente que mande un salto de línea dentro de la
cabecera escribe renglones enteros en el log del servidor, y en un formato de una línea
por evento eso significa fabricar eventos falsos que nadie distingue de los reales.
"""
import contextvars
import datetime
import json
import logging
import re
import time
import uuid
from typing import Any, Dict, Optional

from app.core.config import settings
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

CABECERA_REQUEST_ID = "x-request-id"

# Etiqueta para lo que no encajó con ninguna ruta declarada. Sin esto, un escaneo de
# directorios crearía una serie de métricas por cada URL inventada.
RUTA_DESCONOCIDA = "<sin_ruta>"

# Lo que se admite de un `X-Request-ID` ajeno. Cualquier cosa fuera de esto se descarta y
# se genera uno propio: no se intenta «limpiar» el valor del cliente, porque un saneado
# parcial es una lista de casos que alguien acabará rodeando.
LONGITUD_MAXIMA_REQUEST_ID = 64
REQUEST_ID_ADMISIBLE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

# Contexto de la petición en curso. `contextvars` y no un `threading.local`: el servidor es
# asíncrono, así que dos peticiones pueden turnarse en el MISMO hilo mientras esperan a la
# base de datos, y un almacén por hilo les daría el mismo valor a las dos.
_request_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "plurione_request_id", default=None
)


def request_id_actual() -> Optional[str]:
    """El identificador de la petición que se está atendiendo, si hay una."""
    return _request_id.get()


def nuevo_request_id() -> str:
    return uuid.uuid4().hex


def _request_id_admisible(valor: Optional[str]) -> Optional[str]:
    """Devuelve el valor recibido solo si es seguro imprimirlo en una línea de registro."""
    if not valor:
        return None
    if len(valor) > LONGITUD_MAXIMA_REQUEST_ID:
        return None
    return valor if REQUEST_ID_ADMISIBLE.match(valor) else None


# ==============================================================================
# Formato de registro
# ==============================================================================

# Atributos que `logging` pone en cada `LogRecord`. Todo lo que NO esté aquí lo añadió
# quien emitió el evento con `extra={...}`, y se copia al objeto JSON: es la forma de que
# un `logger.info("...", extra={"lead_id": 12})` acabe siendo un campo consultable en
# lugar de texto interpolado dentro del mensaje.
_ATRIBUTOS_ESTANDAR = frozenset(
    {
        "args", "asctime", "created", "exc_info", "exc_text", "filename", "funcName",
        "levelname", "levelno", "lineno", "module", "msecs", "message", "msg", "name",
        "pathname", "process", "processName", "relativeCreated", "stack_info",
        "taskName", "thread", "threadName",
    }
)


class FormateadorJson(logging.Formatter):
    """
    Un objeto JSON por línea, con el `request_id` de la petición que lo provocó.

    El `request_id` se lee del contexto en el momento de formatear y no se exige que
    quien registra lo pase: la gracia es precisamente que los mensajes de SQLAlchemy, de
    uvicorn o de cualquier dependencia queden correlacionados sin tocar su código.
    """

    def format(self, record: logging.LogRecord) -> str:
        evento: Dict[str, Any] = {
            "ts": datetime.datetime.fromtimestamp(
                record.created, datetime.timezone.utc
            ).isoformat(timespec="milliseconds"),
            "nivel": record.levelname,
            "logger": record.name,
            "mensaje": record.getMessage(),
        }

        identificador = request_id_actual()
        if identificador:
            evento["request_id"] = identificador

        if record.exc_info:
            # La traza va en un campo propio y no concatenada al mensaje: así el renglón
            # sigue siendo un JSON válido de una sola línea, con los saltos escapados
            # dentro de la cadena, que es lo que hace que `jq` pueda leerlo.
            evento["excepcion"] = self.formatException(record.exc_info)
        if record.stack_info:
            evento["pila"] = self.formatStack(record.stack_info)

        for clave, valor in record.__dict__.items():
            if clave in _ATRIBUTOS_ESTANDAR or clave.startswith("_"):
                continue
            evento[clave] = _serializable(valor)

        # `default=str` es la red de seguridad: un `extra` con un objeto que no sabe
        # serializarse no debe hacer que se pierda el evento entero.
        return json.dumps(evento, ensure_ascii=False, default=str)


def _serializable(valor: Any) -> Any:
    if isinstance(valor, (str, int, float, bool)) or valor is None:
        return valor
    return str(valor)


# Loggers de uvicorn. El servidor instala sus propios manejadores al arrancar y les pone
# `propagate = False`, de modo que sin tocarlos convivirían dos formatos en el mismo
# archivo: JSON para la aplicación y texto para el acceso HTTP.
_LOGGERS_DE_UVICORN = ("uvicorn", "uvicorn.error", "uvicorn.access")


def formato_de_registro() -> str:
    """
    Resuelve `LOG_FORMAT`, cuyo valor por defecto es `auto`.

    En producción y staging manda JSON: allí los registros los lee una herramienta. En
    desarrollo manda texto, porque allí los lee una persona en una terminal y un objeto
    JSON por línea es notablemente peor para eso. Fijar el valor a mano gana siempre.
    """
    elegido = (settings.LOG_FORMAT or "auto").strip().lower()
    if elegido in ("json", "text"):
        return elegido
    return "json" if settings.is_hardened_environment else "text"


def configurar_logging() -> None:
    """
    Instala el manejador único de la aplicación. Idempotente.

    Sustituye los manejadores en lugar de añadir uno: `logging.basicConfig` no hace nada
    si el root ya tiene alguno, y llamar a esto dos veces —lo hacen las pruebas— duplicaba
    cada renglón.
    """
    if formato_de_registro() == "json":
        formateador: logging.Formatter = FormateadorJson()
    else:
        formateador = logging.Formatter(
            "%(asctime)s - [%(levelname)s] - %(name)s: %(message)s"
        )

    manejador = logging.StreamHandler()
    manejador.setFormatter(formateador)

    raiz = logging.getLogger()
    raiz.handlers = [manejador]
    raiz.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    for nombre in _LOGGERS_DE_UVICORN:
        uvicorn_logger = logging.getLogger(nombre)
        uvicorn_logger.handlers = [manejador]
        uvicorn_logger.propagate = False


# ==============================================================================
# Middleware
# ==============================================================================

class RequestIdMiddleware:
    """
    Asigna un identificador a cada petición, lo publica en el contexto y lo devuelve.

    Es ASGI puro y no `BaseHTTPMiddleware` a propósito. `BaseHTTPMiddleware` ejecuta el
    resto de la aplicación en una tarea distinta de aquella en la que corre su propio
    código; el `ContextVar` fijado antes de `call_next` sí se hereda, pero cualquier cosa
    que la aplicación escriba en el contexto NO vuelve, y el orden respecto de los
    manejadores de excepción cambia. Un middleware ASGI llano no tiene ninguna de esas
    sutilezas: fija el valor y llama a `app` en la misma tarea.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        entrante = None
        for nombre, valor in scope.get("headers", []):
            if nombre.decode("latin-1").lower() == CABECERA_REQUEST_ID:
                entrante = valor.decode("latin-1")
                break

        identificador = _request_id_admisible(entrante) or nuevo_request_id()
        testigo = _request_id.set(identificador)

        async def enviar(mensaje: Message) -> None:
            if mensaje["type"] == "http.response.start":
                # Se añade sin comprobar si ya está: la respuesta la construye esta
                # aplicación, no un tercero, y duplicar la cabecera es peor que
                # sobrescribirla porque el cliente elegiría cuál leer.
                cabeceras = list(mensaje.get("headers", []))
                cabeceras = [
                    (n, v) for n, v in cabeceras
                    if n.decode("latin-1").lower() != CABECERA_REQUEST_ID
                ]
                cabeceras.append((b"x-request-id", identificador.encode("latin-1")))
                mensaje["headers"] = cabeceras
            await send(mensaje)

        try:
            await self.app(scope, receive, enviar)
        except BaseException:
            # A propósito NO se restablece el contexto aquí.
            #
            # `ServerErrorMiddleware` —el que atiende las excepciones no controladas y
            # construye el 500— es el middleware MÁS EXTERNO de Starlette: se instala
            # antes que cualquiera de los declarados por la aplicación, así que envuelve
            # también a este. Cuando la excepción llega hasta él, un `finally` de aquí ya
            # se habría ejecutado y el manejador encontraría el contexto vacío: volvería a
            # inventarse un identificador, que es exactamente el defecto que este
            # middleware existe para cerrar.
            #
            # No restablecerlo no filtra nada entre peticiones: cada una se atiende en su
            # propia tarea, y una tarea recibe una COPIA del contexto, de modo que lo que
            # se fija aquí no sale de ella.
            raise
        else:
            _request_id.reset(testigo)


def plantillas_por_endpoint(aplicacion: Any) -> Dict[int, str]:
    """
    Mapa `id(función del endpoint) -> ruta declarada`, con los prefijos ya compuestos.

    Hay que recorrerlo en profundidad. FastAPI dejó de aplanar los routers incluidos: en
    lugar de una lista de rutas con la ruta completa, `app.routes` guarda envoltorios de
    router anidados, cada uno con su prefijo, y las rutas hoja llevan la ruta RELATIVA
    (`/{lead_id}`, no `/api/v1/leads/{lead_id}`). Recorrer un solo nivel dejaba TODA la
    API etiquetada como ruta desconocida, y las métricas seguían publicándose sin que
    nada fallara: es exactamente la clase de defecto silencioso que sale caro.

    Se apoya en atributos internos de FastAPI, así que se hace a la defensiva —`getattr`
    en todo— y hay una prueba que exige que ninguna ruta declarada quede sin traducir. Si
    una versión futura cambia la disposición, lo dirá esa prueba y no un panel vacío.
    """
    mapa: Dict[int, str] = {}
    _recolectar_plantillas(getattr(aplicacion, "routes", []), "", mapa)
    return mapa


def _recolectar_plantillas(rutas: Any, prefijo: str, mapa: Dict[int, str]) -> None:
    for ruta in rutas or []:
        # 1) Envoltorio de un router incluido: baja al router con su prefijo.
        contexto = getattr(ruta, "include_context", None)
        incluido = getattr(contexto, "included_router", None) if contexto else None
        if incluido is not None:
            _recolectar_plantillas(
                getattr(incluido, "routes", []),
                prefijo + (getattr(contexto, "prefix", "") or ""),
                mapa,
            )
            continue

        camino = getattr(ruta, "path", None)

        # 2) Montaje (ficheros estáticos): el endpoint que verá el scope es la subaplicación.
        hijas = getattr(ruta, "routes", None)
        if hijas and camino is not None:
            _recolectar_plantillas(hijas, prefijo + camino, mapa)

        # 3) Ruta hoja.
        destino = getattr(ruta, "endpoint", None) or getattr(ruta, "app", None)
        if destino is not None and camino is not None:
            mapa[id(destino)] = prefijo + camino


class RegistroDeAccesoMiddleware:
    """
    Un renglón por petición atendida, con su duración, y la medición para `/metrics`.

    Registra y mide en el mismo sitio porque los dos necesitan exactamente lo mismo: el
    método, la **plantilla** de la ruta, el código y el tiempo. Tenerlo dos veces
    garantiza que un día discrepen.

    La plantilla (`/api/v1/leads/{lead_id}`) y no la ruta concreta (`/api/v1/leads/8123`):
    con la ruta concreta, cada prospecto consultado crea una serie temporal nueva y la
    memoria del proceso —y la del Prometheus que lo recoja— crece sin tope. Es el modo
    clásico de tumbar un sistema de métricas con una instrumentación descuidada.

    La medición se toma al TERMINAR la petición, en un `finally`, para que una que reviente
    con una excepción cuente igual. Excluirla dejaría fuera de la latencia justo las
    peticiones que más interesa mirar.
    """

    def __init__(self, app: ASGIApp, aplicacion: Any = None):
        self.app = app
        # La aplicación completa, no el siguiente eslabón: hace falta su tabla de rutas
        # para traducir el endpoint que casó a la plantilla que lo declara.
        self._aplicacion = aplicacion
        self._plantillas: Optional[Dict[int, str]] = None

    def _plantilla(self, scope: Scope) -> str:
        """
        Traduce el endpoint que atendió la petición a la ruta declarada.

        Starlette 1.6 deja en el scope `endpoint` y `path_params`, pero no la ruta. Se
        podría reconstruir sustituyendo los valores de los parámetros dentro de la ruta
        concreta, y es justo lo que no se hace: en `/api/v1/leads/1`, sustituir el valor
        "1" del primer parámetro produce `/api/v{lead_id}/leads/1`, porque el "1" que
        aparece antes es el de la versión de la API. El mapa por endpoint no tiene esa
        clase de sorpresas.
        """
        endpoint = scope.get("endpoint")
        if endpoint is None:
            return RUTA_DESCONOCIDA

        if self._plantillas is None:
            self._plantillas = plantillas_por_endpoint(self._aplicacion)

        return self._plantillas.get(id(endpoint), RUTA_DESCONOCIDA)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        inicio = time.perf_counter()
        estado = {"codigo": 500}

        async def enviar(mensaje: Message) -> None:
            if mensaje["type"] == "http.response.start":
                estado["codigo"] = mensaje["status"]
            await send(mensaje)

        try:
            await self.app(scope, receive, enviar)
        finally:
            duracion = time.perf_counter() - inicio
            metodo = scope.get("method", "?")
            plantilla = self._plantilla(scope)
            # Importación diferida: `metricas` no debe cargarse al importar este módulo,
            # que a su vez lo importa `main` antes de que exista la aplicación.
            from app.core.metricas import observar_peticion

            observar_peticion(metodo, plantilla, estado["codigo"], duracion)
            logging.getLogger("plurione.acceso").info(
                "%s %s %s", metodo, plantilla, estado["codigo"],
                extra={
                    "metodo": metodo,
                    "ruta": plantilla,
                    "estado": estado["codigo"],
                    "duracion_ms": round(duracion * 1000, 2),
                },
            )


