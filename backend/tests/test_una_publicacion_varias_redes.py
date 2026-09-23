"""
Una publicación, varias redes (capítulo 27).

Lo que se comprueba, por el orden del capítulo:

1. **Las redes de una publicación**: cuáles vienen activadas, cuáles se pueden activar y qué
   pasa con una que no existe. Cada red tiene su enlace a la **misma** página.
2. **La red de llegada**: se registra en la actividad, en la ficha 360 y como canal de la
   ficha. Una red desconocida o manipulada se registra como «sin red» y **nunca** rechaza
   el envío.
3. **El texto de cada red**: X recortado a 280 contando el enlace, WhatsApp y correo cortos,
   Instagram con su aviso. El enlace no se recorta nunca.
4. **Los botones de compartir**: enlaces oficiales, sin API ni cuentas, y «Copiar texto»
   donde la red no se lleva el texto.
5. **El modelo**: ninguno de los canales nuevos lo conoce, así que todos son neutros. Un
   prospecto puntúa igual venga por donde venga.
6. **El informe**: una fila por red con visitas, envíos, tasa, perfiles y score medio.
7. **Los permisos**: como antes, edita el líder y el administrador.
"""
import datetime

import pytest
from app.core import redes as r
from app.core.publicaciones import CANAL_LINKEDIN
from app.core.vector_del_modelo import CATEGORIAS_DEL_MODELO
from app.models.entities import Campaign, Lead, LeadActivity, VisitaDePublicacion
from app.services import ciclo_de_publicaciones as ciclo
from app.services import informe_de_publicaciones as informes
from app.services.pagina_de_interes import NO_DISPONIBLE

CAMPANAS = "/api/v1/campaigns"

SOLICITUD = {
    "nombre": "Rosa Redes",
    "correo": "rosa.redes@example.com",
    "empresa": "Ejemplo SA",
    "cargo": "CTO",
    "sector": "FinTech",
    "tamano_de_empresa": "201-1000",
    "necesidad": "vacantes",
    "aviso_de_privacidad": True,
}


@pytest.fixture
def publicacion(client, lead_headers):
    return client.post(
        CAMPANAS,
        headers=lead_headers,
        json={
            "name": "Post · Redes",
            "channel": CANAL_LINKEDIN,
            "description": "¿Tu equipo de TI tarda meses en cubrir una vacante?",
        },
    ).json()


def _pagina(publicacion, red=None):
    ruta = f"/api/v1/interes/{publicacion['public_slug']}"
    return f"{ruta}?r={red}" if red is not None else ruta


def _enviar(client, publicacion, red=None, **cambios):
    return client.post(_pagina(publicacion, red), json={**SOLICITUD, **cambios})


def _actividad(db_session, correo=SOLICITUD["correo"]):
    db_session.expire_all()
    lead = db_session.query(Lead).filter(Lead.email == correo).one()
    return lead, db_session.query(LeadActivity).filter(LeadActivity.lead_id == lead.id).one()


# ==============================================================================
# 1. Las redes de una publicación
# ==============================================================================

def test_una_publicacion_nace_con_las_redes_de_siempre(publicacion):
    assert publicacion["redes"] == ["linkedin", "whatsapp", "facebook", "correo"]
    assert publicacion["redes_propias"] is False


def test_instagram_y_x_existen_pero_no_vienen_activadas(publicacion):
    por_clave = {red["clave"]: red for red in publicacion["difusion"]}

    assert set(por_clave) == {"linkedin", "whatsapp", "facebook", "correo", "instagram", "x"}
    assert por_clave["instagram"]["activa"] is False
    assert por_clave["x"]["activa"] is False


def test_cada_red_tiene_su_enlace_a_la_misma_pagina(publicacion):
    base = publicacion["enlace_publico"]

    for red in publicacion["difusion"]:
        assert red["enlace"] == f"{base}?r={red['clave']}"


def test_el_lider_activa_y_desactiva_redes(client, lead_headers, publicacion):
    respuesta = client.put(
        f"{CAMPANAS}/{publicacion['id']}", headers=lead_headers, json={"redes": ["x", "whatsapp"]}
    )

    assert respuesta.status_code == 200
    # Se guardan en el orden fijo, no en el que se escribieron: el orden de los botones no
    # es una preferencia que haya que recordar.
    assert respuesta.json()["redes"] == ["whatsapp", "x"]
    assert respuesta.json()["redes_propias"] is True


