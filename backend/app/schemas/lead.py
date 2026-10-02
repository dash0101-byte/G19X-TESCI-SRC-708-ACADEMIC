import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, computed_field, field_validator, model_validator

from app.core.redes import es_de_publicacion
from app.core.telefono import validador_de_telefono
from app.core.texto import (
    ENTRADA_DE_TEXTO,
    campos_sin_los_que_no_existe,
    exigir_texto,
    texto_o_nada,
    vacios_prohibidos,
)
from app.models.entities import (
    ActivityType,
    Lead,
    LeadStatus,
    QualificationStatus,
    ScoreCategory,
)
from app.schemas.activity import ActivityResponse
from app.schemas.desenlaces import DesenlaceDeLaFicha
from app.schemas.publicaciones import LlegoPor
from app.schemas.score import ScoreHistoryResponse

# Los límites replican el ancho de las columnas de `Lead` en `models/entities.py`.
# Sin ellos, un texto largo pasaba la validación y fallaba en el INSERT (PostgreSQL) o
# se guardaba entero rompiendo el contrato declarado del esquema (SQLite, que ignora
# el ancho de VARCHAR): en ambos casos, un 500 en vez de un 422 que señale el campo.
MAX_NAME = 100
MAX_EMAIL = 150
MAX_PHONE = 50
MAX_COMPANY = 150
MAX_JOB_TITLE = 100
MAX_INDUSTRY = 100
MAX_COMPANY_SIZE = 50
MAX_COUNTRY = 100
MAX_CITY = 100
MAX_SOURCE = 100
# `initial_notes` no es una columna: viaja dentro del JSON `activity_data`, con el mismo
# tope que las notas de cualquier actividad registrada a mano.
MAX_NOTES = 500


# Un texto en blanco es ausencia de dato, no la cadena vacía.
#
# El formulario del panel manda `""` cuando el campo se deja sin rellenar, y guardarlo tal
# cual habría dejado en la base dos formas de decir lo mismo: `NULL` para las fichas que
# nunca lo tuvieron y `''` para las que pasaron por la pantalla. Cualquier consulta posterior
# tendría que acordarse de las dos.
#
# La función nació aquí —`_texto_o_vacio`, capítulo 32 para el país y 33 para el resto del
# texto de la **edición**— y en el 41 se mudó a `app.core.texto`, cuando hizo falta la cuarta
# vez: el alta, el webhook del CRM y las integraciones son tres puertas más a la misma base, y
# cada una respondía algo distinto a «qué es un vacío». Los dos nombres anteriores,
# `_texto_o_vacio` y `_pais_o_vacio`, no se conservan como alias: un alias que nadie usa es un
# nombre más que buscar el día que algo falle, y aquí solo servirían para que este comentario
# no tuviera que escribirse.

# Qué campos de la ficha no se pueden dejar vacíos, preguntándoselo a la tabla.
#
# Se deriva de `Lead.__table__` a propósito, y es la mitad del arreglo del capítulo 33. La
# lista «nombre, apellido, correo, etapa» es fácil de escribir a mano y es justo lo que no hay
# que hacer: una copia escrita a mano acierta el día que se escribe y se queda atrás en la
# primera migración que añada o quite un `NOT NULL`, sin que nada se ponga rojo.
#
# Desde el capítulo 41 la derivación es de `app.core.texto` y la comparten `Campaign` y
# `User`. Que fuera una función privada de este módulo no se veía como un límite y lo era: la
# misma edición parcial existe para las publicaciones y para las cuentas, y en las dos un
# `null` sobre una columna obligatoria se escribía y salía como 500.
CAMPOS_QUE_NO_ADMITEN_VACIO = campos_sin_los_que_no_existe(Lead)

