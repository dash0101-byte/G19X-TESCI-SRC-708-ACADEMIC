"""el pais deja de suponerse, telefonos de asesor en E.164 y los ceros de ingresos a vacio

Capítulo 32, «La deuda que muerde». Tres restos que arrastraban desde los capítulos 21, 24
y 25, y que tienen en común la misma forma: en la base hay un valor donde no hubo un dato.

1. `leads.country` deja de ser obligatoria
--------------------------------------------
La columna se declaraba `NOT NULL` con «México» por defecto, así que toda ficha que llegaba
sin país salía con país. No lo escribía nadie: lo escribía la ausencia de nadie. Y una vez
en la fila es indistinguible del país de quien sí lo eligió, que es lo que convierte una
suposición en un problema y no en un valor por defecto cómodo.

El país no puntúa: no está en `COLUMNAS_DEL_MODELO` ni lo mira la regla heurística. Lo que
se corrige no es una predicción, es lo que la ficha AFIRMA de una persona.

La migración de datos, y por qué toca tan poco
-----------------------------------------------
Solo se vacían las fichas de las que consta que **nadie indicó el país**, y hay exactamente
un conjunto del que eso se puede demostrar: las que creó la **página de interés**. Su
formulario no pregunta el país —`construir_evento` nunca lo manda— y su fuente está marcada
`actualiza_prospecto=False`, así que tampoco pudo escribirlo una entrega posterior. Si la
primera actividad de una ficha es `pagina_de_interes` y su país es «México», ese «México»
lo puso el valor por defecto de la columna y no una persona.

Del resto NO se puede distinguir, y por eso no se tocan:

* **El alta del panel** enseñaba el campo relleno con «México». Quien dio de alta la ficha
  lo tuvo delante y lo dejó estar. Es una elección débil, pero es una elección, y la base
  no guarda si el campo se tocó.
* **El CRM y los formularios** pueden mandar `country` o no mandarlo. Lo que llegó y lo que
  se rellenó por defecto acabaron en la misma columna sin marca que los separe.
* **La bitácora no ayuda.** Anota que se creó una ficha, no el cuerpo con el que se creó.

Vaciar esas dos familias habría sido sustituir una suposición por otra —«nadie eligió
México»— sobre las fichas de las que justamente no se sabe. Se quedan como están, y a
partir de esta revisión ninguna ficha nueva entra en esa ambigüedad.

2. `users.phone` en E.164
---------------------------
El capítulo 21 normalizó el teléfono de los prospectos y se olvidó del de los asesores. Se
aplica ahora la misma función, con la misma copia local de `app.core.telefono` que usó
aquella migración y por el mismo motivo: una migración no importa código de la aplicación,
porque ese código puede cambiar después y la migración tiene que seguir haciendo lo que
hizo el día que se escribió.

3. Los ceros de ingresos
--------------------------
Desde el capítulo 24 ni el alta ni la API ni la ingesta escriben cero cuando no hay cifra:
escriben vacío. Los ceros anteriores se quedaron, y `ingresos_o_ausente` ya los lee como
ausentes —ninguna empresa a la que se vende esto factura cero—, así que el modelo nunca los
creyó. Quien sí los creía era la ficha, que los enseñaba como «0». Esto alinea la base con
la lectura que ya se hacía de ella.

La reversión
-------------
`downgrade()` devuelve el esquema, no los datos, y conviene decir exactamente qué recupera:

* **El país.** Para volver a poner la columna `NOT NULL` hay que rellenar los vacíos con
  algo, y el único valor posible es «México». Es decir: **la reversión vuelve a suponer**,
  también sobre las fichas que nunca tuvieron país. No hay forma de evitarlo con una
  columna obligatoria; se escribe aquí para que quien revierta sepa qué está firmando.
* **Los teléfonos** no se des-normalizan. «+525512345678» es el mismo número que «55 1234
  5678» y la forma anterior no está guardada en ninguna parte. Revertir el esquema no
  desanda un cambio de formato, y fingir que sí exigiría inventar la forma antigua.
* **Los ceros de ingresos** no vuelven. Escribir cero en las fichas sin cifra sería
  reintroducir a mano el defecto del capítulo 24, y en fichas que quizá nunca lo tuvieron.
"""
from typing import Optional, Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a4c8d1e70f39"
down_revision: Union[str, None] = "c1d9f4b72a08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# La fuente cuyo formulario no pregunta el país. El nombre es el de `FUENTES` en
# `registro_de_actividad`; se escribe literal y no se importa, como el normalizador.
FUENTE_DE_LA_PAGINA = "pagina_de_interes"
PAIS_SUPUESTO = "México"

