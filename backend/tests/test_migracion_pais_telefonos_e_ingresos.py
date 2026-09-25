"""
La migración del capítulo 32 (`a4c8d1e70f39`), ida y vuelta.

Como las de los capítulos 25 a 30: Alembic de verdad, en un proceso aparte y sobre una
SQLite en fichero temporal. La suite nunca toca la base real.

Lo que tiene que cumplirse, y por qué cada cosa
------------------------------------------------
**El esquema.** `leads.country` pasa a admitir vacío. Es lo que permite que una ficha diga
«no consta» en lugar de decir «México» sin que nadie lo haya dicho.

**La migración de datos toca poco y se puede justificar entera.** Solo vacía las fichas de
las que consta que nadie indicó el país: las que creó la **página de interés**, cuyo
formulario no lo pregunta. Se comprueban las dos direcciones del criterio, porque un
criterio que solo se prueba donde acierta no es un criterio:

* una ficha del panel con «México» **no** se toca —quien la dio de alta tuvo el campo
  delante—, y tampoco una sin ninguna actividad, de la que no se sabe nada;
* «Colombia» no se toca aunque la ficha venga de la página: lo que se borra es la
  suposición, no el país;
* manda la **primera** actividad. Una ficha nacida en la página que después recibió una
  nota manual sigue contando como suya; una nacida en el panel que después recibió un
  envío de la página, no.

**Los teléfonos de los asesores** quedan en E.164, y los que no tienen forma de número se
dejan como estaban: borrarlos sería perder el dato en lugar de corregirlo.

**Los ceros de ingresos** pasan a vacío, y una cifra de verdad no se toca.

**La reversión vuelve a suponer, y se comprueba que lo hace.** Para restaurar `NOT NULL`
hay que rellenar los vacíos, y el único valor posible es «México»: la prueba lo fija por
escrito para que nadie revierta creyendo que recupera el estado anterior. Los teléfonos y
los ceros no vuelven, y también se comprueba.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ANTERIOR = "c1d9f4b72a08"
ESTA = "a4c8d1e70f39"

_SONDA = r"""
import json, os
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
import sqlalchemy as sa

url = os.environ["DATABASE_URL"]
cfg = Config()
cfg.set_main_option("script_location", os.environ["ALEMBIC_DIR"])
cfg.set_main_option("sqlalchemy.url", url)
motor = sa.create_engine(url)
resultado = {}

AHORA = "2026-09-24 08:00:00"

def paises():
    with motor.connect() as c:
        return {f[0]: f[1] for f in c.execute(sa.text(
            "SELECT email, country FROM leads ORDER BY id")).fetchall()}

def telefonos():
    with motor.connect() as c:
        return {f[0]: f[1] for f in c.execute(sa.text(
            "SELECT email, phone FROM users ORDER BY id")).fetchall()}

def ingresos():
    with motor.connect() as c:
        return {f[0]: f[1] for f in c.execute(sa.text(
            "SELECT email, annual_revenue FROM leads ORDER BY id")).fetchall()}

def pais_admite_vacio():
    columna = next(c for c in sa.inspect(motor).get_columns("leads") if c["name"] == "country")
    return columna["nullable"]

# --- antes ------------------------------------------------------------------------------
command.upgrade(cfg, os.environ["ANTERIOR"])

ASESORES = [
    ("ana@plurione.com", "55 9876 5432"),          # se normaliza
    ("luis@plurione.com", "+52 1 55 1234 5678"),   # el «1» de movil mexicano, tambien
    ("eva@plurione.com", "  "),                    # en blanco -> NULL
    ("raul@plurione.com", "pregunta en recepcion"),# sin forma de numero: se deja
    ("nadia@plurione.com", None),                  # sin telefono
]
# (correo, pais, ingresos, fuentes de sus actividades EN ORDEN)
FICHAS = [
    ("pagina@empresa.com",    "Mexico_", 0.0,      ["pagina_de_interes"]),
    ("panel@empresa.com",     "Mexico_", 150000.0, ["manual"]),
    ("colombia@empresa.com",  "Colombia", None,    ["pagina_de_interes"]),
    ("sin_actividad@empresa.com", "Mexico_", 0.0,  []),
    ("pagina_luego_nota@empresa.com", "Mexico_", None, ["pagina_de_interes", "manual"]),
    ("panel_luego_pagina@empresa.com", "Mexico_", None, ["manual", "pagina_de_interes"]),
    ("crm@empresa.com",       "Mexico_", None,     ["crm"]),
]
MEXICO = "México"