def test_volver_a_null_devuelve_las_redes_de_siempre(client, lead_headers, publicacion):
    client.put(f"{CAMPANAS}/{publicacion['id']}", headers=lead_headers, json={"redes": ["x"]})
    respuesta = client.put(f"{CAMPANAS}/{publicacion['id']}", headers=lead_headers, json={"redes": None})

    assert respuesta.json()["redes"] == ["linkedin", "whatsapp", "facebook", "correo"]
    assert respuesta.json()["redes_propias"] is False


@pytest.mark.parametrize("redes", [["tiktok"], ["whatsapp", "telegram"], []])
def test_una_red_desconocida_o_ninguna_no_se_guarda(client, lead_headers, publicacion, redes):
    respuesta = client.put(f"{CAMPANAS}/{publicacion['id']}", headers=lead_headers, json={"redes": redes})

    assert respuesta.status_code == 422


def test_el_catalogo_de_redes_viaja_con_la_lista(client, lead_headers, publicacion):
    """Una sola fuente: el navegador no lleva su propia copia de las redes que existen."""
    datos = client.get(f"{CAMPANAS}?canal={CANAL_LINKEDIN}", headers=lead_headers).json()

    disponibles = {red["clave"]: red for red in datos["redes_disponibles"]}
    assert list(disponibles) == list(r.ORDEN)
    assert disponibles["whatsapp"]["por_defecto"] is True
    assert disponibles["instagram"]["por_defecto"] is False


def test_duplicar_se_lleva_las_redes(client, lead_headers, publicacion):
    client.put(f"{CAMPANAS}/{publicacion['id']}", headers=lead_headers, json={"redes": ["whatsapp", "x"]})

    copia = client.post(f"{CAMPANAS}/{publicacion['id']}/duplicar", headers=lead_headers).json()

    assert copia["redes"] == ["whatsapp", "x"]


# ==============================================================================
# 2. La red de llegada
# ==============================================================================

def test_la_red_queda_en_la_actividad_y_en_el_canal_de_la_ficha(client, publicacion, db_session):
    assert _enviar(client, publicacion, red="whatsapp").status_code == 202

    lead, actividad = _actividad(db_session)
    assert lead.source == "WhatsApp"
    assert actividad.channel == "WhatsApp"
    assert actividad.activity_data["red"] == "whatsapp"
    assert actividad.activity_data["red_etiqueta"] == "WhatsApp"


@pytest.mark.parametrize(
    "red,canal",
    [("linkedin", "LinkedIn"), ("facebook", "Facebook"), ("correo", "Correo"),
     ("instagram", "Instagram"), ("x", "X")],
)
def test_cada_red_deja_su_canal(client, publicacion, db_session, red, canal):
    _enviar(client, publicacion, red=red)

    lead, _ = _actividad(db_session)
    assert lead.source == canal


@pytest.mark.parametrize("valor", ["tiktok", "WHATSAPP-falso", "../../etc", "x" * 400, ""])
def test_una_red_desconocida_o_manipulada_no_rechaza_el_envio(client, publicacion, db_session, valor):
    """
    El parámetro lo edita cualquiera. Si rechazara, bastaría con tocar la dirección para
    dejar la página sin recibir a nadie.
    """
    respuesta = _enviar(client, publicacion, red=valor)

    assert respuesta.status_code == 202
    lead, actividad = _actividad(db_session)
    assert actividad.activity_data["red"] == "sin_red"
    assert lead.source == "Publicación"


def test_sin_parametro_la_ficha_no_dice_que_vino_de_linkedin(client, publicacion, db_session):
    """Un enlace pegado a mano se pudo compartir desde cualquier sitio."""
    _enviar(client, publicacion)

    lead, actividad = _actividad(db_session)
    assert actividad.activity_data["red"] == "sin_red"
    assert lead.source == "Publicación"


