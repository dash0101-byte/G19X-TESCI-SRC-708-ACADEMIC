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
import logging
import uuid

import pytest
from app.core.audit import ACCION_PUBLICACION_COMPARATIVA, ACCION_PUBLICACION_INFORME
from app.core.autorizacion import AlcanceDeCartera
from app.core.publicaciones import NECESIDADES_POR_DEFECTO, base_publica
from app.core.security import CurrentUser, UserRole
from app.models.entities import (
    ActivityType,
    AuditLog,
    Campaign,
    Lead,
    LeadActivity,
    LeadStatus,
    ScoreCategory,
    User,
)
from app.services import ciclo_de_publicaciones, informe_de_publicaciones
from app.services.pagina_de_interes import FUENTE as FUENTE_DE_LA_PAGINA
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


# ==============================================================================
# Las rutas de los datos antiguos, que son las que se recorren contra la base de verdad
# ==============================================================================

def _solicitud_antigua(db_session, lead, publicacion, **datos):
    """
    Una solicitud escrita como las escribía una versión anterior del sistema.

    No es un caso inventado: la base de la demostración y la del servidor llevan filas de
    antes del capítulo 26 —cuando la actividad empezó a guardar la etiqueta de la necesidad
    junto a su clave— y de antes del 30 —cuando empezó a guardar el slug en sus datos—. Lo
    que esas filas tienen es lo que esta función escribe, y ninguna prueba las miraba.
    """
    actividad = LeadActivity(
        lead_id=lead.id,
        activity_type=ActivityType.FORM_SUBMIT,
        channel="Web",
        source=FUENTE_DE_LA_PAGINA,
        external_event_id=f"{publicacion['public_slug']}:{uuid.uuid4().hex}",
        verificada=True,
        activity_data=datos,
        occurred_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30),
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(actividad)
    db_session.commit()
    db_session.refresh(actividad)
    return actividad


def test_la_necesidad_de_una_solicitud_antigua_se_lee_de_la_tabla(
    client, lead_headers, publicacion, db_session, sample_lead
):
    """
    Las solicitudes viejas solo guardan la clave; la etiqueta se busca en la tabla.

    Sin esa salida, la ficha 360 de una persona que llegó hace meses enseñaría la tarjeta
    «Llegó por» sin la línea de qué necesitaba: el dato está, y lo que falla es leerlo.
    """
    _solicitud_antigua(db_session, sample_lead, publicacion, necesidad="vacantes")

    tarjeta = informe_de_publicaciones.llego_por(db_session, sample_lead)

    assert tarjeta is not None
    assert tarjeta.solicitudes[0].necesidad == NECESIDADES_POR_DEFECTO["vacantes"]


def test_una_necesidad_que_ya_no_esta_en_la_tabla_no_inventa_etiqueta(
    client, lead_headers, publicacion, db_session, sample_lead
):
    """Una clave de una lista que se cambió después no se traduce: se deja en blanco."""
    _solicitud_antigua(db_session, sample_lead, publicacion, necesidad="algo-que-ya-no-existe")

    tarjeta = informe_de_publicaciones.llego_por(db_session, sample_lead)

    assert tarjeta.solicitudes[0].necesidad is None


def test_la_publicacion_de_una_solicitud_antigua_sale_del_identificador_externo(
    client, lead_headers, publicacion, db_session, sample_lead
):
    """
    El criterio de atribución tiene dos lecturas y la segunda no se probaba.

    El identificador externo lleva el slug delante desde el primer día
    (`<slug>:<uuid>`), y es lo único que tienen las solicitudes anteriores al capítulo 30.
    De este criterio cuelga también el panel de desenlaces, que atribuye cada cierre a la
    publicación por la que llegó esa persona: dos formas de leerlo darían dos atribuciones
    distintas para las fichas antiguas.
    """
    antigua = _solicitud_antigua(db_session, sample_lead, publicacion, necesidad="equipo")

    assert "publicacion" not in (antigua.activity_data or {})
    assert informe_de_publicaciones.slug_de(antigua) == publicacion["public_slug"]


