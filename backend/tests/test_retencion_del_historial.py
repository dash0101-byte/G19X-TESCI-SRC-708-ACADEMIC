"""
R-3: el historial de puntuación tiene plazo.

Lo que se comprueba no es solo que la purga borre. Es que borre SIN destruir lo que otras
piezas necesitan de ese historial —la instantánea de entrada del bucle de realimentación,
la puntuación vigente de la ficha— y que el resumen cuente exactamente lo que se fue, ni
una fila de más si dos pasadas coinciden ni una de menos si una fila llega tarde.
"""
import datetime

import pytest
from app.core.config import RETENCION_MINIMA_DEL_HISTORIAL_MESES, Settings
from app.models.entities import AuditLog, Lead, ScoreCategory, ScoreHistory, ScoreHistoryMonthly
from app.services import retencion_service
from app.services.retencion_service import (
    aplicar_retencion,
    consulta_instantanea_de_entrada,
    filas_protegidas,
    limite_de_retencion,
)
from pydantic import ValidationError
from sqlalchemy import delete, null

UTC = datetime.timezone.utc
AHORA = datetime.datetime(2026, 9, 10, 12, 0, tzinfo=UTC)


def _dia(anio, mes, dia, hora=9):
    return datetime.datetime(anio, mes, dia, hora, 0, tzinfo=UTC)


def _prospecto(db, n):
    lead = Lead(first_name="Titular", last_name=f"Numero {n}", email=f"retencion.{n}@ejemplo.com")
    db.add(lead)
    db.commit()
    return lead


def _puntuacion(db, lead, instante, score, *, categoria=ScoreCategory.WARM, instantanea=True, version="v1"):
    fila = ScoreHistory(
        lead_id=lead.id,
        score=score,
        score_category=categoria,
        model_version=version,
        # `null()` y no `None`: un None en una columna JSON se guarda como el texto 'null',
        # y las filas anteriores a la instantánea tienen NULL de verdad.
        feature_snapshot={"page_views": int(score)} if instantanea else null(),
        calculated_at=instante,
    )
    db.add(fila)
    db.commit()
    return fila


def _detalle(db, lead):
    return (
        db.query(ScoreHistory)
        .filter(ScoreHistory.lead_id == lead.id)
        .order_by(ScoreHistory.calculated_at, ScoreHistory.id)
        .all()
    )


def _meses(db, lead):
    return {
        r.month: r
        for r in db.query(ScoreHistoryMonthly).filter(ScoreHistoryMonthly.lead_id == lead.id)
    }


@pytest.fixture
def trayectoria(db_session):
    """
    Un prospecto con año y medio de historia.

    Entrada en marzo de 2025, tres recálculos vencidos entre marzo y abril, y la puntuación
    vigente en agosto de 2026. Con 12 meses de retención a 10/09/2026 el corte cae en
    01/09/2025.
    """
    lead = _prospecto(db_session, 1)
    filas = {
        "entrada": _puntuacion(db_session, lead, _dia(2025, 3, 5), 10.0, categoria=ScoreCategory.COLD),
        "marzo_1": _puntuacion(db_session, lead, _dia(2025, 3, 10), 20.0),
        "marzo_2": _puntuacion(db_session, lead, _dia(2025, 3, 20), 30.0, categoria=ScoreCategory.HOT),
        "abril": _puntuacion(db_session, lead, _dia(2025, 4, 2), 40.0, version="v2"),
        "vigente": _puntuacion(db_session, lead, _dia(2026, 8, 1), 50.0),
    }
    return lead, filas


# ==============================================================================
# El plazo
# ==============================================================================

def test_el_corte_se_alinea_al_primer_dia_del_mes():
    assert limite_de_retencion(AHORA, 12) == _dia(2025, 9, 1, hora=0)
    assert limite_de_retencion(AHORA, 3) == _dia(2026, 6, 1, hora=0)
    # El salto de año, que es donde una resta de meses mal hecha se equivoca.
    assert limite_de_retencion(_dia(2026, 1, 15), 12) == _dia(2025, 1, 1, hora=0)
    assert limite_de_retencion(_dia(2026, 2, 28), 14) == _dia(2024, 12, 1, hora=0)


def test_un_plazo_por_debajo_del_minimo_no_se_acepta_ni_en_la_funcion_ni_al_arrancar():
    with pytest.raises(ValueError):
        limite_de_retencion(AHORA, RETENCION_MINIMA_DEL_HISTORIAL_MESES - 1)
    with pytest.raises(ValidationError):
        Settings(SCORE_HISTORY_RETENTION_MONTHS=RETENCION_MINIMA_DEL_HISTORIAL_MESES - 1)


