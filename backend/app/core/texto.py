"""
Qué es un texto en blanco, y en qué orden se comprueba.

El capítulo 32 decidió que un texto en blanco es ausencia de dato y no la cadena vacía, y el
33 lo aplicó a la edición de una ficha. Lo que ninguno de los dos hizo fue poner la
definición en un sitio: `_texto_o_vacio` vivía en `app.schemas.lead`, `_texto` en
`app.services.integraciones`, y las demás puertas no normalizaban nada. Cuatro entradas y
cuatro respuestas a la misma pregunta.

El orden, que es el hallazgo del capítulo 41
---------------------------------------------
Pydantic tiene dos formas de recortar un texto y **solo una ocurre antes de medirlo**:

* `str_strip_whitespace=True` en la configuración del modelo recorta **antes** de aplicar
  las restricciones declaradas del campo.
* Un `field_validator` que recorte corre **después**.

`UsuarioCreate` tenía lo segundo junto a un `min_length=2`, y en ese orden el mínimo mide lo
que llegó y no lo que se guarda: dos espacios pasaban el mínimo de dos caracteres y se
guardaban como `''`, y `' A '` se guardaba como `'A'`. La comprobación y la normalización
estaban en el orden exacto para que la comprobación no comprobara nada.

El arreglo ya estaba escrito en este repositorio, en una sola puerta: `SolicitudDeInteres`
—el formulario público— lleva `str_strip_whitespace=True` desde el capítulo 34, y era la
única entrada del sistema que rechazaba un nombre de tres espacios. De los 61 campos de
texto de las entradas, 34 guardaban el blanco tal cual, 15 lo normalizaban y 12 lo
rechazaban; los 12 eran esa pantalla y tres listas cerradas.

Por qué recortar antes es mejor que rechazar aparte
----------------------------------------------------
Porque el 422 que sale solo es el bueno. Un `'   '` recortado a `''` choca con el
`min_length` que el campo ya declaraba, y Pydantic responde `string_too_short` **con el
nombre del campo en `loc`**, que es justo lo que el capítulo 40 sabe repartir: el mensaje
aparece debajo del campo, en castellano y con la etiqueta de la pantalla, sin escribir una
línea nueva de traducción. Rechazar el blanco en un validador propio habría dado un error
de modelo, sin campo, que acaba en el aviso de arriba.
"""
from typing import Annotated, Any, FrozenSet, List, Optional

import sqlalchemy as sa
from pydantic import ConfigDict, StringConstraints

# La configuración que lleva **toda** entrada con texto. Recorta antes de medir, que es la
# mitad del arreglo; la otra mitad es que la lleven todas.
#
# Se declara aquí y no se copia en cada esquema para que «¿esta entrada normaliza?» tenga una
# respuesta que se puede buscar, y para que una prueba pueda recorrer los esquemas y exigirla
# (`tests/test_un_blanco_no_es_un_dato.py`).
ENTRADA_DE_TEXTO = ConfigDict(str_strip_whitespace=True)

# Lo que NO se recorta.
#
# Una contraseña es la única cadena del sistema donde un espacio del principio o del final es
# parte del secreto, y recortarla tendría dos consecuencias: la cuenta que se creó con
# espacios dejaría de poder entrar, y la política de `app.core.passwords` —que rechaza
# explícitamente una contraseña con espacios en los bordes, porque «se pierden al copiarla y
# luego no coincide»— se quedaría sin nada que rechazar, aceptando en silencio lo que decía
# prohibir. Las restricciones del campo pesan más que la configuración del modelo, así que
# esto se declara en el campo y la configuración de arriba no le llega.
Contrasena = Annotated[str, StringConstraints(strip_whitespace=False)]


def texto_o_nada(valor: Any) -> Optional[str]:
    """
    Un texto, o `None` si lo que hay es ausencia de dato.

    Nació como `_texto_o_vacio` en `app.schemas.lead` (capítulo 32 para el país, 33 para el
    resto de la edición) y se mudó aquí en el 41, cuando hizo falta la cuarta vez. La copia
    que `app.services.integraciones` tenía con otro nombre —`_texto`— desaparece: mientras
    cada puerta tuvo su definición de «vacío», mantenerlas de acuerdo dependía de que quien
    tocara una se acordara de las otras.

    Un diccionario o una lista donde se esperaba texto devuelven `None` y no su `repr`. Viene
    de la copia de `integraciones`, que lee cargas de sistemas ajenos: `{'city': {}}` es un
    campo que ese sistema no supo rellenar, y guardar «{}» en la ciudad sería convertir su
    hueco en nuestro dato.
    """
    if valor is None or isinstance(valor, (dict, list)):
        return None
    texto = str(valor).strip()
    return texto or None


