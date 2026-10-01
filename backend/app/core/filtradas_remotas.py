"""
¿Esta contraseña ya está en una filtración pública? (capítulo 37)

El capítulo 23 dejó una lista LOCAL de contraseñas filtradas dentro de la imagen, y el §3.7
de la congelación anotó sus dos límites: no se actualiza sola y no es exhaustiva. Cubrir
cientos de millones de huellas por el mismo camino pediría decenas de gigabytes en la
imagen, así que el documento concluía que haría falta «una cuenta en un servicio de
comprobación de contraseñas comprometidas».

**Esa conclusión era falsa, y es la mitad de lo que cierra este capítulo.** El servicio de
rango de Have I Been Pwned no pide cuenta, ni clave, ni registro: es una petición `GET`
anónima. Lo que §3.7 describía bien era el *modelo* —k-anonymity— y lo que daba por supuesto
sin comprobarlo era el requisito administrativo.

Qué sale de esta máquina, exactamente
-------------------------------------
De la contraseña se calcula su SHA-1 y **se envían los cinco primeros caracteres
hexadecimales de ese resumen**. Nada más. Ni la contraseña, ni el resumen completo, ni el
correo de quien la eligió.

Cinco caracteres hexadecimales son 20 bits: 1 048 576 prefijos posibles para un espacio de
contraseñas incontable. El servidor devuelve **todos** los sufijos que empiezan por ese
prefijo —entre trescientos y mil en la práctica— y la comparación con el sufijo real se hace
**aquí**. El servidor no puede saber cuál de los cientos era el nuestro, ni si alguno lo era:
la respuesta es idéntica se haya acertado o no.

`Add-Padding: true` va en la petición por lo mismo. Sin esa cabecera, el **tamaño** de la
respuesta identifica el prefijo aunque el cuerpo viaje cifrado; con ella, el servicio rellena
hasta un tamaño uniforme con entradas falsas de recuento cero, que aquí se descartan. Es la
diferencia entre «no mando el secreto» y «no mando nada que lo distinga».

Por qué SHA-1, que está roto
----------------------------
Porque aquí no se usa como función de seguridad: se usa como **índice compartido** con el
servicio, y el servicio publica SHA-1. Lo que protege la contraseña no es la resistencia de
SHA-1 a colisiones, es que solo salen cinco de sus cuarenta caracteres. Lo que protege la
contraseña *guardada* sigue siendo bcrypt, y eso no cambia. Por eso se pide con
`usedforsecurity=False`: es lo que esa bandera significa, y además evita que una compilación
de Python en modo FIPS niegue el algoritmo.

Qué pasa cuando el servicio no contesta
---------------------------------------
No se bloquea a nadie. El veredicto tiene **tres** valores y no dos: `True`, `False` y
`None`. El tercero es «no se pudo preguntar», y no es lo mismo que «no está filtrada»; quien
llama tiene que distinguirlos, y por eso no es un booleano.

La política ante `None` está escrita en `app/core/passwords.py` y es: **seguir adelante con
lo que ya había**. No es «todo vale», porque la lista local del capítulo 23 ya se ha
consultado antes de llegar aquí, junto con la longitud mínima, las clases de carácter, los
fragmentos personales y el nombre del producto. Sin internet, el comportamiento es
exactamente el de ayer. Lo que se pierde es la mejora, no la defensa.

Y por eso **no hay reintentos**. Un reintento con espera convierte un servicio caído en un
formulario de alta que tarda ocho segundos en responder, y el tope corto existe precisamente
para que un tercero caído no pueda retener a nadie. Se pregunta una vez.

El certificado se verifica contra el almacén del sistema
--------------------------------------------------------
`ssl.create_default_context()` y no el `certifi` que trae httpx. En una máquina con la salida
TLS interceptada —un antivirus, un proxy de empresa— el certificado que llega está firmado
por una autoridad que solo vive en el almacén del sistema, y `certifi` la rechaza. El
síntoma sería «el servicio no contesta» sobre un servicio que contesta perfectamente: un
falso negativo que se parece a un fallo del tercero, que es la peor clase. Ya mordió en
`scripts/comprobar_puerta_publica.py` (capítulo 34) y la costumbre está escrita.

Qué queda en la bitácora
------------------------
El prefijo —que es lo que ya salió por el cable—, el resultado y el motivo. **Nunca la
contraseña ni su resumen completo.** Una bitácora que registrase el resumen entero anularía
de un plumazo todo lo que este módulo hace: el fichero de registro acabaría siendo el
diccionario que no quisimos mandar.
"""
from __future__ import annotations

