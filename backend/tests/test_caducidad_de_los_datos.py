"""
Capítulo 22: nada sin plazo.

§20.5 dejaba escritas cuatro tablas sin caducidad —sesiones, trabajos de recálculo, registros
del CRM y, desde el capítulo 21, la bandeja «Sin asociar»—, y la de sesiones tenía una
función de purga que nadie llamaba. Lo que se comprueba aquí no es solo que se borre lo
vencido: es que no se borre lo vivo, que cada pasada quede en la bitácora, que un plazo que
falla no detenga a los demás y que el servicio de la pila de verdad los aplique.
"""
import datetime
import pathlib
import uuid

import pytest
from app.core.config import CONSERVACION_MINIMA_DIAS, Settings, settings
from app.models.entities import (
    ActivityType,
    AuditLog,
    CRMIntegrationLog,
    JobStatus,
    RefreshToken,
    ScoringJob,
    UnmatchedEvent,
    User,
)
from app.services import caducidad_service
from app.services.caducidad_service import PLAZOS, Plazo, aplicar_caducidad
from pydantic import ValidationError

UTC = datetime.timezone.utc
AHORA = datetime.datetime(2026, 9, 14, 12, 0, tzinfo=UTC)
COMPOSE = pathlib.Path(__file__).resolve().parents[2] / "devops" / "docker-compose.yml"


@pytest.fixture(autouse=True)
def plazos_por_defecto(monkeypatch):
    """Los plazos de fábrica, fijados: la prueba no puede depender del entorno de quien la corre."""
    for ajuste, dias in {
        "CONSERVACION_SESIONES_DIAS": 30,
        "CONSERVACION_TRABAJOS_DIAS": 90,
        "CONSERVACION_REGISTROS_CRM_DIAS": 90,
        "CONSERVACION_SIN_ASOCIAR_DIAS": 90,
    }.items():
        monkeypatch.setattr(settings, ajuste, dias)


def _hace(dias, *, desde=AHORA):
    return desde - datetime.timedelta(days=dias)


def _usuario(db):
    return db.query(User).order_by(User.id).first()


def _token(db, n, *, caduco_hace, desde=AHORA):
    token = RefreshToken(
        jti=f"{n:032d}", family_id=f"{n:032d}", user_id=_usuario(db).id,
        issued_at=_hace(caduco_hace + 7, desde=desde), expires_at=_hace(caduco_hace, desde=desde),
    )
    db.add(token)
    db.commit()
    return token.jti


def _trabajo(db, estado, *, termino_hace=None, creado_hace=0, turno=None):
    trabajo = ScoringJob(
        id=str(uuid.uuid4()), status=estado.value, created_at=_hace(creado_hace),
        finished_at=None if termino_hace is None else _hace(termino_hace), lease_key=turno,
    )
    db.add(trabajo)
    db.commit()
    return trabajo.id


def _registro_crm(db, *, hace, desde=AHORA):
    registro = CRMIntegrationLog(event_type="INGEST", synced_at=_hace(hace, desde=desde), payload={})
    db.add(registro)
    db.commit()
    return registro.id


def _aviso(db, n, *, llego_hace, ocurrio_hace=None, desde=AHORA):
    aviso = UnmatchedEvent(
        source="calendly", external_event_id=f"evento-{n}", activity_type=ActivityType.MEETING_SCHEDULED,
        channel="Calendly", contact_email=f"persona.{n}@ejemplo.com",
        occurred_at=_hace(llego_hace if ocurrio_hace is None else ocurrio_hace, desde=desde),
        received_at=_hace(llego_hace, desde=desde),
    )
    db.add(aviso)
    db.commit()
    return aviso.id


# ==============================================================================
# Qué tiene plazo
# ==============================================================================

def test_las_tablas_que_20_5_dejaba_sin_caducidad_tienen_plazo():
    assert {plazo.tabla for plazo in PLAZOS} == {
        "refresh_tokens", "scoring_jobs", "crm_integration_logs", "unmatched_events",
        # Capítulo 28: nacen con plazo el mismo día que nacen.
        "tareas", "avisos",
    }
    assert {plazo.ajuste for plazo in PLAZOS} == set(CONSERVACION_MINIMA_DIAS)


