"""
Capítulo 32: lo último que la ficha seguía suponiendo.

El capítulo 24 quitó los ceros de ingresos y el 25 los tamaños de empresa inventados, y los
dos dejaron el mismo rastro: el código dejó de escribirlos y las filas que ya existían se
quedaron como estaban. El país fue más lejos todavía, porque la suposición no vivía en un
servicio sino en la **columna**: `country` era `NOT NULL` con «México» por defecto, así que
no hacía falta que nadie escribiera nada para que toda ficha saliera con país.

Las tres cosas que se comprueban aquí tienen la misma forma —en la base hay un valor donde
no hubo un dato— y la misma consecuencia: seis meses después nadie puede distinguir lo que
alguien declaró de lo que rellenó la ausencia de alguien.

Qué NO se comprueba, y por qué
-------------------------------
Que el país no puntúe. No hace falta una prueba nueva: `country` no está en
`COLUMNAS_DEL_MODELO` ni lo mira `calculate_heuristic_score`, y eso ya lo vigilan
`test_categorias_del_modelo` y la guarda del vector. Lo que se arregla aquí no es una
predicción, es lo que la ficha AFIRMA de una persona.
"""
import pytest
from app.core.telefono import validador_de_telefono
from app.models.entities import Lead, User
from app.schemas.lead import LeadBase, LeadCreate, LeadUpdate
from app.schemas.user import UsuarioCreate, UsuarioUpdate
from pydantic import ValidationError

LEADS = "/api/v1/leads"
USUARIOS = "/api/v1/users"

FICHA_MINIMA = {
    "first_name": "Sofía",
    "last_name": "Ramos",
    "email": "sofia.sin.pais@example.com",
    "company": "Ejemplo SA",
}


# ==============================================================================
# El país: la columna, el esquema y el alta del registro de actividad
# ==============================================================================

def test_el_esquema_no_rellena_el_pais_que_no_llega():
    """El defecto vivía aquí: `country: str = Field("México")`."""
    assert LeadBase.model_fields["country"].default is None
    assert LeadCreate(**FICHA_MINIMA).country is None


def test_la_columna_admite_vacio():
    assert Lead.__table__.c.country.nullable is True
    assert Lead.__table__.c.country.default is None


def test_quitar_el_pais_no_toca_el_score_ni_el_vector_del_modelo():
    """
    La condición que hizo barato este cambio, fijada por escrito.

    Si el país puntuara, vaciarlo en las fichas de la página de interés habría movido sus
    scores, y el capítulo habría pasado de corregir una afirmación falsa a cambiar lo que el
    sistema recomienda hacer. No es el caso, y conviene que romperlo cueste una prueba roja:
    no está en el vector del modelo —la versión sigue siendo la 2— ni lo mira la regla.
    """
    import inspect

    from app.core import scoring_rules
    from app.core.vector_del_modelo import COLUMNAS_DEL_MODELO, VERSION_DEL_VECTOR

    assert "country" not in COLUMNAS_DEL_MODELO
    assert VERSION_DEL_VECTOR == 2
    assert "country" not in inspect.getsource(scoring_rules)


def test_un_alta_sin_pais_deja_la_ficha_sin_pais(client, lead_headers, db_session):
    respuesta = client.post(LEADS, headers=lead_headers, json=FICHA_MINIMA)

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["country"] is None
    ficha = db_session.query(Lead).filter(Lead.email == FICHA_MINIMA["email"]).one()
    assert ficha.country is None


def test_un_alta_con_pais_lo_conserva(client, lead_headers):
    respuesta = client.post(
        LEADS,
        headers=lead_headers,
        json={**FICHA_MINIMA, "email": "sofia.con.pais@example.com", "country": "Colombia"},
    )

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["country"] == "Colombia"


@pytest.mark.parametrize("en_blanco", ["", "   "])
def test_un_pais_en_blanco_es_ausencia_de_pais_y_no_una_cadena_vacia(en_blanco):
    """
    Dos formas de decir lo mismo en la misma columna serían peor que una suposición: cada
    consulta posterior tendría que acordarse de las dos. El formulario del panel manda `""`
    cuando el campo se deja sin rellenar.
    """
    assert LeadCreate(**FICHA_MINIMA, country=en_blanco).country is None
    assert LeadUpdate(country=en_blanco).country is None


def test_un_pais_ya_escrito_no_se_puede_vaciar_desde_la_edicion(client, lead_headers):
    """
    El límite de este capítulo, fijado por escrito para que se vea.

    Las fichas que la migración no toca —las del panel, las del CRM— siguen diciendo
    «México» porque no consta si alguien lo eligió. Un asesor que sepa que esa persona no
    está en México **no puede dejar el campo vacío**: la actualización parcial del
    repositorio aplica `if value is not None`, así que un `null` explícito se ignora. Y no
    es del país: **ningún campo de la ficha se puede vaciar** una vez escrito. Se puede
    cambiar por otro valor, no borrar.

    No se corrige aquí a propósito. Cambiar esa línea altera el comportamiento de todos los
    campos a la vez —el cliente manda `null` en varios cuando el formulario los deja en
    blanco—, y eso es una decisión de diseño con su propia discusión, no una corrección de
    este capítulo. Queda anotado en §6 de `docs/Congelacion_y_Trabajo_Futuro.md`.

    Esta prueba comprueba lo que el sistema HACE, no lo que convendría que hiciera. Si algún
    día se corrige, esta prueba falla y obliga a decidirlo en lugar de descubrirlo.
    """
    correo = "corregible@example.com"
    creada = client.post(
        LEADS, headers=lead_headers, json={**FICHA_MINIMA, "email": correo, "country": "México"}
    )
    assert creada.status_code == 201, creada.text

    actualizada = client.put(
        f"{LEADS}/{creada.json()['id']}", headers=lead_headers, json={"country": None}
    )

    assert actualizada.status_code == 200, actualizada.text
    assert actualizada.json()["country"] == "México"
    # Cambiarlo por otro país sí funciona: lo que no hay es forma de dejarlo vacío.
    cambiada = client.put(
        f"{LEADS}/{creada.json()['id']}", headers=lead_headers, json={"country": "Perú"}
    )
    assert cambiada.json()["country"] == "Perú"


