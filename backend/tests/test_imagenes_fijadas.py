"""
Capítulo 22: las imágenes base van fijadas por huella y el sistema base no se actualiza a ciegas.

§20.8 y §17.9 lo dejaron escrito: `python:3.13-slim`, `postgres:16-alpine` y
`anchore/syft:latest` se resolvían por etiqueta, y `apk --no-cache upgrade` hacía que dos
construcciones del mismo Dockerfile en fechas distintas dieran imágenes distintas. La guarda
es `scripts/renovar_imagenes.py --solo-fijacion`; aquí se comprueba el repositorio y que la
guarda detecta cada forma de volver atrás.

Capítulo 32: las dos mitades que faltaban
-------------------------------------------
La guarda exigía versión a los paquetes de `apk` y no a los de `apt-get`, es decir, a la
imagen del **cliente** y no a la del **backend**. Y fijaba por huella todo lo que el CI
DESCARGA sin mirar lo que el CI EJECUTA: `actions/checkout@v4` es una etiqueta móvil, y lo
que hay detrás corre con el token del repositorio.
"""
import importlib.util
import pathlib

import pytest
import yaml

RAIZ = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("renovar_imagenes", RAIZ / "scripts" / "renovar_imagenes.py")
renovar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(renovar)

H1 = "sha256:" + "1" * 64
H2 = "sha256:" + "2" * 64


def test_el_repositorio_no_tiene_imagenes_sin_fijar_ni_apk_upgrade():
    assert renovar.problemas_de_fijacion() == []
    assert renovar.main(["--solo-fijacion"]) == 0


@pytest.mark.parametrize("ruta", renovar.COMPOSE)
def test_el_lector_de_compose_ve_lo_mismo_que_yaml(ruta):
    """El lector propio existe para no depender de PyYAML en CI; no puede ver otra pila."""
    texto = (RAIZ / ruta).read_text(encoding="utf-8")
    esperado = {
        nombre: (servicio.get("image"), "build" in servicio)
        for nombre, servicio in yaml.safe_load(texto)["services"].items()
    }
    visto = {
        nombre: (servicio.get("image"), "build" in servicio)
        for nombre, servicio in renovar.servicios_de_compose(texto).items()
    }
    assert visto == esperado


# ==============================================================================
# Cada forma de volver atrás
# ==============================================================================

def test_un_from_por_etiqueta_se_detecta():
    assert renovar.problemas_de_dockerfile("FROM python:3.13-slim AS builder\n")
    assert renovar.problemas_de_dockerfile(f"FROM python:3.13-slim@{H1} AS builder\n") == []


def test_una_etapa_propia_no_es_una_imagen():
    texto = f"FROM nginx:alpine@{H1} AS servidor\nFROM servidor AS production-stage\n"
    assert renovar.problemas_de_dockerfile(texto) == []


@pytest.mark.parametrize("orden", [
    "RUN apk --no-cache upgrade",
    "RUN apk upgrade --no-cache",
    "RUN apk update && apk upgrade",
])
def test_apk_upgrade_se_detecta(orden):
    problemas = renovar.problemas_de_dockerfile(f"FROM nginx:alpine@{H1}\n{orden}\n")
    assert any("apk upgrade" in p for p in problemas)


def test_un_paquete_de_apk_sin_version_se_detecta_aunque_venga_en_otra_linea():
    texto = f"FROM nginx:alpine@{H1}\nRUN apk add --no-cache 'libuuid=2.42.3-r1' \\\n    curl\n"
    assert renovar.problemas_de_dockerfile(texto) == ["`apk add curl`: paquete sin versión"]


def test_un_servicio_de_compose_sin_huella_se_detecta_y_uno_construido_no():
    texto = (
        "services:\n"
        "  redis:\n"
        "    image: redis:7-alpine\n"
        "  backend:\n"
        "    image: plurione/leadscoring-backend:local\n"
        "    build:\n"
        "      context: ..\n"
        "  monitor-deriva:\n"
        "    image: plurione/leadscoring-backend:local\n"
    )
    assert renovar.problemas_de_compose(texto) == ["servicio `redis`: redis:7-alpine no va fijada por huella"]


@pytest.mark.parametrize("linea", [
    "          docker run --rm aquasec/trivy:0.74.0 image x",
    "        image: postgres:16-alpine",
    "          docker run --rm ghcr.io/gitleaks/gitleaks:latest detect",
    "              anchore/syft:latest -q -o cyclonedx-json",
])
def test_una_imagen_sin_huella_en_el_workflow_se_detecta(linea):
    assert renovar.problemas_de_workflow(linea)


@pytest.mark.parametrize("linea", [
    f"          docker run --rm aquasec/trivy:0.74.0@{H1} image x",
    "          docker run -d --name web-ci plurione-frontend:ci",
    "      DATABASE_URL: postgresql+psycopg2://plurione:clave@localhost:5432/lead_scoring_db",
    "          curl -sS http://127.0.0.1:8099/assets/x.css",
    "      # docker run --rm aquasec/trivy:0.74.0 image x",
    "      # - uses: actions/checkout@v4",
])
def test_lo_que_no_es_una_imagen_ajena_no_dispara(linea):
    assert renovar.problemas_de_workflow(linea) == []


