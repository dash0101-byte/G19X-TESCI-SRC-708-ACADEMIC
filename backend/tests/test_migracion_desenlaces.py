"""
La migración del desenlace (`c1d9f4b72a08`), ida y vuelta.

Como las de los capítulos 25 a 28: Alembic de verdad, en un proceso aparte y sobre una
SQLite en fichero temporal. La suite nunca toca la base real.

Lo que tiene que cumplirse:

* Aparece `desenlaces` con sus columnas, y `leads` no cambia: el desenlace acompaña a la
  etapa, no la sustituye.
* Los prospectos que ya estaban cerrados **no** reciben un desenlace inventado. El motivo
  de un cierre anterior a que la lista existiera no está en ninguna parte, y escribir «otro
  motivo» en todos ellos llenaría el panel de una respuesta que nadie dio.
* El índice único **impide** dos desenlaces del mismo prospecto: corregir un cierre es
  reescribir la fila, y dos filas obligarían a decidir cuál es «el» desenlace cada vez que
  el panel o el extractor preguntan.
* Borrar al prospecto se lleva su desenlace (`CASCADE`): el derecho de supresión no admite
  un rincón donde quede constancia de que existió.
* Borrar la instantánea a la que apunta **no** se lo lleva (`SET NULL`): el desenlace sigue
  siendo cierto y lo que se pierde es su ejemplo de entrenamiento, que es lo que el
  contador tiene que poder contar aparte.
* Al revertir desaparece la tabla y **la etapa del prospecto sigue ahí**: el sistema vuelve
  a saber cuántos se ganaron y vuelve a no saber por qué.
* Se puede volver a migrar hacia delante, y al final de la cadena el esquema es el de los
  modelos.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ANTERIOR = "a8d2f16c5b03"
ESTA = "c1d9f4b72a08"

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

AHORA = "2026-09-24 08:00:00"
HOY = "2026-09-24"

# --- antes: dos prospectos, uno ya cerrado, con su instantanea de entrada ----------------
command.upgrade(cfg, os.environ["ANTERIOR"])
with motor.begin() as c:
    c.execute(sa.text("PRAGMA foreign_keys = ON"))
    c.execute(sa.text(
        "INSERT INTO users (email, hashed_password, full_name, role, is_active, token_version, "
        "is_sales_rep, must_change_password, password_changed_at, created_at, updated_at) "
        "VALUES ('asesora@plurione.com', '!x', 'Asesora', 'Commercial_Executive', 1, 0, 1, 0, :t, :t, :t)"
    ), {"t": AHORA})
    for nombre, correo, etapa in [
        ("Rosa", "rosa@empresa.com", "WON"),
        ("Hugo", "hugo@empresa.com", "NEGOTIATION"),
    ]:
        c.execute(sa.text(
            "INSERT INTO leads (first_name, last_name, email, country, source, status, "
            "qualification_status, current_score, score_category, conversion_probability, "
            "last_score_update, last_activity_at, created_at, updated_at, assigned_rep_id) "
            "VALUES (:n, 'Lima', :e, 'México', 'LinkedIn', :s, 'SQL', 72.0, 'HOT', 0.5, "
            ":t, :t, :t, :t, 1)"
        ), {"n": nombre, "e": correo, "s": etapa, "t": AHORA})
    c.execute(sa.text(
        "INSERT INTO score_histories (lead_id, score, score_category, model_version, "
        "ml_probability, heuristic_score, decay_factor, feature_snapshot, calculated_at) "
        "VALUES (1, 50.0, 'WARM', 'v1', 0.5, 50.0, 1.0, '{\"version_del_vector\": 2}', :t)"
    ), {"t": AHORA})
resultado["tablas_antes"] = tablas()

# --- hacia delante -----------------------------------------------------------------------
command.upgrade(cfg, os.environ["ESTA"])
resultado["tablas_despues"] = tablas()
resultado["columnas"] = columnas("desenlaces")
resultado["columnas_leads"] = columnas("leads")
with motor.connect() as c:
    # Nadie recibe un desenlace inventado, ni siquiera el que ya estaba en WON.
    resultado["desenlaces_tras_migrar"] = c.execute(
        sa.text("SELECT COUNT(*) FROM desenlaces")).scalar()
    resultado["etapas_tras_migrar"] = [
        f[0] for f in c.execute(sa.text("SELECT status FROM leads ORDER BY id")).fetchall()
    ]

def inserta(lead_id, resultado_cierre="ganado", motivo="precio", tramo="hasta_100k", historial=1):
    with motor.begin() as c:
        c.execute(sa.text("PRAGMA foreign_keys = ON"))
        c.execute(sa.text(
            "INSERT INTO desenlaces (lead_id, resultado, motivo, cerrado_el, tramo, "
            "score_al_cierre, categoria_al_cierre, score_history_id, version_del_vector, "
            "registrado_en, registrado_por_id) "
            "VALUES (:l, :r, :m, :d, :tr, 72.0, 'HOT', :h, 2, :t, 1)"
        ), {"l": lead_id, "r": resultado_cierre, "m": motivo, "d": HOY, "tr": tramo,
            "h": historial, "t": AHORA})

inserta(1)
try:
    inserta(1, motivo="plazo")
    resultado["segundo_desenlace_entra"] = True
except sa.exc.IntegrityError:
    resultado["segundo_desenlace_entra"] = False

# La instantanea se va: el desenlace sigue, sin ejemplo.
with motor.begin() as c:
    c.execute(sa.text("PRAGMA foreign_keys = ON"))
    c.execute(sa.text("DELETE FROM score_histories WHERE id = 1"))
with motor.connect() as c:
    resultado["tras_borrar_la_instantanea"] = [
        list(f) for f in c.execute(sa.text(
            "SELECT lead_id, score_history_id FROM desenlaces")).fetchall()
    ]

# El prospecto se va: el desenlace se va con el.
inserta(2, resultado_cierre="perdido", motivo="no_contesto", tramo=None, historial=None)
with motor.begin() as c:
    c.execute(sa.text("PRAGMA foreign_keys = ON"))
    c.execute(sa.text("DELETE FROM leads WHERE id = 2"))
with motor.connect() as c:
    resultado["tras_suprimir_al_prospecto"] = c.execute(
        sa.text("SELECT COUNT(*) FROM desenlaces WHERE lead_id = 2")).scalar()
    resultado["desenlaces_antes_de_revertir"] = c.execute(
        sa.text("SELECT COUNT(*) FROM desenlaces")).scalar()

# --- hacia atras -------------------------------------------------------------------------
command.downgrade(cfg, os.environ["ANTERIOR"])
resultado["tablas_tras_revertir"] = tablas()
with motor.connect() as c:
    resultado["prospecto_tras_revertir"] = [
        list(f) for f in c.execute(sa.text(
            "SELECT email, status, current_score FROM leads ORDER BY id")).fetchall()
    ]

# --- y otra vez hacia delante, hasta el final --------------------------------------------
command.upgrade(cfg, "head")
resultado["tablas_al_final"] = tablas()
with motor.connect() as c:
    resultado["desenlaces_al_final"] = c.execute(
        sa.text("SELECT COUNT(*) FROM desenlaces")).scalar()

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
    base = tmp_path / "migracion_desenlaces.db"
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
    assert "desenlaces" not in r["tablas_antes"]
    assert "desenlaces" in r["tablas_despues"]
    assert r["columnas"] == [
        "categoria_al_cierre", "cerrado_el", "id", "lead_id", "motivo", "registrado_en",
        "registrado_por_id", "resultado", "score_al_cierre", "score_history_id", "tramo",
        "version_del_vector",
    ]
    # `leads` no gana ni pierde nada: el desenlace acompaña a la etapa, no la sustituye.
    assert "status" in r["columnas_leads"]

    # Nadie recibe un motivo inventado al migrar, ni siquiera el que ya estaba ganado.
    assert r["desenlaces_tras_migrar"] == 0
    assert r["etapas_tras_migrar"] == ["WON", "NEGOTIATION"]

    # --- el índice único, que es lo que hace que corregir sea reescribir ---------------
    assert r["segundo_desenlace_entra"] is False, (
        "dos desenlaces del mismo prospecto obligarían a decidir cuál es «el» desenlace"
    )

    # --- las dos claves foráneas, cada una con su comportamiento ----------------------
    # La instantánea se borra y el desenlace sigue, sin ejemplo: es lo que el contador del
    # reentrenamiento tiene que poder contar aparte.
    assert r["tras_borrar_la_instantanea"] == [[1, None]]
    # El prospecto se borra y su desenlace se va con él: el derecho de supresión no admite
    # un rincón donde quede constancia de que existió.
    assert r["tras_suprimir_al_prospecto"] == 0

    # --- hacia atrás -----------------------------------------------------------------
    assert "desenlaces" not in r["tablas_tras_revertir"]
    # Se pierde el porqué; no se pierde el qué. La etapa vive en `leads` y no se toca.
    assert r["prospecto_tras_revertir"] == [["rosa@empresa.com", "WON", 72.0]]

    # --- y otra vez hacia delante ------------------------------------------------------
    assert "desenlaces" in r["tablas_al_final"]
    # Vuelve vacía: lo borrado por la reversión no se recupera, y la migración lo dice.
    assert r["desenlaces_al_final"] == 0
    assert r["desenlaces_antes_de_revertir"] == 1

    assert r["diferencias"] == [], "el esquema migrado no es el de los modelos"
