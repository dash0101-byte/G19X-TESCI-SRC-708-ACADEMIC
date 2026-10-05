"""
La tarjeta «Llegó por», el informe de cada publicación y su comparativa.

Lo que se comprueba:

* **La tarjeta**: aparece solo si hubo solicitudes, con su publicación, su enlace, su fecha,
  qué necesitaba y cuándo aceptó el aviso; y si la persona respondió a dos publicaciones,
  con las dos.
* **El informe**: los tres números de arriba, las filas ordenadas por score, los filtros de
  etapa y fecha, y que entra tanto quien está atribuido a la campaña como quien envió su
  perfil por su enlace.
* **El alcance**: el asesor ve los suyos y un número con el resto —ningún nombre ajeno sale
  del servidor—, el líder lo ve todo, y lo que no es una publicación responde 404.
* **La bitácora**: la consulta queda escrita y sin un solo dato de contacto.
* **La comparativa y el contador**: son de dirección, y sus números coinciden con los del
  informe (dos caminos distintos que tienen que dar lo mismo).
"""
import datetime

import pytest
from app.core.audit import ACCION_PUBLICACION_COMPARATIVA, ACCION_PUBLICACION_INFORME
from app.models.entities import AuditLog, Lead, LeadStatus, ScoreCategory, User
from tests.conftest import TEST_ACCOUNTS

CAMPANAS = "/api/v1/campaigns"
PUBLICACIONES = "/api/v1/publicaciones"

SOLICITUD = {
    "nombre": "Ana Prueba",
    "correo": "ana.informe@example.com",
    "telefono": "5598765432",
    "empresa": "Ejemplo SA",
    "cargo": "CTO",
    "sector": "FinTech",
    "tamano_de_empresa": "201-1000",
    "linkedin": "https://www.linkedin.com/in/ana-prueba",
    "necesidad": "vacantes",
    "aviso_de_privacidad": True,
    "sitio_web": "",
}