def test_una_solicitud_sin_rastro_de_publicacion_no_se_atribuye_a_ninguna(db_session, sample_lead):
    """
    Ni en los datos ni en el identificador: entonces no se adivina.

    Devolver cualquier slug aquí atribuiría una ficha a una publicación que no la trajo, y
    eso llega al informe de esa publicación y a la comparativa, que son números de negocio.
    """
    suelta = LeadActivity(
        lead_id=sample_lead.id,
        activity_type=ActivityType.FORM_SUBMIT,
        channel="Web",
        source=FUENTE_DE_LA_PAGINA,
        external_event_id="sin-dos-puntos",
        verificada=True,
        activity_data={},
        occurred_at=datetime.datetime.now(datetime.timezone.utc),
    )

    assert informe_de_publicaciones.slug_de(suelta) is None

    # Y la tarjeta de la ficha con esa solicitud y ninguna otra: sale la solicitud, sin
    # publicacion. Es el camino en que no hay ningun slug que buscar, asi que la consulta
    # de publicaciones no se hace; devolver la tarjeta vacia esconderia una solicitud que
    # existe, y rellenar la publicacion inventaria la atribucion.
    db_session.add(suelta)
    db_session.commit()

    tarjeta = informe_de_publicaciones.llego_por(db_session, sample_lead)

    assert len(tarjeta.solicitudes) == 1
    assert tarjeta.solicitudes[0].publicacion_id is None
    assert tarjeta.solicitudes[0].titulo is None
    assert tarjeta.solicitudes[0].enlace is None


def test_sin_marca_del_aviso_vale_la_fecha_del_envio(
    client, lead_headers, publicacion, db_session, sample_lead, caplog
):
    """
    La fecha del aviso de privacidad es un dato legal: cuándo lo aceptó esa persona.

    Las solicitudes que no la guardan aparte tienen la del envío, que es el mismo instante.
    Dejarla en blanco borraría la prueba de un consentimiento que sí se dio.
    """
    caplog.set_level(logging.DEBUG)
    antigua = _solicitud_antigua(db_session, sample_lead, publicacion, necesidad="demo")

    tarjeta = informe_de_publicaciones.llego_por(db_session, sample_lead)

    assert tarjeta.solicitudes[0].aviso_aceptado_en is not None
    assert tarjeta.solicitudes[0].aviso_aceptado_en.date() == antigua.occurred_at.date()
    # Y sin avisar: una marca que no esta es lo normal en una fila vieja, no una anomalia.
    # Tratarla como ilegible llenaria el registro de avisos por cada ficha antigua que se
    # abre, y los avisos que importan dejarian de verse.
    assert not [r for r in caplog.records if "ilegible" in r.getMessage()]


def test_una_marca_del_aviso_ilegible_no_tumba_la_ficha(
    client, lead_headers, publicacion, db_session, sample_lead, caplog
):
    """
    Una fecha que no se puede leer se cambia por la del envío, con un aviso en el registro.

    Pasa con una fila escrita a mano o migrada de otro sistema. La alternativa sería que la
    ficha 360 de esa persona contestara 500: un dato de más en una columna JSON no puede
    dejar sin ficha a nadie.
    """
    caplog.set_level(logging.DEBUG)
    antigua = _solicitud_antigua(
        db_session, sample_lead, publicacion,
        necesidad="vacantes", aviso_aceptado_en="ayer por la tarde",
    )

    tarjeta = informe_de_publicaciones.llego_por(db_session, sample_lead)

    assert tarjeta.solicitudes[0].aviso_aceptado_en.date() == antigua.occurred_at.date()
    assert any(
        "ilegible" in r.getMessage() and str(antigua.id) in r.getMessage()
        for r in caplog.records
    ), "un dato ilegible tiene que quedar anotado para poder arreglarlo"


# ==============================================================================
# Los bordes del rango de fechas y del grafico
# ==============================================================================

def test_el_informe_acota_tambien_por_la_fecha_de_fin(
    client, lead_headers, publicacion, db_session, sample_leads
):
    """
    `hasta` existe para mirar un mes cerrado, y era la mitad del rango sin ejercitar.

    Con el extremo de arriba roto, el informe de septiembre trae también lo de octubre: la
    cifra que se enseña es mayor que la real y no hay forma de notarlo desde la pantalla.

    **Hace falta una visita contada antes del envío**, y eso lo descubrió esta prueba: los
    dos agregados de envíos arrancan en `desde_el_dia`, que es el primer día con visitas
    —`_envios` devuelve 0 de entrada si no hay ninguna—. Sin la visita, el informe daba
    cero envíos con o sin tope y la prueba no distinguía nada: habría pasado en verde sin
    recorrer ni una de las dos ramas que dice cubrir.
    """
    hoy = datetime.date.today()
    campana = db_session.query(Campaign).filter(Campaign.id == publicacion["id"]).one()
    ciclo_de_publicaciones.registrar_visita(db_session, campana)
    _enviar(client, publicacion)

    sin_tope = client.get(
        f"{PUBLICACIONES}/{publicacion['id']}/informe", headers=lead_headers
    ).json()
    assert sin_tope["resumen"]["envios"] == 1
    assert sum(fila["envios"] for fila in sin_tope["por_red"]) == 1

    respuesta = client.get(
        f"{PUBLICACIONES}/{publicacion['id']}/informe",
        params={"hasta": (hoy - datetime.timedelta(days=1)).isoformat()},
        headers=lead_headers,
    )

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["filas"] == []
    # Los dos agregados que se calculan aparte del listado, y que tambien tienen que
    # respetar el extremo de arriba: la cuenta de envios y el reparto por red.
    assert cuerpo["resumen"]["envios"] == 0
    assert all(fila["envios"] == 0 and fila["perfiles"] == 0 for fila in cuerpo["por_red"])


