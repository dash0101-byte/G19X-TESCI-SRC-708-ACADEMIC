"""
Guarda del CI para el desenlace: lo único que produce etiquetas de entrenamiento.

    python scripts/guarda_de_los_desenlaces.py

Falla —con un mensaje que dice qué se perdió— si el sistema:

1. **cierra sin decir nada**: la edición de la ficha vuelve a aceptar «Ganado» o «Perdido»,
   o el cierre admite un motivo que no está en la lista. Cada cierre es una etiqueta, y una
   etiqueta sin motivo no se puede interpretar seis meses después;
2. **abre la puerta al texto libre**: el esquema del cierre gana un campo de texto, o el
   cliente escribe su propia copia de las listas. Lo primero lleva lo que alguien dijo por
   teléfono a la tabla que alimenta al modelo; lo segundo hace que añadir un motivo exija
   tocar dos sitios, y olvidarse de uno no rompe nada;
3. **reentrena por su cuenta**: el camino del cierre toca el artefacto, el registro de
   modelos o una biblioteca de entrenamiento. El capítulo dice explícitamente que aquí no
   se reentrena;
4. **mueve el score al cerrar**: entonces «¿el score acertaba?» deja de tener respuesta,
   porque el número guardado ya incorpora el desenlace;
5. **sigue mandando trabajo sobre lo cerrado**: la pasada crea tareas sobre un prospecto
   ganado, o la bandeja las enseña;
6. **promete ejemplos que no existen**: el contador del panel y el extractor del dataset
   dejan de contar lo mismo, o dejan de exigir los mismos mínimos. El panel diría «ya se
   puede reentrenar» mientras el extractor se niega;
7. **convierte el panel en un directorio**: el correo, el teléfono o el nombre de un
   prospecto vuelven a viajar en una vista que son totales;
8. **se salta los derechos del titular**: el desenlace deja de salir en la exportación o
   deja de irse con la supresión.

Por qué además de la suite: `test_desenlaces.py` comprueba casos. Esto comprueba
**propiedades**. Un campo `comentario` nuevo en el esquema del cierre no rompe ninguna
prueba existente —nadie lo envía— y aquí falla en cuanto existe.
"""
import datetime
import hashlib
import os
import re
import sys
import tempfile

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_BASE_TEMPORAL = os.path.join(tempfile.mkdtemp(prefix="guarda-desenlaces-"), "guarda.db")
# Antes de importar la aplicación: la configuración lee la base al cargarse.
os.environ["DATABASE_URL"] = f"sqlite:///{_BASE_TEMPORAL}"
os.environ.setdefault("ENVIRONMENT", "development")
sys.path.insert(0, os.path.join(RAIZ, "backend"))
sys.path.insert(0, os.path.join(RAIZ, "ml_pipeline", "src"))

from app.core.agenda import ABIERTA, DESCARTADA, PRIMER_CONTACTO  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.core.desenlaces import (  # noqa: E402
    GANADO,
    MINIMO_DE_CASOS,
    MINIMO_POR_CLASE,
    MOTIVOS,
    PERDIDO,
    TRAMOS,
)
from app.core.rate_limit import limiter  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.core.vector_del_modelo import CONDUCTUALES, VERSION_DEL_VECTOR  # noqa: E402
from app.models.entities import (  # noqa: E402
    Desenlace,
    Lead,
    LeadStatus,
    ScoreCategory,
    ScoreHistory,
    Tarea,
    User,
)
from app.schemas.desenlaces import CierreDelProspecto  # noqa: E402
from app.services import desenlaces as servicio  # noqa: E402
from app.services.derechos_del_titular import (  # noqa: E402
    TABLAS_DEL_PROSPECTO,
    exportar_prospecto,
    suprimir_prospecto,
)
from app.services.motor_de_reglas import ejecutar  # noqa: E402

UTC = datetime.timezone.utc

# Lo que no puede aparecer en el camino del cierre. No es una lista de bibliotecas
# prohibidas por gusto: cada una es una forma de que cerrar un prospecto acabe tocando el
# modelo que sirve en producción.
FORMAS_DE_REENTRENAR = (
    "joblib", "sklearn", "train_model", "model_registry", "feedback_dataset", "pandas",
)

# Los archivos que forman el camino del cierre.
CAMINO_DEL_CIERRE = (
    "backend/app/core/desenlaces.py",
    "backend/app/schemas/desenlaces.py",
    "backend/app/services/desenlaces.py",
    "backend/app/api/v1/endpoints/desenlaces.py",
)

