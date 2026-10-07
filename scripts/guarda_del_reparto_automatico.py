"""
Guarda del CI para el reparto automático: lo que decide solo, en el alta y sin nadie delante.

    python scripts/guarda_del_reparto_automatico.py

Falla —con un mensaje que dice qué se perdió— si el reparto:

1. **deja de repartir**: una tanda entera acaba en la misma cuenta. Es el defecto que el
   capítulo 46 vino a corregir y el que ninguna prueba de «la ficha tiene dueño» puede ver:
   con `ORDER BY capacity DESC` todas las fichas tenían dueño y era siempre el mismo;
2. **vuelve a mirar el score**: un prospecto frío deja de entrar, o entra en otro orden que
   uno caliente. «Pesos por score» queda fuera del encargo por escrito;
3. **deshace lo que decidió una persona**: una reasignación a mano, o una ficha que el líder
   dejó sin asesor a propósito, vuelven atrás en el recálculo siguiente;
4. **pierde el bloqueo**: la consulta de candidatos deja de pedir `FOR UPDATE` o deja de
   tomar las filas en orden, y entonces dos altas simultáneas reparten el mismo hueco dos
   veces. Es lo único de este módulo que la suite no puede ejercitar —SQLite lo ignora en
   silencio—, así que se comprueba sobre la sentencia compilada contra PostgreSQL;
5. **copia la regla**: la definición de «cartera abierta» deja de ser la del motor de reglas
   y pasa a ser una igual. Dos copias de esa regla no fallan: las dos pantallas siguen
   funcionando y dicen cosas distintas el día que una etapa cambie de lado;
6. **reparte a oscuras**: el asiento desaparece, deja de decir con qué regla y entre cuántos
   se eligió, se escribe con actor —como si una persona hubiera elegido— o sobrevive al
   `rollback` del alta que lo produjo;
7. **ignora el interruptor**: apagado sigue repartiendo, o apagarlo mueve lo ya repartido;
8. **reparte sin producir trabajo**: los prospectos repartidos no reciben su tarea de primer
   contacto en la pasada siguiente. Era el punto entero de H-6: sin asesor el motor no tiene
   de quién hablar, y repartir sin que aparezca el trabajo es volver al mismo sitio;
9. **se queda fuera de un camino de alta**: el alta del panel, la página pública o una
   integración acaban con una ficha sin asesor habiendo asesoras activas;
10. **revienta sin asesoras**: una instalación recién puesta en marcha tiene que dejar los
    prospectos a la vista del líder, no contestar un error.

Por qué además de la suite: `test_reparto_automatico.py` comprueba casos. Esto comprueba
**propiedades**. Un reparto que le dé todo a la primera cuenta pasa cualquier caso que mire
una sola ficha, y aquí falla en la primera tanda.
"""
import asyncio
import datetime
import os
import sys
import tempfile

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_BASE_TEMPORAL = os.path.join(tempfile.mkdtemp(prefix="guarda-reparto-"), "guarda.db")
# Antes de importar la aplicación: la configuración lee la base al cargarse.
os.environ["DATABASE_URL"] = f"sqlite:///{_BASE_TEMPORAL}"
os.environ.setdefault("ENVIRONMENT", "development")
sys.path.insert(0, os.path.join(RAIZ, "backend"))

from app.core.agenda import PRIMER_CONTACTO  # noqa: E402
from app.core.audit import ACCION_LEAD_REPARTO_AUTOMATICO  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.models.entities import (  # noqa: E402
    ActivityType,
    AuditLog,
    Aviso,
    Campaign,
    Lead,
    LeadStatus,
    ScoreCategory,
    ScoreHistory,
    Tarea,
    User,
    utc_now,
)
from app.services import motor_de_reglas, reparto_automatico  # noqa: E402
from app.services.motor_de_reglas import ejecutar  # noqa: E402
from app.services.registro_de_actividad import Contacto, Evento, registrar_evento  # noqa: E402
from app.services.reparto_automatico import REGLAS_DEL_REPARTO, elegir, repartir  # noqa: E402
from app.services.scoring_service import ScoringService  # noqa: E402
from sqlalchemy.dialects import postgresql  # noqa: E402