def test_un_rango_al_reves_no_devuelve_ningun_dia(
    client, lead_headers, publicacion, db_session, sample_leads
):
    """
    Pedir del 20 al 10 no es un error del servidor: es un rango vacio.

    Sin la comprobacion, el calculo de los dias del grafico recorreria un rango negativo.
    """
    hoy = datetime.date.today()
    _sembrar(db_session, publicacion, email="cualquiera@ej.mx", score=60.0, etapa=LeadStatus.NEW)

    respuesta = client.get(
        f"{PUBLICACIONES}/{publicacion['id']}/informe",
        params={
            "desde": hoy.isoformat(),
            "hasta": (hoy - datetime.timedelta(days=10)).isoformat(),
        },
        headers=lead_headers,
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["por_dia"] == []


def test_el_dia_de_una_fecha_guardada_como_texto_se_entiende():
    """
    Las fechas de SQLite llegan a veces como cadena, y el grafico las agrupa por dia.

    Es la tercera rama de la funcion que normaliza: `datetime`, `date` y texto. La de texto
    solo se recorre con una fila escrita por otra herramienta, y es justo la que no se puede
    reproducir desde la aplicacion.
    """
    assert informe_de_publicaciones._dia("2026-10-07T18:30:00+00:00") == datetime.date(2026, 10, 7)
    assert informe_de_publicaciones._dia("2026-10-07") == datetime.date(2026, 10, 7)


# ==============================================================================
# Lo que se enseña cuando no hay nada, y el aviso del enlace caducado
# ==============================================================================

def test_la_comparativa_sin_ninguna_publicacion_no_falla(db_session):
    """
    El estado inicial de una instalación limpia, que es el que ve quien la estrena.

    Se mide sobre una base propia y vacía: la de la suite tiene publicaciones de otras
    pruebas, y comprobar «no hay ninguna» ahí dependería del orden de ejecución.
    """
    from app.core.database import Base
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    motor = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=motor)
    sesion = sessionmaker(bind=motor)()
    try:
        comparativa = informe_de_publicaciones.comparativa(sesion)

        assert comparativa.items == []
    finally:
        sesion.close()
        motor.dispose()


def test_el_panel_cuenta_las_publicaciones_con_el_enlace_caducado(
    client, lead_headers, publicacion, db_session
):
    """
    La cifra del aviso de arriba de la pantalla de publicaciones, que no tenía prueba.

    Es la misma comparación que hace cada fila, en una sola consulta: el panel la necesita
    antes de dibujar la lista para decidir si enseña el aviso.

    Sobre el `isnot(None)` de esa consulta —«cuenta solo las que tienen dirección anotada,
    porque las anteriores al capítulo 34 están a `NULL`»— hay algo que decir, porque el
    arnés lo intentó y no pudo: quitarlo **no cambia ninguna cifra**. En SQL
    `NULL != 'una-direccion'` no vale cierto, vale `NULL`, así que esas filas ya quedan
    fuera del `WHERE` sin ayuda. La condición escribe la intención y no tiene ningún efecto
    observable; ninguna prueba puede distinguirla, y decirlo vale más que inventar una que
    finja distinguirla. Lo que esta prueba sí sujeta es la comparación de verdad: que cuenta
    las que llevan una dirección DISTINTA de la actual y no las que llevan la actual.
    """
    def contadas():
        respuesta = client.get(f"{PUBLICACIONES}/direccion-publica", headers=lead_headers)
        assert respuesta.status_code == 200, respuesta.text
        return respuesta.json()["publicaciones_con_enlace_caducado"]

    campana = db_session.query(Campaign).filter(Campaign.id == publicacion["id"]).one()
    # Recien creada se activa bajo la direccion de ahora, asi que no esta caducada.
    assert campana.url_base_publicada == base_publica()
    antes = contadas()

    campana.url_base_publicada = "https://una-direccion-de-antes.example"
    db_session.commit()

    # Una exactamente, y se mide por diferencia: la base de la suite lleva publicaciones de
    # otras pruebas, y un numero absoluto dependeria del orden de ejecucion. Contar las que
    # tienen la direccion a NULL -las de antes del capitulo 34- habria dado el mismo total
    # antes y despues, que es justo el fallo que esta cifra no puede tener.
    assert contadas() == antes + 1


