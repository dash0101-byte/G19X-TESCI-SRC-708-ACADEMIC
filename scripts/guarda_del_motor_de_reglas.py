"""
Guarda del CI para el motor de reglas: lo que decide solo y sin nadie delante.

    python scripts/guarda_del_motor_de_reglas.py

Falla —con un mensaje que dice qué se perdió— si el motor:

1. **duplica**: repetir la pasada crea otra vez lo mismo. Es el fallo que no se nota el
   primer día y deja la bandeja inservible la primera semana, cuando ya nadie la mira;
2. **deja de escalar**: el aviso al líder llega antes o a la vez que el del asesor, o sube
   algo que el asesor no llegó a ver;
3. **sale del panel**: aparece un cliente de correo, de HTTP o de mensajería en el motor. El
   capítulo dice que todo vive dentro del panel, y lo contrario saca de la aplicación el
   nombre de una persona que aceptó un aviso de privacidad para otra cosa;
4. **mueve el score**: una tarea pendiente vuelve a puntuar. Nadie se vuelve más interesante
   porque a su asesor le quede trabajo por hacer;
5. **pierde el alcance**: un asesor ve o cierra trabajo de otro, o lo ajeno responde algo
   distinto de 404;
6. **convierte la bandeja en un directorio**: el correo o el teléfono del prospecto vuelven
   a viajar en la lista de trabajo, fuera del registro de acceso a la ficha;
7. **crea algo sin plazo**: las tareas o los avisos se quedan fuera de la conservación, o
   empieza a caducar lo que sigue abierto o sin leer;
8. **corre a ciegas**: una regla deja de ejecutarse o deja de anotar qué hizo, y entonces
   nadie puede saber si el motor trabajó esta noche.

Por qué además de la suite: `test_motor_de_reglas.py` comprueba casos. Esto comprueba
**propiedades**. Una regla nueva que alguien olvide meter en el orden de ejecución no rompe
ninguna prueba —la suya la llama a mano— y aquí falla en cuanto existe.
"""
import datetime
import os
import re
import sys
import tempfile

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_BASE_TEMPORAL = os.path.join(tempfile.mkdtemp(prefix="guarda-reglas-"), "guarda.db")
# Antes de importar la aplicación: la configuración lee la base al cargarse.
os.environ["DATABASE_URL"] = f"sqlite:///{_BASE_TEMPORAL}"
os.environ.setdefault("ENVIRONMENT", "development")
sys.path.insert(0, os.path.join(RAIZ, "backend"))

from app.core.agenda import (  # noqa: E402
    ABIERTA,
    ESTADOS_CERRADOS,
    HOT_SIN_CONTACTO,
    HOT_SIN_CONTACTO_LIDER,
    ORDEN_DE_LAS_REGLAS,
    PRIMER_CONTACTO,
    REGLAS,
)
from app.core.config import PLAZOS_MINIMOS_DE_LAS_REGLAS, Settings, settings  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.models.entities import (  # noqa: E402
    AuditLog,
    Aviso,
    Lead,
    ScoreCategory,
    Tarea,
    User,
)
from app.services.agenda_del_dia import HORIZONTE_HORAS  # noqa: E402
from app.services.caducidad_service import PLAZOS, aplicar_caducidad  # noqa: E402
from app.services.motor_de_reglas import ORDEN_DE_LA_PASADA, ejecutar  # noqa: E402
from pydantic import ValidationError  # noqa: E402

UTC = datetime.timezone.utc

# Lo que no puede aparecer en el motor ni en la agenda. No es una lista de bibliotecas
# prohibidas por gusto: cada una de estas es una forma de que un aviso salga del panel.
FORMAS_DE_SALIR = (
    "smtplib", "email.message", "requests", "httpx", "urllib.request", "aiosmtplib",
    "sendgrid", "twilio", "boto3",
)

fallos = []


def fallo(mensaje: str) -> None:
    fallos.append(mensaje)
    print(f"  FALLO: {mensaje}")


def _ahora():
    return datetime.datetime.now(UTC)