def test_la_pagina_de_interes_no_manda_pais():
    """
    Su formulario no lo pregunta. Mientras la columna tenía valor por defecto, eso producía
    fichas CON país sin que nadie lo hubiera indicado, y es el único conjunto del que se
    puede demostrar que la suposición fue suposición: por eso la migración de datos vacía
    exactamente esas fichas y ninguna otra.
    """
    from app.schemas.interes import SolicitudDeInteres

    assert "pais" not in SolicitudDeInteres.model_fields
    assert "country" not in SolicitudDeInteres.model_fields


def test_una_ficha_creada_por_la_pagina_de_interes_no_tiene_pais(client, lead_headers, db_session):
    publicacion = client.post(
        "/api/v1/campaigns",
        headers=lead_headers,
        json={"name": "Post · Sin país", "channel": "LinkedIn"},
    ).json()

    respuesta = client.post(
        f"/api/v1/interes/{publicacion['public_slug']}",
        json={
            "nombre": "Marta Sin País",
            "correo": "marta.sin.pais@example.com",
            "empresa": "Ejemplo SA",
            "cargo": "CTO",
            "sector": "FinTech",
            "tamano_de_empresa": "201-1000",
            "necesidad": "vacantes",
            "aviso_de_privacidad": True,
            "sitio_web": "",
        },
    )

    # 202: la página acepta y responde lo mismo exista o no el correo (capítulo 26).
    assert respuesta.status_code == 202, respuesta.text
    db_session.expire_all()
    ficha = db_session.query(Lead).filter(Lead.email == "marta.sin.pais@example.com").one()
    assert ficha.country is None


# ==============================================================================
# El teléfono de los asesores
# ==============================================================================

def test_el_telefono_de_un_asesor_se_normaliza_como_el_de_un_prospecto():
    """Mismo módulo, misma forma. Hasta el capítulo 32 `users.phone` era texto libre."""
    assert UsuarioCreate(
        email="nueva.asesora@plurione.com",
        full_name="Nueva Asesora",
        role="Commercial_Executive",
        password="Una-Frase-Larga-Y-Propia",
        phone="55 9876 5432",
    ).phone == "+525598765432"
    assert UsuarioUpdate(phone="+52 1 55 9876 5432").phone == "+525598765432"


def test_un_telefono_de_asesor_que_no_es_un_numero_se_rechaza_al_guardarlo():
    with pytest.raises(ValidationError) as fallo:
        UsuarioUpdate(phone="pregúntale a Luis")
    assert "phone" in str(fallo.value)
    # Y el mensaje NO repite el número: acaba en la respuesta y puede acabar en un registro.
    assert "pregúntale a Luis" not in str(fallo.value.errors()[0]["msg"])


def test_el_alta_de_una_cuenta_guarda_el_telefono_en_e164(client, admin_headers, db_session):
    respuesta = client.post(
        USUARIOS,
        headers=admin_headers,
        json={
            "email": "asesor.e164@plurione.com",
            "full_name": "Asesor E164",
            "role": "Commercial_Executive",
            "password": "Una-Frase-Larga-Y-Propia-2026",
            "is_sales_rep": True,
            "phone": "(55) 1234-5678",
        },
    )

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["phone"] == "+525512345678"
    cuenta = db_session.query(User).filter(User.email == "asesor.e164@plurione.com").one()
    assert cuenta.phone == "+525512345678"


def test_los_dos_esquemas_comparten_la_misma_definicion():
    """
    Dos copias de la normalización se habrían desincronizado el día que alguien subiera una:
    el capítulo 21 normalizó el teléfono de los prospectos y el de los asesores se quedó
    atrás precisamente porque eran caminos distintos.
    """
    from app.schemas import lead as esquema_de_prospectos

    assert esquema_de_prospectos._telefono_e164 is validador_de_telefono


# ==============================================================================
# Los ceros de ingresos
# ==============================================================================

def test_unos_ingresos_que_no_se_indicaron_no_son_cero():
    """Ya era así desde el capítulo 24; se fija para que no vuelva."""
    assert LeadCreate(**FICHA_MINIMA).annual_revenue is None


def test_la_migracion_de_los_ceros_existentes_esta_escrita():
    """
    Lo que el capítulo 24 no hizo: los ceros que YA estaban en la base. El extractor los
    leía como ausentes —`ingresos_o_ausente` descarta `<= 0`—, así que el modelo nunca los
    creyó; quien sí los creía era la ficha, que los enseñaba como «0».
    """
    import pathlib

    migraciones = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions"
    texto = (migraciones / "a4c8d1e70f39_el_pais_deja_de_suponerse_telefonos_de_.py").read_text(
        encoding="utf-8"
    )
    assert "UPDATE leads SET annual_revenue = NULL WHERE annual_revenue = 0" in texto
