"""
Política de origen cruzado (A-8).

`allow_origins=settings.CORS_ORIGINS or ["*"]` con `allow_credentials=True` no era una
configuración laxa: era una autorización explícita para que cualquier sitio de internet
leyera respuestas autenticadas de esta API. El detalle que lo hace explotable está en
Starlette: al ver el comodín junto a las credenciales **deja de responder `*`** y pasa a
devolver el origen exacto que preguntó, con `Access-Control-Allow-Credentials: true`
detrás. Eso es justo lo que el navegador exige para dejar que la página del atacante lea
la respuesta.

Y aquí la cookie de refresco lo agrava: el navegador la adjunta sola en peticiones con
credenciales, así que la página del atacante no necesita robar nada previamente. Le basta
con que la víctima la visite con la sesión abierta.

Estas pruebas cubren las dos mitades: que la configuración inválida no llegue a
construirse, y que la aplicación realmente montada no conceda el permiso.
"""
import pytest
from app.core.config import Settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

CLAVE_VALIDA = "clave-de-pruebas-suficientemente-larga-para-pasar-el-minimo"
ORIGEN_ATACANTE = "https://sitio-del-atacante.example"


def _settings(**overrides) -> Settings:
    return Settings(SECRET_KEY=CLAVE_VALIDA, **overrides)


# ============================================================================
# El mecanismo: por qué el comodín con credenciales es explotable
# ============================================================================

def test_el_comodin_con_credenciales_devuelve_el_origen_del_atacante():
    """
    Documenta el comportamiento de Starlette que hacía explotable la configuración
    anterior. No prueba nuestro código: prueba la premisa sobre la que se apoya el
    resto del fichero, y por eso conviene que esté escrita y no supuesta.
    """
    app_insegura = FastAPI()
    app_insegura.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],          # exactamente lo que producía `or ["*"]`
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app_insegura.get("/datos-privados")
    def datos_privados():
        return {"prospectos": ["confidencial"]}

    respuesta = TestClient(app_insegura).get(
        "/datos-privados", headers={"Origin": ORIGEN_ATACANTE}
    )

    # El comodín NO se devuelve: se devuelve el origen del atacante, que es lo que el
    # navegador necesita para autorizar la lectura con credenciales.
    assert respuesta.headers["access-control-allow-origin"] == ORIGEN_ATACANTE
    assert respuesta.headers["access-control-allow-credentials"] == "true"


# ============================================================================
# La configuración inválida no se puede construir
# ============================================================================

def test_el_comodin_explicito_aborta_el_arranque():
    with pytest.raises(ValueError) as excinfo:
        _settings(CORS_ORIGINS=["https://app.plurione.com", "*"])
    assert "CORS_ORIGINS" in str(excinfo.value)


@pytest.mark.parametrize("entorno", ["production", "development"])
def test_una_lista_vacia_significa_vacia_y_no_comodin(entorno):
    """
    Este es el camino real del defecto: nadie escribe `*`, alguien deja `CORS_ORIGINS`
    sin definir. `or ["*"]` convertía esa omisión en permiso universal.

    Vacía sigue siendo una configuración válida —y es la correcta cuando el frontend se
    sirve desde el mismo origen que la API, como hace la pila de Compose: nginx entrega
    la SPA y hace de proxy de `/api/`, así que CORS no interviene—. Lo que cambia es que
    ahora cierra el paso en lugar de abrirlo del todo.
    """
    ajustes = _settings(ENVIRONMENT=entorno, CORS_ORIGINS=[])
    assert ajustes.CORS_ORIGINS == []


def test_se_normaliza_la_barra_final_y_los_duplicados():
    """
    La comparación de orígenes es textual y el navegador nunca manda barra final: una
    entrada con barra no coincide jamás. Es un fallo mudo que se suele "arreglar"
    volviendo al comodín, así que se corrige en la carga.
    """
    ajustes = _settings(
        CORS_ORIGINS=[
            "https://app.plurione.com/",
            "  https://app.plurione.com  ",
            "",
            "https://admin.plurione.com",
        ]
    )
    assert ajustes.CORS_ORIGINS == [
        "https://app.plurione.com",
        "https://admin.plurione.com",
    ]


@pytest.mark.parametrize(
    ("crudo", "esperado"),
    [
        ("", []),
        ("   ", []),
        ("[]", []),
        ('["https://app.plurione.com"]', ["https://app.plurione.com"]),
        ("https://app.plurione.com", ["https://app.plurione.com"]),
        ("https://app.plurione.com, https://admin.plurione.com/",
         ["https://app.plurione.com", "https://admin.plurione.com"]),
    ],
)
def test_se_admiten_las_formas_naturales_de_escribir_la_variable(crudo, esperado, monkeypatch):
    """
    `CORS_ORIGINS=` vacío es la forma natural de decir «ninguno», y antes moría en el
    `json.loads` interno de pydantic-settings con un error que no nombra ni la causa ni
    el remedio: el fallo ocurre en la carga de la fuente, antes de cualquier validador.
    Una variable de seguridad cuyo valor más restrictivo es el más difícil de escribir
    acaba rellenada con cualquier cosa.
    """
    monkeypatch.setenv("CORS_ORIGINS", crudo)
    assert Settings(SECRET_KEY=CLAVE_VALIDA).CORS_ORIGINS == esperado


def test_un_json_mal_escrito_dice_como_arreglarlo(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["https://app.plurione.com"')
    with pytest.raises(ValueError) as excinfo:
        Settings(SECRET_KEY=CLAVE_VALIDA)
    assert "CORS_ORIGINS" in str(excinfo.value)


# ============================================================================
# La aplicación montada no concede el permiso
# ============================================================================

def test_la_api_no_autoriza_a_un_origen_desconocido(client):
    respuesta = client.get("/health", headers={"Origin": ORIGEN_ATACANTE})
    assert respuesta.status_code == 200
    # Sin cabecera de autorización de origen, el navegador bloquea la lectura.
    assert "access-control-allow-origin" not in respuesta.headers


def test_el_preflight_de_un_origen_desconocido_se_rechaza(client):
    respuesta = client.options(
        "/api/v1/leads",
        headers={
            "Origin": ORIGEN_ATACANTE,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert respuesta.status_code == 400
    assert "Disallowed CORS origin" in respuesta.text


def test_el_origen_declarado_si_se_autoriza(client):
    """La restricción no debe romper al frontend legítimo."""
    from app.core.config import settings

    if not settings.CORS_ORIGINS:
        pytest.skip("La suite corre con CORS_ORIGINS vacía; no hay origen legítimo que probar.")
    origen = settings.CORS_ORIGINS[0]
    respuesta = client.get("/health", headers={"Origin": origen})
    assert respuesta.headers["access-control-allow-origin"] == origen
    assert respuesta.headers["access-control-allow-credentials"] == "true"
