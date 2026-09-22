"""
Registro estructurado, correlación de peticiones y métricas (N-14).

El sistema registraba una línea de texto por evento y devolvía en los 500 un `request_id`
que se inventaba en el propio manejador de excepciones: no aparecía en ningún otro renglón,
así que el dato que soporte pedía —«deme el request_id»— no servía para encontrar nada.

Lo que se comprueba aquí:

* que cada petición lleva un identificador, que sale en la cabecera y que aparece en los
  renglones que esa petición produce;
* que un identificador ajeno se acepta solo si es seguro imprimirlo, porque un salto de
  línea dentro de la cabecera fabrica renglones falsos en un formato de una línea por evento;
* que `/metrics` mide por PLANTILLA de ruta y no por ruta concreta —lo contrario hace
  crecer las series sin tope—, que el histograma es válido, y que la ruta no queda abierta
  por descuido en un entorno endurecido.
"""
import json
import logging

import pytest
from app.core import metricas
from app.core.config import settings
from app.core.observabilidad import (
    FormateadorJson,
    _request_id,
    _request_id_admisible,
    formato_de_registro,
    plantillas_por_endpoint,
)
from app.main import app
from fastapi.testclient import TestClient

URL_METRICAS = "/metrics"


@pytest.fixture
def metricas_limpias():
    """
    Los contadores son globales del proceso y se acumulan entre pruebas.

    Vaciarlos antes Y después evita las dos formas de que esto engañe: leer restos de otra
    prueba, y dejar restos para la siguiente.
    """
    metricas.reiniciar()
    yield
    metricas.reiniciar()


# ==============================================================================
# request_id
# ==============================================================================

def test_toda_respuesta_lleva_su_identificador(client):
    respuesta = client.get("/health")

    assert respuesta.headers.get("x-request-id")


def test_dos_peticiones_reciben_identificadores_distintos(client):
    primero = client.get("/health").headers["x-request-id"]
    segundo = client.get("/health").headers["x-request-id"]

    assert primero != segundo


def test_se_respeta_el_identificador_que_manda_el_cliente(client):
    """
    Encadenar con el `request_id` de un balanceador o de otro servicio es el motivo de que
    se acepte uno entrante: si cada salto inventa el suyo, la traza se corta en cada salto.
    """
    respuesta = client.get("/health", headers={"X-Request-ID": "trazado-desde-el-balanceador"})

    assert respuesta.headers["x-request-id"] == "trazado-desde-el-balanceador"


def test_el_error_devuelve_el_mismo_identificador_en_cuerpo_y_cabecera(monkeypatch):
    """
    El identificador que se le da al cliente tiene que ser el que llevan los renglones.

    Antes se generaba uno nuevo dentro del manejador de excepciones: el cliente recibía un
    código que no constaba en ningún log, así que «deme el request_id» no llevaba a nada.

    El fallo se inyecta dentro de una ruta que ya existe, en vez de registrar una nueva:
    añadir rutas a una aplicación ya arrancada depende de detalles internos del enrutador
    y haría que esta prueba comprobara eso en lugar de lo que dice comprobar.

    `raise_server_exceptions=False` porque el cliente de pruebas, por defecto, vuelve a
    lanzar la excepción después de que el manejador construya la respuesta: sin esto no se
    llega a ver el 500 que recibiría un cliente real.
    """
    import app.main as modulo

    def revienta(_ruta):
        raise RuntimeError("fallo deliberado para la prueba")

    monkeypatch.setattr(modulo, "resolve_dist_file", revienta)

    with TestClient(app, raise_server_exceptions=False) as cliente:
        respuesta = cliente.get("/", headers={"X-Request-ID": "identificador-de-la-prueba"})

    assert respuesta.status_code == 500
    assert respuesta.json()["request_id"] == "identificador-de-la-prueba"
    assert respuesta.headers["x-request-id"] == "identificador-de-la-prueba"


