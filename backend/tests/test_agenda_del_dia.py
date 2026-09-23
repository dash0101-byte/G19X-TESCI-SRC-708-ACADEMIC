"""
La agenda del día por HTTP: la bandeja, la campana, el cierre y la vista del líder.

Lo que más vigila este fichero es el **alcance**, porque es lo que falla en silencio: una
consulta sin filtrar no da error, da de más. Por eso cada prueba de alcance se escribe con
dos personas y trabajo de las dos en la misma base a la vez; con una sola, pasaría igual con
el filtro roto.
"""
import datetime

import pytest
from app.core.agenda import ABIERTA, CUMPLIDA, HECHA, HOT_SIN_CONTACTO, PRIMER_CONTACTO, VOLVER_A_LLAMAR
from app.models.entities import AuditLog, Aviso, Lead, ScoreCategory, Tarea, User
from tests.conftest import TEST_ACCOUNTS

AGENDA = "/api/v1/agenda"
UTC = datetime.timezone.utc


def _ahora():
    return datetime.datetime.now(UTC)


def _cuenta(db, rol):
    return db.query(User).filter(User.email == TEST_ACCOUNTS[rol][0]).first()


@pytest.fixture
def reparto(db_session):
    """
    Dos asesores con cartera y trabajo, en la misma base.

    Devuelve `(asesor, propio, otra, ajeno)`: la cuenta que inicia sesión en las pruebas, su
    prospecto, otra asesora y el suyo.
    """
    asesor = _cuenta(db_session, "Commercial_Executive")
    asesor.is_sales_rep = True
    asesor.capacity = 50
    otra = User(
        email="otra.agenda@plurione.com", full_name="Otra Agenda", role="Commercial_Executive",
        hashed_password="!sin-contrasena:fixture", is_sales_rep=True, capacity=50,
    )
    db_session.add(otra)
    db_session.commit()
    db_session.refresh(otra)

    propio = Lead(
        first_name="Mía", last_name="Propia", email="mia@ejemplo.com", company="Propia SA",
        assigned_rep_id=asesor.id, current_score=70.0, score_category=ScoreCategory.WARM,
    )
    ajeno = Lead(
        first_name="Suya", last_name="Ajena", email="suya@ejemplo.com", company="Ajena SA",
        assigned_rep_id=otra.id, current_score=90.0, score_category=ScoreCategory.HOT,
    )
    db_session.add_all([propio, ajeno])
    db_session.commit()
    db_session.refresh(propio)
    db_session.refresh(ajeno)
    return asesor, propio, otra, ajeno


def _tarea(db, lead, asesor, *, regla=PRIMER_CONTACTO, clave="1", vence=None, estado=ABIERTA):
    fila = Tarea(
        lead_id=lead.id, asesor_id=asesor.id, regla=regla, clave=clave, estado=estado,
        vence_el=vence or (_ahora() + datetime.timedelta(hours=2)),
        motivo="Asignado y todavía sin contactar.", creada_en=_ahora(),
    )
    db.add(fila)
    db.commit()
    db.refresh(fila)
    return fila


def _aviso(db, lead, usuario, *, regla=HOT_SIN_CONTACTO, clave="1", leido=None):
    fila = Aviso(
        usuario_id=usuario.id, lead_id=lead.id, regla=regla, clave=clave,
        texto="Prospecto HOT sin contactar.", creado_en=_ahora(), leido_en=leido,
    )
    db.add(fila)
    db.commit()
    db.refresh(fila)
    return fila


# ==============================================================================
# La bandeja
# ==============================================================================

