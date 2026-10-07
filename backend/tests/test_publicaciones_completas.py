"""
Publicaciones completas (capítulo 26): estados, cierre por fecha, opciones de «¿Qué
necesitas?», responsable, dirección del post, duplicado, visitas y vista previa.

Cada bloque prueba lo que promete y, sobre todo, lo que no puede pasar:

* fuera de «activa» la página no se sirve, tampoco una que venció sin que nadie mirara;
* las opciones propias de una publicación son las únicas que acepta su página, y siguen
  sin puntuar;
* el responsable recibe las fichas nuevas, y si deja de ser asesor, llegan sin asesor;
* la dirección del post es de linkedin.com por el nombre de la máquina, no por contenerlo;
* las visitas son un número por día y nada más, y mirar desde el panel no cuenta.
"""
import datetime

import pytest
from app.core.config import settings
from app.core.publicaciones import MAX_NECESIDADES, NECESIDADES_POR_DEFECTO
from app.models.entities import (
    ActivityType,
    AuditLog,
    Campaign,
    Lead,
    User,
    VisitaDePublicacion,
)
from app.services import ciclo_de_publicaciones as ciclo
from sqlalchemy import inspect

CAMPANAS = "/api/v1/campaigns"
PUBLICACIONES = "/api/v1/publicaciones"

SOLICITUD = {
    "nombre": "Ana Prueba",
    "correo": "ana.completa@example.com",
    "empresa": "Ejemplo SA",
    "cargo": "CTO",
    "sector": "FinTech",
    "tamano_de_empresa": "201-1000",
    "necesidad": "vacantes",
    "aviso_de_privacidad": True,
}

OPCIONES = ["Cubrir una vacante urgente", "Montar un equipo nuevo", "Hablar con alguien"]


def _crear(client, headers, **extra):
    cuerpo = {"name": "Post · Completo", "channel": "LinkedIn", "description": "Texto del post", **extra}
    respuesta = client.post(CAMPANAS, headers=headers, json=cuerpo)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _pagina(publicacion) -> str:
    return f"/api/v1/interes/{publicacion['public_slug']}"


def _enviar(client, publicacion, **cambios):
    return client.post(_pagina(publicacion), json={**SOLICITUD, **cambios})


def _ficha(db_session, correo=SOLICITUD["correo"]) -> Lead:
    db_session.expire_all()
    return db_session.query(Lead).filter(Lead.email == correo).one()


def _vencer(db_session, campaign_id, dias=1):
    """Pone la fecha de cierre en el pasado directamente en la base, sin pasar por la API."""
    campana = db_session.query(Campaign).filter(Campaign.id == campaign_id).one()
    campana.end_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=dias)
    db_session.commit()


@pytest.fixture
def publicacion(client, lead_headers):
    return _crear(client, lead_headers)


# ==============================================================================
# Estados
# ==============================================================================

def test_sin_estado_una_publicacion_nace_activa_como_antes(client, lead_headers):
    publicacion = _crear(client, lead_headers)

    assert (publicacion["estado"], publicacion["is_active"]) == ("activa", True)
    assert client.get(_pagina(publicacion)).status_code == 200


@pytest.mark.parametrize("estado", ["borrador", "pausada", "cerrada"])
def test_fuera_de_activa_la_pagina_no_esta_disponible(client, lead_headers, db_session, estado):
    publicacion = _crear(client, lead_headers, estado=estado)

    assert publicacion["is_active"] is False
    for respuesta in (client.get(_pagina(publicacion)), _enviar(client, publicacion)):
        assert respuesta.status_code == 404
        assert respuesta.json()["detail"] == "Esta publicación no está disponible."
    assert db_session.query(Lead).count() == 0


def test_un_estado_desconocido_se_rechaza(client, lead_headers):
    respuesta = client.post(
        CAMPANAS, headers=lead_headers, json={"name": "Post", "channel": "LinkedIn", "estado": "publicada"}
    )
    assert respuesta.status_code == 422


