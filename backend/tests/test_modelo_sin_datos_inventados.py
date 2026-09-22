"""
Capítulo 24: el modelo sin datos inventados (§21.12 y §19.9).

* **Ingresos.** Cuando un prospecto no declaraba sus ingresos anuales, el adaptador pasaba
  100 000 al modelo; el alta del panel mandaba 2 000 000 fijos y el esquema de la API, cero.
  Ahora la ausencia llega como ausencia y el artefacto la imputa y la marca.
* **Mensajes y llamadas.** `whatsapp_messages` contaba también LinkedIn, y de las llamadas
  solo llegaban las que conectaron. Ahora son cuatro variables.
* **El aporte con intervalo.** Publicar exigía el IC 95 % del ROC-AUC, pero el aporte sobre
  el heurístico se medía con la estimación puntual.
"""
import json
import math
import os

import joblib
import numpy as np
import pandas as pd
import pytest
from app.adapters.azure_ml_adapter import NativeMLScoringAdapter
from app.core.scoring_rules import calculate_heuristic_score
from app.core.vector_del_modelo import (
    COLUMNAS_DEL_MODELO,
    VERSION_DEL_VECTOR,
    ingresos_o_ausente,
)
from app.models.entities import (
    ActivityType,
    Lead,
    LeadActivity,
    LeadStatus,
    ScoreCategory,
    ScoreHistory,
)
from app.services.scoring_service import ScoringService

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODELOS = os.path.join(RAIZ, "ml_pipeline", "models")


def _json(nombre):
    with open(os.path.join(MODELOS, nombre), encoding="utf-8") as fh:
        return json.load(fh)


# ============================================================================
# Ingresos: la ausencia llega como ausencia
# ============================================================================
@pytest.mark.parametrize("valor", [None, "", 0, 0.0, -5, float("nan"), "no es cifra"])
def test_un_ingreso_ausente_o_a_cero_no_es_un_dato(valor):
    assert ingresos_o_ausente(valor) is None


def test_un_ingreso_declarado_se_respeta():
    assert ingresos_o_ausente(4_500_000) == 4_500_000.0
    assert ingresos_o_ausente("250000.5") == 250_000.5


@pytest.mark.parametrize("valor", [None, 0.0])
def test_el_adaptador_pasa_nan_y_no_una_cifra(valor):
    fila = NativeMLScoringAdapter.construir_fila({"annual_revenue": valor})
    assert math.isnan(fila["annual_revenue"])


def test_el_adaptador_ya_no_escribe_la_cifra_inventada():
    """La constante misma: que no vuelva por otro camino del adaptador."""
    ruta = os.path.join(RAIZ, "backend", "app", "adapters", "azure_ml_adapter.py")
    with open(ruta, encoding="utf-8") as fh:
        codigo = [linea for linea in fh if not linea.lstrip().startswith("#")]
    assert not any("100000" in linea or "100_000" in linea for linea in codigo)


@pytest.fixture(scope="module")
def artefacto():
    return joblib.load(os.path.join(MODELOS, "lead_scorer_model.joblib"))


def test_el_artefacto_imputa_los_ingresos_y_marca_que_faltaban(artefacto):
    tramo = artefacto.named_steps["preprocessor"].named_transformers_["ingresos"]
    imputador = tramo.named_steps["imputar"]
    assert imputador.add_indicator is True
    assert imputador.indicator_ is not None, "el entrenamiento no tenía ingresos ausentes"

    filas = pd.DataFrame(
        [
            NativeMLScoringAdapter.construir_fila({"annual_revenue": None}),
            NativeMLScoringAdapter.construir_fila({"annual_revenue": imputador.statistics_[0]}),
        ],
        columns=COLUMNAS_DEL_MODELO,
    )
    sin_escalar = imputador.transform(filas[["annual_revenue"]])
    # Mismo valor imputado, distinta marca: «no lo sabemos» y «factura la mediana» ya no
    # son la misma entrada para el modelo.
    assert sin_escalar[0, 0] == sin_escalar[1, 0]
    assert (sin_escalar[0, 1], sin_escalar[1, 1]) == (1.0, 0.0)


