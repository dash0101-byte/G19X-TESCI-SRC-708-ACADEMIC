"""
La página de interés: la única ruta que escribe en la base sin sesión.

Lo que se comprueba:

* **Lo que enseña**: título, descripción y las listas del formulario; nunca el presupuesto,
  a quién va dirigida ni el identificador interno de la campaña.
* **Lo que acepta**: obligatorio solo lo imprescindible, listas cerradas, perfil de
  LinkedIn con forma de perfil, aviso aceptado, ningún campo de más y nada de facturación.
* **Lo que hace**: crea la ficha con lo que llegó y nada más, la atribuye a su publicación
  y la puntúa. «¿Qué necesitas?» se guarda y no puntúa. El asesor no lo elige la página:
  hasta el capítulo 46 la ficha esperaba al líder, y desde él la reparte el reparto
  automático por carga, salvo que la publicación tenga responsable.
* **Lo que no hace**: pisar los datos de una ficha que ya existe.
* **Cómo se defiende**: límite por IP y por publicación, campo trampa, «no disponible» y la
  misma respuesta exista o no el correo.
"""
import pytest
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.vector_del_modelo import CATEGORIAS_DEL_MODELO
from app.models.entities import ActivityType, Lead
from app.schemas.interes import NECESIDADES
from app.services.pagina_de_interes import MENSAJE, NO_DISPONIBLE

CAMPANAS = "/api/v1/campaigns"