def _crear_publicacion(client, lead_headers, nombre):
    respuesta = client.post(
        CAMPANAS,
        headers=lead_headers,
        json={
            "name": nombre,
            "channel": "LinkedIn",
            "description": f"Texto de {nombre}",
            "budget": 1000.0,
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


@pytest.fixture
def publicacion(client, lead_headers):
    return _crear_publicacion(client, lead_headers, "Post · Talento TI septiembre")


@pytest.fixture
def segunda_publicacion(client, lead_headers):
    return _crear_publicacion(client, lead_headers, "Post · Equipos completos octubre")


def _enviar(client, publicacion, **cambios):
    cuerpo = {**SOLICITUD, **cambios}
    respuesta = client.post(f"/api/v1/interes/{publicacion['public_slug']}", json=cuerpo)
    assert respuesta.status_code == 202, respuesta.text
    return respuesta


def _ficha(db_session, correo=SOLICITUD["correo"]) -> Lead:
    db_session.expire_all()
    return db_session.query(Lead).filter(Lead.email == correo).one()


def _usuario(db_session, rol) -> User:
    return db_session.query(User).filter(User.email == TEST_ACCOUNTS[rol][0]).one()


def _sembrar(db_session, publicacion, *, email, score, etapa, asesor_id=None, nombre="Fulano"):
    """Una ficha atribuida a la publicación sin pasar por la página: la vía del CRM."""
    ahora = datetime.datetime.now(datetime.timezone.utc)
    lead = Lead(
        first_name=nombre,
        last_name="Atribuido",
        email=email,
        company="Empresa Sembrada",
        job_title="CIO",
        industry="Banking",
        company_size="1000+",
        source="LinkedIn",
        country="México",
        current_score=score,
        score_category=ScoreCategory.HOT if score >= 70 else ScoreCategory.COLD,
        status=etapa,
        campaign_id=publicacion["id"],
        assigned_rep_id=asesor_id,
        last_score_update=ahora,
        last_activity_at=ahora,
        created_at=ahora,
        updated_at=ahora,
        raw_metadata={},
    )
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)
    return lead


# ==============================================================================
# La tarjeta «Llegó por» de la ficha 360
# ==============================================================================

def test_sin_solicitudes_la_ficha_no_trae_tarjeta(client, lead_headers, sample_lead):
    """Una ficha que no llegó por una publicación no enseña una tarjeta vacía: no la enseña."""
    ficha = client.get(f"/api/v1/leads/{sample_lead.id}", headers=lead_headers).json()

    assert ficha["llego_por"] is None


def test_la_tarjeta_trae_la_publicacion_con_su_enlace(client, lead_headers, publicacion, db_session):
    _enviar(client, publicacion)
    lead = _ficha(db_session)

    tarjeta = client.get(f"/api/v1/leads/{lead.id}", headers=lead_headers).json()["llego_por"]

    assert len(tarjeta["solicitudes"]) == 1
    solicitud = tarjeta["solicitudes"][0]
    assert solicitud["publicacion_id"] == publicacion["id"]
    assert solicitud["titulo"] == publicacion["name"]
    assert solicitud["enlace"] == publicacion["enlace_publico"]
    assert solicitud["recibida_en"] is not None


def test_la_tarjeta_dice_que_necesita_y_cuando_acepto_el_aviso(
    client, lead_headers, publicacion, db_session
):
    _enviar(client, publicacion, necesidad="demo")
    lead = _ficha(db_session)

    tarjeta = client.get(f"/api/v1/leads/{lead.id}", headers=lead_headers).json()["llego_por"]

    solicitud = tarjeta["solicitudes"][0]
    assert solicitud["necesidad"] == "Ver una demostración"
    assert solicitud["aviso_aceptado_en"] is not None


def test_la_tarjeta_trae_el_perfil_de_linkedin(client, lead_headers, publicacion, db_session):
    """Va en la tarjeta, no en cada fila: es de la persona, y la ficha guarda el primero."""
    _enviar(client, publicacion)
    lead = _ficha(db_session)

    tarjeta = client.get(f"/api/v1/leads/{lead.id}", headers=lead_headers).json()["llego_por"]

    assert tarjeta["perfil_de_linkedin"] == SOLICITUD["linkedin"]


def test_quien_respondio_a_dos_publicaciones_las_ve_las_dos(
    client, lead_headers, publicacion, segunda_publicacion, db_session
):
    """
    El segundo envío no crea ficha ni pisa datos, pero **sí** es una solicitud más. Si la
    tarjeta se armara con `campaign_id` —que se fija al crear y no se vuelve a tocar— la
    segunda publicación no aparecería nunca.
    """
    _enviar(client, publicacion)
    _enviar(client, segunda_publicacion, necesidad="equipo")
    lead = _ficha(db_session)

    tarjeta = client.get(f"/api/v1/leads/{lead.id}", headers=lead_headers).json()["llego_por"]

    titulos = [s["titulo"] for s in tarjeta["solicitudes"]]
    assert len(tarjeta["solicitudes"]) == 2
    assert set(titulos) == {publicacion["name"], segunda_publicacion["name"]}
    # De la más reciente a la más antigua: lo último que hizo la persona es lo primero
    # que necesita ver quien va a llamarla.
    fechas = [s["recibida_en"] for s in tarjeta["solicitudes"]]
    assert fechas == sorted(fechas, reverse=True)


# ==============================================================================
# El informe de una publicación
# ==============================================================================

def test_el_resumen_cuenta_perfiles_avances_y_score_medio(
    client, lead_headers, publicacion, db_session
):
    _sembrar(db_session, publicacion, email="uno@ej.mx", score=80.0, etapa=LeadStatus.QUALIFIED)
    _sembrar(db_session, publicacion, email="dos@ej.mx", score=40.0, etapa=LeadStatus.NEW)

    resumen = client.get(
        f"{PUBLICACIONES}/{publicacion['id']}/informe", headers=lead_headers
    ).json()["resumen"]

    assert resumen["perfiles_recibidos"] == 2
    assert resumen["avanzaron_de_etapa"] == 1
    assert resumen["score_medio"] == 60.0


def test_las_filas_van_del_score_mas_alto_al_mas_bajo(
    client, lead_headers, publicacion, db_session
):
    _sembrar(db_session, publicacion, email="baja@ej.mx", score=21.0, etapa=LeadStatus.NEW)
    _sembrar(db_session, publicacion, email="alta@ej.mx", score=91.0, etapa=LeadStatus.NEW)
    _sembrar(db_session, publicacion, email="media@ej.mx", score=55.0, etapa=LeadStatus.NEW)

    filas = client.get(
        f"{PUBLICACIONES}/{publicacion['id']}/informe", headers=lead_headers
    ).json()["filas"]

    assert [f["score"] for f in filas] == [91.0, 55.0, 21.0]


def test_cada_fila_trae_lo_que_la_tabla_ensena(client, lead_headers, publicacion, db_session):
    asesor = _usuario(db_session, "Commercial_Executive")
    _sembrar(
        db_session, publicacion, email="fila@ej.mx", score=70.0,
        etapa=LeadStatus.CONTACTED, asesor_id=asesor.id, nombre="Carmen",
    )

    fila = client.get(
        f"{PUBLICACIONES}/{publicacion['id']}/informe", headers=lead_headers
    ).json()["filas"][0]

    assert fila["nombre"] == "Carmen Atribuido"
    assert fila["empresa"] == "Empresa Sembrada"
    assert fila["cargo"] == "CIO"
    assert fila["etapa"] == "CONTACTED"
    assert fila["asesor"] == asesor.full_name
    assert fila["recibida_en"] is not None
    # El identificador es lo que convierte la fila en un enlace a la ficha 360.
    assert fila["lead_id"] > 0
    # Atribuida por el CRM, sin solicitud: no hay necesidad que enseñar, y no se inventa.
    assert fila["necesidad"] is None


def test_la_fila_dice_que_necesita_segun_su_ultima_solicitud(
    client, lead_headers, publicacion, segunda_publicacion
):
    """
    Lo que pidió en su última solicitud **a esta** publicación: si volvió a escribir porque
    ahora quiere una demo, eso es lo que el asesor tiene que leer. La de otra publicación no
    cuenta aquí.
    """
    _enviar(client, publicacion, necesidad="explorando")
    _enviar(client, publicacion, necesidad="demo")
    _enviar(client, segunda_publicacion, necesidad="equipo")

    def necesidad_en(pub):
        return client.get(
            f"{PUBLICACIONES}/{pub['id']}/informe", headers=lead_headers
        ).json()["filas"][0]["necesidad"]

    assert necesidad_en(publicacion) == "Ver una demostración"
    assert necesidad_en(segunda_publicacion) == "Formar un equipo completo"


def test_entra_quien_envio_su_perfil_aunque_su_ficha_sea_de_otra_publicacion(
    client, lead_headers, publicacion, segunda_publicacion, db_session
):
    """
    La ficha se atribuye a la publicación por la que se creó y ahí se queda. Contar solo
    por `campaign_id` dejaría a la segunda publicación sin nadie por quien responder.
    """
    _enviar(client, publicacion)
    _enviar(client, segunda_publicacion)

    segunda = client.get(
        f"{PUBLICACIONES}/{segunda_publicacion['id']}/informe", headers=lead_headers
    ).json()

    assert segunda["resumen"]["perfiles_recibidos"] == 1
    assert segunda["filas"][0]["nombre"] == "Ana Prueba"


def test_el_filtro_de_etapa_deja_solo_esa_etapa(client, lead_headers, publicacion, db_session):
    _sembrar(db_session, publicacion, email="nueva@ej.mx", score=30.0, etapa=LeadStatus.NEW)
    _sembrar(db_session, publicacion, email="ganada@ej.mx", score=95.0, etapa=LeadStatus.WON)

    informe = client.get(
        f"{PUBLICACIONES}/{publicacion['id']}/informe",
        headers=lead_headers,
        params={"etapa": "WON"},
    ).json()

    assert informe["total"] == 1
    assert informe["filas"][0]["etapa"] == "WON"


def test_el_filtro_de_fecha_incluye_el_dia_entero(client, lead_headers, publicacion, db_session):
    """
    `hasta` es un día, no un instante. Con el corte en su medianoche, un perfil recibido
    esa misma tarde quedaría fuera del informe que lo pide expresamente.
    """
    _enviar(client, publicacion)
    hoy = datetime.datetime.now(datetime.timezone.utc).date()

    de_hoy = client.get(
        f"{PUBLICACIONES}/{publicacion['id']}/informe",
        headers=lead_headers,
        params={"desde": hoy.isoformat(), "hasta": hoy.isoformat()},
    ).json()
    de_ayer = client.get(
        f"{PUBLICACIONES}/{publicacion['id']}/informe",
        headers=lead_headers,
        params={"hasta": (hoy - datetime.timedelta(days=1)).isoformat()},
    ).json()

    assert de_hoy["total"] == 1
    assert de_ayer["total"] == 0


def test_el_informe_pagina_sin_perder_el_total(client, lead_headers, publicacion, db_session):
    for i in range(3):
        _sembrar(db_session, publicacion, email=f"p{i}@ej.mx", score=10.0 * i, etapa=LeadStatus.NEW)

    pagina = client.get(
        f"{PUBLICACIONES}/{publicacion['id']}/informe",
        headers=lead_headers,
        params={"limit": 1, "offset": 1},
    ).json()

    assert pagina["total"] == 3
    assert len(pagina["filas"]) == 1
    assert pagina["filas"][0]["score"] == 10.0


# ==============================================================================
# El alcance
# ==============================================================================

def test_el_asesor_ve_los_suyos_y_solo_el_total_del_resto(
    client, executive_headers, lead_headers, publicacion, db_session
):
    asesor = _usuario(db_session, "Commercial_Executive")
    _sembrar(
        db_session, publicacion, email="mio@ej.mx", score=50.0,
        etapa=LeadStatus.NEW, asesor_id=asesor.id, nombre="Propio",
    )
    _sembrar(db_session, publicacion, email="ajeno@ej.mx", score=99.0,
             etapa=LeadStatus.WON, nombre="Ajeno")

    informe = client.get(
        f"{PUBLICACIONES}/{publicacion['id']}/informe", headers=executive_headers
    ).json()

    assert [f["nombre"] for f in informe["filas"]] == ["Propio Atribuido"]
    assert informe["resumen"]["perfiles_recibidos"] == 1
    assert informe["resumen"]["de_otros_asesores"] == 1
    assert informe["resumen"]["alcance_completo"] is False
    # Ni el nombre, ni la empresa, ni el score del prospecto ajeno salen del servidor.
    #
    # Se comprueba recorriendo la estructura y NO buscando «99» en el volcado a texto, que
    # es como estaba escrito. Esa forma fallaba sola: la respuesta lleva cadenas aleatorias
    # —el slug de veintidós caracteres— y marcas de tiempo con microsegundos, y «99» cae
    # dentro de alguna de ellas cada pocos cientos de ejecuciones sin que nada esté mal. El
    # capítulo 32 quitó una de esas fuentes sacando la cabecera `publicacion`; quedaban las
    # otras, y volvió a aparecer en una pasada completa del capítulo 34.
    #
    # Lo que se quiere decir es «ningún número de esta respuesta es el score ajeno y ningún
    # texto es su nombre», así que se dice eso. Además de no fallar sola, es más fuerte: un
    # 99.0 escondido en un campo numérico anidado lo caza, y la búsqueda en texto plano
    # también lo habría cazado pero mezclado con el ruido.
    def _valores(nodo):
        if isinstance(nodo, dict):
            for clave, valor in nodo.items():
                # La cabecera `publicacion` no lleva datos de ningún prospecto.
                if clave != "publicacion":
                    yield from _valores(valor)
        elif isinstance(nodo, list):
            for elemento in nodo:
                yield from _valores(elemento)
        else:
            yield nodo

    for valor in _valores(informe):
        assert not (isinstance(valor, str) and "Ajeno" in valor), valor
        assert not (isinstance(valor, (int, float)) and not isinstance(valor, bool) and valor == 99.0), (
            f"el score del prospecto ajeno salió en la respuesta: {valor}"
        )


def test_el_lider_ve_la_publicacion_entera(client, lead_headers, publicacion, db_session):
    asesor = _usuario(db_session, "Commercial_Executive")
    _sembrar(db_session, publicacion, email="mio@ej.mx", score=50.0,
             etapa=LeadStatus.NEW, asesor_id=asesor.id)
    _sembrar(db_session, publicacion, email="ajeno@ej.mx", score=99.0, etapa=LeadStatus.WON)

    informe = client.get(
        f"{PUBLICACIONES}/{publicacion['id']}/informe", headers=lead_headers
    ).json()

    assert informe["resumen"]["perfiles_recibidos"] == 2
    assert informe["resumen"]["de_otros_asesores"] == 0
    assert informe["resumen"]["alcance_completo"] is True


def test_una_campana_que_no_es_publicacion_no_existe(client, lead_headers, campaigns):
    """Una campaña de otro canal no tiene informe de publicación, y no se dice por qué."""
    for campana in campaigns:
        respuesta = client.get(f"{PUBLICACIONES}/{campana.id}/informe", headers=lead_headers)
        assert respuesta.status_code == 404


def test_una_publicacion_inexistente_responde_404(client, lead_headers):
    assert client.get(f"{PUBLICACIONES}/999999/informe", headers=lead_headers).status_code == 404


def test_una_publicacion_desactivada_conserva_su_informe(
    client, lead_headers, publicacion, db_session
):
    """
    Desactivar es dejar de recibir perfiles, no borrar los que llegaron. El informe de una
    campaña terminada es justo el que se mira.
    """
    _sembrar(db_session, publicacion, email="antes@ej.mx", score=60.0, etapa=LeadStatus.WON)
    client.delete(f"{CAMPANAS}/{publicacion['id']}", headers=lead_headers)

    informe = client.get(
        f"{PUBLICACIONES}/{publicacion['id']}/informe", headers=lead_headers
    ).json()

    assert informe["publicacion"]["activa"] is False
    assert informe["resumen"]["perfiles_recibidos"] == 1


# ==============================================================================
# La bitácora
# ==============================================================================

def test_la_consulta_queda_escrita_sin_datos_de_contacto(
    client, lead_headers, publicacion, db_session
):
    _sembrar(db_session, publicacion, email="registrada@ej.mx", score=60.0,
             etapa=LeadStatus.NEW, nombre="Mencionable")

    client.get(
        f"{PUBLICACIONES}/{publicacion['id']}/informe",
        headers=lead_headers,
        params={"etapa": "NEW"},
    )

    asiento = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == ACCION_PUBLICACION_INFORME)
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert asiento is not None
    assert asiento.entity_id == str(publicacion["id"])
    assert asiento.event_metadata["devueltos"] == 1
    assert asiento.event_metadata["filtros"]["etapa"] == "NEW"
    plano = str(asiento.event_metadata)
    assert "registrada@ej.mx" not in plano
    assert "Mencionable" not in plano