def test_el_preprocesador_marca_los_ingresos_ausentes():
    """El código que entrena, no solo el artefacto que ya se entrenó con él."""
    from feature_engineering import build_preprocessor

    tramos = {nombre: (paso, columnas) for nombre, paso, columnas in build_preprocessor().transformers}
    paso, columnas = tramos["ingresos"]
    assert columnas == ["annual_revenue"]
    assert paso.named_steps["imputar"].add_indicator is True
    assert "annual_revenue" not in tramos["num"][1]


def test_el_artefacto_se_entreno_con_el_vector_vigente(artefacto):
    assert list(artefacto.feature_names_in_) == COLUMNAS_DEL_MODELO


@pytest.mark.asyncio
async def test_un_prospecto_sin_ingresos_se_puntua_con_el_modelo():
    adaptador = NativeMLScoringAdapter()
    assert adaptador.model is not None
    fila = {"job_title": "CTO", "industry": "FinTech", "company_size": "1000+", "requested_demo": 1}

    sin_ingresos = adaptador._predict_sync(adaptador.construir_fila(fila))
    assert 0.0 < sin_ingresos < 1.0


def test_la_ficha_sin_ingresos_llega_al_modelo_como_ausente(db_session, sample_lead):
    for guardado in (None, 0.0):
        sample_lead.annual_revenue = guardado
        db_session.commit()
        assert ScoringService(db_session).extract_features_from_lead(sample_lead)["annual_revenue"] is None


def test_el_alta_sin_ingresos_no_escribe_cero(client, lead_headers, db_session):
    nuevo = {
        "first_name": "Sin",
        "last_name": "Ingresos",
        "email": "sin.ingresos@empresa.mx",
        "company": "Empresa MX",
        "job_title": "CTO",
        "industry": "FinTech",
    }
    respuesta = client.post("/api/v1/leads", json=nuevo, headers=lead_headers)
    assert respuesta.status_code in (200, 201)

    db_session.expire_all()
    lead = db_session.get(Lead, respuesta.json()["id"])
    assert lead.annual_revenue is None
    instantanea = (
        db_session.query(ScoreHistory).filter(ScoreHistory.lead_id == lead.id).first().feature_snapshot
    )
    assert instantanea["annual_revenue"] is None


# ============================================================================
# Llamadas y mensajes
# ============================================================================
def test_una_llamada_sin_resultado_no_cuenta_en_ninguna_variable(db_session, sample_lead):
    """Las anteriores a la Fase 15 no tienen resultado: suponérselo sería inventarlo."""
    db_session.add(LeadActivity(lead_id=sample_lead.id, activity_type=ActivityType.PHONE_CALL, call_outcome=None))
    db_session.commit()
    db_session.expire_all()

    variables = ScoringService(db_session).extract_features_from_lead(db_session.get(Lead, sample_lead.id))
    assert variables["phone_calls_connected"] == 0
    assert variables["phone_calls_unanswered"] == 0


def test_separar_los_canales_no_mueve_el_heuristico():
    """La mitad heurística del score dice lo mismo de cada prospecto que antes del cambio."""
    base = {"job_title": "CTO", "industry": "FinTech", "company_size": "1000+", "days_inactive": 3.0}
    for whatsapp, linkedin in [(1, 1), (0, 2), (2, 0), (3, 4)]:
        juntos = calculate_heuristic_score(**base, whatsapp_messages=whatsapp + linkedin)
        separados = calculate_heuristic_score(**base, whatsapp_messages=whatsapp, linkedin_messages=linkedin)
        assert juntos == separados


def test_la_instantanea_declara_su_vector(db_session, sample_lead):
    variables = ScoringService(db_session).extract_features_from_lead(sample_lead)
    assert variables["version_del_vector"] == VERSION_DEL_VECTOR
    assert set(COLUMNAS_DEL_MODELO) - {"source_channel"} <= set(variables)


