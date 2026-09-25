"""
Capítulo 33: vaciar un campo es un cambio, no la ausencia de uno.

El defecto era una línea del repositorio, `if value is not None`, y su tamaño no se ve en
la línea. `model_dump(exclude_unset=True)` ya distinguía perfectamente «el cliente no mandó
este campo» de «el cliente mandó este campo a nulo» —la primera no aparece en el diccionario
y la segunda sí, con valor `None`—, y el bucle volvía a mezclar las dos tirando cualquier
valor nulo. El `exclude_unset` era decoración: costaba lo mismo hacer `model_dump()` a secas.

Lo que producía no era «no se puede vaciar un campo», que sería un límite. Era peor:
vaciarlo respondía **200 con la ficha entera**, que es una respuesta afirmativa. Quien
borrara el país de una ficha veía «Prospecto actualizado y rescoreado dinámicamente», y el
país seguía ahí al volver a abrirla. Un sistema que no puede hacer algo y lo dice es un
sistema con un límite; uno que dice que lo hizo es un sistema que miente.

Lo encontró el capítulo 32 y lo dejó anotado como punto 24 de §6.1, con una prueba de
fijación, porque el arreglo toca **todos** los campos a la vez y eso había que decidirlo,
no descubrirlo.

Las dos mitades del arreglo
---------------------------
1. El repositorio aplica lo que vino, incluido lo que vino vacío.
2. `LeadUpdate` rechaza con 422 el vacío sobre un campo que la tabla declara `NOT NULL`, y
   la lista de esos campos **se deriva de la tabla**. Escribirla a mano habría acertado hoy
   y habría callado el día que una migración cambiara un `nullable`.

Qué NO se comprueba aquí, y por qué
-----------------------------------
Que el alta (`LeadCreate`) normalice los textos en blanco. No se ha tocado: este capítulo es
sobre la actualización parcial, que es donde vivía el fallo. Queda dicho en el reporte.
"""
import pytest
from app.core.scoring_rules import UNKNOWN_TITLE_POINTS
from app.models.entities import AuditLog, Lead
from app.schemas.lead import CAMPOS_QUE_NO_ADMITEN_VACIO, LeadUpdate
from app.services.scoring_service import ScoringService
from pydantic import ValidationError

LEADS = "/api/v1/leads"

FICHA_COMPLETA = {
    "first_name": "Valeria",
    "last_name": "Ochoa",
    "email": "valeria.ochoa@example.com",
    "phone": "+525512345678",
    "company": "Constructora del Norte",
    "job_title": "CTO",
    "industry": "Tecnología",
    "company_size": "51-200",
    "annual_revenue": 4500000.0,
    "country": "México",
    "city": "Monterrey",
}


@pytest.fixture
def ficha(client, lead_headers):
    """Una ficha con todos los campos escritos, para poder borrarlos de uno en uno."""
    respuesta = client.post(LEADS, headers=lead_headers, json=FICHA_COMPLETA)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _editar(client, lead_headers, lead_id, cuerpo):
    return client.put(f"{LEADS}/{lead_id}", headers=lead_headers, json=cuerpo)


# ==============================================================================
# 1. Vaciar uno que se puede
# ==============================================================================

@pytest.mark.parametrize(
    "campo",
    ["phone", "company", "job_title", "industry", "company_size", "country", "city"],
)
def test_un_campo_que_admite_vacio_se_vacia(client, lead_headers, ficha, campo):
    """
    El caso central del capítulo, uno por cada campo de texto que la tabla deja vacío.

    Se comprueba en la respuesta y **releyendo la ficha**, que no es lo mismo: la respuesta
    la construye el endpoint a partir del objeto que acaba de tocar, y podría enseñar un
    vacío que no llegó a la base. Releer obliga a que el cambio haya pasado por el commit.
    """
    respuesta = _editar(client, lead_headers, ficha["id"], {campo: None})

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()[campo] is None

    releida = client.get(f"{LEADS}/{ficha['id']}", headers=lead_headers)
    assert releida.json()[campo] is None


def test_la_cadena_vacia_y_el_nulo_son_el_mismo_vacio(client, lead_headers, ficha):
    """
    Un solo vacío en la base, no dos.

    El formulario del panel manda `""` en los campos de texto y `null` en los que pasan por
    un conversor. Si cada forma dejara una cosa distinta —`''` y `NULL`— la misma pantalla
    produciría dos representaciones del mismo hecho, y cualquier consulta posterior tendría
    que acordarse de las dos. Es el motivo por el que el capítulo 32 escribió esta regla
    para el país; aquí se extiende al resto del texto de la edición.
    """
    respuesta = _editar(client, lead_headers, ficha["id"], {"city": "", "company": "   "})

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["city"] is None
    assert respuesta.json()["company"] is None