def test_la_bandeja_trae_lo_vencido_y_lo_de_hoy(client, executive_headers, db_session, reparto):
    """
    «Hoy» es lo vencido más las próximas 24 horas, y no lo que queda del día natural.

    Con el corte por día natural, una tarea creada de madrugada con 24 h de plazo —que es
    exactamente lo que hace el motor— no aparecía el día de hacerla, solo al día siguiente y
    ya vencida. Y el resultado dependía de la hora a la que alguien abriera el panel.
    """
    asesor, propio, _, _ = reparto
    _tarea(db_session, propio, asesor, clave="vencida", vence=_ahora() - datetime.timedelta(hours=5))
    _tarea(
        db_session, propio, asesor, regla=VOLVER_A_LLAMAR, clave="hoy",
        vence=_ahora() + datetime.timedelta(hours=23),
    )

    cuerpo = client.get(f"{AGENDA}/hoy", headers=executive_headers).json()

    assert cuerpo["asesor_id"] == asesor.id
    assert len(cuerpo["tareas"]) == 2
    assert cuerpo["vencidas"] == 1
    assert cuerpo["para_hoy"] == 1
    assert cuerpo["mas_adelante"] == 0


def test_lo_de_pasado_manana_se_cuenta_y_no_se_ensena(client, executive_headers, db_session, reparto):
    """
    Saber que hay trabajo después tranquiliza; verlo hoy convierte la bandeja en otra lista
    larga que nadie termina.
    """
    asesor, propio, _, _ = reparto
    _tarea(db_session, propio, asesor, clave="lejos", vence=_ahora() + datetime.timedelta(days=4))
    # Justo al otro lado del horizonte: 25 horas ya es trabajo de mañana.
    _tarea(db_session, propio, asesor, regla=VOLVER_A_LLAMAR, clave="borde",
           vence=_ahora() + datetime.timedelta(hours=25))

    cuerpo = client.get(f"{AGENDA}/hoy", headers=executive_headers).json()

    assert cuerpo["tareas"] == []
    assert cuerpo["mas_adelante"] == 2


def test_la_bandeja_va_ordenada_por_score(client, executive_headers, db_session, reparto):
    """
    Por score y no por fecha.

    Una bandeja por fecha pone arriba lo más viejo, que suele ser también lo más frío, y
    deja al prospecto que más vale para después de comer.
    """
    asesor, propio, _, _ = reparto
    frio = Lead(
        first_name="Frío", last_name="Bajo", email="frio@ejemplo.com", company="Fría SA",
        assigned_rep_id=asesor.id, current_score=10.0, score_category=ScoreCategory.COLD,
    )
    db_session.add(frio)
    db_session.commit()
    # El frío vence antes: por fecha saldría primero.
    _tarea(db_session, frio, asesor, clave="frio", vence=_ahora() - datetime.timedelta(hours=9))
    _tarea(db_session, propio, asesor, clave="calido", vence=_ahora() - datetime.timedelta(hours=1))

    tareas = client.get(f"{AGENDA}/hoy", headers=executive_headers).json()["tareas"]

    assert [t["prospecto"]["score"] for t in tareas] == [70.0, 10.0]


def test_cada_tarea_dice_por_que_existe_y_a_quien_abre(client, executive_headers, db_session, reparto):
    asesor, propio, _, _ = reparto
    _tarea(db_session, propio, asesor)

    tarea = client.get(f"{AGENDA}/hoy", headers=executive_headers).json()["tareas"][0]

    assert tarea["regla"] == PRIMER_CONTACTO
    assert tarea["regla_etiqueta"] == "Primer contacto"
    assert tarea["motivo"]
    assert tarea["prospecto"]["id"] == propio.id
    assert tarea["prospecto"]["nombre"] == "Mía Propia"
    assert tarea["vencida"] is False


def test_la_bandeja_no_lleva_el_correo_ni_el_telefono(client, executive_headers, db_session, reparto):
    """
    Es una lista de trabajo, no un directorio.

    Quien necesita llamar abre la ficha, y ese acceso queda registrado como acceso a la
    ficha. Repetir aquí los datos de contacto los sacaría de ese registro.
    """
    asesor, propio, _, _ = reparto
    propio.phone = "+52 55 9999 0000"
    db_session.commit()
    _tarea(db_session, propio, asesor)

    texto = client.get(f"{AGENDA}/hoy", headers=executive_headers).text

    assert propio.email not in texto
    assert "9999 0000" not in texto


# ==============================================================================
# El alcance
# ==============================================================================

