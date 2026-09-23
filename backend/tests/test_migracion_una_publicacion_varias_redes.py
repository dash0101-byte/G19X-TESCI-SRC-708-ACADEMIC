"""
La migración de «una publicación, varias redes» (`f3c7a90b12e4`), ida y vuelta.

Como las de los capítulos 25 y 26: Alembic de verdad, en un proceso aparte y sobre una
SQLite en fichero temporal. La suite nunca toca la base real.

Lo que tiene que cumplirse:

* `campaigns` gana `redes`, vacío en todas las que ya existen: ninguna cambia de
  comportamiento al migrar.
* `visitas_de_publicacion` gana `red` **dentro de la clave**. Las visitas que ya estaban
  contadas pasan a `sin_red` —se contaron antes de que hubiera redes— y **no se pierde
  ninguna**.
* Con la clave nueva caben dos redes el mismo día, y sigue sin caber dos veces la misma.
* La reversión **suma** las redes de cada día: el total diario se conserva y solo se pierde
  el reparto. Las campañas y sus visitas siguen ahí.
* Se puede volver a migrar hacia delante, y al final de la cadena el esquema es el de los
  modelos.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ANTERIOR = "d5a8e2f41c73"
ESTA = "f3c7a90b12e4"

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

# --- antes: una publicación con visitas contadas sin red ---------------------------------
command.upgrade(cfg, os.environ["ANTERIOR"])
with motor.begin() as c:
    c.execute(sa.text(
        "INSERT INTO campaigns (name, channel, budget, is_active, created_at, public_slug, estado) "
        "VALUES ('Post con visitas', 'LinkedIn', 0, 1, '2026-09-01 00:00:00', 'conVisitas', 'activa')"
    ))
    for dia, visitas in [("2026-09-20", 7), ("2026-09-21", 5)]:
        c.execute(sa.text(
            "INSERT INTO visitas_de_publicacion (campaign_id, dia, visitas) VALUES (1, :d, :v)"
        ), {"d": dia, "v": visitas})
    resultado["visitas_antes"] = c.execute(sa.text(
        "SELECT SUM(visitas) FROM visitas_de_publicacion")).scalar()

# --- hacia delante -----------------------------------------------------------------------
command.upgrade(cfg, os.environ["ESTA"])
resultado["columnas_campanas"] = columnas("campaigns")
resultado["columnas_visitas"] = columnas("visitas_de_publicacion")
with motor.connect() as c:
    resultado["redes_de_las_campanas"] = [
        list(f) for f in c.execute(sa.text("SELECT name, redes FROM campaigns ORDER BY id")).fetchall()
    ]
    resultado["visitas_tras_migrar"] = [
        list(f) for f in c.execute(sa.text(
            "SELECT dia, red, visitas FROM visitas_de_publicacion ORDER BY dia, red")).fetchall()
    ]
    resultado["clave_visitas"] = sa.inspect(motor).get_pk_constraint(
        "visitas_de_publicacion")["constrained_columns"]

# Dos redes el mismo día, sí. La misma red dos veces, no.
with motor.begin() as c:
    c.execute(sa.text(
        "INSERT INTO visitas_de_publicacion (campaign_id, dia, red, visitas) "
        "VALUES (1, '2026-09-20', 'whatsapp', 4)"
    ))
resultado["admite_dos_redes_el_mismo_dia"] = True
try:
    with motor.begin() as c:
        c.execute(sa.text(
            "INSERT INTO visitas_de_publicacion (campaign_id, dia, red, visitas) "
            "VALUES (1, '2026-09-20', 'whatsapp', 1)"
        ))
    resultado["rechaza_la_misma_red_repetida"] = False
except sa.exc.IntegrityError:
    resultado["rechaza_la_misma_red_repetida"] = True

# El valor por defecto: una fila escrita sin decir la red.
with motor.begin() as c:
    c.execute(sa.text(
        "INSERT INTO visitas_de_publicacion (campaign_id, dia, visitas) VALUES (1, '2026-09-22', 2)"
    ))
    resultado["red_por_defecto"] = c.execute(sa.text(
        "SELECT red FROM visitas_de_publicacion WHERE dia = '2026-09-22'")).scalar()
    resultado["visitas_totales_antes_de_revertir"] = c.execute(sa.text(
        "SELECT SUM(visitas) FROM visitas_de_publicacion")).scalar()

# --- hacia atrás -------------------------------------------------------------------------
command.downgrade(cfg, os.environ["ANTERIOR"])
resultado["columnas_campanas_tras_revertir"] = columnas("campaigns")
resultado["columnas_visitas_tras_revertir"] = columnas("visitas_de_publicacion")
with motor.connect() as c:
    resultado["visitas_tras_revertir"] = [
        list(f) for f in c.execute(sa.text(
            "SELECT dia, visitas FROM visitas_de_publicacion ORDER BY dia")).fetchall()
    ]
    resultado["campanas_tras_revertir"] = [
        list(f) for f in c.execute(sa.text("SELECT name, estado FROM campaigns ORDER BY id")).fetchall()
    ]

# --- y otra vez hacia delante, hasta el final --------------------------------------------
command.upgrade(cfg, "head")
with motor.connect() as c:
    resultado["visitas_tras_volver"] = [
        list(f) for f in c.execute(sa.text(
            "SELECT dia, red, visitas FROM visitas_de_publicacion ORDER BY dia")).fetchall()
    ]

import sys
sys.path.insert(0, os.environ["BACKEND"])
from app.core.database import Base
import app.models.entities  # noqa: F401
with motor.connect() as c:
    diferencias = compare_metadata(MigrationContext.configure(c), Base.metadata)
resultado["diferencias"] = [
    repr(d) for d in diferencias
    if "campaigns" in repr(d) or "visitas_de_publicacion" in repr(d)
]
print("__RESULTADO__" + json.dumps(resultado))
"""


