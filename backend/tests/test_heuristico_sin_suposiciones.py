"""
La regla heurística no supone un valor cuando falta el dato. Una prueba por variable.

Hasta el capítulo 25 el tamaño de empresa que no llegaba se leía como «1-10» —el tramo más
bajo— en tres sitios (el servicio, el simulador y la línea base del pipeline), y el
simulador ponía «51-200», cuatro visitas, una demo y un webinar a quien no los mandaba. Un
cargo que faltaba recibía la base de los cargos no listados, la misma que un estudiante.

La regla ahora distingue tres casos por variable firmográfica:

* **falta** (`None`, vacío o solo espacios) → el punto medio de su bloque, `UNKNOWN_*`;
* **no coincide** con ninguna regla → la base de su bloque, porque sí es un dato;
* **coincide** → sus puntos.

Las variables de comportamiento valen cero cuando no hay evento, y eso no es suponer: es lo
que el registro dice que pasó. Aquí se comprueba también.
"""
import pytest
from app.core import scoring_rules as reglas
from app.core.scoring_rules import (
    DEFAULT_INDUSTRY_POINTS,
    DEFAULT_TITLE_POINTS,
    INDUSTRY_RULES,
    SIZE_POINTS,
    TITLE_RULES,
    UNKNOWN_INDUSTRY_POINTS,
    UNKNOWN_SIZE_POINTS,
    UNKNOWN_TITLE_POINTS,
    calculate_heuristic_score,
)
from app.models.entities import ScoreHistory

FALTAS = [None, "", "   "]
CONOCIDOS = {"job_title": "CTO", "industry": "FinTech", "company_size": "201-1000"}


def _desglose(**cambios):
    return calculate_heuristic_score(**{**CONOCIDOS, **cambios})[1]


# ==============================================================================
# Tamaño de empresa
# ==============================================================================

@pytest.mark.parametrize("falta", FALTAS)
def test_sin_tamano_es_desconocido_y_no_1_10(falta):
    puntos = _desglose(company_size=falta)["company_size_fit_score"]

    assert puntos == UNKNOWN_SIZE_POINTS
    assert puntos != SIZE_POINTS["1-10"]


def test_una_empresa_de_1_a_10_sigue_puntuando_como_tal():
    """Lo desconocido deja de confundirse con «1-10», y «1-10» sigue siendo «1-10»."""
    assert _desglose(company_size="1-10")["company_size_fit_score"] == SIZE_POINTS["1-10"]


def test_una_etiqueta_de_tamano_que_no_se_reconoce_tampoco_dice_cuantos_son():
    """«Entre 5 y 8» no es ninguna etiqueta conocida: no se lee como la más pequeña."""
    assert _desglose(company_size="Entre 5 y 8")["company_size_fit_score"] == UNKNOWN_SIZE_POINTS


def test_el_tamano_se_compara_sin_los_espacios_de_los_extremos():
    assert _desglose(company_size=" 1000+ ")["company_size_fit_score"] == SIZE_POINTS["1000+"]


# ==============================================================================
# Cargo e industria
# ==============================================================================

@pytest.mark.parametrize("falta", FALTAS)
def test_sin_cargo_es_desconocido_y_no_la_base_de_un_estudiante(falta):
    puntos = _desglose(job_title=falta)["title_fit_score"]

    assert puntos == UNKNOWN_TITLE_POINTS
    assert puntos != DEFAULT_TITLE_POINTS


def test_un_cargo_que_no_coincide_conserva_su_base():
    """«Chef ejecutivo» es un dato: dijo a qué se dedica, y no es un perfil de TI."""
    assert _desglose(job_title="Chef ejecutivo")["title_fit_score"] == DEFAULT_TITLE_POINTS


@pytest.mark.parametrize("falta", FALTAS)
def test_sin_industria_es_desconocida(falta):
    assert _desglose(industry=falta)["industry_fit_score"] == UNKNOWN_INDUSTRY_POINTS


def test_una_industria_que_no_coincide_conserva_su_base():
    assert _desglose(industry="Hostelería")["industry_fit_score"] == DEFAULT_INDUSTRY_POINTS


# ==============================================================================
# Qué es «neutro»
# ==============================================================================

@pytest.mark.parametrize(
    ("desconocido", "tabla"),
    [
        (UNKNOWN_TITLE_POINTS, [p for p, _ in TITLE_RULES] + [DEFAULT_TITLE_POINTS]),
        (UNKNOWN_INDUSTRY_POINTS, [p for p, _ in INDUSTRY_RULES] + [DEFAULT_INDUSTRY_POINTS]),
        (UNKNOWN_SIZE_POINTS, list(SIZE_POINTS.values())),
    ],
)
def test_lo_desconocido_es_el_punto_medio_de_su_bloque(desconocido, tabla):
    """Ni el mejor tramo ni el peor: ni premia ni castiga no haberlo dicho."""
    assert desconocido == (min(tabla) + max(tabla)) / 2
    assert min(tabla) < desconocido < max(tabla)