def test_el_asesor_no_ve_las_tareas_de_otra_persona(client, executive_headers, db_session, reparto):
    asesor, propio, otra, ajeno = reparto
    _tarea(db_session, propio, asesor, clave="mia")
    _tarea(db_session, ajeno, otra, clave="suya")

    cuerpo = client.get(f"{AGENDA}/hoy", headers=executive_headers).json()

    assert [t["prospecto"]["id"] for t in cuerpo["tareas"]] == [propio.id]


def test_pedir_la_bandeja_de_otro_responde_404(client, executive_headers, db_session, reparto):
    """
    404 y no 403: con un 403 para lo ajeno, recorrer identificadores diría cuántas personas
    hay y cuáles tienen trabajo, sin ver una sola línea.
    """
    _, _, otra, _ = reparto

    respuesta = client.get(f"{AGENDA}/hoy?asesor_id={otra.id}", headers=executive_headers)

    assert respuesta.status_code == 404


def test_el_lider_si_puede_mirar_la_bandeja_de_su_cartera(client, lead_headers, db_session, reparto):
    asesor, propio, _, _ = reparto
    _tarea(db_session, propio, asesor)

    cuerpo = client.get(f"{AGENDA}/hoy?asesor_id={asesor.id}", headers=lead_headers).json()

    assert cuerpo["asesor_id"] == asesor.id
    assert len(cuerpo["tareas"]) == 1


def test_una_tarea_ajena_no_se_puede_marcar_hecha(client, executive_headers, db_session, reparto):
    _, _, otra, ajeno = reparto
    suya = _tarea(db_session, ajeno, otra, clave="suya")

    respuesta = client.post(f"{AGENDA}/tareas/{suya.id}/hecha", headers=executive_headers)

    assert respuesta.status_code == 404
    db_session.refresh(suya)
    assert suya.estado == ABIERTA


def test_ni_el_lider_firma_el_trabajo_de_otro(client, lead_headers, db_session, reparto):
    """
    Verla y decir «ya la hice» no son el mismo permiso.

    El líder ve el trabajo de su equipo; cerrarlo por ellos convertiría la bandeja en una
    lista que cualquiera puede vaciar, y entonces «hecha» dejaría de significar nada.
    """
    asesor, propio, _, _ = reparto
    ajena = _tarea(db_session, propio, asesor)

    respuesta = client.post(f"{AGENDA}/tareas/{ajena.id}/hecha", headers=lead_headers)

    assert respuesta.status_code == 404
    db_session.refresh(ajena)
    assert ajena.estado == ABIERTA


def test_una_tarea_que_no_existe_responde_igual_que_una_ajena(client, executive_headers, db_session, reparto):
    _, _, otra, ajeno = reparto
    suya = _tarea(db_session, ajeno, otra, clave="suya")

    inexistente = client.post(f"{AGENDA}/tareas/999999/hecha", headers=executive_headers)
    de_otra = client.post(f"{AGENDA}/tareas/{suya.id}/hecha", headers=executive_headers)

    assert inexistente.status_code == de_otra.status_code == 404


# ==============================================================================
# Cerrar a mano
# ==============================================================================

def test_marcar_hecha_la_cierra_con_su_firma(client, executive_headers, db_session, reparto):
    asesor, propio, _, _ = reparto
    tarea = _tarea(db_session, propio, asesor)

    cuerpo = client.post(f"{AGENDA}/tareas/{tarea.id}/hecha", headers=executive_headers).json()

    assert cuerpo["estado"] == HECHA
    db_session.refresh(tarea)
    assert tarea.cerrada_en is not None
    # A diferencia de lo que cierra el sistema, esta lleva firma.
    assert tarea.cerrada_por_id == asesor.id


def test_marcarla_dos_veces_no_es_un_error(client, executive_headers, db_session, reparto):
    """Pulsar dos veces no es un error, y la fecha de cierre no se mueve."""
    asesor, propio, _, _ = reparto
    tarea = _tarea(db_session, propio, asesor)

    primera = client.post(f"{AGENDA}/tareas/{tarea.id}/hecha", headers=executive_headers).json()
    segunda = client.post(f"{AGENDA}/tareas/{tarea.id}/hecha", headers=executive_headers).json()

    assert primera["cerrada_en"] == segunda["cerrada_en"]


