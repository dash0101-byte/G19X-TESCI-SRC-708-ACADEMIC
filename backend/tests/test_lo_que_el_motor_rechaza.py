"""
Lo que el servidor contesta cuando la base rechaza una fila.

Siete `except IntegrityError` y, hasta el capítulo 42, siete respuestas a la misma pregunta,
cuatro de ellas inventadas. Lo que esas cuatro suponían era que su tabla solo tiene una forma
de rechazar una fila, y ninguna de ellas la tiene: `leads` tiene una restricción única, dos
claves ajenas y tres columnas obligatorias de texto. Medido antes de arreglarlo, con el motor
comprobando las claves ajenas como las comprueba producción:

* `POST /leads` con `campaign_id: 999999` → **500**, «Excepción no controlada».
* `POST /leads` con `assigned_rep_id: 999999` → **500**.
* `PUT /leads/{id}` con `assigned_rep_id: 999999` → **409 «El correo 'elena.ruiz@fintechmx.com'
  ya está registrado en otro prospecto»**: el correo de la propia ficha, que nadie tocó,
  dentro de una frase sobre un conflicto que no ha ocurrido.
* `PUT /leads/{id}` con `campaign_id: 999999` → **200 con la ficha entera**, sin cambiar nada,
  porque el esquema de la edición no declaraba ese campo y no prohíbe los campos de más.

Las cuatro cosas que se comprueban aquí
----------------------------------------
1. Las puertas: qué contesta cada una ahora, y que lo que funcionaba sigue funcionando.
2. El módulo `app.core.integridad`, que es quien pregunta. Sus listas salen de `__table__`.
3. Que el 422 tiene **la forma que el cliente sabe repartir**: el mecanismo del capítulo 40
   reparte por `loc` y reconoce los mensajes de este repositorio por el prefijo de Pydantic.
   Si esa forma se rompiera, el error seguiría llegando y la pantalla volvería a enseñarlo en
   el aviso de arriba, sin que ninguna prueba del cliente lo notara.
4. La guarda: ningún `except IntegrityError` nuevo puede suponer nada sin quedar inventariado
   con su motivo, y ninguna clave ajena nueva puede entrar por un cuerpo de petición sin
   comprobación. Las dos listas salen del código.
"""
import datetime
import re
from pathlib import Path

import pytest
from app.core import integridad
from app.core.database import Base
from app.models.entities import Lead, Tarea, User, WebhookDelivery
from sqlalchemy.exc import IntegrityError
from tests.test_un_blanco_no_es_un_dato import esquemas_de_entrada

APP = Path(__file__).resolve().parents[1] / "app"


# ==============================================================================
# Las puertas
# ==============================================================================

def _renglon(respuesta):
    detalle = respuesta.json()["detail"]
    assert isinstance(detalle, list), f"Se esperaba un 422 por campos, llegó: {detalle!r}"
    return detalle[0]


def test_el_alta_con_una_publicacion_que_no_existe_nombra_el_campo(client, admin_headers):
    respuesta = client.post("/api/v1/leads", headers=admin_headers, json={
        "first_name": "Ajena", "last_name": "Clave",
        "email": "clave.ajena.alta@ejemplo.com", "source": "Website",
        "campaign_id": 999999,
    })
    assert respuesta.status_code == 422
    renglon = _renglon(respuesta)
    assert renglon["loc"] == ["body", "campaign_id"]
    assert "publicación" in renglon["msg"]


def test_el_alta_con_un_asesor_que_no_existe_nombra_el_campo(client, admin_headers):
    respuesta = client.post("/api/v1/leads", headers=admin_headers, json={
        "first_name": "Ajena", "last_name": "Clave",
        "email": "clave.ajena.alta2@ejemplo.com", "source": "Website",
        "assigned_rep_id": 999999,
    })
    assert respuesta.status_code == 422
    assert _renglon(respuesta)["loc"] == ["body", "assigned_rep_id"]


def test_el_alta_con_una_publicacion_real_sigue_entrando(client, admin_headers, campaigns):
    respuesta = client.post("/api/v1/leads", headers=admin_headers, json={
        "first_name": "Valida", "last_name": "Clave",
        "email": "clave.valida.alta@ejemplo.com", "source": "Website",
        "campaign_id": campaigns[0].id,
    })
    assert respuesta.status_code == 201
    assert respuesta.json()["campaign_id"] == campaigns[0].id


