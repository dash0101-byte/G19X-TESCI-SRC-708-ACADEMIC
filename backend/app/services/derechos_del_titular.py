"""
Derechos de la persona cuyos datos guarda el sistema: acceso y supresión (R-11).

Un prospecto es una persona con nombre, correo, teléfono, cargo y empresa, y el sistema
guarda además lo que hizo —qué páginas vio, qué correos abrió—, cómo se la puntuó y por
qué. Hasta ahora no había forma de responder a «¿qué sabéis de mí?» sin abrir la base a
mano, y el borrado dejaba cosas atrás: las entregas de webhook (clave foránea con
`SET NULL`), los registros de ingesta revertida —que no tienen `lead_id` porque el alta no
llegó a existir— y el correo de la persona dentro de la propia bitácora.

Un solo mapa para exportar y para borrar
----------------------------------------
`TABLAS_DEL_PROSPECTO` enumera las tablas que cuelgan de `leads`. La exportación y la
supresión lo recorren las dos, y la suite compara ese mapa con las claves foráneas reales
del esquema: una tabla nueva que apunte a `leads` rompe las pruebas hasta que alguien
decida qué hacer con ella. Es el mismo principio que la enumeración de rutas de la
contraseña prestada: lo que no se declara explícitamente nace cubierto, no olvidado.

Las columnas no se listan a mano: se exportan todas las del modelo. Una columna nueva sale
en la exportación el mismo día que se crea.

Lo que no cuelga de `leads`
---------------------------
Dos sitios guardan datos de la persona sin clave foránea, y se buscan por su contenido:
los registros de ingesta revertida (por correo, dentro de la carga) y, desde la Fase 15, la
bandeja «Sin asociar» (por correo o por teléfono): un mensaje de WhatsApp de su número que
nadie vinculó todavía también es un dato suyo.

La bitácora
-----------
La bitácora no se borra: dice quién hizo qué y cuándo, y eso sigue siendo cierto después
de suprimir a la persona. Lo que se retira de sus asientos es el dato personal —el correo
que `lead.crear` anotaba, la empresa, el teléfono— y se sustituye por `[suprimido]`. El
asiento del propio borrado no guarda el correo: guarda una huella con clave
(`huella_del_titular`), que permite responder «¿se suprimió a ana@ejemplo.com?» a quien ya
conoce el correo, sin que la bitácora se lo diga a quien no.
"""
import datetime
import enum
import hashlib
import hmac
import logging
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import String, cast, func, inspect, or_
from sqlalchemy.orm import Session

from app.core.audit import ENTIDAD_LEAD
from app.core.config import settings
from app.core.database import Base
from app.models.entities import AuditLog, CRMIntegrationLog, Lead, UnmatchedEvent

logger = logging.getLogger(__name__)

FORMATO_EXPORTACION = "plurione.titular/1"
SUPRIMIDO = "[suprimido]"

# Tabla que cuelga de `leads` → sección de la exportación. Ver la prueba
# `test_el_mapa_cubre_todas_las_tablas_que_apuntan_a_leads`.
TABLAS_DEL_PROSPECTO: Dict[str, str] = {
    "lead_activities": "actividades",
    "score_histories": "historial_de_puntuacion",
    "score_history_monthly": "resumen_mensual_de_puntuacion",
    "crm_integration_logs": "integraciones_crm",
    "webhook_deliveries": "entregas_de_webhook",
    # Capítulo 28. Lo que el sistema mandó hacer sobre esta persona y a quién se lo avisó
    # también es tratamiento de sus datos: entra en la exportación y se va en la supresión.
    "tareas": "tareas",
    "avisos": "avisos",
}

# Lo que el sistema NO puede alcanzar desde la base, dicho en la propia exportación. Una
# respuesta de acceso que calla dónde más están los datos no responde a la pregunta.
FUERA_DE_LA_BASE = [
    "Copias de seguridad: los volcados diarios de PostgreSQL conservan los datos hasta "
    "RETENCION_DIAS días (14 por defecto) después de una supresión; no se editan.",
    "Conjuntos de entrenamiento: si el prospecto llegó a un desenlace (ganado, perdido o "
    "descartado), su instantánea de entrada pudo exportarse a un CSV fuera de la base "
    "(ml_pipeline/data/leads_reales*) para reentrenar el modelo. El modelo resultante no "
    "guarda filas individuales.",
    "Sistemas de origen: los datos pudieron llegar desde un CRM, el formulario web, LinkedIn "
    "Lead Gen, Calendly o WhatsApp. Suprimirlos aquí no los suprime allí, y una nueva entrega "
    "de cualquiera de ellos volvería a crearlos.",
]


def _modelo_de_tabla(nombre: str):
    for mapeo in Base.registry.mappers:
        if mapeo.local_table is not None and mapeo.local_table.name == nombre:
            return mapeo.class_
    raise LookupError(f"No hay modelo para la tabla '{nombre}'.")