# Los campos de texto de la ficha que la tabla sí deja vacíos, y que por tanto se normalizan
# a `None` en vez de rechazarse.
#
# Esta lista sí está escrita, y lleva prueba: `test_un_blanco_no_es_un_dato.py` la compara con
# las columnas de texto de `leads` que admiten nulo y exige que sea esa lista **menos** dos,
# cada una con su motivo —`phone`, que pasa por E.164 y ya normaliza el blanco, y
# `privacy_notice_source`, que no está en ningún esquema de entrada porque lo escribe el
# servidor—. Así un campo de texto nuevo no puede entrar sin que alguien decida en qué montón
# va, que es lo que pasó con los nueve del alta.
TEXTOS_QUE_ADMITEN_VACIO = (
    "company",
    "job_title",
    "industry",
    "company_size",
    "country",
    "city",
)


# Valida y normaliza al guardar. Se aplica a la entrada —alta y edición— y no a `LeadBase`:
# la respuesta hereda de ella, y un teléfono anterior a la Fase 15 que la migración no pudo
# normalizar convertiría la lectura de su ficha en un error.
#
# Desde el capítulo 32 la definición vive en `app.core.telefono` y la comparte el esquema de
# las cuentas: dos copias se habrían desincronizado el día que alguien tocara una.
_telefono_e164 = validador_de_telefono


class LeadBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=MAX_NAME)
    last_name: str = Field(..., min_length=1, max_length=MAX_NAME)
    email: EmailStr = Field(..., max_length=MAX_EMAIL)
    phone: Optional[str] = Field(None, max_length=MAX_PHONE)
    company: Optional[str] = Field(None, max_length=MAX_COMPANY)
    job_title: Optional[str] = Field(None, max_length=MAX_JOB_TITLE)
    industry: Optional[str] = Field(None, max_length=MAX_INDUSTRY)
    # Sin valor por defecto: un tamaño que no se indicó no es «1-10».
    company_size: Optional[str] = Field(None, max_length=MAX_COMPANY_SIZE)
    # Tampoco aquí: unos ingresos que no se indicaron no son cero (capítulo 24).
    annual_revenue: Optional[float] = Field(None, ge=0.0)
    # Sin valor por defecto, por el mismo motivo que `company_size` y `annual_revenue`
    # (capítulo 32): un país que no se indicó no es México. Escribirlo aquí hacía que el
    # alta por API de una ficha sin país produjera una ficha CON país, y la suposición
    # quedaba indistinguible del dato en cuanto la fila entraba en la base.
    country: Optional[str] = Field(None, max_length=MAX_COUNTRY)
    city: Optional[str] = Field(None, max_length=MAX_CITY)
    source: str = Field("Website", max_length=MAX_SOURCE)
    assigned_rep_id: Optional[int] = None
    campaign_id: Optional[int] = None
    raw_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class LeadCreate(LeadBase):
    # Recorta antes de medir, y es lo que hace que `min_length=1` signifique algo: un
    # `first_name` de tres espacios llegaba intacto a una columna que la tabla declara
    # indispensable, porque el mínimo se aplicaba a lo que entró y no a lo que se guarda.
    model_config = ENTRADA_DE_TEXTO

    # `source` se redeclara solo para añadirle el mínimo. La columna es `NOT NULL` y no tenía
    # ninguno: un canal en blanco respondía 201 en esta puerta y 422 en la de al lado, con el
    # mismo valor y sobre la misma columna. No se sube a `LeadBase` porque de ella heredan las
    # respuestas, y un canal en blanco que ya esté en la base convertiría la **lectura** de
    # esa ficha en un error —el mismo motivo por el que `LeadResponse` no hereda el mínimo del
    # nombre—.
    source: str = Field("Website", min_length=1, max_length=MAX_SOURCE)

    initial_activity_type: Optional[ActivityType] = None
    initial_notes: Optional[str] = Field(None, max_length=MAX_NOTES)
    # El asesor que da de alta a la persona deja constancia de que aceptó el aviso de
    # privacidad. Se guarda cuándo y con fuente `manual`.
    privacy_notice_accepted: bool = False

    _phone = field_validator("phone")(_telefono_e164)
    # Los mismos campos que la edición normaliza desde el capítulo 33, y por el mismo motivo.
    # Hasta el 41 aquí solo estaba el país: el capítulo 32 lo escribió para el país porque era
    # el campo del que se ocupaba, el 33 extendió la regla a la edición, y el alta se quedó
    # con un campo normalizado de diez. Una ficha dada de alta por la API y la misma ficha
    # después de una edición no decían lo mismo en la base.
    _textos = field_validator(*TEXTOS_QUE_ADMITEN_VACIO, "initial_notes")(texto_o_nada)


