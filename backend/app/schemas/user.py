"""
Esquemas de gestión de usuarios y asesores.

Nota transversal: **ninguna respuesta lleva el hash de la contraseña**. No es una
casualidad de cada esquema, es la razón de que exista `UsuarioResponse` en lugar de
serializar la entidad: un `model_config = ConfigDict(from_attributes=True)` sobre `User`
sin lista explícita de campos habría publicado `hashed_password` en cuanto alguien
añadiera un endpoint nuevo.
"""
import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_validator

from app.core.publicaciones import (
    ESTADOS,
    MAX_DESCRIPCION,
    MAX_PUBLICO,
    MAX_TEXTO_DE_LINKEDIN,
    enlace_publico,
    necesidades_de,
    normalizar_necesidades,
    normalizar_url_del_post,
    texto_para_linkedin,
)
from app.core.security import UserRole

# El máximo lo impone bcrypt (72 bytes); el mínimo, la política de `app.core.passwords`.
# Aquí se declara laxo a propósito: si Pydantic rechazara antes por longitud, el usuario
# recibiría "String should have at least 12 characters" en vez de la lista completa de
# motivos que sabe dar la política.
MAX_PASSWORD_LENGTH = 72


class UsuarioResponse(BaseModel):
    """Ficha pública de una cuenta. Campos enumerados uno a uno, nunca `__all__`."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    is_sales_rep: bool
    phone: Optional[str] = None
    capacity: Optional[int] = None
    must_change_password: bool
    last_login_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime


class AsesorResponse(UsuarioResponse):
    """
    Un asesor con su carga real de trabajo.

    `leads_asignados` se calcula en la misma consulta agregada que trae la lista. La
    pantalla de administración lo pedía antes con una petición por asesor —tantas consultas
    como personas en el equipo—, y encima contra un endpoint que no existía.
    """

    leads_asignados: int = 0


class ListaDeUsuarios(BaseModel):
    total: int
    items: List[UsuarioResponse]


class ListaDeAsesores(BaseModel):
    total: int
    items: List[AsesorResponse]
    # Prospectos cuyo asesor es una cuenta dada de baja. Se cuenta SIEMPRE, también cuando
    # el listado oculta las bajas: es justo en esa vista por defecto donde la cartera de
    # quien se fue dejaba de verse, y un aviso que solo aparece al pedir las bajas no avisa.
    prospectos_en_cuentas_de_baja: int = 0


class RepartoDeCartera(BaseModel):
    """Traspasa todos los prospectos de una cuenta a otra que atienda cartera."""

    destino_id: int = Field(ge=1)


class ResultadoDeReparto(BaseModel):
    origen_id: int
    destino_id: int
    movidos: int
    carga_del_destino: int
    # No se bloquea: repartir la cartera de quien se fue a alguien ya lleno puede ser la
    # decisión correcta durante una semana. Se dice, para que sea una decisión y no un
    # descuido.
    supera_capacidad: bool


class UsuarioCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)
    role: UserRole
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)
    is_sales_rep: bool = False
    phone: Optional[str] = Field(None, max_length=50)
    capacity: Optional[int] = Field(None, ge=1, le=1000)

    @field_validator("full_name")
    @classmethod
    def _sin_espacios_sobrantes(cls, valor: str) -> str:
        return valor.strip()


class UsuarioUpdate(BaseModel):
    """
    Cambios administrativos sobre una cuenta.

    La contraseña **no está aquí**: se cambia por su propio endpoint. Mezclarla con el
    resto de atributos habría hecho que un cambio de teléfono y un cambio de credencial
    quedaran en la bitácora como la misma acción, y son cosas de gravedad muy distinta.
    """

    full_name: Optional[str] = Field(None, min_length=2, max_length=150)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    is_sales_rep: Optional[bool] = None
    phone: Optional[str] = Field(None, max_length=50)
    capacity: Optional[int] = Field(None, ge=1, le=1000)


class RestablecerContrasena(BaseModel):
    """Un administrador fija una contraseña nueva para otra persona."""

    nueva_contrasena: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class CambiarContrasenaPropia(BaseModel):
    """
    Cambio de contraseña que hace uno mismo.

    Exige la actual aunque la sesión ya esté autenticada. Un token robado, o un equipo que
    alguien dejó abierto, permite hacer cualquier cosa que la aplicación deje hacer sin
    volver a preguntar; pedir la contraseña actual es lo que impide que ese acceso
    temporal se convierta en un acceso permanente cambiando la credencial.
    """

    contrasena_actual: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)
    nueva_contrasena: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class ResultadoDeContrasena(BaseModel):
    mensaje: str
    sesiones_cerradas: int = Field(
        description="Sesiones revocadas por el cambio, incluida la que lo solicitó."
    )


# ==============================================================================
# Campañas
# ==============================================================================

class _CamposDePublicacion(BaseModel):
    """
    Lo que el capítulo 26 añade a una campaña. Se valida igual al crear y al editar.

    `necesidades` entra como la lista de etiquetas que escribe el líder («Cubrir vacantes de
    TI», …) y sale convertida en `[{clave, etiqueta}]`, que es lo que se guarda.
    """

    @field_validator("estado", check_fields=False)
    @classmethod
    def _estado_conocido(cls, valor):
        if valor is not None and valor not in ESTADOS:
            raise ValueError(f"El estado tiene que ser uno de: {', '.join(ESTADOS)}.")
        return valor

    @field_validator("necesidades", mode="before", check_fields=False)
    @classmethod
    def _necesidades(cls, valor):
        if valor is None:
            return None
        if not isinstance(valor, list):
            raise ValueError("Las opciones van en una lista.")
        etiquetas = [v.get("etiqueta") if isinstance(v, dict) else v for v in valor]
        if not all(isinstance(e, str) for e in etiquetas):
            raise ValueError("Cada opción es un texto.")
        return normalizar_necesidades(etiquetas)

    @field_validator("url_del_post", check_fields=False)
    @classmethod
    def _url_del_post(cls, valor):
        return normalizar_url_del_post(valor)


class CampanaBase(_CamposDePublicacion):
    name: str = Field(min_length=2, max_length=200)
    channel: str = Field(min_length=2, max_length=100)
    budget: float = Field(0.0, ge=0)
    utm_source: Optional[str] = Field(None, max_length=100)
    utm_medium: Optional[str] = Field(None, max_length=100)
    utm_campaign: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=MAX_DESCRIPCION)
    target_audience: Optional[str] = Field(None, max_length=MAX_PUBLICO)
    start_date: Optional[datetime.datetime] = None
    # También la fecha de cierre automática de una publicación.
    end_date: Optional[datetime.datetime] = None
    is_active: bool = True


class CampanaCreate(CampanaBase):
    # Sin `public_slug`: lo genera el servidor. Un valor enviado se ignora, igual que en la
    # edición; si se aceptara, el enlace dejaría de ser impredecible.
    #
    # Sin estado, una campaña nace activa, como antes de que hubiera estados: el guion de la
    # demo crea la publicación y copia su enlace en el mismo minuto. Un borrador se pide.
    estado: Optional[str] = None
    necesidades: Optional[List[Any]] = None
    responsable_id: Optional[int] = None
    url_del_post: Optional[str] = None


class CampanaUpdate(_CamposDePublicacion):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    channel: Optional[str] = Field(None, min_length=2, max_length=100)
    budget: Optional[float] = Field(None, ge=0)
    utm_source: Optional[str] = Field(None, max_length=100)
    utm_medium: Optional[str] = Field(None, max_length=100)
    utm_campaign: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=MAX_DESCRIPCION)
    target_audience: Optional[str] = Field(None, max_length=MAX_PUBLICO)
    start_date: Optional[datetime.datetime] = None
    end_date: Optional[datetime.datetime] = None
    is_active: Optional[bool] = None
    estado: Optional[str] = None
    # `null` explícito vuelve a las opciones de siempre.
    necesidades: Optional[List[Any]] = None
    responsable_id: Optional[int] = None
    url_del_post: Optional[str] = None


class OpcionDeNecesidad(BaseModel):
    clave: str
    etiqueta: str


class ResponsableBreve(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str


class CampanaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    channel: str
    budget: float
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    description: Optional[str] = None
    target_audience: Optional[str] = None
    start_date: Optional[datetime.datetime] = None
    end_date: Optional[datetime.datetime] = None
    is_active: bool
    estado: str
    responsable_id: Optional[int] = None
    responsable: Optional[ResponsableBreve] = None
    url_del_post: Optional[str] = None
    public_slug: str
    created_at: datetime.datetime
    # Lo guardado, tal cual: `None` si usa las de siempre.
    necesidades_guardadas: Optional[List[OpcionDeNecesidad]] = Field(
        None, validation_alias="necesidades", exclude=True
    )

    @computed_field
    @property
    def necesidades(self) -> List[OpcionDeNecesidad]:
        """Las opciones que verá el interesado: las propias o las de siempre."""
        guardadas = [o.model_dump() for o in self.necesidades_guardadas] if self.necesidades_guardadas else None
        return [OpcionDeNecesidad(clave=k, etiqueta=v) for k, v in necesidades_de(guardadas).items()]

    @computed_field
    @property
    def necesidades_propias(self) -> bool:
        return bool(self.necesidades_guardadas)

    @computed_field
    @property
    def enlace_publico(self) -> str:
        return enlace_publico(self.public_slug)

    @computed_field
    @property
    def texto_para_linkedin(self) -> str:
        return texto_para_linkedin(self.description, self.public_slug)

    @computed_field
    @property
    def longitud_del_texto(self) -> int:
        """Caracteres del texto copiado, contra el tope de LinkedIn (`max_texto_de_linkedin`)."""
        return len(self.texto_para_linkedin)

    @computed_field
    @property
    def max_texto_de_linkedin(self) -> int:
        return MAX_TEXTO_DE_LINKEDIN


class ListaDeCampanas(BaseModel):
    total: int
    items: List[CampanaResponse]
