"""
Las claves que ya no pueden volver a usarse viven como huella, no en claro (capítulo 27).

Hasta aquí la lista llevaba el texto literal de la clave de firma que se filtró y se rotó en
el capítulo 11. La prohibía bien, pero la dejaba escrita en el repositorio y, en cuanto el
proyecto se subió a GitHub, también en su historial para siempre.

Lo que se comprueba:

* que la lista son huellas SHA-256 y no textos;
* que el mecanismo sigue prohibiendo: una clave cuya huella está en la lista se rechaza, y
  en producción aborta el arranque;
* que una clave nueva y larga pasa;
* y, la que de verdad importa, que **ninguna clave prohibida ha vuelto al árbol del
  proyecto**: se recorre el código y la documentación buscando cualquier palabra que pudiera
  ser una clave y se comprueba que ninguna encaja con la lista. Si alguien vuelve a pegar la
  clave vieja en un fichero, esta prueba lo dice, aunque la pegue en un comentario o en un
  reporte.
"""
import hashlib
import os
import re
import secrets

import pytest
from app.core.config import (
    CLAVES_DE_RELLENO,
    HUELLAS_DE_CLAVES_COMPROMETIDAS,
    MIN_SECRET_KEY_LENGTH,
    Settings,
    es_clave_comprometida,
)

HEXADECIMAL = re.compile(r"^[0-9a-f]{64}$")

# Lo que podría ser una clave escrita en un fichero: una palabra larga sin espacios. El
# tope de longitud evita hashear líneas enteras de un `.lock` o de un base64 pegado.
CANDIDATA = re.compile(r"[A-Za-z0-9_\-+./=]{16,200}")

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CARPETAS_QUE_NO_SE_MIRAN = {
    ".git", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", "venv", ".venv",
    "htmlcov", "coverage", "dist", "build", "docs_residencias",
}
EXTENSIONES = {".py", ".md", ".yml", ".yaml", ".json", ".js", ".jsx", ".toml", ".ini", ".sh", ".env", ".example", ".conf", ".sql"}


def _huella(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _ficheros_del_proyecto():
    for carpeta, subcarpetas, ficheros in os.walk(RAIZ):
        subcarpetas[:] = [s for s in subcarpetas if s not in CARPETAS_QUE_NO_SE_MIRAN]
        for fichero in ficheros:
            if os.path.splitext(fichero)[1].lower() in EXTENSIONES or fichero.startswith(".env"):
                yield os.path.join(carpeta, fichero)


# ==============================================================================
# La lista
# ==============================================================================

def test_la_lista_son_huellas_y_no_claves():
    assert HUELLAS_DE_CLAVES_COMPROMETIDAS, "La lista no puede quedarse vacía."
    for entrada in HUELLAS_DE_CLAVES_COMPROMETIDAS:
        assert HEXADECIMAL.match(entrada), f"«{entrada[:20]}…» no es una huella SHA-256."


def test_los_marcadores_de_relleno_son_cortos():
    """
    Se quedan en claro porque no son secretos de nadie. Si alguno pasara del mínimo, habría
    que tratarlo como una clave de verdad y guardarlo también por su huella.
    """
    for relleno in CLAVES_DE_RELLENO:
        assert len(relleno) < MIN_SECRET_KEY_LENGTH


# ==============================================================================
# El mecanismo
# ==============================================================================

def test_una_clave_de_la_lista_se_rechaza(monkeypatch):
    """La lista real no lleva texto, así que se prueba el mecanismo con una clave inventada."""
    inventada = "clave_inventada_solo_para_esta_prueba_0123456789"
    monkeypatch.setattr(
        "app.core.config.HUELLAS_DE_CLAVES_COMPROMETIDAS", frozenset({_huella(inventada)})
    )

    assert es_clave_comprometida(inventada) is True


@pytest.mark.parametrize("relleno", sorted(CLAVES_DE_RELLENO))
def test_los_marcadores_de_relleno_se_rechazan(relleno):
    assert es_clave_comprometida(relleno) is True


def test_una_clave_nueva_pasa():
    assert es_clave_comprometida(secrets.token_urlsafe(64)) is False


def test_en_produccion_una_clave_de_la_lista_aborta_el_arranque(monkeypatch):
    inventada = "otra_clave_inventada_para_esta_prueba_0123456789"
    monkeypatch.setattr(
        "app.core.config.HUELLAS_DE_CLAVES_COMPROMETIDAS", frozenset({_huella(inventada)})
    )

    with pytest.raises(ValueError, match="comprometida"):
        Settings(ENVIRONMENT="production", SECRET_KEY=inventada)


# ==============================================================================
# Que no haya vuelto al árbol
# ==============================================================================

def test_ninguna_clave_prohibida_esta_escrita_en_el_proyecto():
    """
    Se hashea cada palabra larga de cada fichero de texto y se compara con la lista.

    Es la prueba que justifica el cambio: prohibir la clave no sirve de nada si la clave
    sigue escrita al lado de la prohibición.
    """
    encontradas = []
    for ruta in _ficheros_del_proyecto():
        try:
            with open(ruta, encoding="utf-8", errors="ignore") as f:
                contenido = f.read()
        except OSError:
            continue
        for candidata in CANDIDATA.findall(contenido):
            if _huella(candidata) in HUELLAS_DE_CLAVES_COMPROMETIDAS:
                encontradas.append(os.path.relpath(ruta, RAIZ))
                break

    assert not encontradas, (
        "Una clave comprometida ha vuelto al proyecto, en: " + ", ".join(sorted(encontradas))
    )
