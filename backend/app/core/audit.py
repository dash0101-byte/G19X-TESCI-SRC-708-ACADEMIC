"""
Bitácora de auditoría: quién hizo qué, sobre qué, desde dónde y con qué resultado.

Lo que faltaba
--------------
El sistema trazaba lo que les pasaba a los datos —la sincronización con el CRM en
`crm_integration_logs`, cada puntuación en `score_histories`— pero no lo que hacían las
personas. Un prospecto borrado desaparecía sin dejar constancia de quién lo borró. Un
recálculo masivo, que reescribe la cartera entera, solo se sabía por el `logger` del
contenedor, que rota y se pierde. Y un intento denegado por rol no dejaba absolutamente
nada: la única señal de que alguien estaba tanteando los límites de sus permisos era una
línea de texto entre miles.

Cómo se escribe
---------------
Desde una dependencia con `yield`, no desde cada endpoint. Un `db.add(AuditLog(...))`
repetido a mano en veinte sitios se olvida en el veintiuno, y el que se olvida es siempre
el que hace falta. La dependencia se declara junto a las demás y el endpoint solo añade
el detalle que conoce —qué identificador tocó— con `asiento.anotar(...)`. El resultado lo
pone la propia dependencia: si el endpoint lanza, el asiento queda con el código de estado
en lugar de con `OK`.

Sobre qué sesión se escribe
---------------------------
Sobre la misma de la petición, no sobre una independiente. La tentación es abrirla aparte
para que la bitácora sobreviva a un `rollback` del negocio, pero el desmontaje de esta
dependencia ocurre **después** de que el endpoint haya terminado: a esas alturas la
transacción de negocio ya se confirmó o ya se deshizo, y no queda nada que un `rollback`
propio pueda llevarse por delante. A cambio se evita un problema real: con SQLite en
memoria y `StaticPool` —la configuración de la suite— dos sesiones comparten la misma
conexión, así que un `commit` desde la sesión «independiente» confirmaría de paso lo que
hubiera pendiente en la otra. Se hace un `rollback` explícito antes de escribir para
limpiar una sesión que hubiera quedado en estado fallido tras un 500.
"""
import logging
from typing import Any, Dict, Optional

from app.core.database import get_db
from app.core.proxy import ip_del_cliente
from app.core.security import CurrentUser, get_current_user
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Longitudes máximas de lo que se copia a columnas acotadas. El `User-Agent` lo escribe
# el cliente y no tiene tope por protocolo: sin recorte, una cabecera larga convertiría
# cada operación auditada en un fallo de inserción.
LONGITUD_MAXIMA_AGENTE = 255
LONGITUD_MAXIMA_ENTIDAD_ID = 64

RESULTADO_OK = "OK"
RESULTADO_ERROR = "ERROR"

# Acciones auditadas. Se declaran como constantes y no como cadenas sueltas para que un
# error tipográfico en un endpoint no cree una acción nueva que ninguna consulta encuentre.
ACCION_LOGIN = "auth.login"
ACCION_LOGIN_FALLIDO = "auth.login_fallido"  # noqa: S105  nombre de acción, no una credencial
ACCION_LOGOUT = "auth.logout"
ACCION_REFRESH_REUTILIZADO = "auth.refresh_reutilizado"  # noqa: S105  ídem
ACCION_ACCESO_DENEGADO = "acceso.denegado"
# Se pidió un prospecto que existe y pertenece a otra persona. Hacia fuera la respuesta es
# un 404 indistinguible de "no existe" —lo contrario permitiría recorrer identificadores
# para dibujar la cartera ajena—, pero hacia dentro la diferencia es justo lo que hay que
# poder ver: un 404 aislado es un enlace viejo, una tanda seguida es alguien tanteando.
ACCION_ACCESO_FUERA_DE_ALCANCE = "acceso.fuera_de_alcance"
ACCION_LEAD_CREAR = "lead.crear"
ACCION_LEAD_ACTUALIZAR = "lead.actualizar"
ACCION_LEAD_ELIMINAR = "lead.eliminar"
ACCION_LEAD_ACTIVIDAD = "lead.actividad"
# Entregar a alguien todo lo que el sistema sabe de una persona es un tratamiento de sus
# datos como cualquier otro, y además el más completo: tiene que quedar quién lo pidió.
ACCION_LEAD_EXPORTAR = "lead.exportar"
# La purga programada del historial. No la hace una persona —el asiento va sin actor—, pero
# borra datos, y «¿cuándo se resumió esto y cuántas filas se fueron?» tiene que tener
# respuesta en el mismo sitio donde se contesta todo lo demás.
ACCION_HISTORIAL_RETENCION = "historial.retencion"
# Lo mismo para los demás datos con plazo (capítulo 22): sesiones, trabajos de recálculo,
# registros del CRM y bandeja «Sin asociar». Un asiento por plazo y pasada, también cuando
# no hubo nada que borrar —«la purga corrió y no encontró nada» es distinto de «no corrió»—
# y también cuando falló, con el resultado `ERROR`.
ACCION_CONSERVACION_PURGA = "conservacion.purga"
ACCION_RECALCULO_MASIVO = "scoring.recalculo_masivo"
ACCION_AUDITORIA_CONSULTA = "auditoria.consulta"

