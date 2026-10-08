"""
Pruebas de regresión para C-1: path traversal en el servidor de la SPA.

El catch-all `/{full_path:path}` unía la ruta pedida por el cliente a `frontend/dist`
sin validarla, de modo que una ruta con `../` (o su forma percent-encoded, que Starlette
decodifica antes de enrutar) permitía leer cualquier archivo del host.
"""
import os

import pytest
from app.main import assets_path, dist_path, resolve_dist_file

# Nombre del cebo colocado FUERA de dist/ (en su directorio padre) para comprobar
# que ninguna ruta traversal consigue leerlo.
CANARY_NAME = "canary_no_debe_servirse.txt"
CANARY_CONTENT = "CONTENIDO_FUERA_DE_DIST_NO_DEBE_FILTRARSE"

# Payloads en su forma ya decodificada: es exactamente lo que llega a `full_path`
# después de que Starlette resuelva el percent-encoding de la URL.
TRAVERSAL_PAYLOADS = [
    "../" + CANARY_NAME,                       # ../canary
    "../../" + CANARY_NAME,                    # ..%2f..%2f
    "assets/../../" + CANARY_NAME,             # traversal tras un prefijo legítimo
    "..\\" + CANARY_NAME,                      # separador de Windows
    "....//" + CANARY_NAME,                    # sanitización ingenua de ".."
    "../" * 12 + "etc/passwd",
    "/etc/passwd",                             # ruta absoluta POSIX
    r"C:\Windows\win.ini",                    # ruta absoluta Windows
    "..%2f" + CANARY_NAME,                     # doble codificación: no debe resolver a nada
    "index.html\x00" + CANARY_NAME,            # byte nulo
]

# Los mismos vectores tal como viajan por HTTP, con el traversal percent-encoded para
# que ni el cliente ni el router colapsen los segmentos antes de llegar al endpoint.
ENCODED_HTTP_PATHS = [
    "/%2e%2e%2f" + CANARY_NAME,
    "/%2e%2e%2f%2e%2e%2f" + CANARY_NAME,
    "/assets/%2e%2e%2f%2e%2e%2f" + CANARY_NAME,
    "/%2e%2e%5c" + CANARY_NAME,
    "/..%2f..%2f" + CANARY_NAME,
    "/%2e%2e%2f%2e%2e%2f%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
    "/assets/%2e%2e%2f%2e%2e%2f%2e%2e%2fbackend%2fapp%2fcore%2fconfig.py",
    "/%2e%2e%2f%2e%2e%2f%2e%2e%2f.env",
    "/%2e%2e%2f%2e%2e%2flead_scoring.db",
]


@pytest.fixture(scope="module")
def dist_minimo():
    """
    Garantiza un `dist/` con un `index.html` dentro, y deja el árbol como estaba.

    Hace falta porque **el cliente compilado no viaja en el repositorio** y el trabajo
    `pruebas` del CI no lo construye: declara `needs: modelo` y nada más, de modo que ahí
    `frontend/dist` no existe. Las dos pruebas de abajo son las del RESOLUTOR —no necesitan
    que el comodín esté montado, solo que haya un directorio contra el que resolver— y sin
    esto eran lo único rojo de la suite en el CI desde que se escribieron: una por el
    `index.html` que no estaba, y diez por la precondición del cebo, que en Linux es falsa
    porque el núcleo resuelve `dist/..` y `dist` no existe (en Windows el `..` se normaliza
    antes y la precondición pasaba, que es por lo que en local nunca se vio).

    Se crea en lugar de saltarse a propósito: son las pruebas de regresión de C-1, una
    lectura de cualquier archivo del host, y saltarlas justo en el único sitio que corre
    solo las convierte en diez renglones verdes que no comprueban nada. Lo que sí se queda
    saltado es lo de más abajo, que necesita `dist/assets` para que el comodín se monte, y
    eso se decide al importar `app.main`: ninguna fixture llega a tiempo.
    """
    creados = []
    if not os.path.isdir(dist_path):
        os.makedirs(dist_path)
        creados.append(dist_path)
    indice = os.path.join(dist_path, "index.html")
    if not os.path.isfile(indice):
        with open(indice, "w", encoding="utf-8") as fh:
            fh.write("<!doctype html><title>SPA de pruebas</title>")
        creados.append(indice)

    yield dist_path

    # Se retira solo lo que esta fixture creó: un `dist/` de verdad no se toca.
    for ruta in reversed(creados):
        os.remove(ruta) if os.path.isfile(ruta) else os.rmdir(ruta)


