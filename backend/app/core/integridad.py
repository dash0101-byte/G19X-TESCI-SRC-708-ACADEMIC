"""
Qué rechazó la base, preguntándoselo a la base.

El sistema tiene siete `except IntegrityError` y hasta el capítulo 42 cada uno contestaba
una cosa distinta a la misma pregunta. Dos **preguntaban** —el registro de actividad mira
`_ya_registrado` y vuelve a lanzar si no era un duplicado; el recálculo pregunta
`trabajo_en_curso`— y cuatro **suponían**: «el correo ya existe», «ya existe una cuenta»,
«duplicado» y «ya existía». Suponer funciona mientras la tabla tenga una sola forma de
rechazar una fila, y ninguna de estas la tiene: `leads` tiene una restricción única, dos
claves ajenas y tres columnas obligatorias de texto, así que un asesor que no existe salía
como «El correo 'elena.ruiz@fintechmx.com' ya está registrado en otro prospecto» —el correo
de la propia ficha, que nadie tocó, dentro de una frase sobre un conflicto que no ha
ocurrido—.

Por qué no se lee el mensaje del motor
---------------------------------------
El punto 26 de §6.4 decía que distinguir qué restricción falló obliga a leer el error del
motor, específico de PostgreSQL y de SQLite por separado. Es verdad a medias, y la mitad que
falta cambia el arreglo. Esto es lo que dice SQLite, literal:

* `UNIQUE constraint failed: leads.email`
* `NOT NULL constraint failed: leads.first_name`
* `FOREIGN KEY constraint failed`

La tercera no nombra la columna, ni la tabla, ni el valor: es el caso más probable de los
tres —una clave ajena es lo único de una fila que puede apuntar a algo que ya no está— y es
justo el que el mensaje no permite nombrar. Un arreglo que leyera el texto habría quedado a
medias en el motor de las pruebas y del desarrollo, y distinto en producción.

Así que no se lee el mensaje. Se pregunta a la base cuál de sus reglas no se cumple, con la
lista de reglas sacada de `__table__` —como hizo el capítulo 33 con las columnas
obligatorias y generalizó el 41—, y se contesta eso. Tiene dos ventajas sobre el texto del
motor: no depende del dialecto, y da **el nombre del campo**, que es lo que el mecanismo del
capítulo 40 necesita para pintar el error debajo de él en vez de en el aviso de arriba.

El orden importa: los valores, antes del `rollback`
----------------------------------------------------
Un `rollback` caduca los objetos de la sesión, así que leer `lead.campaign_id` **después**
devuelve lo que hay en la base y no lo que se intentó escribir, que es lo único que explica
el rechazo. Por eso estas funciones reciben un diccionario de valores y no la fila: quien
llama ya lo tiene —`update_data` en la edición— o lo copia antes de intentar el `commit`.
Pedir la fila habría funcionado en las pruebas del alta, donde el objeto es nuevo y conserva
sus valores, y habría leído los valores viejos en la edición sin que nada se pusiera rojo.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

import sqlalchemy as sa
from sqlalchemy.orm import Session

# Las cuatro cosas que pueden haber pasado, y el código con el que se contestan.
#
# Las dos primeras son del cuerpo que llegó y se contestan con un 422 que nombra el campo:
# quien lo envió puede corregirlo. Las dos últimas son conflictos con lo que ya hay y se
# contestan con un 409, que es lo que el sistema ya decía cuando el conflicto era el correo.
OBLIGATORIO = "obligatorio"
INEXISTENTE = "inexistente"
REPETIDO = "repetido"
CARRERA = "carrera"

CODIGO_HTTP = {
    OBLIGATORIO: 422,
    INEXISTENTE: 422,
    REPETIDO: 409,
    CARRERA: 409,
}

# Cómo se llama en castellano lo que hay al otro lado de una clave ajena.
#
# Hace falta porque el mensaje lo lee una persona: «No existe la fila de `users` con ese id»
# es el nombre de la tabla, y el capítulo 40 se ocupó precisamente de que la pantalla dejara
# de enseñar nombres de columnas. La lista se comprueba contra el esquema en
# `tests/test_lo_que_el_motor_rechaza.py`: una tabla nueva con una clave ajena que apunte a
# ella nace en rojo, igual que un token nuevo sin definir en `tokens.test.js`.
NOMBRE_DE_LA_TABLA = {
    "users": "ninguna cuenta",
    "campaigns": "ninguna publicación",
    "leads": "ningún prospecto",
    "score_histories": "ningún historial de puntuación",
}

MOTIVO_DE_LA_CARRERA = (
    "Otra operación modificó estos datos al mismo tiempo. Vuelva a intentarlo."
)


@dataclass(frozen=True)
class Rechazo:
    """Por qué la base no admite esta fila. `campo` es `None` solo en una carrera."""

    clase: str
    campo: Optional[str]
    motivo: str


class LaBaseRechaza(Exception):
    """
    La base rechazó la fila y aquí está por qué, con el campo.

    Es una excepción de dominio y no una `HTTPException` por lo mismo que
    `LeadEmailAlreadyExists`: el repositorio no depende de FastAPI. La capa HTTP la traduce
    con `respuesta()`, que es la única que sabe de códigos.
    """

    def __init__(self, rechazo: Rechazo):
        super().__init__(rechazo.motivo)
        self.rechazo = rechazo


def claves_ajenas(modelo: Any) -> Tuple[Tuple[str, sa.Column], ...]:
    """
    `(columna, columna de destino)` de cada clave ajena de la tabla.

    Se devuelve la columna de destino y no el modelo mapeado: para comprobar si una fila
    existe basta un `SELECT` sobre la tabla, y buscar la clase mapeada obligaría a recorrer
    el registro de SQLAlchemy —lo que hace `derechos_del_titular._modelo_de_tabla`— sin
    ganar nada. Preguntar a la tabla es además lo que hace que esto no caduque: una clave
    ajena nueva entra en la lista el día que se declara.
    """
    return tuple(
        (columna.name, next(iter(columna.foreign_keys)).column)
        for columna in modelo.__table__.columns
        if columna.foreign_keys
    )


def grupos_unicos(modelo: Any) -> Tuple[Tuple[str, ...], ...]:
    """
    Cada restricción única de la tabla, como la tupla de columnas que la forman.

    Las tres formas cuentan, porque las tres las hace cumplir el motor y el esquema usa las
    tres: `unique=True` en la columna (`leads.email`), `UniqueConstraint` y un `Index` con
    `unique=True` (`(regla, lead_id, clave)` de las tareas). Mirar solo la primera —que es lo
    que se ve al leer un modelo de arriba abajo— dejaría fuera las de varias columnas, que
    son justo las que nadie recuerda de memoria.
    """
    grupos = []
    for columna in modelo.__table__.columns:
        if columna.unique:
            grupos.append((columna.name,))
    for restriccion in modelo.__table__.constraints:
        if isinstance(restriccion, sa.UniqueConstraint):
            grupos.append(tuple(columna.name for columna in restriccion.columns))
    for indice in modelo.__table__.indexes:
        if indice.unique:
            grupos.append(tuple(columna.name for columna in indice.columns))
    # Sin repetir y en orden: `leads.email` está declarada `unique=True` y además tiene su
    # índice único, y preguntar dos veces lo mismo no cambia la respuesta pero sí el coste.
    return tuple(sorted(set(grupos)))


def columnas_obligatorias_escribibles(modelo: Any) -> Tuple[str, ...]:
    """
    Las columnas `NOT NULL` que una fila tiene que traer escritas.

    Fuera quedan la clave primaria —la pone el motor— y las que tienen valor por omisión en
    el servidor o en el modelo, porque un `None` en ellas no es lo que la base rechaza: es lo
    que el ORM sustituye antes de insertar.
    """
    return tuple(
        columna.name
        for columna in modelo.__table__.columns
        if not columna.nullable
        and not columna.primary_key
        and columna.default is None
        and columna.server_default is None
    )


def claves_que_no_apuntan_a_nada(
    db: Session, modelo: Any, valores: Mapping[str, Any]
) -> List[Rechazo]:
    """
    Las claves ajenas de `valores` cuyo destino no existe, en el orden de la tabla.

    Es la comprobación que va **antes** de escribir, y la misma que el `except` repite
    después para saber qué pasó. Que las dos salgan de aquí es lo que hace que el 422 diga lo
    mismo lo haya cazado la comprobación o la base: hasta el capítulo 42 el alta no
    comprobaba nada y contestaba un 500, y la edición contestaba un 409 sobre el correo.

    La comprobación **no** está acotada por el alcance de cartera a propósito, igual que la
    del correo en el alta: existir no es lo mismo que poder verse. Si aquí se mirara solo lo
    que quien pide alcanza, un identificador real pero ajeno se diría «no existe», que es una
    respuesta falsa y además cuenta algo —deja saber qué identificadores hay— por el camino.
    """
    rechazos = []
    for columna, destino in claves_ajenas(modelo):
        if columna not in valores:
            continue
        valor = valores[columna]
        if valor is None:
            continue
        existe = db.execute(sa.select(destino).where(destino == valor).limit(1)).first()
        if existe is None:
            rechazos.append(
                Rechazo(
                    clase=INEXISTENTE,
                    campo=columna,
                    motivo=f"No existe {NOMBRE_DE_LA_TABLA[destino.table.name]} con ese identificador.",
                )
            )
    return rechazos


def motivo_del_rechazo(
    db: Session,
    modelo: Any,
    valores: Mapping[str, Any],
    *,
    id_propio: Optional[int] = None,
) -> Rechazo:
    """
    Cuál de las reglas de la tabla no cumple `valores`. Se pregunta a la base.

    Se llama **después** de un `IntegrityError` y de su `rollback`, que es cuando la sesión
    vuelve a poder consultar. El orden de las tres comprobaciones es el de lo que quien envió
    el cuerpo puede arreglar: una columna obligatoria vacía y una clave ajena que no apunta a
    nada son errores del cuerpo (422, con el campo), y un valor repetido es un conflicto con
    otra fila (409). Si dos reglas estuvieran mal a la vez, nombrar la del cuerpo es más útil
    que nombrar el conflicto.

    Cuando no queda ninguna regla incumplida, la respuesta es `CARRERA` y no `None`: la base
    rechazó la fila hace un instante, así que algo pasó, y lo que pasó es que otra transacción
    lo cambió entre el intento y la pregunta. Devolver `None` habría dejado a cada uno de los
    cuatro `except` inventándose qué decir en ese caso, que es exactamente de lo que viene
    este módulo.
    """
    for columna in columnas_obligatorias_escribibles(modelo):
        if columna in valores and valores[columna] is None:
            return Rechazo(
                clase=OBLIGATORIO,
                campo=columna,
                motivo="Este campo no puede quedar vacío.",
            )

    sin_destino = claves_que_no_apuntan_a_nada(db, modelo, valores)
    if sin_destino:
        return sin_destino[0]

    tabla = modelo.__table__
    for grupo in grupos_unicos(modelo):
        if any(columna not in valores or valores[columna] is None for columna in grupo):
            continue
        consulta = sa.select(*tabla.primary_key.columns)
        for columna in grupo:
            consulta = consulta.where(tabla.c[columna] == valores[columna])
        if id_propio is not None:
            # La propia fila no es un duplicado de sí misma: en una edición que no toca el
            # correo, el `SELECT` encuentra la fila que se está editando y diría que el valor
            # ya está cogido.
            consulta = consulta.where(next(iter(tabla.primary_key.columns)) != id_propio)
        if db.execute(consulta.limit(1)).first() is not None:
            return Rechazo(
                clase=REPETIDO,
                campo=grupo[0] if len(grupo) == 1 else None,
                motivo="Ese valor ya está registrado en otro registro.",
            )

    return Rechazo(clase=CARRERA, campo=None, motivo=MOTIVO_DE_LA_CARRERA)


def como_un_renglon_del_422(rechazo: Rechazo) -> List[Dict[str, Any]]:
    """
    El rechazo con la forma exacta que Pydantic da a un error de un validador propio.

    Con esa forma y no con un texto suelto porque es la que el cliente sabe repartir: el
    `detail` de un 422 es una lista de renglones con `loc`, y `erroresDeFormulario.js`
    reparte por `loc` y **reconoce los mensajes de este repositorio por el prefijo**
    `Value error, ` que Pydantic antepone. Un `type: value_error` sin ese prefijo lo tiene
    por mensaje de biblioteca y lo sustituye por una frase vaga, para que el inglés del
    validador de correos no llegue a la pantalla; eso es del capítulo 40 y aquí se respeta en
    vez de añadirle una excepción.

    Es decir: esto no imita un error de validación, **es** uno. Lo único que lo separa de los
    del esquema es que para comprobarlo hay que preguntar a la base, y un esquema no tiene
    sesión.
    """
    return [
        {
            "type": "value_error",
            "loc": ["body", rechazo.campo],
            "msg": f"Value error, {rechazo.motivo}",
            "ctx": {"error": rechazo.motivo},
        }
    ]


def respuesta(rechazo: Rechazo) -> Tuple[int, Any]:
    """
    `(código, detalle)` de un rechazo, lo único que sabe de HTTP en este módulo.

    Un 422 va con sus renglones para que el error aparezca debajo del campo; un 409 va con
    una frase, porque un conflicto con otra fila no es de un campo del formulario y el aviso
    de arriba es su sitio.
    """
    codigo = CODIGO_HTTP[rechazo.clase]
    if codigo == 422 and rechazo.campo:
        return codigo, como_un_renglon_del_422(rechazo)
    return codigo, rechazo.motivo
