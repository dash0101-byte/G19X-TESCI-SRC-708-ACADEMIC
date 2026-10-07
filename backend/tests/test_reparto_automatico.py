"""
El reparto automático del capítulo 46: quién recibe el prospecto que acaba de llegar.

Cierra el punto 10 de §6.2 (H-6). Lo que había era un `if` en el scoring: si la ficha salía
`HOT` y no tenía dueño, se la quedaba quien tuviera el `capacity` más alto. Las dos mitades
estaban mal —una ficha `WARM` esperaba al líder, y `capacity` es la cartera máxima declarada,
no la que alguien tiene—, así que lo que estas pruebas vigilan no es «se asigna un asesor»,
que es lo fácil, sino las cuatro cosas que fallarían sin que nadie viera un error:

* **el reparto reparte.** Una tanda entera en la misma cuenta pasa cualquier prueba que solo
  compruebe que la ficha tiene dueño;
* **lo que ya se decidió no se deshace.** Una reasignación a mano, o un prospecto que el
  líder dejó a propósito sin asesor, no pueden volver atrás en el siguiente recálculo;
* **lo que se reparte produce el mismo trabajo** que lo que se asigna a mano: la tarea de
  primer contacto y el aviso del capítulo 28 salen de una consulta sobre el estado, y la
  única forma de comprobar que el estado es el mismo es compararlos;
* **sin asesores no hay error.** Una instalación recién puesta en marcha deja los prospectos
  sin dueño y el líder los ve, como antes de este capítulo.
"""
import datetime
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from app.core.agenda import ABIERTA, HOT_SIN_CONTACTO, PRIMER_CONTACTO
from app.core.audit import ACCION_LEAD_REPARTO_AUTOMATICO
from app.core.config import settings
from app.models.entities import (
    AuditLog,
    Aviso,
    Campaign,
    Lead,
    LeadStatus,
    ScoreCategory,
    ScoreHistory,
    Tarea,
    User,
)
from app.services import motor_de_reglas, reparto_automatico
from app.services.motor_de_reglas import ejecutar
from app.services.reparto_automatico import (
    MAS_TIEMPO_SIN_RECIBIR,
    MENOS_CARTERA_ABIERTA,
    NO_ES_UN_ALTA,
    ORDEN_ESTABLE,
    PUBLICACION_CON_RESPONSABLE,
    UNICO_CANDIDATO,
    YA_TIENE_ASESOR,
    elegir,
    por_que_no_se_reparte,
    repartir,
)
from app.services.scoring_service import ScoringService
from sqlalchemy.dialects import postgresql

UTC = datetime.timezone.utc
AHORA = datetime.datetime(2026, 10, 6, 9, 0, tzinfo=UTC)

RAIZ = Path(__file__).resolve().parents[2]
GUARDA = "scripts/guarda_del_reparto_automatico.py"


def _hace(**kwargs):
    return AHORA - datetime.timedelta(**kwargs)


@pytest.fixture(autouse=True)
def interruptor_encendido(monkeypatch):
    """El reparto, encendido: la prueba no puede depender del entorno de quien la corre."""
    monkeypatch.setattr(settings, "REPARTO_AUTOMATICO_ACTIVO", True)


@pytest.fixture
def equipo(db_session):
    """
    Tres asesoras activas, una de baja y un administrador de TI.

    Las dos últimas están aquí a propósito: una prueba con solo asesoras activas pasaría
    igual con el filtro roto, que es lo que hacía inútil probar el alcance con cartera de un
    solo dueño (conftest, `cartera_repartida`).
    """
    cuentas = [
        User(
            email=f"{nombre}@plurione.com", full_name=nombre.title(), role=rol,
            hashed_password="!sin-contrasena:fixture",  # noqa: S106  hash inutilizable: no inician sesión
            is_sales_rep=asesor, is_active=activa, capacity=50 if asesor else None,
        )
        for nombre, rol, asesor, activa in (
            ("ana", "Commercial_Executive", True, True),
            ("beto", "Commercial_Executive", True, True),
            ("ceci", "Commercial_Executive", True, True),
            ("dora", "Commercial_Executive", True, False),
            ("elmer", "System_Admin", False, True),
        )
    ]
    db_session.add_all(cuentas)
    db_session.commit()
    for cuenta in cuentas:
        db_session.refresh(cuenta)
    ana, beto, ceci, dora, elmer = cuentas
    return {"ana": ana, "beto": beto, "ceci": ceci, "baja": dora, "admin": elmer}