def en_blanco(valor: Any) -> bool:
    """
    ¿Es este valor ausencia de dato?

    Solo `None` y el texto que no sobrevive a un recorte. **No** el cero ni el falso: un
    presupuesto de cero es una cifra y una cuenta desactivada es un estado, y los dos son
    falsos para `if`. Es la razón de que esto sea una función y no un `not valor` escrito en
    cada sitio; el día que `is_active=False` pasara por uno de esos `not`, desactivar una
    cuenta respondería «este campo no puede quedar vacío».
    """
    if valor is None:
        return True
    return isinstance(valor, str) and not valor.strip()


def campos_sin_los_que_no_existe(modelo: Any) -> FrozenSet[str]:
    """
    Qué columnas de una tabla no admiten vacío, preguntándoselo a la tabla.

    Generaliza `_campos_que_no_admiten_vacio`, que el capítulo 33 escribió para `Lead` y solo
    para `Lead`. Que fuera una función de una sola tabla no se veía como un límite, y lo era:
    la misma edición parcial existe para `Campaign` y para `User`, y en las dos un `null`
    explícito sobre una columna obligatoria llegaba al `commit` y salía como 500. El 422 que
    nombra el campo existía para los prospectos desde el 33 y para nadie más.

    `id` y las columnas calculadas entran en el conjunto y no estorban: nunca están en un
    esquema de entrada, así que el cruce con lo que el cliente envió no las alcanza.
    """
    return frozenset(columna.name for columna in modelo.__table__.columns if not columna.nullable)


def columnas_de_texto(modelo: Any, *, obligatorias: bool) -> List[str]:
    """
    Las columnas de texto de una tabla, separadas por si admiten vacío.

    La usan la prueba de la guarda y la de la migración. Se pregunta por el tipo y no por una
    lista escrita: una columna de texto nueva aparece aquí el día que se declara, que es el
    único momento en que alguien está mirando.
    """
    return [
        columna.name
        for columna in modelo.__table__.columns
        if isinstance(columna.type, (sa.String, sa.Text))
        and (not columna.nullable) == obligatorias
    ]


def exigir_texto(valor: Optional[str]) -> str:
    """
    Validador para un campo de texto que la fila no admite vacío.

    Existe además del `min_length` de cada campo porque los dos sirven para cosas distintas:
    el `min_length` dice cuánto texto hace falta —y da el mensaje preciso, «tiene que tener al
    menos dos caracteres»—, y esto dice que el campo no puede ir vacío aunque nadie se haya
    acordado de declarar un mínimo. `leads.source` no tenía mínimo: la columna es `NOT NULL`
    y un `''` en el alta respondía 201 mientras el mismo `''` en la edición respondía 422.

    El mensaje no dice qué campo es: lo dice el `loc` del 422, y el capítulo 40 lo pone
    debajo del campo con la etiqueta que la pantalla usa. Repetir el nombre de la columna en
    el texto es lo que hacía que la pantalla dijera «source».
    """
    if en_blanco(valor):
        raise ValueError("Este campo no puede quedar vacío.")
    return valor


def vacios_prohibidos(enviados: Any, obligatorios: FrozenSet[str]) -> List[str]:
    """
    Los campos que llegaron vacíos y la fila no admite vacíos, en orden.

    `enviados` es el propio esquema: se recorre `model_fields_set`, que dice qué campos
    **vinieron en el cuerpo**, y no qué campos valen `None`. La diferencia es el capítulo 33
    entero: un campo ausente y un campo enviado a nulo llegaban indistinguibles al
    repositorio, y el repositorio resolvía el empate ignorando los dos.

    Lo que el 41 añade es que el vacío también puede ser un blanco. El validador del 33 solo
    mira `None`, así que `first_name: '   '` pasaba por la edición y por el alta —tres
    espacios en una columna que la tabla declara indispensable— y el mensaje que ese
    validador escribió, «La ficha no existe sin estos campos», no se aplicaba al único caso
    en que la ficha, efectivamente, no los tenía.
    """
    return sorted(
        campo
        for campo in enviados.model_fields_set
        if campo in obligatorios and en_blanco(getattr(enviados, campo, None))
    )
