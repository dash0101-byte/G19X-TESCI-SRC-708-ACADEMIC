"""
Capítulo 22: las imágenes base van fijadas por huella y el sistema base no se actualiza a ciegas.

§20.8 y §17.9 lo dejaron escrito: `python:3.13-slim`, `postgres:16-alpine` y
`anchore/syft:latest` se resolvían por etiqueta, y `apk --no-cache upgrade` hacía que dos
construcciones del mismo Dockerfile en fechas distintas dieran imágenes distintas. La guarda
es `scripts/renovar_imagenes.py --solo-fijacion`; aquí se comprueba el repositorio y que la
guarda detecta cada forma de volver atrás.
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
    "      - uses: actions/checkout@v4",
    "      # docker run --rm aquasec/trivy:0.74.0 image x",
])
def test_lo_que_no_es_una_imagen_ajena_no_dispara(linea):
    assert renovar.problemas_de_workflow(linea) == []


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