def test_la_comparativa_tambien_queda_escrita(client, lead_headers, publicacion, db_session):
    client.get(f"{PUBLICACIONES}/comparativa", headers=lead_headers)

    asiento = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == ACCION_PUBLICACION_COMPARATIVA)
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert asiento is not None
    assert asiento.event_metadata["publicaciones"] >= 1


# ==============================================================================
# La comparativa y el contador
# ==============================================================================

def test_la_comparativa_pone_las_publicaciones_una_al_lado_de_otra(
    client, lead_headers, publicacion, segunda_publicacion, db_session
):
    _sembrar(db_session, publicacion, email="a@ej.mx", score=80.0, etapa=LeadStatus.WON)
    _sembrar(db_session, publicacion, email="b@ej.mx", score=40.0, etapa=LeadStatus.NEW)
    _sembrar(db_session, segunda_publicacion, email="c@ej.mx", score=30.0, etapa=LeadStatus.NEW)

    items = client.get(f"{PUBLICACIONES}/comparativa", headers=lead_headers).json()["items"]

    por_id = {i["publicacion_id"]: i for i in items}
    primera = por_id[publicacion["id"]]
    assert primera["perfiles_recibidos"] == 2
    assert primera["avanzaron_de_etapa"] == 1
    assert primera["score_medio"] == 60.0
    assert por_id[segunda_publicacion["id"]]["perfiles_recibidos"] == 1