class LeadUpdate(BaseModel):
    # La misma configuración que el alta, por el mismo motivo y con una consecuencia más: con
    # el recorte delante, `first_name: '   '` choca con el `min_length=1` de abajo y responde
    # 422 nombrando el campo, que es exactamente lo que el capítulo 33 quería para un campo sin
    # el que la ficha no existe. Su validador —el de más abajo— solo miraba `None`, así que
    # vaciar con un espacio pasaba por donde vaciar con un nulo no pasaba.
    model_config = ENTRADA_DE_TEXTO

    first_name: Optional[str] = Field(None, min_length=1, max_length=MAX_NAME)
    last_name: Optional[str] = Field(None, min_length=1, max_length=MAX_NAME)
    email: Optional[EmailStr] = Field(None, max_length=MAX_EMAIL)
    phone: Optional[str] = Field(None, max_length=MAX_PHONE)
    company: Optional[str] = Field(None, max_length=MAX_COMPANY)
    job_title: Optional[str] = Field(None, max_length=MAX_JOB_TITLE)
    industry: Optional[str] = Field(None, max_length=MAX_INDUSTRY)
    company_size: Optional[str] = Field(None, max_length=MAX_COMPANY_SIZE)
    annual_revenue: Optional[float] = Field(None, ge=0.0)
    country: Optional[str] = Field(None, max_length=MAX_COUNTRY)
    city: Optional[str] = Field(None, max_length=MAX_CITY)
    source: Optional[str] = Field(None, max_length=MAX_SOURCE)
    status: Optional[LeadStatus] = None
    qualification_status: Optional[QualificationStatus] = None
    assigned_rep_id: Optional[int] = None
    raw_metadata: Optional[Dict[str, Any]] = None

    _phone = field_validator("phone")(_telefono_e164)
    # Todo el texto de la edición pasa por la misma normalización desde el capítulo 33, no
    # solo el país: es lo que hace que «lo mandó vacío» signifique una sola cosa. Sin ella,
    # borrar el contenido de «Ciudad» en el panel guardaba `''` y borrar el de «País»
    # guardaba `NULL`, dos vacíos distintos en la misma fila y por la misma pantalla.
    _textos = field_validator(*TEXTOS_QUE_ADMITEN_VACIO)(texto_o_nada)
    # `source` sale de esa lista en el capítulo 41. Su columna es `NOT NULL`, así que
    # normalizarlo a `None` lo dejaba en manos del validador de modelo de abajo, que responde
    # un error **sin campo**: el aviso de arriba decía «revise estos campos» y ninguno de los
    # doce se ponía rojo. Con su propio validador el 422 llega con `loc`, y el mecanismo del
    # capítulo 40 lo pone debajo del canal.
    _source = field_validator("source")(exigir_texto)

    @model_validator(mode="after")
    def _vaciar_solo_lo_que_la_ficha_admite_vaciar(self) -> "LeadUpdate":
        """
        Un vacío explícito sobre un campo obligatorio se rechaza; nunca se ignora.

        Aquí está la diferencia que el capítulo 33 vino a arreglar. `model_fields_set` dice
        qué campos **vinieron en el cuerpo**, que no es lo mismo que qué campos valen `None`:
        un campo ausente y un campo enviado a nulo llegaban indistinguibles al repositorio, y
        el repositorio resolvía el empate ignorando los dos.

        Separadas las dos cosas, hay que decidir qué pasa con el vacío sobre un campo que la
        tabla declara `NOT NULL`. Se responde 422 y se nombra el campo. La alternativa
        —ignorarlo y devolver 200— es la que estaba, y es peor de lo que parece: no es que no
        obedezca, es que **contesta que sí**. El asesor borra el apellido, ve «Prospecto
        actualizado», y el apellido sigue ahí la próxima vez que abra la ficha.

        El capítulo 41 cambia una palabra: `is None` pasa a ser `en_blanco`. Con `is None` el
        mensaje —«La ficha no existe sin estos campos»— no se aplicaba al caso en que la ficha
        de verdad no los tenía, porque tres espacios no son `None` y llegaban a la columna
        intactos. Para la mayoría de los campos el recorte del `model_config` y el `min_length`
        ya lo resuelven antes de llegar aquí; esto es la red que no depende de que cada campo
        se acuerde de declarar un mínimo.
        """
        prohibidos = vacios_prohibidos(self, CAMPOS_QUE_NO_ADMITEN_VACIO)
        if prohibidos:
            raise ValueError(
                "La ficha no existe sin estos campos, así que no se pueden dejar vacíos: "
                + ", ".join(prohibidos)
                + ". Envíe un valor, o no envíe el campo si no quiere cambiarlo."
            )
        return self


