"""Segundo factor TOTP para las cuentas (capítulo 35)

Revision ID: c3f18b6a02d7
Revises: b7e2d94a1f05
Create Date: 2026-09-25

Cinco columnas en `users`, ninguna migración de datos, y **ningún secreto**.

Lo que más conviene dejar escrito de esta migración es lo que NO hay en ella. No hay una
columna con el secreto TOTP, ni cifrado ni en claro: `totp_sal` guarda una sal aleatoria y
el secreto se deriva de ella con `SECRET_KEY`, que vive en el entorno y nunca en la base. Un
volcado de esta tabla —un respaldo, un `pg_dump` que acabe donde no debe— no contiene nada
con lo que generar un código.

El precio va escrito en `app/services/segundo_factor.py` y en la guía: rotar `SECRET_KEY`
invalida todas las altas, y no se pueden recuperar porque no hay nada cifrado que releer.

Todas las cuentas quedan sin segundo factor (`totp_activo = false`). Las de administración
pasan a estar obligadas a darse de alta, y la propia aplicación las lleva por ese camino en
cuanto entran: no hace falta tocarlas aquí, y hacerlo sería imposible —un alta exige un
teléfono delante—.

La reversión borra las cinco columnas. Pierde las altas, que es lo que tiene que pasar:
volver atrás en el esquema significa volver a un sistema sin segundo factor.
"""
import sqlalchemy as sa
from alembic import op

revision = "c3f18b6a02d7"
down_revision = "b7e2d94a1f05"
branch_labels = None
depends_on = None

_COLUMNAS = (
    "totp_sal",
    "totp_activo",
    "totp_activado_en",
    "totp_codigos_de_recuperacion",
    "totp_ultimo_contador",
)


def upgrade() -> None:
    op.add_column("users", sa.Column("totp_sal", sa.String(64), nullable=True))
    # `server_default` además del default del modelo: sin él, las filas que YA existen se
    # quedarían a NULL en una columna NOT NULL y la migración fallaría en la propia
    # sentencia. El default se retira después para que sea la aplicación quien decida.
    op.add_column(
        "users",
        sa.Column("totp_activo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # El `server_default` se retira después, para que sea la aplicación quien decida el
    # valor y no quede una regla duplicada en la base. Va dentro de `batch_alter_table`
    # porque SQLite no sabe hacer `ALTER COLUMN`: alembic reconstruye la tabla entera.
    # Es el mismo camino que sigue `a23deac578cf` con `must_change_password`, y saltárselo
    # rompe la comprobación de ida y vuelta de las migraciones, que corre sobre SQLite.
    with op.batch_alter_table("users") as lote:
        lote.alter_column("totp_activo", server_default=None)
    op.add_column("users", sa.Column("totp_activado_en", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("totp_codigos_de_recuperacion", sa.JSON(), nullable=True))
    op.add_column("users", sa.Column("totp_ultimo_contador", sa.Integer(), nullable=True))


def downgrade() -> None:
    for columna in reversed(_COLUMNAS):
        op.drop_column("users", columna)