def test_una_red_desactivada_sigue_contando_lo_que_trae(client, lead_headers, publicacion, db_session):
    """
    Desactivar WhatsApp no invalida los enlaces ya repartidos. Si los invalidara, la gente
    que llegara por ellos aparecería como «sin red» y el informe borraría de dónde vino.
    """
    client.put(f"{CAMPANAS}/{publicacion['id']}", headers=lead_headers, json={"redes": ["linkedin"]})

    _enviar(client, publicacion, red="whatsapp")

    lead, actividad = _actividad(db_session)
    assert actividad.activity_data["red"] == "whatsapp"
    assert lead.source == "WhatsApp"


def test_la_ficha_360_dice_por_que_red_llego(client, publicacion, lead_headers, db_session):
    _enviar(client, publicacion, red="facebook")
    lead, _ = _actividad(db_session)

    ficha = client.get(f"/api/v1/leads/{lead.id}", headers=lead_headers).json()

    assert ficha["llego_por"]["solicitudes"][0]["red"] == "Facebook"


def test_una_solicitud_anterior_al_capitulo_se_queda_en_sin_red(db_session):
    """Las actividades de antes no llevan red; decir «LinkedIn» sería inventarlo."""
    assert informes.red_de({"publicacion": "abc"}) == "sin_red"
    assert informes.red_de({"red": "whatsapp"}) == "whatsapp"
    assert informes.red_de({"red": "tiktok"}) == "sin_red"


# ==============================================================================
# Las visitas, por red
# ==============================================================================

def test_la_visita_se_cuenta_en_su_red(client, publicacion, db_session):
    client.get(_pagina(publicacion, "whatsapp"))
    client.get(_pagina(publicacion, "whatsapp"))
    client.get(_pagina(publicacion, "facebook"))
    client.get(_pagina(publicacion))

    filas = {
        v.red: v.visitas
        for v in db_session.query(VisitaDePublicacion).filter(
            VisitaDePublicacion.campaign_id == publicacion["id"]
        )
    }
    assert filas == {"whatsapp": 2, "facebook": 1, "sin_red": 1}


def test_una_red_inventada_cuenta_como_sin_red_y_la_pagina_se_sirve(client, publicacion, db_session):
    respuesta = client.get(_pagina(publicacion, "tiktok"))

    assert respuesta.status_code == 200
    assert respuesta.json()["titulo"] == publicacion["name"]
    fila = db_session.query(VisitaDePublicacion).one()
    assert (fila.red, fila.visitas) == ("sin_red", 1)


def test_el_contador_por_red_no_guarda_nada_de_quien_visita():
    columnas = {c.name for c in VisitaDePublicacion.__table__.columns}

    assert columnas == {"campaign_id", "dia", "red", "visitas"}


def test_una_pagina_no_disponible_no_cuenta_visitas_de_ninguna_red(client, lead_headers, db_session):
    borrador = client.post(
        CAMPANAS, headers=lead_headers, json={"name": "Borrador", "channel": CANAL_LINKEDIN, "estado": "borrador"}
    ).json()

    respuesta = client.get(_pagina(borrador, "whatsapp"))

    assert respuesta.json()["detail"] == NO_DISPONIBLE
    assert db_session.query(VisitaDePublicacion).count() == 0


# ==============================================================================
# 3. El texto de cada red
# ==============================================================================

def test_el_texto_de_x_cabe_en_280_contando_el_enlace(publicacion):
    por_clave = {red["clave"]: red for red in publicacion["difusion"]}

    assert por_clave["x"]["maximo"] == 280
    assert por_clave["x"]["longitud"] <= 280


def test_un_texto_largo_se_recorta_en_x_pero_el_enlace_entra_entero(client, lead_headers):
    largo = "Buscamos perfiles de tecnología con experiencia en equipos distribuidos. " * 20
    creada = client.post(
        CAMPANAS,
        headers=lead_headers,
        json={"name": "Post · Largo", "channel": CANAL_LINKEDIN, "description": largo, "redes": ["x", "linkedin"]},
    ).json()

    por_clave = {red["clave"]: red for red in creada["difusion"]}
    texto = por_clave["x"]["texto"]
    assert len(texto) <= 280
    # Lo que cede es la descripción, nunca el enlace: un texto cortado sigue diciendo algo
    # y un enlace cortado no lleva a ninguna parte.
    assert texto.endswith(por_clave["x"]["enlace"])
    assert "…" in texto
    # Y en LinkedIn, donde cabe, no se recorta.
    assert "…" not in por_clave["linkedin"]["texto"]


