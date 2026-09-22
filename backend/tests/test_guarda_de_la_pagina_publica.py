"""
La guarda de la página pública existe, pasa, y el CI la ejecuta donde tiene que ejecutarla.

La guarda (`scripts/guarda_de_la_pagina_publica.py`) es un paso con nombre propio del CI. Un
paso se borra sin que nada falle: el CI sigue en verde, solo que ya no comprueba lo que
comprobaba. Esta prueba es lo que falla entonces. Y ejecuta la guarda también aquí, para
que quien corre la suite en local no tenga que acordarse de lanzarla aparte.
"""
import os
import subprocess
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[2]
GUARDA = "scripts/guarda_de_la_pagina_publica.py"


def _pasos_de_las_pruebas():
    flujo = yaml.safe_load((RAIZ / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    return flujo["jobs"]["pruebas"]["steps"]


def test_el_ci_ejecuta_la_guarda_con_el_modelo_y_antes_de_la_suite():
    """
    Después de descargar el artefacto —sin él no hay contra qué medir la alineación— y antes
    de la suite, para que el motivo de un fallo sea el título del paso.
    """
    pasos = _pasos_de_las_pruebas()
    orden = {
        "modelo": next(i for i, p in enumerate(pasos) if (p.get("with") or {}).get("name") == "modelo-entrenado"),
        "guarda": next(i for i, p in enumerate(pasos) if GUARDA in str(p.get("run", ""))),
        "suite": next(i for i, p in enumerate(pasos) if "pytest" in str(p.get("run", ""))),
    }

    assert orden["modelo"] < orden["guarda"] < orden["suite"]


def test_la_guarda_pasa_con_el_codigo_de_hoy():
    """Una guarda que falla con el código sano no guarda nada: se acaba desactivando."""
    entorno = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    resultado = subprocess.run(  # noqa: S603  intérprete propio y script del repositorio, sin entrada externa
        [sys.executable, GUARDA], cwd=RAIZ, capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=entorno, timeout=300,
    )

    assert resultado.returncode == 0, resultado.stdout[-2000:] + resultado.stderr[-2000:]
    assert "conserva sus defensas" in resultado.stdout