def test_se_recorre_el_ciclo_y_la_bitacora_lo_cuenta(client, lead_headers, publicacion, db_session):
    ruta = f"{CAMPANAS}/{publicacion['id']}"

    assert client.put(ruta, headers=lead_headers, json={"estado": "pausada"}).json()["estado"] == "pausada"
    assert client.get(_pagina(publicacion)).status_code == 404
    assert client.put(ruta, headers=lead_headers, json={"estado": "activa"}).json()["estado"] == "activa"
    assert client.get(_pagina(publicacion)).status_code == 200

    cambio = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "campana.actualizar")
        .order_by(AuditLog.id.asc())
        .first()
    )
    assert cambio.event_metadata["estado_anterior"] == "activa"
    assert cambio.event_metadata["estado_nuevo"] == "pausada"


def test_is_active_suelto_sigue_funcionando_como_antes(client, lead_headers, publicacion):
    """Reactivar con `is_active` es activar; pararlo, pausar. Desactivar (DELETE) es cerrar."""
    ruta = f"{CAMPANAS}/{publicacion['id']}"

    assert client.put(ruta, headers=lead_headers, json={"is_active": False}).json()["estado"] == "pausada"
    assert client.put(ruta, headers=lead_headers, json={"is_active": True}).json()["estado"] == "activa"
    cerrada = client.delete(ruta, headers=lead_headers).json()
    assert (cerrada["estado"], cerrada["is_active"]) == ("cerrada", False)


def test_el_asesor_no_cambia_el_estado(client, executive_headers, publicacion):
    respuesta = client.put(
        f"{CAMPANAS}/{publicacion['id']}", headers=executive_headers, json={"estado": "pausada"}
    )
    assert respuesta.status_code == 403


# ==============================================================================
# Cierre automático por fecha
# ==============================================================================

def test_una_activa_vencida_se_cierra_sola_al_abrir_su_pagina(client, publicacion, db_session):
    """Nadie ha abierto el panel desde que venció: la página no se sirve igualmente."""
    _vencer(db_session, publicacion["id"])

    assert client.get(_pagina(publicacion)).status_code == 404
    db_session.expire_all()
    campana = db_session.query(Campaign).filter(Campaign.id == publicacion["id"]).one()
    assert (campana.estado, campana.is_active) == ("cerrada", False)


def test_una_pausada_vencida_tambien_se_cierra(client, lead_headers, db_session):
    publicacion = _crear(client, lead_headers, estado="pausada")
    _vencer(db_session, publicacion["id"])

    assert client.get(f"{CAMPANAS}/{publicacion['id']}", headers=lead_headers).json()["estado"] == "cerrada"


def test_un_borrador_no_se_cierra_por_fecha(client, lead_headers, db_session):
    """Un borrador nunca se abrió: no hay nada que cerrar."""
    publicacion = _crear(client, lead_headers, estado="borrador")
    _vencer(db_session, publicacion["id"])

    assert client.get(f"{CAMPANAS}/{publicacion['id']}", headers=lead_headers).json()["estado"] == "borrador"


def test_la_lista_ensena_ya_cerradas_las_vencidas(client, lead_headers, publicacion, db_session):
    _vencer(db_session, publicacion["id"])

    lista = client.get(f"{CAMPANAS}?incluir_inactivas=true&canal=LinkedIn", headers=lead_headers).json()
    assert [p["estado"] for p in lista["items"]] == ["cerrada"]


def test_una_fecha_futura_no_cierra_nada(client, lead_headers):
    manana = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).isoformat()
    publicacion = _crear(client, lead_headers, end_date=manana)

    assert client.get(_pagina(publicacion)).status_code == 200


