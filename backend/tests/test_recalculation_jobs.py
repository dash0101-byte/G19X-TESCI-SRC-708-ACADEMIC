"""
Recálculo masivo en segundo plano.

El endpoint recorría todos los prospectos dentro de la petición: el cliente esperaba con
la conexión abierta mientras se ejecutaba una inferencia por registro, y a partir de unos
pocos miles el navegador y el `proxy_read_timeout` de nginx (60 s) cortaban antes de que
terminara, dejando el trabajo a medias sin rastro de por dónde iba.

Ahora se acepta con 202 y un identificador, y el avance se consulta aparte. Lo que se
comprueba aquí es que ese contrato se cumple de verdad: que el trabajo queda registrado,
que se ejecuta, que el progreso es consultable y que un prospecto roto no se lleva por
delante a los demás.
"""
import pytest
from app.models.entities import JobStatus, Lead, ScoreCategory, ScoringJob
from app.services.recalculation_service import (
    BATCH_SIZE_MAXIMO,
    crear_trabajo_de_recalculo,
)
from app.services.scoring_service import ScoringService

URL_RECALCULO = "/api/v1/leads/batch/recalculate-all"
URL_TRABAJO = "/api/v1/leads/batch/jobs"


# ==============================================================================
# Contrato del endpoint
# ==============================================================================

def test_el_recalculo_responde_202_con_identificador(client, lead_headers, sample_leads):
    """La respuesta llega de inmediato y trae con qué seguir el trabajo."""
    respuesta = client.post(URL_RECALCULO, headers=lead_headers)

    assert respuesta.status_code == 202
    trabajo = respuesta.json()
    assert trabajo["id"]
    assert trabajo["job_type"] == "RECALCULATE_ALL"
    assert trabajo["total_leads"] == len(sample_leads)


def test_el_trabajo_queda_registrado_en_la_base(client, lead_headers, db_session, sample_leads):
    """
    El trabajo se confirma en la base antes de responder.

    No es un detalle: el cliente puede consultar el identificador inmediatamente y, con
    varios workers, esa consulta la atenderá probablemente otro proceso. Si la fila no
    estuviera confirmada, recibiría un 404 por un trabajo que sí se aceptó.
    """
    job_id = client.post(URL_RECALCULO, headers=lead_headers).json()["id"]

    fila = db_session.query(ScoringJob).filter(ScoringJob.id == job_id).first()
    assert fila is not None
    assert fila.requested_by  # queda quién lo pidió, para auditoría


def test_el_trabajo_se_ejecuta_y_termina(client, lead_headers, sample_leads):
    """Tras la respuesta, la tarea de fondo procesa los prospectos y cierra el trabajo."""
    job_id = client.post(URL_RECALCULO, headers=lead_headers).json()["id"]

    estado = client.get(f"{URL_TRABAJO}/{job_id}", headers=lead_headers).json()
    assert estado["status"] == JobStatus.COMPLETED.value
    assert estado["processed_leads"] == len(sample_leads)
    assert estado["failed_leads"] == 0
    assert estado["progress_percentage"] == 100.0
    assert estado["started_at"] is not None
    assert estado["finished_at"] is not None


def test_el_recalculo_cambia_los_scores(client, lead_headers, db_session, sample_leads):
    """
    Comprobación de que el trabajo hace algo, no solo de que se marca como hecho.

    Los prospectos de la fixture llevan scores escritos a mano; tras el recálculo deben
    llevar los que produce el pipeline, que no son los mismos.
    """
    antes = {
        lead.id: lead.current_score
        for lead in db_session.query(Lead).order_by(Lead.id).all()
    }

    client.post(URL_RECALCULO, headers=lead_headers)

    db_session.expire_all()
    despues = {
        lead.id: lead.current_score
        for lead in db_session.query(Lead).order_by(Lead.id).all()
    }

    assert antes.keys() == despues.keys()
    assert antes != despues


def test_el_trabajo_desconocido_da_404(client, lead_headers):
    respuesta = client.get(f"{URL_TRABAJO}/no-existe-este-trabajo", headers=lead_headers)
    assert respuesta.status_code == 404


# ==============================================================================
# Paginación por lotes
# ==============================================================================

def test_el_tamano_de_lote_se_respeta(client, lead_headers, sample_leads):
    """El lote pedido queda registrado en el trabajo y se usa para recorrer."""
    respuesta = client.post(URL_RECALCULO, json={"batch_size": 2}, headers=lead_headers)

    assert respuesta.status_code == 202
    assert respuesta.json()["batch_size"] == 2


def test_con_lotes_pequenos_se_procesan_todos(client, lead_headers, sample_leads):
    """
    Seis prospectos en lotes de dos: tres vueltas al bucle, ninguno repetido ni saltado.

    Es lo que verifica que la paginación por clave (`id > último`) avanza de verdad. Con
    un `OFFSET` mal llevado —o sin mover el cursor— esto se quedaría en bucle infinito o
    procesaría solo el primer lote.
    """
    job_id = client.post(URL_RECALCULO, json={"batch_size": 2}, headers=lead_headers).json()["id"]

    estado = client.get(f"{URL_TRABAJO}/{job_id}", headers=lead_headers).json()
    assert estado["processed_leads"] == len(sample_leads)
    assert estado["status"] == JobStatus.COMPLETED.value