SOLICITUD = {
    "nombre": "Ana Prueba",
    "correo": "ana.interes@example.com",
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

# Lo que la página exige: sin cualquiera de estos, no hay envío.
OBLIGATORIOS = (
    "nombre", "correo", "empresa", "cargo", "sector", "tamano_de_empresa", "necesidad",
    "aviso_de_privacidad",
)
# Lo mínimo que se puede mandar: lo obligatorio y nada más.
MINIMA = {campo: SOLICITUD[campo] for campo in OBLIGATORIOS}


@pytest.fixture
def publicacion(client, lead_headers):
    """Una publicación creada por la vía normal: una campaña con canal LinkedIn."""
    return client.post(
        CAMPANAS,
        headers=lead_headers,
        json={
            "name": "Post · Talento TI septiembre",
            "channel": "LinkedIn",
            "description": "¿Tu equipo de TI tarda meses en cubrir una vacante?",
            "target_audience": "Directores de TI",
            "budget": 5000.0,
        },
    ).json()


def _ruta(publicacion) -> str:
    return f"/api/v1/interes/{publicacion['public_slug']}"


def _enviar(client, publicacion, **cambios):
    cuerpo = {**SOLICITUD, **cambios}
    return client.post(_ruta(publicacion), json=cuerpo)


def _ficha(db_session, correo=SOLICITUD["correo"]) -> Lead:
    db_session.expire_all()
    return db_session.query(Lead).filter(Lead.email == correo).one()


# ==============================================================================
# Lo que enseña la página
# ==============================================================================

def test_la_pagina_se_ve_sin_sesion(client, publicacion):
    respuesta = client.get(_ruta(publicacion))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["titulo"] == "Post · Talento TI septiembre"
    assert cuerpo["descripcion"].startswith("¿Tu equipo de TI")


def test_no_ensena_el_presupuesto_ni_a_quien_va_dirigida(client, publicacion):
    cuerpo = client.get(_ruta(publicacion)).json()

    plano = str(cuerpo)
    assert "5000" not in plano
    assert "Directores de TI" not in plano
    assert "id" not in cuerpo


def test_las_listas_del_formulario_son_las_del_modelo(client, publicacion):
    """
    Si la página pintara una lista propia, un sector escrito de otra forma no daría error:
    el preprocesador lo descartaría en silencio y el prospecto puntuaría sin sector.
    """
    opciones = client.get(_ruta(publicacion)).json()["opciones"]

    assert opciones["cargos"] == list(CATEGORIAS_DEL_MODELO["job_title"])
    assert opciones["sectores"] == list(CATEGORIAS_DEL_MODELO["industry"])
    assert opciones["tamanos"] == list(CATEGORIAS_DEL_MODELO["company_size"])
    assert opciones["necesidades"] == NECESIDADES
    # La facturación ya no se pregunta: no hay lista que pintar.
    assert set(opciones) == {"cargos", "sectores", "tamanos", "necesidades"}


def test_una_publicacion_inexistente_no_esta_disponible(client):
    inventada = "/api/v1/interes/estoMeLoInvento00000x"

    for respuesta in (client.get(inventada), client.post(inventada, json=SOLICITUD)):
        assert respuesta.status_code == 404
        assert respuesta.json()["detail"] == NO_DISPONIBLE


def test_una_publicacion_desactivada_no_esta_disponible(client, lead_headers, publicacion, db_session):
    client.delete(f"{CAMPANAS}/{publicacion['id']}", headers=lead_headers)

    assert client.get(_ruta(publicacion)).json()["detail"] == NO_DISPONIBLE
    assert _enviar(client, publicacion).status_code == 404
    assert db_session.query(Lead).filter(Lead.email == SOLICITUD["correo"]).count() == 0


def test_una_campana_que_no_es_publicacion_no_tiene_pagina(client, lead_headers, db_session):
    """El enlace existe para todas las campañas, pero solo las de LinkedIn son publicaciones."""
    campana = client.post(
        CAMPANAS, headers=lead_headers, json={"name": "Google Ads Q3", "channel": "Google Ads"}
    ).json()

    assert client.get(f"/api/v1/interes/{campana['public_slug']}").status_code == 404


# ==============================================================================
# Un envío nuevo
# ==============================================================================

def test_un_envio_crea_la_ficha_puntuada_y_atribuida(client, publicacion, db_session):
    respuesta = _enviar(client, publicacion)

    assert respuesta.status_code == 202
    assert respuesta.json()["mensaje"] == MENSAJE

    lead = _ficha(db_session)
    # El nombre, entero: partirlo sería adivinar dónde empiezan los apellidos.
    assert (lead.first_name, lead.last_name, lead.company) == ("Ana Prueba", "", "Ejemplo SA")
    assert (lead.job_title, lead.industry, lead.company_size) == ("CTO", "FinTech", "201-1000")
    assert lead.phone == "+525598765432"
    # Sin `?r=`, el canal es «Publicación» y no «LinkedIn»: el enlace se pudo compartir
    # desde cualquier sitio y escribir una red que no consta sería inventarla (cap. 27).
    assert lead.source == "Publicación"
    assert lead.campaign_id == publicacion["id"]
    assert lead.current_score > 0
    assert lead.privacy_notice_accepted_at is not None
    assert lead.privacy_notice_source == "pagina_de_interes"


def test_la_pagina_no_elige_asesor(client, publicacion, db_session, sales_reps, monkeypatch):
    """
    La página no elige por nadie: con el reparto apagado, la ficha nace sin asesor.

    Hasta el capítulo 46 esto era todo lo que había, y era el punto 10 de §6.2: la ficha se
    quedaba sin dueño hasta que el líder abriera la matriz, y sin dueño el motor de reglas no
    tiene de quién hablar —ni tarea, ni aviso, ni bandeja—.
    """
    monkeypatch.setattr(settings, "REPARTO_AUTOMATICO_ACTIVO", False)

    _enviar(client, publicacion)

    assert _ficha(db_session).assigned_rep_id is None


def test_la_ficha_de_una_publicacion_sin_responsable_la_reparte_el_reparto(
    client, publicacion, db_session, sales_reps
):
    """
    Capítulo 46. La publicación de este fixture no tiene responsable, así que la ficha entra
    en el reparto y sale con la asesora de menos cartera abierta, no con la del `capacity`
    más alto, que es lo que hacía el `if` anterior.
    """
    _enviar(client, publicacion)

    assert _ficha(db_session).assigned_rep_id in {rep.id for rep in sales_reps}


def test_basta_con_lo_obligatorio(client, publicacion, db_session):
    """Teléfono y perfil de LinkedIn son opcionales: sin ellos, la solicitud entra igual."""
    assert client.post(_ruta(publicacion), json=MINIMA).status_code == 202
    assert _ficha(db_session).current_score > 0


@pytest.mark.parametrize("campo", OBLIGATORIOS)
def test_sin_un_obligatorio_no_hay_envio(client, publicacion, db_session, campo):
    cuerpo = {k: v for k, v in MINIMA.items() if k != campo}

    assert client.post(_ruta(publicacion), json=cuerpo).status_code == 422
    assert db_session.query(Lead).filter(Lead.email == SOLICITUD["correo"]).count() == 0


@pytest.mark.parametrize("vacio", [None, ""])
def test_lo_que_no_se_indico_queda_vacio(client, publicacion, db_session, vacio):
    """
    Ni teléfono, ni perfil, ni ingresos. `annual_revenue` —la variable del modelo— se queda
    vacía: la página no la pregunta y no hay cifra que escribir.
    """
    _enviar(client, publicacion, telefono=vacio, linkedin=vacio)

    lead = _ficha(db_session)
    assert lead.phone is None
    assert lead.annual_revenue is None
    assert lead.city is None
    assert "perfil_de_linkedin" not in lead.raw_metadata


@pytest.mark.parametrize(
    "campo,valor",
    [("tramo_de_ingresos", "10m_50m"), ("annual_revenue", 25_000_000), ("apellidos", "Prueba")],
)
def test_lo_que_ya_no_se_pregunta_se_rechaza(client, publicacion, db_session, campo, valor):
    """
    La facturación salió del formulario, y con ella cualquier forma de colarla. Si un
    cliente viejo la sigue mandando, es un error visible y no un dato que se guarda aparte.
    """
    assert _enviar(client, publicacion, **{campo: valor}).status_code == 422
    assert db_session.query(Lead).filter(Lead.email == SOLICITUD["correo"]).count() == 0


def test_el_perfil_opcional_se_guarda_cuando_llega(client, publicacion, db_session):
    _enviar(client, publicacion)

    lead = _ficha(db_session)
    assert lead.raw_metadata == {"perfil_de_linkedin": "https://www.linkedin.com/in/ana-prueba"}
    assert lead.annual_revenue is None


def test_la_actividad_queda_con_su_procedencia(client, publicacion, db_session):
    _enviar(client, publicacion)

    actividad = _ficha(db_session).activities[0]
    assert actividad.activity_type == ActivityType.FORM_SUBMIT
    assert actividad.source == "pagina_de_interes"
    assert actividad.verificada is True
    assert actividad.channel == "Publicación"
    assert actividad.activity_data["red"] == "sin_red"
    assert actividad.activity_data["publicacion"] == publicacion["public_slug"]


@pytest.mark.parametrize("necesidad", sorted(NECESIDADES))
def test_la_necesidad_se_guarda_para_el_asesor_y_no_en_la_ficha(client, publicacion, db_session, necesidad):
    _enviar(client, publicacion, necesidad=necesidad)

    lead = _ficha(db_session)
    actividad = lead.activities[0]
    # Una solicitud es una solicitud, pida lo que pida: nunca una demo registrada.
    assert actividad.activity_type == ActivityType.FORM_SUBMIT
    assert actividad.activity_data["necesidad"] == necesidad
    # Fuera de `raw_metadata`, que la regla heurística y la explicación sí leen.
    assert "necesidad" not in lead.raw_metadata


def test_la_necesidad_no_puntua(client, publicacion, db_session):
    """
    Dos personas iguales que solo difieren en lo que dicen necesitar puntúan igual, en el
    total y en cada parte. Hasta el capítulo 25, «Ver una demostración» sumaba 25 puntos en
    la regla y encendía `requested_demo` en el modelo.
    """
    historiales = {}
    for necesidad in sorted(NECESIDADES):
        correo = f"necesidad.{necesidad}@example.com"
        # Sin teléfono ni perfil compartidos: el registro uniría las cuatro en una ficha.
        _enviar(client, publicacion, correo=correo, necesidad=necesidad, telefono=None, linkedin=None)
        lead = _ficha(db_session, correo)
        historiales[necesidad] = (lead.current_score, lead.score_histories[0])

    puntuaciones = {score for score, _ in historiales.values()}
    assert len(puntuaciones) == 1, historiales
    desgloses = [h.rule_breakdown for _, h in historiales.values()]
    assert all(d == desgloses[0] for d in desgloses)
    probabilidades = {h.ml_probability for _, h in historiales.values()}
    assert len(probabilidades) == 1
    for _, historial in historiales.values():
        assert historial.feature_snapshot["requested_demo"] == 0


# ==============================================================================
# Un segundo envío con el mismo correo
# ==============================================================================

def test_un_segundo_envio_suma_al_historial_sin_pisar_datos(client, publicacion, db_session):
    _enviar(client, publicacion)
    lead = _ficha(db_session)
    lead.job_title = "Director de Tecnología"
    lead.company = "Nombre corregido por el asesor"
    db_session.commit()
    puntuado_en = lead.last_score_update

    segunda = _enviar(
        client, publicacion, cargo="Estudiante / Trainee", sector="Education",
        tamano_de_empresa="1-10", empresa="Otra empresa",
    )

    assert segunda.status_code == 202
    db_session.expire_all()
    assert db_session.query(Lead).filter(Lead.email == SOLICITUD["correo"]).count() == 1
    lead = _ficha(db_session)
    assert lead.job_title == "Director de Tecnología"
    assert lead.company == "Nombre corregido por el asesor"
    assert len(lead.activities) == 2
    # Se vuelve a puntuar, y con los datos de la ficha —los del asesor—, no con los que
    # acaban de llegar: el cargo que cuenta es «Director de Tecnología».
    assert lead.last_score_update > puntuado_en


def test_la_respuesta_es_la_misma_exista_o_no_el_correo(client, publicacion):
    """Si dijera «ya está registrado», serviría para averiguar qué correos hay en la base."""
    primera = _enviar(client, publicacion)
    segunda = _enviar(client, publicacion)

    assert primera.status_code == segunda.status_code == 202
    assert primera.json()["mensaje"] == segunda.json()["mensaje"]
    assert set(primera.json()) == set(segunda.json())


def test_un_segundo_envio_no_cambia_la_campana_de_la_ficha(client, lead_headers, publicacion, db_session):
    """La atribución de una ficha es de la publicación que la trajo, no de la última que la tocó."""
    _enviar(client, publicacion)
    otra = client.post(
        CAMPANAS, headers=lead_headers,
        json={"name": "Post · Otro", "channel": "LinkedIn", "description": "Otro texto"},
    ).json()

    _enviar(client, otra)

    assert _ficha(db_session).campaign_id == publicacion["id"]


# ==============================================================================
# Defensas
# ==============================================================================

def test_el_campo_trampa_descarta_sin_decirlo(client, publicacion, db_session):
    respuesta = _enviar(client, publicacion, sitio_web="https://spam.example")

    assert respuesta.status_code == 202
    assert respuesta.json()["mensaje"] == MENSAJE
    assert db_session.query(Lead).filter(Lead.email == SOLICITUD["correo"]).count() == 0


def test_sin_aceptar_el_aviso_no_se_registra(client, publicacion, db_session):
    respuesta = _enviar(client, publicacion, aviso_de_privacidad=False)

    assert respuesta.status_code == 422
    assert "aviso de privacidad" in str(respuesta.json()["detail"])
    assert db_session.query(Lead).filter(Lead.email == SOLICITUD["correo"]).count() == 0


def test_un_envio_que_omite_el_aviso_tampoco_se_registra(client, publicacion, db_session):
    """
    Mandarlo en falso y no mandarlo son dos caminos distintos: un valor por defecto en el
    esquema bastaría para que un cliente que simplemente no lo envía quedara registrado
    como si hubiera consentido.
    """
    cuerpo = {k: v for k, v in SOLICITUD.items() if k != "aviso_de_privacidad"}

    respuesta = client.post(_ruta(publicacion), json=cuerpo)

    assert respuesta.status_code == 422
    assert db_session.query(Lead).filter(Lead.email == SOLICITUD["correo"]).count() == 0


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("cargo", "Jefe de todo"),
        ("sector", "Tecnología"),
        ("tamano_de_empresa", "200-999"),
        ("necesidad", "otra cosa"),
        ("linkedin", "https://www.linkedin.com/company/plurione"),
        ("linkedin", "https://ejemplo.com/in/ana"),
        ("correo", "no-es-un-correo"),
        ("empresa", ""),
    ],
)
def test_un_valor_fuera_de_la_lista_se_rechaza(client, publicacion, db_session, campo, valor):
    respuesta = _enviar(client, publicacion, **{campo: valor})

    assert respuesta.status_code == 422
    assert db_session.query(Lead).filter(Lead.email == SOLICITUD["correo"]).count() == 0


