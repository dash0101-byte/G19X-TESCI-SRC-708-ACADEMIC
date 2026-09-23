"""
La migración de las tareas y los avisos (`a8d2f16c5b03`), ida y vuelta.

Como las de los capítulos 25, 26 y 27: Alembic de verdad, en un proceso aparte y sobre una
SQLite en fichero temporal. La suite nunca toca la base real.

Lo que tiene que cumplirse:

* Aparecen `tareas` y `avisos` con sus columnas, y `leads` gana `dormido_desde`.
* Los prospectos que ya existían quedan con `dormido_desde` **nulo**: ninguno se marca a
  ciegas al migrar. Marcarlos habría llenado la campana de avisos sobre un pasado que nadie
  puede atender.
* El índice único de `tareas` **impide** dos veces la misma `(regla, prospecto, clave)` y
  **permite** dos claves distintas de la misma regla. Es lo que hace idempotente la pasada.
* El de `avisos` incluye al destinatario: el mismo hecho avisa al asesor y al líder —dos
  filas— pero no avisa dos veces a la misma persona.
* Al revertir desaparecen las dos tablas y la columna, y **el prospecto y su actividad
  siguen ahí**: nada de lo que se borra es un hecho suyo.
* Se puede volver a migrar hacia delante, y al final de la cadena el esquema es el de los
  modelos.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ANTERIOR = "f3c7a90b12e4"
ESTA = "a8d2f16c5b03"

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

def columnas(tabla):
    return sorted(c["name"] for c in sa.inspect(motor).get_columns(tabla))

def tablas():
    return sorted(sa.inspect(motor).get_table_names())

AHORA = "2026-09-23 08:00:00"

# --- antes: un prospecto asignado, con una actividad y dos cuentas -----------------------
command.upgrade(cfg, os.environ["ANTERIOR"])
with motor.begin() as c:
    for correo, nombre, rol in [
        ("asesora@plurione.com", "Asesora", "Commercial_Executive"),
        ("lider@plurione.com", "Lider", "Sales_Lead"),
    ]:
        c.execute(sa.text(
            "INSERT INTO users (email, hashed_password, full_name, role, is_active, token_version, "
            "is_sales_rep, must_change_password, password_changed_at, created_at, updated_at) "
            "VALUES (:e, '!x', :n, :r, 1, 0, 1, 0, :t, :t, :t)"
        ), {"e": correo, "n": nombre, "r": rol, "t": AHORA})
    c.execute(sa.text(
        "INSERT INTO leads (first_name, last_name, email, country, source, status, "
        "qualification_status, current_score, score_category, conversion_probability, "
        "last_score_update, last_activity_at, created_at, updated_at, assigned_rep_id) "
        "VALUES ('Rosa', 'Lima', 'rosa@empresa.com', 'México', 'LinkedIn', 'NEW', 'INCOMING', "
        "72.0, 'HOT', 0.5, :t, :t, :t, :t, 1)"
    ), {"t": AHORA})
    c.execute(sa.text(
        "INSERT INTO lead_activities (lead_id, activity_type, channel, source, verificada, "
        "occurred_at, created_at) VALUES (1, 'FORM_SUBMIT', 'LinkedIn', 'pagina_de_interes', 1, :t, :t)"
    ), {"t": AHORA})
resultado["tablas_antes"] = tablas()

# --- hacia delante -----------------------------------------------------------------------
command.upgrade(cfg, os.environ["ESTA"])
resultado["tablas_despues"] = tablas()
resultado["columnas_tareas"] = columnas("tareas")
resultado["columnas_avisos"] = columnas("avisos")
resultado["leads_tiene_dormido"] = "dormido_desde" in columnas("leads")
with motor.connect() as c:
    resultado["dormido_de_los_que_ya_estaban"] = [
        f[0] for f in c.execute(sa.text("SELECT dormido_desde FROM leads ORDER BY id")).fetchall()
    ]

def inserta_tarea(regla, clave, asesor=1):
    with motor.begin() as c:
        c.execute(sa.text(
            "INSERT INTO tareas (lead_id, asesor_id, regla, clave, estado, vence_el, motivo, creada_en) "
            "VALUES (1, :a, :r, :k, 'abierta', :t, 'porque sí', :t)"
        ), {"a": asesor, "r": regla, "k": clave, "t": AHORA})

def inserta_aviso(usuario, regla, clave):
    with motor.begin() as c:
        c.execute(sa.text(
            "INSERT INTO avisos (usuario_id, lead_id, regla, clave, texto, creado_en) "
            "VALUES (:u, 1, :r, :k, 'algo pasó', :t)"
        ), {"u": usuario, "r": regla, "k": clave, "t": AHORA})

inserta_tarea("primer_contacto", "1")
# La misma regla y la misma clave, otra vez: es lo que hace la pasada del día siguiente.
try:
    inserta_tarea("primer_contacto", "1")
    resultado["tarea_repetida_entra"] = True
except sa.exc.IntegrityError:
    resultado["tarea_repetida_entra"] = False
# La misma regla con otra clave sí: reasignar el prospecto crea su propia tarea.
inserta_tarea("primer_contacto", "2", asesor=2)
resultado["otra_clave_entra"] = True

inserta_aviso(1, "hot_sin_contacto", "d2026-09-23")
# El mismo hecho, otra persona: el líder también se entera.
inserta_aviso(2, "hot_sin_contacto", "d2026-09-23")
resultado["dos_destinatarios_entran"] = True
try:
    inserta_aviso(1, "hot_sin_contacto", "d2026-09-23")
    resultado["aviso_repetido_entra"] = True
except sa.exc.IntegrityError:
    resultado["aviso_repetido_entra"] = False

with motor.begin() as c:
    c.execute(sa.text("UPDATE leads SET dormido_desde = :t WHERE id = 1"), {"t": AHORA})
    resultado["tareas_antes_de_revertir"] = c.execute(sa.text("SELECT COUNT(*) FROM tareas")).scalar()
    resultado["avisos_antes_de_revertir"] = c.execute(sa.text("SELECT COUNT(*) FROM avisos")).scalar()

# --- hacia atrás -------------------------------------------------------------------------
command.downgrade(cfg, os.environ["ANTERIOR"])
resultado["tablas_tras_revertir"] = tablas()
resultado["leads_tras_revertir"] = columnas("leads")
with motor.connect() as c:
    resultado["prospecto_tras_revertir"] = [
        list(f) for f in c.execute(sa.text(
            "SELECT email, current_score, assigned_rep_id FROM leads ORDER BY id")).fetchall()
    ]
    resultado["actividades_tras_revertir"] = c.execute(sa.text(
        "SELECT COUNT(*) FROM lead_activities")).scalar()

# --- y otra vez hacia delante, hasta el final --------------------------------------------
command.upgrade(cfg, "head")
resultado["tablas_al_final"] = tablas()
with motor.connect() as c:
    resultado["tareas_al_final"] = c.execute(sa.text("SELECT COUNT(*) FROM tareas")).scalar()

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
    base = tmp_path / "migracion_tareas.db"
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


def test_ciclo_completo_de_la_migracion(tmp_path):
    r = _ciclo(tmp_path)

    # --- hacia delante ---------------------------------------------------------------
    assert "tareas" not in r["tablas_antes"] and "avisos" not in r["tablas_antes"]
    assert "tareas" in r["tablas_despues"] and "avisos" in r["tablas_despues"]

    assert r["columnas_tareas"] == [
        "asesor_id", "cerrada_en", "cerrada_por_id", "clave", "creada_en", "datos",
        "estado", "id", "lead_id", "motivo", "regla", "vence_el",
    ]
    assert r["columnas_avisos"] == [
        "clave", "creado_en", "datos", "id", "lead_id", "leido_en", "regla", "texto", "usuario_id",
    ]

    assert r["leads_tiene_dormido"] is True
    # Ninguno se marca dormido al migrar, por muy quieto que llevara.
    assert r["dormido_de_los_que_ya_estaban"] == [None]

    # --- idempotencia, que es para lo que existen los índices ------------------------
    assert r["tarea_repetida_entra"] is False, "la pasada de mañana duplicaría la tarea"
    assert r["otra_clave_entra"] is True
    assert r["dos_destinatarios_entran"] is True, "el líder no podría enterarse de lo mismo"
    assert r["aviso_repetido_entra"] is False, "la campana se llenaría del mismo aviso"

    # --- hacia atrás -----------------------------------------------------------------
    assert "tareas" not in r["tablas_tras_revertir"]
    assert "avisos" not in r["tablas_tras_revertir"]
    assert "dormido_desde" not in r["leads_tras_revertir"]
    # Lo del prospecto no se toca: la reversión borra trabajo nuestro, no hechos suyos.
    assert r["prospecto_tras_revertir"] == [["rosa@empresa.com", 72.0, 1]]
    assert r["actividades_tras_revertir"] == 1

    # --- y otra vez hacia delante ------------------------------------------------------
    assert "tareas" in r["tablas_al_final"] and "avisos" in r["tablas_al_final"]
    # Vuelven vacías: lo borrado por la reversión no se recupera, y el capítulo lo dice.
    assert r["tareas_al_final"] == 0
    assert r["tareas_antes_de_revertir"] == 2
    assert r["avisos_antes_de_revertir"] == 2

    assert r["diferencias"] == [], "el esquema migrado no es el de los modelos"