@pytest.mark.parametrize("ajuste", sorted(CONSERVACION_MINIMA_DIAS))
def test_un_plazo_por_debajo_del_minimo_no_arranca(ajuste):
    minimo = CONSERVACION_MINIMA_DIAS[ajuste]
    with pytest.raises(ValidationError):
        Settings(**{ajuste: minimo - 1})
    assert getattr(Settings(**{ajuste: minimo}), ajuste) == minimo


# ==============================================================================
# Lo vencido se va, lo vivo se queda
# ==============================================================================

def test_las_sesiones_caducan_contando_desde_que_vencieron(db_session):
    vencida_hace_tiempo = _token(db_session, 1, caduco_hace=31)
    vencida_hace_poco = _token(db_session, 2, caduco_hace=29)
    vigente = _token(db_session, 3, caduco_hace=-5)

    aplicar_caducidad(db_session, ahora=AHORA)

    quedan = {t.jti for t in db_session.query(RefreshToken)}
    assert vencida_hace_tiempo not in quedan
    assert vencida_hace_poco in quedan, "Lo vencido hace poco todavía puede hacer falta para investigar."
    assert vigente in quedan


def test_la_purga_de_sesiones_es_la_funcion_que_ya_existia(db_session, monkeypatch):
    """El defecto era que nadie llamaba a `purgar_tokens_caducados`; no se arregla con una segunda."""
    llamadas = []

    def espia(db, margen_dias, ahora):
        llamadas.append((margen_dias, ahora))
        return 0

    monkeypatch.setattr(caducidad_service, "purgar_tokens_caducados", espia)
    aplicar_caducidad(db_session, ahora=AHORA)
    assert llamadas == [(30, AHORA)]


def test_solo_caducan_los_recalculos_terminados_y_desde_que_terminaron(db_session):
    completado_viejo = _trabajo(db_session, JobStatus.COMPLETED, termino_hace=91, creado_hace=91)
    fallido_viejo = _trabajo(db_session, JobStatus.FAILED, termino_hace=120, creado_hace=120)
    completado_reciente = _trabajo(db_session, JobStatus.COMPLETED, termino_hace=10, creado_hace=400)
    en_curso_antiguo = _trabajo(db_session, JobStatus.RUNNING, creado_hace=400, turno="RECALCULATE_ALL")
    pendiente_antiguo = _trabajo(db_session, JobStatus.PENDING, creado_hace=400)
    # Estado contradictorio: dice RUNNING, no ocupa el turno y tiene fecha de fin. No debería
    # existir, pero si existe, la duda se resuelve conservando: el estado manda.
    contradictorio = _trabajo(db_session, JobStatus.RUNNING, termino_hace=400, creado_hace=400)

    aplicar_caducidad(db_session, ahora=AHORA)

    quedan = {t.id for t in db_session.query(ScoringJob)}
    assert completado_viejo not in quedan and fallido_viejo not in quedan
    assert completado_reciente in quedan, "El plazo corre desde que terminó, no desde que se creó."
    assert en_curso_antiguo in quedan and pendiente_antiguo in quedan, "Un trabajo vivo no caduca."
    assert contradictorio in quedan, "Un trabajo que no dice haber terminado no se borra."


def test_los_registros_crm_caducan_esten_o_no_vinculados(db_session, sample_lead):
    _registro_crm(db_session, hace=91)  # sin vincular
    viejo_vinculado = CRMIntegrationLog(lead_id=sample_lead.id, event_type="INGEST", synced_at=_hace(200), payload={})
    db_session.add(viejo_vinculado)
    db_session.commit()
    reciente = _registro_crm(db_session, hace=89)

    aplicar_caducidad(db_session, ahora=AHORA)

    assert {r.id for r in db_session.query(CRMIntegrationLog)} == {reciente}


def test_la_bandeja_caduca_desde_que_llego_el_aviso(db_session):
    viejo = _aviso(db_session, 1, llego_hace=91)
    tardio = _aviso(db_session, 2, llego_hace=10, ocurrio_hace=400)

    aplicar_caducidad(db_session, ahora=AHORA)

    quedan = {a.id for a in db_session.query(UnmatchedEvent)}
    assert viejo not in quedan
    assert tardio in quedan, "Un evento antiguo entregado ayer tiene que dar tiempo a vincularlo."


# ==============================================================================
# Constancia, simulación y fallos
# ==============================================================================