def test_no_se_activa_algo_cuya_fecha_de_cierre_ya_paso(client, lead_headers, db_session):
    ayer = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()
    borrador = _crear(client, lead_headers, estado="borrador", end_date=ayer)

    respuesta = client.put(f"{CAMPANAS}/{borrador['id']}", headers=lead_headers, json={"estado": "activa"})
    assert respuesta.status_code == 422
    assert "fecha de cierre" in respuesta.json()["detail"]
    nueva = client.post(
        CAMPANAS, headers=lead_headers, json={"name": "Otra", "channel": "LinkedIn", "end_date": ayer}
    )
    assert nueva.status_code == 422


def test_cerrar_vencidas_no_toca_nada_si_no_hay(db_session, publicacion):
    assert ciclo.cerrar_vencidas(db_session) == 0


# ==============================================================================
# «¿Qué necesitas?» por publicación
# ==============================================================================

def test_sin_opciones_propias_usa_las_de_siempre(client, publicacion):
    assert publicacion["necesidades_propias"] is False
    assert {o["clave"]: o["etiqueta"] for o in publicacion["necesidades"]} == NECESIDADES_POR_DEFECTO
    assert client.get(_pagina(publicacion)).json()["opciones"]["necesidades"] == NECESIDADES_POR_DEFECTO


def test_la_pagina_ensena_las_opciones_de_su_publicacion_en_su_orden(client, lead_headers):
    publicacion = _crear(client, lead_headers, necesidades=OPCIONES)

    servidas = client.get(_pagina(publicacion)).json()["opciones"]["necesidades"]
    assert list(servidas.values()) == OPCIONES
    assert list(servidas) == ["cubrir_una_vacante_urgente", "montar_un_equipo_nuevo", "hablar_con_alguien"]


def test_solo_se_aceptan_las_opciones_de_esa_publicacion(client, lead_headers, db_session):
    publicacion = _crear(client, lead_headers, necesidades=OPCIONES)

    # «vacantes» es de las de siempre, no de esta publicación.
    respuesta = _enviar(client, publicacion, necesidad="vacantes")
    assert respuesta.status_code == 422
    assert respuesta.json()["detail"][0]["loc"] == ["body", "necesidad"]
    assert db_session.query(Lead).count() == 0
    assert _enviar(client, publicacion, necesidad="hablar_con_alguien").status_code == 202


def test_la_opcion_elegida_llega_a_la_ficha_y_al_informe_con_su_etiqueta(client, lead_headers, db_session):
    publicacion = _crear(client, lead_headers, necesidades=OPCIONES)
    _enviar(client, publicacion, necesidad="montar_un_equipo_nuevo")
    lead = _ficha(db_session)

    ficha = client.get(f"/api/v1/leads/{lead.id}", headers=lead_headers).json()
    assert ficha["llego_por"]["solicitudes"][0]["necesidad"] == "Montar un equipo nuevo"
    informe = client.get(f"{PUBLICACIONES}/{publicacion['id']}/informe", headers=lead_headers).json()
    assert informe["filas"][0]["necesidad"] == "Montar un equipo nuevo"


def test_cambiar_las_opciones_despues_no_cambia_lo_que_eligio_quien_ya_escribio(
    client, lead_headers, db_session
):
    publicacion = _crear(client, lead_headers, necesidades=OPCIONES)
    _enviar(client, publicacion, necesidad="hablar_con_alguien")
    client.put(
        f"{CAMPANAS}/{publicacion['id']}", headers=lead_headers,
        json={"necesidades": ["Otra cosa", "Y otra más"]},
    )
    lead = _ficha(db_session)

    ficha = client.get(f"/api/v1/leads/{lead.id}", headers=lead_headers).json()
    assert ficha["llego_por"]["solicitudes"][0]["necesidad"] == "Hablar con alguien"


def test_volver_a_las_de_siempre(client, lead_headers):
    publicacion = _crear(client, lead_headers, necesidades=OPCIONES)

    editada = client.put(f"{CAMPANAS}/{publicacion['id']}", headers=lead_headers, json={"necesidades": None}).json()
    assert editada["necesidades_propias"] is False
    assert client.get(_pagina(publicacion)).json()["opciones"]["necesidades"] == NECESIDADES_POR_DEFECTO