# ==============================================================================
# Capítulo 32: lo que el 22 dejó a medias
# ==============================================================================

@pytest.mark.parametrize("orden", [
    "RUN apt-get update && apt-get upgrade -y",
    "RUN apt-get dist-upgrade -y",
])
def test_apt_get_upgrade_se_detecta(orden):
    """El equivalente de `apk upgrade` en Debian, que es la base de la imagen del backend."""
    problemas = renovar.problemas_de_dockerfile(f"FROM python:3.13-slim@{H1}\n{orden}\n")
    assert any("apt-get upgrade" in p for p in problemas)


def test_un_paquete_de_apt_get_sin_version_se_detecta_aunque_venga_en_otra_linea():
    texto = (
        f"FROM python:3.13-slim@{H1}\n"
        "RUN apt-get update && apt-get install -y --no-install-recommends \\\n"
        "    'libpq5=17.11-0+deb13u1' \\\n"
        "    build-essential \\\n"
        "    && rm -rf /var/lib/apt/lists/*\n"
    )
    assert renovar.problemas_de_dockerfile(texto) == [
        "`apt-get install build-essential`: paquete sin versión"
    ]


def test_apt_get_update_no_es_una_instalacion_sin_version():
    """`apt-get update` no instala nada: exigirle versión sería un disparo en falso diario."""
    texto = f"FROM python:3.13-slim@{H1}\nRUN apt-get update && rm -rf /var/lib/apt/lists/*\n"
    assert renovar.problemas_de_dockerfile(texto) == []


@pytest.mark.parametrize("linea", [
    "      - uses: actions/checkout@v4",
    "      - uses: actions/setup-python@v5.6.0",
    "        uses: docker/build-push-action@main",
])
def test_una_accion_de_github_por_etiqueta_se_detecta(linea):
    """
    Una etiqueta es móvil: quien controle el repositorio de la acción —o quien le robe la
    cuenta— la reapunta y el siguiente `push` ejecuta otra cosa con el token del trabajo.
    """
    problemas = renovar.problemas_de_workflow(linea)
    assert problemas and "huella del commit" in problemas[0]


@pytest.mark.parametrize("linea", [
    "      - uses: actions/checkout@" + "a" * 40 + " # v4.4.0",
    "        uses: docker/build-push-action@" + "b" * 40,
])
def test_una_accion_fijada_por_commit_no_dispara(linea):
    assert renovar.problemas_de_workflow(linea) == []


def test_el_repositorio_no_usa_ninguna_accion_por_etiqueta():
    acciones = renovar.acciones_fijadas()
    assert acciones, "el workflow usa acciones; si esto queda vacío, la guarda dejó de mirarlas"
    assert all(renovar.HUELLA_DE_COMMIT.fullmatch(huella) for huella in acciones.values())


def test_la_misma_etiqueta_con_dos_huellas_es_una_renovacion_a_medias(monkeypatch):
    textos = {
        "a/Dockerfile": f"FROM python:3.13-slim@{H1}\n",
        "b/Dockerfile": f"FROM python:3.13-slim@{H2}\n",
    }
    monkeypatch.setattr(renovar, "DOCKERFILES", list(textos))
    monkeypatch.setattr(renovar, "COMPOSE", [])
    monkeypatch.setattr(renovar, "WORKFLOWS", [])
    monkeypatch.setattr(renovar, "_leer", textos.__getitem__)

    problemas = renovar.problemas_de_fijacion()
    assert len(problemas) == 1 and "2 huellas distintas" in problemas[0]


# ==============================================================================
# La renovación
# ==============================================================================

def test_renovar_reescribe_solo_la_etiqueta_atrasada():
    texto = f"FROM node:20-alpine@{H1} AS a\nFROM nginx:alpine@{H1} AS b\n"
    renovado = renovar.reescribir(texto, {("nginx", "alpine"): H2})
    assert renovado == f"FROM node:20-alpine@{H1} AS a\nFROM nginx:alpine@{H2} AS b\n"


def test_sin_aplicar_informa_y_falla_y_con_aplicar_reescribe(tmp_path, monkeypatch, capsys):
    (tmp_path / "Dockerfile").write_text(f"FROM nginx:alpine@{H1}\n", encoding="utf-8")
    monkeypatch.setattr(renovar, "RAIZ", tmp_path)
    monkeypatch.setattr(renovar, "DOCKERFILES", ["Dockerfile"])
    monkeypatch.setattr(renovar, "COMPOSE", [])
    monkeypatch.setattr(renovar, "WORKFLOWS", [])
    consultar = lambda imagen, etiqueta: H2  # noqa: E731

    assert renovar.main([], consultar=consultar) == 1
    assert "ATRASADA" in capsys.readouterr().out
    assert (tmp_path / "Dockerfile").read_text(encoding="utf-8") == f"FROM nginx:alpine@{H1}\n"

    assert renovar.main(["--aplicar"], consultar=consultar) == 0
    assert (tmp_path / "Dockerfile").read_text(encoding="utf-8") == f"FROM nginx:alpine@{H2}\n"