_SIGUIENTE = [0]


def _ficha(db, *, asesor=None, campana=None, estado=LeadStatus.NEW, creado=None, categoria=None):
    """Una ficha en la base, sin pasar por el scoring. Para preparar el escenario."""
    _SIGUIENTE[0] += 1
    numero = _SIGUIENTE[0]
    lead = Lead(
        first_name="Persona", last_name=f"Numero{numero}",
        email=f"persona{numero}@ejemplo.mx", company="Empresa SA",
        job_title="CTO", industry="FinTech", company_size="201-1000",
        assigned_rep_id=asesor.id if asesor is not None else None,
        campaign_id=campana.id if campana is not None else None,
        status=estado,
        score_category=categoria or ScoreCategory.WARM,
        created_at=creado or AHORA,
        updated_at=creado or AHORA,
        last_activity_at=creado or AHORA,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def _repartir(db, **kwargs):
    """Una ficha nueva, repartida. Devuelve `(lead, reparto)`."""
    lead = _ficha(db, **kwargs)
    reparto = repartir(db, lead)
    db.commit()
    db.refresh(lead)
    return lead, reparto


async def _alta(db, **kwargs):
    """Una ficha nueva que pasa por el scoring de verdad, que es por donde pasa el reparto."""
    lead = _ficha(db, **kwargs)
    await ScoringService(db).calculate_and_persist_score(lead, generate_ai_text=False)
    db.refresh(lead)
    return lead


# ==============================================================================
# La regla: menos cartera abierta y, con empate, más tiempo sin recibir
# ==============================================================================

def test_una_tanda_se_reparte_entre_las_tres(db_session, equipo):
    """
    Seis altas y tres asesoras: dos cada una.

    Es la prueba que el `ORDER BY capacity DESC` del capítulo anterior no pasaba. Con él las
    seis eran de la misma persona —la del número más alto— y la ficha de cada prospecto
    tenía dueño, así que cualquier comprobación de «se asignó alguien» seguía en verde.
    """
    for _ in range(6):
        _repartir(db_session, creado=AHORA)

    por_asesor = {
        nombre: db_session.query(Lead).filter(Lead.assigned_rep_id == cuenta.id).count()
        for nombre, cuenta in equipo.items()
    }
    assert por_asesor == {"ana": 2, "beto": 2, "ceci": 2, "baja": 0, "admin": 0}


def test_recibe_quien_tiene_menos_cartera_abierta(db_session, equipo):
    for _ in range(3):
        _ficha(db_session, asesor=equipo["ana"])
    _ficha(db_session, asesor=equipo["beto"])

    lead, reparto = _repartir(db_session)

    assert lead.assigned_rep_id == equipo["ceci"].id
    assert (reparto.regla, reparto.candidatos, reparto.cartera_abierta) == (
        MENOS_CARTERA_ABIERTA, 3, 0,
    )


@pytest.mark.parametrize("cerrada", [LeadStatus.WON, LeadStatus.LOST, LeadStatus.UNQUALIFIED])
def test_la_cartera_que_cuenta_es_la_abierta(db_session, equipo, cerrada):
    """
    Un trato ganado, uno perdido y un prospecto descartado no son trabajo.

    Contar la cartera entera habría premiado a quien menos cierra, que es exactamente lo
    contrario de lo que un reparto equitativo quiere decir. La definición de «queda algo que
    hacer» es la del motor de reglas, no una copia.
    """
    for _ in range(5):
        _ficha(db_session, asesor=equipo["ana"], estado=cerrada)
    _ficha(db_session, asesor=equipo["beto"])
    _ficha(db_session, asesor=equipo["ceci"])

    lead, _ = _repartir(db_session)

    assert lead.assigned_rep_id == equipo["ana"].id


def test_la_definicion_de_cartera_abierta_no_esta_copiada(db_session):
    """
    La condición es **la misma función** que usan las reglas del motor, no una igual.

    Dos copias de esta regla no fallarían: las dos pantallas seguirían funcionando y dirían
    cosas distintas el día que `UNQUALIFIED` entrara o saliera de la lista. Es la forma de
    defecto que el recorrido del 5 de octubre encontró siete veces.
    """
    assert reparto_automatico.en_seguimiento is motor_de_reglas.en_seguimiento


def test_con_empate_recibe_quien_lleva_mas_tiempo_sin_recibir(db_session, equipo):
    """
    Dos asesoras con un prospecto abierto cada una: decide cuál lo recibió antes.

    Sin este segundo criterio el empate lo rompería el identificador, y la cuenta más
    antigua se llevaría el primero de cada tanda para siempre.
    """
    _ficha(db_session, asesor=equipo["ana"], creado=_hace(days=9))
    _ficha(db_session, asesor=equipo["beto"], creado=_hace(days=2))
    _ficha(db_session, asesor=equipo["ceci"], creado=_hace(days=5))

    lead, reparto = _repartir(db_session)

    assert lead.assigned_rep_id == equipo["ana"].id
    assert reparto.regla == MAS_TIEMPO_SIN_RECIBIR


def test_quien_no_ha_recibido_nunca_va_primero(db_session, equipo):
    """Una cuenta recién creada no tiene fecha que comparar, y es la que más derecho tiene."""
    _ficha(db_session, asesor=equipo["ana"], estado=LeadStatus.WON, creado=_hace(days=400))
    _ficha(db_session, asesor=equipo["beto"], estado=LeadStatus.WON, creado=_hace(days=500))

    lead, reparto = _repartir(db_session)

    assert lead.assigned_rep_id == equipo["ceci"].id
    assert reparto.regla == MAS_TIEMPO_SIN_RECIBIR


def test_el_empate_completo_lo_rompe_el_identificador_y_lo_dice(db_session, equipo):
    """
    Tres cuentas sin nada: no hay criterio que aplicar, y el asiento lo declara.

    `orden_estable` no es un criterio; es la ausencia de uno, y tiene su propio nombre para
    que en la bitácora no se confunda con una decisión.
    """
    _, reparto = _repartir(db_session)

    assert reparto.regla == ORDEN_ESTABLE
    assert reparto.asesor_id == min(equipo[n].id for n in ("ana", "beto", "ceci"))


def test_con_una_sola_asesora_el_asiento_no_finge_una_eleccion(db_session, equipo):
    for nombre in ("beto", "ceci"):
        equipo[nombre].is_active = False
    db_session.commit()

    _, reparto = _repartir(db_session)

    assert (reparto.regla, reparto.candidatos) == (UNICO_CANDIDATO, 1)


def test_el_reparto_no_mira_el_score(db_session, equipo):
    """
    Un prospecto frío ocupa el mismo tiempo de agenda que uno caliente.

    Es el defecto que cerró el punto 10: mientras el reparto solo tocaba los `HOT`, una
    ficha `WARM` —la mayoría de las que llegan de una publicación— se quedaba sin dueño, y
    sin dueño el motor de reglas no tiene de quién hablar.
    """
    for categoria in (ScoreCategory.HOT, ScoreCategory.WARM, ScoreCategory.COLD):
        lead, _ = _repartir(db_session, categoria=categoria)
        assert lead.assigned_rep_id is not None, categoria


# ==============================================================================
# Entre quiénes se reparte
# ==============================================================================

def test_una_cuenta_de_baja_no_recibe(db_session, equipo):
    """
    Desactivar conserva los prospectos a su nombre y deja de recibir nuevos.

    La cuenta de baja tiene la cartera abierta más pequeña posible —ninguna—, así que es
    justo la que un reparto por carga elegiría si no mirara `is_active`.
    """
    for nombre in ("ana", "beto", "ceci"):
        _ficha(db_session, asesor=equipo[nombre])

    lead, reparto = _repartir(db_session)

    assert lead.assigned_rep_id != equipo["baja"].id
    assert reparto.candidatos == 3


def test_quien_no_atiende_cartera_no_recibe(db_session, equipo):
    """`is_sales_rep` y no el rol: un administrador tiene permisos sobre todo y no atiende a nadie."""
    for nombre in ("ana", "beto", "ceci"):
        _ficha(db_session, asesor=equipo[nombre])

    lead, _ = _repartir(db_session)

    assert lead.assigned_rep_id != equipo["admin"].id


def test_sin_asesoras_la_ficha_queda_sin_asesor_y_sin_error(db_session, equipo):
    """
    El punto 2 del encargo: sin nadie donde repartir, el líder la ve como antes.

    Inventar un destino metería los prospectos en la cartera de alguien que no puede
    atenderlos, que es peor que dejarlos a la vista de quien decide.
    """
    for nombre in ("ana", "beto", "ceci"):
        equipo[nombre].is_sales_rep = False
    db_session.commit()

    lead, reparto = _repartir(db_session)

    assert reparto is None
    assert lead.assigned_rep_id is None
    assert db_session.query(AuditLog).filter(
        AuditLog.action == ACCION_LEAD_REPARTO_AUTOMATICO
    ).count() == 0


def test_sin_ninguna_cuenta_la_eleccion_es_none(db_session):
    """Sin el equipo ni siquiera hay a quién preguntar: `elegir` no revienta, devuelve `None`."""
    assert elegir(db_session) is None


# ==============================================================================
# Lo que no se toca nunca
# ==============================================================================

def test_un_prospecto_con_asesor_no_se_toca(db_session, equipo):
    for _ in range(4):
        _ficha(db_session, asesor=equipo["ana"])

    lead, reparto = _repartir(db_session, asesor=equipo["ana"])

    assert reparto is None
    assert lead.assigned_rep_id == equipo["ana"].id
    assert por_que_no_se_reparte(db_session, lead) == YA_TIENE_ASESOR


def test_un_prospecto_de_una_publicacion_con_responsable_no_se_toca(db_session, equipo):
    """
    La publicación ya declaró de quién son sus prospectos; el reparto no la contradice.

    La ficha llega **sin** asesor cuando el responsable dejó de ser un asesor activo
    (`ciclo.asesor_para`), así que sin esta regla el reparto se la daría a otra persona
    justo en el caso que el capítulo 26 decidió dejar en manos del líder.
    """
    publicacion = Campaign(
        name="Post con responsable", channel="LinkedIn Ads", budget=0.0,
        responsable_id=equipo["baja"].id,
    )
    db_session.add(publicacion)
    db_session.commit()

    lead, reparto = _repartir(db_session, campana=publicacion)

    assert reparto is None
    assert lead.assigned_rep_id is None
    assert por_que_no_se_reparte(db_session, lead) == PUBLICACION_CON_RESPONSABLE


def test_una_publicacion_sin_responsable_si_entra(db_session, equipo, campaigns):
    """El control de la prueba anterior: sin responsable, la ficha de una publicación se reparte."""
    lead, reparto = _repartir(db_session, campana=campaigns[0])

    assert reparto is not None
    assert lead.assigned_rep_id is not None


# ==============================================================================
# El interruptor y lo que decidió una persona
# ==============================================================================

def test_el_interruptor_apagado_deja_la_ficha_sin_asesor(db_session, equipo, monkeypatch):
    monkeypatch.setattr(settings, "REPARTO_AUTOMATICO_ACTIVO", False)

    lead, reparto = _repartir(db_session)

    assert reparto is None
    assert lead.assigned_rep_id is None


@pytest.mark.asyncio
async def test_reasignar_a_mano_no_se_deshace(db_session, equipo):
    """
    El punto 4 del encargo. El reparto corre en el alta y no vuelve a mirar la ficha.

    La prueba de que es un alta es que todavía no tiene ninguna instantánea en
    `score_histories`, y eso lo escribe el propio scoring: cualquier recálculo posterior la
    encuentra. Sin ese corte, editar la ficha de un prospecto recién reasignado lo devolvería
    a quien el reparto eligiera esta vez, sin que nada en la pantalla lo explicara.
    """
    lead = await _alta(db_session)
    assert lead.assigned_rep_id is not None

    lead.assigned_rep_id = equipo["ceci"].id
    db_session.commit()

    await ScoringService(db_session).calculate_and_persist_score(lead, generate_ai_text=False)

    assert lead.assigned_rep_id == equipo["ceci"].id


@pytest.mark.asyncio
async def test_dejar_una_ficha_sin_asesor_a_mano_tampoco_se_deshace(db_session, equipo):
    """Quitarle el asesor es también una decisión; el siguiente recálculo no la revoca."""
    lead = await _alta(db_session)

    lead.assigned_rep_id = None
    db_session.commit()

    await ScoringService(db_session).calculate_and_persist_score(lead, generate_ai_text=False)

    assert lead.assigned_rep_id is None
    assert por_que_no_se_reparte(db_session, lead) == NO_ES_UN_ALTA


@pytest.mark.asyncio
async def test_el_alta_de_verdad_pasa_por_el_reparto(db_session, equipo):
    """
    El cableado: el reparto corre dentro del scoring, que es el paso obligatorio de las
    cuatro formas de dar de alta una ficha.
    """
    lead = await _alta(db_session)

    assert lead.assigned_rep_id is not None
    assert db_session.query(ScoreHistory).filter(ScoreHistory.lead_id == lead.id).count() == 1


# ==============================================================================
# La bitácora
# ==============================================================================

def _asiento(db):
    return (
        db.query(AuditLog)
        .filter(AuditLog.action == ACCION_LEAD_REPARTO_AUTOMATICO)
        .order_by(AuditLog.id.desc())
        .first()
    )


def test_el_asiento_dice_la_regla_y_entre_cuantos_se_eligio(db_session, equipo):
    """
    El punto 3 del encargo. «Se le dio a Ana» no se puede discutir; «se le dio a Ana entre
    tres porque tenía la cartera abierta más pequeña» se comprueba al día siguiente.
    """
    _ficha(db_session, asesor=equipo["beto"])
    _ficha(db_session, asesor=equipo["ceci"])
    lead, reparto = _repartir(db_session)

    asiento = _asiento(db_session)
    assert asiento.entity_id == str(lead.id)
    assert asiento.event_metadata == {
        "asesor_id": equipo["ana"].id,
        "regla": MENOS_CARTERA_ABIERTA,
        "candidatos": 3,
        "cartera_abierta_del_elegido": 0,
    }
    assert reparto.asesor_id == equipo["ana"].id


def test_el_asiento_no_lleva_actor_ni_nada_de_la_persona(db_session, equipo):
    """
    Sin actor, como la purga y como el motor: el alta la pudo pedir alguien, pero a quién le
    tocaba no lo decidió. Y sin datos de contacto: la bitácora cuenta cuántos, nunca quiénes.
    """
    lead, _ = _repartir(db_session)

    asiento = _asiento(db_session)
    assert (asiento.actor_id, asiento.actor_email, asiento.actor_role) == (None, None, None)
    escrito = f"{asiento.event_metadata}{asiento.entity_id}"
    assert lead.email not in escrito
    assert lead.first_name not in escrito


def test_el_asiento_vive_en_la_transaccion_del_alta(db_session, equipo):
    """
    Si la ficha no se queda, su reparto tampoco.

    La ingesta del CRM confirma la ficha, su actividad, su score y su auditoría juntas o no
    confirma nada. Un `commit` desde la bitácora dejaría escrito el reparto de un prospecto
    que el `rollback` siguiente se llevó, y entonces la bitácora afirmaría algo que no pasó.
    """
    lead = _ficha(db_session)
    repartir(db_session, lead)
    db_session.rollback()

    assert db_session.get(Lead, lead.id).assigned_rep_id is None
    assert _asiento(db_session) is None


# ==============================================================================
# Dos altas a la vez
# ==============================================================================

def test_la_consulta_de_candidatos_pide_el_bloqueo(db_session):
    """
    La decisión lee un recuento que la otra transacción está a punto de cambiar.

    Sin bloqueo, dos altas simultáneas leen «Ana tiene 0» y las dos se la dan a Ana: el mismo
    hueco repartido dos veces. SQLite —el motor de esta suite— ignora `FOR UPDATE` en
    silencio, así que aquí no se puede ejercitar; lo que sí se puede comprobar, y es lo que
    importa, es que la sentencia lo pide de verdad contra el motor que corre en la pila. Se
    compila la consulta que usa el reparto, no una copia parecida.
    """
    sentencia = str(
        reparto_automatico.consulta_de_candidatos(db_session).statement.compile(
            dialect=postgresql.dialect()
        )
    )

    assert "FOR UPDATE" in sentencia
    # En orden de identificador: dos pasadas que tomen las mismas filas en el mismo orden no
    # se pueden bloquear una a la otra.
    assert "ORDER BY users.id ASC" in sentencia


def test_dos_altas_en_la_misma_transaccion_no_van_a_la_misma_cuenta(db_session, equipo):
    """
    El caso que sí se puede ejercitar: dos altas seguidas sin confirmar entre ellas.

    Es lo que hace una entrega del CRM con dos eventos. El recuento tiene que ver la primera
    asignación aunque todavía no esté confirmada; si leyera solo lo confirmado, las dos
    fichas irían a la misma persona.
    """
    primera = _ficha(db_session)
    segunda = _ficha(db_session)

    uno = repartir(db_session, primera)
    db_session.flush()
    dos = repartir(db_session, segunda)

    assert uno.asesor_id != dos.asesor_id


# ==============================================================================
# El trabajo que produce: el mismo que una asignación a mano
# ==============================================================================

@pytest.mark.asyncio
async def test_la_tarea_de_primer_contacto_es_identica_a_la_de_una_asignacion_a_mano(
    db_session, equipo
):
    """
    El punto 3 del encargo, y la razón de que no haya un gancho nuevo.

    El motor de reglas no pregunta «¿se acaba de asignar algo?», pregunta «¿hay algún
    prospecto asignado al que nadie haya contactado?». Da igual por dónde se asignara, así
    que lo que había que escribir no era código sino esta comparación: una ficha repartida y
    otra asignada a mano producen la misma tarea, campo por campo.
    """
    for nombre in ("beto", "ceci"):
        equipo[nombre].is_active = False
    db_session.commit()

    repartida = await _alta(db_session)
    a_mano = _ficha(db_session, asesor=equipo["ana"])
    assert repartida.assigned_rep_id == equipo["ana"].id

    ejecutar(db_session, ahora=AHORA, reglas=[PRIMER_CONTACTO])

    tareas = {
        tarea.lead_id: tarea
        for tarea in db_session.query(Tarea).filter(Tarea.regla == PRIMER_CONTACTO).all()
    }
    assert set(tareas) == {repartida.id, a_mano.id}
    comparables = [
        (t.asesor_id, t.regla, t.clave, t.estado, t.vence_el, t.motivo)
        for t in (tareas[repartida.id], tareas[a_mano.id])
    ]
    assert comparables[0] == comparables[1]


@pytest.mark.asyncio
async def test_el_aviso_del_hot_desatendido_llega_igual(db_session, equipo):
    """
    Un `HOT` repartido y desatendido avisa a su asesora, que es lo que antes no podía pasar
    con una ficha que nadie había asignado.
    """
    for nombre in ("beto", "ceci"):
        equipo[nombre].is_active = False
    db_session.commit()

    lead = await _alta(db_session, creado=_hace(hours=settings.REGLA_HOT_SIN_CONTACTO_HORAS + 2))
    lead.score_category = ScoreCategory.HOT
    lead.current_score = 91.0
    db_session.commit()

    ejecutar(db_session, ahora=AHORA, reglas=[HOT_SIN_CONTACTO])

    aviso = db_session.query(Aviso).filter(Aviso.regla == HOT_SIN_CONTACTO).one()
    assert (aviso.usuario_id, aviso.lead_id) == (equipo["ana"].id, lead.id)


def test_el_reparto_no_crea_tareas_ni_avisos(db_session, equipo):
    """
    Repartir no es avisar. La tarea aparece en la pasada siguiente, como todas las demás: el
    precio de barrer el estado en vez de engancharse al suceso, y está escrito en la prueba
    con personas para que no se lea como un fallo.
    """
    _repartir(db_session)

    assert db_session.query(Tarea).count() == 0
    assert db_session.query(Aviso).count() == 0
    assert db_session.query(Tarea).filter(Tarea.estado == ABIERTA).count() == 0


# ==============================================================================
# La guarda del CI existe, pasa y el CI la ejecuta
# ==============================================================================

def test_el_ci_ejecuta_la_guarda_del_reparto_antes_de_la_suite():
    """
    Un paso del CI se borra sin que nada falle: el flujo sigue en verde y deja de comprobar
    lo que comprobaba. Esta prueba es lo que falla entonces.

    Va después de descargar el artefacto —el reparto no lo necesita, pero la guarda levanta
    la aplicación entera y puntúa fichas de verdad— y antes de la suite, para que el motivo
    de un fallo se lea en el título del paso. Es el mismo criterio que la guarda de la página
    pública.
    """
    flujo = yaml.safe_load((RAIZ / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    pasos = flujo["jobs"]["pruebas"]["steps"]
    orden = {
        "modelo": next(
            i for i, p in enumerate(pasos)
            if (p.get("with") or {}).get("name") == "modelo-entrenado"
        ),
        "guarda": next(i for i, p in enumerate(pasos) if GUARDA in str(p.get("run", ""))),
        "suite": next(i for i, p in enumerate(pasos) if "pytest backend/tests" in str(p.get("run", ""))),
    }

    assert orden["modelo"] < orden["guarda"] < orden["suite"]


def test_la_guarda_del_reparto_pasa_con_el_codigo_de_hoy():
    """Una guarda que falla con el código sano no guarda nada: se acaba desactivando."""
    entorno = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    resultado = subprocess.run(  # noqa: S603  intérprete propio y script del repositorio, sin entrada externa
        [sys.executable, GUARDA], cwd=RAIZ, capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=entorno, timeout=300,
    )

    assert resultado.returncode == 0, resultado.stdout[-2000:] + resultado.stderr[-2000:]
    assert "conserva sus defensas" in resultado.stdout
