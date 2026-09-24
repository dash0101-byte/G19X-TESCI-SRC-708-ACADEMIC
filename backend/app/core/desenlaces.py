"""
El vocabulario del desenlace: cómo acabó un prospecto y por qué (capítulo 30).

Lo que pasaba
-------------
El bucle de realimentación existía desde el capítulo 18 y estaba **vacío por un extremo**.
`feedback_dataset.py` sabe leer la instantánea de entrada de cada prospecto cerrado y
etiquetarla; lo que no había era forma de cerrar un prospecto diciendo algo. La etiqueta
salía del estado (`WON` / `LOST`) y nada más: ni cuándo se cerró de verdad, ni por qué, ni
de qué tamaño fue el trato. El sistema podía decir *cuántos* se ganaban y era incapaz de
decir *qué se pierde por precio y qué se pierde por plazo*, que es la única de las dos
preguntas que cambia lo que alguien hace mañana.

Por qué una lista cerrada y no un campo de notas
------------------------------------------------
Un cuadro de texto libre es lo más fácil de programar y lo único que no se puede contar.
«Precio», «muy caro», «presupuesto», «no le cuadraba el costo» son cuatro filas distintas
en cualquier agrupación y el mismo motivo para cualquier persona. Con treinta cierres el
panel enseñaría veintiocho motivos de uno.

Hay además una razón que no es de conveniencia: un texto libre sobre una persona acaba
llevando datos de esa persona —su nombre, el de su jefe, lo que dijo por teléfono— a una
tabla que viaja a los respaldos, a la exportación del titular y, el día que se reentrene,
a un CSV. Este proyecto lleva desde el capítulo 21 quitando texto libre de donde no hace
falta (de los mensajes solo se guarda el tipo y la dirección, nunca el contenido). Sería
raro reintroducirlo justo en el registro que existe para alimentar al modelo.

Por qué «Otro motivo» está en las dos listas
---------------------------------------------
Porque una lista cerrada sin salida no produce datos limpios: produce datos falsos. Quien
no encuentra su caso elige el más parecido, y a partir de ahí «precio» significa «precio o
cualquier otra cosa». Con una salida explícita, lo que no encaja se ve —y se cuenta aparte
en el panel—: si «otro» crece, la lista está mal y hay que discutirla, que es exactamente
la conversación que un cuadro de texto libre impide tener.

**«Otro» no abre un cuadro de texto.** Es una casilla como las demás. Lo que se gana con
ella es saber cuántas veces la lista no sirvió, no una explicación caso por caso.

Por qué el tamaño del acuerdo va por tramos
--------------------------------------------
Una cifra exacta necesita moneda, impuestos, duración del contrato y una definición de qué
se cuenta como «el acuerdo» para significar algo; sin todo eso es un número que alguien
escribió de memoria y que después se suma como si fuera contabilidad. Un tramo es algo que
una persona puede contestar con honestidad el día del cierre.

Y hay un límite explícito del capítulo: **con esto no se hace ninguna previsión de
ingresos**. El tramo está para poder decir «los ganados por recomendación son los de arriba
del todo», no para multiplicar por una tasa de conversión y enseñar un pronóstico. Por eso
existe `NO_CONSTA`: obligar a elegir un tramo cuando todavía no se sabe sería fabricar la
cifra que este módulo evita.

Lo que este módulo NO decide
----------------------------
El **peso** de los motivos. Ninguno vale más que otro, ninguno suma ni resta score, y
ninguno entra al modelo como variable. El motivo es una etiqueta para leer el panel, no una
señal: inventar que «eligió a otro» vale el doble que «no era el momento» sería exactamente
la clase de número que este proyecto lleva veinticuatro capítulos quitando.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- resultados
GANADO = "ganado"
PERDIDO = "perdido"

RESULTADOS: Tuple[str, ...] = (GANADO, PERDIDO)

ETIQUETAS_DE_RESULTADO: Dict[str, str] = {
    GANADO: "Ganado",
    PERDIDO: "Perdido",
}

# La etapa del prospecto que corresponde a cada resultado. Se escribe como texto y no como
# `LeadStatus` porque `app.models.entities` importa de `app.core`, nunca al revés: un
# `import` en esta dirección cerraría el círculo y ninguno de los dos módulos cargaría.
ETAPA_DEL_RESULTADO: Dict[str, str] = {
    GANADO: "WON",
    PERDIDO: "LOST",
}
RESULTADO_DE_LA_ETAPA: Dict[str, str] = {etapa: r for r, etapa in ETAPA_DEL_RESULTADO.items()}

# Las etapas que este capítulo cierra, y que por tanto **exigen** un desenlace registrado.
ETAPAS_CERRADAS: Tuple[str, ...] = tuple(ETAPA_DEL_RESULTADO.values())

# Las etapas en las que el motor de reglas deja de proponer trabajo.
#
# `UNQUALIFIED` está aquí y **no** en `ETAPAS_CERRADAS`, y la diferencia es deliberada.
# Nadie debe recibir la tarea de llamar a alguien a quien ya se descartó, así que el
# seguimiento para; pero descartar no es cerrar un trato, no tiene lista de motivos propia
# y exigirle uno obligaría a inventar el motivo de los descartes anteriores a que la lista
# existiera. El extractor del dataset sigue contándolo como negativo, como desde el
# capítulo 18: descartar es una decisión tomada, no una ausencia de decisión.
ETAPAS_SIN_SEGUIMIENTO: Tuple[str, ...] = ETAPAS_CERRADAS + ("UNQUALIFIED",)


@dataclass(frozen=True)
class Motivo:
    """
    Por qué acabó así. La clave es lo que se guarda y se cuenta; la etiqueta, lo que se lee.

    Es el mismo criterio que las reglas de la agenda (capítulo 28), las necesidades de una
    publicación (capítulo 26) y las redes de difusión (capítulo 27): cambiar cómo se llama
    algo en la pantalla no puede exigir una migración de datos.
    """
    clave: str
    etiqueta: str
    resultado: str
    # Para el panel y para quien rellena el formulario: qué caso cubre exactamente.
    descripcion: str


# Claves compartidas entre las dos listas donde el motivo es **el mismo eje**. «Precio» y
# «plazo» se ganan y se pierden, y que compartan clave es lo que permite ponerlos uno al
# lado del otro en el panel: «doce ganados por precio, treinta perdidos por precio» dice
# algo; dos claves distintas para lo mismo lo habrían hecho imposible de cruzar.
PRECIO = "precio"
PLAZO = "plazo"
PERFIL = "perfil"
OTRO = "otro"

# Solo de los perdidos.
NO_ERA_EL_MOMENTO = "no_era_el_momento"
ELIGIO_A_OTRO = "eligio_a_otro"
NO_CONTESTO = "no_contesto"
SIN_PRESUPUESTO = "sin_presupuesto"
LO_RESOLVIO_DENTRO = "lo_resolvio_dentro"

# Solo de los ganados.
RECOMENDACION = "recomendacion"
ACOMPANAMIENTO = "acompanamiento"

_MOTIVOS_GANADOS: Tuple[Motivo, ...] = (
    Motivo(PRECIO, "Precio", GANADO, "Nuestra propuesta económica fue la que encajó."),
    Motivo(PLAZO, "Plazo", GANADO, "Llegábamos con los tiempos que el cliente necesitaba."),
    Motivo(PERFIL, "Perfil", GANADO, "Los perfiles presentados eran los que buscaba."),
    Motivo(RECOMENDACION, "Recomendación", GANADO, "Llegó recomendado o ya nos conocía."),
    Motivo(ACOMPANAMIENTO, "Acompañamiento", GANADO, "El seguimiento y la atención inclinaron la decisión."),
    Motivo(OTRO, "Otro motivo", GANADO, "Ninguno de los anteriores. Se cuenta aparte en el panel."),
)

_MOTIVOS_PERDIDOS: Tuple[Motivo, ...] = (
    Motivo(PRECIO, "Precio", PERDIDO, "El precio no encajó con lo que el cliente esperaba."),
    Motivo(PLAZO, "Plazo", PERDIDO, "No llegábamos con los tiempos que necesitaba."),
    Motivo(PERFIL, "Perfil", PERDIDO, "Los perfiles no eran los que buscaba."),
    Motivo(NO_ERA_EL_MOMENTO, "No era el momento", PERDIDO, "El proyecto se aplazó o se congeló."),
    Motivo(ELIGIO_A_OTRO, "Eligió a otro", PERDIDO, "Se decidió por otro proveedor."),
    Motivo(NO_CONTESTO, "Dejó de contestar", PERDIDO, "Se perdió el contacto sin una respuesta."),
    Motivo(SIN_PRESUPUESTO, "Sin presupuesto", PERDIDO, "No hubo presupuesto aprobado."),
    Motivo(LO_RESOLVIO_DENTRO, "Lo resolvió por dentro", PERDIDO, "Lo cubrió con su propio equipo."),
    Motivo(OTRO, "Otro motivo", PERDIDO, "Ninguno de los anteriores. Se cuenta aparte en el panel."),
)

# El orden de la lista es el orden del formulario y el del panel. Explícito y no el de un
# diccionario: el orden en que se ofrecen las opciones cambia cuál se elige, así que es una
# decisión y no un efecto secundario de cómo se escribió el código.
MOTIVOS: Dict[str, Tuple[Motivo, ...]] = {
    GANADO: _MOTIVOS_GANADOS,
    PERDIDO: _MOTIVOS_PERDIDOS,
}

_POR_CLAVE: Dict[str, Dict[str, Motivo]] = {
    resultado: {motivo.clave: motivo for motivo in lista}
    for resultado, lista in MOTIVOS.items()
}

# --------------------------------------------------------------------------- los tramos
HASTA_100K = "hasta_100k"
DE_100K_A_500K = "de_100k_a_500k"
DE_500K_A_1M = "de_500k_a_1m"
MAS_DE_1M = "mas_de_1m"
NO_CONSTA = "no_consta"


@dataclass(frozen=True)
class Tramo:
    clave: str
    etiqueta: str


# En pesos mexicanos, que es la moneda del país por defecto de una ficha (`Lead.country`).
# La moneda va escrita en la etiqueta y no en una columna: un tramo con moneda variable
# obligaría a convertir para poder agrupar, y convertir exige un tipo de cambio con fecha,
# que es precisamente el tipo de cifra que este capítulo se niega a inventar.
TRAMOS: Tuple[Tramo, ...] = (
    Tramo(HASTA_100K, "Hasta 100 000 MXN"),
    Tramo(DE_100K_A_500K, "De 100 000 a 500 000 MXN"),
    Tramo(DE_500K_A_1M, "De 500 000 a 1 000 000 MXN"),
    Tramo(MAS_DE_1M, "Más de 1 000 000 MXN"),
    # La salida honesta. Un cierre en el que todavía no se sabe el alcance existe, y
    # obligar a elegir un tramo produciría una cifra inventada con apariencia de dato.
    Tramo(NO_CONSTA, "Todavía no consta"),
)

_TRAMOS_POR_CLAVE: Dict[str, Tramo] = {tramo.clave: tramo for tramo in TRAMOS}

# ------------------------------------------------------- el mínimo del reentrenamiento
#
# Viven aquí y no en `ml_pipeline`, aunque sea el extractor quien los aplica, por la misma
# razón que el vector del modelo vive en `app/core/vector_del_modelo.py`: el backend no
# puede importar del pipeline —la dependencia va en el otro sentido— y el contador que
# enseña el panel tiene que exigir **exactamente** los mismos mínimos que el extractor.
# Dos copias del número se habrían desincronizado el día que alguien subiera uno, y el
# panel diría «ya se puede reentrenar» mientras el extractor se niega.
#
# Por debajo de estos números reentrenar es contraproducente: con unas decenas de ejemplos
# el modelo memoriza a los clientes concretos que cerraron ese trimestre.
MINIMO_DE_CASOS = 200
MINIMO_POR_CLASE = 50


# --------------------------------------------------------------------------- consultas
def es_resultado(valor: Optional[str]) -> bool:
    return (valor or "") in ETIQUETAS_DE_RESULTADO


def motivos_de(resultado: str) -> List[Motivo]:
    """Las opciones de este resultado, en el orden en que se ofrecen."""
    return list(MOTIVOS.get(resultado, ()))


def es_motivo_de(resultado: Optional[str], clave: Optional[str]) -> bool:
    """¿Es este un motivo de la lista cerrada de ese resultado?"""
    return (clave or "") in _POR_CLAVE.get(resultado or "", {})


def etiqueta_de_motivo(resultado: Optional[str], clave: Optional[str]) -> str:
    """
    Cómo se llama este motivo en la pantalla.

    Un motivo que este código no conoce —una fila escrita por una versión posterior, o por
    una lista que se recortó— se enseña por su clave en lugar de dejar un hueco. Es lo
    mismo que hace la agenda con una regla desconocida: un hueco parece un dato perdido.
    """
    motivo = _POR_CLAVE.get(resultado or "", {}).get(clave or "")
    return motivo.etiqueta if motivo is not None else (clave or "")


def es_tramo(clave: Optional[str]) -> bool:
    return (clave or "") in _TRAMOS_POR_CLAVE


def etiqueta_de_tramo(clave: Optional[str]) -> str:
    tramo = _TRAMOS_POR_CLAVE.get(clave or "")
    return tramo.etiqueta if tramo is not None else (clave or "")


def etiqueta_de_resultado(resultado: Optional[str]) -> str:
    return ETIQUETAS_DE_RESULTADO.get(resultado or "", resultado or "")


def tasa(parte: int, total: int) -> Optional[float]:
    """
    Porcentaje con una decimal, o `None` cuando no hay base.

    `None` y no `0.0`: «ninguno de cero» y «ninguno de cuarenta» son cosas distintas, y una
    tasa de cero sobre una base vacía es la forma más fácil de convencer a alguien de algo
    que los datos no dicen. Es el mismo criterio que la tasa de envío de las publicaciones.
    """
    return round(100.0 * parte / total, 1) if total else None


__all__ = [
    "ACOMPANAMIENTO",
    "DE_100K_A_500K",
    "DE_500K_A_1M",
    "ELIGIO_A_OTRO",
    "ETAPAS_CERRADAS",
    "ETAPAS_SIN_SEGUIMIENTO",
    "ETAPA_DEL_RESULTADO",
    "ETIQUETAS_DE_RESULTADO",
    "GANADO",
    "HASTA_100K",
    "LO_RESOLVIO_DENTRO",
    "MAS_DE_1M",
    "MINIMO_DE_CASOS",
    "MINIMO_POR_CLASE",
    "MOTIVOS",
    "Motivo",
    "NO_CONSTA",
    "NO_CONTESTO",
    "NO_ERA_EL_MOMENTO",
    "OTRO",
    "PERDIDO",
    "PERFIL",
    "PLAZO",
    "PRECIO",
    "RECOMENDACION",
    "RESULTADOS",
    "RESULTADO_DE_LA_ETAPA",
    "SIN_PRESUPUESTO",
    "TRAMOS",
    "Tramo",
    "es_motivo_de",
    "es_resultado",
    "es_tramo",
    "etiqueta_de_motivo",
    "etiqueta_de_resultado",
    "etiqueta_de_tramo",
    "motivos_de",
    "tasa",
]