def test_un_campo_de_mas_se_rechaza(client, publicacion):
    """Estricto: un campo que el servidor no espera es un error, no algo que se ignora."""
    assert _enviar(client, publicacion, notas="cuéntame tu caso").status_code == 422
    assert _enviar(client, publicacion, current_score=99).status_code == 422


@pytest.mark.parametrize(
    "perfil",
    [
        "https://www.linkedin.com/in/ana-prueba",
        "https://linkedin.com/in/ana-prueba/",
        "https://mx.linkedin.com/in/ana-prueba",
    ],
)
def test_las_formas_validas_del_perfil_se_aceptan(client, publicacion, perfil):
    assert _enviar(client, publicacion, linkedin=perfil).status_code == 202


@pytest.mark.parametrize(
    ("pegado", "guardado"),
    [
        # Lo que da el botón «compartir» de la aplicación de LinkedIn.
        ("https://www.linkedin.com/in/ana-prueba?utm_source=share&utm_medium=member_ios",
         "https://www.linkedin.com/in/ana-prueba"),
        # Lo que escribe quien lo teclea de memoria.
        ("linkedin.com/in/ana-prueba", "https://linkedin.com/in/ana-prueba"),
        ("www.linkedin.com/in/ana-prueba", "https://www.linkedin.com/in/ana-prueba"),
        ("http://www.linkedin.com/in/ana-prueba", "https://www.linkedin.com/in/ana-prueba"),
        ("https://www.linkedin.com/in/ana-prueba#seccion", "https://www.linkedin.com/in/ana-prueba"),
    ],
)
def test_el_perfil_se_limpia_antes_de_comprobarlo(client, publicacion, db_session, pegado, guardado):
    """
    Lo que la gente pega no es lo que el patrón esperaba, y rechazarlo paraba el envío con
    un mensaje que no decía qué sobraba. Se completa el esquema y se quitan los parámetros
    de campaña; lo que se guarda es la forma limpia.
    """
    assert _enviar(client, publicacion, linkedin=pegado).status_code == 202
    assert _ficha(db_session).raw_metadata["perfil_de_linkedin"] == guardado