def test_no_reabre_lo_que_cerro_el_sistema(client, executive_headers, db_session, reparto):
    asesor, propio, _, _ = reparto
    tarea = _tarea(db_session, propio, asesor, estado=CUMPLIDA)
    tarea.cerrada_en = _ahora()
    db_session.commit()

    cuerpo = client.post(f"{AGENDA}/tareas/{tarea.id}/hecha", headers=executive_headers).json()

    assert cuerpo["estado"] == CUMPLIDA


def test_cerrar_a_mano_queda_en_la_bitacora_con_su_actor(client, executive_headers, db_session, reparto):
    """
    Lo que cierra una persona lleva actor; lo que cierra el sistema, no.

    Cerrar a mano es una afirmación de alguien sobre su propio trabajo y tiene que poder
    atribuirse; que una llamada contestada cierre una tarea no lo hizo nadie.
    """
    asesor, propio, _, _ = reparto
    tarea = _tarea(db_session, propio, asesor)

    client.post(f"{AGENDA}/tareas/{tarea.id}/hecha", headers=executive_headers)

    asiento = db_session.query(AuditLog).filter(AuditLog.action == "tarea.hecha").first()
    assert asiento is not None
    assert asiento.actor_email == TEST_ACCOUNTS["Commercial_Executive"][0]
    assert asiento.entity_id == str(tarea.id)
    assert asiento.event_metadata["regla"] == PRIMER_CONTACTO


def test_una_tarea_cerrada_sale_de_la_bandeja(client, executive_headers, db_session, reparto):
    asesor, propio, _, _ = reparto
    tarea = _tarea(db_session, propio, asesor)

    client.post(f"{AGENDA}/tareas/{tarea.id}/hecha", headers=executive_headers)

    assert client.get(f"{AGENDA}/hoy", headers=executive_headers).json()["tareas"] == []


# ==============================================================================
# La campana
# ==============================================================================

def test_la_campana_cuenta_los_sin_leer(client, executive_headers, db_session, reparto):
    asesor, propio, _, _ = reparto
    _aviso(db_session, propio, asesor, clave="a")
    _aviso(db_session, propio, asesor, clave="b", leido=_ahora())

    cuerpo = client.get(f"{AGENDA}/avisos", headers=executive_headers).json()

    assert cuerpo["sin_leer"] == 1
    assert len(cuerpo["avisos"]) == 2
    # Los sin leer, primero: la campana se abre para ver lo que falta.
    assert cuerpo["avisos"][0]["leido_en"] is None


def test_la_campana_de_una_persona_es_solo_suya(client, executive_headers, db_session, reparto):
    """Un aviso tiene destinatario: leer el de otro no es una vista, es abrir su correo."""
    asesor, propio, otra, ajeno = reparto
    _aviso(db_session, propio, asesor, clave="mio")
    _aviso(db_session, ajeno, otra, clave="suyo")

    cuerpo = client.get(f"{AGENDA}/avisos", headers=executive_headers).json()

    assert cuerpo["sin_leer"] == 1
    assert [a["prospecto"]["id"] for a in cuerpo["avisos"]] == [propio.id]


def test_ni_el_lider_lee_los_avisos_de_otro(client, lead_headers, db_session, reparto):
    asesor, propio, _, _ = reparto
    _aviso(db_session, propio, asesor, clave="del-asesor")

    cuerpo = client.get(f"{AGENDA}/avisos", headers=lead_headers).json()

    assert cuerpo["sin_leer"] == 0
    assert cuerpo["avisos"] == []


def test_marcar_leidos_vacia_la_campana(client, executive_headers, db_session, reparto):
    asesor, propio, _, _ = reparto
    _aviso(db_session, propio, asesor, clave="a")
    _aviso(db_session, propio, asesor, clave="b")

    cuerpo = client.post(f"{AGENDA}/avisos/leidos", headers=executive_headers, json={}).json()

    assert cuerpo["leidos"] == 2
    assert client.get(f"{AGENDA}/avisos", headers=executive_headers).json()["sin_leer"] == 0


