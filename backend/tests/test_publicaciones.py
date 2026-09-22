"""
Publicaciones: campañas con canal LinkedIn, su enlace público y quién puede tocarlas.

Una publicación no es una entidad propia (regla R-2 del guion «Del post de LinkedIn al
prospecto puntuado»): se crea y se lee por `/api/v1/campaigns` con `channel=LinkedIn`.
Lo que se comprueba aquí:

* El enlace no se puede adivinar ni reutilizar. Lo genera el servidor, ningún cliente lo
  elige ni lo cambia, y la base no admite dos iguales.
* El texto para LinkedIn lleva la descripción y el enlace, y cabe en un post.
* Crean y editan el líder y el administrador; el asesor solo consulta.
"""
import os
import re

import pytest
from app.core.config import Settings, settings
from app.core.publicaciones import (
    CANAL_LINKEDIN,
    LONGITUD_DEL_SLUG,
    MAX_DESCRIPCION,
    MAX_TEXTO_DE_LINKEDIN,
    nuevo_slug_publico,
)
from app.models.entities import AuditLog, Campaign
from sqlalchemy.exc import IntegrityError

RAIZ_DEL_PROYECTO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

CAMPANAS = "/api/v1/campaigns"
PATRON_DEL_SLUG = re.compile(rf"^[A-Za-z0-9_-]{{{LONGITUD_DEL_SLUG}}}$")

DESCRIPCION = (
    "¿Tu equipo de TI tarda meses en cubrir una vacante? Te contamos cómo lo resolvimos "
    "para tres empresas de Monterrey."
)


def _publicar(client, headers, **extra):
    cuerpo = {
        "name": "Post · Talento TI septiembre",
        "channel": CANAL_LINKEDIN,
        "description": DESCRIPCION,
        "target_audience": "Directores de TI de empresas de 200 a 1000 empleados",
    }
    cuerpo.update(extra)
    return client.post(CAMPANAS, headers=headers, json=cuerpo)


# ==============================================================================
# El enlace público
# ==============================================================================

def test_el_servidor_genera_el_slug_al_crear(client, lead_headers):
    publicacion = _publicar(client, lead_headers).json()
    assert PATRON_DEL_SLUG.match(publicacion["public_slug"])


def test_el_slug_no_sale_del_nombre_ni_del_id(client, lead_headers):
    """Si saliera, bastaría probar números o títulos para encontrar publicaciones ajenas."""
    publicacion = _publicar(client, lead_headers, name="talento-ti").json()
    slug = publicacion["public_slug"].lower()
    assert "talento" not in slug
    assert slug != str(publicacion["id"])


def test_dos_publicaciones_nunca_comparten_slug(client, lead_headers):
    slugs = {
        _publicar(client, lead_headers, name=f"Post {i}").json()["public_slug"] for i in range(25)
    }
    assert len(slugs) == 25


def test_el_generador_tiene_128_bits_de_azar():
    """22 caracteres de base64 URL son 132 bits de capacidad: los 16 bytes caben enteros."""
    muestras = {nuevo_slug_publico() for _ in range(2000)}
    assert len(muestras) == 2000
    assert all(PATRON_DEL_SLUG.match(s) for s in muestras)


def test_el_cliente_no_elige_el_slug_al_crear(client, lead_headers):
    publicacion = _publicar(client, lead_headers, public_slug="mi-enlace-bonito").json()
    assert publicacion["public_slug"] != "mi-enlace-bonito"
    assert PATRON_DEL_SLUG.match(publicacion["public_slug"])


def test_ninguna_edicion_cambia_el_slug(client, lead_headers):
    """Un enlace ya pegado en LinkedIn tiene que seguir apuntando a la misma publicación."""
    publicacion = _publicar(client, lead_headers).json()
    ruta = f"{CAMPANAS}/{publicacion['id']}"

    client.put(ruta, headers=lead_headers, json={"public_slug": "otro", "name": "Nuevo título"})
    client.put(ruta, headers=lead_headers, json={"description": "Otro texto"})
    client.delete(ruta, headers=lead_headers)
    reactivada = client.put(ruta, headers=lead_headers, json={"is_active": True}).json()

    assert reactivada["public_slug"] == publicacion["public_slug"]
    assert reactivada["name"] == "Nuevo título"
    assert reactivada["is_active"] is True


def test_la_base_rechaza_un_slug_repetido(db_session, campaigns):
    """
    Aunque un camino futuro escribiera el slug a mano, la base no deja que dos campañas lo
    compartan: una desactivada conserva el suyo y ninguna nueva puede heredarlo.
    """
    campaigns[1].is_active = False
    db_session.commit()
    db_session.add(Campaign(name="Copia", channel=CANAL_LINKEDIN, public_slug=campaigns[1].public_slug))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_las_campanas_sin_slug_explicito_tambien_lo_reciben(campaigns):
    """El fixture y el sembrado crean campañas sin pensar en el enlace: el modelo lo pone."""
    assert all(PATRON_DEL_SLUG.match(c.public_slug) for c in campaigns)
    assert campaigns[0].public_slug != campaigns[1].public_slug


# ==============================================================================
# Texto para LinkedIn
# ==============================================================================

def test_el_texto_lleva_la_descripcion_y_el_enlace(client, lead_headers, monkeypatch):
    monkeypatch.setattr(settings, "PUBLICACIONES_URL_BASE", "https://plurione.com/p")
    publicacion = _publicar(client, lead_headers).json()

    enlace = f"https://plurione.com/p/{publicacion['public_slug']}"
    assert publicacion["enlace_publico"] == enlace
    assert publicacion["texto_para_linkedin"] == f"{DESCRIPCION}\n\n{enlace}"


