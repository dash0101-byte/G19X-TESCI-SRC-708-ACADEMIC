"""
Capítulo 22: nada sin plazo.

§20.5 dejaba escritas cuatro tablas sin caducidad —sesiones, trabajos de recálculo, registros
del CRM y, desde el capítulo 21, la bandeja «Sin asociar»—, y la de sesiones tenía una
función de purga que nadie llamaba. Lo que se comprueba aquí no es solo que se borre lo
vencido: es que no se borre lo vivo, que cada pasada quede en la bitácora, que un plazo que
falla no detenga a los demás y que el servicio de la pila de verdad los aplique.

Capítulo 32: las dos filas que el 22 dejó fuera
------------------------------------------------
La **bitácora**, que se remitía a «decisión de operación» y crecía sin techo, y el **conjunto
de realimentación**, que ni siquiera es una tabla. El segundo trae una propiedad que ninguna
de las pruebas anteriores tenía que vigilar: esta purga BORRA ARCHIVOS, así que se comprueba
también lo que NO se lleva por delante —el conjunto sintético con el que se entrena, que
vive en el mismo directorio— y que una pasada restringida a unos plazos concretos no toque
el disco de paso.
"""
import datetime
import os
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
from app.services.caducidad_service import (
    PLAZOS,
    PLAZOS_DE_ARCHIVOS,
    Plazo,
    aplicar_caducidad,
    archivos_vencidos,
    directorio_de_realimentacion,
)
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
        # Capítulo 32.
        "CONSERVACION_AUDITORIA_DIAS": 730,
        "CONSERVACION_REALIMENTACION_DIAS": 30,
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
        # Capítulo 32: la última tabla de §20.5 que decía «sin plazo en la aplicación».
        "audit_log",
    }
    # Ninguna de las dos listas por su cuenta cubre la tabla de mínimos, y las dos juntas
    # sí: un plazo nuevo sin mínimo —o un mínimo escrito para un plazo que nadie aplica—
    # falla aquí en lugar de descubrirse el día de la primera purga.
    ajustes = {p.ajuste for p in PLAZOS} | {p.ajuste for p in PLAZOS_DE_ARCHIVOS}
    assert ajustes == set(CONSERVACION_MINIMA_DIAS)


def test_el_conjunto_de_realimentacion_tiene_plazo_aunque_no_sea_una_tabla():
    assert [p.nombre for p in PLAZOS_DE_ARCHIVOS] == ["conjunto_de_realimentacion"]
    assert PLAZOS_DE_ARCHIVOS[0].ajuste == "CONSERVACION_REALIMENTACION_DIAS"


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
    # El plazo de archivos también deja su asiento, y con su propio nombre de unidad: su
    # «tabla» es el directorio, así que se compara por separado.
    directorio = str(directorio_de_realimentacion())
    assert set(asientos) == {p.tabla for p in PLAZOS} | {directorio}
    assert asientos[directorio].event_metadata["archivos_borrados"] == 0
    assert "filas_borradas" not in asientos[directorio].event_metadata
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
    # Y el de archivos, con su unidad: «0 archivos», no «0 filas».
    assert f"[CADUCIDAD] {directorio_de_realimentacion()}: 0 archivos" in salida
    assert db_session.query(RefreshToken).count() == 0
    assert db_session.query(UnmatchedEvent).count() == 0
    assert db_session.query(CRMIntegrationLog).count() == 0
    # Un asiento por plazo: la lista y la bitácora dicen lo mismo, y añadir un plazo sin
    # anotarlo rompe aquí.
    assert db_session.query(AuditLog).filter(
        AuditLog.action == "conservacion.purga"
    ).count() == len(PLAZOS) + len(PLAZOS_DE_ARCHIVOS)


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


