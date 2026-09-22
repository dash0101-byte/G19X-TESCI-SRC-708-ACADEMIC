"""
N-26 y N-27: dos convenciones del gobierno del modelo convertidas en condiciones (§18.9).

* **El perfil de referencia y el artefacto podían desincronizarse.** Salían del mismo
  entrenamiento, pero nada lo dejaba escrito ni lo comprobaba. Un perfil de una ejecución y
  un `.joblib` de otra hacen que el monitor compare producción contra la población de otro
  modelo, y el PSI sigue saliendo con el mismo aspecto. Ahora el perfil lleva la huella del
  artefacto y el monitor se niega a evaluar si no coincide.

* **`--publicar` no exigía mirar el intervalo de confianza.** Dependía de que quien lo
  escribiera hubiera leído la tabla. Ahora el límite inferior del IC 95 % tiene que alcanzar
  el umbral, o el artefacto no se escribe.
"""
import hashlib
import json
import os

import drift_monitor
import pytest
from drift_monitor import verificar_vinculo
from model_registry import leer_registro

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODELOS = os.path.join(RAIZ, "ml_pipeline", "models")

INTERVALO_HOLGADO = {"inferior": 0.93, "superior": 0.97, "remuestreos_validos": 2000}
INTERVALO_CORTO = {"inferior": 0.60, "superior": 0.99, "remuestreos_validos": 2000}
APORTE_HOLGADO = {"inferior": 0.03, "superior": 0.07, "remuestreos_validos": 2000}


