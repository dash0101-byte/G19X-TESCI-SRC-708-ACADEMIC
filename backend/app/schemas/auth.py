import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field

from app.core.security import exige_segundo_factor
from app.core.texto import ENTRADA_DE_TEXTO, Contrasena

# bcrypt opera sobre un máximo de 72 bytes; se corta aquí, en el borde de la API,
# para devolver un 422 explicativo en lugar de truncar la contraseña en silencio.
MAX_PASSWORD_LENGTH = 72


class LoginRequest(BaseModel):
    """Credenciales enviadas a `POST /api/v1/auth/login`."""

    model_config = ENTRADA_DE_TEXTO

    email: EmailStr
    # La contraseña no se recorta, y es el único campo del sistema del que eso se dice en voz
    # alta. El endpoint ya recorta el correo antes de buscar la cuenta; hacer lo mismo con la
    # contraseña dejaría fuera a quien tenga un espacio en la suya y convertiría el
    # `min_length` de ocho en la medida de otra cadena.
    password: Contrasena = Field(min_length=8, max_length=MAX_PASSWORD_LENGTH)


class TokenResponse(BaseModel):
    """
    Respuesta del login y del refresco.

    El refresh token NO viaja en este cuerpo: se entrega como cookie HttpOnly para que
    JavaScript no pueda leerlo. El access token sí, porque el cliente lo guarda solo en
    memoria y lo pierde al recargar la página.
    """
    # Discriminador de la respuesta del login (capítulo 35). Desde que existe el segundo
    # factor, `POST /auth/login` puede devolver dos cosas distintas —una sesión o un
    # desafío—, y el cliente tiene que poder distinguirlas sin adivinar por qué campos
    # traen. Se declara con un valor fijo para que quede también en el esquema de la API.
    tipo: Literal["sesion"] = "sesion"
    access_token: str
    token_type: str = "bearer"  # noqa: S105  esquema de autorización HTTP, no un secreto
    expires_in: int = Field(description="Segundos de validez del access token.")
    user: "UserResponse"


class UserResponse(BaseModel):
    """Identidad pública del usuario autenticado. Nunca incluye el hash de contraseña."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    # El cliente la necesita en el login y en cada refresco para llevar a la persona a
    # cambiar la contraseña, en lugar de enseñarle una aplicación que el servidor le va a
    # rechazar petición a petición.
    must_change_password: bool = False
    # Lo mismo para el segundo factor: el cliente lo necesita para llevar a una cuenta de
    # administración a la pantalla de alta, en vez de enseñarle una aplicación que el
    # servidor le va a rechazar petición a petición.
    totp_activo: bool = False
    last_login_at: Optional[datetime.datetime] = None

    @computed_field
    @property
    def segundo_factor_obligatorio(self) -> bool:
        """
        Si a esta cuenta se le exige el segundo factor, según el rol.

        Lo calcula el **servidor** y viaja en la respuesta en lugar de deducirlo el cliente
        del rol. Deducirlo allí crearía una segunda definición de «quién está obligado», y
        el día que alguien cambiara la de aquí —`ROLES_OBLIGADOS_A_SEGUNDO_FACTOR`— la otra
        se quedaría atrás sin que nada fallara: el panel enseñaría la aplicación a una
        cuenta a la que el servidor le va a rechazar todo, o al revés.
        """
        return exige_segundo_factor(self.role)


class DesafioDeSegundoFactor(BaseModel):
    """
    Lo que devuelve el login cuando la contraseña es correcta y falta el segundo factor.

    Es una respuesta **200**, no un error, y merece justificarse porque la tentación es
    contestar 401. La contraseña se comprobó y era buena: lo que ocurre es que la
    autenticación tiene dos pasos y va por el primero. Tratarlo como error obligaría al
    cliente a manejar el camino normal dentro de su rama de fallos, que es donde se acaban
    tragando los errores de verdad.

    `desafio` es un token de un solo uso y vida muy corta que acredita **solo** que ese paso
    se superó. No sirve para nada más: no abre sesión, no vale como `Authorization`, y el
    endpoint que lo consume exige que sea de este tipo.
    """

    tipo: Literal["segundo_factor"] = "segundo_factor"
    desafio: str = Field(description="Token de un solo paso, válido unos minutos.")
    expira_en: int = Field(description="Segundos de validez del desafío.")
    codigos_de_recuperacion_restantes: int = Field(
        description="Para poder avisar a quien va quedándose sin códigos."
    )


class SegundoFactorDelLogin(BaseModel):
    """El segundo paso: el desafío y el código del teléfono o uno de recuperación."""

    # Recorta los bordes, que aquí hace algo útil: un código copiado del teléfono o del papel
    # de los de recuperación viene a menudo con un espacio pegado, y hasta ahora ese espacio
    # convertía un código correcto en un intento fallido.
    model_config = ENTRADA_DE_TEXTO

    desafio: str
    # Sin `min_length`: un TOTP son 6 dígitos y un código de recuperación 12 caracteres con
    # guiones. Un mínimo que valiera para los dos no filtraría nada y uno por forma obligaría
    # a que el cliente decidiera de qué tipo es, que es justo lo que no tiene que hacer.
    codigo: str = Field(max_length=64)


class AltaDeSegundoFactor(BaseModel):
    """
    Lo que se enseña **una sola vez**, al dar de alta.

    El secreto y los códigos no se vuelven a mostrar nunca: no existe ningún endpoint que
    los devuelva, porque el servidor no los tiene. Del secreto solo guarda la sal de la que
    se deriva, y de los códigos, su resumen.
    """

    uri_otpauth: str = Field(description="Lo que codifica el QR; también sirve pegada a mano.")
    qr_svg: str = Field(description="El código QR ya dibujado, para enseñarlo sin más.")
    secreto_en_base32: str = Field(description="Para teclearlo si la cámara no va.")
    codigos_de_recuperacion: List[str]


class EstadoDelSegundoFactor(BaseModel):
    """Lo que el panel necesita saber para dibujar la pantalla de seguridad."""

    activo: bool
    obligatorio: bool
    activado_en: Optional[datetime.datetime] = None
    codigos_de_recuperacion_restantes: int = 0


class CodigoDelSegundoFactor(BaseModel):
    """
    Un código del teléfono, o uno de recuperación. Sirve para activar y para dar de baja.

    Para la baja se pide un código y no la contraseña a propósito: quien deja una sesión
    abierta en un equipo ajeno tiene ahí la contraseña guardada en el navegador mucho más a
    menudo que el teléfono.
    """

    model_config = ENTRADA_DE_TEXTO

    codigo: str = Field(max_length=64)


TokenResponse.model_rebuild()