# ============================================================================
# El dataset real no traduce instantáneas antiguas
# ============================================================================
INSTANTANEA_V1 = {
    "page_views": 5, "email_opens": 3, "email_clicks": 1, "content_downloads": 0,
    "attended_webinar": 0, "requested_demo": 0, "meeting_scheduled": 0, "proposal_sent": 0,
    "phone_calls": 1, "whatsapp_messages": 2, "days_since_last_activity": 2.0,
}
INSTANTANEA_V2 = {
    "page_views": 5, "email_opens": 3, "email_clicks": 1, "content_downloads": 0,
    "attended_webinar": 0, "requested_demo": 0, "meeting_scheduled": 0, "proposal_sent": 0,
    "phone_calls_connected": 1, "phone_calls_unanswered": 2, "whatsapp_messages": 1,
    "linkedin_messages": 1, "days_since_last_activity": 2.0, "version_del_vector": 2,
}


def _terminal(db_session, email, instantanea, ingresos):
    lead = Lead(
        first_name="Caso", last_name="Terminal", email=email, company="Empresa",
        job_title="CTO", industry="FinTech", company_size="1000+", annual_revenue=ingresos,
        source="LinkedIn Ads", status=LeadStatus.WON, current_score=70.0,
        score_category=ScoreCategory.WARM,
    )
    db_session.add(lead)
    db_session.flush()
    db_session.add(ScoreHistory(
        lead_id=lead.id, score=70.0, score_category=ScoreCategory.WARM, ml_probability=0.6,
        heuristic_score=70.0, decay_factor=1.0, feature_snapshot=instantanea,
    ))
    db_session.commit()
    return lead


def test_una_instantanea_del_vector_anterior_se_descarta_y_se_cuenta(db_session):
    from feedback_dataset import construir_dataset

    antiguo = _terminal(db_session, "vector.uno@empresa.mx", INSTANTANEA_V1, 3_000_000.0)
    vigente = _terminal(db_session, "vector.dos@empresa.mx", INSTANTANEA_V2, None)

    df, manifiesto = construir_dataset(db=db_session, exigir_minimos=False)

    assert antiguo.id not in set(df["lead_id"])
    assert manifiesto["terminales_con_instantanea_de_un_vector_anterior"] == 1
    fila = df[df["lead_id"] == vigente.id].iloc[0]
    assert pd.isna(fila["annual_revenue"]), "los ingresos ausentes se rellenaron en el dataset"
    assert (fila["whatsapp_messages"], fila["linkedin_messages"]) == (1, 1)


def test_el_monitor_no_compara_instantaneas_de_otro_vector():
    from drift_monitor import del_mismo_vector

    df = pd.DataFrame([dict(INSTANTANEA_V1), dict(INSTANTANEA_V2), dict(INSTANTANEA_V2)])
    vigentes, fuera = del_mismo_vector(df, {"version_del_vector": 2})
    assert (len(vigentes), fuera) == (2, 1)

    solo_antiguas, fuera = del_mismo_vector(pd.DataFrame([INSTANTANEA_V1]), {"version_del_vector": 2})
    assert (len(solo_antiguas), fuera) == (0, 1)


# ============================================================================
# §19.9: el aporte sobre el heurístico con intervalo
# ============================================================================
def test_el_intervalo_del_aporte_es_pareado():
    """Si modelo y regla puntúan igual, el aporte es cero en TODAS las réplicas."""
    from train_model import intervalo_bootstrap_del_aporte

    generador = np.random.default_rng(3)
    y = generador.integers(0, 2, 300)
    puntuaciones = generador.random(300)
    ic = intervalo_bootstrap_del_aporte(y, puntuaciones, puntuaciones * 100, remuestreos=300)
    assert (ic["inferior"], ic["superior"]) == (0.0, 0.0)


def test_el_intervalo_del_aporte_ve_un_modelo_mejor():
    from train_model import intervalo_bootstrap_del_aporte

    generador = np.random.default_rng(5)
    y = generador.integers(0, 2, 400)
    modelo = y + generador.normal(0, 0.4, 400)
    regla = y + generador.normal(0, 1.5, 400)
    ic = intervalo_bootstrap_del_aporte(y, modelo, regla, remuestreos=300)
    assert ic["inferior"] > 0.0


def test_sin_dos_clases_no_hay_intervalo_del_aporte():
    from train_model import intervalo_bootstrap_del_aporte

    assert intervalo_bootstrap_del_aporte([1, 1, 1], [0.2, 0.5, 0.9], [10, 20, 30]) is None


