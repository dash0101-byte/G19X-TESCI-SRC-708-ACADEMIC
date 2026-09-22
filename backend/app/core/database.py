import logging
import os
from typing import Generator, Optional

from app.core.config import settings
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

logger = logging.getLogger(__name__)

IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")
# SQLite en memoria: "sqlite://" sin ruta, o el equivalente explícito ":memory:".
IS_IN_MEMORY_SQLITE = IS_SQLITE and (
    settings.DATABASE_URL in ("sqlite://", "sqlite:///") or ":memory:" in settings.DATABASE_URL
)

# Configurar argumentos según motor de base de datos
connect_args = {"check_same_thread": False} if IS_SQLITE else {}

engine_kwargs = {
    "connect_args": connect_args,
    "echo": settings.DEBUG and not IS_SQLITE,
    "pool_pre_ping": not IS_SQLITE,
}

if IS_IN_MEMORY_SQLITE:
    # Cada conexión nueva a SQLite en memoria abre su PROPIA base de datos vacía. Con el
    # pool por defecto, la sesión que escribe y la que lee acabarían en bases distintas y
    # la configuración `DATABASE_URL=sqlite://` sería inservible. `StaticPool` mantiene una
    # única conexión compartida, que es lo que hace utilizable ese modo (lo usa la suite
    # de pruebas para no tocar ninguna base de datos real).
    engine_kwargs["poolclass"] = StaticPool

# Creación de motor SQLAlchemy
engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

# Fábrica de sesiones
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base declarativa para modelos
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Generador de dependencias de sesión de base de datos para FastAPI.
    Garantiza el cierre automático de la conexión tras atender la petición.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Identificador arbitrario pero fijo del lock consultivo que serializa la creación del
# esquema. Solo tiene que ser el mismo en todos los procesos de esta aplicación y no
# colisionar con otro uso de locks consultivos en la misma base.
SCHEMA_LOCK_ID = 0x1EAD5C04

# Ubicación de las migraciones, para comparar la revisión aplicada en la base con la
# última escrita en el repositorio. Se busca en dos sitios porque la imagen de Docker no
# replica la disposición del repositorio: allí el paquete `app` cuelga de `/app`, mientras
# que en el árbol de fuentes cuelga de `backend/`.
_RAIZ_PAQUETE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_CANDIDATOS_ALEMBIC = (
    os.path.join(_RAIZ_PAQUETE, "alembic"),                    # imagen: /app/alembic
    os.path.join(_RAIZ_PAQUETE, "backend", "alembic"),         # repositorio, desde la raíz
)


def _directorio_alembic() -> str:
    for candidato in _CANDIDATOS_ALEMBIC:
        if os.path.isdir(os.path.join(candidato, "versions")):
            return candidato
    raise RuntimeError(
        "No se encontró el directorio de migraciones de Alembic. Se buscó en: "
        + ", ".join(_CANDIDATOS_ALEMBIC)
    )


class EsquemaDesactualizado(RuntimeError):
    """La base no está en la última revisión de Alembic."""


def revision_aplicada() -> Optional[str]:
    """Revisión de Alembic que la base dice tener, o None si nunca se migró."""
    from alembic.runtime.migration import MigrationContext

    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def revision_esperada() -> Optional[str]:
    """Última revisión escrita en `backend/alembic/versions`."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config()
    config.set_main_option("script_location", _directorio_alembic())
    return ScriptDirectory.from_config(config).get_current_head()


def verificar_esquema() -> None:
    """
    Comprueba que la base esté en la última migración, y aborta si no lo está.

    Es lo que sustituye a `create_all()` en producción. Desplegar código nuevo contra una
    base sin migrar es una de las formas más comunes de caída: la aplicación arranca, sirve
    tráfico y falla con `UndefinedColumn` en la primera petición que toque la columna que
    falta —a veces horas después, y solo en un endpoint concreto—. Verificarlo al arrancar
    convierte ese fallo difuso en un mensaje único y accionable.

    No se migra automáticamente a propósito: la imagen levanta varios workers y todos
    ejecutarían la migración a la vez. Aplicar el esquema es un paso explícito del
    despliegue:  `alembic upgrade head`.
    """
    aplicada = revision_aplicada()
    esperada = revision_esperada()

    if aplicada == esperada:
        logger.info(f"Esquema de base de datos en la revisión {aplicada}.")
        return

    if aplicada is None:
        detalle = (
            "la base no tiene ninguna migración aplicada. Si es una base nueva, ejecute "
            "`alembic upgrade head`; si viene de una versión anterior a Alembic y ya "
            "tiene las tablas, márquela con `alembic stamp head` tras comprobar que el "
            "esquema coincide."
        )
    else:
        detalle = (
            f"la base está en la revisión {aplicada} y el código espera {esperada}. "
            "Ejecute `alembic upgrade head` antes de desplegar."
        )

    raise EsquemaDesactualizado(f"Esquema de base de datos desactualizado: {detalle}")


def init_db() -> None:
    """
    Prepara el esquema de base de datos según el entorno.

    En producción y staging **no se crea nada**: el esquema lo gobierna Alembic y aquí solo
    se verifica que esté al día. `create_all()` no borra ni altera lo existente, así que
    parecía inofensivo, pero es incapaz de evacuar un cambio: renombrar una columna, cambiar
    un tipo o añadir un índice sobre datos ya escritos no lo ve. Dejarlo en producción daba
    la falsa impresión de que el esquema se mantenía solo, mientras la base se quedaba en la
    forma con la que se creó el primer día.

    Fuera de esos entornos sí se crea directamente: para las pruebas —SQLite en memoria, que
    nace vacía en cada ejecución— y para el arranque local, migrar sería una ceremonia sin
    contrapartida.

    `create_all(checkfirst=True)` mira qué existe y luego lo crea, y entre esas dos cosas no
    hay atomicidad. Cuando varios procesos arrancan a la vez, dos entran, ambos ven la base
    vacía y el segundo revienta con `duplicate key ... pg_type_typname_nsp_index` al crear un
    tipo ENUM que el primero acababa de crear. El lock consultivo serializa esa sección.
    """
    if settings.is_hardened_environment:
        verificar_esquema()
        return

    logger.info("Inicializando esquema de base de datos...")

    if IS_SQLITE:
        Base.metadata.create_all(bind=engine)
        logger.info("Esquema de base de datos verificado y listo.")
        return

    with engine.begin() as connection:
        # El lock se libera solo al cerrar la transacción, incluso si create_all falla.
        connection.execute(text("SELECT pg_advisory_xact_lock(:clave)"), {"clave": SCHEMA_LOCK_ID})
        Base.metadata.create_all(bind=connection)

    logger.info("Esquema de base de datos verificado y listo.")