ARTEFACTO = os.path.join(RAIZ, "ml_pipeline", "models", "lead_scorer_model.joblib")
REGISTRO = os.path.join(RAIZ, "ml_pipeline", "models", "registry.json")

fallos = []


def fallo(mensaje: str) -> None:
    fallos.append(mensaje)
    print(f"  FALLO: {mensaje}")


def _ahora():
    return datetime.datetime.now(UTC)


def _hoy():
    return _ahora().date()


def _limpiar(db):
    for modelo in (Desenlace, Tarea, ScoreHistory, Lead):
        db.query(modelo).delete()
    db.commit()


def _equipo(db):
    lider = db.query(User).filter(User.email == "lider.desenlaces@plurione.com").first()
    if lider is None:
        db.add_all([
            User(
                email="lider.desenlaces@plurione.com", full_name="Lider Desenlaces",
                role="Sales_Lead", hashed_password="!sin-contrasena:guarda",  # noqa: S106  hash inutilizable: estas cuentas no inician sesión
                is_sales_rep=True, capacity=40,
            ),
            User(
                email="asesor.desenlaces@plurione.com", full_name="Asesor Desenlaces",
                role="Commercial_Executive", hashed_password="!sin-contrasena:guarda",  # noqa: S106  ídem
                is_sales_rep=True, capacity=50,
            ),
        ])
        db.commit()
        lider = db.query(User).filter(User.email == "lider.desenlaces@plurione.com").first()
    asesor = db.query(User).filter(User.email == "asesor.desenlaces@plurione.com").first()
    return lider, asesor


# Una instantánea completa del vector vigente. Se construye desde `CONDUCTUALES` y no a
# mano: una variable nueva del modelo la incorpora sola, y así esta guarda no empieza a
# medir contra un vector que ya no existe sin que nadie lo note.
def _instantanea(version):
    return dict.fromkeys(CONDUCTUALES, 0) | {"version_del_vector": version}


def _prospecto(db, asesor, *, correo, con_instantanea=True, version=VERSION_DEL_VECTOR):
    lead = Lead(
        first_name="Prospecto", last_name="Desenlace", email=correo, company="Desenlaces SA",
        phone="+52 55 0000 2222",
        assigned_rep_id=asesor.id if asesor else None,
        created_at=_ahora() - datetime.timedelta(days=40),
        last_activity_at=_ahora() - datetime.timedelta(hours=3),
        current_score=77.0, score_category=ScoreCategory.HOT,
        status=LeadStatus.NEGOTIATION,
    )
    db.add(lead)
    db.commit()
    if con_instantanea:
        db.add(
            ScoreHistory(
                lead_id=lead.id, score=50.0, score_category=ScoreCategory.WARM,
                feature_snapshot=_instantanea(version),
                calculated_at=_ahora() - datetime.timedelta(days=40),
            )
        )
        db.commit()
    db.refresh(lead)
    return lead


def _cabeceras(usuario):
    return {"Authorization": f"Bearer {create_access_token(usuario)}"}


def _cierre(**extra):
    return {"resultado": PERDIDO, "motivo": "precio", "cerrado_el": _hoy().isoformat(), **extra}


# Cualquier bloque entre comillas triples. Se recorta antes de buscar: los docstrings de
# este proyecto explican precisamente POR QUÉ no se usa cada una de las formas de abajo, y
# buscarlas en el texto entero convertiría la explicación en el fallo.
TRIPLE_COMILLA = r'\"\"\".*?\"\"\"'


def _codigo(relativa: str) -> str:
    """El archivo sin comentarios ni docstrings: aquí se explica POR QUÉ no se usan."""
    texto = open(os.path.join(RAIZ, relativa), encoding="utf-8").read()
    codigo = "\n".join(
        linea for linea in texto.splitlines() if not linea.lstrip().startswith("#")
    )
    return re.sub(TRIPLE_COMILLA, "", codigo, flags=re.S)