def test_marcar_uno_solo_deja_el_resto(client, executive_headers, db_session, reparto):
    asesor, propio, _, _ = reparto
    uno = _aviso(db_session, propio, asesor, clave="a")
    _aviso(db_session, propio, asesor, clave="b")

    cuerpo = client.post(
        f"{AGENDA}/avisos/leidos", headers=executive_headers, json={"ids": [uno.id]}
    ).json()

    assert cuerpo["leidos"] == 1
    assert client.get(f"{AGENDA}/avisos", headers=executive_headers).json()["sin_leer"] == 1


def test_marcar_como_leido_el_aviso_de_otro_no_hace_nada(client, executive_headers, db_session, reparto):
    """Y no lo dice: es la misma respuesta que daría si ese aviso no existiera."""
    _, _, otra, ajeno = reparto
    suyo = _aviso(db_session, ajeno, otra, clave="suyo")

    cuerpo = client.post(
        f"{AGENDA}/avisos/leidos", headers=executive_headers, json={"ids": [suyo.id]}
    ).json()

    assert cuerpo["leidos"] == 0
    db_session.refresh(suyo)
    assert suyo.leido_en is None


# ==============================================================================
# Lo que ve el líder
# ==============================================================================

def test_el_lider_ve_los_hot_que_se_enfrian_y_con_quien_estan(client, lead_headers, db_session, reparto):
    _, _, otra, ajeno = reparto
    ajeno.created_at = _ahora() - datetime.timedelta(hours=30)
    ajeno.last_activity_at = ajeno.created_at
    db_session.commit()

    cuerpo = client.get(f"{AGENDA}/enfriandose", headers=lead_headers).json()

    assert cuerpo["total"] == 1
    fila = cuerpo["filas"][0]
    assert fila["prospecto"]["id"] == ajeno.id
    assert fila["asesor_id"] == otra.id
    assert fila["asesor"] == "Otra Agenda"
    assert fila["horas_sin_contacto"] >= 30


def test_un_hot_recien_llegado_no_se_esta_enfriando(client, lead_headers, db_session, reparto):
    _, _, _, ajeno = reparto
    ajeno.created_at = _ahora() - datetime.timedelta(hours=2)
    ajeno.last_activity_at = ajeno.created_at
    db_session.commit()

    assert client.get(f"{AGENDA}/enfriandose", headers=lead_headers).json()["total"] == 0


def test_el_asesor_no_abre_la_vista_del_lider(client, executive_headers):
    """Un prospecto caliente enfriándose es problema del equipo; la lista es de dirección."""
    assert client.get(f"{AGENDA}/enfriandose", headers=executive_headers).status_code == 403


def test_la_vista_del_lider_dice_si_ya_se_aviso(client, lead_headers, db_session, reparto):
    """
    Para que el líder sepa si está llegando tarde él o si el aviso ya se mandó y no sirvió.
    """
    _, _, otra, ajeno = reparto
    ajeno.created_at = _ahora() - datetime.timedelta(hours=30)
    ajeno.last_activity_at = ajeno.created_at
    db_session.commit()
    _aviso(db_session, ajeno, otra, regla=HOT_SIN_CONTACTO, clave="x")

    fila = client.get(f"{AGENDA}/enfriandose", headers=lead_headers).json()["filas"][0]

    assert fila["avisado_al_asesor"] is True
    assert fila["avisado_al_lider"] is False


# ==============================================================================
# Sin sesión
# ==============================================================================

@pytest.mark.parametrize(
    "metodo,ruta",
    [
        ("get", "/hoy"),
        ("get", "/avisos"),
        ("get", "/enfriandose"),
        ("post", "/avisos/leidos"),
        ("post", "/tareas/1/hecha"),
    ],
)
def test_nada_de_la_agenda_se_abre_sin_sesion(client, metodo, ruta):
    assert getattr(client, metodo)(f"{AGENDA}{ruta}").status_code == 401
