import logging
import os
import secrets
import sys

# Garantizar que el directorio 'backend' esté siempre en sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import paginas_publicas
from app.api.v1.api import api_router
from app.core import metricas
from app.core.config import settings
from app.core.database import engine, get_db, init_db
from app.core.observabilidad import (
    RegistroDeAccesoMiddleware,
    RequestIdMiddleware,
    configurar_logging,
    formato_de_registro,
    nuevo_request_id,
    request_id_actual,
)
from app.core.proxy import avisar_de_confianza_en_proxy
from app.core.rate_limit import avisar_de_almacen_en_memoria, limiter
from app.services.recalculation_service import (
    identificador_de_worker,
    recuperar_trabajos_huerfanos,
)

# Registro estructurado. Sustituye al `basicConfig` de una línea de texto por evento: con
# dos workers escribiendo sobre el mismo descriptor y trazas multilínea entremezcladas, ese
# formato no permitía reunir lo que produjo una misma petición. Ahora cada evento es un
# objeto JSON con su `request_id`.
configurar_logging()
logger = logging.getLogger(__name__)

# Frontend compilado (dist) para entrega productiva unificada
dist_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
assets_path = os.path.join(dist_path, "assets")


def resolve_dist_file(relative_path: str) -> Optional[str]:
    """
    Resuelve una ruta solicitada por el navegador dentro de `dist/` impidiendo path traversal.

    Devuelve la ruta absoluta del archivo únicamente si tras normalizarla (resolviendo
    `..`, enlaces simbólicos y separadores) sigue contenida en `dist_path` y existe.
    En cualquier otro caso devuelve None.
    """
    try:
        dist_root = os.path.realpath(dist_path)
        candidate = os.path.realpath(os.path.join(dist_root, relative_path))
        common = os.path.commonpath([dist_root, candidate])
    except (ValueError, OSError):
        # Rutas con bytes nulos, unidades distintas en Windows o rutas ilegales
        return None

    if os.path.normcase(common) != os.path.normcase(dist_root):
        return None
    return candidate if os.path.isfile(candidate) else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de la aplicación: inicialización y apagado."""
    logger.info("Iniciando Sistema Inteligente de Lead Scoring - PluriOne...")
    init_db()
    logger.info("Base de datos y modelos relacionales verificados.")

    avisar_de_almacen_en_memoria()
    avisar_de_confianza_en_proxy()
    _avisar_de_la_ruta_de_metricas()

    # Recálculos que quedaron a medias. Un proceso que muere a mitad del recorrido deja su
    # fila en RUNNING para siempre: quien consulta ve avanzar algo que lleva parado desde
    # el martes y, como el sistema cree que hay uno en curso, ninguno nuevo puede empezar.
    # Se cierran los que tengan el arriendo vencido; los que sigan vigentes NO se tocan,
    # porque reiniciar un worker no autoriza a dar por muerto lo que otro esté ejecutando.
    huerfanos = recuperar_trabajos_huerfanos()
    if huerfanos:
        logger.warning(
            "Recálculos huérfanos cerrados al arrancar: %s", ", ".join(huerfanos)
        )

    # Verificar disponibilidad del modelo ML al arrancar para detectar problemas temprano
    try:
        from app.adapters.azure_ml_adapter import get_ml_scoring_adapter
        ml_adapter = get_ml_scoring_adapter()
        logger.info(f"Motor de inferencia ML verificado: {type(ml_adapter).__name__} — listo.")
    except Exception as ml_exc:
        logger.warning(
            f"ADVERTENCIA CRÍTICA: El motor de scoring ML no pudo inicializarse: {ml_exc}. "
            "El sistema operará en modo degradado. Ejecuta 'python ml_pipeline/src/train_model.py' para generar el modelo."
        )

    yield
    logger.info("Cerrando aplicación y liberando recursos...")


# En producción y staging no se publica el explorador de la API. El esquema OpenAPI
# enumera cada ruta, cada parámetro y cada código de error del sistema: es un mapa
# completo de la superficie de ataque servido anónimamente, y no aporta nada a un
# despliegue real, donde quien integra ya dispone de la especificación por otra vía.
DOCS_ENABLED = not settings.is_hardened_environment

app = FastAPI(
    title=settings.APP_NAME,
    description="API REST Empresarial de Lead Scoring impulsada por Inteligencia Artificial y Machine Learning para PluriOne S.A. de C.V.",
    version="1.0.0",
    docs_url="/docs" if DOCS_ENABLED else None,
    redoc_url="/redoc" if DOCS_ENABLED else None,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if DOCS_ENABLED else None,
    lifespan=lifespan,
)

# --- Limitación de tasa ---
# El middleware aplica los límites que cada endpoint declara con @limiter.limit.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Configuración de CORS.
#
# El `or ["*"]` que había aquí convertía una lista vacía de orígenes —una variable de
# entorno sin definir, un `CORS_ORIGINS=` suelto en un `.env`— en permiso universal, y
# junto a `allow_credentials=True` eso autoriza a cualquier sitio web a leer respuestas
# autenticadas de esta API desde el navegador de un usuario con sesión abierta (A-8).
# La lista viene ya normalizada y validada por `Settings`, que aborta el arranque si
# contiene el comodín o si queda vacía en un entorno endurecido.
#
# Métodos y cabeceras también se enumeran: `["*"]` en `allow_headers` hace que el
# preflight refleje cualquier cabecera que el cliente pida, lo que anula el aviso que
# supone tener que declararlas.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# --- Observabilidad ---
#
# El orden importa y es el inverso al de estas llamadas: `add_middleware` antepone, así
# que el ÚLTIMO declarado es el más externo. Se quiere `RequestIdMiddleware` envolviéndolo
# todo, para que el identificador ya esté fijado cuando cualquier otra capa —incluido el
# manejador global de excepciones— escriba su primer renglón; y el de acceso justo por
# dentro, para que mida también lo que tardan CORS y la limitación de tasa, que es tiempo
# que el cliente espera igual.
app.add_middleware(RegistroDeAccesoMiddleware, aplicacion=app)
app.add_middleware(RequestIdMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Handler global de errores no controlados.

    El detalle de la excepción se registra únicamente en el log del servidor; al cliente
    solo se le entrega un mensaje genérico y un `request_id` con el que soporte puede
    correlacionar el incidente, evitando filtrar rutas, SQL o trazas internas.

    El identificador se toma del contexto de la petición y ya no se inventa aquí. Antes se
    generaba uno nuevo en este punto: el cliente recibía un código que no aparecía en
    ningún otro renglón del registro, de modo que el dato que soporte pedía —«deme el
    request_id»— no servía para encontrar nada. Ahora es el mismo que llevan todas las
    líneas que esa petición produjo, incluidas las de las librerías.
    """
    request_id = request_id_actual() or nuevo_request_id()
    logger.error(
        "Excepción no controlada en %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Ocurrió un error interno en el servidor de Lead Scoring.",
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id},
    )