def test_el_recorte_no_parte_palabras():
    """
    Palabras largas y todas iguales: sin corte por palabra, el recorte cae dentro de una de
    ellas casi seguro. Cortar a mitad de palabra deja textos que parecen un error de
    programa y no un resumen.
    """
    descripcion = ("responsabilidades " * 40).strip()

    cuerpo = r.texto_para("x", descripcion, "SLUG").split("\n\n")[0]

    assert cuerpo.endswith("…")
    recortado = cuerpo[:-1]
    assert descripcion.startswith(recortado), "el recorte no es un prefijo del texto"
    # Lo que sigue en el original tiene que ser un espacio: si fuera una letra, el recorte
    # habría partido «responsabilidades» por la mitad.
    assert descripcion[len(recortado)] == " ", f"cortó dentro de una palabra: «{recortado[-20:]}»"


def test_whatsapp_y_correo_son_mas_cortos_que_linkedin(publicacion):
    por_clave = {red["clave"]: red["maximo"] for red in publicacion["difusion"]}

    assert por_clave["whatsapp"] < por_clave["linkedin"]
    assert por_clave["correo"] < por_clave["linkedin"]


def test_instagram_avisa_de_que_el_enlace_va_en_la_biografia(publicacion):
    instagram = next(red for red in publicacion["difusion"] if red["clave"] == "instagram")

    assert "biografía" in instagram["aviso"]
    assert "historia" in instagram["aviso"]


def test_sin_descripcion_el_texto_es_solo_el_enlace_de_la_red():
    assert r.texto_para("whatsapp", None, "SLUG") == r.enlace_de_red("SLUG", "whatsapp")


# ==============================================================================
# 4. Los botones de compartir
# ==============================================================================

@pytest.mark.parametrize(
    "red,dominio",
    [
        ("linkedin", "https://www.linkedin.com/sharing/share-offsite/"),
        ("facebook", "https://www.facebook.com/sharer/sharer.php"),
        ("x", "https://x.com/intent/post"),
        ("whatsapp", "https://wa.me/"),
        ("correo", "mailto:"),
    ],
)
def test_cada_red_usa_su_enlace_oficial_de_compartir(publicacion, red, dominio):
    fila = next(f for f in publicacion["difusion"] if f["clave"] == red)

    assert fila["compartir"].startswith(dominio)


def test_instagram_no_tiene_enlace_de_compartir_y_por_eso_lleva_copiar(publicacion):
    instagram = next(red for red in publicacion["difusion"] if red["clave"] == "instagram")

    assert instagram["compartir"] is None
    assert instagram["admite_texto"] is False


def test_linkedin_y_facebook_solo_se_llevan_el_enlace(publicacion):
    por_clave = {red["clave"]: red for red in publicacion["difusion"]}

    for clave in ("linkedin", "facebook"):
        assert por_clave[clave]["admite_texto"] is False
        # El texto no va en la dirección, así que el panel tiene que ofrecer «Copiar texto».
        assert "Buscamos" not in por_clave[clave]["compartir"]
        assert por_clave[clave]["aviso"]


def test_el_enlace_de_x_no_repite_el_enlace_dos_veces(publicacion):
    x = next(red for red in publicacion["difusion"] if red["clave"] == "x")

    # El enlace va dentro del texto; mandarlo además como `url` lo pondría dos veces y el
    # recorte a 280 dejaría de cuadrar.
    assert "url=" not in x["compartir"]
    assert x["compartir"].count("interes") == 1


def test_ningun_enlace_de_compartir_pide_clave_ni_cuenta(publicacion):
    """Sin API: son direcciones públicas que abren la red con la sesión de quien pulsa."""
    for red in publicacion["difusion"]:
        if red["compartir"]:
            assert "api" not in red["compartir"].lower()
            assert "token" not in red["compartir"].lower()
            assert "client_id" not in red["compartir"].lower()