def test_limpiar_no_es_aceptar_cualquier_cosa(client, publicacion):
    """La limpieza no abre la puerta: después sigue teniendo que ser un perfil de LinkedIn."""
    for perfil in ("ejemplo.com/in/ana", "linkedin.com/company/plurione", "javascript:alert(1)"):
        assert _enviar(client, publicacion, linkedin=perfil).status_code == 422


def test_el_limite_por_ip_corta_los_envios(client, publicacion, monkeypatch):
    monkeypatch.setattr(settings, "INTERES_LIMITE_POR_IP", "2/hour")
    limiter.enabled = True
    limiter.reset()

    assert _enviar(client, publicacion, correo="uno@example.com").status_code == 202
    assert _enviar(client, publicacion, correo="dos@example.com").status_code == 202
    assert _enviar(client, publicacion, correo="tres@example.com").status_code == 429


def test_el_limite_por_publicacion_corta_aunque_cambie_la_ip(client, publicacion, lead_headers, monkeypatch):
    """Sin este límite, un enlace difundido llena la base repartiendo los envíos entre IP."""
    monkeypatch.setattr(settings, "INTERES_LIMITE_POR_PUBLICACION", "1/hour")
    limiter.enabled = True
    limiter.reset()

    assert _enviar(client, publicacion, correo="uno@example.com").status_code == 202
    assert _enviar(client, publicacion, correo="dos@example.com").status_code == 429

    otra = client.post(
        CAMPANAS, headers=lead_headers,
        json={"name": "Post · Otro", "channel": "LinkedIn", "description": "Otro"},
    ).json()
    assert _enviar(client, otra, correo="tres@example.com").status_code == 202