class LeadResponse(LeadBase):
    # Sin mínimo de longitud en la respuesta. Una ficha creada por el CRM o un formulario que
    # no mandó el nombre lo tiene vacío —antes era «Prospecto» / «Sin Apellido», inventado—,
    # y un mínimo heredado de la entrada convertiría el listado entero en un error.
    first_name: str = Field(..., max_length=MAX_NAME)
    last_name: str = Field(..., max_length=MAX_NAME)
    id: int
    status: LeadStatus
    qualification_status: QualificationStatus
    current_score: float
    score_category: ScoreCategory
    conversion_probability: float
    last_score_update: datetime.datetime
    last_activity_at: datetime.datetime
    privacy_notice_accepted_at: Optional[datetime.datetime] = None
    privacy_notice_source: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def esperando_asesor(self) -> bool:
        """
        Llegó por una publicación y todavía no la atiende nadie.

        Lo decide el servidor y no el navegador a propósito: es la **misma** condición que
        cuenta el contador del líder (`nuevos_sin_asesor`). Calculada dos veces, en dos
        lenguajes, volvería a pasar lo del capítulo 27 —el número decía tres y en la lista
        había una sola marca, porque el listado seguía preguntando por «LinkedIn» cuando
        ya se llegaba por seis redes—.
        """
        return self.assigned_rep_id is None and es_de_publicacion(self.source)


class LeadDetailResponse(LeadResponse):
    activities: List[ActivityResponse] = Field(default_factory=list)
    score_histories: List[ScoreHistoryResponse] = Field(default_factory=list)
    latest_explanation: Optional[Dict[str, Any]] = None
    # De qué publicación llegó esta persona. `None` cuando no llegó de ninguna: la ficha no
    # pinta la tarjeta en vez de enseñarla vacía, que sugeriría un dato perdido.
    llego_por: Optional[LlegoPor] = None
    # Cómo acabó, si acabó (capítulo 30). `None` mientras siga en curso, y también en los
    # que se cerraron antes de que el desenlace existiera: la diferencia entre «no ha
    # cerrado» y «cerró y no sabemos por qué» la enseña la etapa, que sigue ahí.
    desenlace: Optional[DesenlaceDeLaFicha] = None


class LeadListResponse(BaseModel):
    """Respuesta paginada de la lista de prospectos con total para soporte de paginación en el frontend."""
    items: List[LeadResponse]
    total: int
    limit: int
    offset: int


class LeadListFilter(BaseModel):
    score_category: Optional[ScoreCategory] = None
    status: Optional[LeadStatus] = None
    industry: Optional[str] = Field(None, max_length=MAX_INDUSTRY)
    search: Optional[str] = Field(None, max_length=200)
    assigned_rep_id: Optional[int] = None
    min_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    max_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)