@pytest.mark.parametrize(
    "valor",
    [
        'salto\nde linea',
        'retorno\rde carro',
        '{"nivel":"CRITICAL","mensaje":"todo bien"}',
        "con espacios",
        "x" * 65,
        "",
    ],
)
def test_un_identificador_inadmisible_se_descarta(valor):
    """
    No se «limpia» el valor del cliente: se descarta y se genera uno propio.

    Un saneado parcial es una lista de casos que alguien acabará rodeando. Y el riesgo es
    concreto: con un objeto JSON por línea, un salto de línea dentro de la cabecera escribe
    renglones enteros en el registro del servidor, indistinguibles de los reales.
    """
    assert _request_id_admisible(valor) is None


def test_un_identificador_con_saltos_no_llega_a_la_respuesta(client):
    respuesta = client.get("/health", headers={"X-Request-ID": "a" * 200})

    devuelto = respuesta.headers["x-request-id"]
    assert devuelto != "a" * 200
    assert len(devuelto) <= 64


# ==============================================================================
# Formato de los registros
# ==============================================================================

def _formatear(mensaje: str, **extra) -> dict:
    registro = logging.LogRecord(
        name="prueba", level=logging.INFO, pathname=__file__, lineno=1,
        msg=mensaje, args=(), exc_info=None,
    )
    for clave, valor in extra.items():
        setattr(registro, clave, valor)
    return json.loads(FormateadorJson().format(registro))


def test_cada_evento_es_un_json_de_una_linea():
    evento = _formatear("algo pasó")

    assert evento["nivel"] == "INFO"
    assert evento["logger"] == "prueba"
    assert evento["mensaje"] == "algo pasó"
    assert evento["ts"].endswith("+00:00"), "La marca de tiempo debe ser UTC explícito."


def test_el_identificador_de_la_peticion_entra_en_cada_renglon():
    """
    Es la razón de ser del `contextvars`: que los mensajes de SQLAlchemy, de uvicorn o de
    cualquier dependencia queden correlacionados sin tocar su código.
    """
    testigo = _request_id.set("correlacion-de-prueba")
    try:
        evento = _formatear("mensaje de una librería cualquiera")
    finally:
        _request_id.reset(testigo)

    assert evento["request_id"] == "correlacion-de-prueba"


def test_los_campos_extra_salen_como_campos_y_no_como_texto():
    evento = _formatear("prospecto actualizado", lead_id=42, ruta="/api/v1/leads/{lead_id}")

    assert evento["lead_id"] == 42
    assert evento["ruta"] == "/api/v1/leads/{lead_id}"


def test_la_traza_va_en_su_propio_campo_y_no_parte_la_linea():
    """
    Una traza concatenada al mensaje rompería el «un evento por línea», que es justo lo que
    hacía inservible el formato anterior con dos workers escribiendo a la vez.
    """
    try:
        raise ValueError("reventó")
    except ValueError:
        import sys
        registro = logging.LogRecord(
            name="prueba", level=logging.ERROR, pathname=__file__, lineno=1,
            msg="algo falló", args=(), exc_info=sys.exc_info(),
        )
        linea = FormateadorJson().format(registro)

    assert "\n" not in linea, "El renglón debe seguir siendo uno solo."
    evento = json.loads(linea)
    assert "ValueError: reventó" in evento["excepcion"]


def test_el_formato_lo_decide_el_entorno_cuando_es_auto(monkeypatch):
    monkeypatch.setattr(settings, "LOG_FORMAT", "auto")

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert formato_de_registro() == "json"

    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    assert formato_de_registro() == "text"


def test_un_log_format_mal_escrito_no_cae_en_silencio_a_texto():
    """
    `LOG_FORMAT=jsonn` en producción dejaría los registros en texto sin que nada lo dijera,
    y el agregador que espera JSON los descartaría en bloque: el sistema seguiría
    «funcionando» y nadie tendría registros hasta el día que hicieran falta.
    """
    from app.core.config import Settings
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(LOG_FORMAT="jsonn")


# ==============================================================================
# Métricas
# ==============================================================================

def test_las_metricas_se_publican(client, metricas_limpias):
    respuesta = client.get(URL_METRICAS)

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/plain")
    assert "plurione_http_peticiones_total" in respuesta.text


