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
    """El motor corre donde se dijo que correría: en la pasada que ya existía.

    OJO CON LA FECHA DEL PROSPECTO, y es la razón de que no se use `AHORA`. Esta es la
    única prueba del archivo que entra por el guion de verdad, así que el motor mira el
    reloj **real** y no el contexto que arma la prueba. Con la fecha fija de `AHORA`
    —23-09-2026— el prospecto se salió de la ventana de `REGLA_DORMIDO_DIAS` (30 días)
    el 23-10-2026 a las 07:00 UTC, y la prueba se puso roja sola, sin que nadie tocara
    nada. Una fecha escrita a mano medida contra el reloj real es una bomba de relojería:
    pasa todos los días hasta el que no.
    """
    from scripts import retencion_historial

    asesor, _ = equipo
    _prospecto(db_session, asesor,
               creado=datetime.datetime.now(UTC) - datetime.timedelta(hours=2))

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


# ==============================================================================
# Las vueltas que nadie dio: una tanda de uno no prueba un bucle
# ==============================================================================
#
# Todas las pruebas de arriba montan UN prospecto, UNA reunion, UN destinatario. Una regla
# que solo atendiera al primero de la tanda pasaria entera en verde, y eso no es una
# hipotesis: es la septima linea de lo que este repositorio aprendio por las malas -«una
# regla que reparte ordenando por un campo no reparte, ordena, y cada ficha sale con dueno,
# asi que ninguna prueba de un caso lo ve»-. Lo que falta medir no es el caso: es la vuelta.

def test_dos_llamadas_sin_contestar_dejan_dos_tareas_y_no_una(db_session, equipo):
    """
    La regla recorre la tanda entera, no el primero de la tanda.

    Con una sola ficha, un `break` en lugar del final del bucle, o un `return` dentro de el,
    darian exactamente el mismo resultado que el codigo correcto. Dos fichas los separan.
    Y no es un bucle cualquiera: de aqui sale la lista de a quien hay que volver a llamar
    hoy, asi que atender solo a la primera deja al resto sin llamada y sin rastro.
    """
    asesor, _ = equipo
    primera = _prospecto(db_session, asesor, correo="llama.uno@ejemplo.com", creado=_hace(days=5))
    segunda = _prospecto(db_session, asesor, correo="llama.dos@ejemplo.com", creado=_hace(days=5))
    for lead in (primera, segunda):
        _actividad(db_session, lead, ActivityType.PHONE_CALL,
                   ocurrida=_hace(days=3), resultado=CallOutcome.NO_CONTESTO)

    resultado = motor_de_reglas.regla_volver_a_llamar(
        motor_de_reglas.Contexto(db=db_session, ahora=AHORA, lideres=sorted(_lideres(db_session)))
    )
    db_session.commit()

    tareas = _tareas(db_session, VOLVER_A_LLAMAR)
    assert resultado.tareas == 2
    assert {t.lead_id for t in tareas} == {primera.id, segunda.id}


def test_dos_reuniones_de_manana_se_recuerdan_las_dos(db_session, equipo):
    """
    Lo mismo en el recordatorio de reunion, que tiene su propio bucle y su propio salto.

    Este tiene dos `continue` antes del cuerpo -la reunion sin fecha y la que todavia no
    toca- y los dos estaban probados con un caso cada uno. Lo que no estaba probado es que
    despues de uno de esos saltos el bucle SIGA: una reunion que no toca seguida de una que
    si, que es el dia normal de cualquier semana con agenda.
    """
    asesor, _ = equipo
    manana = (AHORA + datetime.timedelta(hours=20)).isoformat()
    la_semana_que_viene = (AHORA + datetime.timedelta(days=8)).isoformat()
    cerca = _prospecto(db_session, asesor, correo="reunion.cerca@ejemplo.com")
    lejos = _prospecto(db_session, asesor, correo="reunion.lejos@ejemplo.com")
    otra_cerca = _prospecto(db_session, asesor, correo="reunion.cerca2@ejemplo.com")
    # En medio la que no toca, para que el salto tenga que dejar seguir al bucle.
    for lead, cuando in ((cerca, manana), (lejos, la_semana_que_viene), (otra_cerca, manana)):
        _actividad(db_session, lead, ActivityType.MEETING_SCHEDULED,
                   datos={"inicio_de_la_reunion": cuando})

    resultado = motor_de_reglas.regla_recordatorio_de_reunion(
        motor_de_reglas.Contexto(db=db_session, ahora=AHORA, lideres=sorted(_lideres(db_session)))
    )
    db_session.commit()

    assert resultado.tareas == 2
    recordadas = {t.lead_id for t in _tareas(db_session, RECORDATORIO_DE_REUNION)}
    assert recordadas == {cerca.id, otra_cerca.id}
    assert lejos.id not in recordadas