@pytest.mark.parametrize(
    "opciones",
    [
        ["Solo una"],
        # Seis, escrito a mano: el requisito es «de 2 a 5», y si la constante cambiara la
        # prueba tiene que fallar, no moverse con ella.
        [f"Opción {i}" for i in range(6)],
        ["Repetida", "repetida"],
        ["Bien", "x" * 41],
        ["Bien", "¡¡!!"],
        ["Bien", 3],
        "no es una lista",
    ],
)
def test_opciones_que_no_valen(client, lead_headers, opciones):
    respuesta = client.post(
        CAMPANAS, headers=lead_headers, json={"name": "Post", "channel": "LinkedIn", "necesidades": opciones}
    )
    assert respuesta.status_code == 422


def test_de_dos_a_cinco_opciones_valen(client, lead_headers):
    assert MAX_NECESIDADES == 5
    for n in (2, 5):
        opciones = [f"Opción número {i}" for i in range(n)]
        assert len(_crear(client, lead_headers, necesidades=opciones)["necesidades"]) == n


def test_las_opciones_propias_tampoco_puntuan(client, lead_headers, db_session):
    publicacion = _crear(client, lead_headers, necesidades=OPCIONES)
    resultados = set()
    for i, clave in enumerate(["cubrir_una_vacante_urgente", "montar_un_equipo_nuevo", "hablar_con_alguien"]):
        correo = f"opcion{i}@example.com"
        _enviar(client, publicacion, correo=correo, necesidad=clave)
        lead = _ficha(db_session, correo)
        historial = lead.score_histories[0]
        resultados.add((lead.current_score, historial.ml_probability, tuple(sorted(historial.rule_breakdown.items()))))
        assert [a.activity_type for a in lead.activities] == [ActivityType.FORM_SUBMIT]
    assert len(resultados) == 1


def test_una_frase_como_necesidad_no_llega_ni_a_buscar_la_publicacion(client, publicacion):
    """El esquema exige forma de clave: texto libre por aquí sigue siendo un 422."""
    assert _enviar(client, publicacion, necesidad="Quiero que me llamen mañana").status_code == 422


# ==============================================================================
# Responsable
# ==============================================================================

def test_con_responsable_la_ficha_nueva_llega_asignada(client, lead_headers, db_session, sales_reps):
    responsable = sales_reps[1]
    publicacion = _crear(client, lead_headers, responsable_id=responsable.id)

    assert publicacion["responsable"] == {"id": responsable.id, "full_name": responsable.full_name}
    _enviar(client, publicacion)
    assert _ficha(db_session).assigned_rep_id == responsable.id


def test_sin_responsable_la_publicacion_no_elige_asesor(
    client, publicacion, db_session, sales_reps, monkeypatch
):
    """
    La publicación no elige por nadie: sin responsable, la ficha no sale a nombre de nadie
    por venir de ella. Hasta el capítulo 46 eso era todo y la ficha esperaba al líder; se
    comprueba con el reparto apagado, que es lo que aísla la decisión de la publicación.
    """
    monkeypatch.setattr(settings, "REPARTO_AUTOMATICO_ACTIVO", False)

    _enviar(client, publicacion)

    assert _ficha(db_session).assigned_rep_id is None


def test_sin_responsable_la_reparte_el_reparto_automatico(
    client, publicacion, db_session, sales_reps
):
    """Capítulo 46: lo que la publicación no decide, lo decide el reparto por carga."""
    _enviar(client, publicacion)

    assert _ficha(db_session).assigned_rep_id in {rep.id for rep in sales_reps}


def test_el_responsable_tiene_que_ser_un_asesor_activo(client, lead_headers, db_session, sales_reps):
    lider = db_session.query(User).filter(User.email == "test.lider@plurione.com").one()
    for candidato in (lider.id, 999999):
        respuesta = client.post(
            CAMPANAS, headers=lead_headers,
            json={"name": "Post", "channel": "LinkedIn", "responsable_id": candidato},
        )
        assert respuesta.status_code == 422