def test_el_historial_se_consulta_por_prospecto_e_instante_con_indice():
    """
    El índice que pedía R-3 ya existía desde la migración de base. Esta prueba no lo crea:
    impide que desaparezca, porque la purga y la ficha del prospecto consultan justo así.
    """
    indices = {tuple(c.name for c in i.columns) for i in ScoreHistory.__table__.indexes}
    assert ("lead_id", "calculated_at") in indices


# ==============================================================================
# Qué se resume, qué se borra y qué se conserva
# ==============================================================================

def test_resume_por_mes_y_borra_el_detalle_vencido(db_session, trayectoria):
    lead, filas = trayectoria

    resultado = aplicar_retencion(db_session, meses=12, ahora=AHORA)

    assert resultado.filas_resumidas == 3
    assert resultado.resumenes_nuevos == 2
    assert resultado.prospectos == 1
    # Solo la entrada estaba vencida y protegida; la vigente no había vencido.
    assert resultado.filas_protegidas == 1

    assert [f.id for f in _detalle(db_session, lead)] == [filas["entrada"].id, filas["vigente"].id]

    meses = _meses(db_session, lead)
    marzo = meses[datetime.date(2025, 3, 1)]
    assert marzo.scores_count == 2
    assert marzo.score_sum == pytest.approx(50.0)
    assert (marzo.score_min, marzo.score_max) == (20.0, 30.0)
    assert (marzo.first_score, marzo.last_score) == (20.0, 30.0)
    assert marzo.last_category == ScoreCategory.HOT
    assert marzo.category_counts == {"WARM": 1, "HOT": 1}

    abril = meses[datetime.date(2025, 4, 1)]
    assert abril.scores_count == 1
    assert abril.model_versions == ["v2"]


def test_el_detalle_mas_resumen_cuenta_todas_las_puntuaciones(db_session, trayectoria):
    """Lo que no está en el detalle está en el resumen, y nada está en los dos."""
    lead, _ = trayectoria
    antes = len(_detalle(db_session, lead))

    aplicar_retencion(db_session, meses=12, ahora=AHORA)

    en_resumen = sum(r.scores_count for r in _meses(db_session, lead).values())
    assert len(_detalle(db_session, lead)) + en_resumen == antes


def test_la_instantanea_de_entrada_sobrevive_y_el_extractor_la_sigue_eligiendo(db_session):
    """
    El caso que motiva la regla: filas antiguas SIN instantánea —anteriores a la columna—
    delante de la entrada real. La purga se lleva la más antigua de todas y tiene que dejar
    la de entrada, que no es la primera fila sino la primera con vector.

    Si la purga no la protegiera, `feedback_dataset` no fallaría: elegiría la siguiente
    instantánea, ya contaminada por el avance comercial.
    """
    from feedback_dataset import _instantanea_de_entrada

    lead = _prospecto(db_session, 2)
    _puntuacion(db_session, lead, _dia(2024, 1, 3), 5.0, instantanea=False)
    entrada = _puntuacion(db_session, lead, _dia(2024, 2, 3), 15.0)
    _puntuacion(db_session, lead, _dia(2024, 3, 3), 25.0)
    _puntuacion(db_session, lead, _dia(2024, 4, 3), 35.0)

    assert _instantanea_de_entrada(db_session, lead.id).id == entrada.id

    aplicar_retencion(db_session, meses=12, ahora=AHORA)

    assert _instantanea_de_entrada(db_session, lead.id).id == entrada.id
    assert consulta_instantanea_de_entrada(db_session, lead.id).first().id == entrada.id


def test_la_puntuacion_vigente_de_un_prospecto_dormido_se_conserva(db_session):
    """Sin actividad en dos años, pero con un score que la ficha tiene que poder explicar."""
    lead = _prospecto(db_session, 3)
    _puntuacion(db_session, lead, _dia(2024, 1, 3), 5.0)
    _puntuacion(db_session, lead, _dia(2024, 2, 3), 15.0)
    vigente = _puntuacion(db_session, lead, _dia(2024, 3, 3), 25.0)

    aplicar_retencion(db_session, meses=12, ahora=AHORA)

    ids = [f.id for f in _detalle(db_session, lead)]
    assert vigente.id in ids
    assert len(ids) == 2  # entrada y vigente


