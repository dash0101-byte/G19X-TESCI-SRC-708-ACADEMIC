from ml_pipeline.src.feature_engineering import calculate_heuristic_score, calculate_temporal_decay


def test_temporal_decay_mathematical_precision():
    """Valida la precisión matemática de la función de decaimiento exponencial continuo."""
    # En t = 0 días, no hay decaimiento (factor = 1.0)
    assert calculate_temporal_decay(0.0) == 1.0
    assert calculate_temporal_decay(-5.0) == 1.0

    # En t = 14 días (vida media), el factor debe ser exactamente 0.50
    assert round(calculate_temporal_decay(14.0, half_life_days=14.0), 4) == 0.5000

    # En t = 7 días, el factor debe ser 1/sqrt(2) approx 0.7071
    assert round(calculate_temporal_decay(7.0, half_life_days=14.0), 4) == 0.7071

    # En t = 28 días (2 vidas medias), el factor debe ser 0.25
    assert round(calculate_temporal_decay(28.0, half_life_days=14.0), 4) == 0.2500

    # En t = 42 días (3 vidas medias), el factor debe ser 0.125
    assert round(calculate_temporal_decay(42.0, half_life_days=14.0), 4) == 0.1250


def test_heuristic_icp_rules_and_bounds():
    """Valida que las reglas de ajuste de perfil cumplan los límites superiores e inferiores."""
    # Caso 1: Perfil Ideal Máximo (CTO + FinTech + 1000+ + Demo + Webinar + Descargas) activo hoy
    score_max, breakdown_max, decay_max = calculate_heuristic_score(
        job_title="CTO & Co-Founder",
        industry="FinTech",
        company_size="1000+",
        page_views=15,
        email_opens=8,
        email_clicks=4,
        downloads=3,
        requested_demo=True,
        attended_webinar=True,
        days_inactive=0.0,
    )
    assert decay_max == 1.0
    assert breakdown_max["firmographic_total"] == 50.0  # 25 + 15 + 10
    assert breakdown_max["behavior_raw_total"] == 50.0  # Cap de 50 pts
    assert score_max == 100.0

    # Caso 2: Mismo perfil ideal pero inactivo hace 28 días
    score_decayed, breakdown_decayed, decay_val = calculate_heuristic_score(
        job_title="CTO & Co-Founder",
        industry="FinTech",
        company_size="1000+",
        page_views=15,
        email_opens=8,
        email_clicks=4,
        downloads=3,
        requested_demo=True,
        attended_webinar=True,
        days_inactive=28.0,
    )
    assert decay_val == 0.25
    # Firmográfico se mantiene (50.0), pero conductual decae a 50 * 0.25 = 12.5
    assert breakdown_decayed["firmographic_total"] == 50.0
    assert breakdown_decayed["behavior_decayed_total"] == 12.5
    assert score_decayed == 62.5

    # Caso 3: Prospecto de muy bajo ajuste (Estudiante + Industria no prioritaria + Sin interacciones)
    score_min, breakdown_min, _ = calculate_heuristic_score(
        job_title="Estudiante de Informática",
        industry="Educación Básica",
        company_size="1-10",
        page_views=0,
        days_inactive=30.0,
    )
    assert score_min <= 15.0
    assert breakdown_min["title_fit_score"] == 5.0