def test_si_el_responsable_deja_de_ser_asesor_llega_sin_asesor(client, lead_headers, db_session, sales_reps):
    responsable = sales_reps[0]
    publicacion = _crear(client, lead_headers, responsable_id=responsable.id)
    usuario = db_session.query(User).filter(User.id == responsable.id).one()
    usuario.is_active = False
    db_session.commit()

    _enviar(client, publicacion)
    assert _ficha(db_session).assigned_rep_id is None


def test_una_ficha_que_ya_existia_no_se_reasigna(client, lead_headers, db_session, sales_reps):
    """
    El responsable de una publicación solo alcanza a las fichas que **nacen** de ella.

    Desde el capítulo 46 la primera solicitud deja la ficha ya repartida, así que lo que esta
    prueba comprueba es más fuerte que antes: el segundo envío, desde una publicación que sí
    tiene responsable, no se la lleva de la cartera donde está. Afirmar que sigue sin asesor
    habría dejado de medir eso el día que algo la asignara.
    """
    sin_responsable = _crear(client, lead_headers)
    _enviar(client, sin_responsable)
    dueno = _ficha(db_session).assigned_rep_id
    con_responsable = _crear(client, lead_headers, name="Post · Otro", responsable_id=sales_reps[1].id)

    _enviar(client, con_responsable)
    assert _ficha(db_session).assigned_rep_id == dueno
    assert dueno != sales_reps[1].id


def test_el_asesor_no_elige_responsable(client, executive_headers, publicacion, sales_reps):
    respuesta = client.put(
        f"{CAMPANAS}/{publicacion['id']}", headers=executive_headers,
        json={"responsable_id": sales_reps[0].id},
    )
    assert respuesta.status_code == 403


def test_el_responsable_sale_en_el_informe(client, lead_headers, sales_reps):
    publicacion = _crear(client, lead_headers, responsable_id=sales_reps[0].id)

    informe = client.get(f"{PUBLICACIONES}/{publicacion['id']}/informe", headers=lead_headers).json()
    assert informe["publicacion"]["responsable"] == sales_reps[0].full_name


# ==============================================================================
# Dirección del post
# ==============================================================================

@pytest.mark.parametrize(
    ("escrita", "guardada"),
    [
        ("https://www.linkedin.com/posts/plurione_equipos-ti-activity-7240000000000000000-abcd",
         "https://www.linkedin.com/posts/plurione_equipos-ti-activity-7240000000000000000-abcd"),
        ("www.linkedin.com/feed/update/urn:li:activity:7240000000000000000/?utm_source=share",
         "https://www.linkedin.com/feed/update/urn:li:activity:7240000000000000000/"),
        ("https://mx.linkedin.com/posts/algo", "https://mx.linkedin.com/posts/algo"),
        ("https://LinkedIn.com/posts/algo#comentarios", "https://linkedin.com/posts/algo"),
    ],
)
def test_la_direccion_del_post_se_guarda_limpia(client, lead_headers, escrita, guardada):
    assert _crear(client, lead_headers, url_del_post=escrita)["url_del_post"] == guardada


@pytest.mark.parametrize(
    "escrita",
    [
        "http://www.linkedin.com/posts/algo",
        "https://linkedin.com.ejemplo.net/posts/algo",
        "https://ejemplo.net/posts/?ir=linkedin.com",
        "https://milinkedin.com/posts/algo",
        "https://usuario:clave@www.linkedin.com/posts/algo",
        "https://www.linkedin.com:8443/posts/algo",
        "https://www.linkedin.com/",
        "javascript:alert(1)//linkedin.com/x",
        "https://www.linkedin.com/" + "a" * 300,
    ],
)
def test_una_direccion_que_no_es_de_linkedin_se_rechaza(client, lead_headers, escrita):
    respuesta = client.post(
        CAMPANAS, headers=lead_headers, json={"name": "Post", "channel": "LinkedIn", "url_del_post": escrita}
    )
    assert respuesta.status_code == 422