UTC = datetime.timezone.utc

# El vocabulario cerrado del desenlace, que es de donde sale «de este prospecto ya no queda
# nada que hacer». Se lee de ahí y no se escribe: esta guarda vigila precisamente que no
# aparezca una segunda copia.
from app.core.desenlaces import ETAPAS_SIN_SEGUIMIENTO  # noqa: E402

MODULO = os.path.join(RAIZ, "backend", "app", "services", "reparto_automatico.py")

fallos = []
_correo = [0]


def fallo(mensaje: str) -> None:
    fallos.append(mensaje)
    print(f"  FALLO: {mensaje}")


def _ahora():
    return datetime.datetime.now(UTC)


def _limpiar(db):
    for modelo in (Tarea, Aviso, AuditLog, ScoreHistory, Lead, Campaign):
        db.query(modelo).delete()
    db.commit()


def _equipo(db, *, cuantas=4):
    """`cuantas` asesoras activas, una de baja y un administrador que no atiende cartera."""
    db.query(User).delete()
    db.commit()
    # El borrado por consulta no vacía el mapa de identidad: sin esto, las cuentas nuevas
    # reutilizan los identificadores de las borradas y SQLAlchemy avisa de que está
    # reemplazando objetos que creía vivos.
    db.expire_all()
    cuentas = [
        User(
            email=f"asesora{numero}.reparto@plurione.com", full_name=f"Asesora {numero}",
            role="Commercial_Executive", hashed_password="!sin-contrasena:guarda",  # noqa: S106  hash inutilizable: estas cuentas no inician sesion
            is_sales_rep=True, is_active=True, capacity=10 * numero,
        )
        for numero in range(1, cuantas + 1)
    ]
    cuentas.append(
        User(
            email="debaja.reparto@plurione.com", full_name="De Baja",
            role="Commercial_Executive", hashed_password="!sin-contrasena:guarda",  # noqa: S106  idem
            is_sales_rep=True, is_active=False, capacity=999,
        )
    )
    cuentas.append(
        User(
            email="admin.reparto@plurione.com", full_name="Admin Reparto",
            role="System_Admin", hashed_password="!sin-contrasena:guarda",  # noqa: S106  idem
            is_sales_rep=False, is_active=True,
        )
    )
    cuentas.append(
        User(
            email="lider.reparto@plurione.com", full_name="Lider Reparto",
            role="Sales_Lead", hashed_password="!sin-contrasena:guarda",  # noqa: S106  idem
            is_sales_rep=False, is_active=True,
        )
    )
    db.add_all(cuentas)
    db.commit()
    for cuenta in cuentas:
        db.refresh(cuenta)
    return cuentas[:cuantas], cuentas[cuantas], cuentas[cuantas + 1], cuentas[cuantas + 2]


