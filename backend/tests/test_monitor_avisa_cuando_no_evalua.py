"""
§19.9: cuando el monitor se niega a evaluar, lo dice por el mismo canal que sus alertas.

Negarse con un perfil ajeno era correcto desde la Fase 13, pero solo quedaba en la salida del
contenedor. Un monitor que no vigila y no lo comunica deja al sistema aparentando vigilancia.
Lo que se comprueba: que la negativa llega a `ML_DRIFT_WEBHOOK`, que no se repite en cada
reinicio, que no filtra detalles de la base al receptor y que se avisa de la vuelta.
"""
import hashlib
import json

import drift_monitor
import pytest
from drift_monitor import (
    MOTIVO_EVALUACION_FALLIDA,
    MOTIVO_PERFIL_AJENO,
    MOTIVO_PERFIL_AUSENTE,
    MOTIVO_PERFIL_ILEGIBLE,
    procesar_alertas,
    procesar_negativa,
)


@pytest.fixture
def receptor(monkeypatch):
    """Lo que llega al webhook, ya decodificado. Nada sale a la red."""
    entregas = []

    class _Respuesta:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    def _urlopen(peticion, timeout=None):
        entregas.append(json.loads(peticion.data.decode("utf-8")))
        return _Respuesta()

    monkeypatch.setattr(drift_monitor, "WEBHOOK", "https://avisos.example.invalid/hook")
    monkeypatch.setattr(drift_monitor.urllib.request, "urlopen", _urlopen)
    return entregas


def _perfil_ajeno(tmp_path):
    artefacto = tmp_path / "modelo.joblib"
    artefacto.write_bytes(b"el desplegado")
    perfil = tmp_path / "perfil.json"
    perfil.write_text(json.dumps({
        "model_sha256": hashlib.sha256(b"el de otro entrenamiento").hexdigest(), "columnas": {},
    }), encoding="utf-8")
    return perfil, artefacto


def _argumentos(tmp_path, perfil, artefacto, *extra):
    return ["--perfil", str(perfil), "--modelo", str(artefacto), "--estado", str(tmp_path / "estado.json"), *extra]


def test_negarse_con_un_perfil_ajeno_avisa_por_el_webhook(tmp_path, receptor, capsys):
    perfil, artefacto = _perfil_ajeno(tmp_path)

    assert drift_monitor.main(_argumentos(tmp_path, perfil, artefacto, "--alertar")) == 1

    assert [(e["tipo"], e["motivo"]) for e in receptor] == [("sin_evaluar", MOTIVO_PERFIL_AJENO)]
    salida = capsys.readouterr().out
    assert "[DERIVA-SIN-EVALUAR]" in salida
    assert "No se evalua" in salida


def test_sin_alertar_la_negativa_no_sale_de_la_salida(tmp_path, receptor):
    perfil, artefacto = _perfil_ajeno(tmp_path)
    assert drift_monitor.main(_argumentos(tmp_path, perfil, artefacto)) == 1
    assert receptor == []


def test_un_perfil_ausente_o_ilegible_tambien_avisa(tmp_path, receptor):
    artefacto = tmp_path / "modelo.joblib"
    artefacto.write_bytes(b"m")
    roto = tmp_path / "roto.json"
    roto.write_text("{esto no es json", encoding="utf-8")

    assert drift_monitor.main(_argumentos(tmp_path, tmp_path / "no_existe.json", artefacto, "--alertar")) == 1
    assert drift_monitor.main(_argumentos(tmp_path, roto, artefacto, "--alertar")) == 1

    assert [e["motivo"] for e in receptor] == [MOTIVO_PERFIL_AUSENTE, MOTIVO_PERFIL_ILEGIBLE]


def test_la_misma_negativa_no_se_repite_en_cada_reinicio(tmp_path, receptor):
    """El proceso sale con 1 y Docker lo reinicia: sin memoria, cada reinicio sería un aviso."""
    perfil, artefacto = _perfil_ajeno(tmp_path)
    for _ in range(3):
        assert drift_monitor.main(_argumentos(tmp_path, perfil, artefacto, "--alertar")) == 1
    assert len(receptor) == 1


def test_la_negativa_se_repite_pasado_el_silencio_y_con_un_motivo_nuevo(tmp_path, receptor):
    ruta = str(tmp_path / "estado.json")
    silencio = drift_monitor.SILENCIO_ENTRE_ALERTAS

    assert procesar_negativa(ruta, MOTIVO_PERFIL_AJENO, "x", ahora=1000.0)
    assert not procesar_negativa(ruta, MOTIVO_PERFIL_AJENO, "x", ahora=1000.0 + silencio - 1)
    assert procesar_negativa(ruta, MOTIVO_PERFIL_AJENO, "x", ahora=1000.0 + silencio)
    assert procesar_negativa(ruta, MOTIVO_EVALUACION_FALLIDA, "x", ahora=1000.0 + silencio + 1)

    assert len(receptor) == 3
    # Cuánto lleva sin vigilancia se cuenta desde la primera negativa, aunque cambie el motivo.
    assert len({e["sin_evaluar_desde"] for e in receptor}) == 1


class _FinDelBucle(Exception):
    pass


def test_una_evaluacion_fallida_en_bucle_avisa_sin_filtrar_la_base(tmp_path, receptor, monkeypatch):
    artefacto = tmp_path / "modelo.joblib"
    artefacto.write_bytes(b"m")
    perfil = tmp_path / "perfil.json"
    perfil.write_text(json.dumps({"model_sha256": hashlib.sha256(b"m").hexdigest(), "columnas": {}}), encoding="utf-8")

    def base_caida(*_a, **_k):
        raise RuntimeError('connection to server at "postgres" port 5432 failed for user "plurione"')

    def parar(_segundos):
        raise _FinDelBucle

    monkeypatch.setattr(drift_monitor, "instantaneas_de_produccion", base_caida)
    monkeypatch.setattr(drift_monitor.time, "sleep", parar)

    with pytest.raises(_FinDelBucle):
        drift_monitor.main(_argumentos(tmp_path, perfil, artefacto, "--alertar", "--cada", "5"))

    assert [(e["motivo"], e["detalle"]) for e in receptor] == [(MOTIVO_EVALUACION_FALLIDA, "RuntimeError")]
    assert "plurione" not in json.dumps(receptor) and "5432" not in json.dumps(receptor)


def test_al_volver_a_evaluar_se_avisa_una_sola_vez(tmp_path, receptor):
    ruta = tmp_path / "estado.json"
    procesar_negativa(str(ruta), MOTIVO_EVALUACION_FALLIDA, "OperationalError", ahora=1000.0)
    estable = {"veredicto": "estable", "columnas_con_deriva": [], "por_columna": {}, "observaciones": 500, "evaluado_en": "t"}

    procesar_alertas(estable, str(ruta), ahora=2000.0)
    procesar_alertas(estable, str(ruta), ahora=3000.0)

    assert [e["tipo"] for e in receptor] == ["sin_evaluar", "evalua_de_nuevo"]
    assert receptor[1]["motivo_anterior"] == MOTIVO_EVALUACION_FALLIDA
    assert "sin_evaluar" not in json.loads(ruta.read_text(encoding="utf-8"))
