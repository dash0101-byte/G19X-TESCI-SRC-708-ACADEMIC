"""
Segundo factor TOTP (RFC 6238), sobre la biblioteca estándar.

Por qué está escrito aquí y no se usa `pyotp`
---------------------------------------------
Porque no hay nada que inventar y sí algo que demostrar. TOTP **no es un diseño
criptográfico**: es un contador de treinta segundos metido en un HMAC-SHA1 y truncado, y el
HMAC lo pone `hmac` de la biblioteca estándar. El RFC publica además **vectores de prueba
oficiales**, así que esta implementación no se afirma correcta: se comprueba contra los
valores que publica la norma, para SHA-1, SHA-256 y SHA-512
(`tests/test_segundo_factor.py`). Una dependencia más en el lock de un proyecto congelado
tendría que ganarse el sitio, y aquí lo único que aportaría es no tener que leer cuarenta
líneas.

Lo que sí se respeta escrupulosamente es la norma, incluido el detalle que más se falla: la
tolerancia al reloj desfasado y su precio.

El secreto no se guarda
-----------------------
Este módulo no persiste nada. El secreto de cada cuenta se **deriva** de la clave del
servidor y de una sal aleatoria por alta (`segundo_factor.py`), de modo que la base de datos
no contiene ningún secreto que cifrar: contiene una sal, que sola no vale nada. La
consecuencia, dicha entera, está en ese módulo.
"""
import base64
import hashlib
import hmac
import struct
from typing import Optional
from urllib.parse import quote, urlencode

# Los tres parámetros que fija RFC 6238 §4 como valores por defecto y que espera cualquier
# aplicación de autenticación del teléfono. No se tocan: un TOTP con parámetros propios
# obliga a configurarlos a mano en el móvil, y nadie lo hace bien a la primera.
DIGITOS = 6
PERIODO_SEGUNDOS = 30
ALGORITMO = "SHA1"

_HASH = {"SHA1": hashlib.sha1, "SHA256": hashlib.sha256, "SHA512": hashlib.sha512}

# Cuántos periodos hacia atrás y hacia delante se aceptan además del actual.
#
# Uno (±30 s) y no más, y conviene decir qué se compra y qué se paga. Se compra que funcione
# el teléfono que va un poco desfasado y el código tecleado justo cuando cambiaba. Se paga
# que la ventana de validez de cada código pasa de 30 a 90 segundos, es decir que un código
# robado sirve el triple de tiempo. Con dos periodos serían 150 s por un caso que casi no
# ocurre: los teléfonos sincronizan la hora por red.
#
# RFC 6238 §5.2 lo dice en estos mismos términos y recomienda «como mucho uno».
DERIVA_DE_RELOJ = 1

# Longitud del secreto. 160 bits es lo que recomienda RFC 4226 §4 para HMAC-SHA1 y lo que
# produce 32 caracteres en base32, que es lo que las aplicaciones esperan poder pegar.
BYTES_DE_SECRETO = 20


def a_base32(secreto: bytes) -> str:
    """El secreto tal como se teclea a mano en la aplicación del teléfono, sin relleno."""
    return base64.b32encode(secreto).decode("ascii").rstrip("=")


def de_base32(texto: str) -> bytes:
    """Lo contrario, tolerando espacios, minúsculas y relleno ausente."""
    limpio = texto.replace(" ", "").upper()
    return base64.b32decode(limpio + "=" * (-len(limpio) % 8))


def _hotp(secreto: bytes, contador: int, digitos: int, algoritmo: str) -> str:
    """
    HOTP, RFC 4226 §5.3. Es el núcleo y son cuatro líneas.

    El «truncamiento dinámico» —tomar los cuatro bits bajos del último byte como índice y
    leer cuatro bytes desde ahí— existe para que el código no dependa siempre de la misma
    parte del HMAC. Se enmascara el bit más alto porque el resultado se interpreta como
    entero con signo en varias plataformas, y sin la máscara la mitad de los códigos
    saldrían negativos.
    """
    resumen = hmac.new(secreto, struct.pack(">Q", contador), _HASH[algoritmo]).digest()
    desplazamiento = resumen[-1] & 0x0F
    fragmento = struct.unpack(">I", resumen[desplazamiento : desplazamiento + 4])[0] & 0x7FFFFFFF
    return str(fragmento % (10**digitos)).zfill(digitos)


def contador_de(momento: float, periodo: int = PERIODO_SEGUNDOS) -> int:
    """El número de periodo al que pertenece ese instante (RFC 6238 §4.2)."""
    return int(momento // periodo)


def codigo(
    secreto: bytes,
    momento: float,
    *,
    digitos: int = DIGITOS,
    periodo: int = PERIODO_SEGUNDOS,
    algoritmo: str = ALGORITMO,
) -> str:
    """El código que enseña el teléfono en ese instante."""
    return _hotp(secreto, contador_de(momento, periodo), digitos, algoritmo)


def verificar(
    secreto: bytes,
    entregado: str,
    momento: float,
    *,
    deriva: int = DERIVA_DE_RELOJ,
    digitos: int = DIGITOS,
    periodo: int = PERIODO_SEGUNDOS,
    algoritmo: str = ALGORITMO,
    contador_minimo: Optional[int] = None,
) -> Optional[int]:
    """
    ¿Es válido ese código? Devuelve **el contador con el que casó**, o `None`.

    Devuelve el contador y no un booleano a propósito: quien llama tiene que guardarlo para
    que el mismo código no valga dos veces. Un TOTP es válido durante noventa segundos con
    la tolerancia puesta, así que sin esa memoria, un código leído por encima del hombro —o
    sacado de un registro— se puede reutilizar dentro de esa ventana. `contador_minimo`
    rechaza cualquier código de un periodo que ya se usó.

    La comparación es en **tiempo constante**. Comparar con `==` filtra por el tiempo de
    respuesta cuántos dígitos iniciales se acertaron, y con un millón de combinaciones eso
    convierte una búsqueda exhaustiva en una búsqueda dígito a dígito.
    """
    limpio = (entregado or "").replace(" ", "").replace("-", "").strip()
    if not limpio.isdigit() or len(limpio) != digitos:
        return None

    actual = contador_de(momento, periodo)
    for salto in range(-deriva, deriva + 1):
        contador = actual + salto
        if contador < 0:
            continue
        if contador_minimo is not None and contador < contador_minimo:
            # Ya se usó un código de este periodo o de uno posterior.
            continue
        if hmac.compare_digest(_hotp(secreto, contador, digitos, algoritmo), limpio):
            return contador
    return None


def uri_otpauth(
    secreto: bytes,
    cuenta: str,
    emisor: str,
    *,
    digitos: int = DIGITOS,
    periodo: int = PERIODO_SEGUNDOS,
    algoritmo: str = ALGORITMO,
) -> str:
    """
    La dirección `otpauth://` que se convierte en código QR.

    El formato no es un estándar del IETF sino la convención que sigue todo el mundo, y
    tiene una trampa conocida: el emisor va **dos veces**, en la etiqueta y como parámetro.
    Las aplicaciones antiguas leen la etiqueta y las nuevas el parámetro; poniendo solo uno,
    unas cuantas enseñan la cuenta sin decir de qué sistema es, y quien tenga varias no sabe
    cuál es cuál.
    """
    etiqueta = quote(f"{emisor}:{cuenta}", safe="")
    parametros = urlencode(
        {
            "secret": a_base32(secreto),
            "issuer": emisor,
            "algorithm": algoritmo,
            "digits": digitos,
            "period": periodo,
        }
    )
    return f"otpauth://totp/{etiqueta}?{parametros}"