def test_la_comparativa_y_el_informe_dan_lo_mismo(
    client, lead_headers, publicacion, db_session
):
    """
    Dos caminos distintos —uno en SQL con filtros, otro agrupando en memoria— sobre la
    misma pregunta. Si divergen, uno de los dos números está mal y nadie lo notaría.
    """
    _enviar(client, publicacion)
    _sembrar(db_session, publicacion, email="mixto@ej.mx", score=88.0, etapa=LeadStatus.WON)

    informe = client.get(
        f"{PUBLICACIONES}/{publicacion['id']}/informe", headers=lead_headers
    ).json()["resumen"]
    fila = next(
        i for i in client.get(f"{PUBLICACIONES}/comparativa", headers=lead_headers).json()["items"]
        if i["publicacion_id"] == publicacion["id"]
    )

    assert fila["perfiles_recibidos"] == informe["perfiles_recibidos"]
    assert fila["avanzaron_de_etapa"] == informe["avanzaron_de_etapa"]
    assert fila["score_medio"] == informe["score_medio"]


def test_sin_perfiles_no_hay_score_medio_en_ninguna_de_las_tres_tablas(
    client, lead_headers, publicacion
):
    """
    La media de un conjunto vacío no es un cero, igual que la tasa sin visitas no es un 0 %.

    Se encontró recorriendo la demostración: una publicación recién creada salía en la
    comparativa con «Tasa de envío —» y «Score medio 0» en la misma fila, y las dos cifras
    cuentan lo mismo —que todavía no ha llegado nadie—. El cero se lee como una media baja:
    quien compara publicaciones no tiene cómo distinguirlo de un post que sí trae perfiles y
    los trae malos.

    Las tres tablas, y no solo la que se vio: la comparativa, la cabecera del informe y el
    reparto por red. Las tres salen del mismo sitio, así que un arreglo en una sola habría
    dejado las otras dos diciendo cero.
    """
    fila = next(
        i for i in client.get(f"{PUBLICACIONES}/comparativa", headers=lead_headers).json()["items"]
        if i["publicacion_id"] == publicacion["id"]
    )
    assert fila["perfiles_recibidos"] == 0
    assert fila["tasa_de_envio"] is None
    assert fila["score_medio"] is None

    informe = client.get(
        f"{PUBLICACIONES}/{publicacion['id']}/informe", headers=lead_headers
    ).json()
    assert informe["resumen"]["perfiles_recibidos"] == 0
    assert informe["resumen"]["score_medio"] is None

    # El reparto por red trae una fila por red activa aunque no haya llegado nadie por
    # ninguna: son exactamente las que no tienen media.
    assert informe["por_red"], "el informe tiene que traer sus redes aunque estén a cero"
    assert all(f["score_medio"] is None for f in informe["por_red"] if f["perfiles"] == 0)