def _ciclo(tmp_path: Path) -> dict:
    raiz = Path(__file__).resolve().parents[2]
    base = tmp_path / "migracion_redes.db"
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
    assert "redes" in r["columnas_campanas"]
    # Vacío: las que ya existen siguen con las redes de siempre.
    assert r["redes_de_las_campanas"] == [["Post con visitas", None]]

    assert r["columnas_visitas"] == ["campaign_id", "dia", "red", "visitas"]
    assert r["clave_visitas"] == ["campaign_id", "dia", "red"]
    # Las visitas de antes no saben de dónde vinieron: se quedan en «sin red», y no se
    # pierde ninguna.
    assert r["visitas_tras_migrar"] == [
        ["2026-09-20", "sin_red", 7],
        ["2026-09-21", "sin_red", 5],
    ]
    assert sum(f[2] for f in r["visitas_tras_migrar"]) == r["visitas_antes"]

    assert r["admite_dos_redes_el_mismo_dia"] is True
    assert r["rechaza_la_misma_red_repetida"] is True
    assert r["red_por_defecto"] == "sin_red"

    # --- hacia atrás -----------------------------------------------------------------
    assert "redes" not in r["columnas_campanas_tras_revertir"]
    assert r["columnas_visitas_tras_revertir"] == ["campaign_id", "dia", "visitas"]
    # El 20 tenía 7 sin red y 4 de WhatsApp: al revertir se suman en una sola fila de 11.
    # Se pierde el reparto por red, nunca el total.
    assert r["visitas_tras_revertir"] == [
        ["2026-09-20", 11],
        ["2026-09-21", 5],
        ["2026-09-22", 2],
    ]
    assert sum(f[1] for f in r["visitas_tras_revertir"]) == r["visitas_totales_antes_de_revertir"]
    # Las campañas y sus estados no se tocan.
    assert r["campanas_tras_revertir"] == [["Post con visitas", "activa"]]

    # --- y otra vez hacia delante ------------------------------------------------------
    assert r["visitas_tras_volver"] == [
        ["2026-09-20", "sin_red", 11],
        ["2026-09-21", "sin_red", 5],
        ["2026-09-22", "sin_red", 2],
    ]
    assert r["diferencias"] == [], "el esquema migrado no es el de los modelos"