# --- Gestión de identidades ---
# Toda mutación sobre una cuenta queda escrita. Es la superficie más sensible del sistema:
# quien puede cambiar roles puede darse permisos, y quien puede restablecer contraseñas
# puede entrar como otra persona. Sin registro, ambas cosas son indistinguibles del uso
# normal.
ACCION_USUARIO_CREAR = "usuario.crear"
ACCION_USUARIO_ACTUALIZAR = "usuario.actualizar"
ACCION_USUARIO_DESACTIVAR = "usuario.desactivar"
ACCION_USUARIO_REACTIVAR = "usuario.reactivar"
ACCION_USUARIO_CAMBIO_DE_ROL = "usuario.cambio_de_rol"
ACCION_USUARIO_RESET_CONTRASENA = "usuario.reset_contrasena"  # noqa: S105  nombre de acción
ACCION_CONTRASENA_PROPIA = "usuario.cambio_de_contrasena_propia"  # noqa: S105  ídem
ACCION_CARTERA_REPARTIR = "usuario.reparto_de_cartera"

ACCION_CAMPANA_CREAR = "campana.crear"
ACCION_CAMPANA_ACTUALIZAR = "campana.actualizar"
ACCION_CAMPANA_DESACTIVAR = "campana.desactivar"
# Duplicar crea una campaña nueva a partir de otra: queda escrito de cuál salió.
ACCION_CAMPANA_DUPLICAR = "campana.duplicar"
# Consultar el informe de una publicación es leer, de una sentada, el nombre y la empresa
# de todas las personas que respondieron a un post. Que sea una lectura no lo hace menor:
# es el acceso más amplio a datos de contacto que ofrece la aplicación después de la
# exportación, y queda escrito con los filtros y el número de filas, nunca con las filas.
ACCION_PUBLICACION_INFORME = "publicacion.informe"
# La comparativa no lleva datos de nadie —son totales por publicación—, pero describe el
# rendimiento comercial entero, y quién lo consultó es parte de la misma pregunta.
ACCION_PUBLICACION_COMPARATIVA = "publicacion.comparativa"

# --- Registro de actividad (Fase 15) ---
# Vincular un aviso de la bandeja «Sin asociar» a un prospecto es decidir de quién es un
# dato; descartarlo es borrarlo. Las dos cosas las hace una persona y tienen que poder
# atribuirse.
ACCION_EVENTO_VINCULAR = "evento.vincular"
ACCION_EVENTO_DESCARTAR = "evento.descartar"
# Una entrega aceptada de una integración: cuántos eventos traía y en qué acabó cada uno.
# Sin actor, como la purga del historial, y sin datos de contacto.
ACCION_INTEGRACION_ENTREGA = "integracion.entrega"

# --- El motor de reglas (capítulo 28) ---
# Una pasada de una regla: cuántas tareas y cuántos avisos creó, cuántas cerró y si falló.
# Sin actor, como la purga: no la pidió nadie, la disparó el reloj. Sin datos de contacto:
# la bitácora cuenta cuántos, nunca quiénes.
ACCION_REGLA_EJECUCION = "regla.ejecucion"
# Una persona dice que ya hizo una tarea. Es una afirmación sobre su propio trabajo y por
# eso lleva actor; el sistema cerrando una tarea porque ocurrió lo que esperaba, no.
ACCION_TAREA_HECHA = "tarea.hecha"