def _huella(ruta: str):
    if not os.path.exists(ruta):
        return None
    with open(ruta, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


# ==============================================================================
# 1. No se cierra sin decir nada
# ==============================================================================

def comprobar_que_no_se_cierra_sin_motivo(db, cliente):
    print("1. Ganado y perdido exigen motivo, fecha y —si se ganó— tramo")
    _limpiar(db)
    lider, asesor = _equipo(db)
    lead = _prospecto(db, asesor, correo="sin.motivo@guarda.test")

    for etapa in ("WON", "LOST"):
        # La llamada va envuelta porque quitar la guarda no produce un 200 limpio: produce
        # lo que produzca el resto del camino, y una excepción del servidor abortaría esta
        # comprobación sin decir qué defensa se perdió. Cualquier cosa que no sea 422 es el
        # mismo defecto: la ficha vuelve a poder cerrar un prospecto sin decir por qué.
        try:
            codigo = cliente.put(
                f"/api/v1/leads/{lead.id}", json={"status": etapa}, headers=_cabeceras(lider)
            ).status_code
        except Exception as exc:  # noqa: BLE001
            codigo = f"excepción {exc.__class__.__name__}"
        if codigo != 422:
            fallo(
                f"la edición de la ficha acepta «{etapa}» (HTTP {codigo}): "
                "se pueden volver a cerrar prospectos sin decir por qué."
            )
    db.refresh(lead)
    if lead.status != LeadStatus.NEGOTIATION:
        fallo("un cierre rechazado dejó la etapa movida: el 422 no revirtió nada.")

    rechazos = {
        "un motivo inventado": _cierre(motivo="me-cayo-mal"),
        "un motivo del otro desenlace": _cierre(motivo="recomendacion"),
        "un ganado sin tramo": _cierre(resultado=GANADO, motivo="precio"),
        "un perdido con tramo": _cierre(tramo="mas_de_1m"),
        "una fecha futura": _cierre(cerrado_el=(_hoy() + datetime.timedelta(days=1)).isoformat()),
        "una fecha anterior al alta": _cierre(
            cerrado_el=(_hoy() - datetime.timedelta(days=400)).isoformat()
        ),
    }
    for descripcion, cuerpo in rechazos.items():
        respuesta = cliente.post(
            f"/api/v1/leads/{lead.id}/desenlace", json=cuerpo, headers=_cabeceras(lider)
        )
        if respuesta.status_code != 422:
            fallo(f"el cierre admite {descripcion} (HTTP {respuesta.status_code}).")

    valido = cliente.post(
        f"/api/v1/leads/{lead.id}/desenlace", json=_cierre(), headers=_cabeceras(lider)
    )
    if valido.status_code != 200:
        fallo(f"un cierre correcto no se pudo registrar (HTTP {valido.status_code}): {valido.text}")


# ==============================================================================
# 2. Nada de texto libre, y una sola copia de las listas
# ==============================================================================

def comprobar_que_no_hay_texto_libre(cliente, db):
    print("2. Ni un campo de texto, ni una segunda copia de las listas")
    campos = set(CierreDelProspecto.model_fields)
    esperados = {"resultado", "motivo", "cerrado_el", "tramo"}
    if campos != esperados:
        fallo(
            f"el esquema del cierre tiene {sorted(campos)} y debería tener {sorted(esperados)}: "
            "un campo de más acaba llevando lo que alguien dijo por teléfono a la tabla que "
            "alimenta al modelo."
        )

    # Las claves válidas, servidas por el servidor, tienen que ser las del vocabulario.
    lider, _ = _equipo(db)
    cuerpo = cliente.get("/api/v1/desenlaces/opciones", headers=_cabeceras(lider)).json()
    servidas = {
        r["clave"]: {m["clave"] for m in r["motivos"]} for r in cuerpo["resultados"]
    }
    del_codigo = {r: {m.clave for m in MOTIVOS[r]} for r in (GANADO, PERDIDO)}
    if servidas != del_codigo:
        fallo(f"las opciones servidas no son las del vocabulario: {servidas} vs {del_codigo}.")
    if {t["clave"] for t in cuerpo["tramos"]} != {t.clave for t in TRAMOS}:
        fallo("los tramos servidos no son los del vocabulario.")

    # Y el cliente no puede llevar su propia copia: el día que alguien añada un motivo,
    # tocaría dos sitios y olvidarse de uno no rompería nada.
    claves = {m.clave for lista in MOTIVOS.values() for m in lista} - {"otro", "precio", "plazo", "perfil"}
    for carpeta, _, archivos in os.walk(os.path.join(RAIZ, "frontend", "src")):
        for archivo in archivos:
            if not archivo.endswith((".js", ".jsx")) or archivo.endswith(".test.jsx"):
                continue
            ruta = os.path.join(carpeta, archivo)
            texto = open(ruta, encoding="utf-8").read()
            escritas = sorted(c for c in claves if f"'{c}'" in texto or f'"{c}"' in texto)
            if escritas:
                relativa = os.path.relpath(ruta, RAIZ).replace("\\", "/")
                fallo(
                    f"{relativa} lleva escritas las claves {escritas}: el cliente tiene una "
                    "segunda copia de una lista que solo debería vivir en el servidor."
                )


# ==============================================================================
# 3. Cerrar no reentrena
# ==============================================================================

def comprobar_que_cerrar_no_reentrena(db, cliente):
    print("3. Cerrar un prospecto no toca el modelo")
    for relativa in CAMINO_DEL_CIERRE:
        codigo = _codigo(relativa)
        for forma in FORMAS_DE_REENTRENAR:
            if re.search(rf"\b{re.escape(forma)}\b", codigo):
                fallo(f"{relativa} usa «{forma}»: cerrar un prospecto puede acabar tocando el modelo.")

    antes = (_huella(ARTEFACTO), _huella(REGISTRO))
    if antes == (None, None):
        print("  (sin artefacto ni registro en el árbol: solo se comprueba el código)")
        return

    _limpiar(db)
    lider, asesor = _equipo(db)
    lead = _prospecto(db, asesor, correo="no.reentrena@guarda.test")
    cliente.post(f"/api/v1/leads/{lead.id}/desenlace", json=_cierre(), headers=_cabeceras(lider))
    cliente.get("/api/v1/desenlaces/panel", headers=_cabeceras(lider))

    if (_huella(ARTEFACTO), _huella(REGISTRO)) != antes:
        fallo(
            "el artefacto del modelo o el registro cambiaron al cerrar un prospecto: este "
            "capítulo no reentrena nada."
        )


# ==============================================================================
# 4. El score del cierre es el del momento
# ==============================================================================

def comprobar_que_no_mueve_el_score(db, cliente):
    print("4. Cerrar no recalcula la puntuación")
    _limpiar(db)
    lider, asesor = _equipo(db)
    lead = _prospecto(db, asesor, correo="score.cierre@guarda.test")
    antes = (lead.current_score, lead.score_category)

    respuesta = cliente.post(
        f"/api/v1/leads/{lead.id}/desenlace",
        json=_cierre(resultado=GANADO, motivo="perfil", tramo="no_consta"),
        headers=_cabeceras(lider),
    )
    if respuesta.status_code != 200:
        fallo(f"no se pudo cerrar para medir el score (HTTP {respuesta.status_code}).")
        return

    db.refresh(lead)
    if (lead.current_score, lead.score_category) != antes:
        fallo(
            f"cerrar movió la puntuación: {antes} -> ({lead.current_score}, {lead.score_category}); "
            "«¿el score acertaba?» deja de tener respuesta."
        )
    guardado = db.query(Desenlace).filter(Desenlace.lead_id == lead.id).first()
    if guardado.score_al_cierre != antes[0]:
        fallo("el desenlace guardó un score distinto del que el prospecto tenía al cerrarse.")


# ==============================================================================
# 5. Lo cerrado sale del trabajo
# ==============================================================================

def comprobar_que_lo_cerrado_sale_del_trabajo(db, cliente):
    print("5. Un prospecto cerrado no recibe más tareas ni sale en la bandeja")
    _limpiar(db)
    lider, asesor = _equipo(db)
    lead = _prospecto(db, asesor, correo="fuera.del.trabajo@guarda.test")
    lead.created_at = _ahora() - datetime.timedelta(hours=2)
    db.commit()

    ejecutar(db, ahora=_ahora())
    if db.query(Tarea).filter(Tarea.lead_id == lead.id, Tarea.estado == ABIERTA).count() == 0:
        fallo("la pasada no creó ninguna tarea antes de cerrar: el resto no mediría nada.")
        return

    cliente.post(f"/api/v1/leads/{lead.id}/desenlace", json=_cierre(), headers=_cabeceras(lider))

    abiertas = db.query(Tarea).filter(Tarea.lead_id == lead.id, Tarea.estado == ABIERTA).count()
    if abiertas:
        fallo(f"cerrar dejó {abiertas} tarea(s) abierta(s): alguien seguiría llamando a un cliente cerrado.")
    descartadas = db.query(Tarea).filter(Tarea.lead_id == lead.id, Tarea.estado == DESCARTADA).count()
    if descartadas == 0:
        fallo("las tareas se cerraron con un estado que no es «descartada»: nadie las hizo.")

    # Un prospecto que se cierra ANTES de que corra ninguna pasada. Hace falta uno así:
    # sobre el primero, el índice único de las tareas impediría recrear la que ya existe
    # —aunque estuviera descartada—, y esta comprobación pasaría con el filtro de las
    # reglas quitado. Este segundo no tiene ninguna tarea que le estorbe.
    virgen = _prospecto(db, asesor, correo="cerrado.de.entrada@guarda.test")
    virgen.created_at = _ahora() - datetime.timedelta(hours=2)
    db.commit()
    cliente.post(f"/api/v1/leads/{virgen.id}/desenlace", json=_cierre(), headers=_cabeceras(lider))

    ejecutar(db, ahora=_ahora() + datetime.timedelta(days=1))
    for cerrado, cual in ((lead, "uno que ya tenía tareas"), (virgen, "uno cerrado de entrada")):
        if db.query(Tarea).filter(Tarea.lead_id == cerrado.id, Tarea.estado == ABIERTA).count():
            fallo(
                f"la pasada del día siguiente volvió a crear trabajo sobre {cual}, ya cerrado."
            )

    # Y la segunda defensa: una tarea abierta sobre un prospecto que se cerró por otro
    # camino —una migración, un arreglo a mano— tampoco puede salir en la bandeja. Se monta
    # a mano justamente porque el cierre normal ya la habría descartado, y entonces esta
    # comprobación no mediría el filtro sino el descarte.
    por_otro_camino = _prospecto(db, asesor, correo="cerrado.a.mano@guarda.test", con_instantanea=False)
    db.add(
        Tarea(
            lead_id=por_otro_camino.id, asesor_id=asesor.id, regla=PRIMER_CONTACTO,
            clave="a-mano", estado=ABIERTA, vence_el=_ahora(),
            motivo="Asignado y todavía sin contactar.", creada_en=_ahora(),
        )
    )
    por_otro_camino.status = LeadStatus.WON
    db.commit()

    bandeja = cliente.get("/api/v1/agenda/hoy", headers=_cabeceras(asesor)).json()
    vistos = {t["prospecto"]["id"] for t in bandeja["tareas"]}
    if lead.id in vistos:
        fallo("la bandeja «Hoy» sigue enseñando trabajo de un prospecto cerrado.")
    if por_otro_camino.id in vistos:
        fallo(
            "la bandeja «Hoy» enseña una tarea abierta sobre un prospecto cerrado por otro "
            "camino: la segunda defensa no existe."
        )


# ==============================================================================
# 6. El contador cuenta lo que el extractor usaría
# ==============================================================================

def comprobar_el_contador(db, cliente):
    print("6. El contador del panel y el extractor del dataset cuentan lo mismo")
    import feedback_dataset

    if feedback_dataset.MINIMO_EJEMPLOS != MINIMO_DE_CASOS:
        fallo(
            f"el extractor exige {feedback_dataset.MINIMO_EJEMPLOS} ejemplos y el contador "
            f"{MINIMO_DE_CASOS}: el panel diría «ya se puede reentrenar» y el extractor se negaría."
        )
    if feedback_dataset.MINIMO_POR_CLASE != MINIMO_POR_CLASE:
        fallo("el mínimo por clase del extractor y el del contador discrepan.")

    _limpiar(db)
    lider, asesor = _equipo(db)
    # Uno utilizable, uno con la instantánea de otra versión y uno sin instantánea.
    utilizable = _prospecto(db, asesor, correo="utilizable@guarda.test")
    viejo_vector = _prospecto(db, asesor, correo="vector.viejo@guarda.test", version=1)
    sin_nada = _prospecto(db, asesor, correo="sin.instantanea@guarda.test", con_instantanea=False)
    for lead in (utilizable, viejo_vector, sin_nada):
        cliente.post(
            f"/api/v1/leads/{lead.id}/desenlace", json=_cierre(), headers=_cabeceras(lider)
        )

    progreso = servicio.progreso_del_reentrenamiento(db)
    if progreso.cerrados != 3:
        fallo(f"el contador ve {progreso.cerrados} cierres y se registraron 3.")
    if progreso.utilizables != 1:
        fallo(
            f"el contador considera utilizables {progreso.utilizables} de 3; solo uno tiene "
            "instantánea de la versión vigente del vector."
        )
    if progreso.de_un_vector_anterior != 1 or progreso.sin_instantanea != 1:
        fallo("la merma no se desglosa: el panel escondería cuántos cierres no sirven.")

    marco, _ = feedback_dataset.construir_dataset(db=db, exigir_minimos=False)
    if len(marco) != progreso.utilizables:
        fallo(
            f"el extractor trae {len(marco)} filas y el contador promete {progreso.utilizables}: "
            "el panel estaría prometiendo ejemplos que no existen."
        )
    if len(marco) and "motivo" in getattr(feedback_dataset, "COLUMNAS_MODELO", []):
        fallo("el motivo del cierre entró entre las variables del modelo: se conoce al cerrar.")


# ==============================================================================
# 7. El panel no es un directorio
# ==============================================================================

def comprobar_que_el_panel_no_lleva_a_nadie(db, cliente):
    print("7. El panel son totales: ni correo, ni teléfono, ni nombres")
    _limpiar(db)
    lider, asesor = _equipo(db)
    lead = _prospecto(db, asesor, correo="directorio@guarda.test")
    cliente.post(f"/api/v1/leads/{lead.id}/desenlace", json=_cierre(), headers=_cabeceras(lider))

    texto = cliente.get("/api/v1/desenlaces/panel", headers=_cabeceras(lider)).text
    if lead.email in texto:
        fallo("el panel devuelve el correo del prospecto: una vista de totales es un directorio.")
    if lead.phone and lead.phone.replace(" ", "") in texto.replace(" ", ""):
        fallo("el panel devuelve el teléfono del prospecto.")
    if lead.company and lead.company in texto:
        fallo("el panel devuelve la empresa del prospecto.")

    # Y es de dirección: un asesor no lo ve.
    if cliente.get("/api/v1/desenlaces/panel", headers=_cabeceras(asesor)).status_code != 403:
        fallo("la vista de dirección se abrió a un asesor.")


# ==============================================================================
# 8. Los derechos del titular alcanzan al desenlace
# ==============================================================================

def comprobar_los_derechos_del_titular(db, cliente):
    print("8. El desenlace sale en la exportación y se va con la supresión")
    if "desenlaces" not in TABLAS_DEL_PROSPECTO:
        fallo("«desenlaces» no está en el mapa de tablas del titular: no se exporta ni se borra.")
        return

    _limpiar(db)
    lider, asesor = _equipo(db)
    lead = _prospecto(db, asesor, correo="titular.desenlace@guarda.test")
    cliente.post(f"/api/v1/leads/{lead.id}/desenlace", json=_cierre(), headers=_cabeceras(lider))

    documento = exportar_prospecto(db, lead)
    seccion = TABLAS_DEL_PROSPECTO["desenlaces"]
    if not documento.get(seccion):
        fallo(f"la exportación no trae la sección «{seccion}»: se guarda un dato suyo y no se dice.")
    if not documento.get("conservacion", {}).get("desenlace"):
        fallo("la exportación no dice cuánto se conserva el desenlace.")

    lead_id = lead.id
    suprimir_prospecto(db, lead)
    if db.query(Desenlace).filter(Desenlace.lead_id == lead_id).count():
        fallo("tras suprimir al prospecto queda su desenlace: el borrado deja un rincón.")


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
            (comprobar_que_no_se_cierra_sin_motivo, (db, cliente)),
            (comprobar_que_no_hay_texto_libre, (cliente, db)),
            (comprobar_que_cerrar_no_reentrena, (db, cliente)),
            (comprobar_que_no_mueve_el_score, (db, cliente)),
            (comprobar_que_lo_cerrado_sale_del_trabajo, (db, cliente)),
            (comprobar_el_contador, (db, cliente)),
            (comprobar_que_el_panel_no_lleva_a_nadie, (db, cliente)),
            (comprobar_los_derechos_del_titular, (db, cliente)),
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
        print(f"\nEl desenlace perdió {len(fallos)} defensa(s).")
        return 1
    print(
        "\nMotivo obligatorio, sin texto libre, sin reentrenar, score intacto, lo cerrado "
        "fuera del trabajo, contador fiel al extractor, panel sin nadie dentro y derechos "
        "del titular: el desenlace conserva sus defensas."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
