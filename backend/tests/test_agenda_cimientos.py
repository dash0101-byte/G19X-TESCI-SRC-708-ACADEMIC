"""
Los cimientos de «el sistema dice qué hacer hoy» (capítulo 28), antes de que haya motor.

Tres cosas que tienen que estar bien **antes** de crear la primera tarea:

* el vocabulario de `app/core/agenda.py` es coherente consigo mismo: el orden de ejecución
  no puede olvidarse de una regla ni inventarse una que no existe;
* los plazos se pueden configurar pero no por debajo de su mínimo, y el aviso al líder no
  puede llegar antes que el del asesor —un error que ningún validador de un solo campo ve—;
* lo que se guarda caduca como todo lo demás, y caduca **cerrado**: una tarea pendiente no
  desaparece por vieja, porque eso sería limpiarla en vez de hacerla.
"""
import datetime

import pytest
from app.core.agenda import (
    ABIERTA,
    CUMPLIDA,
    DESCARTADA,
    ESTADOS_CERRADOS,
    ESTADOS_DE_TAREA,
    ETIQUETAS_DE_ESTADO,
    HECHA,
    ORDEN_DE_LAS_REGLAS,
    REGLAS,
    etiqueta_de_regla,
)
from app.core.config import PLAZOS_MINIMOS_DE_LAS_REGLAS, Settings
from app.models.entities import Aviso, Lead, Tarea, User
from app.services.caducidad_service import PLAZOS, aplicar_caducidad
from pydantic import ValidationError

UTC = datetime.timezone.utc


def _ahora():
    return datetime.datetime.now(UTC)


def _hace(dias: int):
    return _ahora() - datetime.timedelta(days=dias)


@pytest.fixture
def prospecto_y_asesor(db_session):
    asesor = db_session.query(User).first()
    lead = Lead(first_name="Rita", last_name="Vela", email="rita.vela@ejemplo.com", company="Vela SA")
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)
    return lead, asesor


# ==============================================================================
# El vocabulario
# ==============================================================================

def test_el_orden_de_ejecucion_cubre_exactamente_las_reglas():
    """
    Una regla que existe y no está en el orden no corre nunca, y no falla nada.

    Es el fallo silencioso típico de este módulo: alguien añade la sexta regla, la prueba de
    esa regla la llama a mano y pasa, y en producción el motor no la ejecuta jamás porque
    recorre una lista que no la incluye.
    """
    assert set(ORDEN_DE_LAS_REGLAS) == set(REGLAS)
    assert len(ORDEN_DE_LAS_REGLAS) == len(set(ORDEN_DE_LAS_REGLAS)), "una regla repetida correría dos veces"


def test_el_aviso_al_lider_corre_despues_del_aviso_al_asesor():
    """Escalar exige orden: el líder solo se entera de lo que el asesor ya no resolvió."""
    orden = list(ORDEN_DE_LAS_REGLAS)
    assert orden.index("hot_sin_contacto") < orden.index("hot_sin_contacto_lider")


def test_cada_regla_se_describe_a_si_misma():
    for clave, regla in REGLAS.items():
        assert regla.clave == clave
        assert regla.etiqueta and regla.descripcion
        assert regla.crea in ("tarea", "aviso", "ambos")
        assert regla.para in ("asesor", "lider")
    # Una clave desconocida se enseña tal cual en vez de reventar: el panel nunca se queda
    # en blanco por una regla que este código no conoce.
    assert etiqueta_de_regla("inventada") == "inventada"
    assert etiqueta_de_regla(None) == ""


def test_los_estados_cerrados_son_los_que_no_estan_abiertos():
    # `descartada` entro en el capitulo 30: la tarea no se hizo y no se resolvio sola, el
    # prospecto se cerro y dejo de tener sentido. Es un tercer estado y no un alias de
    # `hecha`, porque juntarlos inflaria la primera metrica de cumplimiento que alguien
    # calcule con los tratos que se cerraron solos.
    assert set(ESTADOS_DE_TAREA) == {ABIERTA, HECHA, CUMPLIDA, DESCARTADA}
    assert set(ESTADOS_CERRADOS) == set(ESTADOS_DE_TAREA) - {ABIERTA}
    # Todos los cerrados tienen etiqueta: un estado sin ella se pintaria como un hueco.
    assert set(ETIQUETAS_DE_ESTADO) == set(ESTADOS_DE_TAREA)


# ==============================================================================
# Los plazos: configurables, con suelo
# ==============================================================================

@pytest.mark.parametrize("ajuste", sorted(PLAZOS_MINIMOS_DE_LAS_REGLAS))
def test_un_plazo_de_regla_por_debajo_del_minimo_no_arranca(ajuste):
    minimo = PLAZOS_MINIMOS_DE_LAS_REGLAS[ajuste]
    with pytest.raises(ValidationError):
        Settings(**{ajuste: minimo - 1})

    # Justo en el mínimo sí arranca. El plazo del líder no se puede probar solo: en su
    # mínimo (8 h) quedaría por debajo del plazo del asesor por defecto (24 h) y lo
    # rechazaría el OTRO validador, el del escalado. Se baja el del asesor a su propio
    # mínimo (4 h) para que la pareja sea coherente y lo que se esté midiendo aquí sea el
    # suelo del campo y no el orden entre los dos.
    companera = {"REGLA_HOT_SIN_CONTACTO_HORAS": 4} if ajuste == "REGLA_HOT_LIDER_HORAS" else {}
    assert getattr(Settings(**companera, **{ajuste: minimo}), ajuste) == minimo