with motor.begin() as c:
    c.execute(sa.text("PRAGMA foreign_keys = ON"))
    for correo, telefono in ASESORES:
        c.execute(sa.text(
            "INSERT INTO users (email, hashed_password, full_name, role, is_active, "
            "token_version, is_sales_rep, must_change_password, phone, password_changed_at, "
            "created_at, updated_at) "
            "VALUES (:e, '!x', 'Persona', 'Commercial_Executive', 1, 0, 1, 0, :p, :t, :t, :t)"
        ), {"e": correo, "p": telefono, "t": AHORA})
    for indice, (correo, pais, revenue, fuentes) in enumerate(FICHAS, start=1):
        c.execute(sa.text(
            "INSERT INTO leads (first_name, last_name, email, country, annual_revenue, source, "
            "status, qualification_status, current_score, score_category, conversion_probability, "
            "last_score_update, last_activity_at, created_at, updated_at) "
            "VALUES ('Persona', 'Apellido', :e, :pais, :rev, 'LinkedIn', 'NEW', 'INCOMING', "
            "10.0, 'COLD', 0.1, :t, :t, :t, :t)"
        ), {"e": correo, "pais": MEXICO if pais == "Mexico_" else pais, "rev": revenue, "t": AHORA})
        for fuente in fuentes:
            c.execute(sa.text(
                "INSERT INTO lead_activities (lead_id, activity_type, channel, source, "
                "verificada, occurred_at, created_at) "
                "VALUES (:l, 'FORM_SUBMIT', 'Web', :f, 0, :t, :t)"
            ), {"l": indice, "f": fuente, "t": AHORA})

resultado["pais_admite_vacio_antes"] = pais_admite_vacio()
resultado["paises_antes"] = paises()

# --- hacia delante -----------------------------------------------------------------------
command.upgrade(cfg, os.environ["ESTA"])
resultado["pais_admite_vacio_despues"] = pais_admite_vacio()
resultado["paises_despues"] = paises()
resultado["telefonos_despues"] = telefonos()
resultado["ingresos_despues"] = ingresos()

# Una ficha nueva puede nacer sin pais: el esquema lo admite de verdad, no solo en el modelo.
with motor.begin() as c:
    c.execute(sa.text(
        "INSERT INTO leads (first_name, last_name, email, source, status, qualification_status, "
        "current_score, score_category, conversion_probability, last_score_update, "
        "last_activity_at, created_at, updated_at) "
        "VALUES ('Nueva', 'Ficha', 'nueva@empresa.com', 'Website', 'NEW', 'INCOMING', 0.0, "
        "'COLD', 0.0, :t, :t, :t, :t)"
    ), {"t": AHORA})
with motor.connect() as c:
    resultado["ficha_nueva_sin_pais"] = c.execute(sa.text(
        "SELECT country FROM leads WHERE email = 'nueva@empresa.com'")).scalar()

# --- hacia atras --------------------------------------------------------------------------
command.downgrade(cfg, os.environ["ANTERIOR"])
resultado["pais_admite_vacio_tras_revertir"] = pais_admite_vacio()
resultado["paises_tras_revertir"] = paises()
resultado["telefonos_tras_revertir"] = telefonos()
resultado["ingresos_tras_revertir"] = ingresos()

# --- y otra vez hacia delante, hasta el final ----------------------------------------------
command.upgrade(cfg, "head")
resultado["pais_admite_vacio_al_final"] = pais_admite_vacio()

import sys
sys.path.insert(0, os.environ["BACKEND"])
from app.core.database import Base
import app.models.entities  # noqa: F401
with motor.connect() as c:
    diferencias = compare_metadata(MigrationContext.configure(c), Base.metadata)