def test_el_informe_enlaza_el_post(client, lead_headers):
    publicacion = _crear(client, lead_headers, url_del_post="https://www.linkedin.com/posts/algo")

    informe = client.get(f"{PUBLICACIONES}/{publicacion['id']}/informe", headers=lead_headers).json()
    assert informe["publicacion"]["url_del_post"] == "https://www.linkedin.com/posts/algo"


# ==============================================================================
# Duplicar
# ==============================================================================

def test_duplicar_da_un_borrador_con_enlace_propio(client, lead_headers, db_session, sales_reps):
    original = _crear(
        client, lead_headers, necesidades=OPCIONES, responsable_id=sales_reps[0].id,
        target_audience="Directores de TI", url_del_post="https://www.linkedin.com/posts/algo",
    )

    respuesta = client.post(f"{CAMPANAS}/{original['id']}/duplicar", headers=lead_headers)
    assert respuesta.status_code == 201
    copia = respuesta.json()
    assert copia["id"] != original["id"]
    assert copia["public_slug"] != original["public_slug"]
    assert copia["name"] == "Post · Completo (copia)"
    assert copia["estado"] == "borrador"
    assert copia["description"] == original["description"]
    assert copia["target_audience"] == "Directores de TI"
    assert copia["necesidades"] == original["necesidades"]
    assert copia["responsable_id"] == sales_reps[0].id
    # Lo que es del post publicado no se copia.
    assert copia["url_del_post"] is None
    assert copia["end_date"] is None
    assert client.get(_pagina(copia)).status_code == 404
    asiento = db_session.query(AuditLog).filter(AuditLog.action == "campana.duplicar").one()
    assert asiento.event_metadata["duplicada_de"] == original["id"]


def test_duplicar_no_se_lleva_lo_que_trajo_el_original(client, lead_headers, publicacion, db_session):
    _enviar(client, publicacion)
    client.get(_pagina(publicacion))
    copia = client.post(f"{CAMPANAS}/{publicacion['id']}/duplicar", headers=lead_headers).json()

    informe = client.get(f"{PUBLICACIONES}/{copia['id']}/informe", headers=lead_headers).json()
    assert (informe["total"], informe["resumen"]["visitas"], informe["resumen"]["envios"]) == (0, 0, 0)


def test_el_asesor_no_duplica(client, executive_headers, publicacion):
    assert client.post(f"{CAMPANAS}/{publicacion['id']}/duplicar", headers=executive_headers).status_code == 403


def test_duplicar_algo_que_no_existe_es_404(client, lead_headers):
    assert client.post(f"{CAMPANAS}/999999/duplicar", headers=lead_headers).status_code == 404


# ==============================================================================
# Visitas
# ==============================================================================

def test_cada_apertura_de_la_pagina_suma_una_visita_del_dia(client, publicacion, db_session):
    for _ in range(3):
        client.get(_pagina(publicacion))

    filas = db_session.query(VisitaDePublicacion).all()
    assert [(f.campaign_id, f.dia, f.visitas) for f in filas] == [
        (publicacion["id"], datetime.datetime.now(datetime.timezone.utc).date(), 3)
    ]


def test_el_contador_no_guarda_nada_de_quien_visita():
    """Una fila por publicación, día y red con un número. Ni IP, ni navegador, ni hora."""
    columnas = {c.name for c in VisitaDePublicacion.__table__.columns}
    assert columnas == {"campaign_id", "dia", "red", "visitas"}


def test_la_respuesta_de_la_pagina_no_pone_cookies(client, publicacion):
    respuesta = client.get(_pagina(publicacion))
    assert "set-cookie" not in {k.lower() for k in respuesta.headers}