def test_el_directorio_de_realimentacion_lo_comparten_quien_extrae_y_quien_purga():
    """
    El plazo del conjunto solo existe si los dos contenedores miran el mismo sitio.

    Esta es la comprobación que convierte «hay un plazo» en «el plazo alcanza al archivo».
    Sin el volumen compartido, el servicio de purga aplicaría su corte cada día sobre un
    directorio vacío, anotaría cero archivos en la bitácora —cierto— y el CSV con una fila
    por persona cerrada seguiría en el otro contenedor para siempre.
    """
    import yaml

    pila = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    purga = pila["services"]["retencion-historial"]
    extractor = pila["services"]["backend"]

    directorio = purga["environment"]["REALIMENTACION_DIR"]
    montaje = f"realimentacion:{directorio}"
    assert montaje in purga["volumes"], "el servicio de purga no monta el volumen que va a purgar"
    assert montaje in extractor["volumes"], "el backend no escribe donde la purga mira"
    assert "realimentacion" in pila["volumes"]


# ==============================================================================
# El plazo que no es una tabla (capítulo 32)
# ==============================================================================

def _archivo(directorio: pathlib.Path, nombre: str, dias_de_antiguedad: float) -> pathlib.Path:
    """Un archivo con su fecha de modificación puesta hacia atrás."""
    ruta = directorio / nombre
    ruta.write_text("resultado,converted\n1,0\n", encoding="utf-8")
    cuando = (AHORA - datetime.timedelta(days=dias_de_antiguedad)).timestamp()
    os.utime(ruta, (cuando, cuando))
    return ruta


@pytest.fixture
def directorio_del_conjunto(tmp_path, monkeypatch):
    destino = tmp_path / "realimentacion"
    destino.mkdir()
    monkeypatch.setattr(settings, "REALIMENTACION_DIR", str(destino))
    return destino


def test_el_conjunto_vencido_se_borra_con_su_manifiesto(db_session, directorio_del_conjunto):
    _archivo(directorio_del_conjunto, "leads_reales.csv", 31)
    _archivo(directorio_del_conjunto, "leads_reales_manifiesto.json", 31)
    reciente = _archivo(directorio_del_conjunto, "leads_reales_2026_09.csv", 5)

    resultados = {r.tabla: r for r in aplicar_caducidad(db_session, ahora=AHORA)}
    resultado = resultados[str(directorio_del_conjunto)]

    assert resultado.filas == 2 and resultado.unidad == "archivos"
    assert reciente.exists()
    assert sorted(p.name for p in directorio_del_conjunto.iterdir()) == ["leads_reales_2026_09.csv"]


def test_el_conjunto_sintetico_de_entrenamiento_no_caduca(db_session, directorio_del_conjunto):
    """
    `leads_historical.csv` vive en el mismo directorio y NO lleva datos de nadie: es la
    entrada reproducible del artefacto que hoy sirve. Un patrón `*.csv` se lo habría
    llevado a los treinta días y habría dejado el entrenamiento sin poder repetirse.
    """
    sintetico = _archivo(directorio_del_conjunto, "leads_historical.csv", 400)
    _archivo(directorio_del_conjunto, "leads_reales.csv", 400)

    aplicar_caducidad(db_session, ahora=AHORA)

    assert sintetico.exists()
    assert not (directorio_del_conjunto / "leads_reales.csv").exists()


def test_un_directorio_que_no_existe_no_es_un_fallo(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "REALIMENTACION_DIR", str(tmp_path / "todavia-no-hay-nada"))

    resultados = {r.plazo: r for r in aplicar_caducidad(db_session, ahora=AHORA)}
    resultado = resultados["conjunto_de_realimentacion"]

    # La instalación que aún no ha extraído ningún conjunto es la normal durante meses. Un
    # plazo que fallara todos los días enseñaría a no leer el registro.
    assert resultado.error is None and resultado.filas == 0