def tablas_que_apuntan_a_leads() -> List[str]:
    """Tablas del esquema con alguna clave foránea hacia `leads.id`."""
    return sorted(
        tabla.name
        for tabla in Base.metadata.sorted_tables
        if any(fk.column.table.name == Lead.__tablename__ for fk in tabla.foreign_keys)
    )


def _valor(valor: Any) -> Any:
    if isinstance(valor, datetime.datetime):
        if valor.tzinfo is None:
            valor = valor.replace(tzinfo=datetime.timezone.utc)
        return valor.isoformat()
    if isinstance(valor, datetime.date):
        return valor.isoformat()
    if isinstance(valor, enum.Enum):
        return valor.value
    return valor


def _fila(objeto) -> Dict[str, Any]:
    return {atributo.key: _valor(getattr(objeto, atributo.key)) for atributo in inspect(objeto).mapper.column_attrs}


def huella_del_titular(email: str) -> str:
    """
    Huella con clave del correo de una persona suprimida.

    Con clave y no un SHA-256 a secas: sin ella, cualquiera con una lista de correos —el
    propio CRM, sin ir más lejos— recorrería la bitácora y sabría quién pidió que lo
    borraran. Con clave, solo puede comprobarlo quien opera el sistema. Rotar
    `SECRET_KEY` deja las huellas anteriores sin forma de comprobarse, que para un registro
    de supresiones es un efecto aceptable.
    """
    normalizado = email.strip().lower().encode("utf-8")
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), b"titular:" + normalizado, hashlib.sha256).hexdigest()[:32]


def _identificativos(lead: Lead) -> List[str]:
    """
    Valores que, dentro de un texto libre, delatan a la persona.

    Nombre y apellido sueltos no: «Ana» o «García» aparecen en asientos de otras personas.
    El nombre completo, el correo, el teléfono y la empresa sí. Los muy cortos se descartan
    porque suprimirían medio registro por coincidencia.
    """
    candidatos = [
        lead.email,
        f"{lead.first_name or ''} {lead.last_name or ''}".strip(),
        lead.phone,
        lead.company,
    ]
    return sorted({c.strip().lower() for c in candidatos if c and len(c.strip()) >= 4})


def _retirar(valor: Any, identificativos: Iterable[str]) -> Any:
    if isinstance(valor, str):
        texto = valor.lower()
        return SUPRIMIDO if any(dato in texto for dato in identificativos) else valor
    if isinstance(valor, dict):
        return {clave: _retirar(contenido, identificativos) for clave, contenido in valor.items()}
    if isinstance(valor, list):
        return [_retirar(contenido, identificativos) for contenido in valor]
    return valor


def _contiene(valor: Any, email: str) -> bool:
    if isinstance(valor, str):
        return valor.strip().lower() == email
    if isinstance(valor, dict):
        return any(_contiene(contenido, email) for contenido in valor.values())
    if isinstance(valor, list):
        return any(_contiene(contenido, email) for contenido in valor)
    return False


def _ingestas_sin_vincular(db: Session, email: str) -> List[CRMIntegrationLog]:
    """
    Registros de ingesta revertida que llevan el correo de la persona pero no su `lead_id`.

    Cuando la ingesta falla antes de que el alta exista, el registro guarda la carga
    completa del CRM y no tiene a qué fila apuntar. La búsqueda es en dos pasos: un LIKE
    sobre el JSON como texto para no leer la tabla entera, y una comprobación exacta sobre
    los valores para no llevarse a «diana@x.com» al buscar «ana@x.com».
    """
    correo = email.strip().lower()
    patron = "%" + correo.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    posibles = (
        db.query(CRMIntegrationLog)
        .filter(CRMIntegrationLog.lead_id.is_(None))
        .filter(func.lower(cast(CRMIntegrationLog.payload, String)).like(patron, escape="\\"))
        .all()
    )
    return [registro for registro in posibles if _contiene(registro.payload, correo)]


def _eventos_sin_asociar(db: Session, lead: Lead) -> List[UnmatchedEvent]:
    """
    Avisos de la bandeja «Sin asociar» con el correo o el teléfono de la persona.

    Por igualdad exacta, no por contenido: la bandeja guarda correo y teléfono ya
    normalizados —minúsculas y E.164—, así que «diana@x.com» no sale al buscar «ana@x.com».
    """
    condiciones = []
    if lead.email:
        condiciones.append(func.lower(UnmatchedEvent.contact_email) == lead.email.strip().lower())
    if lead.phone:
        condiciones.append(UnmatchedEvent.contact_phone == lead.phone)
    if not condiciones:
        return []
    return db.query(UnmatchedEvent).filter(or_(*condiciones)).order_by(UnmatchedEvent.id).all()


def _asientos_del_prospecto(db: Session, lead_id: int) -> List[AuditLog]:
    return (
        db.query(AuditLog)
        .filter(AuditLog.entity == ENTIDAD_LEAD, AuditLog.entity_id == str(lead_id))
        .order_by(AuditLog.occurred_at, AuditLog.id)
        .all()
    )


