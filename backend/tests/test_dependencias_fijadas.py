"""
R-2: lo que se instala es lo que está escrito, byte a byte.

`requirements.txt` declara rangos (`fastapi>=0.110,<1`). Dos construcciones de la misma
imagen con un mes de diferencia instalaban versiones distintas, y la suite, el
entrenamiento y `pip-audit` corrían cada uno sobre lo que el índice sirviera ese día. El
entorno local de quien escribe esto difería del lock en once de noventa y tres paquetes
el día que se generó.

Estas pruebas no instalan nada. Comprueban que los locks estén bien formados y sean
coherentes entre sí y con los rangos, que la imagen y el CI instalen desde ellos, y que
el lock llegue de verdad al contexto de construcción de la imagen. Que lo instalado
coincida con lo fijado lo comprueba `scripts/comprobar_instalado.py`, en el CI y dentro
de la propia imagen.
"""
import fnmatch
import re
from pathlib import Path

import pytest
import yaml
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from scripts.comprobar_instalado import aplicables, comparar, leer_lock

RAIZ = Path(__file__).resolve().parents[2]
PROD = leer_lock((RAIZ / "backend/requirements.lock").read_text(encoding="utf-8"))
DEV = leer_lock((RAIZ / "backend/requirements-dev.lock").read_text(encoding="utf-8"))

# El entorno de la imagen: python:3.13-slim sobre Debian, x86_64.
LINUX = {
    "sys_platform": "linux",
    "platform_system": "Linux",
    "platform_machine": "x86_64",
    "os_name": "posix",
    "implementation_name": "cpython",
    "platform_python_implementation": "CPython",
    "python_version": "3.13",
    "python_full_version": "3.13.0",
}


def _directos(ruta: Path):
    requisitos = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.split("#", 1)[0].strip()
        if not linea:
            continue
        if linea.startswith("-r "):
            requisitos.extend(_directos(ruta.parent / linea[3:].strip()))
            continue
        requisitos.append(Requirement(linea))
    return requisitos


def _aplica_en_linux(fijado) -> bool:
    return fijado.marcador is None or Requirement(f"x; {fijado.marcador}").marker.evaluate(LINUX)


# ==============================================================================
# Los locks
# ==============================================================================

@pytest.mark.parametrize("nombre, lock", [("produccion", PROD), ("desarrollo", DEV)])
def test_cada_entrada_tiene_version_exacta_y_huella(nombre, lock):
    assert len(lock) > 40, nombre
    for paquete, fijado in lock.items():
        assert fijado.hashes, f"{paquete} sin huella en el lock de {nombre}"
        assert all(re.fullmatch(r"[0-9a-f]{64}", h) for h in fijado.hashes), paquete


def test_leer_un_lock_rechaza_lo_que_no_es_un_lock():
    """Un rango colado en el lock se convertiría en «lo último que haya» sin que nada lo dijera."""
    with pytest.raises(ValueError):
        leer_lock("fastapi>=0.110 \\\n    --hash=sha256:" + "0" * 64 + "\n")


@pytest.mark.parametrize(
    "requisitos, lock",
    [("backend/requirements.txt", PROD), ("backend/requirements-dev.txt", DEV)],
)
def test_el_lock_satisface_los_rangos_declarados(requisitos, lock):
    for req in _directos(RAIZ / requisitos):
        nombre = canonicalize_name(req.name)
        assert nombre in lock, f"{req.name} está en {requisitos} y no en su lock: regenérelo"
        assert req.specifier.contains(lock[nombre].version, prereleases=True), (
            f"{req.name}=={lock[nombre].version} no cumple '{req.specifier}' de {requisitos}"
        )


def test_las_pruebas_corren_sobre_las_mismas_versiones_que_produccion():
    """
    El lock de desarrollo se compila con el de producción como restricción. Sin eso, la
    suite podría pasar sobre un FastAPI distinto del que lleva la imagen.
    """
    for nombre, fijado in PROD.items():
        assert nombre in DEV, nombre
        assert DEV[nombre].version == fijado.version, nombre
        assert set(DEV[nombre].hashes) == set(fijado.hashes), nombre


def test_produccion_no_lleva_herramientas_de_desarrollo():
    for herramienta in ("pytest", "pytest-cov", "ruff", "pip-audit", "coverage"):
        assert herramienta not in PROD


def test_el_lock_de_produccion_resuelve_para_la_imagen_linux_y_no_para_quien_lo_genero():
    """
    Se generó en Windows. Un `pip-compile` corriente habría resuelto para Windows: sin
    `uvloop` —que uvicorn[standard] solo pide fuera de Windows— y con `tzdata`, que solo
    pide en Windows. Por eso se compila con `--universal` y los marcadores quedan escritos.
    """
    en_linux = {nombre for nombre, fijado in PROD.items() if _aplica_en_linux(fijado)}
    assert "uvloop" in en_linux
    assert "tzdata" not in en_linux
    assert "psycopg2-binary" in en_linux