def test_un_dormido_sin_asesor_avisa_a_todos_los_lideres(db_session, equipo):
    """
    Sin dueno, el aviso va a CADA lider activo, y ahi el bucle de destinatarios da vueltas.

    Es la unica regla con un bucle anidado -prospectos y, dentro, destinatarios- y la vuelta
    de dentro no se recorria: las pruebas de dormido usaban fichas con asesor, o sea un
    destinatario. Una ficha sin asesor que lleva un mes muerta es justo la que nadie va a
    reclamar, asi que si el aviso se queda en el primer lider puede no llegarle a quien
    reparte.
    """
    huerfano = _prospecto(
        db_session, None, correo="dormido.sin.dueno@ejemplo.com",
        creado=_hace(days=90), actividad=_hace(days=60),
    )
    lideres = sorted(_lideres(db_session))
    assert len(lideres) >= 2, "la base de pruebas trae mas de un lider; de eso vive esta prueba"

    resultado = motor_de_reglas.regla_prospecto_dormido(
        motor_de_reglas.Contexto(db=db_session, ahora=AHORA, lideres=lideres)
    )
    db_session.commit()

    avisados = {
        a.usuario_id for a in _avisos(db_session, PROSPECTO_DORMIDO) if a.lead_id == huerfano.id
    }
    assert avisados == set(lideres)
    assert resultado.avisos == len(lideres)


# ==============================================================================
# Las reglas de direccion cuando no hay direccion
# ==============================================================================

def test_sin_ningun_lider_activo_las_dos_reglas_que_le_hablan_no_hacen_nada(db_session, equipo):
    """
    Las dos reglas que escriben AL LIDER salen temprano si no hay ninguno.

    No es un caso de laboratorio: una baja, o un cambio de rol, deja el sistema sin
    `Sales_Lead` durante un rato, y la pasada de madrugada corre igual. Sin la salida
    temprana, `regla_desenlaces_suficientes` haria antes sus consultas sobre la tabla de
    desenlaces cada noche para no escribir nada.

    Lo que esta prueba sujeta es que no se escribe nada **a nadie**: un aviso con
    `usuario_id` vacio, o escalado al asesor en lugar del lider, seria contarle al asesor
    justo lo que la regla existe para no contarle -que el lider ya sabe que no lo ha
    atendido-.
    """
    sin_lideres = motor_de_reglas.Contexto(db=db_session, ahora=AHORA, lideres=[])
    _prospecto(
        db_session, equipo[0], correo="hot.desatendido@ejemplo.com",
        creado=_hace(days=4), actividad=_hace(days=4), categoria=ScoreCategory.HOT,
    )

    del_lider = motor_de_reglas.regla_hot_sin_contacto_lider(sin_lideres)
    de_desenlaces = motor_de_reglas.regla_desenlaces_suficientes(sin_lideres)
    db_session.commit()

    assert (del_lider.avisos, de_desenlaces.avisos) == (0, 0)
    assert _avisos(db_session, HOT_SIN_CONTACTO_LIDER) == []


# ==============================================================================
# El barrido que repasa prospectos que ya no estan o que ya se cerraron
# ==============================================================================

def test_el_barrido_nunca_ve_una_tarea_sin_ficha(db_session, equipo):
    """
    La premisa del `pragma` del barrido, medida en sus propios terminos.

    La primera version de esta prueba borraba el prospecto, dejaba su tarea y comprobaba que
    el barrido «no levantaba». No comprobaba nada: `tareas.lead_id` declara
    `ondelete=CASCADE`, asi que al irse la ficha se va su tarea y el barrido no se encuentra
    ninguna huerfana. La prueba pasaba porque no habia nada que saltar, y el `if lead is
    None` quedaba sin recorrer igual —lo decia la cobertura, no la prueba—.

    Asi que lo que se mide es la premisa: borrar la ficha se lleva su tarea, de modo que la
    lista que el barrido recorre no puede traer identificadores que no resuelvan. El `if`
    queda marcado como red de ultimo recurso, con su motivo, y no fingido con una prueba que
    no puede provocarlo. La clausula, derivada del esquema y no escrita a mano, la comprueba
    `test_las_cascadas_declaradas.py` sobre las dieciocho claves.
    """
    asesor, _ = equipo
    vivo = _prospecto(db_session, asesor, correo="sigue.vivo@ejemplo.com")
    fantasma = _prospecto(db_session, asesor, correo="ya.no.esta@ejemplo.com")
    for lead in (vivo, fantasma):
        db_session.add(Tarea(
            lead_id=lead.id, asesor_id=asesor.id, regla=PRIMER_CONTACTO,
            clave=f"{lead.id}-barrido", estado=ABIERTA,
            motivo="Contactar", vence_el=AHORA + datetime.timedelta(days=1),
        ))
    db_session.commit()
    ido = fantasma.id

    db_session.query(Lead).filter(Lead.id == ido).delete()
    db_session.commit()

    # La cascada se la llevo: no queda tarea que apunte a una ficha que no esta.
    assert db_session.query(Tarea).filter(Tarea.lead_id == ido).count() == 0
    abiertas = db_session.query(Tarea.lead_id).filter(Tarea.estado == ABIERTA).distinct().all()
    vivos = {fila.id for fila in db_session.query(Lead.id).all()}
    assert {fila.lead_id for fila in abiertas} <= vivos, (
        "la lista que recorre el barrido no puede traer fichas que no existan"
    )

    # Y la pasada sigue funcionando sobre el que queda.
    resultado = motor_de_reglas.regla_cerrar_lo_cumplido(
        motor_de_reglas.Contexto(db=db_session, ahora=AHORA, lideres=sorted(_lideres(db_session)))
    )
    db_session.commit()

    assert resultado.cerradas >= 0
    assert db_session.query(Tarea).filter(Tarea.lead_id == vivo.id).count() == 1