# --- El desenlace (capítulo 30) ---
# Cerrar un prospecto es la única decisión del sistema que produce una etiqueta de
# entrenamiento. Quién dijo que este trato se ganó, cuándo y por qué motivo tiene que poder
# atribuirse: el día que una métrica del modelo sorprenda, la primera pregunta será de
# dónde salieron las etiquetas. Se anota el motivo —una clave de una lista cerrada— y
# nunca el nombre ni la empresa de nadie.
ACCION_DESENLACE_REGISTRAR = "desenlace.registrar"
# El panel del líder son totales por motivo, publicación y red, sin una sola fila con
# nombre. Se anota igual que la comparativa de publicaciones y por lo mismo: describe el
# rendimiento comercial entero, y quién lo consultó es parte de la misma pregunta.
ACCION_DESENLACE_PANEL = "desenlace.panel"

ENTIDAD_SESION = "sesion"
ENTIDAD_LEAD = "lead"
ENTIDAD_ENDPOINT = "endpoint"
ENTIDAD_TRABAJO = "trabajo_de_scoring"
ENTIDAD_AUDITORIA = "bitacora"
ENTIDAD_USUARIO = "usuario"
ENTIDAD_CAMPANA = "campana"
ENTIDAD_HISTORIAL = "historial_de_puntuacion"
ENTIDAD_EVENTO_SIN_ASOCIAR = "evento_sin_asociar"
ENTIDAD_INTEGRACION = "integracion"
ENTIDAD_REGISTRO_CRM = "registro_crm"
ENTIDAD_REGLA = "regla"
ENTIDAD_TAREA = "tarea"
ENTIDAD_AVISO = "aviso"
ENTIDAD_DESENLACE = "desenlace"
# Capítulo 32. La única entidad de esta lista que no es una tabla: el conjunto de
# realimentación son archivos, y su plazo cuenta archivos en lugar de filas.
ENTIDAD_REALIMENTACION = "conjunto_de_realimentacion"


def _recortar(valor: Optional[str], limite: int) -> Optional[str]:
    if valor is None:
        return None
    texto = str(valor)
    return texto if len(texto) <= limite else texto[:limite]


