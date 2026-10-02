"""un blanco no es un dato: los textos en blanco de la base pasan a vacio

Capítulo 41. No cambia ni una columna: solo lo que hay escrito en ellas.

Qué se corrige
--------------
Hasta este capítulo, cuatro de las cinco puertas por las que entra texto guardaban un blanco
tal cual. El alta de una ficha normalizaba el país —el capítulo 32 lo escribió para el país,
que era el campo del que se ocupaba— y dejaba los otros nueve campos de texto; la edición los
normalizaba todos desde el 33; y el alta y la edición de una publicación, ninguno. En la base
quedaron por tanto dos formas de decir «no hay dato» en la misma columna: `NULL` en las filas
que pasaron por la edición y `''` —o espacios— en las que entraron por el alta.

Esto las iguala. `TRIM(columna) = ''` cubre las tres formas que llegaban: la cadena vacía de un
campo que nadie tocó, el espacio que queda al borrar lo escrito y el par de espacios de un
copiado y pegado.

Por qué esta migración sí puede tocarlo todo, y la del capítulo 32 no podía
---------------------------------------------------------------------------
La del 32 solo vació el país de las fichas de las que **constaba** que nadie lo había
indicado, porque «México» podía ser una suposición de la columna o la elección de una persona
y la fila no guarda cuál de las dos fue. Aquí no hay esa duda: nadie escribe tres espacios en
«Ciudad» a propósito. Un blanco no es un dato, y eso sí se puede demostrar fila a fila.

Qué columnas, y por qué esas
-----------------------------
Las de texto que admiten nulo de las tres tablas que un cuerpo de petición escribe, y solo las
que algún esquema de entrada nombra. `backend/tests/test_migracion_un_blanco_no_es_un_dato.py`
deriva esa misma lista de los esquemas y de las tablas y la compara con la de abajo, para que
una columna nueva no se quede fuera en silencio.

Quedan fuera, y cada una por su motivo:

* `leads.privacy_notice_source`, `campaigns.url_base_publicada`, `campaigns.public_slug`,
  `users.totp_sal` y todo lo de las tablas de traza y de trabajo —bitácora, entregas,
  historiales—: **las escribe el servidor**, no un cuerpo de petición. Un blanco ahí no sería
  un dato sin normalizar, sería un defecto de otro sitio, y vaciarlo lo taparía.
* Las columnas `NOT NULL`. No se puede escribir nulo en ellas, así que no hay nada que
  igualar; lo que hay es un recuento, y está abajo.

Lo que esta migración NO arregla, y se cuenta
----------------------------------------------
`leads.first_name`, `leads.last_name`, `leads.source`, `users.full_name`, `campaigns.name` y
`campaigns.channel` son obligatorias. Una de ellas en blanco solo tiene dos salidas: inventar
un valor, que es lo que el capítulo 25 quitó de este sistema —«Prospecto», «Sin Apellido»,
«Empresa no identificada»— o dejar que lo escriba quien lo sepa. Se cuentan y se nombran en la
salida de la migración para que alguien pueda ir a corregirlas, que es posible: la edición
admite un nombre de verdad y la ficha se encuentra por su correo.

Un nombre vacío además **puede ser correcto**: desde el capítulo 25, una ficha que entra por
el webhook de un CRM que no mandó el nombre se queda sin nombre a propósito, porque perder el
prospecto sería peor. Esta migración no puede distinguir ese vacío del que escribió el alta del
panel —la fila no guarda por dónde entró—, y es exactamente la situación del capítulo 32 con el
país: cuando no se puede distinguir, no se toca.

Reversión
---------
No hay. Un `NULL` que antes era `''` es indistinguible de un `NULL` que siempre fue `NULL`, así
que escribir `''` en los nulos reintroduciría el defecto en filas que quizá nunca lo tuvieron
—el mismo motivo por el que el capítulo 32 no des-normaliza los teléfonos—. `downgrade` no
hace nada y lo dice.
"""
from typing import Dict, Sequence, Tuple, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d8b3e5f09a71"
down_revision: Union[str, None] = "c3f18b6a02d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tabla -> columnas de texto que admiten nulo y que un esquema de entrada nombra.
COLUMNAS_QUE_SE_IGUALAN: Dict[str, Tuple[str, ...]] = {
    "leads": ("phone", "company", "job_title", "industry", "company_size", "country", "city"),
    "users": ("phone",),
    "campaigns": (
        "description",
        "target_audience",
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "url_del_post",
    ),
}

# Tabla -> columnas de texto obligatorias que un esquema de entrada nombra. No se tocan: se
# cuentan.
COLUMNAS_QUE_SOLO_SE_CUENTAN: Dict[str, Tuple[str, ...]] = {
    "leads": ("first_name", "last_name", "source"),
    "users": ("full_name",),
    "campaigns": ("name", "channel"),
}


def _igualar_los_vacios(bind) -> None:
    total = 0
    for tabla, columnas in COLUMNAS_QUE_SE_IGUALAN.items():
        for columna in columnas:
            # `TRIM` es ANSI y lo entienden SQLite y PostgreSQL igual. La condición excluye el
            # nulo por sí sola —`TRIM(NULL)` es nulo y no iguala a nada—, así que no se
            # reescriben filas que ya estaban bien.
            resultado = bind.execute(
                sa.text(f"UPDATE {tabla} SET {columna} = NULL WHERE TRIM({columna}) = ''")  # noqa: S608
            )
            if resultado.rowcount:
                print(
                    f"[migracion d8b3e5f09a71] {tabla}.{columna}: "
                    f"{resultado.rowcount} blancos pasados a vacio."
                )
            total += max(resultado.rowcount, 0)
    print(
        f"[migracion d8b3e5f09a71] Total: {total} valores en blanco igualados a NULL en "
        f"{sum(len(c) for c in COLUMNAS_QUE_SE_IGUALAN.values())} columnas."
    )


def _contar_los_que_no_se_pueden_vaciar(bind) -> None:
    pendientes = []
    for tabla, columnas in COLUMNAS_QUE_SOLO_SE_CUENTAN.items():
        for columna in columnas:
            cuantos = bind.execute(
                sa.text(f"SELECT COUNT(*) FROM {tabla} WHERE TRIM({columna}) = ''")  # noqa: S608
            ).scalar()
            if cuantos:
                pendientes.append(f"{tabla}.{columna}: {cuantos}")
    if not pendientes:
        print(
            "[migracion d8b3e5f09a71] Columnas obligatorias: ninguna fila con el texto en "
            "blanco. Nada que corregir a mano."
        )
        return
    print(
        "[migracion d8b3e5f09a71] Columnas obligatorias EN BLANCO (no se tocan; hay que "
        "escribirlas): " + "; ".join(pendientes) + ". Un nombre no se puede inventar, y en "
        "las fichas puede ser el vacio deliberado del webhook (capitulo 25); vease el "
        "docstring de esta revision."
    )


def upgrade() -> None:
    bind = op.get_bind()
    _igualar_los_vacios(bind)
    _contar_los_que_no_se_pueden_vaciar(bind)


def downgrade() -> None:
    # A propósito, y explicado en el docstring: no se puede saber qué nulo fue antes un blanco.
    print(
        "[migracion d8b3e5f09a71] Reversion: no se escribe nada. Un NULL que fue '' no se "
        "distingue de uno que siempre fue NULL, y rellenarlos reintroduciria el defecto en "
        "filas que quizas nunca lo tuvieron."
    )
