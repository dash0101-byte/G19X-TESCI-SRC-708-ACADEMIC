"""Bajo qué dirección se repartió el enlace de cada publicación (capítulo 34)

Revision ID: b7e2d94a1f05
Revises: a4c8d1e70f39
Create Date: 2026-09-25

Una columna, sin migración de datos, y el motivo de que no la haya es lo que más conviene
dejar escrito.

`campaigns.url_base_publicada` guarda el valor de `PUBLICACIONES_URL_BASE` en el instante en
que la publicación se activó, que es cuando su enlace se vuelve repartible. Comparar eso con
la dirección de ahora es lo que permite decir «el enlace que está en ese post ya no lleva
aquí» en vez de dejar que el post falle en silencio durante semanas, y hace falta porque un
túnel de prueba gratuito da una dirección **distinta en cada arranque**.

Por qué las publicaciones que ya existen se quedan en NULL
----------------------------------------------------------
La tentación es rellenarlas con la dirección actual: son una línea de SQL y dejan la columna
sin huecos. Sería falso. De esas publicaciones **no consta** bajo qué dirección salieron
—pudo cambiar cinco veces desde que se activaron— y escribir la de hoy afirmaría que sus
enlaces están vigentes, que es justo lo contrario de lo que la columna existe para detectar.

Un `NULL` aquí significa «no se sabe», y `enlace_caducado` lo trata como «no se avisa». Es el
mismo criterio del capítulo 32 con el país supuesto: se prefiere una advertencia que falta a
una advertencia inventada, porque la segunda enseña a ignorar la primera.

La reversión borra la columna. No pierde nada que no se pueda reconstruir activando de nuevo.
"""
import sqlalchemy as sa
from alembic import op

revision = "b7e2d94a1f05"
down_revision = "a4c8d1e70f39"
branch_labels = None
depends_on = None

# El mismo ancho que `url_del_post`, que guarda una dirección del mismo orden.
_ANCHO = 300


def upgrade() -> None:
    op.add_column("campaigns", sa.Column("url_base_publicada", sa.String(_ANCHO), nullable=True))


def downgrade() -> None:
    op.drop_column("campaigns", "url_base_publicada")
