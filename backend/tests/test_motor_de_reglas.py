"""
El motor de reglas del capítulo 28: qué crea, qué no duplica y qué cierra solo.

Lo que estas pruebas vigilan de verdad no es que una regla cree una tarea —eso es fácil—,
sino las tres cosas que fallarían en silencio:

* **repetir la pasada no duplica nada.** Un motor que duplica no rompe nada el primer día;
  rompe la bandeja la primera semana, cuando ya nadie la mira;
* **el escalado escala.** El líder solo se entera de lo que el asesor ya no resolvió;
* **lo que se cumple se cierra en el momento**, no en la pasada del día siguiente, porque
  hasta entonces el asesor vería en su lista una llamada que acaba de hacer.
"""
import datetime

import pytest
from app.core.agenda import (
    ABIERTA,
    CUMPLIDA,
    HOT_SIN_CONTACTO,
    HOT_SIN_CONTACTO_LIDER,
    ORDEN_DE_LAS_REGLAS,
    PRIMER_CONTACTO,
    PROSPECTO_DORMIDO,
    RECORDATORIO_DE_REUNION,
    VOLVER_A_LLAMAR,
)
from app.models.entities import (
    ActivityType,
    AuditLog,
    Aviso,
    CallOutcome,
    Lead,
    LeadActivity,
    ScoreCategory,
    Tarea,
    User,
)
from app.services import motor_de_reglas
from app.services.motor_de_reglas import ORDEN_DE_LA_PASADA, cerrar_lo_cumplido, ejecutar

UTC = datetime.timezone.utc
AHORA = datetime.datetime(2026, 9, 23, 9, 0, tzinfo=UTC)


def _hace(**kwargs):
    return AHORA - datetime.timedelta(**kwargs)


@pytest.fixture
def equipo(db_session):
    """Un asesor y un líder activos. El líder es quien recibe lo que se escala."""
    asesor = User(
        email="asesor.motor@plurione.com", full_name="Asesor Motor", role="Commercial_Executive",
        hashed_password="!sin-contrasena:fixture", is_sales_rep=True, capacity=50,
    )
    lider = User(
        email="lider.motor@plurione.com", full_name="Líder Motor", role="Sales_Lead",
        hashed_password="!sin-contrasena:fixture", is_sales_rep=True, capacity=40,
    )
    db_session.add_all([asesor, lider])
    db_session.commit()
    db_session.refresh(asesor)
    db_session.refresh(lider)
    return asesor, lider


