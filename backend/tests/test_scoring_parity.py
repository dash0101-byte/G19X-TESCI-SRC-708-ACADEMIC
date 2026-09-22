"""
Paridad entre las dos rutas de cálculo del heurístico.

El heurístico ICP existía duplicado palabra por palabra en el servicio de scoring y en
el pipeline de entrenamiento. Dos copias que nadie obligaba a coincidir: el modelo se
entrenaba con una definición de "buen prospecto" y luego se evaluaba a los prospectos
reales con otra, y la divergencia era silenciosa —ningún test fallaba, los scores
simplemente dejaban de significar lo mismo—.

Ahora ambas rutas entran al mismo módulo (`app.core.scoring_rules`). Estas pruebas
fijan esa condición: si alguien vuelve a copiar las reglas en cualquiera de los dos
lados, la comparación deja de cuadrar y la suite lo dice.
"""
import pytest
from app.core.config import settings
from app.core.scoring_rules import HeuristicParams
from app.services.scoring_service import ScoringService

from ml_pipeline.src.feature_engineering import (
    calculate_heuristic_score as pipeline_heuristic,
)
from ml_pipeline.src.feature_engineering import (
    calculate_temporal_decay as pipeline_decay,
)

# Perfiles elegidos para tocar cada tramo de las tablas de reglas y cada rama del
# cálculo: firmográfico alto y bajo, comportamiento saturado y vacío, con y sin
# decaimiento, con y sin campos personalizados.
PERFILES = [
    pytest.param(
        {
            "job_title": "CTO & Co-Founder",
            "industry": "FinTech",
            "company_size": "1000+",
            "page_views": 15,
            "email_opens": 8,
            "email_clicks": 4,
            "downloads": 3,
            "requested_demo": True,
            "attended_webinar": True,
            "days_inactive": 0.0,
        },
        id="perfil-ideal-activo",
    ),
    pytest.param(
        {
            "job_title": "Estudiante de Informática",
            "industry": "Educación Básica",
            "company_size": "1-10",
            "days_inactive": 30.0,
        },
        id="perfil-minimo-inactivo",
    ),
    pytest.param(
        {
            "job_title": "Gerente de Talento",
            "industry": "Retail & E-Commerce",
            "company_size": "51-200",
            "page_views": 4,
            "email_clicks": 2,
            "proposal_sent": True,
            "meeting_scheduled": True,
            "phone_calls": 3,
            "whatsapp_messages": 1,
            "linkedin_messages": 1,
            "custom_events": 1,
            "days_inactive": 7.0,
        },
        id="comportamiento-comercial-saturado",
    ),
    pytest.param(
        {
            "job_title": "Analista de Sistemas",
            "industry": "Industria inventada que no está en ninguna tabla",
            "company_size": "201-500",
            "email_opens": 3,
            "days_inactive": 14.0,
            "custom_metadata": {"urgency": "INMEDIATA"},
        },
        id="industria-libre-con-urgencia",
    ),
    pytest.param(
        {
            "job_title": "",
            "industry": "",
            "company_size": "",
            "days_inactive": 45.0,
        },
        id="campos-vacios",
    ),
]


@pytest.fixture(scope="module")
def service():
    """
    El servicio no toca la base de datos para calcular el heurístico.

    De ámbito de módulo porque construirlo carga el artefacto .joblib del modelo; los
    parámetros de calibración se releen en cada acceso, así que reutilizar la instancia
    no oculta los cambios que hacen los tests sobre `settings`.
    """
    return ScoringService(db=None)


@pytest.mark.parametrize("perfil", PERFILES)
def test_ambas_rutas_producen_el_mismo_heuristico(service, perfil):
    """
    La ruta de producción (servicio web) y la de entrenamiento (pipeline ML) deben
    coincidir en el score, en el desglose completo y en el factor de decaimiento.
    """
    score_servicio, desglose_servicio, decay_servicio = service.compute_heuristic_score(**perfil)
    score_pipeline, desglose_pipeline, decay_pipeline = pipeline_heuristic(**perfil)

    assert score_servicio == score_pipeline
    assert desglose_servicio == desglose_pipeline
    assert decay_servicio == decay_pipeline


@pytest.mark.parametrize("dias", [0.0, 7.0, 14.0, 28.0, 45.0])
def test_ambas_rutas_aplican_el_mismo_decaimiento(service, dias):
    assert service.calculate_temporal_decay(dias) == pipeline_decay(
        dias, half_life_days=settings.DECAY_HALF_LIFE_DAYS
    )


def test_el_servicio_respeta_la_vida_media_configurada(service, monkeypatch):
    """
    Recalibrar `DECAY_HALF_LIFE_DAYS` debe mover el cálculo.

    Es exactamente el punto por el que las dos copias habían divergido: el servicio leía
    la vida media de `settings` y el pipeline la tenía escrita a fuego en 14.0, así que
    tocar la configuración cambiaba una ruta y dejaba la otra intacta.
    """
    monkeypatch.setattr(settings, "DECAY_HALF_LIFE_DAYS", 7.0)

    # Con vida media de 7 días, 7 días de inactividad son exactamente media vida.
    assert round(service.calculate_temporal_decay(7.0), 4) == 0.5
    assert service.params.half_life_days == 7.0

    # Y el pipeline, invocado con esos mismos parámetros, coincide.
    params = HeuristicParams.from_settings()
    _, desglose_servicio, _ = service.compute_heuristic_score(
        job_title="CTO", industry="FinTech", company_size="1000+",
        requested_demo=True, days_inactive=7.0,
    )
    _, desglose_pipeline, _ = pipeline_heuristic(
        job_title="CTO", industry="FinTech", company_size="1000+",
        requested_demo=True, days_inactive=7.0, params=params,
    )
    assert desglose_servicio == desglose_pipeline
    assert desglose_servicio["decay_factor"] == 0.5


def test_los_pesos_de_fusion_provienen_de_settings(service, monkeypatch):
    """La calibración de los pesos llega al servicio sin reiniciar el proceso."""
    monkeypatch.setattr(settings, "SCORE_WEIGHT_ML", 0.25)
    monkeypatch.setattr(settings, "SCORE_WEIGHT_HEURISTIC", 0.75)

    assert service.params.weight_ml == 0.25
    assert service.params.weight_heuristic == 0.75