def test_la_edicion_con_un_asesor_que_no_existe_ya_no_habla_del_correo(
    client, admin_headers, sample_leads
):
    lead = sample_leads[0]
    respuesta = client.put(
        f"/api/v1/leads/{lead.id}", headers=admin_headers, json={"assigned_rep_id": 999999}
    )
    assert respuesta.status_code == 422
    renglon = _renglon(respuesta)
    assert renglon["loc"] == ["body", "assigned_rep_id"]
    # Lo que esta prueba vigila es la frase que no debe volver: el 409 de antes nombraba el
    # correo de la propia ficha, que quien edita no había tocado.
    assert "correo" not in renglon["msg"]


def test_la_edicion_con_un_asesor_real_sigue_reasignando(
    client, admin_headers, sample_leads, sales_reps
):
    lead = sample_leads[0]
    respuesta = client.put(
        f"/api/v1/leads/{lead.id}", headers=admin_headers,
        json={"assigned_rep_id": sales_reps[0].id},
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["assigned_rep_id"] == sales_reps[0].id


def test_existir_no_es_lo_mismo_que_valer(client, admin_headers, db_session, sales_reps):
    """
    Una cuenta desactivada existe, así que la ficha se le puede asignar como antes.

    Es el límite de este capítulo escrito en una prueba. La comprobación nueva responde a
    «¿hay una fila ahí?», que es lo que la base pregunta y lo que convertía el error en un
    500. Si además tiene que ser un asesor activo —que es lo que `comprobar_responsable` exige
    para el responsable de una publicación— es otra decisión, con su propia discusión, y
    tomarla de paso habría cambiado a quién se le puede asignar cartera sin que nadie lo
    pidiera.
    """
    rep = sales_reps[0]
    rep.is_active = False
    db_session.commit()
    respuesta = client.post("/api/v1/leads", headers=admin_headers, json={
        "first_name": "Cuenta", "last_name": "Apagada",
        "email": "cuenta.apagada@ejemplo.com", "source": "Website",
        "assigned_rep_id": rep.id,
    })
    assert respuesta.status_code == 201


def test_la_edicion_no_dice_que_si_a_la_atribucion(
    client, admin_headers, db_session, sample_leads, campaigns
):
    """
    `PUT` con `campaign_id` respondía 200 con la ficha entera y no cambiaba nada.

    Es la forma exacta del defecto que el capítulo 33 cerró para los campos que se vaciaban:
    la pantalla decía «Prospecto actualizado» y el dato seguía como estaba.
    """
    lead = sample_leads[0]
    antes = lead.campaign_id
    respuesta = client.put(
        f"/api/v1/leads/{lead.id}", headers=admin_headers,
        json={"campaign_id": campaigns[0].id},
    )
    assert respuesta.status_code == 422
    assert _renglon(respuesta)["loc"] == ["body", "campaign_id"]
    db_session.refresh(lead)
    assert lead.campaign_id == antes


def test_la_edicion_de_siempre_sigue_igual(client, admin_headers, sample_leads):
    lead = sample_leads[0]
    respuesta = client.put(
        f"/api/v1/leads/{lead.id}", headers=admin_headers, json={"city": "Monterrey"}
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["city"] == "Monterrey"


def _escrituras_sobre_fichas(hacer):
    """Las instrucciones que la base recibe sobre `leads` mientras se hace algo."""
    from app.core.database import engine
    from sqlalchemy import event

    escrituras = []

    def anotar(conn, cursor, instruccion, parametros, contexto, muchos):
        if "INSERT INTO leads" in instruccion or "UPDATE leads" in instruccion:
            escrituras.append(instruccion.split("\n")[0])

    event.listen(engine, "before_cursor_execute", anotar)
    try:
        respuesta = hacer()
    finally:
        event.remove(engine, "before_cursor_execute", anotar)
    return respuesta, escrituras


def test_la_edicion_tampoco_intenta_escribir_para_contestar(
    client, admin_headers, sample_leads
):
    """
    La misma medición que la del alta, en la otra puerta, y por el mismo motivo.

    El arnés encontró que quitar esta comprobación tampoco ponía nada rojo: la red del
    `except` contesta el mismo 422 con el mismo campo. Lo que distingue a las dos capas es el
    momento, así que es el momento lo que se mide, y en las dos puertas, porque que contesten
    lo mismo **y en el mismo momento** es lo que este capítulo vino a arreglar.
    """
    lead = sample_leads[0]
    respuesta, escrituras = _escrituras_sobre_fichas(lambda: client.put(
        f"/api/v1/leads/{lead.id}", headers=admin_headers, json={"assigned_rep_id": 999999},
    ))
    assert respuesta.status_code == 422
    assert escrituras == [], (
        "La edición intentó actualizar la ficha y dejó que la base la rechazara."
    )


def test_la_comprobacion_contesta_sin_intentar_escribir(client, admin_headers):
    """
    La diferencia entre la comprobación y la red, que el arnés obligó a escribir.

    Al reintroducir los defectos del capítulo apareció que quitar la comprobación previa del
    alta **no ponía nada rojo**: la red del `except` clasifica el mismo rechazo y contesta el
    mismo 422 con el mismo campo. Dos capas con la misma respuesta son una de más, y el
    capítulo 41 dejó dicho qué hacer cuando eso pasa: o falta una prueba, o el arreglo sobra.

    Faltaba esta prueba. Las dos capas no contestan en el mismo momento: la comprobación
    responde **sin llegar a intentar el INSERT**, y la red existe para el hueco que la
    comprobación no puede cubrir —entre preguntar y escribir cabe otra transacción—. Lo que
    se mide, entonces, es el momento: con la comprobación, la base no recibe ninguna
    inserción en `leads`; sin ella, recibe una que falla.
    """
    respuesta, escrituras = _escrituras_sobre_fichas(lambda: client.post(
        "/api/v1/leads", headers=admin_headers, json={
            "first_name": "Antes", "last_name": "DeEscribir",
            "email": "antes.de.escribir@ejemplo.com", "source": "Website",
            "campaign_id": 999999,
        },
    ))
    assert respuesta.status_code == 422
    assert escrituras == [], (
        "El alta intentó insertar la ficha y dejó que la base la rechazara. Contestar lo "
        "mismo después del rechazo funciona, pero significa que la comprobación previa no "
        "está haciendo nada."
    )


def test_la_red_del_alta_tambien_nombra_el_campo(client, admin_headers, monkeypatch):
    """
    El hueco entre comprobar y escribir, que es para lo que está la red.

    Se simula dejando pasar la comprobación: es lo que ocurre cuando la publicación existe
    al preguntar y ya no existe al insertar. Sin esta prueba, la red del alta —el punto 40 de
    §6.4— no tenía ninguna, y volver a poner en ella el 409 del correo no ponía nada rojo.
    """
    # Se deja pasar **solo** la comprobación previa del alta, que es la que recibe las dos
    # claves juntas. El `except` usa la misma función por dentro para clasificar el rechazo,
    # así que silenciarla del todo habría silenciado también a quien tiene que explicar el
    # fallo, y la prueba habría medido otra cosa: un 409 en vez del 422 con el campo.
    original = integridad.claves_que_no_apuntan_a_nada

    def deja_pasar(db, modelo, valores):
        if set(valores) == {"assigned_rep_id", "campaign_id"}:
            return []
        return original(db, modelo, valores)

    monkeypatch.setattr(
        "app.repositories.lead_repository.integridad.claves_que_no_apuntan_a_nada", deja_pasar
    )
    respuesta = client.post("/api/v1/leads", headers=admin_headers, json={
        "first_name": "Carrera", "last_name": "DelAlta",
        "email": "carrera.del.alta@ejemplo.com", "source": "Website",
        "campaign_id": 999999,
    })
    assert respuesta.status_code == 422
    renglon = _renglon(respuesta)
    assert renglon["loc"] == ["body", "campaign_id"]
    assert "correo" not in renglon["msg"]


def test_el_correo_repetido_sigue_contestando_lo_de_siempre(
    client, admin_headers, sample_leads
):
    """La comprobación explícita del correo no cambia: es el camino normal y ya era bueno."""
    respuesta = client.post("/api/v1/leads", headers=admin_headers, json={
        "first_name": "Repetido", "last_name": "Correo",
        "email": sample_leads[0].email, "source": "Website",
    })
    assert respuesta.status_code == 400
    assert "Ya existe" in respuesta.json()["detail"]


# ==============================================================================
# La forma del 422, que es lo que el cliente reparte
# ==============================================================================

def test_el_renglon_del_422_tiene_la_forma_que_el_cliente_reparte(client, admin_headers):
    """
    `erroresDeFormulario.js` reparte por `loc` y reconoce lo nuestro por el prefijo.

    El prefijo `Value error, ` es el nombre interno de la excepción de Pydantic, y el cliente
    lo usa para distinguir un mensaje escrito en este repositorio de uno de biblioteca —el
    validador de correos contesta en inglés y también con `type: value_error`—. Un renglón sin
    el prefijo acabaría en la pantalla como «No se admite este valor», perdiendo la frase que
    explica qué pasó, y ninguna prueba del cliente lo vería porque el cliente estaría
    haciendo lo correcto.
    """
    respuesta = client.post("/api/v1/leads", headers=admin_headers, json={
        "first_name": "Forma", "last_name": "Del422",
        "email": "forma.del.422@ejemplo.com", "source": "Website",
        "campaign_id": 999999,
    })
    renglon = _renglon(respuesta)
    assert renglon["type"] == "value_error"
    assert renglon["loc"][0] == "body"
    assert renglon["msg"].startswith("Value error, ")
    assert renglon["ctx"]["error"] == renglon["msg"][len("Value error, "):]


def test_ningun_mensaje_dice_el_nombre_de_una_columna():
    """
    Lo que el capítulo 40 vino a arreglar: la pantalla enseñaba `source: ...`.

    El nombre del campo viaja en `loc` y la pantalla lo traduce a su etiqueta. Repetirlo
    dentro del texto es lo que hacía que una persona leyera «assigned_rep_id».
    """
    # Solo los nombres con guion bajo, que son los que delatan al esquema: `campaign_id`,
    # `assigned_rep_id`, `first_name`. Los de una sola palabra no se pueden comparar así,
    # porque varios son palabras castellanas —`datos`, `motivo`, `clave`— y un mensaje
    # escrito para leerse las usa; «Vuelva a intentarlo … estos datos» no enseña ninguna
    # columna.
    nombres = {
        columna.name
        for tabla in Base.metadata.sorted_tables
        for columna in tabla.columns
        if "_" in columna.name
    }
    mensajes = list(integridad.NOMBRE_DE_LA_TABLA.values()) + [integridad.MOTIVO_DE_LA_CARRERA]
    for mensaje in mensajes:
        for palabra in re.findall(r"[a-z_]{4,}", mensaje):
            assert palabra not in nombres, f"«{mensaje}» nombra la columna {palabra}."


# ==============================================================================
# El módulo que pregunta
# ==============================================================================

def test_las_claves_ajenas_salen_de_la_tabla():
    claves = {nombre: destino.table.name for nombre, destino in integridad.claves_ajenas(Lead)}
    assert claves == {"assigned_rep_id": "users", "campaign_id": "campaigns"}
    assert integridad.claves_ajenas(User) == ()


def test_los_grupos_unicos_salen_de_las_tres_formas():
    """
    Columna con `unique=True`, `UniqueConstraint` e `Index(unique=True)`.

    Mirar solo la primera —que es lo que se ve al leer un modelo de arriba abajo— dejaría
    fuera las de varias columnas, que son justo las que nadie recuerda de memoria.
    """
    assert integridad.grupos_unicos(Lead) == (("email",),)
    assert ("clave", "lead_id", "regla") in {
        tuple(sorted(grupo)) for grupo in integridad.grupos_unicos(Tarea)
    }


def test_las_columnas_obligatorias_no_cuentan_las_que_alguien_rellena():
    obligatorias = integridad.columnas_obligatorias_escribibles(Lead)
    assert "first_name" in obligatorias
    assert "last_name" in obligatorias
    assert "id" not in obligatorias, "La clave primaria la pone el motor."
    assert "source" not in obligatorias, "Tiene valor por omisión en el modelo."


def test_el_motivo_nombra_la_clave_que_no_apunta_a_nada(db_session):
    rechazo = integridad.motivo_del_rechazo(db_session, Lead, {"campaign_id": 999999})
    assert rechazo.clase == integridad.INEXISTENTE
    assert rechazo.campo == "campaign_id"
    assert "publicación" in rechazo.motivo


def test_el_motivo_nombra_la_columna_obligatoria_vacia(db_session):
    rechazo = integridad.motivo_del_rechazo(db_session, Lead, {"first_name": None})
    assert rechazo.clase == integridad.OBLIGATORIO
    assert rechazo.campo == "first_name"


def test_el_motivo_ve_el_valor_repetido(db_session, sample_leads):
    rechazo = integridad.motivo_del_rechazo(
        db_session, Lead, {"email": sample_leads[0].email}
    )
    assert rechazo.clase == integridad.REPETIDO
    assert rechazo.campo == "email"


def test_la_propia_fila_no_es_un_duplicado_de_si_misma(db_session, sample_leads):
    lead = sample_leads[0]
    rechazo = integridad.motivo_del_rechazo(
        db_session, Lead, {"email": lead.email}, id_propio=lead.id
    )
    assert rechazo.clase == integridad.CARRERA, (
        "Sin descontar la propia fila, cualquier edición que no toque el correo se "
        "contestaría como un conflicto con un prospecto que es ella misma."
    )


def test_sin_ninguna_regla_incumplida_la_respuesta_es_la_carrera(db_session):
    rechazo = integridad.motivo_del_rechazo(db_session, Lead, {"city": "Mérida"})
    assert rechazo.clase == integridad.CARRERA
    assert rechazo.campo is None
    assert "Vuelva a intentarlo" in rechazo.motivo


def test_cada_clase_tiene_su_codigo():
    codigos = {
        clase: integridad.respuesta(integridad.Rechazo(clase, "campo", "motivo"))[0]
        for clase in (
            integridad.OBLIGATORIO, integridad.INEXISTENTE,
            integridad.REPETIDO, integridad.CARRERA,
        )
    }
    assert codigos == {
        integridad.OBLIGATORIO: 422,
        integridad.INEXISTENTE: 422,
        integridad.REPETIDO: 409,
        integridad.CARRERA: 409,
    }


def test_un_conflicto_sin_campo_no_se_contesta_como_un_error_de_campo():
    """Un 409 va con una frase: no es de un campo del formulario y su sitio es el aviso."""
    codigo, detalle = integridad.respuesta(
        integridad.Rechazo(integridad.CARRERA, None, integridad.MOTIVO_DE_LA_CARRERA)
    )
    assert codigo == 409
    assert isinstance(detalle, str)


# ==============================================================================
# El webhook del CRM: el «duplicado» que descartaba el evento
# ==============================================================================

def _cuerpo_del_webhook():
    from tests.conftest import sign_webhook
    return sign_webhook({
        "event": "lead.created",
        "crm_platform": "HubSpot",
        "external_lead_id": "HS-INTEGRIDAD-1",
        "data": {"email": "integridad.webhook@ejemplo.com", "activity_type": "PAGE_VIEW"},
    })


def test_el_webhook_no_llama_duplicado_a_lo_que_no_es_un_duplicado(client, monkeypatch):
    """
    Era la respuesta más cara de las cuatro: «duplicado» descarta el evento entero.

    El emisor recibe que su evento ya se procesó, así que no reintenta, y el prospecto no
    existe en ninguna parte. El registro de actividad, dos capas más abajo, ya preguntaba
    `_ya_registrado` y volvía a lanzar si no lo era; esta capa lo suponía.
    """
    async def rechaza(self, payload):
        raise IntegrityError("INSERT", {}, Exception("rechazo de prueba"))

    monkeypatch.setattr("app.api.v1.endpoints.crm.CRMService.process_webhook", rechaza)
    cuerpo, cabeceras = _cuerpo_del_webhook()
    respuesta = client.post("/api/v1/crm/webhook", content=cuerpo, headers=cabeceras)
    assert respuesta.status_code == 500
    assert "recibida" not in respuesta.json()["detail"]


def test_una_entrega_que_perdio_la_carrera_sigue_siendo_un_duplicado(client, monkeypatch):
    """
    Y el caso para el que se escribió aquel `except` sigue contestando lo mismo.

    La entrega se confirma antes de que el rechazo ocurra, de modo que cuando el `except`
    pregunta, la fila está: es lo que pasa cuando otra transacción gana la carrera.
    """
    async def confirma_y_rechaza(self, payload):
        self.db.commit()
        raise IntegrityError("INSERT", {}, Exception("rechazo de prueba"))

    monkeypatch.setattr(
        "app.api.v1.endpoints.crm.CRMService.process_webhook", confirma_y_rechaza
    )
    cuerpo, cabeceras = _cuerpo_del_webhook()
    respuesta = client.post("/api/v1/crm/webhook", content=cuerpo, headers=cabeceras)
    assert respuesta.status_code == 409
    assert "ya fue recibida" in respuesta.json()["detail"]


def test_la_pregunta_del_webhook_no_mira_si_la_entrada_caduco(db_session):
    """
    `entrega_registrada` responde si la fila existe, no si vale como respuesta repetida.

    Una entrada vencida que siguiera ahí explica igual el rechazo del índice único, que es
    lo único que esta pregunta tiene que decidir.
    """
    from app.services.webhook_dedup import entrega_registrada

    ayer = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
    db_session.add(WebhookDelivery(
        signature="firma-caducada", idempotency_key="clave-caducada",
        crm_platform="HubSpot", event="lead.created",
        received_at=ayer, expires_at=ayer, response_data={},
    ))
    db_session.commit()
    assert entrega_registrada(
        db_session, signature="firma-caducada", idempotency_key="otra"
    ) is True
    assert entrega_registrada(
        db_session, signature="no-consta", idempotency_key="tampoco"
    ) is False


# ==============================================================================
# El alta de una cuenta: el «ya existe una cuenta» que valía para todo
# ==============================================================================

def test_el_alta_de_una_cuenta_no_culpa_al_correo_de_lo_que_no_hizo(
    client, admin_headers, monkeypatch
):
    """
    `users` tiene una restricción única y nueve columnas obligatorias.

    Esta red se escribió para la carrera del correo —dos administradores creando la misma
    cuenta a la vez— y contestaba lo mismo para cualquier otra cosa que la base rechazara.
    Cuando al preguntar no hay ninguna regla incumplida, la respuesta honesta es que algo
    cambió debajo y conviene repetir, no que el correo esté cogido.
    """
    def rechaza(self):
        raise IntegrityError("INSERT", {}, Exception("rechazo de prueba"))

    monkeypatch.setattr("sqlalchemy.orm.Session.commit", rechaza)
    respuesta = client.post("/api/v1/users", headers=admin_headers, json={
        "email": "cuenta.nueva.integridad@plurione.com",
        "full_name": "Cuenta Nueva",
        "role": "Commercial_Executive",
        "password": "Un4-Clave-Larga!x",
    })
    assert respuesta.status_code == 409
    assert "Vuelva a intentarlo" in respuesta.json()["detail"]
    assert "correo" not in respuesta.json()["detail"]


# ==============================================================================
# La agenda: el «ya existía» que se saltaba tareas
# ==============================================================================

def _tarea(lead_id, asesor_id, clave="agenda-1"):
    return Tarea(
        lead_id=lead_id, asesor_id=asesor_id, regla="prueba_de_integridad", clave=clave,
        vence_el=datetime.datetime.now(datetime.timezone.utc), motivo="prueba",
    )


def test_una_tarea_repetida_sigue_siendo_un_duplicado(db_session, sample_leads, sales_reps):
    from app.services.motor_de_reglas import _crear

    lead, rep = sample_leads[0], sales_reps[0]
    assert _crear(db_session, _tarea(lead.id, rep.id)) is True
    db_session.commit()
    assert _crear(db_session, _tarea(lead.id, rep.id)) is False


def test_una_tarea_rechazada_por_otro_motivo_no_pasa_por_duplicada(
    db_session, sample_leads
):
    """
    Devolver `False` ante cualquier rechazo decía «ya existía» de una tarea que no existía.

    La pasada seguía adelante contando que no había nada que hacer, y el trabajo que esa
    regla había decidido crear no se creaba ni constaba en ningún sitio.
    """
    from app.services.motor_de_reglas import _crear

    with pytest.raises(integridad.LaBaseRechaza) as fallo:
        _crear(db_session, _tarea(sample_leads[0].id, 999999))
    assert fallo.value.rechazo.clase == integridad.INEXISTENTE
    assert fallo.value.rechazo.campo == "asesor_id"
    db_session.rollback()


# ==============================================================================
# La guarda
# ==============================================================================

# Cada `except IntegrityError` del código, y cómo decide lo que contesta.
#
# «pregunta» significa que consulta la base antes de decir qué pasó; la prueba de abajo lo
# comprueba buscando la llamada, no el nombre del archivo. Lo demás tiene que traer un
# motivo escrito, que es la forma de que una excepción deliberada se distinga de un olvido.
COMO_DECIDE = {
    "api/v1/endpoints/crm.py": "pregunta",
    "api/v1/endpoints/users.py": "pregunta",
    "repositories/lead_repository.py": "pregunta",
    "services/motor_de_reglas.py": "pregunta",
    "services/recalculation_service.py": "pregunta",
    "services/registro_de_actividad.py": "pregunta",
    # El único que no tiene que averiguar nada: no traduce el rechazo a ningún mensaje ni
    # decide si la fila existía, vuelve a ejecutar la suma. Lo que puede perderse es el
    # recuento de una visita.
    "services/ciclo_de_publicaciones.py": "reintenta la operación, no interpreta el rechazo",
}

PREGUNTAS = (
    "motivo_del_rechazo",
    "_ya_registrado",
    "trabajo_en_curso",
    "entrega_registrada",
    "_lo_que_la_base_rechazo",
)


def _bloques_con_except():
    """Cada `except IntegrityError` del código, con las líneas que vienen detrás."""
    encontrados = {}
    for fuente in sorted(APP.rglob("*.py")):
        lineas = fuente.read_text(encoding="utf-8").splitlines()
        for numero, linea in enumerate(lineas):
            # La cláusula y no la palabra: varios comentarios de este capítulo hablan de
            # `except IntegrityError` dentro de una frase, y contarlos habría hecho que
            # explicar el arreglo cambiara la cuenta de lo arreglado.
            if re.match(r"\s*except IntegrityError", linea):
                relativo = fuente.relative_to(APP).as_posix()
                encontrados.setdefault(relativo, []).append(
                    "\n".join(lineas[numero:numero + 25])
                )
    return encontrados


def test_cada_except_integrityerror_pregunta_o_trae_su_motivo():
    bloques = _bloques_con_except()
    assert set(bloques) == set(COMO_DECIDE), (
        "Hay un `except IntegrityError` en un archivo que no está inventariado, o el "
        "inventario nombra uno que ya no existe. Cada uno tiene que decir cómo decide lo "
        "que contesta."
    )
    for archivo, cuerpos in bloques.items():
        if COMO_DECIDE[archivo] != "pregunta":
            continue
        for cuerpo in cuerpos:
            assert any(pregunta in cuerpo for pregunta in PREGUNTAS), (
                f"El `except IntegrityError` de {archivo} no consulta la base: está "
                f"suponiendo qué restricción falló, que es el punto 26 de §6.4."
            )


def test_eran_siete_y_el_octavo_es_la_red_que_le_faltaba_al_alta():
    """
    Siete antes del capítulo 42 y ocho después, los dos últimos en el repositorio de fichas.

    El que entra es el punto 40 de §6.4: la edición llevaba su red desde el capítulo 33 —«red
    de seguridad ante dos actualizaciones simultáneas»— y el alta comprobaba el correo y
    después insertaba, sin nada entre las dos cosas. El número está en el Reporte 40 y en los
    comentarios del código, y un `except IntegrityError` nuevo tiene que pasar por el
    inventario de arriba; pasar por él obliga a contestar la pregunta: ¿este sabe de verdad
    qué rechazó la base?
    """
    bloques = _bloques_con_except()
    assert sum(len(cuerpos) for cuerpos in bloques.values()) == 8
    assert len(bloques["repositories/lead_repository.py"]) == 2, (
        "El alta y la edición tienen cada una la suya, y las dos preguntan por la misma vía."
    )


# Clave ajena que puede llegar en un cuerpo de petición → cómo se trata.
#
# La lista se **deriva** de los esquemas de entrada y del esquema de la base, abajo; esto es
# la decisión sobre cada una, y lo que hace que una nueva nazca en rojo.
#
# Son siete campos sobre cuatro columnas, y al derivarla aparecieron tres que no se
# esperaban: las dos de `responsable_id` y la de `vincular`. Las tres estaban ya comprobadas,
# cada una a su manera y en su endpoint —un 422 que además exige que sea un asesor activo, y
# un 404 porque el cuerpo nombra un prospecto que quien pide puede no alcanzar—, lo que
# significa que la pregunta «¿y si ese identificador no existe?» tenía tres respuestas
# escritas en este repositorio y que la cuarta era no preguntar.
CLAVES_DE_UN_CUERPO = {
    # Comprobada aparte desde el capítulo 28, en `ciclo.comprobar_responsable`: 422, y además
    # exige que la cuenta sea un asesor **activo**, que es más de lo que la base pide.
    ("CampanaCreate", "responsable_id"): "comprobada aparte",
    ("CampanaUpdate", "responsable_id"): "comprobada aparte",
    # Comprobada aparte en el endpoint de la bandeja: 404 y no 422, porque el cuerpo nombra
    # un prospecto que quien vincula puede no tener en su alcance, y decir «no existe» es la
    # respuesta que no cuenta nada de la cartera ajena.
    ("VinculacionRequest", "lead_id"): "comprobada aparte",
    ("LeadCreate", "assigned_rep_id"): "comprobada",
    ("LeadCreate", "campaign_id"): "comprobada",
    ("LeadUpdate", "assigned_rep_id"): "comprobada",
    # La atribución no se edita: el campo se declara para poder rechazarlo, porque sin
    # declararlo el 200 decía que sí a algo que no hacía.
    ("LeadUpdate", "campaign_id"): "rechazada",
}


def _columnas_de_clave_ajena():
    return {
        columna.name
        for tabla in Base.metadata.sorted_tables
        for columna in tabla.columns
        if columna.foreign_keys
    }


def test_las_claves_ajenas_que_entran_por_un_cuerpo_estan_decididas():
    """
    Dieciocho claves ajenas, y cuatro columnas que pueden salir de un cuerpo de petición.

    Las demás se escriben desde una fila ya cargada —`lead.id`, `campana.id`, `destino.id`—,
    y eso no es casualidad ni se puede dar por hecho mañana: la lista sale de cruzar los
    campos de cada esquema de entrada con las columnas de clave ajena del esquema, así que un
    campo nuevo que se llame como una de ellas aparece aquí el día que se declara.
    """
    ajenas = _columnas_de_clave_ajena()
    encontradas = {
        (nombre, campo)
        for nombre, esquema in esquemas_de_entrada().items()
        for campo in esquema.model_fields
        if campo in ajenas
    }
    assert encontradas == set(CLAVES_DE_UN_CUERPO), (
        "Un esquema de entrada acepta una clave ajena que nadie ha decidido cómo tratar. "
        "Sin comprobación, un identificador que no existe llega al INSERT y sale como 500."
    )


@pytest.mark.parametrize(
    "esquema,campo",
    sorted(clave for clave, trato in CLAVES_DE_UN_CUERPO.items() if trato == "comprobada"),
)
def test_toda_clave_comprobada_se_comprueba_de_verdad(
    db_session, sample_leads, esquema, campo
):
    """
    La comprobación existe y es la misma para las dos puertas: sale de `integridad`.

    Se ejercita el repositorio y no el endpoint a propósito: lo que esta prueba vigila es
    que el alta y la edición pasen por la misma función, que es lo que hace que contesten lo
    mismo. Las respuestas HTTP las comprueban las pruebas de las puertas, arriba.
    """
    rechazos = integridad.claves_que_no_apuntan_a_nada(db_session, Lead, {campo: 999999})
    assert [rechazo.campo for rechazo in rechazos] == [campo]


def test_la_comprobacion_no_estorba_cuando_el_destino_existe(db_session, sales_reps, campaigns):
    valores = {"assigned_rep_id": sales_reps[0].id, "campaign_id": campaigns[0].id}
    assert integridad.claves_que_no_apuntan_a_nada(db_session, Lead, valores) == []


def test_un_nulo_no_es_una_clave_que_no_apunta_a_nada(db_session):
    """
    Una ficha sin asesor y sin publicación es lo normal, y las dos columnas lo admiten.

    Si esto no distinguiera `None` de un identificador inexistente, el alta de cualquier
    prospecto sin asignar contestaría que no existe la cuenta.
    """
    valores = {"assigned_rep_id": None, "campaign_id": None}
    assert integridad.claves_que_no_apuntan_a_nada(db_session, Lead, valores) == []


def test_lo_que_no_vino_en_el_cuerpo_no_se_comprueba(db_session):
    """Una edición parcial que no toca el asesor no tiene que preguntar por él."""
    assert integridad.claves_que_no_apuntan_a_nada(db_session, Lead, {"city": "Mérida"}) == []


def test_el_pragma_esta_en_el_motor_y_no_en_las_pruebas():
    """
    Donde vive el motor, no en `conftest`.

    En `conftest` habría encendido las claves ajenas para la suite y las habría dejado
    apagadas para el desarrollo local, que usa el mismo motor y la misma base de archivo. El
    sitio de esta línea es el único donde se crea el motor.
    """
    fuente = (APP / "core" / "database.py").read_text(encoding="utf-8")
    assert "PRAGMA foreign_keys=ON" in fuente
    assert 'event.listens_for(engine, "connect")' in fuente
    conftest = (Path(__file__).resolve().parent / "conftest.py").read_text(encoding="utf-8")
    assert "PRAGMA foreign_keys" not in conftest