def test_con_perfiles_el_score_medio_sigue_siendo_el_numero(
    client, lead_headers, publicacion, db_session
):
    """
    La otra mitad del arreglo anterior, que es la que lo vuelve una comprobación.

    Devolver `None` siempre también haría pasar la prueba de arriba, y la columna se
    quedaría muda en todas las publicaciones.
    """
    _sembrar(db_session, publicacion, email="uno@media.mx", score=80.0, etapa=LeadStatus.NEW)
    _sembrar(db_session, publicacion, email="dos@media.mx", score=40.0, etapa=LeadStatus.NEW)

    fila = next(
        i for i in client.get(f"{PUBLICACIONES}/comparativa", headers=lead_headers).json()["items"]
        if i["publicacion_id"] == publicacion["id"]
    )
    assert fila["score_medio"] == 60.0

    informe = client.get(
        f"{PUBLICACIONES}/{publicacion['id']}/informe", headers=lead_headers
    ).json()
    assert informe["resumen"]["score_medio"] == 60.0


def test_la_comparativa_es_de_direccion(client, executive_headers, publicacion):
    """Acotada por cartera compararía asesores, no publicaciones."""
    assert client.get(f"{PUBLICACIONES}/comparativa", headers=executive_headers).status_code == 403


def test_el_contador_cuenta_lo_de_linkedin_sin_asesor(
    client, lead_headers, publicacion, db_session, sample_leads
):
    asesor = _usuario(db_session, "Commercial_Executive")
    _sembrar(db_session, publicacion, email="sin.asesor@ej.mx", score=50.0, etapa=LeadStatus.NEW)
    _sembrar(db_session, publicacion, email="con.asesor@ej.mx", score=50.0,
             etapa=LeadStatus.NEW, asesor_id=asesor.id)

    total = client.get(f"{PUBLICACIONES}/nuevos-sin-asesor", headers=lead_headers).json()["total"]

    # Los seis prospectos de muestra no son de LinkedIn ni cuentan aquí.
    assert total == 1


def test_el_contador_es_del_lider(client, executive_headers):
    assert client.get(
        f"{PUBLICACIONES}/nuevos-sin-asesor", headers=executive_headers
    ).status_code == 403