def test_la_comparacion_detecta_lo_que_falta_lo_distinto_y_lo_que_sobra():
    esperado = {"fastapi": "0.141.1", "uvloop": "0.22.1"}
    presente = {"fastapi": "0.141.0", "pytest": "9.1.1", "pip": "26.2.1"}
    problemas = comparar(esperado, presente, ignorar=["pip"])
    assert any(p.startswith("distinto") and "fastapi" in p for p in problemas)
    assert any(p.startswith("falta") and "uvloop" in p for p in problemas)
    assert any(p.startswith("sobra") and "pytest" in p for p in problemas)
    assert not any("pip==" in p for p in problemas)
    assert comparar({"fastapi": "1"}, {"fastapi": "1"}) == []


def test_el_modelo_versionado_se_entreno_con_las_versiones_del_lock():
    """
    El `.joblib` es un pickle de objetos de scikit-learn. Cargarlo con otra versión da un
    aviso; entre versiones menores puede dar predicciones distintas sin ningún error. Fijar
    las dependencias no sirve de nada si el artefacto que se despliega salió de otro
    entorno, que es exactamente como estaba: entrenado con scikit-learn 1.9.0 y servido
    con lo que resolviera el rango ese día.
    """
    import hashlib

    from model_registry import entrada_de_artefacto

    modelos = RAIZ / "ml_pipeline" / "models"
    sha = hashlib.sha256((modelos / "lead_scorer_model.joblib").read_bytes()).hexdigest()
    entrada = entrada_de_artefacto(sha, str(modelos / "registry.json"))
    assert entrada is not None and entrada.get("publicado"), "el artefacto versionado no está registrado"

    entorno = entrada.get("entorno") or {}
    for paquete in ("scikit-learn", "numpy", "pandas", "joblib"):
        assert entorno.get(paquete) == PROD[paquete].version, (
            f"El artefacto se entrenó con {paquete} {entorno.get(paquete)} y el lock fija "
            f"{PROD[paquete].version}: reentrénelo en un entorno instalado desde el lock."
        )


def test_los_marcadores_se_evaluan_en_la_plataforma_que_comprueba():
    lock = leer_lock(
        "uvloop==0.22.1 ; sys_platform != 'win32' \\\n    --hash=sha256:" + "a" * 64 + "\n"
        "tzdata==2026.3 ; sys_platform == 'win32' \\\n    --hash=sha256:" + "b" * 64 + "\n"
    )
    import sys

    esperado = aplicables(lock)
    assert ("uvloop" in esperado) == (sys.platform != "win32")
    assert ("tzdata" in esperado) == (sys.platform == "win32")


# ==============================================================================
# Quién instala desde dónde
# ==============================================================================