@app.get("/", tags=["Health Check"])
def root(request: Request):
    accept = request.headers.get("accept", "")
    index_file = resolve_dist_file("index.html")
    if "text/html" in accept and index_file:
        return FileResponse(index_file)
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "status": "online",
        "environment": settings.ENVIRONMENT,
        "ai_mode": settings.AI_MODE,
        "docs_url": "/docs" if DOCS_ENABLED else None,
    }


@app.get("/health", tags=["Health Check"])
def health():
    """
    Comprobación de salud real, no declarativa.

    Antes devolvía `{"status": "healthy", "database": "connected"}` como constante: seguía
    respondiendo "sano" con la base de datos caída, de modo que el HEALTHCHECK del
    contenedor —y cualquier balanceador por delante— continuaba enviando tráfico a una
    instancia incapaz de atenderlo. Ahora ejecuta un SELECT y responde 503 si falla.
    """
    detalle = {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "database": "connected",
        "ml_engine": "unavailable",
    }

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as db_exc:
        logger.error("Health check: la base de datos no responde: %s", db_exc)
        detalle["status"] = "unhealthy"
        detalle["database"] = "unreachable"
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=detalle)

    # El motor de scoring no tumba la instancia: sin artefacto cae a su heurístico
    # calibrado y el servicio sigue siendo útil. Se informa, pero no marca "unhealthy".
    try:
        from app.adapters.azure_ml_adapter import get_ml_scoring_adapter

        adaptador = get_ml_scoring_adapter()
        detalle["ml_engine"] = type(adaptador).__name__
        detalle["ml_model_loaded"] = getattr(adaptador, "model", None) is not None
    except Exception as ml_exc:
        logger.warning("Health check: el motor de scoring no está disponible: %s", ml_exc)

    return detalle


