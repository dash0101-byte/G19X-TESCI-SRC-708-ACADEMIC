"""
El vocabulario de lo que hay que hacer hoy: reglas, estados de una tarea y de un aviso.

Por qué un módulo de vocabulario y no cadenas sueltas
-----------------------------------------------------
Una tarea la crea el motor de reglas, la guarda el modelo, la valida el esquema, la filtra
el endpoint y la pinta el cliente. Cinco sitios escribiendo `"primer_contacto"` a mano son
cinco sitios donde una errata pasa las pruebas: el motor crearía tareas que el endpoint no
sabe filtrar, y nadie recibiría un error. Aquí están las claves una sola vez, y
`REGLAS`/`ESTADOS_DE_TAREA` permiten comprobar de golpe que no se inventó ninguna.

Por qué la clave y la etiqueta van separadas
--------------------------------------------
Lo que se guarda en la base es la **clave** (`primer_contacto`), estable, y lo que lee una
persona es la **etiqueta** («Primer contacto»), que puede cambiar sin migrar nada. Es el
mismo criterio que las necesidades de una publicación (capítulo 26) y las redes de difusión
(capítulo 27): la clave es lo que se cuenta, la etiqueta lo que se enseña.

Lo que este módulo NO decide
----------------------------
Los plazos. Viven en `app/core/config.py` con su mínimo, como los de conservación
(capítulo 22), porque son configuración de la instalación y no vocabulario del dominio.
"""
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class Regla:
    """
    Una regla del motor.

    `crea` dice qué produce —una tarea, un aviso o las dos cosas— y se usa para comprobar
    que la bitácora de cada ejecución cuadra con lo que la regla dice de sí misma.
    """
    clave: str
    etiqueta: str
    # Qué produce: "tarea", "aviso" o "ambos".
    crea: str
    # Para quién es lo que produce: "asesor" o "lider".
    para: str
    # Una frase para la pantalla y para el reporte. Sin datos de nadie.
    descripcion: str


# --- Claves de las reglas --------------------------------------------------------------
# Se escriben en `tareas.regla` y en `avisos.regla`; cambiarlas exige una migración de datos.
PRIMER_CONTACTO = "primer_contacto"
HOT_SIN_CONTACTO = "hot_sin_contacto"
HOT_SIN_CONTACTO_LIDER = "hot_sin_contacto_lider"
VOLVER_A_LLAMAR = "volver_a_llamar"
RECORDATORIO_DE_REUNION = "recordatorio_de_reunion"
PROSPECTO_DORMIDO = "prospecto_dormido"

CREA_TAREA = "tarea"
CREA_AVISO = "aviso"
CREA_AMBOS = "ambos"

PARA_ASESOR = "asesor"
PARA_LIDER = "lider"

REGLAS: Dict[str, Regla] = {
    regla.clave: regla
    for regla in (
        Regla(
            clave=PRIMER_CONTACTO,
            etiqueta="Primer contacto",
            crea=CREA_TAREA,
            para=PARA_ASESOR,
            descripcion="Al asignar un prospecto, su asesor tiene que hablar con él.",
        ),
        Regla(
            clave=HOT_SIN_CONTACTO,
            etiqueta="HOT sin contactar",
            crea=CREA_AVISO,
            para=PARA_ASESOR,
            descripcion="Un prospecto HOT lleva demasiado tiempo sin que nadie lo contacte.",
        ),
        Regla(
            clave=HOT_SIN_CONTACTO_LIDER,
            etiqueta="HOT sin contactar (aviso al líder)",
            crea=CREA_AVISO,
            para=PARA_LIDER,
            descripcion="El aviso al asesor no bastó: el HOT sigue sin contacto y lo ve el líder.",
        ),
        Regla(
            clave=VOLVER_A_LLAMAR,
            etiqueta="Volver a llamar",
            crea=CREA_TAREA,
            para=PARA_ASESOR,
            descripcion="La última llamada no la contestó nadie; se vuelve a intentar.",
        ),
        Regla(
            clave=RECORDATORIO_DE_REUNION,
            etiqueta="Reunión mañana",
            crea=CREA_TAREA,
            para=PARA_ASESOR,
            descripcion="Recordatorio la víspera de una reunión ya agendada.",
        ),
        Regla(
            clave=PROSPECTO_DORMIDO,
            etiqueta="Prospecto dormido",
            # Avisa, y además deja la marca en la ficha. La marca no es una tarea: nadie
            # tiene que hacer nada con ella, es un hecho sobre el prospecto.
            crea=CREA_AVISO,
            para=PARA_ASESOR,
            descripcion="Nadie ha tocado este prospecto en mucho tiempo; queda marcado como dormido.",
        ),
    )
}

# El orden en que corre el motor. Explícito y no el de un diccionario: el aviso al líder
# tiene que correr DESPUÉS del aviso al asesor, porque solo avisa cuando aquel ya se mandó.
ORDEN_DE_LAS_REGLAS: Tuple[str, ...] = (
    PRIMER_CONTACTO,
    VOLVER_A_LLAMAR,
    RECORDATORIO_DE_REUNION,
    HOT_SIN_CONTACTO,
    HOT_SIN_CONTACTO_LIDER,
    PROSPECTO_DORMIDO,
)

# --- Estados de una tarea --------------------------------------------------------------
ABIERTA = "abierta"
# La cerró una persona: dice que ya la hizo.
HECHA = "hecha"
# La cerró el sistema porque ocurrió lo que la tarea esperaba: una llamada contestada cierra
# «volver a llamar» sin que nadie la marque. Se distingue de `hecha` a propósito: «lo hice»
# y «pasó» no son lo mismo, y el informe de mañana querrá poder separarlos.
CUMPLIDA = "cumplida"

ESTADOS_DE_TAREA: Tuple[str, ...] = (ABIERTA, HECHA, CUMPLIDA)
ESTADOS_CERRADOS: Tuple[str, ...] = (HECHA, CUMPLIDA)

ETIQUETAS_DE_ESTADO: Dict[str, str] = {
    ABIERTA: "Pendiente",
    HECHA: "Hecha",
    CUMPLIDA: "Se resolvió sola",
}


def etiqueta_de_regla(clave: Optional[str]) -> str:
    """La etiqueta de una regla, o la propia clave si es una que este código no conoce."""
    regla = REGLAS.get(clave or "")
    return regla.etiqueta if regla is not None else (clave or "")


def es_regla(clave: Optional[str]) -> bool:
    return (clave or "") in REGLAS