def registrar_evento(
    db: Session,
    *,
    accion: str,
    entidad: str,
    entidad_id: Optional[str] = None,
    resultado: str = RESULTADO_OK,
    actor_id: Optional[int] = None,
    actor_email: Optional[str] = None,
    actor_role: Optional[str] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    metadatos: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Escribe un asiento en la bitácora.

    Nunca propaga una excepción. Que la auditoría falle no puede convertir una operación
    correcta en un 500 para el usuario: el asiento se pierde —y el fallo queda en el log
    del servidor, que es donde alguien puede verlo— pero la operación se respeta. Al revés
    sería peor de lo que se intenta arreglar.
    """
    # Import local: `app.models.entities` importa `app.core.database`, y este módulo lo
    # importan las rutas; hacerlo arriba cerraría el ciclo.
    from app.models.entities import AuditLog

    try:
        db.add(
            AuditLog(
                actor_id=actor_id,
                actor_email=_recortar(actor_email, 150),
                actor_role=_recortar(actor_role, 50),
                action=_recortar(accion, 60),
                entity=_recortar(entidad, 60),
                entity_id=_recortar(entidad_id, LONGITUD_MAXIMA_ENTIDAD_ID),
                outcome=_recortar(resultado, 20) or RESULTADO_OK,
                ip_address=_recortar(ip, 64),
                user_agent=_recortar(user_agent, LONGITUD_MAXIMA_AGENTE),
                event_metadata=metadatos or {},
            )
        )
        db.commit()
    except Exception:
        logger.exception(
            "No fue posible escribir el asiento de auditoría '%s' sobre %s.", accion, entidad
        )
        try:
            db.rollback()
        except Exception:
            logger.exception("Tampoco fue posible deshacer la sesión tras el fallo de auditoría.")


class AsientoDeAuditoria:
    """
    Asiento en construcción durante una petición.

    Lo crea la dependencia, lo enriquece el endpoint con `anotar(...)` y lo escribe la
    dependencia al terminar. El endpoint no decide el resultado: si lanza una excepción, la
    dependencia sustituye el `OK` por el estado real, de modo que un 404 o un 409 quedan
    registrados como lo que fueron y no como una operación correcta.
    """

    def __init__(
        self,
        *,
        accion: str,
        entidad: str,
        db: Session,
        actor: Optional[CurrentUser] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        self.accion = accion
        self.entidad = entidad
        self.db = db
        self.actor = actor
        self.ip = ip
        self.user_agent = user_agent
        self.entidad_id: Optional[str] = None
        self.resultado: str = RESULTADO_OK
        self.metadatos: Dict[str, Any] = {}

    def anotar(self, *, entidad_id: Optional[Any] = None, **metadatos: Any) -> None:
        """Añade al asiento lo que solo el endpoint sabe: sobre qué actuó y con qué detalle."""
        if entidad_id is not None:
            self.entidad_id = str(entidad_id)
        self.metadatos.update(metadatos)

    def persistir(self) -> None:
        actor_id: Optional[int] = None
        if self.actor is not None:
            try:
                actor_id = int(self.actor.user_id)
            except (TypeError, ValueError):
                actor_id = None

        # Limpia una sesión que hubiera quedado en estado fallido tras una excepción del
        # endpoint. Sin esto, el `add` siguiente moriría con PendingRollbackError y el
        # asiento del error —el que más interesa— sería justo el que no se escribe.
        try:
            self.db.rollback()
        except Exception:
            logger.exception("La sesión no admitió el rollback previo al asiento de auditoría.")
            return

        registrar_evento(
            self.db,
            accion=self.accion,
            entidad=self.entidad,
            entidad_id=self.entidad_id,
            resultado=self.resultado,
            actor_id=actor_id,
            actor_email=self.actor.email if self.actor else None,
            actor_role=self.actor.role.value if self.actor else None,
            ip=self.ip,
            user_agent=self.user_agent,
            metadatos=self.metadatos,
        )


def auditar(accion: str, entidad: str):
    """
    Fábrica de dependencias que auditan una operación.

    Se declara en el endpoint junto a las demás dependencias:

        auditoria: AsientoDeAuditoria = Depends(auditar(ACCION_LEAD_ELIMINAR, ENTIDAD_LEAD))

    y dentro del cuerpo se anota lo que corresponda:

        auditoria.anotar(entidad_id=lead_id, email=lead.email)

    El asiento se escribe siempre, tanto si la operación sale bien como si no. Un borrado
    que devolvió 404 es información: dice que alguien intentó borrar algo que no estaba, y
    esa es exactamente la traza que se busca cuando se investiga qué pasó con un registro.
    """

    def dependencia(
        request: Request,
        db: Session = Depends(get_db),
        current_user: CurrentUser = Depends(get_current_user),
    ):
        asiento = AsientoDeAuditoria(
            accion=accion,
            entidad=entidad,
            db=db,
            actor=current_user,
            ip=ip_del_cliente(request),
            user_agent=request.headers.get("user-agent"),
        )
        try:
            yield asiento
        except HTTPException as exc:
            asiento.resultado = f"HTTP_{exc.status_code}"
            raise
        except Exception:
            asiento.resultado = RESULTADO_ERROR
            raise
        finally:
            # El `finally` traga cualquier fallo del asiento, y no por precaución
            # genérica: lo que aquí se levante sustituye a la respuesta que el endpoint ya
            # había producido, de modo que un problema al escribir la bitácora convertiría
            # un alta correcta —ya confirmada en la base— en un 500 para quien la hizo.
            # `registrar_evento` ya se protege por dentro; esto cubre el resto del camino.
            try:
                asiento.persistir()
            except Exception:
                logger.exception(
                    "El asiento de auditoría '%s' sobre %s no pudo escribirse; la operación "
                    "se respeta.",
                    accion,
                    entidad,
                )

    return dependencia