def test_una_pagina_no_disponible_no_cuenta_visitas(client, lead_headers, db_session):
    borrador = _crear(client, lead_headers, estado="borrador")
    client.get(_pagina(borrador))
    client.get("/api/v1/interes/estoMeLoInvento00000x")

    assert db_session.query(VisitaDePublicacion).count() == 0


def test_las_visitas_de_dias_distintos_van_por_separado(db_session, publicacion):
    campana = db_session.query(Campaign).filter(Campaign.id == publicacion["id"]).one()
    ayer = datetime.date.today() - datetime.timedelta(days=1)
    ciclo.registrar_visita(db_session, campana, dia=ayer)
    ciclo.registrar_visita(db_session, campana, dia=ayer)
    ciclo.registrar_visita(db_session, campana)

    assert sorted(f.visitas for f in db_session.query(VisitaDePublicacion).all()) == [1, 2]


def test_el_informe_da_visitas_envios_y_tasa(client, lead_headers, publicacion):
    for _ in range(4):
        client.get(_pagina(publicacion))
    _enviar(client, publicacion)

    resumen = client.get(f"{PUBLICACIONES}/{publicacion['id']}/informe", headers=lead_headers).json()["resumen"]
    assert (resumen["visitas"], resumen["envios"], resumen["tasa_de_envio"]) == (4, 1, 25.0)


def test_los_envios_de_antes_de_contar_visitas_no_entran_en_la_tasa(client, lead_headers, publicacion, db_session):
    """
    Una publicación anterior al capítulo 26 tiene envíos sin ninguna visita contada detrás:
    dividirlos entre las visitas de después daba tasas del 200 %.
    """
    from app.models.entities import LeadActivity

    _enviar(client, publicacion, correo="antes@example.com")
    antigua = db_session.query(LeadActivity).one()
    antigua.occurred_at = antigua.occurred_at - datetime.timedelta(days=3)
    db_session.commit()
    client.get(_pagina(publicacion))
    client.get(_pagina(publicacion))
    _enviar(client, publicacion, correo="despues@example.com")

    resumen = client.get(f"{PUBLICACIONES}/{publicacion['id']}/informe", headers=lead_headers).json()["resumen"]
    assert (resumen["visitas"], resumen["envios"], resumen["tasa_de_envio"]) == (2, 1, 50.0)
    assert resumen["perfiles_recibidos"] == 2
    fila = client.get(f"{PUBLICACIONES}/comparativa", headers=lead_headers).json()["items"][0]
    assert (fila["visitas"], fila["envios"], fila["tasa_de_envio"]) == (2, 1, 50.0)


def test_sin_visitas_no_hay_tasa(client, lead_headers, publicacion):
    """Dividir entre cero no es un 0 %: no hay dato."""
    resumen = client.get(f"{PUBLICACIONES}/{publicacion['id']}/informe", headers=lead_headers).json()["resumen"]
    assert resumen["tasa_de_envio"] is None


def test_la_comparativa_tambien_trae_visitas_y_tasa(client, lead_headers, publicacion):
    client.get(_pagina(publicacion))
    client.get(_pagina(publicacion))
    _enviar(client, publicacion)

    fila = client.get(f"{PUBLICACIONES}/comparativa", headers=lead_headers).json()["items"][0]
    assert (fila["estado"], fila["visitas"], fila["envios"], fila["tasa_de_envio"]) == ("activa", 2, 1, 50.0)


# ==============================================================================
# Perfiles por día
# ==============================================================================

def test_el_grafico_trae_un_dia_por_barra_con_ceros(client, lead_headers, publicacion, db_session):
    _enviar(client, publicacion)
    campana = db_session.query(Campaign).filter(Campaign.id == publicacion["id"]).one()
    hoy = datetime.datetime.now(datetime.timezone.utc).date()
    ciclo.registrar_visita(db_session, campana, dia=hoy - datetime.timedelta(days=3))

    por_dia = client.get(f"{PUBLICACIONES}/{publicacion['id']}/informe", headers=lead_headers).json()["por_dia"]
    assert [d["dia"] for d in por_dia] == [(hoy - datetime.timedelta(days=n)).isoformat() for n in (3, 2, 1, 0)]
    assert [d["perfiles"] for d in por_dia] == [0, 0, 0, 1]
    assert [d["visitas"] for d in por_dia] == [1, 0, 0, 0]


