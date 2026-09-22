"""
Alineación del vector de variables y bucle de realimentación.

Dos cosas distintas que comparten motivo: evitar que el sistema aparente aprender más de
lo que aprende.

* **ML-4.** El backend calculaba `proposal_sent`, `meeting_scheduled`, `phone_calls` y
  `whatsapp_messages` desde las actividades del prospecto, pero no se los pasaba al
  clasificador: las señales más informativas del embudo solo movían la mitad heurística
  del score. Fue una divergencia silenciosa entre tres listas que nadie comparaba.

* **Realimentación.** Construir el dataset de reentrenamiento a partir del estado actual
  de los prospectos produce fuga de información: un prospecto ganado lleva, por
  definición, la propuesta y la reunión que llevaron al cierre.
"""
import datetime
from pathlib import Path

import pytest
from app.models.entities import Lead, LeadStatus, ScoreCategory, ScoreHistory

RAIZ = Path(__file__).resolve().parents[2]


# ==============================================================================
# ML-4: las tres listas de variables no pueden divergir
# ==============================================================================

def _variables_del_adaptador() -> list:
    """Las claves de la fila que construye el adaptador, en su orden, llamándolo."""
    from app.adapters.azure_ml_adapter import NativeMLScoringAdapter

    return list(NativeMLScoringAdapter.construir_fila({}).keys())


def _variables_del_preprocesador() -> set:
    """Las columnas que el preprocesador selecciona de verdad, leídas del objeto construido."""
    from feature_engineering import build_preprocessor

    columnas = set()
    for _, _, seleccion in build_preprocessor().transformers:
        columnas.update(seleccion)
    return columnas


def _variables_del_entrenamiento() -> list:
    """
    La lista que entra al entrenamiento, importada y no leída del texto del archivo.

    Antes las tres listas se leían del fuente con expresiones regulares. Desde el capítulo 24
    las tres salen de `app.core.vector_del_modelo`, y leerlas del texto ya no diría nada:
    se comprueban los objetos que se ejecutan.
    """
    from train_model import FEATURE_COLS

    return list(FEATURE_COLS)


def test_el_adaptador_pasa_exactamente_lo_que_el_modelo_espera():
    """
    El vector que construye el adaptador en producción debe coincidir con el que se
    entrenó. Cuando divergen, scikit-learn no protesta —el preprocesador ignora columnas
    de más y falla o imputa las de menos—, así que el sistema sigue puntuando con un
    modelo que ve menos de lo que cree ver.
    """
    from app.core.vector_del_modelo import COLUMNAS_DEL_MODELO

    adaptador = _variables_del_adaptador()
    preprocesador = _variables_del_preprocesador()

    assert adaptador == COLUMNAS_DEL_MODELO
    assert set(adaptador) == preprocesador, (
        f"faltan en el adaptador: {sorted(preprocesador - set(adaptador))}; "
        f"sobran en el adaptador: {sorted(set(adaptador) - preprocesador)}"
    )


def test_el_entrenamiento_usa_las_mismas_variables_que_el_preprocesador():
    assert set(_variables_del_entrenamiento()) == _variables_del_preprocesador()


@pytest.mark.parametrize(
    "variable",
    [
        "meeting_scheduled",
        "proposal_sent",
        "phone_calls_connected",
        "phone_calls_unanswered",
        "whatsapp_messages",
        "linkedin_messages",
    ],
)
def test_las_senales_de_compra_llegan_al_modelo(variable):
    """
    Comprobación nominal de las señales comerciales.

    Se nombran una a una y no solo por el conjunto: si alguien recorta la lista, el
    informe debe decir cuál se perdió, no solo que los conjuntos difieren.
    """
    assert variable in _variables_del_adaptador()
    assert variable in _variables_del_preprocesador()
    assert variable in _variables_del_entrenamiento()


def test_el_dataset_sintetico_no_publica_la_probabilidad_latente():
    """
    `latent_prob` es la probabilidad con la que se fabrica la etiqueta: la respuesta del
    examen. Publicarla en el CSV dejaba a quien reentrenara desde ese archivo a un paso de
    un modelo con fuga de información y precisión aparente casi perfecta.
    """
    from synthetic_generator import generate_synthetic_leads_dataset

    df = generate_synthetic_leads_dataset(num_samples=50, random_seed=1)

    assert "latent_prob" not in df.columns
    assert "converted" in df.columns


# ==============================================================================
# La instantánea de variables se persiste al puntuar
# ==============================================================================