@pytest.fixture(scope="module")
def canary_file(dist_minimo):
    """Crea el cebo en el directorio padre de dist/ y lo elimina al terminar."""
    path = os.path.join(os.path.dirname(os.path.realpath(dist_path)), CANARY_NAME)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(CANARY_CONTENT)
    # Precondición: el archivo existe y es alcanzable por traversal ingenuo
    assert os.path.isfile(os.path.join(dist_path, "..", CANARY_NAME))
    yield path
    os.remove(path)


@pytest.mark.parametrize("payload", TRAVERSAL_PAYLOADS)
def test_resolver_rechaza_rutas_fuera_de_dist(canary_file, payload):
    """El resolutor devuelve None para cualquier ruta que escape de dist/."""
    assert resolve_dist_file(payload) is None


def test_resolver_sirve_archivos_legitimos_dentro_de_dist(dist_minimo):
    """El resolutor sigue devolviendo archivos reales contenidos en dist/."""
    resolved = resolve_dist_file("index.html")
    assert resolved is not None
    assert os.path.isfile(resolved)
    assert os.path.realpath(resolved).startswith(os.path.realpath(dist_path))

    # Un archivo inexistente dentro de dist/ no se resuelve
    assert resolve_dist_file("no-existe-este-archivo.js") is None
    # La raíz de dist/ no es un archivo servible
    assert resolve_dist_file("") is None


@pytest.mark.skipif(
    not os.path.exists(assets_path),
    reason="El frontend compilado (frontend/dist/assets) no está presente; el catch-all no se monta.",
)
@pytest.mark.parametrize("http_path", ENCODED_HTTP_PATHS)
def test_http_traversal_no_filtra_archivos_del_host(client, canary_file, http_path):
    """
    Ninguna petición HTTP con traversal codificado debe devolver contenido de fuera de dist/.
    La SPA responde con su index.html (fallback de cliente) o con 404, nunca con el cebo.
    """
    response = client.get(http_path)
    assert response.status_code in (200, 404)
    assert CANARY_CONTENT not in response.text
    assert "root:x:0:0" not in response.text
    if response.status_code == 200:
        assert "<html" in response.text.lower()


@pytest.mark.skipif(
    not os.path.exists(assets_path),
    reason="El frontend compilado (frontend/dist/assets) no está presente; el catch-all no se monta.",
)
def test_rutas_de_api_no_caen_en_el_catch_all(client):
    """El catch-all sigue excluyendo las rutas de API y documentación."""
    response = client.get("/api/v1/ruta-inexistente")
    assert response.status_code == 404
    assert response.json()["detail"] == "Not Found"


@pytest.mark.skipif(
    not os.path.exists(assets_path),
    reason="El frontend compilado (frontend/dist/assets) no está presente; el catch-all no se monta.",
)
def test_los_assets_legitimos_se_siguen_sirviendo_por_http(client):
    """
    Control positivo: la defensa no consiste en bloquearlo todo.

    Sin esta comprobación, un `resolve_dist_file` que devolviera None siempre pasaría
    todas las pruebas de traversal y rompería la aplicación en silencio.
    """
    archivos = [f for f in os.listdir(assets_path) if f.endswith((".js", ".css"))]
    assert archivos, "El build del frontend no contiene assets; regenérelo con `npm run build`."

    respuesta = client.get(f"/assets/{archivos[0]}")
    assert respuesta.status_code == 200
    assert len(respuesta.content) > 0


@pytest.mark.skipif(
    not os.path.exists(assets_path),
    reason="El frontend compilado (frontend/dist/assets) no está presente; el catch-all no se monta.",
)
def test_el_catch_all_no_expone_codigo_fuente_del_backend(client, canary_file):
    """Ningún vector debe devolver archivos de configuración o código del servidor."""
    for ruta in ("/../backend/app/core/config.py", "/../../backend/app/core/security.py", "/../.env"):
        respuesta = client.get(ruta)
        assert respuesta.status_code in (200, 404)
        assert "SECRET_KEY" not in respuesta.text
        assert "def hash_password" not in respuesta.text