# ==============================================================================
# Repetir la pasada: tres reglas con su propia idempotencia, y ninguna probada
# ==============================================================================
#
# La pasada corre cada madrugada y `test_repetir_la_pasada_no_duplica_la_tarea` solo cubria
# «primer contacto». Las otras tres escriben con su propia clave -la llamada concreta, la
# reunion concreta, el episodio de silencio- y en las tres el camino de «ya estaba» pasa por
# dentro del bucle: si la segunda pasada duplicara, el asesor abriria la bandeja con la misma
# tarea siete veces el lunes siguiente, que es la forma de dejar de usar una bandeja.

def test_repetir_la_pasada_no_duplica_la_tarea_de_volver_a_llamar(db_session, equipo):
    """La clave es la llamada concreta: el mismo intento releido no es otra tarea."""
    asesor, _ = equipo
    lead = _prospecto(db_session, asesor, correo="llama.otra.vez@ejemplo.com", creado=_hace(days=5))
    _actividad(db_session, lead, ActivityType.PHONE_CALL,
               ocurrida=_hace(days=3), resultado=CallOutcome.NO_CONTESTO)
    ctx = motor_de_reglas.Contexto(db=db_session, ahora=AHORA, lideres=sorted(_lideres(db_session)))

    primera = motor_de_reglas.regla_volver_a_llamar(ctx)
    db_session.commit()
    segunda = motor_de_reglas.regla_volver_a_llamar(ctx)
    db_session.commit()

    assert (primera.tareas, segunda.tareas) == (1, 0)
    assert len([t for t in _tareas(db_session, VOLVER_A_LLAMAR) if t.lead_id == lead.id]) == 1


def test_repetir_la_pasada_no_duplica_el_recordatorio_de_reunion(db_session, equipo):
    """La clave es la reunion concreta, no el dia: la vispera se recuerda una vez."""
    asesor, _ = equipo
    lead = _prospecto(db_session, asesor, correo="reunion.otra.vez@ejemplo.com")
    _actividad(db_session, lead, ActivityType.MEETING_SCHEDULED,
               datos={"inicio_de_la_reunion": (AHORA + datetime.timedelta(hours=20)).isoformat()})
    ctx = motor_de_reglas.Contexto(db=db_session, ahora=AHORA, lideres=sorted(_lideres(db_session)))

    primera = motor_de_reglas.regla_recordatorio_de_reunion(ctx)
    db_session.commit()
    segunda = motor_de_reglas.regla_recordatorio_de_reunion(ctx)
    db_session.commit()

    assert (primera.tareas, segunda.tareas) == (1, 0)
    assert len([t for t in _tareas(db_session, RECORDATORIO_DE_REUNION) if t.lead_id == lead.id]) == 1


def test_repetir_la_pasada_no_duplica_el_aviso_de_dormido(db_session, equipo):
    """
    Aqui la idempotencia esta DENTRO del bucle de destinatarios, y es la que faltaba.

    `test_la_marca_evita_avisar_cada_manana` comprueba la otra mitad -la marca
    `dormido_desde` hace que la regla ni mire a esa ficha-, asi que el camino de «el aviso ya
    estaba» no se recorria nunca. Se provoca quitando la marca entre las dos pasadas, que es
    lo que hace cualquier actividad: el prospecto se despierta, vuelve a dormirse, y el
    episodio de silencio sigue siendo el mismo.
    """
    huerfano = _prospecto(
        db_session, None, correo="dormido.repetido@ejemplo.com",
        creado=_hace(days=90), actividad=_hace(days=60),
    )
    lideres = sorted(_lideres(db_session))
    ctx = motor_de_reglas.Contexto(db=db_session, ahora=AHORA, lideres=lideres)

    primera = motor_de_reglas.regla_prospecto_dormido(ctx)
    db_session.commit()
    # La marca se quita a mano: sin eso la regla no vuelve a mirar esta ficha y el camino de
    # «el aviso ya estaba» no se recorre -que es por lo que no se recorria-.
    huerfano.dormido_desde = None
    db_session.commit()
    segunda = motor_de_reglas.regla_prospecto_dormido(ctx)
    db_session.commit()

    assert primera.avisos == len(lideres)
    assert segunda.avisos == 0, "el episodio de silencio es el mismo, asi que el aviso tambien"
    assert segunda.marcados == 1, "la ficha se vuelve a marcar; lo que no se repite es el aviso"
    del_huerfano = [a for a in _avisos(db_session, PROSPECTO_DORMIDO) if a.lead_id == huerfano.id]
    assert len(del_huerfano) == len(lideres)