def _prospecto(db, asesor=None, *, correo="nuevo@ejemplo.com", creado=None, categoria=None, actividad=None):
    lead = Lead(
        first_name="Nuevo", last_name="Prospecto", email=correo, company="Empresa SA",
        assigned_rep_id=asesor.id if asesor else None,
        created_at=creado or _hace(hours=2),
        last_activity_at=actividad or creado or _hace(hours=2),
        score_category=categoria or ScoreCategory.WARM,
        current_score=80.0 if categoria == ScoreCategory.HOT else 40.0,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def _actividad(db, lead, tipo, *, ocurrida=None, resultado=None, datos=None):
    fila = LeadActivity(
        lead_id=lead.id, activity_type=tipo, channel="Teléfono", source="manual",
        call_outcome=resultado, activity_data=datos or {},
        occurred_at=ocurrida or _hace(hours=1),
    )
    db.add(fila)
    db.commit()
    db.refresh(fila)
    return fila


def _tareas(db, regla=None):
    consulta = db.query(Tarea)
    if regla:
        consulta = consulta.filter(Tarea.regla == regla)
    return consulta.all()


def _avisos(db, regla=None):
    consulta = db.query(Aviso)
    if regla:
        consulta = consulta.filter(Aviso.regla == regla)
    return consulta.all()


def _lideres(db):
    """
    Todas las cuentas de líder activas, no solo la del escenario.

    La base de pruebas ya trae una cuenta `Sales_Lead`, así que lo escalado llega a dos
    personas. Escribir «uno» aquí habría sido escribir el número que salía, no la regla: lo
    que el motor promete es que se entera **cada** líder activo.
    """
    return {
        fila.id
        for fila in db.query(User.id).filter(User.role == "Sales_Lead", User.is_active.is_(True)).all()
    }


# ==============================================================================
# Primer contacto
# ==============================================================================

def test_un_prospecto_asignado_y_sin_contactar_estrena_tarea(db_session, equipo):
    asesor, _ = equipo
    lead = _prospecto(db_session, asesor)

    ejecutar(db_session, ahora=AHORA)

    tareas = _tareas(db_session, PRIMER_CONTACTO)
    assert len(tareas) == 1
    assert tareas[0].lead_id == lead.id
    assert tareas[0].asesor_id == asesor.id
    assert tareas[0].estado == ABIERTA
    # Vence al plazo configurado, contado desde la pasada.
    assert tareas[0].vence_el.replace(tzinfo=UTC) == AHORA + datetime.timedelta(hours=24)


def test_un_prospecto_sin_asesor_no_genera_trabajo_para_nadie(db_session, equipo):
    """Una tarea sin dueño no la ve nadie y no la hace nadie: no se crea."""
    _prospecto(db_session, None)

    ejecutar(db_session, ahora=AHORA)

    assert _tareas(db_session, PRIMER_CONTACTO) == []


def test_repetir_la_pasada_no_duplica_la_tarea(db_session, equipo):
    """
    La garantía de la que depende todo lo demás.

    La pasada se repite: la misma mañana tras un reintento, después de una caída, dos veces
    por un despliegue. Si duplicara, la bandeja se volvería inservible sin que nada fallara.
    """
    asesor, _ = equipo
    _prospecto(db_session, asesor)

    ejecutar(db_session, ahora=AHORA)
    ejecutar(db_session, ahora=AHORA + datetime.timedelta(hours=1))
    ejecutar(db_session, ahora=AHORA + datetime.timedelta(days=1))

    assert len(_tareas(db_session, PRIMER_CONTACTO)) == 1


def test_reasignar_el_prospecto_estrena_la_tarea_de_la_persona_nueva(db_session, equipo):
    """La persona nueva no hereda una tarea cerrada por otra: empieza la suya."""
    asesor, lider = equipo
    lead = _prospecto(db_session, asesor)
    ejecutar(db_session, ahora=AHORA)

    primera = _tareas(db_session, PRIMER_CONTACTO)[0]
    primera.estado = CUMPLIDA
    lead.assigned_rep_id = lider.id
    db_session.commit()

    ejecutar(db_session, ahora=AHORA + datetime.timedelta(hours=1))

    tareas = _tareas(db_session, PRIMER_CONTACTO)
    assert len(tareas) == 2
    assert {t.asesor_id for t in tareas} == {asesor.id, lider.id}


def test_un_prospecto_viejo_no_estrena_primer_contacto(db_session, equipo):
    """
    Pasado el plazo del dormido se ocupa la otra regla.

    Es también lo que impide que la primera pasada tras instalar el capítulo abra una tarea
    por cada prospecto antiguo que hubiera en la base.
    """
    asesor, _ = equipo
    _prospecto(db_session, asesor, creado=_hace(days=60), actividad=_hace(days=60))

    ejecutar(db_session, ahora=AHORA)

    assert _tareas(db_session, PRIMER_CONTACTO) == []


def test_un_correo_abierto_no_es_haberlo_contactado(db_session, equipo):
    """
    Abrir un correo lo hace la persona; contactar lo hacemos nosotros.

    Confundirlos haría que un prospecto muy interesado y completamente desatendido pareciera
    atendido, que es el error más caro que puede cometer esta regla.
    """
    asesor, _ = equipo
    lead = _prospecto(db_session, asesor)
    _actividad(db_session, lead, ActivityType.EMAIL_OPEN)

    ejecutar(db_session, ahora=AHORA)

    assert len(_tareas(db_session, PRIMER_CONTACTO)) == 1


def test_una_llamada_previa_evita_la_tarea(db_session, equipo):
    asesor, _ = equipo
    lead = _prospecto(db_session, asesor)
    _actividad(db_session, lead, ActivityType.PHONE_CALL, resultado=CallOutcome.CONECTO.value)

    ejecutar(db_session, ahora=AHORA)

    assert _tareas(db_session, PRIMER_CONTACTO) == []


# ==============================================================================
# Volver a llamar
# ==============================================================================

def test_una_llamada_sin_respuesta_deja_tarea_a_dos_dias(db_session, equipo):
    asesor, _ = equipo
    lead = _prospecto(db_session, asesor)
    llamada = _actividad(
        db_session, lead, ActivityType.PHONE_CALL,
        resultado=CallOutcome.NO_CONTESTO.value, ocurrida=_hace(hours=3),
    )

    ejecutar(db_session, ahora=AHORA)

    tareas = _tareas(db_session, VOLVER_A_LLAMAR)
    assert len(tareas) == 1
    # Dos días desde LA LLAMADA, no desde hoy: si no, la pasada de mañana la aplazaría otra vez.
    assert tareas[0].vence_el.replace(tzinfo=UTC) == _hace(hours=3) + datetime.timedelta(days=2)
    assert tareas[0].clave == str(llamada.id)


def test_solo_cuenta_la_ultima_llamada(db_session, equipo):
    """Diez intentos seguidos sin respuesta son un trabajo pendiente, no diez."""
    asesor, _ = equipo
    lead = _prospecto(db_session, asesor)
    for horas in (10, 8, 6):
        _actividad(
            db_session, lead, ActivityType.PHONE_CALL,
            resultado=CallOutcome.BUZON.value, ocurrida=_hace(hours=horas),
        )

    ejecutar(db_session, ahora=AHORA)

    assert len(_tareas(db_session, VOLVER_A_LLAMAR)) == 1


def test_si_la_ultima_llamada_se_contesto_no_hay_que_volver_a_llamar(db_session, equipo):
    asesor, _ = equipo
    lead = _prospecto(db_session, asesor)
    _actividad(
        db_session, lead, ActivityType.PHONE_CALL,
        resultado=CallOutcome.NO_CONTESTO.value, ocurrida=_hace(hours=10),
    )
    _actividad(
        db_session, lead, ActivityType.PHONE_CALL,
        resultado=CallOutcome.CONECTO.value, ocurrida=_hace(hours=2),
    )

    ejecutar(db_session, ahora=AHORA)

    assert _tareas(db_session, VOLVER_A_LLAMAR) == []


# ==============================================================================
# Recordatorio de reunión
# ==============================================================================

def test_la_reunion_de_manana_se_recuerda_hoy(db_session, equipo):
    asesor, _ = equipo
    lead = _prospecto(db_session, asesor)
    inicio = AHORA + datetime.timedelta(hours=20)
    _actividad(
        db_session, lead, ActivityType.MEETING_SCHEDULED,
        ocurrida=_hace(days=3), datos={"inicio_de_la_reunion": inicio.isoformat()},
    )

    ejecutar(db_session, ahora=AHORA)

    tareas = _tareas(db_session, RECORDATORIO_DE_REUNION)
    assert len(tareas) == 1
    assert tareas[0].vence_el.replace(tzinfo=UTC) == inicio


def test_la_reunion_de_la_semana_que_viene_todavia_no_se_recuerda(db_session, equipo):
    """El recordatorio es la víspera; avisar el día que se agendó no es recordar."""
    asesor, _ = equipo
    lead = _prospecto(db_session, asesor)
    _actividad(
        db_session, lead, ActivityType.MEETING_SCHEDULED, ocurrida=_hace(hours=1),
        datos={"inicio_de_la_reunion": (AHORA + datetime.timedelta(days=7)).isoformat()},
    )

    ejecutar(db_session, ahora=AHORA)

    assert _tareas(db_session, RECORDATORIO_DE_REUNION) == []


def test_una_reunion_sin_fecha_no_se_recuerda(db_session, equipo):
    """
    `occurred_at` es cuándo se agendó, no cuándo es.

    Recordar sobre esa fecha avisaría siempre tarde, así que una reunión que no dice cuándo
    es no genera recordatorio. No recordar es mejor que recordar el día equivocado.
    """
    asesor, _ = equipo
    lead = _prospecto(db_session, asesor)
    _actividad(db_session, lead, ActivityType.MEETING_SCHEDULED, ocurrida=_hace(hours=1))

    ejecutar(db_session, ahora=AHORA)

    assert _tareas(db_session, RECORDATORIO_DE_REUNION) == []


def test_una_fecha_de_reunion_ilegible_no_tumba_la_pasada(db_session, equipo):
    """Un dato roto de una integración no puede dejar sin avisar al resto del equipo."""
    asesor, _ = equipo
    lead = _prospecto(db_session, asesor)
    _actividad(
        db_session, lead, ActivityType.MEETING_SCHEDULED, ocurrida=_hace(hours=1),
        datos={"inicio_de_la_reunion": "mañana por la tarde"},
    )

    resultados = {r.regla: r for r in ejecutar(db_session, ahora=AHORA)}

    assert resultados[RECORDATORIO_DE_REUNION].error is None
    assert _tareas(db_session, RECORDATORIO_DE_REUNION) == []


# ==============================================================================
# HOT sin contacto, y el escalado
# ==============================================================================

def test_un_hot_desatendido_avisa_a_su_asesor(db_session, equipo):
    asesor, _ = equipo
    lead = _prospecto(db_session, asesor, categoria=ScoreCategory.HOT, creado=_hace(hours=30))

    ejecutar(db_session, ahora=AHORA)

    avisos = _avisos(db_session, HOT_SIN_CONTACTO)
    assert len(avisos) == 1
    assert avisos[0].usuario_id == asesor.id
    assert avisos[0].lead_id == lead.id
    assert avisos[0].leido_en is None


def test_a_las_24_horas_el_lider_todavia_no_se_entera(db_session, equipo):
    asesor, _ = equipo
    _prospecto(db_session, asesor, categoria=ScoreCategory.HOT, creado=_hace(hours=30))

    ejecutar(db_session, ahora=AHORA)

    assert _avisos(db_session, HOT_SIN_CONTACTO_LIDER) == []


def test_a_las_48_horas_sube_al_lider(db_session, equipo):
    asesor, lider = equipo
    _prospecto(db_session, asesor, categoria=ScoreCategory.HOT, creado=_hace(hours=50))

    ejecutar(db_session, ahora=AHORA)

    escalados = _avisos(db_session, HOT_SIN_CONTACTO_LIDER)
    assert {a.usuario_id for a in escalados} == _lideres(db_session)
    assert lider.id in {a.usuario_id for a in escalados}
    # Y el asesor sigue teniendo el suyo: escalar no es mover.
    assert len(_avisos(db_session, HOT_SIN_CONTACTO)) == 1


def test_el_lider_no_se_entera_de_lo_que_el_asesor_no_ha_visto(db_session, equipo):
    """
    Escalar exige que hubiera algo que escalar.

    Si el aviso al asesor no llegó a existir —porque el prospecto no tenía asesor cuando
    tocaba—, subirlo al líder sería inventarse un escalado.
    """
    asesor, _ = equipo
    lead = _prospecto(db_session, None, categoria=ScoreCategory.HOT, creado=_hace(hours=50))

    ejecutar(db_session, ahora=AHORA)
    assert _avisos(db_session, HOT_SIN_CONTACTO_LIDER) == []

    # Ahora sí tiene asesor: primero le llega a él, y solo después sube.
    lead.assigned_rep_id = asesor.id
    db_session.commit()
    ejecutar(db_session, ahora=AHORA + datetime.timedelta(minutes=5))

    assert len(_avisos(db_session, HOT_SIN_CONTACTO)) == 1
    assert len(_avisos(db_session, HOT_SIN_CONTACTO_LIDER)) == len(_lideres(db_session))


def test_repetir_la_pasada_no_llena_la_campana(db_session, equipo):
    asesor, _ = equipo
    _prospecto(db_session, asesor, categoria=ScoreCategory.HOT, creado=_hace(hours=50))

    for dias in range(4):
        ejecutar(db_session, ahora=AHORA + datetime.timedelta(days=dias))

    assert len(_avisos(db_session, HOT_SIN_CONTACTO)) == 1
    # Uno por líder, y ni uno más por mucho que se repita la pasada.
    assert len(_avisos(db_session, HOT_SIN_CONTACTO_LIDER)) == len(_lideres(db_session))


def test_un_silencio_nuevo_merece_un_aviso_nuevo(db_session, equipo):
    """
    Dos episodios distintos, dos avisos.

    Con una clave fija el segundo no llegaría jamás; con la fecha del día llegaría uno cada
    mañana. La clave es la última actividad conocida, que es lo que identifica el silencio.
    """
    asesor, _ = equipo
    lead = _prospecto(db_session, asesor, categoria=ScoreCategory.HOT, creado=_hace(days=40))
    ejecutar(db_session, ahora=AHORA)
    assert len(_avisos(db_session, HOT_SIN_CONTACTO)) == 1

    # Lo llaman, y vuelve a quedarse quieto (se borra el contacto para simular el silencio
    # posterior, que es lo que esta prueba mide).
    lead.last_activity_at = AHORA
    db_session.commit()

    ejecutar(db_session, ahora=AHORA + datetime.timedelta(days=5))

    assert len(_avisos(db_session, HOT_SIN_CONTACTO)) == 2


# ==============================================================================
# Dormido
# ==============================================================================

def test_treinta_dias_sin_nada_marcan_dormido_y_avisan(db_session, equipo):
    asesor, _ = equipo
    lead = _prospecto(db_session, asesor, creado=_hace(days=60), actividad=_hace(days=45))

    ejecutar(db_session, ahora=AHORA)

    db_session.refresh(lead)
    assert lead.dormido_desde is not None
    avisos = _avisos(db_session, PROSPECTO_DORMIDO)
    assert len(avisos) == 1 and avisos[0].usuario_id == asesor.id


def test_la_marca_evita_avisar_cada_manana(db_session, equipo):
    """Sin la marca, un prospecto quieto generaría un aviso al día para siempre."""
    asesor, _ = equipo
    _prospecto(db_session, asesor, creado=_hace(days=60), actividad=_hace(days=45))

    for dias in range(5):
        ejecutar(db_session, ahora=AHORA + datetime.timedelta(days=dias))

    assert len(_avisos(db_session, PROSPECTO_DORMIDO)) == 1


def test_un_dormido_sin_asesor_lo_ve_el_lider(db_session, equipo):
    _, lider = equipo
    _prospecto(db_session, None, creado=_hace(days=60), actividad=_hace(days=45))

    ejecutar(db_session, ahora=AHORA)

    avisos = _avisos(db_session, PROSPECTO_DORMIDO)
    assert {a.usuario_id for a in avisos} == _lideres(db_session)
    assert lider.id in {a.usuario_id for a in avisos}


@pytest.mark.asyncio
async def test_cualquier_actividad_lo_despierta(db_session, equipo):
    from app.services.registro_de_actividad import Evento, registrar_evento

    asesor, _ = equipo
    lead = _prospecto(db_session, asesor, creado=_hace(days=60), actividad=_hace(days=45))
    ejecutar(db_session, ahora=AHORA)
    db_session.refresh(lead)
    assert lead.dormido_desde is not None

    await registrar_evento(
        db_session, Evento(fuente="manual", tipo=ActivityType.PHONE_CALL, resultado_de_llamada="CONECTO"),
        lead=lead, generar_explicacion=False,
    )

    db_session.refresh(lead)
    assert lead.dormido_desde is None


# ==============================================================================
# Cerrar lo cumplido
# ==============================================================================

@pytest.mark.asyncio
async def test_una_llamada_contestada_cierra_volver_a_llamar_en_el_momento(db_session, equipo):
    """
    En el momento, no en la pasada de mañana.

    Si esperara al barrido diario, el asesor vería toda la tarde en su bandeja una llamada
    que acaba de hacer, y la bandeja dejaría de creerse.
    """
    from app.services.registro_de_actividad import Evento, registrar_evento

    asesor, _ = equipo
    lead = _prospecto(db_session, asesor)
    _actividad(
        db_session, lead, ActivityType.PHONE_CALL,
        resultado=CallOutcome.NO_CONTESTO.value, ocurrida=_hace(hours=3),
    )
    ejecutar(db_session, ahora=AHORA)
    assert _tareas(db_session, VOLVER_A_LLAMAR)[0].estado == ABIERTA

    await registrar_evento(
        db_session, Evento(fuente="manual", tipo=ActivityType.PHONE_CALL, resultado_de_llamada="CONECTO"),
        lead=lead, generar_explicacion=False,
    )

    tarea = _tareas(db_session, VOLVER_A_LLAMAR)[0]
    assert tarea.estado == CUMPLIDA
    assert tarea.cerrada_en is not None
    # La cerró el sistema: nadie dijo «ya la hice».
    assert tarea.cerrada_por_id is None


@pytest.mark.asyncio
async def test_otra_llamada_sin_respuesta_no_cierra_nada(db_session, equipo):
    """Es justo lo que la tarea está esperando: que alguien conteste."""
    from app.services.registro_de_actividad import Evento, registrar_evento

    asesor, _ = equipo
    lead = _prospecto(db_session, asesor)
    _actividad(
        db_session, lead, ActivityType.PHONE_CALL,
        resultado=CallOutcome.BUZON.value, ocurrida=_hace(hours=3),
    )
    ejecutar(db_session, ahora=AHORA)

    await registrar_evento(
        db_session, Evento(fuente="manual", tipo=ActivityType.PHONE_CALL, resultado_de_llamada="BUZON"),
        lead=lead, generar_explicacion=False,
    )

    assert _tareas(db_session, VOLVER_A_LLAMAR)[0].estado == ABIERTA


@pytest.mark.asyncio
async def test_una_llamada_sin_respuesta_cierra_el_primer_contacto(db_session, equipo):
    """
    El asesor hizo el trabajo aunque no hubiera nadie al otro lado.

    Lo contrario dejaría «primer contacto» y «volver a llamar» abiertas a la vez sobre el
    mismo prospecto, que es el ruido que una bandeja de trabajo no se puede permitir.
    """
    from app.services.registro_de_actividad import Evento, registrar_evento

    asesor, _ = equipo
    lead = _prospecto(db_session, asesor)
    ejecutar(db_session, ahora=AHORA)
    assert _tareas(db_session, PRIMER_CONTACTO)[0].estado == ABIERTA

    await registrar_evento(
        db_session, Evento(fuente="manual", tipo=ActivityType.PHONE_CALL, resultado_de_llamada="NO_CONTESTO"),
        lead=lead, generar_explicacion=False,
    )

    assert _tareas(db_session, PRIMER_CONTACTO)[0].estado == CUMPLIDA


def test_el_barrido_cierra_lo_que_se_escribio_por_otro_camino(db_session, equipo):
    """
    Una actividad escrita sin pasar por el registro —o antes de que existiera el capítulo—
    también tiene que cerrar lo suyo. Por eso la pasada vuelve a llamar a la misma función.
    """
    asesor, _ = equipo
    lead = _prospecto(db_session, asesor)
    ejecutar(db_session, ahora=AHORA)
    assert _tareas(db_session, PRIMER_CONTACTO)[0].estado == ABIERTA

    _actividad(db_session, lead, ActivityType.PROPOSAL_SENT, ocurrida=AHORA)

    ejecutar(db_session, ahora=AHORA + datetime.timedelta(days=1))

    assert _tareas(db_session, PRIMER_CONTACTO)[0].estado == CUMPLIDA


def test_el_barrido_no_cierra_lo_que_no_ha_ocurrido(db_session, equipo):
    """
    La prueba que impide el atajo.

    El barrido no tiene actividad que mirar, así que la condición general lo deja pasar y
    hay que volver a preguntar si de verdad hubo contacto. Sin esa segunda pregunta, el
    barrido cerraría cada mañana todas las tareas de primer contacto del mundo.
    """
    asesor, _ = equipo
    _prospecto(db_session, asesor)
    ejecutar(db_session, ahora=AHORA)

    ejecutar(db_session, ahora=AHORA + datetime.timedelta(days=1))

    assert _tareas(db_session, PRIMER_CONTACTO)[0].estado == ABIERTA


def test_el_recordatorio_de_una_reunion_pasada_deja_de_ser_trabajo(db_session, equipo):
    asesor, _ = equipo
    lead = _prospecto(db_session, asesor)
    inicio = AHORA + datetime.timedelta(hours=20)
    _actividad(
        db_session, lead, ActivityType.MEETING_SCHEDULED, ocurrida=_hace(days=3),
        datos={"inicio_de_la_reunion": inicio.isoformat()},
    )
    ejecutar(db_session, ahora=AHORA)
    assert _tareas(db_session, RECORDATORIO_DE_REUNION)[0].estado == ABIERTA

    ejecutar(db_session, ahora=inicio + datetime.timedelta(hours=1))

    assert _tareas(db_session, RECORDATORIO_DE_REUNION)[0].estado == CUMPLIDA


# ==============================================================================
# La pasada, como conjunto
# ==============================================================================

def test_la_pasada_corre_todas_las_reglas_y_el_cierre(db_session, equipo):
    resultados = ejecutar(db_session, ahora=AHORA)

    assert [r.regla for r in resultados] == list(ORDEN_DE_LA_PASADA)
    assert set(ORDEN_DE_LA_PASADA) == {"cerrar_lo_cumplido", *ORDEN_DE_LAS_REGLAS}


def test_cada_regla_deja_su_asiento_en_la_bitacora(db_session, equipo):
    asesor, _ = equipo
    _prospecto(db_session, asesor)

    ejecutar(db_session, ahora=AHORA)

    asientos = db_session.query(AuditLog).filter(AuditLog.action == "regla.ejecucion").all()
    assert len(asientos) == len(ORDEN_DE_LA_PASADA)
    assert {a.entity_id for a in asientos} == set(ORDEN_DE_LA_PASADA)
    assert all(a.outcome == "OK" for a in asientos)

    primer_contacto = next(a for a in asientos if a.entity_id == PRIMER_CONTACTO)
    assert primer_contacto.event_metadata["tareas_creadas"] == 1
    assert primer_contacto.event_metadata["etiqueta"] == "Primer contacto"
    # Sin actor: no la pidió nadie, la disparó el reloj.
    assert primer_contacto.actor_email is None


def test_una_regla_que_falla_no_impide_las_demas(db_session, equipo, monkeypatch):
    """
    Que el recordatorio de las reuniones falle un martes no puede dejar sin avisar a nadie
    de los HOT desatendidos de ese martes.
    """
    asesor, _ = equipo
    _prospecto(db_session, asesor, categoria=ScoreCategory.HOT, creado=_hace(hours=30))

    def rota(_ctx):
        raise RuntimeError("la regla explotó")

    monkeypatch.setitem(motor_de_reglas._FUNCIONES, RECORDATORIO_DE_REUNION, rota)

    resultados = {r.regla: r for r in ejecutar(db_session, ahora=AHORA)}

    assert resultados[RECORDATORIO_DE_REUNION].error == "RuntimeError"
    assert resultados[HOT_SIN_CONTACTO].avisos == 1
    assert len(_avisos(db_session, HOT_SIN_CONTACTO)) == 1
    asiento = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "regla.ejecucion", AuditLog.entity_id == RECORDATORIO_DE_REUNION)
        .first()
    )
    assert asiento.outcome == "ERROR"