def exportar_prospecto(db: Session, lead: Lead, *, ahora: Optional[datetime.datetime] = None) -> Dict[str, Any]:
    """Todo lo que el sistema guarda de esta persona, en un documento JSON."""
    documento: Dict[str, Any] = {
        "formato": FORMATO_EXPORTACION,
        "generado_en": _valor(ahora or datetime.datetime.now(datetime.timezone.utc)),
        "prospecto_id": lead.id,
        "datos_del_prospecto": _fila(lead),
        # De la campaña y del asesor, lo que describe la relación con esta persona. El
        # correo del asesor es un dato personal del asesor, no del prospecto.
        "campana": (
            {
                clave: _valor(getattr(lead.campaign, clave))
                for clave in ("id", "name", "channel", "utm_source", "utm_medium", "utm_campaign")
            }
            if lead.campaign
            else None
        ),
        "asesor_asignado": (
            {"id": lead.assigned_rep.id, "nombre": lead.assigned_rep.full_name} if lead.assigned_rep else None
        ),
    }

    for tabla, seccion in TABLAS_DEL_PROSPECTO.items():
        modelo = _modelo_de_tabla(tabla)
        filas = db.query(modelo).filter(modelo.lead_id == lead.id).order_by(modelo.id).all()
        documento[seccion] = [_fila(fila) for fila in filas]

    documento["integraciones_crm_sin_vincular"] = [_fila(r) for r in _ingestas_sin_vincular(db, lead.email)]
    documento["eventos_sin_asociar"] = [_fila(e) for e in _eventos_sin_asociar(db, lead)]

    # Qué se hizo con sus datos y cuándo. Quién lo hizo se da por rol: el correo y la IP
    # del empleado son datos personales del empleado.
    documento["tratamientos_registrados"] = [
        {
            "accion": asiento.action,
            "resultado": asiento.outcome,
            "rol": asiento.actor_role,
            "ocurrido_en": _valor(asiento.occurred_at),
        }
        for asiento in _asientos_del_prospecto(db, lead.id)
    ]
    documento["conservacion"] = {
        "historial_de_puntuacion": (
            f"Detalle de los últimos {settings.SCORE_HISTORY_RETENTION_MONTHS} meses completos más el "
            "mes en curso; lo anterior, resumido por mes. Se conservan siempre la puntuación de "
            "entrada y la vigente."
        ),
        "mensajes": (
            "Del contenido de los mensajes no se guarda nada: solo el tipo, la dirección, la fecha "
            "y el identificador que les dio el sistema de origen."
        ),
        "resto_de_datos": "Mientras el prospecto exista en el sistema o hasta que se solicite su supresión.",
    }
    documento["fuera_de_la_base"] = FUERA_DE_LA_BASE
    return documento


def suprimir_prospecto(db: Session, lead: Lead) -> Dict[str, int]:
    """
    Borra al prospecto y todo lo que cuelga de él, y retira sus datos de la bitácora.

    Devuelve cuántas filas se fueron de cada sitio: es lo que el asiento del borrado guarda
    en lugar del correo. Todo ocurre en una transacción; si algo falla, no se borra nada.
    """
    lead_id = lead.id
    email = lead.email
    identificativos = _identificativos(lead)
    pendientes = [evento.id for evento in _eventos_sin_asociar(db, lead)]
    recuento: Dict[str, int] = {}

    try:
        for tabla in TABLAS_DEL_PROSPECTO:
            modelo = _modelo_de_tabla(tabla)
            recuento[tabla] = db.query(modelo).filter(modelo.lead_id == lead_id).delete(synchronize_session=False)

        sin_vincular = [registro.id for registro in _ingestas_sin_vincular(db, email)]
        recuento["crm_integration_logs_sin_vincular"] = (
            db.query(CRMIntegrationLog)
            .filter(CRMIntegrationLog.id.in_(sin_vincular))
            .delete(synchronize_session=False)
            if sin_vincular
            else 0
        )

        recuento["unmatched_events"] = (
            db.query(UnmatchedEvent)
            .filter(UnmatchedEvent.id.in_(pendientes))
            .delete(synchronize_session=False)
            if pendientes
            else 0
        )

        retirados = 0
        for asiento in _asientos_del_prospecto(db, lead_id):
            limpio = _retirar(asiento.event_metadata or {}, identificativos)
            if limpio != (asiento.event_metadata or {}):
                asiento.event_metadata = limpio
                retirados += 1
        recuento["asientos_con_datos_retirados"] = retirados

        recuento["leads"] = db.query(Lead).filter(Lead.id == lead_id).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
        raise

    # Los objetos de la sesión apuntan a filas que ya no existen.
    db.expire_all()
    logger.info("Prospecto %s suprimido con todos sus registros asociados.", lead_id)
    return recuento