def _patrones_dockerignore():
    return [
        linea.strip()
        for linea in (RAIZ / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if linea.strip() and not linea.strip().startswith("#")
    ]


def _coincide(ruta: str, patron: str) -> bool:
    patron = patron.lstrip("/")
    partes = ruta.split("/")
    for fin in range(1, len(partes) + 1):
        candidata = partes[:fin]
        if fnmatch.fnmatchcase("/".join(candidata), patron):
            return True
        if patron.startswith("**/"):
            for inicio in range(len(candidata)):
                if fnmatch.fnmatchcase("/".join(candidata[inicio:]), patron[3:]):
                    return True
    return False


def _excluido(ruta: str) -> bool:
    """Semántica de `.dockerignore`: gana el último patrón que coincide; `!` vuelve a incluir."""
    fuera = False
    for patron in _patrones_dockerignore():
        negado = patron.startswith("!")
        if _coincide(ruta, patron[1:] if negado else patron):
            fuera = not negado
    return fuera


def _origenes_de_copy(dockerfile: Path):
    origenes = []
    for linea in dockerfile.read_text(encoding="utf-8").splitlines():
        partes = linea.split()
        if not partes or partes[0] != "COPY" or any(p.startswith("--from") for p in partes):
            continue
        argumentos = [p for p in partes[1:] if not p.startswith("--")]
        origenes.extend(argumentos[:-1])
    return origenes


def test_la_imagen_instala_desde_el_lock_con_huellas():
    dockerfile = (RAIZ / "backend/Dockerfile").read_text(encoding="utf-8")
    ordenes = "\n".join(linea for linea in dockerfile.splitlines() if not linea.lstrip().startswith("#"))
    assert "COPY backend/requirements.lock /tmp/requirements.lock" in ordenes
    assert "pip install --require-hashes -r /tmp/requirements.lock" in ordenes
    assert "requirements.txt" not in ordenes
    assert "pip install --upgrade" not in ordenes


def test_todo_lo_que_la_imagen_copia_llega_al_contexto_de_construccion():
    """
    Un `COPY` de un fichero que `.dockerignore` excluye rompe la construcción, y nada lo
    avisaba antes de construir. Así estuvo la imagen desde la Fase 12 hasta la 14: el
    Dockerfile copiaba `feedback_dataset.py` y el `.dockerignore` lo dejaba fuera. Esta
    prueba es la que lo habría detectado; también impide que el lock se quede fuera.
    """
    origenes = _origenes_de_copy(RAIZ / "backend/Dockerfile")
    assert "backend/requirements.lock" in origenes
    excluidos = [origen for origen in origenes if _excluido(origen)]
    assert excluidos == [], f".dockerignore deja fuera lo que el Dockerfile copia: {excluidos}"


def test_el_contexto_de_la_imagen_no_lleva_lo_que_no_se_despliega():
    """La otra mitad de la misma regla: las herramientas de desarrollo se quedan fuera."""
    for ruta in ("backend/requirements-dev.lock", "backend/requirements-dev.txt", "backend/tests/conftest.py"):
        assert _excluido(ruta), ruta


def test_el_ci_no_instala_nada_que_no_salga_de_un_lock():
    """
    Cada `pip install` de cada paso del workflow. Un `pip install ruff` suelto instala la
    versión publicada ese día, y una regla nueva de ruff puede poner el pipeline en rojo
    sin que nadie haya tocado el código.
    """
    flujo = yaml.safe_load((RAIZ / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    permitida = re.compile(r"pip install --require-hashes -r backend/requirements(-dev)?\.lock\b")
    instalaciones = 0
    for trabajo, definicion in flujo["jobs"].items():
        for paso in definicion.get("steps", []):
            for linea in str(paso.get("run", "")).splitlines():
                orden = linea.strip()
                if re.match(r"^(\S*/)?pip install\b", orden) or re.match(r"^python\S* -m pip install\b", orden):
                    instalaciones += 1
                    assert permitida.search(orden), f"[{trabajo}] instala fuera de un lock: {orden}"
    assert instalaciones >= 5


def test_pip_audit_no_ignora_ningun_aviso():
    """
    Capítulo 23: auditar sin excepciones.

    Hasta entonces el CI ignoraba PYSEC-2026-1325, temporización Minerva en `ecdsa`, que
    llegaba con python-jose y no tenía arreglo. La excepción estaba acotada y justificada,
    pero una excepción justificada sigue siendo un aviso que nadie mira. Se retiró la causa:
    PyJWT firma con HMAC sin `ecdsa` ni `cryptography`.

    Si un aviso futuro no tiene arreglo, esta prueba obliga a decidirlo a la vista —y a
    cambiarla— en lugar de añadir otro `--ignore-vuln` que pase desapercibido.
    """
    flujo = (RAIZ / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    # Las órdenes que auditan, no el archivo entero: la guarda que vigila esto mismo en el
    # pipeline nombra `--ignore-vuln` en su propio `grep`.
    auditorias = [
        orden for orden in re.findall(r"[^\n]*pip-audit --requirement \S+[^\n]*", flujo)
        if "grep" not in orden and not orden.lstrip().startswith("#")
    ]
    assert len(auditorias) == 3, auditorias
    for auditoria in auditorias:
        assert "--ignore-vuln" not in auditoria, auditoria
        assert "--strict" in auditoria, auditoria


def test_la_biblioteca_de_jwt_no_arrastra_criptografia_asimetrica():
    """
    Ni python-jose ni lo que traía: `ecdsa`, `rsa`, `pyasn1`, `cryptography`. Y la aplicación
    sigue sin poder firmar con otra cosa que HMAC, ni por configuración.
    """
    from app.core.config import ALGORITMOS_JWT_ADMITIDOS, Settings
    from pydantic import ValidationError

    for paquete in ("python-jose", "ecdsa", "rsa", "pyasn1", "cryptography"):
        assert paquete not in PROD, f"{paquete} vuelve a instalarse en producción"
    assert "pyjwt" in PROD

    for fuente in (RAIZ / "backend").rglob("*.py"):
        texto = fuente.read_text(encoding="utf-8")
        assert not re.search(r"^\s*(import|from)\s+(jose|ecdsa)\b", texto, re.M), fuente

    assert ALGORITMOS_JWT_ADMITIDOS == {"HS256", "HS384", "HS512"}
    for algoritmo in ("ES256", "RS256", "none"):
        with pytest.raises(ValidationError):
            Settings(JWT_ALGORITHM=algoritmo)
