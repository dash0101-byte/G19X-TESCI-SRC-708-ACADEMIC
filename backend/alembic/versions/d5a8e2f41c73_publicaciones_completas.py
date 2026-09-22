"""publicaciones completas: estado, opciones de necesidad, responsable, post real y visitas

Capítulo 26, «Publicaciones completas».

`campaigns` gana:

* `estado`: borrador, activa, pausada o cerrada. Obligatorio. Las campañas que ya existen lo
  reciben de `is_active`: activa si lo estaba, **cerrada** si no. Una campaña desactivada
  antes de que hubiera estados se desactivó para dejar de recibir perfiles, y «cerrada» es
  lo que eso significa ahora; «pausada» sería afirmar que se piensa reanudar.
* `necesidades`: las opciones de «¿Qué necesitas?» de la publicación (JSON). Vacío en todas
  las que ya existen: siguen con las de siempre.
* `responsable_id`: el asesor que recibe sus prospectos. Vacío en todas: siguen llegando sin
  asesor, como hasta ahora.
* `url_del_post`: la dirección del post publicado. Vacía.

Y una tabla nueva, `visitas_de_publicacion` (publicación, día, visitas): un contador agregado,
sin nada de quien visita.

La reversión quita la tabla y las cuatro columnas. Se pierden los estados (vuelve a quedar
solo `is_active`, que se ha mantenido igual a «activa»: una pausada o un borrador quedan
inactivos, que es lo más cercano), las opciones propias de cada publicación, el responsable,
la dirección del post y el recuento de visitas. Los prospectos, sus solicitudes y sus
asignaciones no se tocan.

Revision ID: d5a8e2f41c73
Revises: b7e41c9d2f60
Create Date: 2026-09-22 09:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5a8e2f41c73"
down_revision: Union[str, None] = "b7e41c9d2f60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("campaigns", schema=None) as batch_op:
        batch_op.add_column(sa.Column("estado", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("necesidades", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("responsable_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("url_del_post", sa.String(length=300), nullable=True))
        batch_op.create_foreign_key(
            "fk_campaigns_responsable_id_users", "users", ["responsable_id"], ["id"], ondelete="SET NULL"
        )

    campanas = sa.table(
        "campaigns", sa.column("is_active", sa.Boolean), sa.column("estado", sa.String)
    )
    op.execute(campanas.update().where(campanas.c.is_active.is_(True)).values(estado="activa"))
    op.execute(campanas.update().where(campanas.c.is_active.is_(False)).values(estado="cerrada"))

    with op.batch_alter_table("campaigns", schema=None) as batch_op:
        batch_op.alter_column(
            "estado", existing_type=sa.String(length=20), nullable=False, server_default="activa"
        )

    op.create_table(
        "visitas_de_publicacion",
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("dia", sa.Date(), nullable=False),
        sa.Column("visitas", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("campaign_id", "dia"),
    )


def downgrade() -> None:
    op.drop_table("visitas_de_publicacion")
    with op.batch_alter_table("campaigns", schema=None) as batch_op:
        batch_op.drop_constraint("fk_campaigns_responsable_id_users", type_="foreignkey")
        batch_op.drop_column("url_del_post")
        batch_op.drop_column("responsable_id")
        batch_op.drop_column("necesidades")
        batch_op.drop_column("estado")