def test_la_version_por_lotes_elige_las_mismas_filas_que_la_de_uno_en_uno(db_session):
    """
    `filas_protegidas` agrupa en SQL lo que `consulta_instantanea_de_entrada` hace de uno
    en uno. Si divergieran, la purga protegería una fila y el extractor usaría otra. Se
    incluyen empates de instante, que es donde dos formas de ordenar discrepan.
    """
    leads = [_prospecto(db_session, 10 + n) for n in range(4)]
    empate = _dia(2024, 5, 5)
    _puntuacion(db_session, leads[0], empate, 1.0)
    _puntuacion(db_session, leads[0], empate, 2.0)
    _puntuacion(db_session, leads[0], _dia(2024, 6, 1), 3.0)
    _puntuacion(db_session, leads[1], _dia(2024, 1, 1), 4.0, instantanea=False)
    _puntuacion(db_session, leads[1], _dia(2024, 2, 1), 5.0)
    _puntuacion(db_session, leads[1], _dia(2024, 2, 1), 6.0)
    _puntuacion(db_session, leads[2], _dia(2024, 3, 1), 7.0, instantanea=False)
    _puntuacion(db_session, leads[3], _dia(2024, 4, 1), 8.0)

    esperado = set()
    for lead in leads:
        entrada = consulta_instantanea_de_entrada(db_session, lead.id).first()
        if entrada is not None:
            esperado.add(entrada.id)
        filas = _detalle(db_session, lead)
        esperado.add(max(filas, key=lambda f: (f.calculated_at, f.id)).id)

    assert filas_protegidas(db_session, [lead.id for lead in leads]) == esperado


def test_una_segunda_pasada_no_cambia_nada(db_session, trayectoria):
    lead, _ = trayectoria
    aplicar_retencion(db_session, meses=12, ahora=AHORA)
    antes = {m: (r.scores_count, r.score_sum) for m, r in _meses(db_session, lead).items()}

    segunda = aplicar_retencion(db_session, meses=12, ahora=AHORA)

    assert segunda.filas_resumidas == 0
    assert segunda.resumenes_nuevos == segunda.resumenes_fusionados == 0
    db_session.expire_all()
    assert {m: (r.scores_count, r.score_sum) for m, r in _meses(db_session, lead).items()} == antes


def test_una_fila_que_llega_tarde_se_fusiona_con_su_mes(db_session, trayectoria):
    """
    La razón de guardar la suma y no la media: dos pasadas sobre el mismo mes se combinan
    sin saber cuántas filas había detrás de la primera.
    """
    lead, _ = trayectoria
    aplicar_retencion(db_session, meses=12, ahora=AHORA)

    _puntuacion(db_session, lead, _dia(2025, 3, 25), 90.0, categoria=ScoreCategory.HOT)
    _puntuacion(db_session, lead, _dia(2025, 3, 6), 1.0, categoria=ScoreCategory.COLD)
    resultado = aplicar_retencion(db_session, meses=12, ahora=AHORA)

    assert resultado.resumenes_fusionados == 1
    assert resultado.resumenes_nuevos == 0
    db_session.expire_all()
    marzo = _meses(db_session, lead)[datetime.date(2025, 3, 1)]
    assert marzo.scores_count == 4
    assert marzo.score_sum == pytest.approx(141.0)
    assert (marzo.score_min, marzo.score_max) == (1.0, 90.0)
    assert (marzo.first_score, marzo.last_score) == (1.0, 90.0)
    assert marzo.category_counts == {"WARM": 1, "HOT": 2, "COLD": 1}
    assert db_session.query(ScoreHistoryMonthly).filter(ScoreHistoryMonthly.lead_id == lead.id).count() == 2


def test_simular_cuenta_lo_mismo_y_no_escribe(db_session, trayectoria):
    lead, _ = trayectoria
    antes = [f.id for f in _detalle(db_session, lead)]

    simulado = aplicar_retencion(db_session, meses=12, ahora=AHORA, simular=True)

    assert [f.id for f in _detalle(db_session, lead)] == antes
    assert _meses(db_session, lead) == {}

    real = aplicar_retencion(db_session, meses=12, ahora=AHORA)
    for campo in ("prospectos", "filas_resumidas", "filas_protegidas", "resumenes_nuevos"):
        assert getattr(simulado, campo) == getattr(real, campo), campo