def test_un_asesor_sin_identificador_resoluble_no_ve_ninguna_fila_del_informe(
    db_session, publicacion, sample_leads
):
    """
    El mismo «fallar cerrado» del repositorio, en el informe, y por el mismo motivo.

    Las condiciones de alcance del informe reparten las filas en «mías» y «del resto»; con
    un identificador que no se puede resolver, la comparación natural con `NULL` convertiría
    «ninguna» en «las que no tienen asesor».

    **Hay que sembrar las dos fichas, y eso lo dijo el arnés.** La primera versión de esta
    prueba pedía el informe de una publicación recién creada y comprobaba `filas == []`,
    que salía vacío con alcance o sin él: neutralizar la condición —devolver `(None, None)`,
    que es justo lo que significa «ve la cartera completa»— no la ponía roja. Una prueba de
    alcance sobre un conjunto vacío no mide el alcance, mide que no hay nada.
    """
    campana = db_session.query(Campaign).filter(Campaign.id == publicacion["id"]).one()
    asesor = _usuario(db_session, "Commercial_Executive")
    _sembrar(
        db_session, publicacion, email="de.otro@ej.mx", score=80.0,
        etapa=LeadStatus.NEW, asesor_id=asesor.id, nombre="De otro",
    )
    # Y una sin dueño: es la que la comparación natural con `NULL` habría dejado ver.
    _sembrar(
        db_session, publicacion, email="de.nadie@ej.mx", score=70.0,
        etapa=LeadStatus.NEW, nombre="De nadie",
    )
    sin_identificador = AlcanceDeCartera.de(
        CurrentUser(
            user_id="no-soy-un-numero",
            email="raro@plurione.com",
            name="Sin identificador",
            role=UserRole.COMMERCIAL_EXECUTIVE,
        )
    )

    resultado = informe_de_publicaciones.informe(db_session, sin_identificador, campana)

    assert resultado.filas == []
    assert resultado.resumen.perfiles_recibidos == 0
    # Ni el número del resto: sin saber quién pregunta no hay «el resto» de nadie.
    assert resultado.resumen.de_otros_asesores == 0
    assert resultado.resumen.alcance_completo is False


def test_una_necesidad_que_ya_no_esta_en_la_tabla_deja_la_fila_del_informe_en_blanco(
    db_session, publicacion, sample_lead
):
    """
    La misma lectura que la tarjeta, por el otro camino: la fila del informe.

    `_necesidades` recorre las solicitudes de la publicacion y se queda con la etiqueta de
    la ultima de cada ficha. Una clave que ya no esta en la lista no se traduce y la fila
    sale sin necesidad; ensenar la clave interna -«equipo-ti-2024»- en una pantalla de
    negocio es ensenar un dato del sistema, no del prospecto.
    """
    campana = db_session.query(Campaign).filter(Campaign.id == publicacion["id"]).one()
    sample_lead.campaign_id = campana.id
    db_session.commit()
    _solicitud_antigua(db_session, sample_lead, publicacion, necesidad="una-clave-retirada")

    resultado = informe_de_publicaciones.informe(
        db_session, AlcanceDeCartera.del_sistema("prueba"), campana
    )

    fila = next(f for f in resultado.filas if f.lead_id == sample_lead.id)
    assert fila.necesidad is None


