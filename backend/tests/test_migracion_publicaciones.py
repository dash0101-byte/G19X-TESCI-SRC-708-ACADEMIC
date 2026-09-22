"""
La migración de publicaciones (`b7e41c9d2f60`), hacia delante y hacia atrás.

Se ejecuta con Alembic de verdad, en un proceso aparte y sobre una base SQLite en fichero
temporal: `env.py` toma la URL de `settings`, y cambiarla dentro del proceso de la suite
dejaría al resto de pruebas mirando otra base. La suite nunca toca la base real.

Lo que tiene que cumplirse:

* Las campañas que ya existían reciben cada una su slug, todos distintos y con la forma
  del generador, sin perder ninguna fila ni ningún dato.
* Después, la base no admite una campaña sin slug ni dos con el mismo.
* La reversión quita las tres columnas y el índice y conserva las campañas.
* Se puede volver a migrar hacia delante tras revertir.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ANTERIOR = "e3a9c41d7b25"
ESTA = "b7e41c9d2f60"

_SONDA = r"""
import json, os, re
from alembic import command
from alembic.config import Config
import sqlalchemy as sa

url = os.environ["DATABASE_URL"]
cfg = Config()
cfg.set_main_option("script_location", os.environ["ALEMBIC_DIR"])
cfg.set_main_option("sqlalchemy.url", url)
motor = sa.create_engine(url)
resultado = {}

def columnas():
    return {c["name"] for c in sa.inspect(motor).get_columns("campaigns")}

def indices():
    return {i["name"] for i in sa.inspect(motor).get_indexes("campaigns")}

command.upgrade(cfg, os.environ["ANTERIOR"])
with motor.begin() as c:
    for nombre, canal in [("Q3 Tech Talent Summit", "LinkedIn Ads"), ("Webinar IA", "Webinar"), ("SEO", "Organic Search")]:
        c.execute(sa.text(
            "INSERT INTO campaigns (name, channel, budget, is_active, created_at) "
            "VALUES (:n, :c, 1000.0, 1, '2026-09-01 00:00:00')"
        ), {"n": nombre, "c": canal})

command.upgrade(cfg, os.environ["ESTA"])
with motor.connect() as c:
    filas = c.execute(sa.text(
        "SELECT name, channel, budget, public_slug, description, target_audience FROM campaigns ORDER BY id"
    )).fetchall()
resultado["tras_migrar"] = [list(f) for f in filas]
resultado["columnas_tras_migrar"] = sorted(columnas())
resultado["indices_tras_migrar"] = sorted(indices())

def rechaza(sql, parametros):
    try:
        with motor.begin() as c:
            c.execute(sa.text(sql), parametros)
    except sa.exc.IntegrityError:
        return True
    return False

insertar = ("INSERT INTO campaigns (name, channel, budget, is_active, created_at, public_slug) "
            "VALUES ('x', 'LinkedIn', 0, 1, '2026-09-01 00:00:00', :s)")
resultado["rechaza_repetido"] = rechaza(insertar, {"s": filas[0][3]})
resultado["rechaza_sin_slug"] = rechaza(insertar, {"s": None})

command.downgrade(cfg, os.environ["ANTERIOR"])
with motor.connect() as c:
    resultado["tras_revertir"] = [list(f) for f in c.execute(sa.text(
        "SELECT name, channel, budget FROM campaigns ORDER BY id")).fetchall()]
resultado["columnas_tras_revertir"] = sorted(columnas())
resultado["indices_tras_revertir"] = sorted(indices())

command.upgrade(cfg, "head")
with motor.connect() as c:
    resultado["slugs_tras_volver"] = [f[0] for f in c.execute(sa.text(
        "SELECT public_slug FROM campaigns ORDER BY id")).fetchall()]
print("__RESULTADO__" + json.dumps(resultado))
"""


def _ciclo(tmp_path: Path) -> dict:
    raiz = Path(__file__).resolve().parents[2]
    base = tmp_path / "migracion_publicaciones.db"
    entorno = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{base.as_posix()}",
        "ALEMBIC_DIR": str(raiz / "backend" / "alembic"),
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

    # Hacia delante: cada campaña existente con su slug, sin tocar lo demás.
    filas = r["tras_migrar"]
    assert [f[:3] for f in filas] == [
        ["Q3 Tech Talent Summit", "LinkedIn Ads", 1000.0],
        ["Webinar IA", "Webinar", 1000.0],
        ["SEO", "Organic Search", 1000.0],
    ]
    slugs = [f[3] for f in filas]
    assert all(s and len(s) == 22 for s in slugs)
    assert len(set(slugs)) == 3
    assert all(f[4] is None and f[5] is None for f in filas), "no se inventa descripción ni público"
    assert {"description", "target_audience", "public_slug"} <= set(r["columnas_tras_migrar"])
    assert "uq_campaigns_public_slug" in r["indices_tras_migrar"]
    assert r["rechaza_repetido"] is True
    assert r["rechaza_sin_slug"] is True

    # Hacia atrás: fuera las columnas y el índice, dentro las campañas.
    assert r["tras_revertir"] == [f[:3] for f in filas]
    assert not {"description", "target_audience", "public_slug"} & set(r["columnas_tras_revertir"])
    assert "uq_campaigns_public_slug" not in r["indices_tras_revertir"]

    # Y otra vez hacia delante. Los slugs son nuevos: revertir rompe los enlaces publicados,
    # como advierte la migración.
    nuevos = r["slugs_tras_volver"]
    assert len(set(nuevos)) == 3
    assert not set(nuevos) & set(slugs)