def test_cada_plazo_deja_su_asiento_tambien_sin_nada_que_borrar(db_session):
    _aviso(db_session, 1, llego_hace=91)

    aplicar_caducidad(db_session, ahora=AHORA)

    asientos = {
        a.event_metadata["tabla"]: a
        for a in db_session.query(AuditLog).filter(AuditLog.action == "conservacion.purga")
    }
    assert set(asientos) == {p.tabla for p in PLAZOS}
    assert asientos["unmatched_events"].event_metadata["filas_borradas"] == 1
    assert asientos["refresh_tokens"].event_metadata["filas_borradas"] == 0
    assert all(a.actor_id is None and a.outcome == "OK" for a in asientos.values())
    # El asiento dice cuántas filas, no de quién eran.
    assert "persona.1@ejemplo.com" not in str(asientos["unmatched_events"].event_metadata)


def test_simular_cuenta_sin_borrar_ni_anotar(db_session):
    _aviso(db_session, 1, llego_hace=91)
    _token(db_session, 1, caduco_hace=60)

    resultados = {r.tabla: r for r in aplicar_caducidad(db_session, ahora=AHORA, simular=True)}

    assert resultados["unmatched_events"].filas == 1
    assert resultados["refresh_tokens"].filas == 1
    assert db_session.query(UnmatchedEvent).count() == 1
    assert db_session.query(RefreshToken).count() == 1
    assert db_session.query(AuditLog).filter(AuditLog.action == "conservacion.purga").count() == 0


def test_un_plazo_que_falla_no_detiene_a_los_demas(db_session):
    _aviso(db_session, 1, llego_hace=91)

    def roto(*_args):
        raise RuntimeError("la tabla no responde")

    plazo_roto = Plazo("roto", "tabla_rota", "CONSERVACION_SESIONES_DIAS", "sesion", roto, roto)
    bandeja = next(p for p in PLAZOS if p.tabla == "unmatched_events")

    resultados = aplicar_caducidad(db_session, ahora=AHORA, plazos=[plazo_roto, bandeja])

    assert resultados[0].error == "RuntimeError"
    assert resultados[1].error is None and resultados[1].filas == 1
    assert db_session.query(UnmatchedEvent).count() == 0
    fallido = db_session.query(AuditLog).filter(AuditLog.action == "conservacion.purga", AuditLog.outcome == "ERROR").one()
    assert fallido.event_metadata["tabla"] == "tabla_rota"


# ==============================================================================
# El servicio diario
# ==============================================================================

def test_el_guion_diario_aplica_los_plazos(db_session, capsys):
    from scripts import retencion_historial

    ahora = datetime.datetime.now(UTC)
    _token(db_session, 7, caduco_hace=400, desde=ahora)
    _aviso(db_session, 7, llego_hace=400, desde=ahora)
    _registro_crm(db_session, hace=400, desde=ahora)

    assert retencion_historial.main([]) == 0

    salida = capsys.readouterr().out
    for plazo in PLAZOS:
        assert f"[CADUCIDAD] {plazo.tabla}:" in salida
    assert db_session.query(RefreshToken).count() == 0
    assert db_session.query(UnmatchedEvent).count() == 0
    assert db_session.query(CRMIntegrationLog).count() == 0
    # Un asiento por plazo: la lista y la bitácora dicen lo mismo, y añadir un plazo sin
    # anotarlo rompe aquí.
    assert db_session.query(AuditLog).filter(
        AuditLog.action == "conservacion.purga"
    ).count() == len(PLAZOS)


def test_si_el_historial_falla_los_plazos_se_aplican_y_la_pasada_sale_con_1(db_session, monkeypatch):
    from scripts import retencion_historial

    def historial_roto(*_args, **_kwargs):
        raise RuntimeError("fallo en el resumen")

    monkeypatch.setattr(retencion_historial, "aplicar_retencion", historial_roto)
    _aviso(db_session, 8, llego_hace=400, desde=datetime.datetime.now(UTC))

    assert retencion_historial.main([]) == 1
    assert db_session.query(UnmatchedEvent).count() == 0


def test_la_pila_programa_los_plazos_en_el_servicio_diario():
    import yaml

    servicio = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]["retencion-historial"]
    orden = " ".join(servicio["command"])
    assert "/app/scripts/retencion_historial.py" in orden and "--cada" in orden
    for ajuste in CONSERVACION_MINIMA_DIAS:
        assert ajuste in servicio["environment"], f"{ajuste} no llega al servicio que aplica el plazo."