IC_AUC = {"inferior": 0.93, "superior": 0.97}


def test_un_aporte_cuyo_intervalo_baja_del_minimo_no_se_publica():
    from train_model import motivo_para_no_publicar

    motivo = motivo_para_no_publicar(
        0.94, 0.0277, IC_AUC, 200, intervalo_aporte={"inferior": -0.0015, "superior": 0.0587}
    )
    assert motivo is not None and "aporte" in motivo and "limite inferior" in motivo


def test_sin_intervalo_del_aporte_no_se_publica():
    from train_model import motivo_para_no_publicar

    assert motivo_para_no_publicar(0.94, 0.05, IC_AUC, 200, intervalo_aporte=None) is not None


def test_el_intervalo_del_aporte_no_se_puede_omitir():
    """Obligatorio y sin valor por defecto: omitirlo no puede volver a la estimación puntual."""
    from train_model import motivo_para_no_publicar

    with pytest.raises(TypeError):
        motivo_para_no_publicar(0.94, 0.05, IC_AUC, 200)


def test_un_modelo_con_aporte_incierto_no_se_escribe(tmp_path):
    """
    Sin sustituir el intervalo: 1000 filas dan un aporte puntual de +0.028, que pasaba, con
    un IC [-0.002, +0.059] que admite un modelo que no mejora la regla.
    """
    import train_model
    from synthetic_generator import generate_synthetic_leads_dataset

    cohorte = generate_synthetic_leads_dataset(num_samples=1000, random_seed=7)
    metricas = train_model.entrenar(
        cohorte, origen="realimentacion", procedencia={},
        publicar=True, directorio_modelos=str(tmp_path),
    )

    assert metricas["passed"] is True
    assert metricas["roc_auc_ic95"]["inferior"] >= metricas["auc_threshold"]
    assert metricas["delta_sobre_heuristico_ic95"]["inferior"] < metricas["min_delta_sobre_heuristico"]
    assert metricas["publicado"] is False
    assert "aporte" in metricas["motivo_no_publicable"]
    assert not (tmp_path / "lead_scorer_model.joblib").exists()


# ============================================================================
# El artefacto publicado
# ============================================================================
def test_lo_publicado_cumple_los_dos_intervalos():
    metricas = _json("metrics.json")
    assert metricas["publicado"] is True
    assert metricas["version_del_vector"] == VERSION_DEL_VECTOR
    assert metricas["roc_auc_ic95"]["inferior"] >= metricas["auc_threshold"]
    assert metricas["delta_sobre_heuristico_ic95"]["inferior"] >= metricas["min_delta_sobre_heuristico"]


def test_perfil_y_registro_son_del_vector_vigente():
    metricas = _json("metrics.json")
    perfil = _json("reference_profile.json")
    assert perfil["version_del_vector"] == VERSION_DEL_VECTOR
    assert perfil["model_sha256"] == metricas["model_sha256"]
    assert set(perfil["columnas"]) == set(COLUMNAS_DEL_MODELO)

    entrada = [e for e in _json("registry.json") if e.get("model_sha256") == metricas["model_sha256"]][-1]
    assert entrada["publicado"] is True
    assert entrada["version_del_vector"] == VERSION_DEL_VECTOR
    assert entrada["columnas"] == COLUMNAS_DEL_MODELO
    assert entrada["delta_sobre_heuristico_ic95"] == metricas["delta_sobre_heuristico_ic95"]


def test_un_artefacto_de_otro_vector_no_se_usa(tmp_path):
    """
    Con el artefacto del vector 1 y el código del 2, `predict_proba` fallaría en cada petición y
    la inferencia caería en silencio al cálculo de contingencia, anotada como `ml:<huella>`.
    """
    from sklearn.dummy import DummyClassifier

    antiguo = DummyClassifier().fit(pd.DataFrame({"phone_calls": [0, 1], "whatsapp_messages": [1, 0]}), [0, 1])
    ruta = tmp_path / "lead_scorer_model.joblib"
    joblib.dump(antiguo, ruta)

    adaptador = NativeMLScoringAdapter(model_path=str(ruta), expected_sha256="")
    assert adaptador.model is None
    assert adaptador.version_del_motor() == "heuristico"