def test_vaciar_el_asesor_asignado_deja_el_prospecto_sin_dueno(
    client, lead_headers, sales_reps, ficha
):
    """
    `assigned_rep_id` también admite vacío, y su vacío significa algo concreto.

    Es el estado en el que nacen los prospectos que llegan por una publicación: sin asesor,
    esperando a que alguien los tome, y es lo que cuenta el contador del líder. Que se pueda
    volver a él importa porque una asignación equivocada solo se podía **sustituir por
    otra**, nunca deshacer: el prospecto quedaba atribuido a alguien para siempre.

    Se asigna primero y se retira después, en dos llamadas, porque un prospecto que ya nació
    sin asesor no demostraría nada. Con credenciales de líder: retirar el dueño de un
    prospecto es repartir trabajo, así que pasa por la misma guarda que reasignar.
    """
    asignada = _editar(client, lead_headers, ficha["id"], {"assigned_rep_id": sales_reps[0].id})
    assert asignada.status_code == 200, asignada.text
    assert asignada.json()["assigned_rep_id"] == sales_reps[0].id

    retirada = _editar(client, lead_headers, ficha["id"], {"assigned_rep_id": None})

    assert retirada.status_code == 200, retirada.text
    assert retirada.json()["assigned_rep_id"] is None


# ==============================================================================
# 2. Rechazar uno que no se puede, y decir por qué
# ==============================================================================

@pytest.mark.parametrize("campo", ["first_name", "last_name", "email", "source", "status"])
def test_un_campo_obligatorio_no_se_vacia_y_responde_422(client, lead_headers, ficha, campo):
    """
    422 con el motivo, nunca 200 fingiendo que obedeció.

    La respuesta tiene que nombrar el campo: el asesor que acaba de borrar el apellido
    necesita saber cuál de los que tocó fue el que no se admitió, y un 422 genérico en un
    formulario de doce campos no se lo dice.
    """
    respuesta = _editar(client, lead_headers, ficha["id"], {campo: None})

    assert respuesta.status_code == 422, respuesta.text
    assert campo in respuesta.text

    intacta = client.get(f"{LEADS}/{ficha['id']}", headers=lead_headers)
    assert intacta.json()[campo] == ficha[campo]


def test_el_rechazo_no_deja_a_medias_el_resto_del_cuerpo(client, lead_headers, ficha):
    """
    Un cuerpo con un vacío prohibido no escribe **nada**, ni siquiera lo que sí era válido.

    Lo da gratis la validación del esquema, que ocurre antes del endpoint, pero conviene
    fijarlo: un arreglo que validara campo a campo dentro del bucle habría dejado la ficha a
    medias —la ciudad vaciada, el apellido no— y eso es peor que rechazarlo entero, porque
    el 422 haría pensar que no se guardó nada.
    """
    respuesta = _editar(
        client, lead_headers, ficha["id"], {"city": None, "first_name": None}
    )

    assert respuesta.status_code == 422, respuesta.text
    intacta = client.get(f"{LEADS}/{ficha['id']}", headers=lead_headers)
    assert intacta.json()["city"] == FICHA_COMPLETA["city"]


def test_la_lista_de_obligatorios_sale_de_la_tabla_y_no_de_una_copia():
    """
    La mitad que evita que este arreglo caduque.

    Si la lista fuera literal, seguiría siendo correcta hoy y se quedaría atrás en la primera
    migración que cambiara un `nullable`, en silencio y con el fallo apareciendo meses
    después. Se comprueba contra los dos extremos conocidos —lo que la tabla exige y lo que
    la tabla deja vacío— y contra la propia declaración de las columnas, que es la fuente.
    """
    esperados = {c.name for c in Lead.__table__.columns if not c.nullable}
    assert CAMPOS_QUE_NO_ADMITEN_VACIO == esperados

    assert {"first_name", "last_name", "email", "source", "status"} <= CAMPOS_QUE_NO_ADMITEN_VACIO
    assert not ({"country", "city", "phone", "annual_revenue"} & CAMPOS_QUE_NO_ADMITEN_VACIO)


def test_el_esquema_rechaza_el_vacio_prohibido_antes_de_tocar_la_base():
    """El 422 nace en `LeadUpdate`, así que se puede comprobar sin cliente ni base."""
    with pytest.raises(ValidationError) as error:
        LeadUpdate(first_name=None)
    assert "first_name" in str(error.value)

    # Y no se dispara por un campo simplemente ausente, que es el caso normal.
    assert LeadUpdate(city="Puebla").first_name is None


# ==============================================================================
# 3. No mandarlo y que no cambie
# ==============================================================================

