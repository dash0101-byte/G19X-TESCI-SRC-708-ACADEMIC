"""
Entorno de Alembic para el Sistema Inteligente de Lead Scoring.

La URL de conexión NO se lee de `alembic.ini`: se toma de `settings`, es decir de la misma
variable `DATABASE_URL` que usa la aplicación. Escribirla en el .ini habría significado
tener una credencial de producción versionada en el repositorio, que es justo el problema
que se corrigió al principio del endurecimiento.
"""
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# El paquete `app` vive en `backend/`, dos niveles por encima de este archivo.
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.core.config import settings  # noqa: E402  (requiere el sys.path de arriba)
from app.core.database import Base  # noqa: E402

# Importar el módulo de entidades tiene el efecto de registrar cada tabla en
# `Base.metadata`. Sin esta línea, `--autogenerate` compararía contra unos metadatos
# vacíos y propondría borrar el esquema entero.
from app.models import entities  # noqa: E402,F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))

target_metadata = Base.metadata


def _opciones_comunes() -> dict:
    return {
        "target_metadata": target_metadata,
        # Sin esto, Alembic no detecta un cambio de tipo de columna: el paso de
        # `DateTime` a `DateTime(timezone=True)` habría pasado desapercibido.
        "compare_type": True,
        "compare_server_default": True,
        # SQLite no sabe alterar columnas en sitio; el modo por lotes reconstruye la tabla.
        # Es imprescindible para que las mismas migraciones sirvan en las pruebas.
        "render_as_batch": settings.DATABASE_URL.startswith("sqlite"),
    }


def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse, para revisarlo antes de aplicarlo en producción."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_opciones_comunes(),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica las migraciones contra la base configurada."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, **_opciones_comunes())

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
