import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# bcrypt opera sobre un máximo de 72 bytes; se corta aquí, en el borde de la API,
# para devolver un 422 explicativo en lugar de truncar la contraseña en silencio.
MAX_PASSWORD_LENGTH = 72


class LoginRequest(BaseModel):
    """Credenciales enviadas a `POST /api/v1/auth/login`."""
    email: EmailStr
    password: str = Field(min_length=8, max_length=MAX_PASSWORD_LENGTH)


class TokenResponse(BaseModel):
    """
    Respuesta del login y del refresco.

    El refresh token NO viaja en este cuerpo: se entrega como cookie HttpOnly para que
    JavaScript no pueda leerlo. El access token sí, porque el cliente lo guarda solo en
    memoria y lo pierde al recargar la página.
    """
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
    last_login_at: Optional[datetime.datetime] = None


TokenResponse.model_rebuild()