resultado["diferencias"] = [repr(d) for d in diferencias]
print("__RESULTADO__" + json.dumps(resultado))
"""


def _ciclo(tmp_path: Path) -> dict:
    raiz = Path(__file__).resolve().parents[2]
    base = tmp_path / "migracion_capitulo_32.db"
    entorno = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{base.as_posix()}",
        "ALEMBIC_DIR": str(raiz / "backend" / "alembic"),
        "BACKEND": str(raiz / "backend"),
        "ANTERIOR": ANTERIOR,
        "ESTA": ESTA,
        "PYTHONPATH": str(raiz / "backend") + os.pathsep + str(raiz),
        "PYTHONIOENCODING": "utf-8",
    }
    proceso = subprocess.run(  # noqa: S603  intérprete propio y script literal, sin entrada externa
        [sys.executable, "-c", _SONDA],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(raiz),
        env=entorno,
        timeout=300,
    )
    assert proceso.returncode == 0, proceso.stderr
    linea = next(s for s in proceso.stdout.splitlines() if s.startswith("__RESULTADO__"))
    return json.loads(linea.removeprefix("__RESULTADO__"))


MEXICO = "México"


def test_ciclo_completo_de_la_migracion(tmp_path):
    r = _ciclo(tmp_path)

    # --- el esquema ------------------------------------------------------------------
    assert r["pais_admite_vacio_antes"] is False
    assert r["pais_admite_vacio_despues"] is True
    assert r["ficha_nueva_sin_pais"] is None, "la columna admite vacío en la base, no solo en el modelo"

    # --- la migración de datos, en sus dos direcciones --------------------------------
    despues = r["paises_despues"]
    # Se vacía: nació en la página de interés, que no pregunta el país.
    assert despues["pagina@empresa.com"] is None
    # Y también si después recibió una nota manual: manda la PRIMERA actividad, que es la
    # que creó la ficha.
    assert despues["pagina_luego_nota@empresa.com"] is None

    # No se toca: el panel enseñaba el campo relleno y quien dio de alta lo dejó estar. Es
    # una elección débil, pero es una elección, y la base no guarda si el campo se tocó.
    assert despues["panel@empresa.com"] == MEXICO
    # Tampoco si la página llegó DESPUÉS: esa fuente no reescribe fichas existentes.
    assert despues["panel_luego_pagina@empresa.com"] == MEXICO
    # Ni una ficha sin actividades, de la que no consta nada.
    assert despues["sin_actividad@empresa.com"] == MEXICO
    # Ni la que llegó por el CRM, que puede mandar `country` o no mandarlo.
    assert despues["crm@empresa.com"] == MEXICO
    # Lo que se borra es la suposición, no el país.
    assert despues["colombia@empresa.com"] == "Colombia"

    # --- los teléfonos de los asesores ------------------------------------------------
    telefonos = r["telefonos_despues"]
    assert telefonos["ana@plurione.com"] == "+525598765432"
    assert telefonos["luis@plurione.com"] == "+525512345678", "el «1» de móvil mexicano se retira"
    assert telefonos["eva@plurione.com"] is None, "en blanco es «sin teléfono», no un teléfono"
    assert telefonos["raul@plurione.com"] == "pregunta en recepcion", (
        "lo que no se entiende se deja: borrarlo sería perder el dato en lugar de corregirlo"
    )
    assert telefonos["nadia@plurione.com"] is None

    # --- los ceros de ingresos ---------------------------------------------------------
    ingresos = r["ingresos_despues"]
    assert ingresos["pagina@empresa.com"] is None, "el cero era un hueco rellenado, no una cifra"
    assert ingresos["panel@empresa.com"] == 150000.0, "una cifra de verdad no se toca"
    assert ingresos["colombia@empresa.com"] is None

    # --- hacia atrás: qué recupera y qué no --------------------------------------------
    assert r["pais_admite_vacio_tras_revertir"] is False
    # La reversión VUELVE A SUPONER. No hay forma de restaurar `NOT NULL` sin rellenar, y
    # el único valor posible es «México»; queda escrito aquí para que quien revierta sepa
    # qué está firmando.
    assert r["paises_tras_revertir"]["pagina@empresa.com"] == MEXICO
    # Los teléfonos no se des-normalizan: la forma anterior no está guardada en ninguna
    # parte, y fingir lo contrario exigiría inventarla.
    assert r["telefonos_tras_revertir"]["ana@plurione.com"] == "+525598765432"
    # Y los ceros no vuelven: escribirlos sería reintroducir a mano el defecto del
    # capítulo 24, en fichas que quizá nunca lo tuvieron.
    assert r["ingresos_tras_revertir"]["pagina@empresa.com"] is None

    # --- y otra vez hacia delante, hasta el final ---------------------------------------
    assert r["pais_admite_vacio_al_final"] is True
    assert r["diferencias"] == [], "el esquema migrado y el declarado por los modelos coinciden"