def test_el_texto_para_linkedin_de_siempre_lleva_su_red(publicacion):
    """Sin `?r=linkedin`, la vía principal se contaría entera como «sin red»."""
    assert publicacion["texto_para_linkedin"].endswith(f"{publicacion['enlace_publico']}?r=linkedin")


# ==============================================================================
# 5. El modelo no conoce estas redes
# ==============================================================================

def test_ningun_canal_de_las_redes_lo_conoce_el_modelo():
    """
    Todos son categorías que el modelo no vio al entrenar, así que el preprocesador las
    descarta y cuentan como desconocidas: neutras. Escribir «LinkedIn Ads» para que sumaran
    sería declarar publicidad pagada donde hubo un post orgánico.
    """
    conocidas = set(CATEGORIAS_DEL_MODELO["source_channel"])

    for canal in r.CANALES_DE_PUBLICACION:
        assert canal not in conocidas


def test_un_prospecto_puntua_igual_venga_por_donde_venga(client, lead_headers, db_session):
    """Mismos datos y distinta red: el score no se mueve."""
    scores = []
    for indice, red in enumerate(("whatsapp", "facebook", "x", None)):
        creada = client.post(
            CAMPANAS, headers=lead_headers, json={"name": f"Post {indice}", "channel": CANAL_LINKEDIN}
        ).json()
        correo = f"mismo.perfil.{indice}@example.com"
        _enviar(client, creada, red=red, correo=correo)
        db_session.expire_all()
        scores.append(db_session.query(Lead).filter(Lead.email == correo).one().current_score)

    assert len(set(scores)) == 1, f"la red movió el score: {scores}"


# ==============================================================================
# 6. El informe
# ==============================================================================

def _informe(client, headers, publicacion):
    return client.get(f"/api/v1/publicaciones/{publicacion['id']}/informe", headers=headers).json()


def test_el_informe_trae_una_fila_por_red(client, lead_headers, publicacion):
    client.get(_pagina(publicacion, "whatsapp"))
    _enviar(client, publicacion, red="whatsapp")
    client.get(_pagina(publicacion, "facebook"))
    client.get(_pagina(publicacion, "facebook"))

    por_red = {fila["red"]: fila for fila in _informe(client, lead_headers, publicacion)["por_red"]}

    assert por_red["whatsapp"]["visitas"] == 1
    assert por_red["whatsapp"]["envios"] == 1
    assert por_red["whatsapp"]["perfiles"] == 1
    assert por_red["whatsapp"]["tasa_de_envio"] == 100.0
    assert por_red["whatsapp"]["score_medio"] > 0
    assert por_red["facebook"]["visitas"] == 2
    assert por_red["facebook"]["envios"] == 0
    assert por_red["facebook"]["tasa_de_envio"] == 0.0


def test_una_red_sin_visitas_no_tiene_tasa(client, lead_headers, publicacion):
    client.get(_pagina(publicacion, "whatsapp"))

    por_red = {fila["red"]: fila for fila in _informe(client, lead_headers, publicacion)["por_red"]}

    # Sin visitas no hay tasa: un 0 % diría que nadie escribió de los que miraron, y lo que
    # pasa es que no miró nadie.
    assert por_red["correo"]["visitas"] == 0
    assert por_red["correo"]["tasa_de_envio"] is None


def test_las_filas_llevan_la_etiqueta_que_se_lee(client, lead_headers, publicacion):
    client.get(_pagina(publicacion, "whatsapp"))

    etiquetas = {fila["red"]: fila["etiqueta"] for fila in _informe(client, lead_headers, publicacion)["por_red"]}

    assert etiquetas["whatsapp"] == "WhatsApp"
    assert etiquetas["linkedin"] == "LinkedIn"


def test_sin_red_sale_como_una_fila_mas(client, lead_headers, publicacion):
    client.get(_pagina(publicacion))
    _enviar(client, publicacion)

    por_red = {fila["red"]: fila for fila in _informe(client, lead_headers, publicacion)["por_red"]}

    assert por_red["sin_red"]["etiqueta"] == "Sin red"
    assert por_red["sin_red"]["envios"] == 1