def test_simular_cuenta_los_archivos_sin_borrarlos(db_session, directorio_del_conjunto):
    _archivo(directorio_del_conjunto, "leads_reales.csv", 60)

    resultados = {r.plazo: r for r in aplicar_caducidad(db_session, ahora=AHORA, simular=True)}

    assert resultados["conjunto_de_realimentacion"].filas == 1
    assert (directorio_del_conjunto / "leads_reales.csv").exists()


def test_una_pasada_restringida_a_unos_plazos_no_toca_el_disco(db_session, directorio_del_conjunto):
    """
    La propiedad que impide que una guarda o una prueba de otra cosa borre datos de paso.

    `guarda_del_motor_de_reglas.py` aplica los plazos de `tareas` y `avisos` para comprobar
    otra cosa. Si pedir unos plazos concretos arrastrara también los de archivos, esa guarda
    borraría el conjunto de realimentación de quien la ejecutara.
    """
    vencido = _archivo(directorio_del_conjunto, "leads_reales.csv", 400)

    resultados = aplicar_caducidad(
        db_session, ahora=AHORA, plazos=[p for p in PLAZOS if p.tabla == "avisos"]
    )

    assert [r.plazo for r in resultados] == ["avisos"]
    assert vencido.exists()


def test_un_enlace_simbolico_no_convierte_la_purga_en_un_borrado_de_cualquier_cosa(
    directorio_del_conjunto, tmp_path
):
    """
    Un `leads_reales.csv` que apunte fuera no se sigue. Sin esto, quien pudiera escribir un
    nombre en ese directorio podría hacer que la purga diaria borrara cualquier archivo de
    la máquina al que llegara el proceso.
    """
    ajeno = tmp_path / "algo_importante.csv"
    ajeno.write_text("no soy el conjunto", encoding="utf-8")
    enlace = directorio_del_conjunto / "leads_reales_enlace.csv"
    try:
        enlace.symlink_to(ajeno)
    except (OSError, NotImplementedError):  # pragma: no cover  (Windows sin permiso)
        pytest.skip("este sistema no deja crear enlaces simbólicos sin privilegios")
    cuando = (AHORA - datetime.timedelta(days=400)).timestamp()
    os.utime(enlace, (cuando, cuando), follow_symlinks=False)

    assert archivos_vencidos(directorio_del_conjunto, AHORA) == []


def test_la_bitacora_tiene_plazo_y_deja_dicho_lo_que_se_llevo(db_session):
    """
    La purga que borra la prueba. Se comprueba lo que se borra, lo que no, y que el asiento
    de la propia purga quede diciendo cuántos asientos se llevó y hasta qué fecha: lo que se
    pierde tiene que quedar acotado por escrito (N-8).
    """
    for dias, accion in ((900, "lead.eliminar"), (100, "lead.eliminar")):
        db_session.add(
            AuditLog(
                actor_email="alguien@plurione.test",
                action=accion,
                entity="lead",
                outcome="OK",
                occurred_at=AHORA - datetime.timedelta(days=dias),
            )
        )
    db_session.commit()

    aplicar_caducidad(db_session, ahora=AHORA, plazos=[p for p in PLAZOS if p.tabla == "audit_log"])

    quedan = db_session.query(AuditLog).filter(AuditLog.action == "lead.eliminar").all()
    assert len(quedan) == 1, "el asiento de hace 100 días está dentro del plazo de 730"
    asiento = db_session.query(AuditLog).filter(AuditLog.action == "conservacion.purga").one()
    assert asiento.event_metadata["filas_borradas"] == 1
    assert asiento.event_metadata["dias"] == 730
    assert asiento.event_metadata["corte"].startswith("2024-09")


def test_la_bitacora_va_la_ultima_para_no_llevarse_los_errores_de_la_misma_pasada():
    """
    Un plazo que falla escribe su asiento de ERROR durante la pasada. Si la purga de la
    bitácora corriera antes, podría llevárselo en esa misma pasada y el fallo del día
    quedaría sin rastro.
    """
    assert PLAZOS[-1].tabla == "audit_log"
