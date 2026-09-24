"""el desenlace del prospecto: motivo, fecha de cierre y tramo del acuerdo

Capítulo 30, «Cerrar el bucle: el desenlace con su motivo».

Una tabla nueva, `desenlaces`: cómo acabó cada prospecto, por qué, cuándo y —si se ganó— de
qué tamaño. Una fila por prospecto (`uq_desenlaces_lead`), porque un prospecto se cierra
una vez y corregir un cierre reescribe la fila en lugar de añadir otra.

Qué NO hace esta migración, y por qué
--------------------------------------
**No rellena nada.** Los prospectos que ya estén en `WON` o `LOST` cuando esto se despliegue
se quedan sin desenlace, y eso es lo correcto: el motivo de un cierre anterior a que la
lista existiera no está en ninguna parte, y escribir «otro motivo» en todos ellos llenaría
el panel de una respuesta que nadie dio. El contador del reentrenamiento los cuenta como
cerrados y no como utilizables, que es exactamente la verdad, y la merma se ve en el panel
en lugar de quedar disimulada.

Lo mismo con la fecha: `updated_at` es la última vez que alguien tocó la ficha, no el día
del cierre. Usarla habría producido un panel por meses con fechas plausibles y falsas, que
es peor que un panel con menos filas.

**No borra el estado.** `leads.status` sigue siendo la etapa y sigue mandando: el desenlace
la acompaña, no la sustituye. El extractor del dataset sigue leyendo `UNQUALIFIED` como
negativo aunque esa etapa no tenga desenlace.

Las dos claves foráneas y su comportamiento
--------------------------------------------
* `lead_id` con `CASCADE`: suprimir a una persona se lleva su desenlace, como se lleva sus
  actividades y su historial. El derecho de supresión no admite un rincón donde quede
  constancia de que existió.
* `score_history_id` con `SET NULL`: el desenlace apunta a la instantánea de entrada que
  etiqueta. La purga del historial tiene prohibido borrar esa fila, pero si algún día se
  borrara, el desenlace tiene que seguir existiendo diciendo que ya no tiene instantánea
  —y el contador dejará de considerarlo utilizable— en lugar de desaparecer con ella.
* `registrado_por_id` con `SET NULL`: la cuenta de quien lo registró puede darse de baja;
  el hecho sigue siendo cierto.

Los nombres de las restricciones se escriben a mano, como desde el capítulo 28: en
PostgreSQL el espacio de nombres de las restricciones es de todo el esquema y no de cada
tabla, y dejar que los genere la convención por defecto funcionó en SQLite y falló en
PostgreSQL. Esa lección se paga una sola vez.

La reversión
------------
`downgrade()` quita la tabla entera. Se pierden los motivos, las fechas de cierre y los
tramos; **no** se pierde qué prospectos estaban ganados o perdidos, porque eso vive en
`leads.status` y esta migración no lo toca. Dicho de otro modo: al revertir, el sistema
vuelve a saber cuántos se ganaron y vuelve a no saber por qué, que es justo el estado
anterior a este capítulo.

Revision ID: c1d9f4b72a08
Revises: a8d2f16c5b03
Create Date: 2026-09-24 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d9f4b72a08"
down_revision: Union[str, None] = "a8d2f16c5b03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CATEGORIAS = ("HOT", "WARM", "COLD")


def _categoria():
    """
    El mismo tipo enumerado que ya usan `leads.score_category` y `score_histories`.

    En PostgreSQL un `Enum` dentro de un `CREATE TABLE` emite además un `CREATE TYPE`, y el
    tipo `scorecategory` existe desde el esquema inicial: la migración fallaría con «type
    already exists». `create_type=False` le dice que se apoye en el que hay. En SQLite no
    existe la noción de tipo enumerado —se guarda como texto con una comprobación—, así que
    allí se usa el `Enum` genérico.

    Se resuelve mirando el dialecto en tiempo de ejecución y no con dos migraciones: el
    capítulo 27 ya enseñó que lo que funciona en el SQLite de las pruebas y no se ejerce
    contra PostgreSQL se descubre en el despliegue.
    """
    if op.get_bind().dialect.name == "postgresql":
        from sqlalchemy.dialects import postgresql

        return postgresql.ENUM(*CATEGORIAS, name="scorecategory", create_type=False)
    return sa.Enum(*CATEGORIAS, name="scorecategory")


def upgrade() -> None:
    op.create_table(
        "desenlaces",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("resultado", sa.String(length=20), nullable=False),
        sa.Column("motivo", sa.String(length=40), nullable=False),
        sa.Column("cerrado_el", sa.Date(), nullable=False),
        sa.Column("tramo", sa.String(length=30), nullable=True),
        sa.Column("score_al_cierre", sa.Float(), nullable=False),
        sa.Column("categoria_al_cierre", _categoria(), nullable=False),
        sa.Column("score_history_id", sa.Integer(), nullable=True),
        sa.Column("version_del_vector", sa.Integer(), nullable=True),
        sa.Column("registrado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("registrado_por_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_desenlaces"),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["leads.id"], name="fk_desenlaces_lead_id_leads", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["score_history_id"],
            ["score_histories.id"],
            name="fk_desenlaces_score_history_id_score_histories",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["registrado_por_id"],
            ["users.id"],
            name="fk_desenlaces_registrado_por_id_users",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_desenlaces_id", "desenlaces", ["id"])
    op.create_index("ix_desenlaces_resultado", "desenlaces", ["resultado"])
    op.create_index("ix_desenlaces_motivo", "desenlaces", ["motivo"])
    op.create_index("ix_desenlaces_cerrado_el", "desenlaces", ["cerrado_el"])
    op.create_index("ix_desenlaces_categoria_al_cierre", "desenlaces", ["categoria_al_cierre"])
    # Un prospecto se cierra una vez. Es el índice que convierte «reescribir el desenlace»
    # en la única forma posible de corregir un cierre.
    op.create_index("uq_desenlaces_lead", "desenlaces", ["lead_id"], unique=True)
    # La consulta del panel: los de un periodo, agrupados por resultado.
    op.create_index("idx_desenlaces_cerrado_resultado", "desenlaces", ["cerrado_el", "resultado"])


def downgrade() -> None:
    op.drop_index("idx_desenlaces_cerrado_resultado", table_name="desenlaces")
    op.drop_index("uq_desenlaces_lead", table_name="desenlaces")
    op.drop_index("ix_desenlaces_categoria_al_cierre", table_name="desenlaces")
    op.drop_index("ix_desenlaces_cerrado_el", table_name="desenlaces")
    op.drop_index("ix_desenlaces_motivo", table_name="desenlaces")
    op.drop_index("ix_desenlaces_resultado", table_name="desenlaces")
    op.drop_index("ix_desenlaces_id", table_name="desenlaces")
    op.drop_table("desenlaces")