def test_el_plazo_del_lider_tiene_que_superar_al_del_asesor():
    """
    Por separado los dos valores son legales; juntos, no.

    Con 24 y 24 las dos reglas disparan en la misma pasada y el líder recibe el aviso a la
    vez que quien todavía podía resolverlo. Nada falla, nada se rompe: simplemente el
    escalado deja de ser un escalado, y nadie se entera hasta que el líder se queja.
    """
    with pytest.raises(ValidationError):
        Settings(REGLA_HOT_SIN_CONTACTO_HORAS=24, REGLA_HOT_LIDER_HORAS=24)
    with pytest.raises(ValidationError):
        Settings(REGLA_HOT_SIN_CONTACTO_HORAS=24, REGLA_HOT_LIDER_HORAS=12)

    ajustado = Settings(REGLA_HOT_SIN_CONTACTO_HORAS=8, REGLA_HOT_LIDER_HORAS=9)
    assert ajustado.REGLA_HOT_LIDER_HORAS == 9


def test_los_dos_plazos_nuevos_estan_en_la_lista_de_conservacion():
    por_tabla = {plazo.tabla: plazo for plazo in PLAZOS}
    assert por_tabla["tareas"].ajuste == "CONSERVACION_TAREAS_DIAS"
    assert por_tabla["avisos"].ajuste == "CONSERVACION_AVISOS_DIAS"


# ==============================================================================
# Lo cerrado caduca; lo pendiente, no
# ==============================================================================

def test_una_tarea_abierta_no_caduca_por_vieja(db_session, prospecto_y_asesor):
    """
    Borrar trabajo pendiente es limpiarlo, no hacerlo.

    Si el plazo mirara `creada_en`, la bandeja se vaciaría sola cada seis meses y el sistema
    diría que no hay nada que hacer hoy porque olvidó lo que había que hacer.
    """
    lead, asesor = prospecto_y_asesor
    db_session.add_all([
        Tarea(
            lead_id=lead.id, asesor_id=asesor.id, regla="primer_contacto", clave="vieja-abierta",
            estado=ABIERTA, vence_el=_hace(900), motivo="Nadie la hizo nunca.", creada_en=_hace(900),
        ),
        Tarea(
            lead_id=lead.id, asesor_id=asesor.id, regla="primer_contacto", clave="vieja-hecha",
            estado=HECHA, vence_el=_hace(900), motivo="Se hizo hace mucho.", creada_en=_hace(900),
            cerrada_en=_hace(900),
        ),
    ])
    db_session.commit()

    aplicar_caducidad(db_session, plazos=[p for p in PLAZOS if p.tabla == "tareas"])

    quedan = {t.clave for t in db_session.query(Tarea).all()}
    assert quedan == {"vieja-abierta"}


def test_una_tarea_cerrada_hace_poco_tampoco_caduca(db_session, prospecto_y_asesor):
    lead, asesor = prospecto_y_asesor
    db_session.add(
        Tarea(
            lead_id=lead.id, asesor_id=asesor.id, regla="volver_a_llamar", clave="reciente",
            estado=CUMPLIDA, vence_el=_hace(3), motivo="La contestaron.", creada_en=_hace(5),
            cerrada_en=_hace(2),
        )
    )
    db_session.commit()

    aplicar_caducidad(db_session, plazos=[p for p in PLAZOS if p.tabla == "tareas"])

    assert db_session.query(Tarea).count() == 1


def test_un_aviso_sin_leer_no_caduca(db_session, prospecto_y_asesor):
    """Uno sin leer no ha cumplido: nadie se ha enterado todavía de lo que decía."""
    lead, asesor = prospecto_y_asesor
    db_session.add_all([
        Aviso(
            usuario_id=asesor.id, lead_id=lead.id, regla="hot_sin_contacto", clave="sin-leer",
            texto="Lleva mucho sin contacto.", creado_en=_hace(900),
        ),
        Aviso(
            usuario_id=asesor.id, lead_id=lead.id, regla="hot_sin_contacto", clave="leido",
            texto="Lleva mucho sin contacto.", creado_en=_hace(900), leido_en=_hace(900),
        ),
    ])
    db_session.commit()

    aplicar_caducidad(db_session, plazos=[p for p in PLAZOS if p.tabla == "avisos"])

    quedan = {a.clave for a in db_session.query(Aviso).all()}
    assert quedan == {"sin-leer"}


def test_ni_las_tareas_ni_los_avisos_guardan_el_correo_de_nadie(db_session, prospecto_y_asesor):
    """
    El motivo y el texto se escriben sin datos de contacto a propósito.

    Viajan a la bitácora, a la exportación del titular y a cada respaldo. El nombre y la
    empresa salen del prospecto al pintar la pantalla, donde ya estaban.
    """
    lead, asesor = prospecto_y_asesor
    tarea = Tarea(
        lead_id=lead.id, asesor_id=asesor.id, regla="primer_contacto", clave="1",
        vence_el=_ahora(), motivo="Prospecto recién asignado, sin contacto todavía.",
    )
    aviso = Aviso(
        usuario_id=asesor.id, lead_id=lead.id, regla="hot_sin_contacto", clave="h24",
        texto="Un prospecto HOT lleva 24 h sin contacto.",
    )
    db_session.add_all([tarea, aviso])
    db_session.commit()

    for texto in (tarea.motivo, aviso.texto):
        assert lead.email not in texto
        assert lead.first_name not in texto
        assert lead.company not in texto
