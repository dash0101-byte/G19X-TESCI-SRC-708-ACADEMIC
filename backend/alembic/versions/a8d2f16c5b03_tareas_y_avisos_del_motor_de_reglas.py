"""tareas y avisos del motor de reglas, y la marca de prospecto dormido

Capítulo 28, «El sistema dice qué hacer hoy».

Dos tablas nuevas y una columna:

* `tareas`: qué hay que hacer con un prospecto, de quién es el trabajo y para cuándo. El
  índice único `(regla, lead_id, clave)` es lo que hace idempotente la pasada diaria: el
  motor puede correr dos veces la misma mañana sin duplicar nada.
* `avisos`: lo que alguien tiene que enterarse de que pasó, dentro del panel. Su índice
  único incluye al destinatario, porque el mismo hecho puede avisar al asesor y, más tarde,
  al líder: son dos avisos distintos, no uno repetido.
* `leads.dormido_desde`: desde cuándo nadie toca al prospecto. Nulo en todos los que ya
  existen, que es lo correcto: ninguno ha sido evaluado todavía por la regla, y marcarlos a
  ciegas llenaría la campana de avisos sobre un pasado que nadie puede atender. La primera
  pasada tras desplegar los marca según la regla, y esa pasada sí avisa.

Los nombres de las restricciones se escriben a mano. En PostgreSQL el espacio de nombres de
las restricciones es de todo el esquema y no de cada tabla: dos índices llamados igual en
tablas distintas chocan. Dejar que los genere la convención por defecto funcionó en SQLite y
falló en PostgreSQL en el capítulo 27, y esa lección se paga una sola vez.

La reversión quita las dos tablas y la columna. Se pierde el trabajo pendiente, el que ya se
hizo y los avisos leídos y sin leer. Los prospectos, sus actividades y sus asignaciones no se
tocan: nada de lo que se borra aquí es un hecho del prospecto, sino trabajo nuestro sobre él.

Revision ID: a8d2f16c5b03
Revises: f3c7a90b12e4
Create Date: 2026-09-23 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8d2f16c5b03"
down_revision: Union[str, None] = "f3c7a90b12e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ABIERTA = "abierta"


def upgrade() -> None:
    op.create_table(
        "tareas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("asesor_id", sa.Integer(), nullable=False),
        sa.Column("regla", sa.String(length=40), nullable=False),
        sa.Column("clave", sa.String(length=80), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default=ABIERTA),
        sa.Column("vence_el", sa.DateTime(timezone=True), nullable=False),
        sa.Column("motivo", sa.String(length=200), nullable=False),
        sa.Column("datos", sa.JSON(), nullable=True),
        sa.Column("creada_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cerrada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cerrada_por_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_tareas"),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["leads.id"], name="fk_tareas_lead_id_leads", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["asesor_id"], ["users.id"], name="fk_tareas_asesor_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["cerrada_por_id"], ["users.id"], name="fk_tareas_cerrada_por_id_users", ondelete="SET NULL"
        ),
    )
    op.create_index("ix_tareas_id", "tareas", ["id"])
    op.create_index("ix_tareas_lead_id", "tareas", ["lead_id"])
    op.create_index("ix_tareas_asesor_id", "tareas", ["asesor_id"])
    op.create_index("ix_tareas_regla", "tareas", ["regla"])
    op.create_index("ix_tareas_estado", "tareas", ["estado"])
    op.create_index("ix_tareas_vence_el", "tareas", ["vence_el"])
    op.create_index("uq_tareas_regla_lead_clave", "tareas", ["regla", "lead_id", "clave"], unique=True)
    op.create_index("idx_tareas_asesor_estado_vence", "tareas", ["asesor_id", "estado", "vence_el"])

    op.create_table(
        "avisos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("regla", sa.String(length=40), nullable=False),
        sa.Column("clave", sa.String(length=80), nullable=False),
        sa.Column("texto", sa.String(length=300), nullable=False),
        sa.Column("datos", sa.JSON(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("leido_en", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_avisos"),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["users.id"], name="fk_avisos_usuario_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["leads.id"], name="fk_avisos_lead_id_leads", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_avisos_id", "avisos", ["id"])
    op.create_index("ix_avisos_usuario_id", "avisos", ["usuario_id"])
    op.create_index("ix_avisos_lead_id", "avisos", ["lead_id"])
    op.create_index("ix_avisos_regla", "avisos", ["regla"])
    op.create_index("ix_avisos_creado_en", "avisos", ["creado_en"])
    op.create_index(
        "uq_avisos_usuario_regla_lead_clave", "avisos", ["usuario_id", "regla", "lead_id", "clave"], unique=True
    )
    op.create_index("idx_avisos_usuario_leido_creado", "avisos", ["usuario_id", "leido_en", "creado_en"])

    with op.batch_alter_table("leads", schema=None) as batch_op:
        batch_op.add_column(sa.Column("dormido_desde", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("ix_leads_dormido_desde", ["dormido_desde"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("leads", schema=None) as batch_op:
        batch_op.drop_index("ix_leads_dormido_desde")
        batch_op.drop_column("dormido_desde")

    op.drop_index("idx_avisos_usuario_leido_creado", table_name="avisos")
    op.drop_index("uq_avisos_usuario_regla_lead_clave", table_name="avisos")
    op.drop_index("ix_avisos_creado_en", table_name="avisos")
    op.drop_index("ix_avisos_regla", table_name="avisos")
    op.drop_index("ix_avisos_lead_id", table_name="avisos")
    op.drop_index("ix_avisos_usuario_id", table_name="avisos")
    op.drop_index("ix_avisos_id", table_name="avisos")
    op.drop_table("avisos")

    op.drop_index("idx_tareas_asesor_estado_vence", table_name="tareas")
    op.drop_index("uq_tareas_regla_lead_clave", table_name="tareas")
    op.drop_index("ix_tareas_vence_el", table_name="tareas")
    op.drop_index("ix_tareas_estado", table_name="tareas")
    op.drop_index("ix_tareas_regla", table_name="tareas")
    op.drop_index("ix_tareas_asesor_id", table_name="tareas")
    op.drop_index("ix_tareas_lead_id", table_name="tareas")
    op.drop_index("ix_tareas_id", table_name="tareas")
    op.drop_table("tareas")