def test_lo_que_no_se_manda_no_se_toca(client, lead_headers, ficha):
    """
    La otra mitad de la distinción, y la que era fácil romper al arreglar la primera.

    Un arreglo apresurado —usar `model_dump()` sin `exclude_unset`— habría hecho que cada
    edición vaciara todos los campos que el formulario no incluyera. El fallo simétrico del
    que se corrige, y mucho más destructivo.
    """
    respuesta = _editar(client, lead_headers, ficha["id"], {"city": "Guadalajara"})

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["city"] == "Guadalajara"
    for campo in ("phone", "company", "job_title", "industry", "company_size", "country"):
        assert cuerpo[campo] == FICHA_COMPLETA[campo], campo
    assert cuerpo["annual_revenue"] == FICHA_COMPLETA["annual_revenue"]


# ==============================================================================
# 4. Los ingresos vaciados llegan al modelo como ausentes
# ==============================================================================

def test_vaciar_los_ingresos_los_deja_ausentes_para_el_modelo(
    client, lead_headers, db_session, ficha
):
    """
    Vaciar no puede significar cero: el capítulo 24 existe entero por esa diferencia.

    Un cero en `annual_revenue` es una cifra —dice que la empresa factura cero— y el modelo
    lo leería como tal. Ausente es ausente: el codificador lo imputa y sabe que faltaba. Se
    comprueba en la columna y en el vector, porque son dos sitios donde el cero podía
    colarse y solo el segundo llega al modelo.
    """
    respuesta = _editar(client, lead_headers, ficha["id"], {"annual_revenue": None})
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["annual_revenue"] is None

    lead = db_session.query(Lead).filter(Lead.id == ficha["id"]).one()
    assert lead.annual_revenue is None

    features = ScoringService(db_session).extract_features_from_lead(lead)
    assert features["annual_revenue"] is None


# ==============================================================================
# 5. Vaciar un campo que puntúa recalcula el score
# ==============================================================================

def test_vaciar_un_campo_que_puntua_recalcula_el_score(client, lead_headers, ficha):
    """
    Vaciar es un cambio de la ficha, así que tiene que mover lo que la ficha produce.

    `job_title` puntúa en las dos mitades del score. «CTO» es un cargo de decisión y suma lo
    alto de su bloque; sin cargo, la regla no supone uno: aplica `UNKNOWN_TITLE_POINTS`, el
    punto medio. Lo que se comprueba no es el número —eso lo hacen las pruebas del
    heurístico— sino que el recálculo **ocurrió**: un arreglo que escribiera la columna sin
    pasar por el scoring habría dejado la ficha diciendo una cosa y su score otra.
    """
    assert UNKNOWN_TITLE_POINTS > 0  # si el desconocido valiera cero, la prueba no distinguiría

    antes = ficha["current_score"]
    respuesta = _editar(client, lead_headers, ficha["id"], {"job_title": None})

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["job_title"] is None
    assert respuesta.json()["current_score"] != antes


# ==============================================================================
# 6. La bitácora distingue lo vaciado, sin copiar valores
# ==============================================================================

def test_la_bitacora_distingue_los_campos_vaciados(client, lead_headers, db_session, ficha):
    """
    Borrar el dato de una persona y corregirlo no son la misma acción ante quien pida cuentas.

    Se anotan **nombres de campo**, nunca valores: la bitácora se consulta con otro criterio
    de acceso que la tabla de negocio, y copiar allí un teléfono o un correo los duplicaría
    fuera del alcance que los protege (R-11). Por eso la comprobación de que el valor no está
    va explícita y no de adorno.
    """
    respuesta = _editar(
        client, lead_headers, ficha["id"], {"city": None, "company": "Otra Constructora"}
    )
    assert respuesta.status_code == 200, respuesta.text

    asiento = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "lead.actualizar")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert asiento is not None
    assert asiento.event_metadata["campos"] == ["city", "company"]
    assert asiento.event_metadata["campos_vaciados"] == ["city"]
    assert "Otra Constructora" not in str(asiento.event_metadata)


def test_una_edicion_sin_vaciados_lo_dice_con_una_lista_vacia(
    client, lead_headers, db_session, ficha
):
    """
    La clave está siempre, aunque no se haya vaciado nada.

    Es lo que permite preguntar «qué ediciones borraron datos» con un solo criterio. Si solo
    apareciera cuando hay vaciados, la ausencia de la clave significaría dos cosas a la vez:
    una edición que no vació nada, y una edición anterior al capítulo 33.
    """
    _editar(client, lead_headers, ficha["id"], {"city": "Mérida"})

    asiento = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "lead.actualizar")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert asiento.event_metadata["campos_vaciados"] == []