def test_una_red_desactivada_que_trajo_algo_sigue_en_el_informe(client, lead_headers, publicacion):
    """Si se escondiera, las filas dejarían de sumar el total de la publicación."""
    client.get(_pagina(publicacion, "x"))
    client.put(f"{CAMPANAS}/{publicacion['id']}", headers=lead_headers, json={"redes": ["linkedin"]})

    por_red = {fila["red"]: fila for fila in _informe(client, lead_headers, publicacion)["por_red"]}

    assert por_red["x"]["visitas"] == 1


def test_un_asesor_ve_sus_perfiles_por_red_y_no_los_ajenos(
    client, lead_headers, executive_headers, publicacion, db_session, sales_reps
):
    """
    Las visitas son de la publicación —un contador agregado no sabe de carteras—, pero los
    perfiles y el score medio de cada fila son los que ve quien pregunta.
    """
    client.get(_pagina(publicacion, "whatsapp"))
    _enviar(client, publicacion, red="whatsapp")

    del_lider = {f["red"]: f for f in _informe(client, lead_headers, publicacion)["por_red"]}
    del_asesor = {f["red"]: f for f in _informe(client, executive_headers, publicacion)["por_red"]}

    assert del_lider["whatsapp"]["perfiles"] == 1
    assert del_asesor["whatsapp"]["visitas"] == 1
    assert del_asesor["whatsapp"]["perfiles"] == 0


def test_el_grafico_por_dia_suma_las_visitas_de_todas_las_redes(client, lead_headers, publicacion):
    """Sin sumar, el gráfico enseñaría solo la última red de cada día."""
    client.get(_pagina(publicacion, "whatsapp"))
    client.get(_pagina(publicacion, "facebook"))
    client.get(_pagina(publicacion))

    dias = _informe(client, lead_headers, publicacion)["por_dia"]

    assert sum(dia["visitas"] for dia in dias) == 3


def test_el_contador_de_sin_asesor_cuenta_todos_los_canales(client, publicacion, db_session):
    """
    Con el filtro de antes —solo «LinkedIn»— el líder habría dejado de ver a casi todos los
    que están esperando justo cuando empezaron a llegar por más sitios.
    """
    _enviar(client, publicacion, red="whatsapp", correo="uno@example.com")
    _enviar(client, publicacion, red="facebook", correo="dos@example.com")
    _enviar(client, publicacion, correo="tres@example.com")

    assert informes.nuevos_sin_asesor(db_session) == 3


# ==============================================================================
# 7. Los permisos, como estaban
# ==============================================================================

def test_un_asesor_no_cambia_las_redes(client, executive_headers, publicacion):
    respuesta = client.put(
        f"{CAMPANAS}/{publicacion['id']}", headers=executive_headers, json={"redes": ["x"]}
    )

    assert respuesta.status_code == 403


def test_un_asesor_si_ve_los_textos_para_compartir(client, executive_headers, publicacion):
    datos = client.get(f"{CAMPANAS}?canal={CANAL_LINKEDIN}", headers=executive_headers).json()

    assert datos["items"][0]["difusion"]


# ==============================================================================
# El núcleo, en corto
# ==============================================================================

@pytest.mark.parametrize(
    "valor,esperado",
    [
        ("whatsapp", "whatsapp"),
        ("WhatsApp", "whatsapp"),
        ("  x  ", "x"),
        ("tiktok", None),
        ("", None),
        (None, None),
        ("whatsapp; DROP TABLE", None),
        ("w" * 500, None),
    ],
)
def test_normalizar_red_de_llegada(valor, esperado):
    assert r.normalizar_red_de_llegada(valor) == esperado


def test_registrar_visita_exige_nombrar_la_red_y_el_dia(db_session, publicacion):
    """
    Antes del capítulo 27 el tercer argumento era el día. Si `red` se hubiera colado
    delante como posicional, una llamada antigua habría contado visitas de una red llamada
    «2026-09-21», sin error y sin que nada lo dijera.
    """
    campana = db_session.query(Campaign).filter(Campaign.id == publicacion["id"]).one()

    with pytest.raises(TypeError):
        ciclo.registrar_visita(db_session, campana, datetime.date.today())
