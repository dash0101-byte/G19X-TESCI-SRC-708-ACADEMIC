"""
El segundo factor de una cuenta: alta, activación, uso y baja (capítulo 35).

Cierra §3.6 de la congelación, que llevaba abierto desde el capítulo 19 y que decía por qué
no se había hecho: «un TOTP para `System_Admin` exige alta con código de verificación,
códigos de recuperación, un paso más en el login del cliente y una respuesta para quien
pierde el teléfono siendo el único administrador —que es justo la cuenta que no puede
quedarse fuera—. Añadir la verificación sin eso produce una cuenta de administración que se
bloquea sola.» Las cuatro cosas están aquí, y la cuarta es la que manda en el diseño.

El secreto no se guarda: se deriva
----------------------------------
La base de datos **no contiene ningún secreto TOTP**. Contiene una **sal** aleatoria por
alta, y el secreto sale de:

    secreto = HMAC-SHA256(SECRET_KEY, "totp:v1:" + sal)[:20]

Quien se lleve un volcado de la base se lleva sales, que solas no valen nada: sin
`SECRET_KEY` —que vive en el entorno, fuera del árbol y fuera de la base— no puede generar
un solo código. Es la misma propiedad que da cifrar el secreto con una clave derivada de
`SECRET_KEY`, y ahorra tener que implantar un cifrador: **lo que no se guarda no hay que
cifrarlo**. No es criptografía propia; es HMAC usado como función de derivación, que es
para lo que está.

**El precio, dicho entero:** rotar `SECRET_KEY` invalida **todas** las altas de segundo
factor, y no hay forma de volver a cifrarlas bajo la clave nueva porque no hay nada
cifrado que releer. No es un caso nuevo —rotar esa clave ya invalida todas las sesiones y
todos los tokens—, pero sí es peor: las sesiones se recuperan volviendo a entrar, y esto
exige volver a dar de alta el teléfono. Quien rote la clave tiene que contar con ello, y
está escrito en `docs/Guia_del_Segundo_Factor.md`.

La sal hace que dos altas de la misma cuenta den secretos distintos: volver a darse de alta
invalida el teléfono anterior sin tocar `SECRET_KEY`.

Los códigos de recuperación
---------------------------
Diez, de un solo uso, y se guardan **como resumen SHA-256**, no en claro y no con bcrypt.

Lo de bcrypt merece explicación porque el resto del sistema sí lo usa: bcrypt es lento a
propósito para que una contraseña **elegida por una persona** no se pueda probar por
diccionario. Un código de recuperación no lo elige nadie: son 60 bits de `secrets`, y
probarlos por fuerza bruta no es viable con ningún resumen. Lo que sí sería un problema es
el coste: comprobar un código contra diez bcrypt son diez comprobaciones lentas en cada
intento, y eso convierte el endpoint en un amplificador de carga para quien lo llame en
bucle.
"""
import datetime
import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.core import totp
from app.core.config import settings
from app.core.security import ROLES_OBLIGADOS_A_SEGUNDO_FACTOR, UserRole
from app.models.entities import User, utc_now

logger = logging.getLogger(__name__)

# Etiqueta de versión dentro de la derivación. Si algún día cambiara el algoritmo, subir
# esto da secretos distintos sin tocar las sales ya guardadas, y permite distinguir las
# altas viejas de las nuevas en lugar de romperlas todas en silencio.
_ETIQUETA = "totp:v1:"

EMISOR = "PluriOne Lead Scoring"

CODIGOS_DE_RECUPERACION = 10
# Alfabeto sin los caracteres que se confunden al copiar a mano de una hoja impresa: 0/O,
# 1/I/L. Quedan 31, y con doce caracteres son ~59 bits por código.
_ALFABETO = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_LARGO_DE_CODIGO = 12
_GRUPO = 4

# La regla de a quién se le exige vive en `core.security`, junto a la resolución de
# identidad que la aplica, y se reexporta aquí para que quien lea este módulo la encuentre.
# Definirla en los dos sitios habría sido la forma más fácil de que dejaran de coincidir.
ROLES_OBLIGADOS = ROLES_OBLIGADOS_A_SEGUNDO_FACTOR


class SegundoFactorInvalido(Exception):
    """El código no vale: ni TOTP dentro de la ventana, ni código de recuperación."""


class AltaNoIniciada(Exception):
    """Se intentó activar sin haber pedido el alta, o después de desactivarla."""


@dataclass(frozen=True)
class AltaDelSegundoFactor:
    """Lo que se enseña **una sola vez**, al dar de alta."""

    uri_otpauth: str
    secreto_en_base32: str
    codigos_de_recuperacion: List[str]


def _secreto_de(sal: str) -> bytes:
    """El secreto TOTP de esa sal. Determinista, y nunca se persiste."""
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        (_ETIQUETA + sal).encode("utf-8"),
        hashlib.sha256,
    ).digest()[: totp.BYTES_DE_SECRETO]


def _nuevo_codigo() -> str:
    crudo = "".join(secrets.choice(_ALFABETO) for _ in range(_LARGO_DE_CODIGO))
    return "-".join(crudo[i : i + _GRUPO] for i in range(0, _LARGO_DE_CODIGO, _GRUPO))


def _normalizar(codigo: str) -> str:
    """Quita guiones, espacios y mayúsculas para que copiar de una hoja impresa perdone."""
    return "".join(c for c in (codigo or "").upper() if c in _ALFABETO)


def _resumen(codigo: str) -> str:
    return hashlib.sha256(_normalizar(codigo).encode("ascii")).hexdigest()


