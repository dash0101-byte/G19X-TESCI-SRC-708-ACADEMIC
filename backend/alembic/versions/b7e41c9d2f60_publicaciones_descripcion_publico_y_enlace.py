"""publicaciones: descripción, a quién va dirigida y enlace público de la campaña

Fase 1 de «Del post de LinkedIn al prospecto puntuado».

Una publicación es una campaña con canal LinkedIn; no hay tabla nueva. `campaigns` gana:

* `description`: el texto de la publicación.
* `target_audience`: a quién va dirigida.
* `public_slug`: el identificador del enlace público. Aleatorio (128 bits), obligatorio y
  con índice único `uq_campaigns_public_slug`.

Las campañas que ya existen reciben su slug aquí, uno por fila, antes de volver la columna
obligatoria.

La reversión quita las tres columnas y el índice. Con ellas se pierden los slugs: si
después se vuelve a migrar hacia delante, cada campaña recibe uno nuevo y los enlaces
publicados con el anterior dejan de valer. Revertir esta migración con publicaciones ya
difundidas es romper esos enlaces.

Revision ID: b7e41c9d2f60
Revises: e3a9c41d7b25
Create Date: 2026-09-17 09:00:00.000000

"""
import secrets
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e41c9d2f60"
down_revision: Union[str, None] = "e3a9c41d7b25"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _slug() -> str:
    """
    Copia de `app.core.publicaciones.nuevo_slug_publico` tal como es en esta fase. Una
    migración no importa código de la aplicación: ese código puede cambiar después, y la
    migración tiene que seguir haciendo lo mismo que hizo el día que se escribió.
    """
    return secrets.token_urlsafe(16)


def upgrade() -> None:
    with op.batch_alter_table("campaigns", schema=None) as batch_op:
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("target_audience", sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column("public_slug", sa.String(length=32), nullable=True))

    conexion = op.get_bind()
    campanas = sa.table("campaigns", sa.column("id", sa.Integer), sa.column("public_slug", sa.String))
    usados: set = set()
    for (campana_id,) in conexion.execute(sa.select(campanas.c.id)).fetchall():
        slug = _slug()
        # 128 bits no chocan en la práctica; comprobarlo cuesta una línea y hace que el
        # índice único de abajo no pueda fallar por azar.
        while slug in usados:
            slug = _slug()
        usados.add(slug)
        conexion.execute(
            campanas.update().where(campanas.c.id == campana_id).values(public_slug=slug)
        )

    with op.batch_alter_table("campaigns", schema=None) as batch_op:
        batch_op.alter_column("public_slug", existing_type=sa.String(length=32), nullable=False)
    op.create_index("uq_campaigns_public_slug", "campaigns", ["public_slug"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_campaigns_public_slug", table_name="campaigns")
    with op.batch_alter_table("campaigns", schema=None) as batch_op:
        batch_op.drop_column("public_slug")
        batch_op.drop_column("target_audience")
        batch_op.drop_column("description")