def test_sin_descripcion_el_texto_es_solo_el_enlace(client, lead_headers):
    publicacion = _publicar(client, lead_headers, description=None).json()
    assert publicacion["texto_para_linkedin"] == publicacion["enlace_publico"]


def test_la_descripcion_mas_larga_cabe_en_un_post(client, lead_headers):
    publicacion = _publicar(client, lead_headers, description="x" * MAX_DESCRIPCION)
    assert publicacion.status_code == 201
    assert len(publicacion.json()["texto_para_linkedin"]) <= MAX_TEXTO_DE_LINKEDIN


def test_una_descripcion_que_no_cabe_se_rechaza(client, lead_headers):
    assert _publicar(client, lead_headers, description="x" * (MAX_DESCRIPCION + 1)).status_code == 422


def test_el_publico_se_guarda_y_se_edita(client, lead_headers):
    publicacion = _publicar(client, lead_headers).json()
    editada = client.put(
        f"{CAMPANAS}/{publicacion['id']}",
        headers=lead_headers,
        json={"target_audience": "Líderes de talento"},
    ).json()
    assert editada["target_audience"] == "Líderes de talento"
    assert editada["description"] == DESCRIPCION


def test_el_listado_filtra_las_publicaciones_por_canal(client, lead_headers, campaigns):
    _publicar(client, lead_headers)
    listado = client.get(
        CAMPANAS, params={"canal": CANAL_LINKEDIN, "incluir_inactivas": True}, headers=lead_headers
    ).json()
    # El fixture trae una campaña «LinkedIn Ads»: es publicidad pagada, no una publicación.
    assert listado["total"] == 1
    assert {c["channel"] for c in listado["items"]} == {CANAL_LINKEDIN}


@pytest.mark.parametrize(
    "valor",
    ["ftp://plurione.com/p", "plurione.com/p", "https://plurione.com/p?x=1", "https:///p"],
)
def test_una_url_base_mal_escrita_no_arranca(valor):
    with pytest.raises(ValueError, match="PUBLICACIONES_URL_BASE"):
        Settings(PUBLICACIONES_URL_BASE=valor)


def test_la_url_base_se_guarda_sin_barra_final():
    assert Settings(PUBLICACIONES_URL_BASE="https://plurione.com/p/").PUBLICACIONES_URL_BASE == (
        "https://plurione.com/p"
    )


# ==============================================================================
# Permisos
# ==============================================================================

@pytest.mark.parametrize("rol", ["Sales_Lead", "System_Admin"])
def test_el_lider_y_el_administrador_crean_y_editan(client, auth_headers, rol):
    headers = auth_headers(rol)
    creada = _publicar(client, headers, name=f"Post de {rol}")
    assert creada.status_code == 201
    ruta = f"{CAMPANAS}/{creada.json()['id']}"

    assert client.put(ruta, headers=headers, json={"description": "Nuevo texto"}).status_code == 200
    assert client.delete(ruta, headers=headers).status_code == 200
    assert client.put(ruta, headers=headers, json={"is_active": True}).status_code == 200


def test_el_asesor_consulta_las_publicaciones(client, lead_headers, executive_headers):
    creada = _publicar(client, lead_headers).json()

    listado = client.get(CAMPANAS, params={"canal": CANAL_LINKEDIN}, headers=executive_headers)
    assert listado.status_code == 200
    visto = listado.json()["items"][0]
    assert visto["texto_para_linkedin"] == creada["texto_para_linkedin"]

    detalle = client.get(f"{CAMPANAS}/{creada['id']}", headers=executive_headers)
    assert detalle.status_code == 200


def test_el_asesor_no_crea_edita_activa_ni_desactiva(client, lead_headers, executive_headers, db_session):
    creada = _publicar(client, lead_headers).json()
    ruta = f"{CAMPANAS}/{creada['id']}"

    assert _publicar(client, executive_headers).status_code == 403
    assert client.put(ruta, headers=executive_headers, json={"description": "cambio"}).status_code == 403
    assert client.delete(ruta, headers=executive_headers).status_code == 403
    client.delete(ruta, headers=lead_headers)
    assert client.put(ruta, headers=executive_headers, json={"is_active": True}).status_code == 403

    db_session.expire_all()
    guardada = db_session.query(Campaign).filter(Campaign.id == creada["id"]).one()
    assert guardada.description == DESCRIPCION
    assert guardada.is_active is False
    assert db_session.query(Campaign).count() == 1
    denegaciones = db_session.query(AuditLog).filter(AuditLog.action == "acceso.denegado").count()
    assert denegaciones == 4


def test_el_enlace_por_defecto_lleva_a_la_pagina_y_no_a_la_pantalla_de_acceso():
    """
    El último segmento de la dirección por defecto tiene que ser la ruta que el panel
    reconoce como pública.

    Estuvo en `/p` mientras la página se servía en `/interes/<slug>`: escribiendo la
    dirección a mano todo funcionaba, y el texto copiado para LinkedIn llevaba a la
    pantalla de acceso. Un enlace ya publicado no se puede corregir, así que el desajuste
    se comprueba aquí, contra la ruta de verdad y no contra una copia.
    """
    ruta = os.path.join(RAIZ_DEL_PROYECTO, "frontend", "src", "main.jsx")
    fuente = open(ruta, encoding="utf-8").read()
    regla = re.search(r"RUTA_DE_INTERES\s*=\s*/\^\\/([A-Za-z0-9_-]+)\\/", fuente)
    assert regla, "No se pudo leer la ruta pública de frontend/src/main.jsx."

    base = Settings().PUBLICACIONES_URL_BASE
    assert base.rsplit("/", 1)[-1] == regla.group(1)