def _ficha(db, *, asesor=None, campana=None, categoria=None, creada=None, estado=LeadStatus.NEW):
    _correo[0] += 1
    cuando = creada or _ahora()
    lead = Lead(
        first_name="Persona", last_name=f"Guarda{_correo[0]}",
        email=f"reparto{_correo[0]}@ejemplo.mx", company="Empresa SA",
        job_title="CTO", industry="FinTech", company_size="201-1000",
        assigned_rep_id=asesor.id if asesor is not None else None,
        campaign_id=campana.id if campana is not None else None,
        status=estado, score_category=categoria or ScoreCategory.WARM,
        created_at=cuando, updated_at=cuando, last_activity_at=cuando,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def _tanda(db, cuantas, *, categoria=None):
    """`cuantas` altas repartidas, cada una confirmada como lo estaría la suya."""
    repartos = []
    for _ in range(cuantas):
        lead = _ficha(db, categoria=categoria)
        reparto = repartir(db, lead)
        db.commit()
        repartos.append((lead, reparto))
    return repartos


def _reparto_por_asesora(repartos):
    cuenta = {}
    for lead, _ in repartos:
        cuenta[lead.assigned_rep_id] = cuenta.get(lead.assigned_rep_id, 0) + 1
    return cuenta


# ==============================================================================
# 1. Reparte de verdad
# ==============================================================================

def comprobar_que_reparte(db):
    print("\n[1/10] Una tanda se reparte, no se acumula.")
    _limpiar(db)
    asesoras, _, _, _ = _equipo(db, cuantas=4)

    repartos = _tanda(db, 12)
    reparto = _reparto_por_asesora(repartos)

    sin_nada = [a.id for a in asesoras if a.id not in reparto]
    if sin_nada:
        fallo(
            f"{len(sin_nada)} de {len(asesoras)} asesoras activas no recibieron nada en una "
            "tanda de 12: el reparto no reparte, ordena."
        )
        return
    if max(reparto.values()) - min(reparto.values()) > 1:
        fallo(
            f"la tanda de 12 quedó {sorted(reparto.values())} entre {len(asesoras)} asesoras: "
            "un reparto equitativo no puede desviarse en mas de una ficha."
        )
    if any(lead.assigned_rep_id is None for lead, _ in repartos):
        fallo("alguna ficha de la tanda quedó sin asesor habiendo asesoras activas.")

    # Y la carga que cuenta es la ABIERTA. Quien cerró cinco tratos no tiene cinco de
    # cartera: si contara la cartera entera, el reparto premiaría a quien menos cierra.
    _limpiar(db)
    for etapa in ETAPAS_SIN_SEGUIMIENTO:
        for _ in range(3):
            _ficha(db, asesor=asesoras[0], estado=LeadStatus(etapa))
    for asesora in asesoras[1:]:
        _ficha(db, asesor=asesora)
    lead = _ficha(db)
    repartir(db, lead)
    db.commit()
    if lead.assigned_rep_id != asesoras[0].id:
        fallo(
            "la cartera que decide el reparto dejó de ser la abierta: quien tiene nueve "
            "tratos cerrados y ninguno abierto no recibió el siguiente."
        )


# ==============================================================================
# 2. No mira el score
# ==============================================================================

def comprobar_que_no_mira_el_score(db):
    print("\n[2/10] El score no cambia a quién le toca.")
    secuencias = {}
    for categoria in (ScoreCategory.HOT, ScoreCategory.WARM, ScoreCategory.COLD):
        _limpiar(db)
        asesoras, _, _, _ = _equipo(db, cuantas=3)
        repartos = _tanda(db, 6, categoria=categoria)
        if any(lead.assigned_rep_id is None for lead, _ in repartos):
            fallo(f"una ficha {categoria.value} se quedó sin asesor: el reparto volvió a mirar el score.")
            return
        # Por posición y no por identificador: cada tanda tiene su propio equipo.
        orden = [a.id for a in asesoras]
        secuencias[categoria.value] = [orden.index(lead.assigned_rep_id) for lead, _ in repartos]

    distintas = {tuple(v) for v in secuencias.values()}
    if len(distintas) != 1:
        fallo(f"el reparto no es el mismo segun la categoria: {secuencias}")


# ==============================================================================
# 3. No deshace lo que decidió una persona
# ==============================================================================

def comprobar_que_no_deshace_lo_decidido(db):
    print("\n[3/10] Lo que decidió una persona se queda.")
    _limpiar(db)
    asesoras, baja, _, _ = _equipo(db, cuantas=3)
    servicio = ScoringService(db)

    # (a) Un alta de verdad se reparte; reasignada a mano, el recálculo no la devuelve.
    lead = _ficha(db)
    asyncio.run(servicio.calculate_and_persist_score(lead, generate_ai_text=False))
    if lead.assigned_rep_id is None:
        fallo("un alta que pasa por el scoring no se repartió: el reparto no está en el paso obligatorio.")
        return
    lead.assigned_rep_id = asesoras[-1].id
    db.commit()
    asyncio.run(servicio.calculate_and_persist_score(lead, generate_ai_text=False))
    if lead.assigned_rep_id != asesoras[-1].id:
        fallo("el recálculo deshizo una reasignación hecha a mano.")

    # (b) Quitarle el asesor también es una decisión.
    lead.assigned_rep_id = None
    db.commit()
    asyncio.run(servicio.calculate_and_persist_score(lead, generate_ai_text=False))
    if lead.assigned_rep_id is not None:
        fallo("el recálculo volvió a asignar una ficha que alguien dejó sin asesor a propósito.")

    # (c) Una ficha con dueño no se toca aunque su dueña sea la más cargada.
    for _ in range(9):
        _ficha(db, asesor=asesoras[0])
    cargada = _ficha(db, asesor=asesoras[0])
    if repartir(db, cargada) is not None or cargada.assigned_rep_id != asesoras[0].id:
        fallo("el reparto reasignó un prospecto que ya tenía asesor.")
    db.rollback()

    # (d) Una publicación con responsable manda, incluso si el responsable se dio de baja:
    # esa cartera la reparte el líder (`ciclo.asesor_para` la deja sin asesor a propósito).
    publicacion = Campaign(
        name="Post con responsable", channel="LinkedIn Ads", budget=0.0, responsable_id=baja.id
    )
    db.add(publicacion)
    db.commit()
    de_publicacion = _ficha(db, campana=publicacion)
    if repartir(db, de_publicacion) is not None or de_publicacion.assigned_rep_id is not None:
        fallo("el reparto tocó un prospecto de una publicación con responsable.")
    db.rollback()


# ==============================================================================
# 4. El bloqueo de las dos altas a la vez
# ==============================================================================

def comprobar_el_bloqueo(db):
    print("\n[4/10] La consulta de candidatos pide el bloqueo.")
    sentencia = str(
        reparto_automatico.consulta_de_candidatos(db).statement.compile(
            dialect=postgresql.dialect()
        )
    )
    if "FOR UPDATE" not in sentencia:
        fallo(
            "la consulta de candidatos dejó de pedir FOR UPDATE: dos altas simultáneas leen "
            "la misma cartera y reparten el mismo hueco dos veces."
        )
    if "ORDER BY users.id ASC" not in sentencia:
        fallo(
            "la consulta de candidatos dejó de tomar las filas en orden de identificador: "
            "dos pasadas pueden bloquearse una a la otra."
        )
    # Y el recuento tiene que ver lo que la misma transacción acaba de escribir: dos altas
    # seguidas sin confirmar entre ellas —una entrega del CRM con dos eventos— no pueden ir
    # a la misma cuenta.
    _limpiar(db)
    _equipo(db, cuantas=3)
    primera, segunda = _ficha(db), _ficha(db)
    uno = repartir(db, primera)
    db.flush()
    dos = repartir(db, segunda)
    if uno is None or dos is None or uno.asesor_id == dos.asesor_id:
        fallo(
            "dos altas en la misma transacción fueron a la misma cuenta: el recuento no ve "
            "lo que la transacción ya escribió."
        )
    db.rollback()


# ==============================================================================
# 5. La regla no está copiada
# ==============================================================================

def comprobar_que_la_regla_no_esta_copiada(db):
    print("\n[5/10] «Cartera abierta» sigue siendo la definición del motor.")
    if reparto_automatico.en_seguimiento is not motor_de_reglas.en_seguimiento:
        fallo(
            "el reparto dejó de usar la condición del motor de reglas y tiene su propia "
            "definición de «queda algo que hacer»: dos copias de esa regla no fallan, "
            "discrepan."
        )
    with open(MODULO, encoding="utf-8") as archivo:
        codigo = archivo.read()
    copiadas = [etapa for etapa in ETAPAS_SIN_SEGUIMIENTO if f'"{etapa}"' in codigo]
    if copiadas:
        fallo(
            f"el módulo del reparto nombra etapas cerradas a mano ({', '.join(copiadas)}): "
            "la lista sale de app.core.desenlaces o se queda atrás en la primera que cambie."
        )
    # El vocabulario de las reglas del reparto, cerrado: un asiento con una regla inventada
    # no lo encontraría ninguna consulta.
    if len(set(REGLAS_DEL_REPARTO)) != len(REGLAS_DEL_REPARTO):
        fallo("REGLAS_DEL_REPARTO tiene claves repetidas.")


# ==============================================================================
# 6. La bitácora
# ==============================================================================

def comprobar_la_bitacora(db):
    print("\n[6/10] Cada reparto queda escrito, con su regla y entre cuántos.")
    _limpiar(db)
    asesoras, _, _, _ = _equipo(db, cuantas=3)
    repartos = _tanda(db, 5)

    asientos = (
        db.query(AuditLog)
        .filter(AuditLog.action == ACCION_LEAD_REPARTO_AUTOMATICO)
        .order_by(AuditLog.id)
        .all()
    )
    if len(asientos) != len(repartos):
        fallo(
            f"{len(repartos)} repartos dejaron {len(asientos)} asientos: un reparto que no se "
            "escribe no se puede discutir al día siguiente."
        )
        return
    for asiento, (lead, reparto) in zip(asientos, repartos, strict=True):
        datos = asiento.event_metadata or {}
        if datos.get("regla") not in REGLAS_DEL_REPARTO:
            fallo(f"el asiento del prospecto {lead.id} no dice con qué regla se eligió: {datos!r}")
            break
        if not isinstance(datos.get("candidatos"), int) or datos["candidatos"] < 1:
            fallo(f"el asiento del prospecto {lead.id} no dice entre cuántos se eligió: {datos!r}")
            break
        if datos.get("asesor_id") != reparto.asesor_id:
            fallo(f"el asiento del prospecto {lead.id} nombra a otra asesora que la asignada.")
            break
        if asiento.entity_id != str(lead.id):
            fallo(f"el asiento del reparto no apunta al prospecto {lead.id}.")
            break
    if any(a.actor_email or a.actor_id for a in asientos):
        fallo(
            "un asiento del reparto lleva actor: el alta la pudo pedir una persona, pero a "
            "quién le tocaba no lo decidió ella, y con su correo dentro se leería al revés."
        )
    escrito = " ".join(f"{a.event_metadata}" for a in asientos)
    for lead, _ in repartos:
        if lead.email in escrito or lead.first_name in escrito:
            fallo("el asiento del reparto lleva datos de la persona: la bitácora cuenta cuántos.")
            break

    # Y el asiento vive en la transacción del alta: si la ficha no se queda, su reparto tampoco.
    lead = _ficha(db)
    antes = db.query(AuditLog).filter(AuditLog.action == ACCION_LEAD_REPARTO_AUTOMATICO).count()
    repartir(db, lead)
    db.rollback()
    despues = db.query(AuditLog).filter(AuditLog.action == ACCION_LEAD_REPARTO_AUTOMATICO).count()
    if despues != antes:
        fallo(
            "el asiento del reparto sobrevivió al rollback del alta: la bitácora afirma un "
            "reparto que no ocurrió."
        )
    if db.get(Lead, lead.id).assigned_rep_id is not None:
        fallo("la asignación sobrevivió al rollback del alta.")


# ==============================================================================
# 7. El interruptor
# ==============================================================================

def comprobar_el_interruptor(db):
    print("\n[7/10] Apagado no reparte, y apagarlo no mueve lo repartido.")
    _limpiar(db)
    _equipo(db, cuantas=3)

    ya_repartido = _ficha(db)
    repartir(db, ya_repartido)
    db.commit()
    dueno = ya_repartido.assigned_rep_id

    original = settings.REPARTO_AUTOMATICO_ACTIVO
    settings.REPARTO_AUTOMATICO_ACTIVO = False
    try:
        antes = db.query(AuditLog).filter(AuditLog.action == ACCION_LEAD_REPARTO_AUTOMATICO).count()
        lead = _ficha(db)
        if repartir(db, lead) is not None or lead.assigned_rep_id is not None:
            fallo("el interruptor apagado sigue repartiendo.")
        db.commit()
        if db.query(AuditLog).filter(
            AuditLog.action == ACCION_LEAD_REPARTO_AUTOMATICO
        ).count() != antes:
            fallo("el interruptor apagado sigue escribiendo asientos de reparto.")
        asyncio.run(ScoringService(db).calculate_and_persist_score(lead, generate_ai_text=False))
        if lead.assigned_rep_id is not None:
            fallo("el interruptor apagado no alcanza al alta que pasa por el scoring.")
        db.refresh(ya_repartido)
        if ya_repartido.assigned_rep_id != dueno:
            fallo("apagar el interruptor movió un prospecto ya repartido.")
    finally:
        settings.REPARTO_AUTOMATICO_ACTIVO = original


# ==============================================================================
# 8. Repartir produce trabajo
# ==============================================================================

def comprobar_que_produce_trabajo(db):
    print("\n[8/10] Lo repartido recibe su tarea de primer contacto.")
    _limpiar(db)
    _equipo(db, cuantas=3)
    repartos = _tanda(db, 6)

    ejecutar(db, reglas=[PRIMER_CONTACTO])

    tareas = {
        (tarea.lead_id, tarea.asesor_id)
        for tarea in db.query(Tarea).filter(Tarea.regla == PRIMER_CONTACTO).all()
    }
    esperadas = {(lead.id, lead.assigned_rep_id) for lead, _ in repartos}
    if tareas != esperadas:
        fallo(
            f"la pasada siguiente creó {len(tareas)} tareas de primer contacto para "
            f"{len(esperadas)} prospectos repartidos, o a nombre de otra persona: era el "
            "punto entero de H-6, repartir para que aparezca el trabajo."
        )

    # Y repartir, por sí solo, no crea nada: el trabajo lo propone el motor en su pasada.
    _limpiar(db)
    _equipo(db, cuantas=3)
    _tanda(db, 3)
    if db.query(Tarea).count() or db.query(Aviso).count():
        fallo(
            "el reparto creó tareas o avisos por su cuenta: la agenda se decide en la pasada "
            "del motor y en un solo sitio (capítulo 28)."
        )


# ==============================================================================
# 9. Los caminos del alta
# ==============================================================================

def comprobar_los_caminos_del_alta(db, cliente):
    print("\n[9/10] El alta del panel, la página pública y una integración reparten igual.")
    _limpiar(db)
    asesoras, _, _, lider = _equipo(db, cuantas=3)
    activas = {a.id for a in asesoras}
    cabeceras = {"Authorization": f"Bearer {create_access_token(lider)}"}

    # (a) El alta del panel, sin elegir dueño.
    respuesta = cliente.post(
        "/api/v1/leads",
        headers=cabeceras,
        json={
            "first_name": "Panel", "last_name": "Reparto", "email": "panel.reparto@ejemplo.mx",
            "company": "Empresa SA", "job_title": "CTO", "industry": "FinTech",
        },
    )
    if respuesta.status_code not in (200, 201):
        fallo(f"el alta del panel no se pudo probar: {respuesta.status_code} {respuesta.text[:120]}")
    else:
        del_panel = db.get(Lead, respuesta.json()["id"])
        db.refresh(del_panel)
        if del_panel.assigned_rep_id not in activas:
            fallo("el alta del panel dejó la ficha sin asesor habiendo asesoras activas.")

    # (b) La página pública, sobre una publicación sin responsable.
    publicacion = cliente.post(
        "/api/v1/campaigns",
        headers=cabeceras,
        json={
            "name": "Post de la guarda", "channel": "LinkedIn",
            "description": "¿Tu equipo de TI tarda meses en cubrir una vacante?",
            "target_audience": "Directores de TI", "budget": 0.0,
        },
    )
    if publicacion.status_code not in (200, 201):
        fallo(f"la publicación de la guarda no se pudo crear: {publicacion.status_code}")
    else:
        slug = publicacion.json()["public_slug"]
        envio = cliente.post(
            f"/api/v1/interes/{slug}",
            json={
                "nombre": "Publica Reparto", "correo": "publica.reparto@ejemplo.mx",
                "empresa": "Ejemplo SA", "cargo": "CTO", "sector": "FinTech",
                "tamano_de_empresa": "201-1000", "necesidad": "vacantes",
                "aviso_de_privacidad": True, "sitio_web": "",
            },
        )
        if envio.status_code != 202:
            fallo(f"el envío de la página pública no se pudo probar: {envio.status_code}")
        else:
            db.expire_all()
            publica = db.query(Lead).filter(Lead.email == "publica.reparto@ejemplo.mx").one()
            if publica.assigned_rep_id not in activas:
                fallo("la ficha de la página pública se quedó sin asesor.")

    # (c) Una integración que crea ficha.
    evento = Evento(
        fuente="formulario_web",
        tipo=ActivityType.FORM_SUBMIT,
        ocurrido_en=utc_now(),
        identificador_externo="guarda-del-reparto-1",
        contacto=Contacto(email="integracion.reparto@ejemplo.mx", nombre="Integra Reparto"),
        prospecto={
            "first_name": "Integra", "last_name": "Reparto",
            "email": "integracion.reparto@ejemplo.mx", "company": "Empresa SA",
            "job_title": "CTO", "industry": "FinTech",
        },
    )
    resultado = asyncio.run(registrar_evento(db, evento, generar_explicacion=False))
    if resultado.lead is None:
        fallo("la integración no creó la ficha: el camino no se pudo probar.")
    else:
        db.refresh(resultado.lead)
        if resultado.lead.assigned_rep_id not in activas:
            fallo("la ficha creada por una integración se quedó sin asesor.")


# ==============================================================================
# 10. Sin asesoras
# ==============================================================================

def comprobar_sin_asesoras(db):
    print("\n[10/10] Sin asesoras activas, la ficha queda a la vista del líder.")
    _limpiar(db)
    asesoras, _, _, _ = _equipo(db, cuantas=2)
    for asesora in asesoras:
        asesora.is_active = False
    db.commit()

    if elegir(db) is not None:
        fallo("el reparto eligió una cuenta de baja.")
    antes = db.query(AuditLog).filter(AuditLog.action == ACCION_LEAD_REPARTO_AUTOMATICO).count()
    lead = _ficha(db)
    asyncio.run(ScoringService(db).calculate_and_persist_score(lead, generate_ai_text=False))
    if lead.assigned_rep_id is not None:
        fallo("sin asesoras activas, el reparto asignó a alguien que no puede atender.")
    if db.query(AuditLog).filter(AuditLog.action == ACCION_LEAD_REPARTO_AUTOMATICO).count() != antes:
        fallo("sin asesoras activas, el reparto escribió un asiento de algo que no hizo.")


# ==============================================================================

def main() -> int:
    init_db()
    from app.main import app
    from fastapi.testclient import TestClient

    cliente = TestClient(app)
    limiter.enabled = False

    db = SessionLocal()
    try:
        for comprobacion, argumentos in (
            (comprobar_que_reparte, (db,)),
            (comprobar_que_no_mira_el_score, (db,)),
            (comprobar_que_no_deshace_lo_decidido, (db,)),
            (comprobar_el_bloqueo, (db,)),
            (comprobar_que_la_regla_no_esta_copiada, (db,)),
            (comprobar_la_bitacora, (db,)),
            (comprobar_el_interruptor, (db,)),
            (comprobar_que_produce_trabajo, (db,)),
            (comprobar_los_caminos_del_alta, (db, cliente)),
            (comprobar_sin_asesoras, (db,)),
        ):
            try:
                comprobacion(*argumentos)
            except Exception as exc:  # noqa: BLE001
                # Una comprobación que revienta tiene que informar de qué defensa se perdió,
                # no soltar un rastro de pila: el CI enseña el título del paso, y «fallo» es
                # lo que hay que poder leer ahí.
                db.rollback()
                fallo(f"{comprobacion.__name__} no se pudo comprobar ({exc.__class__.__name__}: {exc}).")
    finally:
        db.close()

    if fallos:
        print(f"\nEl reparto automático perdió {len(fallos)} defensa(s).")
        return 1
    print(
        "\nReparte, ignora el score, respeta lo decidido a mano, pide el bloqueo, no copia la "
        "regla del motor, deja asiento sin actor, obedece el interruptor, produce trabajo en la "
        "pasada siguiente, alcanza los tres caminos del alta y sin asesoras no inventa un "
        "destino: el reparto automático conserva sus defensas."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