def test_el_grafico_se_recorta_a_los_ultimos_90_dias(client, lead_headers, publicacion, db_session):
    campana = db_session.query(Campaign).filter(Campaign.id == publicacion["id"]).one()
    hoy = datetime.datetime.now(datetime.timezone.utc).date()
    ciclo.registrar_visita(db_session, campana, dia=hoy - datetime.timedelta(days=200))
    ciclo.registrar_visita(db_session, campana, dia=hoy)

    informe = client.get(f"{PUBLICACIONES}/{publicacion['id']}/informe", headers=lead_headers).json()
    assert informe["grafico_recortado"] is True
    assert len(informe["por_dia"]) == 90
    assert informe["por_dia"][-1]["dia"] == hoy.isoformat()


def test_el_asesor_ve_en_el_grafico_solo_sus_perfiles(
    client, lead_headers, executive_headers, publicacion, db_session
):
    """Las barras son perfiles con nombre detrás: se acotan como las filas."""
    _enviar(client, publicacion)

    por_dia = client.get(f"{PUBLICACIONES}/{publicacion['id']}/informe", headers=executive_headers).json()["por_dia"]
    assert sum(d["perfiles"] for d in por_dia) == 0
    por_dia_lider = client.get(f"{PUBLICACIONES}/{publicacion['id']}/informe", headers=lead_headers).json()["por_dia"]
    assert sum(d["perfiles"] for d in por_dia_lider) == 1


# ==============================================================================
# Vista previa
# ==============================================================================

def test_la_vista_previa_ensena_la_pagina_de_un_borrador(client, lead_headers, executive_headers):
    borrador = _crear(client, lead_headers, estado="borrador", necesidades=OPCIONES)

    for cabeceras in (lead_headers, executive_headers):
        previa = client.get(f"{PUBLICACIONES}/{borrador['id']}/vista-previa", headers=cabeceras)
        assert previa.status_code == 200
        assert previa.json()["titulo"] == "Post · Completo"
        assert list(previa.json()["opciones"]["necesidades"].values()) == OPCIONES


def test_la_vista_previa_es_lo_mismo_que_sirve_la_pagina(client, lead_headers, publicacion):
    previa = client.get(f"{PUBLICACIONES}/{publicacion['id']}/vista-previa", headers=lead_headers).json()
    assert previa == client.get(_pagina(publicacion)).json()


def test_la_vista_previa_no_cuenta_visitas(client, lead_headers, publicacion, db_session):
    client.get(f"{PUBLICACIONES}/{publicacion['id']}/vista-previa", headers=lead_headers)

    assert db_session.query(VisitaDePublicacion).count() == 0


def test_la_vista_previa_pide_sesion_y_solo_de_publicaciones(client, lead_headers, campaigns, publicacion):
    assert client.get(f"{PUBLICACIONES}/{publicacion['id']}/vista-previa").status_code == 401
    otra = next(c for c in campaigns if c.channel != "LinkedIn")
    assert client.get(f"{PUBLICACIONES}/{otra.id}/vista-previa", headers=lead_headers).status_code == 404


# ==============================================================================
# El texto para LinkedIn
# ==============================================================================

def test_la_respuesta_dice_cuanto_ocupa_el_texto_y_el_tope(publicacion):
    assert publicacion["longitud_del_texto"] == len(publicacion["texto_para_linkedin"])
    assert publicacion["max_texto_de_linkedin"] == 3000


def test_la_tabla_de_visitas_existe_con_su_clave(db_session):
    clave = inspect(db_session.get_bind()).get_pk_constraint("visitas_de_publicacion")
    assert clave["constrained_columns"] == ["campaign_id", "dia", "red"]