def test_el_punto_medio_se_mueve_con_las_tablas():
    """Se calcula desde las tablas, no se escribe a mano: no puede quedarse atrás."""
    assert reglas._punto_medio([2.0, 10.0]) == 6.0
    assert reglas._punto_medio([0.0, 30.0]) == 15.0


# ==============================================================================
# Comportamiento: cero cuando no hay evento
# ==============================================================================

def test_sin_comportamiento_declarado_no_suma_nada():
    _, desglose, _ = calculate_heuristic_score(**CONOCIDOS)

    assert desglose["behavior_raw_total"] == 0.0
    assert desglose["heuristic_total"] == desglose["firmographic_total"]


@pytest.mark.parametrize("metadatos", [None, {}, {"urgency": None}, {"urgency": ""}, {"otro": "ALTA"}])
def test_sin_urgencia_declarada_no_suma(metadatos):
    """`{"urgency": None}` se leería como la cadena «NONE»: tampoco puede sumar."""
    _, desglose, _ = calculate_heuristic_score(**CONOCIDOS, custom_metadata=metadatos)

    assert desglose["behavior_raw_total"] == 0.0


def test_los_dias_sin_actividad_no_mueven_nada_si_no_hay_comportamiento():
    """Solo atenúan comportamiento: un prospecto sin actividad no gana ni pierde por la fecha."""
    hoy = calculate_heuristic_score(**CONOCIDOS, days_inactive=0.0)[0]
    hace_un_ano = calculate_heuristic_score(**CONOCIDOS, days_inactive=365.0)[0]

    assert hoy == hace_un_ano


# ==============================================================================
# Los que llaman a la regla tampoco suponen
# ==============================================================================

def test_una_ficha_sin_tamano_se_puntua_como_desconocida(client, lead_headers, sample_lead, db_session):
    sample_lead.company_size = None
    sample_lead.job_title = None
    db_session.commit()

    respuesta = client.post(f"/api/v1/leads/{sample_lead.id}/recalculate-score", headers=lead_headers)
    assert respuesta.status_code == 200, respuesta.text

    db_session.expire_all()
    historial = (
        db_session.query(ScoreHistory)
        .filter(ScoreHistory.lead_id == sample_lead.id)
        .order_by(ScoreHistory.id.desc())
        .first()
    )
    assert historial.rule_breakdown["company_size_fit_score"] == UNKNOWN_SIZE_POINTS
    assert historial.rule_breakdown["title_fit_score"] == UNKNOWN_TITLE_POINTS
    assert historial.feature_snapshot["company_size"] == ""


def test_el_simulador_no_rellena_lo_que_no_se_le_manda(client, lead_headers):
    """
    Solo cargo e industria. Antes salían «51-200», cuatro visitas, dos aperturas, un clic,
    una descarga, un webinar y una demo que nadie había declarado.
    """
    respuesta = client.post(
        "/api/v1/scoring/predict",
        headers=lead_headers,
        json={"job_title": "CTO", "industry": "FinTech"},
    )
    assert respuesta.status_code == 200, respuesta.text

    desglose = respuesta.json()["rule_breakdown"]
    assert desglose["company_size_fit_score"] == UNKNOWN_SIZE_POINTS
    assert desglose["behavior_raw_total"] == 0.0


def test_el_calculo_sin_persistencia_no_supone_nada_de_lo_que_falta(db_session):
    """
    El servicio, llamado sin el esquema del simulador delante: el esquema rellena ceros,
    pero quien llame al servicio con un diccionario incompleto no pasa por él. Aquí se
    suponía una visita a la página y el tramo «1-10».
    """
    import asyncio

    from app.services.scoring_service import ScoringService

    resultado = asyncio.run(
        ScoringService(db_session).predict_standalone({"job_title": "CTO", "industry": "FinTech"})
    )

    assert resultado.rule_breakdown["behavior_raw_total"] == 0.0
    assert resultado.rule_breakdown["company_size_fit_score"] == UNKNOWN_SIZE_POINTS


def test_la_linea_base_del_pipeline_tampoco_supone_el_tamano():
    """La comparación del modelo contra la regla tiene que medir la misma regla."""
    import pandas as pd

    from ml_pipeline.src.baselines import puntuar_con_heuristico

    sin_tamano = pd.DataFrame([{"job_title": "CTO", "industry": "FinTech", "company_size": None}])
    con_1_10 = pd.DataFrame([{"job_title": "CTO", "industry": "FinTech", "company_size": "1-10"}])

    assert puntuar_con_heuristico(sin_tamano).iloc[0] != puntuar_con_heuristico(con_1_10).iloc[0]
    esperado = calculate_heuristic_score("CTO", "FinTech", None)[0]
    assert puntuar_con_heuristico(sin_tamano).iloc[0] == esperado
