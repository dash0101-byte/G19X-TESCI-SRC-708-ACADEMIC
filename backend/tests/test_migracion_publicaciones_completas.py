"""
La migración de publicaciones completas (`d5a8e2f41c73`), hacia delante y hacia atrás.

Como la del capítulo 25: Alembic de verdad, en un proceso aparte y sobre una SQLite en
fichero temporal. La suite nunca toca la base real.

Lo que tiene que cumplirse:

* Una campaña activa pasa a «activa»; una desactivada, a «cerrada» (no a «pausada», que sería
  prometer que se reanuda). Ninguna recibe opciones, responsable ni dirección de post.
* Después, el estado es obligatorio y nace «activa» si nadie lo dice.
* La tabla de visitas tiene solo publicación, día y número, y no admite dos filas del mismo
  día para la misma publicación.
* La reversión quita la tabla y las cuatro columnas y conserva las campañas; y se puede
  volver a migrar hacia delante.
* El esquema que deja la migración es el que declaran los modelos.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ANTERIOR = "b7e41c9d2f60"
ESTA = "d5a8e2f41c73"
NUEVAS = {"estado", "necesidades", "responsable_id", "url_del_post"}

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

command.upgrade(cfg, os.environ["ANTERIOR"])
with motor.begin() as c:
    for nombre, activa in [("Post activo", 1), ("Post desactivado", 0)]:
        c.execute(sa.text(
            "INSERT INTO campaigns (name, channel, budget, is_active, created_at, public_slug) "
            "VALUES (:n, 'LinkedIn', 0, :a, '2026-09-01 00:00:00', :s)"
        ), {"n": nombre, "a": activa, "s": nombre.replace(" ", "")[:22]})

command.upgrade(cfg, os.environ["ESTA"])
with motor.connect() as c:
    resultado["tras_migrar"] = [list(f) for f in c.execute(sa.text(
        "SELECT name, is_active, estado, necesidades, responsable_id, url_del_post FROM campaigns ORDER BY id"
    )).fetchall()]
resultado["columnas_campanas"] = columnas("campaigns")
resultado["columnas_visitas"] = columnas("visitas_de_publicacion")

with motor.begin() as c:
    c.execute(sa.text(
        "INSERT INTO campaigns (name, channel, budget, is_active, created_at, public_slug) "
        "VALUES ('Nueva', 'LinkedIn', 0, 1, '2026-09-01 00:00:00', 'nuevaSinEstado')"
    ))
    resultado["estado_por_defecto"] = c.execute(sa.text(
        "SELECT estado FROM campaigns WHERE name = 'Nueva'")).scalar()
    c.execute(sa.text("INSERT INTO visitas_de_publicacion (campaign_id, dia, visitas) VALUES (1, '2026-09-20', 3)"))
try:
    with motor.begin() as c:
        c.execute(sa.text("INSERT INTO visitas_de_publicacion (campaign_id, dia, visitas) VALUES (1, '2026-09-20', 1)"))
    resultado["rechaza_dia_repetido"] = False
except sa.exc.IntegrityError:
    resultado["rechaza_dia_repetido"] = True

# El esquema migrado frente a los modelos, para estas dos tablas.
import sys
sys.path.insert(0, os.environ["BACKEND"])
from app.core.database import Base
import app.models.entities  # noqa: F401
with motor.connect() as c:
    diferencias = compare_metadata(MigrationContext.configure(c), Base.metadata)
def _toca(d):
    texto = repr(d)
    return "campaigns" in texto or "visitas_de_publicacion" in texto
resultado["diferencias"] = [repr(d) for d in diferencias if _toca(d)]

command.downgrade(cfg, os.environ["ANTERIOR"])
resultado["columnas_tras_revertir"] = columnas("campaigns")
resultado["tablas_tras_revertir"] = sorted(sa.inspect(motor).get_table_names())
with motor.connect() as c:
    resultado["tras_revertir"] = [list(f) for f in c.execute(sa.text(
        "SELECT name, is_active FROM campaigns ORDER BY id")).fetchall()]

command.upgrade(cfg, "head")
with motor.connect() as c:
    resultado["tras_volver"] = [list(f) for f in c.execute(sa.text(
        "SELECT name, estado FROM campaigns ORDER BY id")).fetchall()]
print("__RESULTADO__" + json.dumps(resultado))
"""


def _ciclo(tmp_path: Path) -> dict:
    raiz = Path(__file__).resolve().parents[2]
    base = tmp_path / "migracion_publicaciones_completas.db"
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

    # Hacia delante: el estado sale de `is_active`, y nada más se inventa.
    assert r["tras_migrar"] == [
        ["Post activo", 1, "activa", None, None, None],
        ["Post desactivado", 0, "cerrada", None, None, None],
    ]
    assert NUEVAS <= set(r["columnas_campanas"])
    assert r["columnas_visitas"] == ["campaign_id", "dia", "visitas"]
    assert r["estado_por_defecto"] == "activa"
    assert r["rechaza_dia_repetido"] is True
    assert r["diferencias"] == [], "el esquema migrado no es el de los modelos"

    # Hacia atrás: fuera la tabla y las columnas, dentro las campañas y su `is_active`.
    assert not NUEVAS & set(r["columnas_tras_revertir"])
    assert "visitas_de_publicacion" not in r["tablas_tras_revertir"]
    assert r["tras_revertir"] == [["Post activo", 1], ["Post desactivado", 0], ["Nueva", 1]]

    # Y otra vez hacia delante.
    assert r["tras_volver"] == [["Post activo", "activa"], ["Post desactivado", "cerrada"], ["Nueva", "activa"]]
