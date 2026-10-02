from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.texto import ENTRADA_DE_TEXTO, texto_o_nada

# Ancho de las columnas de `Lead` en las que aterriza cada clave conocida de `data`.
# El webhook es la única entrada del sistema que no pasa por `LeadCreate`, así que sin
# esta comprobación un CRM externo podía enviar un `company` de 200 KB (por debajo del
# tope de 256 KiB del cuerpo) y provocar un fallo de inserción dentro del servicio.
CRM_DATA_MAX_LENGTHS: Dict[str, int] = {
    "first_name": 100,
    "last_name": 100,
    "email": 150,
    "phone": 50,
    "company": 150,
    "job_title": 100,
    "industry": 100,
    "company_size": 50,
    "country": 100,
    "city": 100,
    "source": 100,
    "activity_type": 50,
}


class CRMWebhookPayload(BaseModel):
    # Lo que el capítulo 41 corrige aquí es **el sobre**, no la carga.
    #
    # Los campos de `data` ya estaban cubiertos por dos sitios: el validador de abajo acota su
    # longitud y `_prospecto_normalizado` —en `registro_de_actividad`, desde el capítulo 25—
    # recorta cada uno y descarta el que se queda en nada. Un `data.city` de espacios no llega
    # a la columna desde entonces.
    #
    # El sobre no lo normalizaba nadie, y `crm_platform` es el valor que más lejos llega: es el
    # canal de la actividad (`lead_activities.channel`), la plataforma de las dos trazas
    # (`crm_integration_logs`, `webhook_deliveries`) —cuatro columnas `NOT NULL`— y, lo
    # importante, el prefijo del identificador con el que el evento se deduplica para siempre.
    # «HubSpot» y «HubSpot » son dos prefijos distintos, así que el mismo evento del mismo CRM
    # entregado con un espacio de más **vuelve a entrar**: una actividad duplicada en la ficha
    # y un score recalculado sobre un hecho que ocurrió una vez. Es el mismo fallo que §3.10
    # describe para los CRM que no mandan `event_id`, pero por una causa que sí está en
    # nuestras manos.
    #
    # Con mínimo, además: un sobre sin plataforma no identifica a nadie y no puede ser el canal
    # de una columna obligatoria. Es un 422 al emisor, que es quien puede corregirlo.
    model_config = ENTRADA_DE_TEXTO

    event: str = Field("lead.created", min_length=1, max_length=50, description="Tipo de evento CRM (lead.created, lead.updated, form.submission)")
    crm_platform: str = Field("HubSpot", min_length=1, max_length=50, description="Plataforma de origen (HubSpot, Salesforce, Zoho, CustomCRM)")
    external_lead_id: Optional[str] = Field(None, max_length=100, description="Identificador único en el CRM externo")
    data: Dict[str, Any] = Field(..., description="Carga útil con los atributos del prospecto y actividad")

    # El identificador del prospecto en el CRM ajeno: en blanco es que no lo mandó, no que su
    # identificador sea la cadena vacía. Se guarda en `webhook_deliveries.external_lead_id`,
    # que admite nulo precisamente para decir eso.
    _external = field_validator("external_lead_id")(texto_o_nada)

    @field_validator("data")
    @classmethod
    def _validate_known_field_lengths(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        """
        Acota las claves que se copian a columnas de `leads`.

        `data` sigue siendo abierto a propósito —los campos que no reconocemos se
        conservan en `raw_metadata` para no perder información del CRM emisor—, pero las
        que sí sabemos dónde acaban se validan aquí, en el borde, para responder 422 en
        vez de romper el INSERT.
        """
        for field, max_length in CRM_DATA_MAX_LENGTHS.items():
            raw = value.get(field)
            if isinstance(raw, str) and len(raw) > max_length:
                raise ValueError(
                    f"El campo 'data.{field}' excede el máximo de {max_length} caracteres "
                    f"(recibidos {len(raw)})."
                )
        return value


class CRMIngestResponse(BaseModel):
    status: str
    message: str
    lead_id: int
    external_crm_id: Optional[str] = None
    calculated_score: float
    score_category: str
    assigned_rep: Optional[str] = None