def test_la_comparativa_atribuye_las_solicitudes_antiguas_por_su_identificador(
    db_session, publicacion, sample_lead
):
    """
    La comparativa tiene su propia copia de la lectura del slug, y no se ejercitaba.

    Son dos copias de la misma regla en dos funciones -el informe de una publicacion y la
    comparativa de todas-, y si solo una sabe leer el identificador externo, los numeros de
    las dos pantallas no cuadran: la publicacion sale con una ficha en su informe y con
    cero en la tabla que la compara con las demas. Eso es exactamente la forma de fallo que
    este repositorio lleva anotada: una regla aplicada en uno solo de los sitios que la
    necesitaban no falla, se lee.
    """
    campana = db_session.query(Campaign).filter(Campaign.id == publicacion["id"]).one()
    antigua = _solicitud_antigua(db_session, sample_lead, publicacion, necesidad="equipo")
    assert "publicacion" not in (antigua.activity_data or {})

    fila = next(
        f for f in informe_de_publicaciones.comparativa(db_session).items
        if f.publicacion_id == campana.id
    )

    assert fila.perfiles_recibidos == 1


def test_la_comparativa_no_atribuye_una_solicitud_de_una_publicacion_que_no_existe(
    db_session, publicacion, sample_lead
):
    """
    Un slug que no es de ninguna publicacion no se suma a ninguna.

    Pasa de verdad: una publicacion borrada deja sus solicitudes en la tabla de actividad
    -que no se borra, porque es de donde sale el score- con un slug que ya no resuelve.
    Sumarlas a la primera publicacion, o a la que tenga un slug parecido, inventaria
    perfiles en una pantalla de negocio.
    """
    campana = db_session.query(Campaign).filter(Campaign.id == publicacion["id"]).one()
    huerfana = LeadActivity(
        lead_id=sample_lead.id,
        activity_type=ActivityType.FORM_SUBMIT,
        channel="Web",
        source=FUENTE_DE_LA_PAGINA,
        external_event_id=f"publicacion-que-ya-no-existe-{uuid.uuid4().hex[:8]}:{uuid.uuid4().hex}",
        verificada=True,
        activity_data={},
        occurred_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(huerfana)
    db_session.commit()

    items = informe_de_publicaciones.comparativa(db_session).items

    assert next(f for f in items if f.publicacion_id == campana.id).perfiles_recibidos == 0
    assert all(f.perfiles_recibidos == 0 for f in items)


def test_la_cuenta_de_envios_siempre_tiene_un_instante_de_inicio(
    db_session, publicacion, sample_lead
):
    """
    La premisa del `pragma: no branch` de `_envios`, derivada de la funcion y no escrita a mano.

    `_envios` recibe `inicio` opcional, y justo antes de usarlo hace
    `inicio = max(inicio, primero) if inicio is not None else primero`, donde `primero`
    siempre es un instante. A partir de esa linea `inicio` no puede ser None, asi que la
    salida contraria del `if inicio is not None` de debajo no se puede recorrer: no hay
    prueba que la alcance, y fingir una seria peor que marcarla.

    La premisa se comprueba por lo que se OBSERVA y no repitiendo el `max` en la prueba,
    que seria escribir el defecto encima del defecto: **sin `inicio`, la cuenta sigue
    acotada por abajo**. Un envio anterior al primer dia con visitas no se cuenta aunque no
    haya filtro de fechas, porque el suelo lo pone `primero`. Si alguien quitara ese valor
    por defecto, `inicio` volveria a poder ser None, el suelo desapareceria, el envio viejo
    entraria en la cuenta y esto se pone rojo -y entonces la marca deja de valer-.
    """
    campana = db_session.query(Campaign).filter(Campaign.id == publicacion["id"]).one()
    hoy = datetime.date.today()
    primer_dia_contado = hoy - datetime.timedelta(days=3)
    ciclo_de_publicaciones.registrar_visita(db_session, campana, dia=primer_dia_contado)

    for dias in (10, 1):
        db_session.add(
            LeadActivity(
                lead_id=sample_lead.id,
                activity_type=ActivityType.FORM_SUBMIT,
                channel="Web",
                source=FUENTE_DE_LA_PAGINA,
                external_event_id=f"{publicacion['public_slug']}:{uuid.uuid4().hex}",
                verificada=True,
                activity_data={},
                occurred_at=datetime.datetime.now(datetime.timezone.utc)
                - datetime.timedelta(days=dias),
            )
        )
    db_session.commit()

    sin_inicio = informe_de_publicaciones._envios(
        db_session, campana.public_slug, None, None, desde_el_dia=primer_dia_contado
    )

    # Dos envios en la tabla, uno de hace diez dias y otro de ayer; el suelo es hace tres.
    assert sin_inicio == 1, "sin `inicio`, el suelo lo pone el primer dia con visitas"
    # Y sin ningun dia contado no hay tasa, asi que no hay envios que contar para ella.
    assert informe_de_publicaciones._envios(
        db_session, campana.public_slug, None, None, desde_el_dia=None
    ) == 0
