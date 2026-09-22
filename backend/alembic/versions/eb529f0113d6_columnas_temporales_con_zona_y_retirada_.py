"""columnas temporales con zona y retirada de tenant_id

Revision ID: eb529f0113d6
Revises: 675112244474
Create Date: 2026-09-09 09:38:05.646908

Dos cambios independientes que viajan juntos porque afectan a la misma tabla `users`:

1. **Zona horaria explícita en las 19 columnas temporales.** La aplicación siempre escribió
   instantes en UTC (`utc_now()` devuelve un valor con zona), pero las columnas eran
   `TIMESTAMP WITHOUT TIME ZONE` y la descartaban al persistir. Lo que entraba como
   «14:03 UTC» se leía después como «14:03 sin zona» y el consumidor tenía que adivinar.
   El cálculo de inactividad —del que depende el decaimiento temporal del score— acababa
   restando un instante con zona de otro sin ella.

2. **Retirada de `users.tenant_id`.** El sistema declaraba un identificador de inquilino y
   lo incluía en cada token, pero ninguna consulta filtraba por él: las tablas de negocio
   no tienen esa columna. Una separación que no separa induce a confiar en un aislamiento
   inexistente, así que se retira. Implementar multi-tenencia de verdad exigiría añadir la
   columna a `leads`, `campaigns` y `sales_reps` y filtrar en el repositorio.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "eb529f0113d6"
down_revision: Union[str, Sequence[str], None] = "675112244474"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (tabla, columna, admite nulos)
COLUMNAS_TEMPORALES = [
    ("campaigns", "start_date", True),
    ("campaigns", "end_date", True),
    ("campaigns", "created_at", False),
    ("crm_integration_logs", "synced_at", False),
    ("lead_activities", "timestamp", False),
    ("lead_activities", "created_at", False),
    ("leads", "last_score_update", False),
    ("leads", "last_activity_at", False),
    ("leads", "created_at", False),
    ("leads", "updated_at", False),
    ("sales_reps", "created_at", False),
    ("sales_reps", "updated_at", False),
    ("score_histories", "calculated_at", False),
    ("scoring_jobs", "created_at", False),
    ("scoring_jobs", "started_at", True),
    ("scoring_jobs", "finished_at", True),
    ("users", "last_login_at", True),
    ("users", "created_at", False),
    ("users", "updated_at", False),
]


def upgrade() -> None:
    """Convierte a `timestamptz` interpretando lo ya guardado como UTC, y elimina tenant_id."""
    dialecto = op.get_bind().dialect.name

    for tabla, columna, admite_nulos in COLUMNAS_TEMPORALES:
        if dialecto == "postgresql":
            # El `USING` es lo importante de esta migración y por eso no se deja el
            # `alter_column` que generó Alembic. Sin él, PostgreSQL interpreta cada valor
            # sin zona según el huso de la SESIÓN que ejecuta la migración: aplicada desde
            # un servidor en America/Mexico_City, las fechas quedarían desplazadas seis
            # horas y el decaimiento temporal calcularía sobre datos falseados. Como todo
            # se escribió en UTC, se declara explícitamente.
            op.alter_column(
                tabla,
                columna,
                existing_type=postgresql.TIMESTAMP(),
                type_=sa.DateTime(timezone=True),
                existing_nullable=admite_nulos,
                postgresql_using=f'"{columna}" AT TIME ZONE \'UTC\'',
            )
        else:
            # SQLite no sabe alterar una columna en sitio: hay que reconstruir la tabla, que
            # es lo que hace `batch_alter_table`. El cambio en si es un no-operativo alli
            # —SQLite guarda texto y no distingue ambos tipos—, pero se recorre igualmente
            # para que el historial de revisiones sea el mismo en las pruebas y en produccion.
            with op.batch_alter_table(tabla) as lote:
                lote.alter_column(
                    columna,
                    existing_type=sa.DateTime(),
                    type_=sa.DateTime(timezone=True),
                    existing_nullable=admite_nulos,
                )

    if dialecto == "postgresql":
        op.drop_column("users", "tenant_id")
    else:
        with op.batch_alter_table("users") as lote:
            lote.drop_column("tenant_id")


def downgrade() -> None:
    """
    Revierte a `timestamp` sin zona y restaura la columna `tenant_id`.

    La vuelta atrás también convierte a UTC explícitamente, de modo que un ciclo
    upgrade→downgrade devuelva exactamente los mismos valores con los que empezó.

    `tenant_id` se restaura con un valor por defecto en el servidor porque la columna es
    obligatoria y las filas existentes no lo tienen; el valor se retira acto seguido para
    dejar la definición como estaba.
    """
    dialecto = op.get_bind().dialect.name

    columna_tenant = sa.Column(
        "tenant_id",
        sa.String(length=100),
        nullable=False,
        server_default="plurione-enterprise-tenant",
    )
    if dialecto == "postgresql":
        op.add_column("users", columna_tenant)
        op.alter_column("users", "tenant_id", server_default=None)
    else:
        with op.batch_alter_table("users") as lote:
            lote.add_column(columna_tenant)

    for tabla, columna, admite_nulos in reversed(COLUMNAS_TEMPORALES):
        if dialecto == "postgresql":
            op.alter_column(
                tabla,
                columna,
                existing_type=sa.DateTime(timezone=True),
                type_=postgresql.TIMESTAMP(),
                existing_nullable=admite_nulos,
                postgresql_using=f'"{columna}" AT TIME ZONE \'UTC\'',
            )
        else:
            with op.batch_alter_table(tabla) as lote:
                lote.alter_column(
                    columna,
                    existing_type=sa.DateTime(timezone=True),
                    type_=sa.DateTime(),
                    existing_nullable=admite_nulos,
                )