@pytest.mark.parametrize("tamano", [0, -5, 99999])
def test_el_tamano_de_lote_se_acota(client, lead_headers, sample_leads, tamano):
    """
    Valores absurdos se rechazan en el esquema o se recortan en el servicio.

    Un lote de cero dejaría el bucle sin avanzar nunca; uno de cien mil cargaría la tabla
    entera en memoria, que es justo lo que se venía a evitar.
    """
    respuesta = client.post(URL_RECALCULO, json={"batch_size": tamano}, headers=lead_headers)

    if respuesta.status_code == 202:
        assert 1 <= respuesta.json()["batch_size"] <= BATCH_SIZE_MAXIMO
    else:
        assert respuesta.status_code == 422


def test_el_servicio_acota_el_lote_aunque_no_pase_por_el_esquema(db_session, sample_leads):
    """
    La cota vive también en el servicio: no depende de que el esquema la haya filtrado.

    Hay que liberar el turno entre los dos: desde que el recálculo es exclusivo, un
    trabajo vivo bloquea al siguiente. Se hace a mano lo que el ejecutor hace al terminar
    —soltar `lease_key`—, en lugar de esperar a que caduque el arriendo.
    """
    primero = crear_trabajo_de_recalculo(db_session, batch_size=0)
    assert primero.batch_size == 1

    primero.lease_key = None
    db_session.commit()

    segundo = crear_trabajo_de_recalculo(db_session, batch_size=10**6)
    assert segundo.batch_size == BATCH_SIZE_MAXIMO


# ==============================================================================
# Robustez
# ==============================================================================

def test_un_prospecto_roto_no_detiene_el_lote(
    client, lead_headers, db_session, sample_leads, monkeypatch
):
    """
    Un prospecto que revienta se cuenta como fallido y el recorrido continúa.

    El fallo se inyecta en lugar de intentar construir datos "suficientemente corruptos":
    así el test es determinista y realmente entra por la rama de excepción, en vez de pasar
    porque el pipeline resultó ser tolerante con el dato elegido.

    Sin esta tolerancia, un solo registro corrupto entre diez mil abortaba el recálculo
    completo y dejaba media cartera con scores viejos.
    """
    id_maldito = db_session.query(Lead).order_by(Lead.id).first().id
    original = ScoringService.calculate_and_persist_score

    async def falla_para_uno(self, lead, *args, **kwargs):
        if lead.id == id_maldito:
            raise RuntimeError("fallo inyectado en el recálculo")
        return await original(self, lead, *args, **kwargs)

    monkeypatch.setattr(ScoringService, "calculate_and_persist_score", falla_para_uno)

    job_id = client.post(URL_RECALCULO, headers=lead_headers).json()["id"]
    estado = client.get(f"{URL_TRABAJO}/{job_id}", headers=lead_headers).json()

    assert estado["status"] == JobStatus.COMPLETED.value
    assert estado["failed_leads"] == 1
    assert estado["processed_leads"] == len(sample_leads) - 1


def test_un_fallo_irrecuperable_marca_el_trabajo_como_fallido(
    client, lead_headers, sample_leads, monkeypatch
):
    """
    Si el recorrido se rompe entero, el trabajo queda en FAILED y no en RUNNING para siempre.

    Un trabajo colgado en RUNNING es peor que uno fallido: quien consulta no distingue
    "sigue trabajando" de "murió hace media hora".
    """
    import app.services.recalculation_service as modulo

    def consulta_rota(*args, **kwargs):
        raise RuntimeError("la base se cayó a mitad del recorrido")

    monkeypatch.setattr(modulo.ScoringService, "__init__", consulta_rota)

    job_id = client.post(URL_RECALCULO, headers=lead_headers).json()["id"]
    estado = client.get(f"{URL_TRABAJO}/{job_id}", headers=lead_headers).json()

    assert estado["status"] == JobStatus.FAILED.value
    assert estado["finished_at"] is not None
    assert "recorrido" in (estado["error_message"] or "")


def test_sin_prospectos_el_trabajo_termina_al_100(client, lead_headers):
    """Una base vacía no debe dejar el avance clavado en 0 % ni dividir por cero."""
    job_id = client.post(URL_RECALCULO, headers=lead_headers).json()["id"]

    estado = client.get(f"{URL_TRABAJO}/{job_id}", headers=lead_headers).json()
    assert estado["total_leads"] == 0
    assert estado["status"] == JobStatus.COMPLETED.value
    assert estado["progress_percentage"] == 100.0


def test_los_scores_recalculados_son_coherentes(client, lead_headers, db_session, sample_leads):
    """Cada prospecto queda con un score dentro de rango y su categoría correspondiente."""
    client.post(URL_RECALCULO, headers=lead_headers)
    db_session.expire_all()

    for lead in db_session.query(Lead).all():
        assert 0.0 <= lead.current_score <= 100.0
        assert lead.score_category in set(ScoreCategory)


# ==============================================================================
# Control de acceso
# ==============================================================================

def test_un_ejecutivo_no_puede_lanzar_el_recalculo(client, executive_headers, sample_leads):
    """El recálculo masivo sigue reservado a Sales_Lead y System_Admin."""
    assert client.post(URL_RECALCULO, headers=executive_headers).status_code == 403


def test_un_ejecutivo_no_puede_consultar_trabajos(client, lead_headers, executive_headers, sample_leads):
    """Tampoco el estado: revela el volumen de la cartera y quién opera el sistema."""
    job_id = client.post(URL_RECALCULO, headers=lead_headers).json()["id"]

    assert client.get(f"{URL_TRABAJO}/{job_id}", headers=executive_headers).status_code == 403


def test_sin_token_no_se_encola_nada(client, db_session, sample_leads):
    respuesta = client.post(URL_RECALCULO)

    assert respuesta.status_code in (401, 403)
    assert db_session.query(ScoringJob).count() == 0
