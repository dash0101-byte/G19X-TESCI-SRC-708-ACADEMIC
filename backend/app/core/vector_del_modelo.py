"""
El vector de variables del modelo: qué columnas, en qué orden y qué significa cada una.

Vive en un solo sitio porque lo consumen cuatro: el adaptador que puntúa en producción, el
servicio que guarda la instantánea, el entrenamiento y el extractor del dataset real. La
primera vez que esas listas se escribieron por separado (ML-4), el adaptador dejó de pasar
las cuatro señales comerciales más fuertes y nada falló.

## Versión 2 (capítulo 24): sin datos inventados

La versión 1 tenía tres variables que no medían lo que su nombre decía:

* **`annual_revenue`** llegaba al modelo como 100 000 cuando el prospecto no la declaraba,
  porque el preprocesador no sabía qué hacer con un hueco. El modelo leía una empresa
  pequeña donde solo había un dato ausente. Ahora la ausencia viaja como ausencia, el
  preprocesador la imputa con la mediana del entrenamiento y añade una columna que dice
  que faltaba: «no lo sabemos» y «factura poco» dejan de ser lo mismo.
* **`whatsapp_messages`** contaba también los mensajes de LinkedIn. Son dos canales con
  intención distinta —uno lo abre casi siempre el prospecto, el otro casi siempre el
  asesor— y ahora son dos variables.
* **`phone_calls`** contaba solo las llamadas que conectaron, y el resto se perdía. Un
  prospecto al que se ha llamado seis veces sin respuesta no es igual que uno al que no se
  ha llamado nunca. Ahora el resultado de la llamada es la variable: conectadas por un lado,
  sin respuesta —no contestó o buzón— por otro.

Una instantánea de la versión 1 no se puede traducir a la 2 sin inventar: no dice qué
mensajes eran de LinkedIn ni cuántas llamadas quedaron sin respuesta. Por eso cada
instantánea lleva `version_del_vector`, y quien la lee descarta las que no son de la
versión vigente en lugar de rellenar lo que no sabe.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

VERSION_DEL_VECTOR = 2

# Clave con la que la instantánea declara su versión. Las de la versión 1 no la llevan.
CLAVE_DE_VERSION = "version_del_vector"

CATEGORICAS: List[str] = ["job_title", "industry", "company_size", "source_channel"]

# Los valores que el modelo aprendió de cada variable categórica, en un solo sitio.
#
# El preprocesador descarta en silencio las categorías que no vio al entrenar
# (`OneHotEncoder(handle_unknown="ignore")`): un sector escrito de otra forma no produce un
# error, simplemente deja de verse. Por eso el formulario público ofrece exactamente estos
# valores y no una lista parecida, y por eso `tests/test_categorias_del_modelo.py` los
# compara contra el artefacto servido y contra el generador del dataset.
#
# `source_channel` está aquí para la misma comprobación, pero no es una lista de formulario:
# el canal lo escribe el sistema según por dónde entró la persona. La página de interés
# escribe «LinkedIn», que el modelo todavía no conoce —una publicación orgánica no es
# «LinkedIn Ads»— y hasta el próximo reentrenamiento cuenta como canal desconocido, es decir,
# neutro. Escribir «LinkedIn Ads» para que sume sería declarar un origen que no es.
CATEGORIAS_DEL_MODELO: Dict[str, Tuple[str, ...]] = {
    "job_title": (
        "CTO",
        "CIO",
        "Director de Tecnología",
        "VP de Recursos Humanos",
        "Head of Engineering",
        "Gerente de Talento TI",
        "Engineering Manager",
        "Director de Operaciones",
        "Gerente de Proyectos TI",
        "Líder Técnico",
        "Desarrollador Senior",
        "Consultor Independiente",
        "Estudiante / Trainee",
    ),
    "industry": (
        "FinTech",
        "Software/TI",
        "Banking",
        "E-Commerce",
        "Healthcare",
        "Logistics",
        "Retail",
        "Consulting",
        "Manufacturing",
        "Education",
    ),
    "company_size": ("1-10", "11-50", "51-200", "201-1000", "1000+"),
    "source_channel": (
        "LinkedIn Ads",
        "Webinar",
        "Demo Request Form",
        "Organic Search",
        "Outbound Cold Email",
        "Referral",
    ),
}

# Las únicas numéricas que pueden faltar. El resto son recuentos que el sistema calcula
# desde las actividades y que siempre existen, aunque valgan cero.
NUMERICAS_CON_AUSENTES: List[str] = ["annual_revenue"]

NUMERICAS_COMPLETAS: List[str] = [
    "page_views",
    "email_opens",
    "email_clicks",
    "content_downloads",
    "attended_webinar",
    "requested_demo",
    "meeting_scheduled",
    "proposal_sent",
    "phone_calls_connected",
    "phone_calls_unanswered",
    "whatsapp_messages",
    "linkedin_messages",
    "days_since_last_activity",
]

# Orden en que se entrena y se guarda. El preprocesador selecciona por nombre, así que el
# orden no cambia la predicción, pero sí la huella de los datos.
COLUMNAS_DEL_MODELO: List[str] = [
    "job_title",
    "industry",
    "company_size",
    "annual_revenue",
    "source_channel",
    *NUMERICAS_COMPLETAS,
]

# Lo que la instantánea guarda por sí misma; los firmográficos se leen de la ficha.
CONDUCTUALES: List[str] = list(NUMERICAS_COMPLETAS)


def ingresos_o_ausente(valor: Any) -> Optional[float]:
    """
    Los ingresos anuales declarados, o `None` si no hay un dato utilizable.

    Cero cuenta como ausente. Ninguna empresa a la que se vende este servicio factura cero,
    y hasta el capítulo 24 el cero era lo que escribían el alta del panel, el esquema de la
    API y la ingesta de integraciones cuando el campo llegaba vacío: en la base, un cero es
    un hueco rellenado, no una cifra.
    """
    if valor is None or valor == "":
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    if math.isnan(numero) or numero <= 0:
        return None
    return numero


def es_instantanea_vigente(instantanea: Any) -> bool:
    """¿Se tomó esta instantánea con el vector que consume el modelo actual?"""
    return isinstance(instantanea, dict) and instantanea.get(CLAVE_DE_VERSION) == VERSION_DEL_VECTOR