def iniciar_alta(usuario: User) -> AltaDelSegundoFactor:
    """
    Genera sal, secreto y códigos, y los deja **pendientes de activación**.

    No activa nada. Entre esta llamada y `activar()` la cuenta sigue entrando con solo la
    contraseña, y es justo lo que hace falta: si se activara aquí, quien se equivoque al
    escanear el QR se queda fuera de su propia cuenta sin haber comprobado ni una vez que el
    teléfono genera el código bueno.

    Volver a llamarla **descarta el alta anterior**: sal nueva, secreto nuevo y códigos
    nuevos. Es lo que permite rehacer un alta a medias sin pasar por un administrador.
    """
    usuario.totp_sal = secrets.token_urlsafe(24)
    usuario.totp_activo = False
    usuario.totp_activado_en = None
    usuario.totp_ultimo_contador = None

    codigos = [_nuevo_codigo() for _ in range(CODIGOS_DE_RECUPERACION)]
    usuario.totp_codigos_de_recuperacion = [_resumen(c) for c in codigos]

    secreto = _secreto_de(usuario.totp_sal)
    return AltaDelSegundoFactor(
        uri_otpauth=totp.uri_otpauth(secreto, usuario.email, EMISOR),
        secreto_en_base32=totp.a_base32(secreto),
        codigos_de_recuperacion=codigos,
    )


def activar(usuario: User, codigo: str, *, ahora: Optional[datetime.datetime] = None) -> None:
    """
    Comprueba un código del teléfono y, si vale, activa el segundo factor.

    Es el paso que convierte «escaneé un QR» en «mi teléfono genera los códigos de esta
    cuenta». Sin él, el alta sería un acto de fe.
    """
    if not usuario.totp_sal:
        raise AltaNoIniciada("No hay un alta de segundo factor pendiente para esta cuenta.")

    momento = (ahora or utc_now()).timestamp()
    contador = totp.verificar(_secreto_de(usuario.totp_sal), codigo, momento)
    if contador is None:
        raise SegundoFactorInvalido("El código no es válido.")

    usuario.totp_activo = True
    usuario.totp_activado_en = ahora or utc_now()
    usuario.totp_ultimo_contador = contador


def comprobar(
    usuario: User, codigo: str, *, ahora: Optional[datetime.datetime] = None
) -> Tuple[str, int]:
    """
    Comprueba un código al iniciar sesión. Devuelve `(forma, restantes)`.

    `forma` es `"totp"` o `"recuperacion"`, y quien llama lo anota en la bitácora: gastar un
    código de recuperación significa que alguien perdió el teléfono, y eso hay que poder
    verlo sin cruzar tablas.

    Se prueba **primero el TOTP**. Es el caso normal, y además evita que un código del
    teléfono mal tecleado se compare contra los de recuperación: no casaría —los alfabetos
    no se solapan— pero el orden inverso haría trabajo inútil en cada intento.
    """
    if not usuario.totp_activo or not usuario.totp_sal:
        raise SegundoFactorInvalido("Esta cuenta no tiene segundo factor activo.")

    momento = (ahora or utc_now()).timestamp()
    contador = totp.verificar(
        _secreto_de(usuario.totp_sal),
        codigo,
        momento,
        # Ningún código de un periodo ya usado vuelve a valer. Sin esto, un código tiene
        # noventa segundos de vida —los treinta suyos más la tolerancia de reloj— y quien
        # lo lea por encima del hombro o lo saque de un registro lo puede reutilizar dentro
        # de esa ventana.
        contador_minimo=(usuario.totp_ultimo_contador or -1) + 1,
    )
    if contador is not None:
        usuario.totp_ultimo_contador = contador
        return "totp", len(usuario.totp_codigos_de_recuperacion or [])

    restantes = list(usuario.totp_codigos_de_recuperacion or [])
    resumen = _resumen(codigo)
    # Recorrido completo y comparación en tiempo constante: salir en cuanto casa filtraría
    # por tiempo cuántos códigos hay y en qué posición está el bueno.
    encontrado = None
    for guardado in restantes:
        if hmac.compare_digest(guardado, resumen):
            encontrado = guardado
    if encontrado is None:
        raise SegundoFactorInvalido("El código no es válido.")

    restantes.remove(encontrado)
    usuario.totp_codigos_de_recuperacion = restantes
    return "recuperacion", len(restantes)


def desactivar(usuario: User) -> None:
    """
    Quita el segundo factor y **borra la sal**.

    Borrarla importa: con la sal y `SECRET_KEY` se puede volver a calcular el secreto, así
    que dejarla ahí mantendría vivo el teléfono de alguien que ya no usa esta cuenta.
    Volver a darse de alta genera una sal nueva y, con ella, un secreto distinto.
    """
    usuario.totp_activo = False
    usuario.totp_sal = None
    usuario.totp_activado_en = None
    usuario.totp_ultimo_contador = None
    usuario.totp_codigos_de_recuperacion = None


def codigos_restantes(usuario: User) -> int:
    return len(usuario.totp_codigos_de_recuperacion or [])


def administradores_con_segundo_factor(db, excluyendo: Optional[int] = None) -> int:
    """
    Cuántas cuentas de administración activas podrían entrar ahora mismo.

    Es la comprobación que impide el escenario que §3.6 daba como motivo para no hacer
    nada: quedarse sin ninguna cuenta de administración utilizable. La usa la baja del
    segundo factor propio.
    """
    consulta = db.query(User).filter(
        User.role == UserRole.SYSTEM_ADMIN.value,
        User.is_active.is_(True),
        User.totp_activo.is_(True),
    )
    if excluyendo is not None:
        consulta = consulta.filter(User.id != excluyendo)
    return consulta.count()
