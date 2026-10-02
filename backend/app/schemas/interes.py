"""
La página de interés: lo que enseña y lo que acepta.

Todo lo que se puede elegir es una lista cerrada, y las tres que alimentan al modelo
—cargo, sector y tamaño— son literalmente las suyas (`CATEGORIAS_DEL_MODELO`). Una lista
propia «parecida» no daría un error: el preprocesador descartaría en silencio el valor que
no conoce, y el prospecto se puntuaría como si no hubiera dicho a qué se dedica.

No hay ninguna caja de texto libre. Lo único que la persona escribe son sus datos de
contacto y su empresa; no hay «cuéntanos tu caso», que sería contenido que después habría
que minimizar y que nadie va a leer desde aquí.

Un formulario de treinta segundos
---------------------------------
Obligatorio solo lo que el asesor necesita para llamar y el modelo para puntuar: nombre,
correo, empresa, cargo, tamaño, sector, qué necesita y el aviso. El teléfono y el perfil de
LinkedIn son opcionales, y la facturación ya no se pregunta: el tramo que se pedía nunca
llegaba al modelo —convertirlo en cifra habría sido inventarla— y solo alargaba la página.
`annual_revenue` se queda vacío, que es lo que el modelo sabe tratar como «no lo sabemos».

El nombre es un solo campo. Partir «María José García» en nombre y apellidos sería adivinar
dónde acaba uno y empieza el otro; la ficha lo guarda entero en `first_name` y deja
`last_name` vacío.
"""
import datetime
import re
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.publicaciones import CLAVE_DE_NECESIDAD, NECESIDADES_POR_DEFECTO
from app.core.texto import ENTRADA_DE_TEXTO
from app.core.vector_del_modelo import CATEGORIAS_DEL_MODELO

MAX_NOMBRE = 100
MAX_EMPRESA = 150
MAX_LINKEDIN = 200

# Qué busca quien escribe. Es la razón del contacto, no un texto libre, y **no puntúa**:
# informa al asesor en la ficha 360 y en el informe de la publicación, y nada más. Hasta el
# capítulo 25 «Ver una demostración» se registraba como `DEMO_REQUEST`, que la regla suma
# con 25 puntos y el modelo lee como `requested_demo`: un botón elegido en un segundo pesaba
# como una demo pedida de verdad. Darle peso es una decisión de negocio que queda fuera.
#
# Desde el capítulo 26 cada publicación puede tener las suyas (de 2 a 5); estas son las que
# usa la que no las tiene. La lista válida para un envío es la de su publicación, así que se
# comprueba en el servicio, después de saber a qué publicación va.
NECESIDADES: Dict[str, str] = NECESIDADES_POR_DEFECTO

# `linkedin.com/in/<identificador>`, con o sin «www» y con o sin subdominio de país (mx.,
# es.). Es lo que LinkedIn entrega como `LINKEDIN_PROFILE_LINK`.
PERFIL_DE_LINKEDIN = re.compile(
    r"^https://([a-z]{2}\.)?(www\.)?linkedin\.com/in/[A-Za-z0-9\-_%]{3,100}/?$"
)


def normalizar_perfil(valor: str) -> str:
    """
    Deja el perfil en su forma canónica antes de comprobarlo.

    Lo que la gente pega no es lo que un patrón estricto espera. El botón «compartir» de la
    aplicación de LinkedIn entrega
    `https://www.linkedin.com/in/perfil?utm_source=share&utm_medium=member_ios`, y quien lo
    escribe a mano pone `linkedin.com/in/perfil`, sin esquema. Las dos son la misma persona
    y las dos las rechazaba el patrón, con un mensaje que no decía qué sobraba.

    Se quita lo que no identifica al perfil —los parámetros de campaña, el fragmento— y se
    completa el esquema. No se acepta cualquier cosa: después de esto, el patrón sigue
    exigiendo que sea un perfil de LinkedIn. Y lo que se guarda es la forma limpia, no la
    que traía los parámetros de una campaña ajena.
    """
    limpio = valor.strip()
    if limpio and "://" not in limpio:
        limpio = f"https://{limpio}"
    limpio = limpio.replace("http://", "https://", 1) if limpio.startswith("http://") else limpio
    for separador in ("?", "#"):
        limpio = limpio.split(separador, 1)[0]
    return limpio


