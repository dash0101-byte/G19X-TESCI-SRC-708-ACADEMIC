"""
Capítulo 22: un solo modo de arrancar la pila, con el entorno fuera del repositorio.

Había tres, y en las tres los secretos acababan dentro del árbol de trabajo. Lo que se
comprueba: que `devops/pila.py` se niega en cada caso que debe negarse sin llegar a ejecutar
Docker, que la orden que construye conserva el proyecto de Compose —y con él los volúmenes
existentes—, y que la documentación ya no enseña ningún otro modo.
"""
import importlib.util
import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("pila", RAIZ / "devops" / "pila.py")
pila = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pila)


def _entorno(ruta: pathlib.Path, **variables) -> pathlib.Path:
    valores = {"SECRET_KEY": "k" * 64, "POSTGRES_PASSWORD": "p" * 24, **variables}
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("".join(f"{k}={v}\n" for k, v in valores.items()), encoding="utf-8")
    return ruta


def _no_debe_ejecutarse(orden):
    raise AssertionError(f"se ejecutó Docker con un entorno que no vale: {orden}")


@pytest.fixture
def sin_env_sueltos(monkeypatch):
    """Aísla las pruebas del estado del repositorio real; ese se comprueba en su propia prueba."""
    monkeypatch.setattr(pila, "ENV_QUE_SE_LEEN_SOLOS", ())


# ==============================================================================
# Cuándo se niega
# ==============================================================================

def test_un_entorno_fuera_y_completo_se_acepta(tmp_path, sin_env_sueltos):
    assert pila.problemas_del_entorno(_entorno(tmp_path / "pila.env")) == []


def test_el_entorno_por_defecto_vive_fuera_del_repositorio():
    assert not pila.dentro_del_repositorio(pila.ENTORNO_POR_DEFECTO)


def test_un_entorno_dentro_del_repositorio_se_rechaza(tmp_path, monkeypatch, sin_env_sueltos):
    # No se escribe nada en el repositorio real: se finge que la raíz es un directorio temporal.
    monkeypatch.setattr(pila, "RAIZ", tmp_path)
    dentro = _entorno(tmp_path / "devops" / "secretos.env")

    problemas = pila.problemas_del_entorno(dentro)

    assert any("dentro del repositorio" in p for p in problemas)
    assert pila.main(["--entorno", str(dentro), "up", "-d"], ejecutar=_no_debe_ejecutarse) == 2


def test_un_env_suelto_en_el_repositorio_impide_arrancar(tmp_path, monkeypatch):
    suelto = tmp_path / "repositorio" / "devops" / ".env"
    suelto.parent.mkdir(parents=True)
    suelto.write_text("SECRET_KEY=la-de-antes\n", encoding="utf-8")
    monkeypatch.setattr(pila, "ENV_QUE_SE_LEEN_SOLOS", (suelto,))
    fuera = _entorno(tmp_path / "fuera" / "pila.env")

    problemas = pila.problemas_del_entorno(fuera)

    assert any(str(suelto) in p for p in problemas)
    assert pila.main(["--entorno", str(fuera), "up", "-d"], ejecutar=_no_debe_ejecutarse) == 2


@pytest.mark.parametrize("falta", pila.OBLIGATORIAS)
def test_sin_un_secreto_obligatorio_no_arranca(tmp_path, sin_env_sueltos, falta):
    ruta = _entorno(tmp_path / "pila.env", **{falta: ""})
    assert any(falta in p for p in pila.problemas_del_entorno(ruta))
    assert pila.main(["--entorno", str(ruta), "up"], ejecutar=_no_debe_ejecutarse) == 2


def test_sin_archivo_de_entorno_dice_como_crearlo(tmp_path, sin_env_sueltos, capsys):
    assert pila.main(["--entorno", str(tmp_path / "no_existe.env"), "up"], ejecutar=_no_debe_ejecutarse) == 2
    assert "pila.py iniciar" in capsys.readouterr().out


def test_la_variable_de_entorno_elige_el_archivo(tmp_path):
    elegido = tmp_path / "otro.env"
    assert pila.ruta_del_entorno(None, {"PLURIONE_ENTORNO": str(elegido)}) == elegido
    assert pila.ruta_del_entorno(None, {}) == pila.ENTORNO_POR_DEFECTO


# ==============================================================================
# Qué ejecuta
# ==============================================================================