import hashlib
import logging
import ssl
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

# Cuántos caracteres del resumen salen de esta máquina. No es configurable: subirlo
# estrecharía el conjunto en el que nos escondemos, y bajarlo devolvería respuestas de
# megabytes. Cinco es el valor que el servicio publica y el que hace que el anonimato sea
# comprobable de un vistazo.
PREFIJO = 5

URL_DE_RANGO = "https://api.pwnedpasswords.com/range/"

# Una respuesta legítima ronda los 20 KB; con relleno, algo más. El tope corta una respuesta
# absurda antes de recorrerla entera: este módulo corre dentro de la petición de alta.
MAXIMO_DE_RESPUESTA = 1024 * 1024

NO_SE_PREGUNTO = "La comprobación está apagada (COMPROBAR_CONTRASENAS_FILTRADAS)."

# El motivo que `passwords.evaluar` devuelve cuando el servicio sí contestó y la contraseña
# estaba. Vive aquí, junto a quien lo decide, y no en el módulo de política: así una prueba
# puede comprobar el texto exacto sin importar las dos mitades del sistema.
MOTIVO_FILTRADA_FUERA = (
    "Esa contraseña aparece en filtraciones públicas conocidas. No se ha enviado su "
    "contraseña a ningún sitio: solo cinco caracteres del resumen, que no permiten "
    "reconstruirla. Elija una que no haya usado en otro sitio."
)


@dataclass(frozen=True)
class Veredicto:
    """
    Lo que se sabe de la contraseña después de preguntar fuera.

    `filtrada` es de tres valores a propósito; está explicado en la cabecera del módulo.
    `apariciones` solo tiene sentido con `filtrada=True` y **no se enseña** a quien elige la
    contraseña: saber que apareció 3 800 veces en lugar de 12 no le ayuda a elegir otra, y
    el número es exactamente la pista que un atacante querría.
    """

    filtrada: Optional[bool]
    apariciones: int = 0
    detalle: str = ""
    prefijo: str = ""

    @property
    def se_pudo_preguntar(self) -> bool:
        return self.filtrada is not None


def huella_partida(contrasena: str) -> Tuple[str, str]:
    """
    El resumen SHA-1 en mayúsculas, partido en lo que sale y lo que se queda.

    Se devuelve partido y no entero para que **ninguna función de este módulo tenga a mano
    la cadena completa por descuido**: quien quiera registrar algo solo puede registrar una
    de las dos mitades, y la que es segura registrar es la primera.
    """
    resumen = (
        hashlib.sha1(contrasena.encode("utf-8"), usedforsecurity=False)  # noqa: S324
        .hexdigest()
        .upper()
    )
    return resumen[:PREFIJO], resumen[PREFIJO:]


def _contexto_tls() -> ssl.SSLContext:
    """El almacén de certificados del sistema. El porqué, en la cabecera del módulo."""
    return ssl.create_default_context()


def _sonda_https(prefijo: str, timeout: float) -> Tuple[int, str]:
    """
    La única función de todo el proyecto que manda el prefijo a un tercero.

    No reintenta y no sigue redirecciones: una redirección en este servicio sería un
    intermediario, y seguirla mandaría el prefijo a donde no se decidió mandarlo.
    """
    respuesta = httpx.get(
        URL_DE_RANGO + prefijo,
        timeout=timeout,
        follow_redirects=False,
        verify=_contexto_tls(),
        headers={
            # Relleno contra el análisis de tamaño; explicado en la cabecera.
            "Add-Padding": "true",
            "User-Agent": "plurione-lead-scoring",
        },
    )
    return respuesta.status_code, respuesta.text[:MAXIMO_DE_RESPUESTA]


def _buscar_sufijo(cuerpo: str, sufijo: str) -> int:
    """
    Cuántas veces aparece nuestro sufijo en la lista devuelta. Cero si no está.

    Las líneas con recuento 0 son el relleno y se descartan: contarlas haría que una
    contraseña pareciera filtrada en cuanto el relleno acertara con su sufijo, que es
    justamente lo que el relleno está diseñado para parecer.
    """
    for linea in cuerpo.splitlines():
        candidato, _, recuento = linea.strip().partition(":")
        if candidato.upper() != sufijo:
            continue
        try:
            return int(recuento.split(",")[0])
        except ValueError:
            return 0
    return 0