class OpcionesDelFormulario(BaseModel):
    """Las listas que la página tiene que pintar. Salen del servidor para que no se copien."""
    cargos: List[str]
    sectores: List[str]
    tamanos: List[str]
    necesidades: Dict[str, str]


class PublicacionPublica(BaseModel):
    """Lo que se enseña de la publicación. Ni presupuesto, ni a quién va dirigida, ni id."""
    titulo: str
    descripcion: Optional[str] = None
    opciones: OpcionesDelFormulario


class SolicitudDeInteres(BaseModel):
    # Estricto: un campo de más es un error, no algo que se ignora en silencio. Si mañana la
    # página manda algo que el servidor no espera, se ve en la primera prueba.
    #
    # El recorte lleva aquí desde el capítulo 34 y, hasta el 41, esta era la **única** entrada
    # del sistema que lo tenía: la única que rechazaba un nombre de tres espacios, y lo hacía
    # con esta línea y sin una comprobación propia. Ahora el recorte sale de `app.core.texto`,
    # donde lo comparten las once entradas, y lo que queda propio de esta pantalla es el
    # `extra="forbid"`.
    model_config = ConfigDict(**ENTRADA_DE_TEXTO, extra="forbid")

    nombre: str = Field(min_length=1, max_length=MAX_NOMBRE)
    correo: EmailStr = Field(max_length=150)
    empresa: str = Field(min_length=1, max_length=MAX_EMPRESA)
    cargo: str
    sector: str
    tamano_de_empresa: str
    necesidad: str
    # Obligatorio y comprobado abajo: sin aviso aceptado no hay tratamiento que defender.
    aviso_de_privacidad: bool
    # Opcionales, plegados en la página bajo «Añadir más datos». Vacío es `None`.
    telefono: Optional[str] = Field(None, max_length=50)
    linkedin: Optional[str] = Field(None, max_length=MAX_LINKEDIN)
    # Campo trampa. Está oculto en la página, así que una persona nunca lo rellena; los
    # robots que completan todos los campos del formulario, sí.
    sitio_web: str = Field("", max_length=200)

    @field_validator("cargo")
    @classmethod
    def _cargo_conocido(cls, valor: str) -> str:
        return _de_la_lista(valor, CATEGORIAS_DEL_MODELO["job_title"], "cargo")

    @field_validator("sector")
    @classmethod
    def _sector_conocido(cls, valor: str) -> str:
        return _de_la_lista(valor, CATEGORIAS_DEL_MODELO["industry"], "sector")

    @field_validator("tamano_de_empresa")
    @classmethod
    def _tamano_conocido(cls, valor: str) -> str:
        return _de_la_lista(valor, CATEGORIAS_DEL_MODELO["company_size"], "tamaño de empresa")

    @field_validator("necesidad")
    @classmethod
    def _necesidad_con_forma_de_clave(cls, valor: str) -> str:
        # Aquí solo la forma: una clave, nunca una frase. Si es de la lista de **esta**
        # publicación lo comprueba el servicio (`comprobar_necesidad`).
        if not CLAVE_DE_NECESIDAD.match(valor):
            raise ValueError("Elige un motivo de la lista.")
        return valor

    @field_validator("telefono")
    @classmethod
    def _telefono_o_nada(cls, valor: Optional[str]) -> Optional[str]:
        return valor or None

    @field_validator("linkedin")
    @classmethod
    def _perfil_de_linkedin(cls, valor: Optional[str]) -> Optional[str]:
        if not valor:
            return None
        limpio = normalizar_perfil(valor)
        if not PERFIL_DE_LINKEDIN.match(limpio):
            raise ValueError(
                "El perfil tiene que ser una dirección de LinkedIn como "
                "https://www.linkedin.com/in/tu-perfil"
            )
        return limpio

    @field_validator("aviso_de_privacidad")
    @classmethod
    def _aviso_aceptado(cls, valor: bool) -> bool:
        if valor is not True:
            raise ValueError("Hay que aceptar el aviso de privacidad para enviar la solicitud.")
        return valor


def _de_la_lista(valor: str, admitidos, campo: str) -> str:
    if valor not in admitidos:
        raise ValueError(f"Elige un {campo} de la lista.")
    return valor


class RespuestaDeInteres(BaseModel):
    """
    La misma respuesta siempre: exista o no el correo, sea la primera vez o la quinta.

    Si dijera «ya está registrado», la página serviría para averiguar qué correos hay en la
    base probándolos uno a uno.
    """
    mensaje: str
    recibido_en: datetime.datetime