def test_se_mide_por_plantilla_y_no_por_ruta_concreta(
    client, lead_headers, sample_lead, metricas_limpias
):
    """
    Con la ruta concreta, cada prospecto consultado crea una serie temporal nueva y la
    memoria del proceso —y la del Prometheus que lo recoja— crece sin tope. Es el modo
    clásico de tumbar un sistema de métricas con una instrumentación descuidada.
    """
    client.get(f"/api/v1/leads/{sample_lead.id}", headers=lead_headers)

    volcado = client.get(URL_METRICAS).text

    assert 'ruta="/api/v1/leads/{lead_id}"' in volcado
    assert f'ruta="/api/v1/leads/{sample_lead.id}"' not in volcado


def test_el_histograma_es_valido(client, lead_headers, sample_leads, metricas_limpias):
    """
    El cubo `+Inf` debe existir y valer lo mismo que `_count`: es la definición de
    histograma acumulado, y sin él Prometheus rechaza la métrica entera.
    """
    client.get("/api/v1/leads", headers=lead_headers)
    volcado = client.get(URL_METRICAS).text

    infinitos = [
        linea for linea in volcado.splitlines()
        if linea.startswith("plurione_http_duracion_segundos_bucket") and 'le="+Inf"' in linea
    ]
    assert infinitos, "Falta el cubo +Inf."

    for linea in infinitos:
        etiquetas = linea[linea.index("{") + 1: linea.index("}")]
        sin_le = ",".join(p for p in etiquetas.split(",") if not p.startswith("le="))
        valor_inf = int(linea.rsplit(" ", 1)[1])
        cuenta = next(
            int(otra.rsplit(" ", 1)[1])
            for otra in volcado.splitlines()
            if otra.startswith(f"plurione_http_duracion_segundos_count{{{sin_le}}}")
        )
        assert valor_inf == cuenta


def test_los_contadores_llevan_el_codigo_de_respuesta(client, metricas_limpias):
    client.get("/health")

    volcado = client.get(URL_METRICAS).text
    assert 'ruta="/health",estado="200"' in volcado


def test_los_recuentos_derivados_salen_de_la_base(
    client, lead_headers, db_session, sample_leads, metricas_limpias
):
    """
    Lo que puede leerse de la base se lee de la base: sale exacto lo atienda el worker que
    lo atienda, y no depende de cuántos scores llevara contados este proceso.
    """
    volcado = client.get(URL_METRICAS).text

    assert "plurione_base_de_datos_accesible 1" in volcado
    assert "plurione_recalculos_en_curso 0" in volcado
    assert "plurione_prospectos_total{" in volcado


def test_el_recalculo_vivo_se_ve_en_las_metricas(
    client, lead_headers, db_session, sample_leads, metricas_limpias
):
    import datetime

    from app.models.entities import JobStatus, ScoringJob, utc_now
    from app.services.recalculation_service import CLAVE_DE_TURNO

    db_session.add(
        ScoringJob(
            id="trabajo-visible-en-metricas",
            job_type="RECALCULATE_ALL",
            status=JobStatus.RUNNING.value,
            total_leads=10, processed_leads=1, failed_leads=0, batch_size=100,
            lease_key=CLAVE_DE_TURNO,
            lease_until=utc_now() + datetime.timedelta(minutes=5),
        )
    )
    db_session.commit()

    volcado = client.get(URL_METRICAS).text
    assert "plurione_recalculos_en_curso 1" in volcado


def test_la_recogida_dice_que_worker_la_atendio(client, metricas_limpias):
    """
    Con dos workers, los contadores de proceso son los de UNO de ellos. Que el propio
    volcado lo diga hace visible esa limitación en los datos, no solo en un comentario.
    """
    volcado = client.get(URL_METRICAS).text

    assert "plurione_worker_info{worker=" in volcado


def test_los_scores_calculados_se_cuentan(client, lead_headers, sample_leads, metricas_limpias):
    client.post(URL_METRICAS.replace("/metrics", "/api/v1/leads/batch/recalculate-all"),
                headers=lead_headers)

    volcado = client.get(URL_METRICAS).text
    assert "plurione_scores_calculados_total{categoria=" in volcado


# ==============================================================================
# Quién puede pedirlas
# ==============================================================================