def test_puntuar_guarda_la_instantanea_de_variables(client, lead_headers, db_session):
    """
    Sin instantánea no hay reentrenamiento honesto posible: es el único registro de qué
    se sabía del prospecto ANTES de conocer su desenlace.
    """
    nuevo = {
        "first_name": "Instantánea",
        "last_name": "Registrada",
        "email": "instantanea.registrada@empresa.mx",
        "company": "Empresa MX",
        "job_title": "CTO",
        "industry": "FinTech",
        "company_size": "1000+",
    }
    respuesta = client.post("/api/v1/leads", json=nuevo, headers=lead_headers)
    assert respuesta.status_code in (200, 201)

    lead_id = respuesta.json()["id"]
    historial = (
        db_session.query(ScoreHistory)
        .filter(ScoreHistory.lead_id == lead_id)
        .order_by(ScoreHistory.calculated_at.asc())
        .first()
    )

    assert historial is not None
    assert historial.feature_snapshot, "la instantánea quedó vacía"
    for variable in ("page_views", "requested_demo", "proposal_sent", "days_since_last_activity"):
        assert variable in historial.feature_snapshot


# ==============================================================================
# Extracción del dataset con desenlaces reales
# ==============================================================================

def _lead_con_desenlace(db_session, email, estado, instantanea, momento=None):
    """Crea un prospecto en estado terminal con una instantánea de entrada asociada."""
    momento = momento or datetime.datetime.now(datetime.timezone.utc)
    lead = Lead(
        first_name="Caso",
        last_name="Terminal",
        email=email,
        company="Empresa",
        job_title="CTO",
        industry="FinTech",
        company_size="1000+",
        annual_revenue=5_000_000.0,
        source="LinkedIn Ads",
        status=estado,
        current_score=70.0,
        score_category=ScoreCategory.WARM,
    )
    db_session.add(lead)
    db_session.flush()
    db_session.add(
        ScoreHistory(
            lead_id=lead.id,
            score=70.0,
            score_category=ScoreCategory.WARM,
            ml_probability=0.6,
            heuristic_score=70.0,
            decay_factor=1.0,
            feature_snapshot=instantanea,
            calculated_at=momento,
        )
    )
    db_session.commit()
    return lead


INSTANTANEA_DE_ENTRADA = {
    "page_views": 5,
    "email_opens": 3,
    "email_clicks": 1,
    "content_downloads": 0,
    "attended_webinar": 0,
    "requested_demo": 0,
    # Clave del asunto: al ENTRAR al embudo nadie tiene propuesta ni reunión.
    "meeting_scheduled": 0,
    "proposal_sent": 0,
    "phone_calls_connected": 0,
    "phone_calls_unanswered": 0,
    "whatsapp_messages": 0,
    "linkedin_messages": 0,
    "days_since_last_activity": 2.0,
    "version_del_vector": 2,
}


def test_el_dataset_se_construye_desde_la_instantanea_no_desde_el_estado_actual(db_session):
    """
    El prospecto está GANADO y hoy tiene propuesta y reunión; su fila debe llevar los
    ceros del momento de entrada.

    Es la comprobación central del bucle: si el extractor leyera el estado actual, el
    modelo aprendería que enviar propuestas causa cierres —la relación invertida— y sería
    inútil justo cuando hay que decidir a quién llamar, que es antes de enviar nada.
    """
    from feedback_dataset import construir_dataset

    lead = _lead_con_desenlace(
        db_session, "ganado.con.propuesta@empresa.mx", LeadStatus.WON, INSTANTANEA_DE_ENTRADA
    )
    # El prospecto avanza: hoy tiene propuesta y reunión, como todo prospecto ganado.
    db_session.add(
        ScoreHistory(
            lead_id=lead.id,
            score=95.0,
            score_category=ScoreCategory.HOT,
            ml_probability=0.95,
            heuristic_score=95.0,
            decay_factor=1.0,
            feature_snapshot={**INSTANTANEA_DE_ENTRADA, "proposal_sent": 1, "meeting_scheduled": 1},
            calculated_at=datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(days=30),
        )
    )
    db_session.commit()

    df, _ = construir_dataset(db=db_session, exigir_minimos=False)
    fila = df[df["lead_id"] == lead.id].iloc[0]

    assert fila["converted"] == 1
    assert fila["proposal_sent"] == 0, "se coló el estado posterior al desenlace"
    assert fila["meeting_scheduled"] == 0