def _hace(**kwargs):
    return _ahora() - datetime.timedelta(**kwargs)


def _limpiar(db):
    for modelo in (Tarea, Aviso, AuditLog, Lead):
        db.query(modelo).delete()
    db.commit()


def _equipo(db):
    asesor = db.query(User).filter(User.email == "asesor.guarda@plurione.com").first()
    if asesor is None:
        asesor = User(
            email="asesor.guarda@plurione.com", full_name="Asesor Guarda",
            role="Commercial_Executive", hashed_password="!sin-contrasena:guarda",  # noqa: S106  hash inutilizable: estas cuentas no inician sesión
            is_sales_rep=True, capacity=50,
        )
        otro = User(
            email="otro.guarda@plurione.com", full_name="Otro Guarda",
            role="Commercial_Executive", hashed_password="!sin-contrasena:guarda",  # noqa: S106  hash inutilizable: estas cuentas no inician sesión
            is_sales_rep=True, capacity=50,
        )
        lider = User(
            email="lider.guarda@plurione.com", full_name="Lider Guarda",
            role="Sales_Lead", hashed_password="!sin-contrasena:guarda",  # noqa: S106  hash inutilizable: estas cuentas no inician sesión
            is_sales_rep=True, capacity=40,
        )
        db.add_all([asesor, otro, lider])
        db.commit()
    otro = db.query(User).filter(User.email == "otro.guarda@plurione.com").first()
    lider = db.query(User).filter(User.email == "lider.guarda@plurione.com").first()
    return asesor, otro, lider