def test_en_produccion_sin_testigo_la_ruta_no_existe(client, monkeypatch):
    """
    404 y no 403: un 403 confirma que la ruta está ahí, y con ella que hay algo que pedir.

    Vacío significa «abierta» en desarrollo y «apagada» en producción a propósito. El
    volcado dice cuántos prospectos hay y cómo se reparten; publicarlo debe ser una
    decisión, no un valor por defecto.
    """
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "METRICS_TOKEN", "")

    assert client.get(URL_METRICAS).status_code == 404


def test_con_testigo_hace_falta_presentarlo(client, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "METRICS_TOKEN", "testigo-del-recolector")

    assert client.get(URL_METRICAS).status_code == 404
    assert client.get(
        URL_METRICAS, headers={"Authorization": "Bearer testigo-equivocado"}
    ).status_code == 404
    assert client.get(
        URL_METRICAS, headers={"Authorization": "Bearer testigo-del-recolector"}
    ).status_code == 200


def test_la_ruta_se_puede_apagar_del_todo(client, monkeypatch):
    monkeypatch.setattr(settings, "METRICS_ENABLED", False)

    assert client.get(URL_METRICAS).status_code == 404


def test_todas_las_rutas_declaradas_saben_su_plantilla():
    """
    Guarda del recorrido de rutas, que se apoya en atributos internos de FastAPI.

    FastAPI dejó de aplanar los routers incluidos: `app.routes` guarda envoltorios
    anidados y las rutas hoja llevan la ruta relativa. La primera versión de este código
    recorría un solo nivel y etiquetaba TODA la API como `<sin_ruta>` —las métricas se
    seguían publicando, sin un solo error, solo que no decían nada—.

    Esta prueba es lo que hará que una versión futura de FastAPI que vuelva a cambiar la
    disposición se note aquí y no en un panel vacío dentro de tres meses.
    """
    mapa = plantillas_por_endpoint(app)
    plantillas = set(mapa.values())

    esperadas = {
        "/health",
        "/metrics",
        f"{settings.API_V1_STR}/leads",
        f"{settings.API_V1_STR}/leads/{{lead_id}}",
        f"{settings.API_V1_STR}/leads/{{lead_id}}/activities",
        f"{settings.API_V1_STR}/leads/batch/recalculate-all",
        f"{settings.API_V1_STR}/auth/login",
        f"{settings.API_V1_STR}/users/{{user_id}}",
        f"{settings.API_V1_STR}/campaigns",
        f"{settings.API_V1_STR}/analytics/summary",
    }
    faltan = esperadas - plantillas
    assert not faltan, (
        f"Estas rutas no se traducen a plantilla y se medirían como '<sin_ruta>': {sorted(faltan)}. "
        "Revise `plantillas_por_endpoint`: la disposición de los routers de FastAPI cambió."
    )


def test_ninguna_peticion_normal_se_mide_como_ruta_desconocida(
    client, lead_headers, sample_lead, metricas_limpias
):
    """
    Lo mismo, pero de extremo a extremo: se pide de verdad y se mira el volcado.

    Una ruta sin traducir no rompe nada —el volcado sale igual—, así que sin una prueba
    que lo mire el fallo vive indefinidamente.
    """
    client.get("/health")
    client.get("/api/v1/leads", headers=lead_headers)
    client.get(f"/api/v1/leads/{sample_lead.id}", headers=lead_headers)

    volcado = client.get(URL_METRICAS).text

    assert 'ruta="<sin_ruta>"' not in volcado, (
        "Alguna petición a una ruta declarada se midió como desconocida:\n" + volcado
    )


def test_las_metricas_no_cuelgan_de_la_api_versionada():
    """
    El nginx de la pila solo hace de pasarela para `/api/`. Dejar `/metrics` fuera de ese
    prefijo la mantiene inalcanzable desde el puerto público sin depender de una regla de
    denegación que alguien pueda borrar.
    """
    rutas = {getattr(ruta, "path", None) for ruta in app.router.routes}

    assert "/metrics" in rutas
    assert f"{settings.API_V1_STR}/metrics" not in rutas