# Vacía el país de las fichas cuya PRIMERA actividad la registró la página de interés, es
# decir, las que creó ella. `MIN(id)` y no la fecha: la actividad se escribe en la misma
# transacción que la ficha, y dos actividades pueden compartir `occurred_at` al milisegundo.
#
# Un literal entero, sin composición: los dos únicos valores variables son parámetros
# enlazados, y escribir la subconsulta aparte para interpolarla obligaría a explicar en cada
# revisión por qué esa interpolación es inocua.
_VACIAR_EL_PAIS_SUPUESTO = """
    UPDATE leads
       SET country = NULL
     WHERE country = :pais
       AND id IN (SELECT la.lead_id
                    FROM lead_activities AS la
                   WHERE la.source = :fuente
                     AND la.id = (SELECT MIN(la2.id)
                                    FROM lead_activities AS la2
                                   WHERE la2.lead_id = la.lead_id))
"""


def _e164(texto: str) -> Optional[str]:
    """
    Copia de `app.core.telefono.normalizar_telefono` tal como es en esta fase, igual que en
    la migración `e3a9c41d7b25`, que hizo lo mismo con el teléfono de los prospectos.
    """
    import phonenumbers

    try:
        numero = phonenumbers.parse(texto, "MX")
    except phonenumbers.NumberParseException:
        return None
    if numero.country_code == 52:
        nacional = str(numero.national_number)
        if len(nacional) == 11 and nacional.startswith("1"):
            numero = phonenumbers.parse("+52" + nacional[1:], None)
    if not phonenumbers.is_valid_number(numero):
        return None
    return phonenumbers.format_number(numero, phonenumbers.PhoneNumberFormat.E164)


def _vaciar_el_pais_supuesto(bind) -> None:
    resultado = bind.execute(
        sa.text(_VACIAR_EL_PAIS_SUPUESTO),
        {"pais": PAIS_SUPUESTO, "fuente": FUENTE_DE_LA_PAGINA},
    )
    restantes = bind.execute(
        sa.text("SELECT COUNT(*) FROM leads WHERE country = :pais"), {"pais": PAIS_SUPUESTO}
    ).scalar()
    print(
        f"[migracion a4c8d1e70f39] Pais: {resultado.rowcount} fichas de la pagina de interes "
        f"pasadas a vacio; quedan {restantes} con «{PAIS_SUPUESTO}» escrito, de las que no "
        "consta si lo eligio alguien (vease el docstring)."
    )


def _normalizar_telefonos_de_asesores(bind) -> None:
    filas = bind.execute(sa.text("SELECT id, phone FROM users WHERE phone IS NOT NULL")).fetchall()
    normalizados = vaciados = sin_forma = 0
    for usuario_id, telefono in filas:
        texto = (telefono or "").strip()
        if not texto:
            bind.execute(sa.text("UPDATE users SET phone = NULL WHERE id = :id"), {"id": usuario_id})
            vaciados += 1
            continue
        e164 = _e164(texto)
        if e164 is None:
            # Se deja como estaba, igual que hizo `e3a9c41d7b25` con los prospectos: un
            # numero que no se entiende puede seguir siendo la unica forma de localizar a
            # esa persona, y borrarlo seria perder el dato en lugar de corregirlo.
            sin_forma += 1
            continue
        if e164 != telefono:
            bind.execute(
                sa.text("UPDATE users SET phone = :telefono WHERE id = :id"),
                {"telefono": e164, "id": usuario_id},
            )
            normalizados += 1
    print(
        f"[migracion a4c8d1e70f39] Telefonos de asesor: {normalizados} normalizados a E.164, "
        f"{vaciados} vacios pasados a NULL, {sin_forma} sin forma de numero (se dejan)."
    )


def _ingresos_en_cero_a_vacio(bind) -> None:
    resultado = bind.execute(sa.text("UPDATE leads SET annual_revenue = NULL WHERE annual_revenue = 0"))
    print(
        f"[migracion a4c8d1e70f39] Ingresos: {resultado.rowcount} ceros pasados a vacio. "
        "El extractor ya los leia como ausentes; ahora la ficha tampoco los enseña como cifra."
    )


def upgrade() -> None:
    bind = op.get_bind()

    with op.batch_alter_table("leads", schema=None) as batch_op:
        batch_op.alter_column(
            "country",
            existing_type=sa.String(length=100),
            nullable=True,
        )

    _vaciar_el_pais_supuesto(bind)
    _normalizar_telefonos_de_asesores(bind)
    _ingresos_en_cero_a_vacio(bind)


def downgrade() -> None:
    bind = op.get_bind()

    # Volver a suponer, porque la columna vuelve a ser obligatoria. Está escrito arriba y
    # se repite aquí: esta línea escribe «México» también en fichas que nunca tuvieron país.
    rellenadas = bind.execute(
        sa.text("UPDATE leads SET country = :pais WHERE country IS NULL"), {"pais": PAIS_SUPUESTO}
    ).rowcount
    print(
        f"[migracion a4c8d1e70f39] Reversion: {rellenadas} fichas sin pais reciben "
        f"«{PAIS_SUPUESTO}» para poder restaurar la restriccion NOT NULL."
    )

    with op.batch_alter_table("leads", schema=None) as batch_op:
        batch_op.alter_column(
            "country",
            existing_type=sa.String(length=100),
            nullable=False,
        )