def test_los_prospectos_en_curso_no_cuentan_como_perdidos(db_session, sample_leads):
    """
    Un prospecto en negociación no es un fracaso: es un resultado que aún no se conoce.

    Contar la censura por la derecha como negativo es el error más común al montar estos
    bucles y sesga el modelo hacia el pesimismo precisamente en los prospectos más activos.
    """
    from feedback_dataset import construir_dataset

    _lead_con_desenlace(
        db_session, "aun.negociando@empresa.mx", LeadStatus.NEGOTIATION, INSTANTANEA_DE_ENTRADA
    )
    _lead_con_desenlace(
        db_session, "perdido.de.verdad@empresa.mx", LeadStatus.LOST, INSTANTANEA_DE_ENTRADA
    )

    df, manifiesto = construir_dataset(db=db_session, exigir_minimos=False)

    correos_incluidos = set(
        db_session.query(Lead.email).filter(Lead.id.in_(df["lead_id"].tolist())).all()
    )
    correos_incluidos = {c[0] for c in correos_incluidos}

    assert "perdido.de.verdad@empresa.mx" in correos_incluidos
    assert "aun.negociando@empresa.mx" not in correos_incluidos
    assert manifiesto["prospectos_en_curso_excluidos"] >= 1


def test_los_descartados_cuentan_como_negativos(db_session):
    """`UNQUALIFIED` es una decisión tomada, no una ausencia de decisión."""
    from feedback_dataset import construir_dataset

    lead = _lead_con_desenlace(
        db_session, "descartado@empresa.mx", LeadStatus.UNQUALIFIED, INSTANTANEA_DE_ENTRADA
    )

    df, _ = construir_dataset(db=db_session, exigir_minimos=False)
    assert df[df["lead_id"] == lead.id].iloc[0]["converted"] == 0


def test_un_terminal_sin_instantanea_se_descarta(db_session):
    """
    Las filas anteriores a que existiera la instantánea no pueden fabricársela.

    Rellenarlas con el estado actual sería exactamente la fuga que este diseño evita, así
    que se descartan y se contabilizan en el manifiesto para que la merma sea visible.
    """
    from feedback_dataset import construir_dataset

    lead = Lead(
        first_name="Sin",
        last_name="Instantanea",
        email="sin.instantanea@empresa.mx",
        company="Empresa",
        status=LeadStatus.WON,
        current_score=80.0,
        score_category=ScoreCategory.HOT,
    )
    db_session.add(lead)
    db_session.commit()

    df, manifiesto = construir_dataset(db=db_session, exigir_minimos=False)

    assert df.empty or lead.id not in set(df["lead_id"])
    assert manifiesto["terminales_sin_instantanea_utilizable"] >= 1


def test_reentrenar_con_pocos_datos_se_rechaza(db_session):
    """
    Con unas decenas de ejemplos el modelo memoriza los clientes concretos del periodo.
    El extractor prefiere no producir dataset a producir uno que invite a reentrenar mal.
    """
    from feedback_dataset import DatasetInsuficiente, construir_dataset

    _lead_con_desenlace(
        db_session, "unico.caso@empresa.mx", LeadStatus.WON, INSTANTANEA_DE_ENTRADA
    )

    with pytest.raises(DatasetInsuficiente):
        construir_dataset(db=db_session, exigir_minimos=True)


def test_el_manifiesto_acompana_siempre_al_dataset(db_session):
    """Sin ventana temporal ni balance de clases, una métrica sobre el dataset no se interpreta."""
    from feedback_dataset import construir_dataset

    _lead_con_desenlace(db_session, "uno@empresa.mx", LeadStatus.WON, INSTANTANEA_DE_ENTRADA)
    _lead_con_desenlace(db_session, "dos@empresa.mx", LeadStatus.LOST, INSTANTANEA_DE_ENTRADA)

    _, manifiesto = construir_dataset(db=db_session, exigir_minimos=False)

    for clave in ("ejemplos", "positivos_won", "tasa_de_conversion", "ventana", "advertencia"):
        assert clave in manifiesto
    assert manifiesto["ventana"]["desde"] is not None


def test_la_huella_del_dataset_cambia_con_los_datos(db_session):
    """
    La huella liga un modelo a los datos exactos con que se entrenó. Si no cambiara al
    cambiar los datos, no serviría para rastrear una métrica sorprendente hasta su origen.
    """
    from feedback_dataset import COLUMNAS_MODELO, construir_dataset, huella_del_dataset

    _lead_con_desenlace(db_session, "primero@empresa.mx", LeadStatus.WON, INSTANTANEA_DE_ENTRADA)
    df1, _ = construir_dataset(db=db_session, exigir_minimos=False)
    huella1 = huella_del_dataset(df1[COLUMNAS_MODELO + ["converted"]])

    _lead_con_desenlace(db_session, "segundo@empresa.mx", LeadStatus.LOST, INSTANTANEA_DE_ENTRADA)
    df2, _ = construir_dataset(db=db_session, exigir_minimos=False)
    huella2 = huella_del_dataset(df2[COLUMNAS_MODELO + ["converted"]])

    assert huella1 != huella2
    assert len(huella1) == 64