def test_el_motor_no_toca_el_score(db_session, equipo):
    """Nadie se vuelve más interesante porque a su asesor le quede trabajo por hacer."""
    asesor, _ = equipo
    lead = _prospecto(db_session, asesor, categoria=ScoreCategory.HOT, creado=_hace(hours=50))
    antes = lead.current_score

    ejecutar(db_session, ahora=AHORA)

    db_session.refresh(lead)
    assert lead.current_score == antes
    assert lead.score_category == ScoreCategory.HOT


def test_la_pasada_diaria_ejecuta_el_motor(db_session, equipo, capsys):
    """El motor corre donde se dijo que correría: en la pasada que ya existía."""
    from scripts import retencion_historial

    asesor, _ = equipo
    _prospecto(db_session, asesor)

    assert retencion_historial.main([]) == 0

    salida = capsys.readouterr().out
    for clave in ORDEN_DE_LA_PASADA:
        assert f"[REGLAS] {clave}:" in salida
    assert len(_tareas(db_session, PRIMER_CONTACTO)) == 1


def test_simular_no_crea_nada(db_session, equipo, capsys):
    """Una simulación que creara tareas no sería una simulación."""
    from scripts import retencion_historial

    asesor, _ = equipo
    _prospecto(db_session, asesor)

    assert retencion_historial.main(["--simular"]) == 0

    assert "[REGLAS] Simulacion" in capsys.readouterr().out
    assert _tareas(db_session) == []
    assert _avisos(db_session) == []


def test_cerrar_lo_cumplido_no_confirma_por_su_cuenta(db_session, equipo):
    """
    Lo que cierra tiene que poder deshacerse con la actividad que lo provocó.

    Si confirmara por su cuenta, una actividad que falla al puntuarse dejaría igualmente
    cerrada una tarea que nadie hizo.
    """
    asesor, _ = equipo
    lead = _prospecto(db_session, asesor)
    ejecutar(db_session, ahora=AHORA)
    _actividad(db_session, lead, ActivityType.PROPOSAL_SENT, ocurrida=AHORA)

    cerradas = cerrar_lo_cumplido(db_session, lead, None, ahora=AHORA)
    assert cerradas == 1
    db_session.rollback()

    assert _tareas(db_session, PRIMER_CONTACTO)[0].estado == ABIERTA