def _prospecto(db, asesor, *, correo, creado=None, categoria=ScoreCategory.WARM, score=50.0):
    lead = Lead(
        first_name="Prospecto", last_name="Guarda", email=correo, company="Guarda SA",
        phone="+52 55 0000 1111",
        assigned_rep_id=asesor.id if asesor else None,
        created_at=creado or _hace(hours=2),
        last_activity_at=creado or _hace(hours=2),
        current_score=score, score_category=categoria,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


# ==============================================================================
# 1. No duplica
# ==============================================================================

def comprobar_idempotencia(db):
    print("1. Repetir la pasada no duplica nada")
    _limpiar(db)
    asesor, _, _ = _equipo(db)
    _prospecto(db, asesor, correo="idempotencia@guarda.test")
    _prospecto(db, asesor, correo="hot@guarda.test", creado=_hace(hours=60), categoria=ScoreCategory.HOT, score=90.0)

    ejecutar(db, ahora=_ahora())
    tareas, avisos = db.query(Tarea).count(), db.query(Aviso).count()
    if tareas == 0 or avisos == 0:
        fallo("la pasada no creó nada; el resto de comprobaciones no medirían nada.")
        return

    for dias in (0, 1, 2):
        ejecutar(db, ahora=_ahora() + datetime.timedelta(days=dias))
    if db.query(Tarea).count() != tareas:
        fallo(f"repetir la pasada duplicó tareas: {tareas} -> {db.query(Tarea).count()}.")
    if db.query(Aviso).count() != avisos:
        fallo(f"repetir la pasada duplicó avisos: {avisos} -> {db.query(Aviso).count()}.")


# ==============================================================================
# 2. El escalado escala
# ==============================================================================

def comprobar_escalado(db):
    print("2. El líder se entera después, y solo de lo que el asesor ya vio")
    if settings.REGLA_HOT_LIDER_HORAS <= settings.REGLA_HOT_SIN_CONTACTO_HORAS:
        fallo("el plazo del líder no supera al del asesor: el escalado dejó de escalar.")
    try:
        Settings(REGLA_HOT_SIN_CONTACTO_HORAS=24, REGLA_HOT_LIDER_HORAS=24)
        fallo("una pareja de plazos invertida arranca; el escalado puede configurarse mal sin aviso.")
    except ValidationError:
        pass

    _limpiar(db)
    asesor, _, _ = _equipo(db)
    # Sin asesor no hay a quién avisar primero, así que tampoco hay nada que escalar.
    huerfano = _prospecto(
        db, None, correo="huerfano@guarda.test",
        creado=_hace(hours=settings.REGLA_HOT_LIDER_HORAS + 10), categoria=ScoreCategory.HOT, score=95.0,
    )
    ejecutar(db, ahora=_ahora())
    if db.query(Aviso).filter(Aviso.regla == HOT_SIN_CONTACTO_LIDER, Aviso.lead_id == huerfano.id).count():
        fallo("el líder recibió un escalado de algo que ningún asesor llegó a ver.")

    # Y con asesor, primero el asesor y después el líder.
    reciente = _prospecto(
        db, asesor, correo="reciente@guarda.test",
        creado=_hace(hours=settings.REGLA_HOT_SIN_CONTACTO_HORAS + 1),
        categoria=ScoreCategory.HOT, score=92.0,
    )
    ejecutar(db, ahora=_ahora())
    del_asesor = db.query(Aviso).filter(Aviso.regla == HOT_SIN_CONTACTO, Aviso.lead_id == reciente.id).count()
    del_lider = db.query(Aviso).filter(Aviso.regla == HOT_SIN_CONTACTO_LIDER, Aviso.lead_id == reciente.id).count()
    if del_asesor == 0:
        fallo("un HOT desatendido dejó de avisar a su asesor.")
    if del_lider:
        fallo("el líder se enteró a la vez que el asesor: el aviso ya no da margen para resolverlo.")


# ==============================================================================
# 3. Nada sale del panel
# ==============================================================================

def comprobar_que_nada_sale_del_panel():
    print("3. Ni correo, ni mensajería, ni llamadas a nadie")
    for relativa in (
        "backend/app/services/motor_de_reglas.py",
        "backend/app/services/agenda_del_dia.py",
        "backend/app/api/v1/endpoints/agenda.py",
    ):
        texto = open(os.path.join(RAIZ, relativa), encoding="utf-8").read()
        # Los comentarios explican precisamente por qué NO se usa ninguna de estas, así que
        # se miran solo las líneas de código.
        codigo = "\n".join(
            linea for linea in texto.splitlines() if not linea.lstrip().startswith("#")
        )
        codigo = re.sub(r'""".*?"""', "", codigo, flags=re.S)
        for forma in FORMAS_DE_SALIR:
            if re.search(rf"\b{re.escape(forma)}\b", codigo):
                fallo(f"{relativa} usa «{forma}»: un aviso puede salir del panel.")


# ==============================================================================
# 4. No mueve el score
# ==============================================================================

def comprobar_que_no_toca_el_score(db):
    print("4. El motor no mueve la puntuación de nadie")
    _limpiar(db)
    asesor, _, _ = _equipo(db)
    lead = _prospecto(
        db, asesor, correo="score@guarda.test",
        creado=_hace(hours=60), categoria=ScoreCategory.HOT, score=88.0,
    )
    antes = (lead.current_score, lead.score_category)

    ejecutar(db, ahora=_ahora())

    db.refresh(lead)
    if (lead.current_score, lead.score_category) != antes:
        fallo(
            f"el motor movió la puntuación: {antes} -> "
            f"({lead.current_score}, {lead.score_category}); el trabajo pendiente puntúa."
        )


# ==============================================================================
# 5. El alcance
# ==============================================================================

def _cabeceras(usuario):
    #  recibe la cuenta entera, no un diccionario de reclamaciones: el
    # token lleva además la versión de la cuenta, que es lo que permite invalidarlo.
    return {"Authorization": f"Bearer {create_access_token(usuario)}"}


def comprobar_alcance(db, cliente):
    print("5. Cada uno ve y cierra lo suyo")
    _limpiar(db)
    asesor, otro, lider = _equipo(db)
    mio = _prospecto(db, asesor, correo="mio@guarda.test")
    suyo = _prospecto(db, otro, correo="suyo@guarda.test")
    ejecutar(db, ahora=_ahora())

    tarea_ajena = db.query(Tarea).filter(Tarea.lead_id == suyo.id).first()
    if tarea_ajena is None:
        fallo("no se creó la tarea ajena; el alcance no se estaría midiendo.")
        return

    cuerpo = cliente.get("/api/v1/agenda/hoy", headers=_cabeceras(asesor)).json()
    vistos = {t["prospecto"]["id"] for t in cuerpo["tareas"]}
    if suyo.id in vistos:
        fallo("un asesor ve en su bandeja el trabajo de otra persona.")
    if mio.id not in vistos:
        fallo("un asesor dejó de ver su propio trabajo.")

    for quien, etiqueta in ((asesor, "un asesor"), (lider, "el líder")):
        respuesta = cliente.post(
            f"/api/v1/agenda/tareas/{tarea_ajena.id}/hecha", headers=_cabeceras(quien)
        )
        if respuesta.status_code != 404:
            fallo(
                f"{etiqueta} pudo cerrar trabajo ajeno (HTTP {respuesta.status_code}); "
                "«hecha» deja de significar que alguien lo hizo."
            )
    db.refresh(tarea_ajena)
    if tarea_ajena.estado != ABIERTA:
        fallo("la tarea ajena acabó cerrada por quien no era su dueño.")

    ajena = cliente.get(f"/api/v1/agenda/hoy?asesor_id={otro.id}", headers=_cabeceras(asesor))
    if ajena.status_code != 404:
        fallo(f"pedir la bandeja de otro no responde 404 sino {ajena.status_code}.")

    if cliente.get("/api/v1/agenda/enfriandose", headers=_cabeceras(asesor)).status_code != 403:
        fallo("la vista de dirección se abrió a un asesor.")


# ==============================================================================
# 6. La bandeja no es un directorio
# ==============================================================================

def comprobar_que_no_hay_datos_de_contacto(db, cliente):
    print("6. La bandeja no lleva correo ni teléfono")
    _limpiar(db)
    asesor, _, _ = _equipo(db)
    lead = _prospecto(
        db, asesor, correo="contacto@guarda.test",
        creado=_hace(hours=60), categoria=ScoreCategory.HOT, score=91.0,
    )
    ejecutar(db, ahora=_ahora())

    for ruta in ("/api/v1/agenda/hoy", "/api/v1/agenda/avisos"):
        texto = cliente.get(ruta, headers=_cabeceras(asesor)).text
        if lead.email in texto:
            fallo(f"{ruta} devuelve el correo del prospecto: la lista de trabajo es un directorio.")
        if lead.phone and lead.phone.replace(" ", "") in texto.replace(" ", ""):
            fallo(f"{ruta} devuelve el teléfono del prospecto.")


# ==============================================================================
# 7. Todo lo que se crea tiene plazo, y solo caduca lo cerrado
# ==============================================================================

def comprobar_plazos(db):
    print("7. Tareas y avisos tienen plazo, y solo caduca lo que ya cumplió")
    con_plazo = {plazo.tabla for plazo in PLAZOS}
    for tabla in ("tareas", "avisos"):
        if tabla not in con_plazo:
            fallo(f"«{tabla}» se quedó sin plazo de conservación: vuelve a crecer para siempre.")

    for ajuste, minimo in PLAZOS_MINIMOS_DE_LAS_REGLAS.items():
        try:
            Settings(**{ajuste: minimo - 1})
            fallo(f"{ajuste} arranca por debajo de su mínimo ({minimo}).")
        except ValidationError:
            pass

    _limpiar(db)
    asesor, _, _ = _equipo(db)
    lead = _prospecto(db, asesor, correo="plazos@guarda.test")
    db.add_all([
        Tarea(
            lead_id=lead.id, asesor_id=asesor.id, regla=PRIMER_CONTACTO, clave="abierta-vieja",
            estado=ABIERTA, vence_el=_hace(days=900), motivo="Nadie la hizo.", creada_en=_hace(days=900),
        ),
        Tarea(
            lead_id=lead.id, asesor_id=asesor.id, regla=PRIMER_CONTACTO, clave="cerrada-vieja",
            estado=ESTADOS_CERRADOS[0], vence_el=_hace(days=900), motivo="Se hizo.",
            creada_en=_hace(days=900), cerrada_en=_hace(days=900),
        ),
        Aviso(
            usuario_id=asesor.id, lead_id=lead.id, regla=HOT_SIN_CONTACTO, clave="sin-leer",
            texto="Sin leer.", creado_en=_hace(days=900),
        ),
        Aviso(
            usuario_id=asesor.id, lead_id=lead.id, regla=HOT_SIN_CONTACTO, clave="leido",
            texto="Leído.", creado_en=_hace(days=900), leido_en=_hace(days=900),
        ),
    ])
    db.commit()

    aplicar_caducidad(db, plazos=[p for p in PLAZOS if p.tabla in ("tareas", "avisos")])

    if db.query(Tarea).filter(Tarea.clave == "abierta-vieja").count() == 0:
        fallo("una tarea abierta caducó: el trabajo pendiente se limpia en vez de hacerse.")
    if db.query(Tarea).filter(Tarea.clave == "cerrada-vieja").count():
        fallo("una tarea cerrada hace años no caduca: la tabla crece sin límite.")
    if db.query(Aviso).filter(Aviso.clave == "sin-leer").count() == 0:
        fallo("un aviso sin leer caducó: nadie llegó a enterarse y ya no podrá.")
    if db.query(Aviso).filter(Aviso.clave == "leido").count():
        fallo("un aviso leído hace años no caduca.")


# ==============================================================================
# 8. El motor no corre a ciegas
# ==============================================================================

def comprobar_bitacora(db):
    print("8. Cada regla corre y deja escrito qué hizo")
    if set(ORDEN_DE_LAS_REGLAS) != set(REGLAS):
        faltan = set(REGLAS) - set(ORDEN_DE_LAS_REGLAS)
        sobran = set(ORDEN_DE_LAS_REGLAS) - set(REGLAS)
        fallo(f"el orden de ejecución no cuadra con las reglas (faltan {faltan}, sobran {sobran}).")

    _limpiar(db)
    asesor, _, _ = _equipo(db)
    _prospecto(db, asesor, correo="bitacora@guarda.test")

    resultados = ejecutar(db, ahora=_ahora())

    corridas = [r.regla for r in resultados]
    if corridas != list(ORDEN_DE_LA_PASADA):
        fallo(f"la pasada no ejecutó todas las reglas: {corridas}.")

    asientos = db.query(AuditLog).filter(AuditLog.action == "regla.ejecucion").all()
    if len(asientos) != len(ORDEN_DE_LA_PASADA):
        fallo(
            f"la bitácora tiene {len(asientos)} asientos para {len(ORDEN_DE_LA_PASADA)} reglas: "
            "no se podría saber si el motor trabajó esta noche."
        )
    for asiento in asientos:
        if asiento.event_metadata is None or "tareas_creadas" not in asiento.event_metadata:
            fallo(f"el asiento de «{asiento.entity_id}» no dice cuántas tareas creó.")
            break
    if any(a.actor_email for a in asientos):
        fallo("un asiento del motor lleva actor: esa pasada no la pidió ninguna persona.")

    if HORIZONTE_HORAS < settings.REGLA_PRIMER_CONTACTO_HORAS:
        fallo(
            f"la bandeja mira {HORIZONTE_HORAS} h y el motor da {settings.REGLA_PRIMER_CONTACTO_HORAS} h "
            "de plazo: una tarea recién creada no se vería el día de hacerla."
        )


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
            (comprobar_idempotencia, (db,)),
            (comprobar_escalado, (db,)),
            (comprobar_que_nada_sale_del_panel, ()),
            (comprobar_que_no_toca_el_score, (db,)),
            (comprobar_alcance, (db, cliente)),
            (comprobar_que_no_hay_datos_de_contacto, (db, cliente)),
            (comprobar_plazos, (db,)),
            (comprobar_bitacora, (db,)),
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
        print(f"\nEl motor de reglas perdió {len(fallos)} defensa(s).")
        return 1
    print(
        "\nIdempotencia, escalado, nada fuera del panel, score intacto, alcance, sin datos de "
        "contacto, plazos y bitácora: el motor de reglas conserva sus defensas."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
