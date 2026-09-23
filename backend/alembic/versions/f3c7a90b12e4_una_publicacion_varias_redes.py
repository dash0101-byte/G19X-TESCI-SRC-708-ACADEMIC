"""una publicación, varias redes: redes de difusión y visitas por red

Capítulo 27, «Una publicación, varias redes».

`campaigns` gana `redes`: las redes de difusión activas (JSON). Vacío en todas las que ya
existen, que es «las de siempre» —LinkedIn, WhatsApp, Facebook y correo—, así que ninguna
publicación cambia de comportamiento al migrar.

`visitas_de_publicacion` gana `red` **dentro de la clave primaria**: pasa de (publicación,
día) a (publicación, día, red). Las visitas que ya estaban contadas no saben por dónde
llegaron —se contaron antes de que hubiera redes—, así que se quedan en `sin_red`, que es lo
que significan: se abrió la página y no consta desde dónde. Inventarles «linkedin» habría
dado una tabla por red con una primera fila falsa.

Cómo se cambia la clave
-----------------------
Con una tabla nueva y una copia, no con `ALTER`. Cambiar una clave primaria no se escribe
igual en SQLite que en PostgreSQL, y `batch_alter_table` resuelve el caso de SQLite pero
deja el de PostgreSQL a medias. Crear, copiar, borrar y renombrar es la misma secuencia en
los dos motores, y es la que se prueba en los dos.

La tabla provisional se crea con las restricciones **con sufijo**, y el sufijo se quita al
final. En PostgreSQL el nombre de una restricción es único en todo el esquema y no dentro de
su tabla, así que crear la provisional con el nombre definitivo choca con el que todavía
tiene la original. En SQLite esto no ocurre, y por eso el fallo solo aparece ejecutando la
migración contra PostgreSQL —que es donde corre en producción—.

La reversión vuelve a (publicación, día) **sumando** las filas de las distintas redes del
mismo día: el total de visitas de cada día se conserva, y lo único que se pierde es el
reparto por red. Las redes activas de cada publicación se pierden también; los prospectos,
sus canales y sus solicitudes no se tocan, así que una ficha que llegó por WhatsApp sigue
diciendo «WhatsApp» después de revertir.

Revision ID: f3c7a90b12e4
Revises: d5a8e2f41c73
Create Date: 2026-09-22 16:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3c7a90b12e4"
down_revision: Union[str, None] = "d5a8e2f41c73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLA = "visitas_de_publicacion"
PROVISIONAL = "visitas_de_publicacion_tmp"

# Los nombres de las restricciones de la tabla provisional llevan sufijo, y se les quita
# después de renombrar la tabla.
#
# En PostgreSQL el nombre de una restricción es único **en todo el esquema**, no dentro de
# su tabla: crear la provisional con el nombre definitivo choca con la restricción que
# todavía tiene la tabla original, y la migración revienta con «relation
# "pk_visitas_de_publicacion" already exists». En SQLite no pasa —ahí el nombre vive dentro
# del CREATE TABLE—, así que este fallo no se ve hasta ejecutarla contra PostgreSQL, que es
# donde corre en producción.
PK = "pk_visitas_de_publicacion"
FK = "fk_visitas_de_publicacion_campaign_id_campaigns"
SUFIJO = "_tmp"


def _renombrar_restricciones() -> None:
    """
    Les quita el sufijo a las restricciones de la tabla ya renombrada.

    Solo en PostgreSQL: SQLite no tiene `RENAME CONSTRAINT` y tampoco lo necesita, porque
    allí el nombre no sale de la tabla que lo declara.
    """
    if op.get_bind().dialect.name != "postgresql":
        return
    for nombre in (PK, FK):
        op.execute(f'ALTER TABLE {TABLA} RENAME CONSTRAINT "{nombre}{SUFIJO}" TO "{nombre}"')


# El mismo valor que `app.core.redes.SIN_RED`. Escrito aquí a mano a propósito: una
# migración describe la base tal como quedó el día que se ejecutó, y no puede cambiar de
# sentido porque mañana alguien renombre una constante del código.
SIN_RED = "sin_red"


def upgrade() -> None:
    with op.batch_alter_table("campaigns", schema=None) as batch_op:
        batch_op.add_column(sa.Column("redes", sa.JSON(), nullable=True))

    op.create_table(
        PROVISIONAL,
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("dia", sa.Date(), nullable=False),
        sa.Column("red", sa.String(length=20), nullable=False, server_default=SIN_RED),
        sa.Column("visitas", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=f"{FK}{SUFIJO}",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("campaign_id", "dia", "red", name=f"{PK}{SUFIJO}"),
    )
    # Los nombres de tabla no se pueden pasar como parámetro y aquí son constantes escritas
    # unas líneas más arriba: no entra nada de fuera en esta consulta.
    op.execute(
        sa.text(
            f"INSERT INTO {PROVISIONAL} (campaign_id, dia, red, visitas) "  # noqa: S608
            f"SELECT campaign_id, dia, '{SIN_RED}', visitas FROM {TABLA}"
        )
    )
    op.drop_table(TABLA)
    op.rename_table(PROVISIONAL, TABLA)
    _renombrar_restricciones()


def downgrade() -> None:
    op.create_table(
        PROVISIONAL,
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("dia", sa.Date(), nullable=False),
        sa.Column("visitas", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=f"{FK}{SUFIJO}",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("campaign_id", "dia", name=f"{PK}{SUFIJO}"),
    )
    # Se suman las redes del mismo día: el total diario se conserva y solo se pierde el
    # reparto. Sin el `SUM` la copia chocaría con la clave primaria en cuanto una
    # publicación tuviera visitas de dos redes el mismo día.
    op.execute(
        sa.text(
            # Nombres de tabla constantes, como en `upgrade`.
            f"INSERT INTO {PROVISIONAL} (campaign_id, dia, visitas) "  # noqa: S608
            f"SELECT campaign_id, dia, SUM(visitas) FROM {TABLA} GROUP BY campaign_id, dia"
        )
    )
    op.drop_table(TABLA)
    op.rename_table(PROVISIONAL, TABLA)
    _renombrar_restricciones()

    with op.batch_alter_table("campaigns", schema=None) as batch_op:
        batch_op.drop_column("redes")