def test_si_otra_purga_se_lleva_filas_a_mitad_el_lote_se_descarta_entero(db_session, trayectoria, monkeypatch):
    """
    Entre leer el lote y borrarlo, otra transacción borra una de las filas. Sumar lo leído
    contaría dos veces esa fila —la otra purga ya la resumió—. Se deshace el lote entero.
    """
    lead, filas = trayectoria
    original = retencion_service.primer_dia_del_mes
    intrusa = {"hecho": False}

    def primer_dia_con_intrusa(instante):
        if not intrusa["hecho"]:
            intrusa["hecho"] = True
            db_session.execute(delete(ScoreHistory).where(ScoreHistory.id == filas["marzo_1"].id))
        return original(instante)

    monkeypatch.setattr(retencion_service, "primer_dia_del_mes", primer_dia_con_intrusa)
    resultado = aplicar_retencion(db_session, meses=12, ahora=AHORA)

    assert resultado.lotes_descartados == 1
    assert resultado.filas_resumidas == 0
    assert _meses(db_session, lead) == {}
    assert len(_detalle(db_session, lead)) == 5


def test_los_lotes_recorren_todos_los_prospectos(db_session):
    """Paginación por clave: con OFFSET, borrar mientras se pagina se saltaría prospectos."""
    leads = [_prospecto(db_session, 20 + n) for n in range(5)]
    for lead in leads:
        for mes in (1, 2, 3):
            _puntuacion(db_session, lead, _dia(2024, mes, 10), float(mes))
        _puntuacion(db_session, lead, _dia(2026, 9, 1), 99.0)

    resultado = aplicar_retencion(db_session, meses=12, ahora=AHORA, lote=2)

    assert resultado.prospectos == 5
    for lead in leads:
        assert len(_detalle(db_session, lead)) == 2


# ==============================================================================
# El servicio programado
# ==============================================================================

def test_el_guion_purga_y_deja_constancia_en_la_bitacora(db_session, capsys):
    from scripts import retencion_historial

    lead = _prospecto(db_session, 30)
    for dia in (1, 2, 3):
        _puntuacion(db_session, lead, _dia(2020, 1, dia), float(dia))
    _puntuacion(db_session, lead, _dia(2020, 2, 1), 9.0)

    assert retencion_historial.main(["--meses", "12"]) == 0
    assert "2 filas resumidas" in capsys.readouterr().out

    asiento = db_session.query(AuditLog).filter(AuditLog.action == "historial.retencion").one()
    assert asiento.actor_id is None
    assert asiento.event_metadata["filas_resumidas"] == 2
    assert asiento.event_metadata["simulado"] is False


def test_simular_desde_el_guion_no_anota_ni_borra(db_session):
    from scripts import retencion_historial

    lead = _prospecto(db_session, 31)
    for dia in (1, 2, 3):
        _puntuacion(db_session, lead, _dia(2020, 1, dia), float(dia))

    assert retencion_historial.main(["--simular"]) == 0
    assert len(_detalle(db_session, lead)) == 3
    assert db_session.query(AuditLog).filter(AuditLog.action == "historial.retencion").count() == 0


def test_el_guion_no_purga_con_un_plazo_por_debajo_del_minimo(db_session):
    from scripts import retencion_historial

    lead = _prospecto(db_session, 32)
    for dia in (1, 2, 3):
        _puntuacion(db_session, lead, _dia(2020, 1, dia), float(dia))

    assert retencion_historial.main(["--meses", str(RETENCION_MINIMA_DEL_HISTORIAL_MESES - 1)]) == 2
    assert len(_detalle(db_session, lead)) == 3


def test_en_modo_servicio_un_fallo_no_detiene_la_purga(monkeypatch):
    """Una caída momentánea de la base no puede dejar la purga parada hasta el próximo despliegue."""
    from scripts import retencion_historial

    llamadas = []

    def pasada(*_args):
        llamadas.append(1)
        if len(llamadas) == 1:
            raise RuntimeError("la base no responde")
        return 0

    class FinDelBucle(Exception):
        pass

    def dormir(_segundos):
        if len(llamadas) >= 2:
            raise FinDelBucle

    monkeypatch.setattr(retencion_historial, "una_pasada", pasada)
    monkeypatch.setattr(retencion_historial.time, "sleep", dormir)

    with pytest.raises(FinDelBucle):
        retencion_historial.main(["--cada", "5"])
    assert len(llamadas) == 2