def test_el_barrido_descarta_las_tareas_de_un_prospecto_ya_cerrado(db_session, equipo):
    """
    Un prospecto en una etapa sin seguimiento no tiene tareas que cumplir: se descartan.

    Es el camino del capitulo 30 para lo que se cerro por fuera del servicio de cierre -una
    carga del CRM, una edicion a mano, una ficha cerrada antes de que el desenlace
    existiera-. Sin el, el asesor sigue viendo en su bandeja «contactar a X» de alguien que
    ya compro o que ya dijo que no, que es la forma mas rapida de que una bandeja deje de
    mirarse.
    """
    from app.models.entities import LeadStatus

    asesor, _ = equipo
    cerrado = _prospecto(db_session, asesor, correo="ya.cerrado@ejemplo.com")
    cerrado.status = LeadStatus.LOST
    db_session.add(Tarea(
        lead_id=cerrado.id, asesor_id=asesor.id, regla=PRIMER_CONTACTO,
        clave=f"{cerrado.id}-cerrado", estado=ABIERTA,
        motivo="Contactar", vence_el=AHORA + datetime.timedelta(days=1),
    ))
    db_session.commit()
    assert LeadStatus.LOST in motor_de_reglas._ETAPAS_SIN_SEGUIMIENTO

    resultado = motor_de_reglas.regla_cerrar_lo_cumplido(
        motor_de_reglas.Contexto(db=db_session, ahora=AHORA, lideres=sorted(_lideres(db_session)))
    )
    db_session.commit()

    assert resultado.cerradas >= 1
    quedan = db_session.query(Tarea).filter(
        Tarea.lead_id == cerrado.id, Tarea.estado == ABIERTA
    ).count()
    assert quedan == 0


def test_cerrar_lo_cumplido_con_commit_confirma_y_sin_el_no(db_session, equipo):
    """
    `commit=True` confirma de verdad; el valor por defecto no, y eso no es un detalle.

    La funcion la llama `registrar_evento` EN MEDIO de una transaccion que todavia puede
    fallar -la actividad, el score, la auditoria- y por eso no confirma por su cuenta:
    cerrar la tarea de un contacto cuya actividad acabo rechazandose dejaria la bandeja
    diciendo que algo se hizo. La pasada diaria, en cambio, la llama como barrido y si
    quiere confirmar.

    Se mide escuchando el evento `commit` de la sesion, que es la unica forma de distinguir
    «se confirmo» de «se escribio y alguien confirmo despues»: con `pysqlite` las dos cosas
    dejan la base igual. Es el mismo procedimiento que el sello del esquema.
    """
    from sqlalchemy import event

    asesor, _ = equipo
    lead = _prospecto(db_session, asesor, correo="despierta@ejemplo.com")
    lead.dormido_desde = _hace(days=10)
    db_session.add(Tarea(
        lead_id=lead.id, asesor_id=asesor.id, regla=PRIMER_CONTACTO,
        clave=f"{lead.id}-commit", estado=ABIERTA,
        motivo="Contactar", vence_el=AHORA + datetime.timedelta(days=1),
    ))
    db_session.commit()
    actividad = _actividad(db_session, lead, ActivityType.PHONE_CALL,
                           ocurrida=_hace(hours=1), resultado=CallOutcome.CONECTO)

    confirmaciones = []

    def apuntar(_sesion):
        confirmaciones.append(1)

    event.listen(db_session, "after_commit", apuntar)
    try:
        cerradas = cerrar_lo_cumplido(db_session, lead, actividad, ahora=AHORA, commit=True)
    finally:
        event.remove(db_session, "after_commit", apuntar)

    assert cerradas >= 1
    assert confirmaciones, "con commit=True la funcion confirma ella misma"
    # Y de paso lo despierta: la marca decia «nadie lo toca» y acaban de tocarlo.
    assert lead.dormido_desde is None