def consultar(
    contrasena: str,
    *,
    sonda: Optional[Callable[[str, float], Tuple[int, str]]] = None,
    timeout: Optional[float] = None,
) -> Veredicto:
    """
    Pregunta por rango si la contraseña ya está filtrada.

    `sonda` se inyecta en las pruebas, igual que en `services/direccion_publica.py`. No hay
    ninguna versión de esta función que salga a internet sin que alguien lo haya pedido: con
    `COMPROBAR_CONTRASENAS_FILTRADAS` apagada devuelve «no se preguntó» sin abrir un socket.

    **Nunca lanza.** Cualquier fallo —red, TLS, cuerpo inesperado, el servicio devolviendo
    un 503— se convierte en `filtrada=None`. Una excepción que subiera hasta el endpoint
    convertiría un tercero caído en un alta de usuario rota, y eso es exactamente la
    degradación que este capítulo se propuso evitar.
    """
    if not settings.COMPROBAR_CONTRASENAS_FILTRADAS:
        return Veredicto(filtrada=None, detalle=NO_SE_PREGUNTO)

    prefijo, sufijo = huella_partida(contrasena)
    espera = timeout if timeout is not None else settings.CONTRASENAS_FILTRADAS_TIMEOUT_SEGUNDOS

    if sonda is None:
        # Guarda deliberada: la suite corre con ENVIRONMENT=test y no debe abrir sockets
        # contra un tercero. Una prueba que necesite esta ruta inyecta su propia sonda; una
        # que llegue aquí por descuido se entera ahora, y no en el CI de otra persona el día
        # que el servicio esté lento.
        if settings.ENVIRONMENT == "test":
            raise RuntimeError(
                "La suite no sale a internet: inyecte `sonda` o deje "
                "COMPROBAR_CONTRASENAS_FILTRADAS apagada."
            )
        sonda = _sonda_https

    try:
        codigo, cuerpo = sonda(prefijo, espera)
    except Exception as exc:  # noqa: BLE001 - el tipo no importa aquí; el resultado sí
        # Se guarda la CLASE de la excepción y no su mensaje: el mensaje de httpx lleva la
        # URL, y la URL lleva el prefijo. El prefijo ya está en el registro una línea más
        # abajo, pero dejar que se cuele dentro de un texto libre es cómo se escapan los
        # secretos que nadie decidió registrar.
        return _sin_respuesta(prefijo, exc.__class__.__name__)

    if codigo != 200:
        return _sin_respuesta(prefijo, f"HTTP {codigo}")

    apariciones = _buscar_sufijo(cuerpo, sufijo)
    if apariciones > 0:
        # Ni la contraseña ni el resumen: el prefijo, que ya viajó, y el número.
        logger.info(
            "Contraseña rechazada por aparecer en filtraciones públicas "
            "(prefijo %s, %d apariciones).",
            prefijo,
            apariciones,
        )
        return Veredicto(
            filtrada=True, apariciones=apariciones, detalle="encontrada", prefijo=prefijo
        )

    logger.debug("Contraseña no encontrada en filtraciones públicas (prefijo %s).", prefijo)
    return Veredicto(filtrada=False, detalle="no encontrada", prefijo=prefijo)


def _sin_respuesta(prefijo: str, motivo: str) -> Veredicto:
    """
    El caso que de verdad importa: el servicio no contestó y nadie se queda fuera.

    Se registra en WARNING y no en ERROR. ERROR es para lo que alguien tiene que arreglar
    hoy; esto es un tercero que no contesta, y la respuesta correcta del sistema es seguir
    con la lista local. Un ERROR por cada alta mientras dura un corte de internet entrena a
    quien lee la bitácora a no leerla.
    """
    logger.warning(
        "No se pudo comprobar la contraseña contra el servicio de filtradas (prefijo %s): "
        "%s. Se continúa con la lista local; no se bloquea a nadie.",
        prefijo,
        motivo,
    )
    return Veredicto(filtrada=None, detalle=motivo, prefijo=prefijo)