def _sha(ruta) -> str:
    with open(ruta, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


@pytest.fixture(scope="module")
def cohorte():
    from synthetic_generator import generate_synthetic_leads_dataset

    # 1500: con 400 el aporte sobre el heurístico es ruido (véase test_gobierno_del_modelo).
    return generate_synthetic_leads_dataset(num_samples=1500, random_seed=7)


# ============================================================================
# N-26 — El perfil sabe de qué artefacto salió
# ============================================================================
@pytest.fixture(scope="module")
def publicacion(tmp_path_factory, cohorte):
    """
    Una publicación completa en un directorio desechable.

    Se fija el intervalo holgado porque lo que se prueba aquí es el vínculo, no la
    decisión de publicar: con 80 ejemplos de prueba el intervalo real puede quedar por
    debajo del umbral —que es precisamente lo que N-27 impide publicar—.
    """
    import train_model

    directorio = tmp_path_factory.mktemp("publicacion")
    original = train_model.intervalo_bootstrap
    original_aporte = train_model.intervalo_bootstrap_del_aporte
    train_model.intervalo_bootstrap = lambda *a, **k: dict(INTERVALO_HOLGADO)
    train_model.intervalo_bootstrap_del_aporte = lambda *a, **k: dict(APORTE_HOLGADO)
    try:
        metricas = train_model.entrenar(
            cohorte, origen="sinteticos", procedencia={"semilla": 7},
            publicar=True, directorio_modelos=str(directorio),
        )
    finally:
        train_model.intervalo_bootstrap = original
        train_model.intervalo_bootstrap_del_aporte = original_aporte
    return directorio, metricas


def test_el_perfil_publicado_lleva_la_huella_del_artefacto(publicacion):
    directorio, metricas = publicacion
    assert metricas["publicado"] is True

    with open(directorio / "reference_profile.json", encoding="utf-8") as fh:
        perfil = json.load(fh)

    artefacto = directorio / "lead_scorer_model.joblib"
    assert perfil["model_sha256"] == _sha(artefacto) == metricas["model_sha256"]
    assert perfil["huella_datos_sha256"] == metricas["huella_datos_sha256"]
    assert verificar_vinculo(perfil, str(artefacto)) is None


def test_un_perfil_de_otro_artefacto_se_rechaza(tmp_path):
    artefacto = tmp_path / "modelo.joblib"
    artefacto.write_bytes(b"el modelo que esta puntuando")
    perfil = {"model_sha256": hashlib.sha256(b"otro modelo").hexdigest(), "columnas": {}}

    problema = verificar_vinculo(perfil, str(artefacto))

    assert problema is not None
    assert perfil["model_sha256"][:12] in problema
    assert _sha(artefacto)[:12] in problema


def test_un_perfil_sin_huella_se_rechaza_en_lugar_de_darse_por_bueno(tmp_path):
    """
    Es el caso que hay que forzar a regenerar, no el que hay que tolerar por no poder
    comprobarlo: un perfil anterior a la Fase 13 no dice de qué modelo salió.
    """
    artefacto = tmp_path / "modelo.joblib"
    artefacto.write_bytes(b"modelo")
    problema = verificar_vinculo({"columnas": {}}, str(artefacto))
    assert problema is not None and "model_sha256" in problema


def test_sin_artefacto_no_se_puede_dar_por_bueno(tmp_path):
    perfil = {"model_sha256": "a" * 64, "columnas": {}}
    assert verificar_vinculo(perfil, str(tmp_path / "no_existe.joblib")) is not None


class _ElBucleArranco(Exception):
    pass


@pytest.mark.parametrize("modo", [[], ["--cada", "5"]], ids=["una-vez", "en-bucle"])
def test_el_monitor_no_lee_produccion_con_un_perfil_ajeno(tmp_path, monkeypatch, capsys, modo):
    """
    Se comprueba ANTES de leer una sola instantánea, también en modo servicio.

    En bucle, un monitor que empezara a evaluar con un perfil ajeno produciría informes
    cada seis horas con un aspecto impecable. Si la comprobación se moviera dentro del
    bucle —donde sus excepciones se atrapan y se reintenta—, el `sleep` saltaría y esta
    prueba fallaría en lugar de colgarse.
    """
    artefacto = tmp_path / "modelo.joblib"
    artefacto.write_bytes(b"el desplegado")
    ruta_perfil = tmp_path / "perfil.json"
    ruta_perfil.write_text(json.dumps({
        "model_sha256": hashlib.sha256(b"el de otro entrenamiento").hexdigest(),
        "columnas": {},
    }), encoding="utf-8")

    def _no_debe_leerse(*_a, **_k):
        raise AssertionError("se leyeron instantaneas de produccion con un perfil ajeno")

    def _no_debe_dormir(*_a, **_k):
        raise _ElBucleArranco()

    monkeypatch.setattr(drift_monitor, "instantaneas_de_produccion", _no_debe_leerse)
    monkeypatch.setattr(drift_monitor.time, "sleep", _no_debe_dormir)

    codigo = drift_monitor.main([
        "--perfil", str(ruta_perfil), "--modelo", str(artefacto),
        "--alertar", "--estado", str(tmp_path / "estado.json"), *modo,
    ])

    assert codigo == 1
    assert "No se evalua" in capsys.readouterr().out


def test_el_perfil_desplegado_corresponde_al_artefacto_versionado():
    """
    El estado del repositorio, no solo el del código: lo que viaja en la imagen.

    El perfil versionado tiene que nombrar al `.joblib` versionado, y el registro tiene que
    tener esa publicación con la misma huella de datos. Si alguien sustituye uno de los tres
    archivos a mano, esto falla antes de construir la imagen.
    """
    with open(os.path.join(MODELOS, "reference_profile.json"), encoding="utf-8") as fh:
        perfil = json.load(fh)
    artefacto = os.path.join(MODELOS, "lead_scorer_model.joblib")

    assert verificar_vinculo(perfil, artefacto) is None

    publicaciones = [
        e for e in leer_registro(os.path.join(MODELOS, "registry.json"))
        if e.get("model_sha256") == perfil["model_sha256"] and e.get("publicado")
    ]
    assert publicaciones, "el artefacto desplegado no aparece publicado en el registro"
    assert publicaciones[-1]["huella_datos_sha256"] == perfil["huella_datos_sha256"]


# ============================================================================
# N-27 — Publicar exige el intervalo
# ============================================================================
def test_el_ensayo_de_45_desenlaces_no_se_habria_publicado():
    """
    Las cifras reales del ensayo del bucle (§18.4): la estimación puntual pasaba el umbral,
    y el intervalo admitía un modelo muy por debajo de él.
    """
    from train_model import motivo_para_no_publicar

    motivo = motivo_para_no_publicar(
        0.8889, 0.05, {"inferior": 0.571, "superior": 1.0}, 9, intervalo_aporte=dict(APORTE_HOLGADO)
    )
    assert motivo is not None and "limite inferior" in motivo


def test_con_miles_de_ejemplos_el_intervalo_no_estorba():
    """Con los datos sintéticos el límite inferior queda en 0.93: la condición no cuesta nada."""
    from train_model import motivo_para_no_publicar

    assert motivo_para_no_publicar(
        0.9469, 0.0519, {"inferior": 0.9275, "superior": 0.9635}, 600,
        intervalo_aporte={"inferior": 0.0296, "superior": 0.0761},
    ) is None


def test_sin_intervalo_no_se_publica():
    """Una sola clase en la partición de prueba, o muy pocos ejemplos: no hay nada que mirar."""
    from train_model import motivo_para_no_publicar

    assert motivo_para_no_publicar(0.95, 0.05, None, 6, intervalo_aporte=dict(APORTE_HOLGADO)) is not None


@pytest.mark.parametrize(
    ("auc", "delta"), [(0.70, 0.05), (0.95, 0.001)], ids=["umbral", "aporte"]
)
def test_los_umbrales_de_siempre_siguen_mandando(auc, delta):
    from train_model import motivo_para_no_publicar

    assert motivo_para_no_publicar(
        auc, delta, dict(INTERVALO_HOLGADO), 600, intervalo_aporte=dict(APORTE_HOLGADO)
    ) is not None


def test_pedir_publicar_con_un_intervalo_corto_no_escribe_el_artefacto(tmp_path, cohorte, monkeypatch):
    """
    Pasa los umbrales, se pide publicar, y no se publica.

    Es el caso exacto que antes dependía de que alguien mirase la tabla.
    """
    import train_model

    monkeypatch.setattr(train_model, "intervalo_bootstrap", lambda *a, **k: dict(INTERVALO_CORTO))
    monkeypatch.setattr(train_model, "intervalo_bootstrap_del_aporte", lambda *a, **k: dict(APORTE_HOLGADO))
    metricas = train_model.entrenar(
        cohorte, origen="realimentacion", procedencia={},
        publicar=True, directorio_modelos=str(tmp_path),
    )

    assert metricas["passed"] is True, "la cohorte deberia superar los umbrales puntuales"
    assert metricas["publicable"] is False
    assert metricas["publicado"] is False
    assert "limite inferior" in metricas["motivo_no_publicable"]
    assert not (tmp_path / "lead_scorer_model.joblib").exists()
    assert not (tmp_path / "reference_profile.json").exists()
    assert leer_registro(str(tmp_path / "registry.json"))[-1]["publicado"] is False


@pytest.mark.parametrize(
    ("intervalo", "codigo"), [(INTERVALO_CORTO, 1), (INTERVALO_HOLGADO, 0)], ids=["corto", "holgado"]
)
def test_la_orden_falla_cuando_se_pidio_publicar_y_no_se_pudo(
    tmp_path, cohorte, monkeypatch, intervalo, codigo
):
    """
    El código de salida es lo que convierte el criterio en una puerta para quien lo
    automatice. Antes salía 0 con cualquier modelo que pasara los umbrales puntuales.
    """
    import train_model

    datos = tmp_path / "leads_reales.csv"
    cohorte.to_csv(datos, index=False)
    # Los modelos se resuelven relativos al directorio del módulo: se desvían al temporal
    # para que esta prueba no escriba en el registro ni en el artefacto de producción.
    monkeypatch.setattr(train_model, "current_dir", str(tmp_path / "src"))
    monkeypatch.setattr(train_model, "intervalo_bootstrap", lambda *a, **k: dict(intervalo))
    monkeypatch.setattr(train_model, "intervalo_bootstrap_del_aporte", lambda *a, **k: dict(APORTE_HOLGADO))

    assert train_model.main(["--datos", "realimentacion", "--dataset", str(datos), "--publicar"]) == codigo
    assert (tmp_path / "models" / "lead_scorer_model.joblib").exists() is (codigo == 0)
