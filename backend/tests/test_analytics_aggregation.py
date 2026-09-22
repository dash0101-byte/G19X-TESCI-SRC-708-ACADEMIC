"""
Rendimiento por campaña resuelto en una sola consulta.

El cálculo era un N+1: una consulta para las campañas y, al tocar `camp.leads`, otra por
campaña, materializando cada prospecto entero en memoria solo para contarlos. Reescribirlo
como agregación cambia *dónde* se calcula, así que lo primero que hay que demostrar es que
no cambia *qué* se calcula: los tests comparan contra el mismo cómputo hecho en Python.
"""
import pytest
from app.core.autorizacion import AlcanceDeCartera
from app.models.entities import Campaign, Lead, LeadStatus, ScoreCategory
from app.services.analytics_service import AnalyticsService
from sqlalchemy import event

# El informe por campaña se calcula sobre la cartera completa: es un informe de
# dirección, y el endpoint que lo expone está restringido a quien la dirige. Estas
# pruebas comprueban la agregación en sí, no el alcance, que tiene las suyas.
TODA_LA_CARTERA = AlcanceDeCartera.del_sistema("pruebas de agregación")

URL_CAMPANAS = "/api/v1/analytics/campaigns"


@pytest.fixture
def cartera_atribuida(db_session, campaigns, sample_leads):
    """
    Reparte los prospectos entre las campañas y deja una tercera sin ninguno.

    La campaña vacía no es adorno: es el caso que un `JOIN` interno haría desaparecer del
    informe, y es justo cuando más interesa verla —una campaña con presupuesto y cero
    captación—.
    """
    vacia = Campaign(name="Radio Local", channel="Offline", budget=45000.0)
    db_session.add(vacia)
    db_session.commit()
    db_session.refresh(vacia)

    for indice, lead in enumerate(sample_leads):
        lead.campaign_id = campaigns[indice % len(campaigns)].id
    db_session.commit()

    return {"con_leads": campaigns, "vacia": vacia}


def _calculo_en_python(db_session):
    """El cómputo anterior, recorriendo en Python. Sirve de referencia."""
    esperado = {}
    for camp in db_session.query(Campaign).all():
        leads = camp.leads
        total = len(leads)
        esperado[camp.id] = {
            "total_leads": total,
            "hot_leads": sum(1 for lead in leads if lead.score_category == ScoreCategory.HOT),
            "avg_score": (
                round(sum(lead.current_score for lead in leads) / total, 1) if total else 0.0
            ),
            "conversion_rate": (
                round(sum(1 for lead in leads if lead.status == LeadStatus.WON) / total * 100.0, 1)
                if total else 0.0
            ),
        }
    return esperado


# ==============================================================================
# Equivalencia con el cálculo anterior
# ==============================================================================

def test_la_agregacion_da_lo_mismo_que_el_recorrido_en_python(db_session, cartera_atribuida):
    """Misma respuesta, distinto sitio donde se calcula."""
    esperado = _calculo_en_python(db_session)
    obtenido = {
        fila.campaign_id: {
            "total_leads": fila.total_leads,
            "hot_leads": fila.hot_leads,
            "avg_score": fila.avg_score,
            "conversion_rate": fila.conversion_rate,
        }
        for fila in AnalyticsService(db_session, TODA_LA_CARTERA).get_campaigns_performance()
    }

    assert obtenido == esperado


def test_las_campanas_sin_prospectos_siguen_apareciendo(db_session, cartera_atribuida):
    """Con un JOIN interno, esta campaña se habría caído del informe."""
    filas = AnalyticsService(db_session, TODA_LA_CARTERA).get_campaigns_performance()
    vacia = next(f for f in filas if f.campaign_id == cartera_atribuida["vacia"].id)

    assert vacia.total_leads == 0
    assert vacia.hot_leads == 0
    assert vacia.avg_score == 0.0
    assert vacia.conversion_rate == 0.0
    assert vacia.budget == 45000.0


def test_sin_campanas_devuelve_una_lista_vacia(db_session):
    assert AnalyticsService(db_session, TODA_LA_CARTERA).get_campaigns_performance() == []


# ==============================================================================
# Que sea de verdad una sola consulta
# ==============================================================================

def test_el_informe_se_resuelve_en_una_unica_consulta(db_session, cartera_atribuida):
    """
    Se cuentan las sentencias emitidas, no se confía en que el código parezca agregado.

    Es la única forma de que esto siga siendo una prueba dentro de un año: un `joinedload`
    mal puesto, o alguien que vuelva a tocar `camp.leads` en un bucle, restauran el N+1 sin
    que el resultado cambie ni un dígito.
    """
    sentencias = []

    def registrar(conn, cursor, statement, parameters, context, executemany):
        sentencias.append(statement)

    motor = db_session.get_bind()
    event.listen(motor, "before_cursor_execute", registrar)
    try:
        db_session.expire_all()
        AnalyticsService(db_session, TODA_LA_CARTERA).get_campaigns_performance()
    finally:
        event.remove(motor, "before_cursor_execute", registrar)

    consultas = [s for s in sentencias if s.lstrip().upper().startswith("SELECT")]
    assert len(consultas) == 1, f"se esperaba 1 consulta y se emitieron {len(consultas)}"


def test_el_numero_de_consultas_no_crece_con_las_campanas(db_session, cartera_atribuida):
    """
    Añadir campañas no debe añadir viajes a la base. Es la definición de haber matado el N+1.
    """
    def contar():
        sentencias = []
        motor = db_session.get_bind()
        registrar = lambda c, cur, s, p, ctx, em: sentencias.append(s)  # noqa: E731
        event.listen(motor, "before_cursor_execute", registrar)
        try:
            db_session.expire_all()
            AnalyticsService(db_session, TODA_LA_CARTERA).get_campaigns_performance()
        finally:
            event.remove(motor, "before_cursor_execute", registrar)
        return len([s for s in sentencias if s.lstrip().upper().startswith("SELECT")])

    antes = contar()

    db_session.add_all(
        Campaign(name=f"Campaña {i}", channel="Email Marketing", budget=1000.0 * i)
        for i in range(10)
    )
    db_session.commit()

    assert contar() == antes


# ==============================================================================
# El endpoint sigue sirviendo lo mismo
# ==============================================================================

def test_el_endpoint_devuelve_todas_las_campanas(client, lead_headers, db_session, cartera_atribuida):
    respuesta = client.get(URL_CAMPANAS, headers=lead_headers)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert len(cuerpo) == db_session.query(Campaign).count()
    assert {"campaign_id", "campaign_name", "channel", "budget", "total_leads",
            "hot_leads", "avg_score", "conversion_rate"} <= set(cuerpo[0])


def test_los_totales_del_informe_cuadran_con_la_cartera(client, lead_headers, db_session, cartera_atribuida):
    """La suma por campañas no debe perder ni duplicar prospectos atribuidos."""
    cuerpo = client.get(URL_CAMPANAS, headers=lead_headers).json()

    atribuidos = db_session.query(Lead).filter(Lead.campaign_id.isnot(None)).count()
    assert sum(fila["total_leads"] for fila in cuerpo) == atribuidos