def test_abrir_la_pagina_no_gasta_los_envios(client, publicacion, monkeypatch):
    """
    Ver no es enviar. Con la misma cuenta, unas cuantas visitas desde una oficina detrás de
    una sola IP dejaban sin poder enviar —y sin ver el formulario— a quien sí quería.
    """
    monkeypatch.setattr(settings, "INTERES_LIMITE_POR_IP", "2/hour")
    limiter.enabled = True
    limiter.reset()

    for _ in range(5):
        assert client.get(_ruta(publicacion)).status_code == 200
    assert _enviar(client, publicacion, correo="uno@example.com").status_code == 202
    assert _enviar(client, publicacion, correo="dos@example.com").status_code == 202
    assert _enviar(client, publicacion, correo="tres@example.com").status_code == 429


def test_las_lecturas_tienen_su_propio_limite(client, publicacion, monkeypatch):
    monkeypatch.setattr(settings, "INTERES_LIMITE_DE_LECTURAS_POR_IP", "2/hour")
    limiter.enabled = True
    limiter.reset()

    assert [client.get(_ruta(publicacion)).status_code for _ in range(3)] == [200, 200, 429]
    # Y agotar las lecturas no gasta los envíos.
    assert _enviar(client, publicacion).status_code == 202


def test_un_limite_mal_escrito_se_rechaza_al_arrancar():
    from app.core.config import Settings

    with pytest.raises(ValueError):
        Settings(INTERES_LIMITE_POR_IP="unos cuantos por hora")


def test_el_registro_no_lleva_el_correo_de_quien_escribe(client, publicacion, caplog):
    import logging

    with caplog.at_level(logging.INFO, logger="app.services.pagina_de_interes"):
        _enviar(client, publicacion)

    assert SOLICITUD["correo"] not in caplog.text
    assert publicacion["public_slug"] in caplog.text
