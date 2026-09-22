"""
Concesiones que se cierran en producción (punto 23) y comprobación de salud real.

El explorador de la API describe cada ruta, cada parámetro y cada código de error del
sistema. Servido anónimamente en producción es un mapa completo de la superficie de
ataque, y no aporta nada: quien integra ya dispone de la especificación por otra vía.

Estas pruebas construyen una aplicación aparte por entorno en lugar de reutilizar la de
la suite, porque `docs_url` se decide al construir `FastAPI(...)` y no se puede cambiar
después.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

CLAVE_VALIDA = "clave-larga-y-valida-para-construir-la-app-en-estas-pruebas-de-entorno"

# La decisión se toma al construir `FastAPI(...)`, así que comprobarla exige levantar la
# aplicación con otro `ENVIRONMENT`. Se hace en un subproceso y no con `importlib.reload`
# porque recargar `app.core.config` fabrica un `settings` nuevo que los demás módulos ya
# cargados no comparten: el resto de la suite empezaba a fallar por arrastre.
_SONDA = """
import json, os, sys

# En entornos endurecidos la aplicacion ya NO crea el esquema al arrancar: lo gobierna
# Alembic y el arranque se limita a comprobar que la base este en la ultima revision. La
# sonda reproduce por tanto un despliegue real: primero migra, despues levanta el servicio.
# Sin este paso el arranque aborta, que es exactamente lo que debe hacer.
from alembic import command
from alembic.config import Config

_cfg = Config()
_cfg.set_main_option("script_location", os.environ["ALEMBIC_DIR"])
_cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
command.upgrade(_cfg, "head")

from fastapi.testclient import TestClient
from app.main import DOCS_ENABLED, app

with TestClient(app) as cliente:
    resultado = {
        "docs_enabled": DOCS_ENABLED,
        "docs": cliente.get("/docs").status_code,
        "redoc": cliente.get("/redoc").status_code,
        "openapi": cliente.get("/api/v1/openapi.json").status_code,
        "raiz": cliente.get("/", headers={"accept": "application/json"}).json(),
    }
print("__RESULTADO__" + json.dumps(resultado))
"""


def _sondear_entorno(entorno: str, tmp_path: Path) -> dict:
    raiz = Path(__file__).resolve().parents[2]
    # Base en fichero y no en memoria: Alembic abre su propia conexion, y con "sqlite://"
    # esa conexion veria una base distinta y vacia. El fichero vive en el directorio
    # temporal de la prueba, asi que sigue sin tocarse ninguna base real.
    base = tmp_path / f"sonda_{entorno}.db"
    entorno_proceso = {
        **os.environ,
        "ENVIRONMENT": entorno,
        "SECRET_KEY": CLAVE_VALIDA,
        "DATABASE_URL": f"sqlite:///{base.as_posix()}",
        "ALEMBIC_DIR": str(raiz / "backend" / "alembic"),
        "PYTHONPATH": str(raiz / "backend") + os.pathsep + str(raiz),
        "PYTHONIOENCODING": "utf-8",
    }
    proceso = subprocess.run(  # noqa: S603  intérprete propio y script literal, sin entrada externa
        [sys.executable, "-c", _SONDA],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(raiz),
        env=entorno_proceso,
        timeout=180,
    )
    assert proceso.returncode == 0, proceso.stderr
    linea = next(
        salida for salida in proceso.stdout.splitlines()
        if salida.startswith("__RESULTADO__")
    )
    return json.loads(linea.removeprefix("__RESULTADO__"))


@pytest.mark.parametrize("entorno", ["production", "staging", "prod"])
def test_la_documentacion_no_se_publica_en_entornos_endurecidos(entorno, tmp_path):
    resultado = _sondear_entorno(entorno, tmp_path)
    assert resultado["docs_enabled"] is False
    assert resultado["docs"] == 404
    assert resultado["redoc"] == 404
    assert resultado["openapi"] == 404


@pytest.mark.parametrize("entorno", ["development", "local"])
def test_la_documentacion_sigue_disponible_fuera_de_produccion(entorno, tmp_path):
    """Cerrarla en producción no debe estorbar el desarrollo ni la revisión académica."""
    resultado = _sondear_entorno(entorno, tmp_path)
    assert resultado["docs_enabled"] is True
    assert resultado["docs"] == 200
    assert resultado["openapi"] == 200


def test_la_raiz_no_anuncia_una_url_de_documentacion_inexistente(tmp_path):
    """Publicitar `/docs` cuando devuelve 404 sería una pista falsa para el integrador."""
    resultado = _sondear_entorno("production", tmp_path)
    assert resultado["raiz"]["docs_url"] is None
    assert resultado["raiz"]["environment"] == "production"


# ==============================================================================
# Comprobación de salud real
# ==============================================================================

def test_el_health_consulta_de_verdad_la_base_de_datos(client):
    """
    Devolvía `{"status": "healthy", "database": "connected"}` como constante: seguía
    diciendo "sano" con la base caída, así que el HEALTHCHECK del contenedor y cualquier
    balanceador delante mantenían la instancia en rotación.
    """
    respuesta = client.get("/health")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "healthy"
    assert cuerpo["database"] == "connected"
    assert "ml_engine" in cuerpo


def test_el_health_responde_503_si_la_base_no_contesta(client, monkeypatch):
    """Con la base inalcanzable el servicio debe declararse enfermo, no sano."""
    import app.main as main_module

    class MotorCaido:
        def connect(self):
            raise RuntimeError("no se pudo abrir la conexión con la base de datos")

    monkeypatch.setattr(main_module, "engine", MotorCaido())

    respuesta = client.get("/health")
    assert respuesta.status_code == 503
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "unhealthy"
    assert cuerpo["database"] == "unreachable"


def test_el_health_no_filtra_el_detalle_del_fallo(client, monkeypatch):
    """El mensaje del error va al log; la respuesta pública no expone cadenas de conexión."""
    import app.main as main_module

    class MotorCaido:
        def connect(self):
            raise RuntimeError("postgresql://usuario:contrasena-secreta@10.0.0.5:5432/prod")

    monkeypatch.setattr(main_module, "engine", MotorCaido())

    respuesta = client.get("/health")
    assert respuesta.status_code == 503
    assert "contrasena-secreta" not in respuesta.text
    assert "10.0.0.5" not in respuesta.text
