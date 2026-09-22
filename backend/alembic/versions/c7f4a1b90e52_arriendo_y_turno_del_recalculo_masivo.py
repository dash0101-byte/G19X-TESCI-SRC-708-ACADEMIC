"""arriendo y turno exclusivo del recalculo masivo

Revision ID: c7f4a1b90e52
Revises: a23deac578cf
Create Date: 2026-09-09 21:18:05.117402

`scoring_jobs.status` decía qué se pretendía hacer, no qué estaba pasando. Un proceso que
muere a mitad del recorrido deja su fila en RUNNING para siempre: quien consulta ve un
avance congelado que no distingue de uno lento, y el sistema sigue creyendo que hay un
recálculo vivo.

Esta migración añade lo que convierte ese estado en una afirmación comprobable:

* `lease_until` — hasta cuándo el proceso que lo tomó afirma seguir vivo. Lo renueva en
  cada lote. Vencido y sin renovar, el trabajo se da por abandonado.
* `heartbeat_at` — última señal de vida, informativa.
* `worker_id` — host y PID de quien lo ejecuta, para saber en qué contenedor mirar.
* `lease_key` — el turno, con **índice único**. Vale `RECALCULATE_ALL` mientras el trabajo
  está vivo y NULL en cuanto termina. NULL no colisiona consigo mismo ni en PostgreSQL ni
  en SQLite, así que los trabajos terminados no ocupan turno.

Sobre el índice único: es lo que hace que «un recálculo a la vez» sea cierto y no una
intención. La comprobación previa —mirar si hay uno activo y, si no, insertar— es una
carrera: con dos workers, dos peticiones simultáneas leen «no hay ninguno» y ambas
insertan. El motor no tiene ese problema.

Las filas existentes quedan con `lease_key` a NULL y `lease_until` a NULL. Un trabajo
histórico que hubiera quedado colgado en RUNNING se lee entonces como arriendo vencido y
lo cierra el primer barrido, que es exactamente lo que se quiere: la migración no arrastra
turnos ocupados por procesos que ya no existen.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c7f4a1b90e52'
down_revision: Union[str, Sequence[str], None] = 'a23deac578cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLA = "scoring_jobs"
INDICE_DEL_TURNO = "uq_scoring_jobs_lease_key"


def upgrade() -> None:
    # `batch_alter_table` para que valga también en SQLite, donde ALTER TABLE apenas
    # existe: Alembic recrea la tabla y copia las filas. En PostgreSQL se traduce a los
    # ALTER de siempre y no cuesta nada.
    with op.batch_alter_table(TABLA) as lote:
        lote.add_column(sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True))
        lote.add_column(sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
        lote.add_column(sa.Column("worker_id", sa.String(length=120), nullable=True))
        lote.add_column(sa.Column("lease_key", sa.String(length=40), nullable=True))

    # El índice se crea aparte y con `unique=True` explícito. Va después de las columnas
    # porque no puede indexarse lo que aún no existe.
    op.create_index(INDICE_DEL_TURNO, TABLA, ["lease_key"], unique=True)


def downgrade() -> None:
    op.drop_index(INDICE_DEL_TURNO, table_name=TABLA)
    with op.batch_alter_table(TABLA) as lote:
        lote.drop_column("lease_key")
        lote.drop_column("worker_id")
        lote.drop_column("heartbeat_at")
        lote.drop_column("lease_until")