def test_la_orden_pasa_siempre_el_entorno_y_conserva_el_proyecto(tmp_path, sin_env_sueltos):
    ruta = _entorno(tmp_path / "pila.env")
    ejecutadas = []

    codigo = pila.main(["--entorno", str(ruta), "--dev", "--profile", "respaldo", "up", "-d"], ejecutar=lambda o: ejecutadas.append(o) or 0)

    assert codigo == 0
    assert ejecutadas == [[
        "docker", "compose", "--env-file", str(ruta), "--project-directory", str(pila.DEVOPS),
        "-f", str(pila.COMPOSE), "-f", str(pila.COMPOSE_DEV), "--profile", "respaldo", "up", "-d",
    ]]
    # Compose nombra el proyecto por el directorio: `devops`, como cuando se arrancaba desde
    # esa carpeta. Con otro nombre, la pila crearía volúmenes nuevos y vacíos.
    assert pathlib.Path(ejecutadas[0][5]).name == "devops"


def test_comprobar_no_ejecuta_docker(tmp_path, sin_env_sueltos):
    ruta = _entorno(tmp_path / "pila.env")
    assert pila.main(["--entorno", str(ruta), "--comprobar"], ejecutar=_no_debe_ejecutarse) == 0


def test_iniciar_genera_secretos_nuevos_y_no_sobrescribe(tmp_path, sin_env_sueltos):
    primero, segundo = tmp_path / "a" / "pila.env", tmp_path / "b" / "pila.env"

    assert pila.main(["--entorno", str(primero), "iniciar"]) == 0
    assert pila.main(["--entorno", str(segundo), "iniciar"]) == 0

    variables = pila.leer_variables(primero)
    assert len(variables["SECRET_KEY"]) >= 64 and len(variables["POSTGRES_PASSWORD"]) >= 24
    assert variables["SECRET_KEY"] != pila.leer_variables(segundo)["SECRET_KEY"]
    assert set(pila.leer_variables(pila.EJEMPLO)) <= set(variables), "Faltan variables de la plantilla."
    assert pila.problemas_del_entorno(primero) == []

    contenido = primero.read_text(encoding="utf-8")
    assert pila.main(["--entorno", str(primero), "iniciar"]) == 2
    assert primero.read_text(encoding="utf-8") == contenido, "iniciar sobrescribió un entorno existente."


def test_iniciar_no_crea_el_entorno_dentro_del_repositorio(tmp_path, monkeypatch, sin_env_sueltos):
    monkeypatch.setattr(pila, "RAIZ", tmp_path)
    dentro = tmp_path / "devops" / "pila.env"
    assert pila.main(["--entorno", str(dentro), "iniciar"]) == 2
    assert not dentro.exists()


# ==============================================================================
# El repositorio y la documentación
# ==============================================================================

def test_el_repositorio_no_lleva_archivos_de_entorno_sueltos():
    sueltos = [str(ruta) for ruta in pila.ENV_QUE_SE_LEEN_SOLOS if ruta.exists()]
    assert sueltos == [], (
        f"Hay archivos de entorno dentro del repositorio: {sueltos}. Muévalos fuera "
        f"({pila.ENTORNO_POR_DEFECTO}) y arranque con `python devops/pila.py`."
    )


DOCUMENTOS = ["README.md", "devops/docker-compose.yml", "devops/docker-compose.dev.yml", "devops/.env.example"]


def _bloques_de_codigo(texto: str):
    return re.findall(r"```[^\n]*\n(.*?)```", texto, flags=re.DOTALL)


@pytest.mark.parametrize("documento", DOCUMENTOS)
def test_la_documentacion_solo_arranca_por_el_lanzador(documento):
    texto = (RAIZ / documento).read_text(encoding="utf-8")
    if documento.endswith(".md"):
        lineas = "\n".join(_bloques_de_codigo(texto)).splitlines()
        ordenes = [linea for linea in lineas if re.match(r"\s*docker compose\b", linea)]
    else:
        ordenes = [linea for linea in texto.splitlines() if re.match(r"\s*#\s+docker compose\b", linea)]
    assert ordenes == [], f"{documento} enseña a llamar a Compose sin el entorno: {ordenes}"

    assert not re.search(r"devops/\.env(?!\.example)", texto), f"{documento} vuelve a mencionar devops/.env."
    assert ">> .env" not in texto
