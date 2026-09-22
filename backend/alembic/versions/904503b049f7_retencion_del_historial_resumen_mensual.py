"""retencion del historial: resumen mensual por prospecto

Revision ID: 904503b049f7
Revises: c7f4a1b90e52
Create Date: 2026-09-10 19:32:56.129729

`score_histories` crecía sin techo: una fila por recálculo, cada una con su vector de
variables y su explicación, para siempre (R-3). Esta migración crea el sitio donde va lo
que la purga retira: `score_history_monthly`, una fila por prospecto y mes con recuento,
suma, extremos, primera y última puntuación, categorías y versiones de modelo.

El índice que R-3 pedía sobre `(lead_id, calculated_at)` NO se crea aquí porque ya existe
desde la migración de base (`idx_score_history_lead_time`). Crearlo otra vez habría dejado
dos índices idénticos que PostgreSQL mantiene en cada INSERT.

Sobre el tipo enumerado
-----------------------
`last_category` reutiliza el tipo `scorecategory` que ya usan `leads` y `score_histories`.
Tal como la genera `--autogenerate`, la columna declara un `sa.Enum` con ese nombre, y en
PostgreSQL eso hace dos cosas que esta migración no puede hacer:

* al subir desde la revisión anterior —el despliegue real, no el `upgrade head` desde cero
  del CI— emite `CREATE TYPE scorecategory` y falla porque el tipo existe;
* al bajar, `drop_table` emite `DROP TYPE scorecategory` y se lo quita a las dos tablas que
  lo siguen usando.

La variante con `create_type=False` le dice a PostgreSQL que el tipo no es de esta tabla.
En SQLite no hay tipos con nombre y la columna sigue siendo el VARCHAR con CHECK de siempre.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '904503b049f7'
down_revision: Union[str, Sequence[str], None] = 'c7f4a1b90e52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLA = "score_history_monthly"
CATEGORIAS = ("HOT", "WARM", "COLD")
CATEGORIA = sa.Enum(*CATEGORIAS, name="scorecategory").with_variant(
    postgresql.ENUM(*CATEGORIAS, name="scorecategory", create_type=False), "postgresql"
)


def upgrade() -> None:
    op.create_table(
        TABLA,
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('month', sa.Date(), nullable=False),
        sa.Column('scores_count', sa.Integer(), nullable=False),
        sa.Column('score_sum', sa.Float(), nullable=False),
        sa.Column('score_min', sa.Float(), nullable=False),
        sa.Column('score_max', sa.Float(), nullable=False),
        sa.Column('first_score', sa.Float(), nullable=False),
        sa.Column('first_calculated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_score', sa.Float(), nullable=False),
        sa.Column('last_category', CATEGORIA, nullable=False),
        sa.Column('last_calculated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('category_counts', sa.JSON(), nullable=False),
        sa.Column('model_versions', sa.JSON(), nullable=False),
        sa.Column('aggregated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table(TABLA, schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_score_history_monthly_id'), ['id'], unique=False)
        # Un mes por prospecto: una segunda pasada de la purga fusiona, no duplica.
        batch_op.create_index('uq_score_history_monthly_lead_month', ['lead_id', 'month'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table(TABLA, schema=None) as batch_op:
        batch_op.drop_index('uq_score_history_monthly_lead_month')
        batch_op.drop_index(batch_op.f('ix_score_history_monthly_id'))

    op.drop_table(TABLA)