def _metricas_publicables() -> bool:
    """
    Si `/metrics` debe responder en este despliegue.

    Sin testigo configurado la ruta queda ABIERTA en desarrollo y APAGADA en producción y
    staging. El volcado dice cuántos prospectos hay, cómo se reparten por categoría y qué
    rutas se usan: poco para quien busca entrar, bastante para un competidor, y en todo
    caso información que nadie eligió publicar. Que haya que declarar `METRICS_TOKEN` para
    encenderla en producción convierte esa publicación en una decisión y no en un descuido.
    """
    if not settings.METRICS_ENABLED:
        return False
    if settings.METRICS_TOKEN:
        return True
    return not settings.is_hardened_environment


def _avisar_de_la_ruta_de_metricas() -> None:
    """Deja dicho en el arranque en qué estado quedó `/metrics` y por qué."""
    logger.info("Formato de registro: %s (LOG_FORMAT=%s).", formato_de_registro(), settings.LOG_FORMAT)

    if not settings.METRICS_ENABLED:
        logger.info("/metrics desactivada (METRICS_ENABLED=false).")
    elif settings.METRICS_TOKEN:
        logger.info("/metrics activa y protegida con METRICS_TOKEN.")
    elif settings.is_hardened_environment:
        logger.warning(
            "/metrics NO se publica: falta METRICS_TOKEN y ENVIRONMENT='%s' es un entorno "
            "endurecido. Defina el testigo para exponerla al recolector.",
            settings.ENVIRONMENT,
        )
    else:
        logger.info("/metrics activa y SIN testigo (entorno de desarrollo).")


@app.get("/metrics", tags=["Observabilidad"], include_in_schema=False)
def metrics(request: Request, db: Session = Depends(get_db)):
    """
    Volcado en formato de exposición de Prometheus.

    No va bajo `/api/v1`: el nginx de la pila solo hace de pasarela para `/api/`, así que
    dejarla fuera de ese prefijo la mantiene inalcanzable desde el puerto público sin
    depender de una regla de denegación que alguien pueda quitar. El recolector la
    consulta contra el backend por la red interna.

    Cuando no debe publicarse responde **404** y no 403: un 403 confirma que la ruta
    existe, y con ella que hay algo que pedir.
    """
    if not _metricas_publicables():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")

    if settings.METRICS_TOKEN:
        presentado = request.headers.get("authorization", "")
        prefijo = "Bearer "
        # `compare_digest` y no `==`: la comparación de cadenas de Python corta en el
        # primer byte distinto, y ese tiempo es medible desde fuera.
        valido = presentado.startswith(prefijo) and secrets.compare_digest(
            presentado[len(prefijo):], settings.METRICS_TOKEN
        )
        if not valido:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")

    volcado = metricas.render(db=db, worker=identificador_de_worker())
    # `version=0.0.4` es lo que espera el recolector; sin él, algunos clientes suponen
    # OpenMetrics y rechazan un volcado que no lleva su marca de fin.
    return Response(
        content=volcado,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


# Montar Router v1
app.include_router(api_router, prefix=settings.API_V1_STR)

# El HTML de la página de interés y su imagen de vista previa (capítulo 27). Va **antes**
# del comodín de la SPA: si se registrara después, el comodín se quedaría con `/interes/...`
# y devolvería el índice genérico del panel, que es justo lo que esto viene a corregir.
app.include_router(paginas_publicas.router, tags=["Página de interés"])

if os.path.exists(assets_path):
    app.mount("/assets", StaticFiles(directory=assets_path), name="static_assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend_spa(full_path: str):
        # Excluir rutas de API y documentación
        if full_path.startswith("api") or full_path.startswith("docs") or full_path.startswith("redoc") or full_path.startswith("openapi.json"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        target_file = resolve_dist_file(full_path)
        if target_file:
            return FileResponse(target_file)

        # Fallback de SPA: cualquier ruta no resuelta devuelve el index del cliente
        index_file = resolve_dist_file("index.html")
        if index_file:
            return FileResponse(index_file)
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
