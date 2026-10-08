"""
La cola larga: sesenta bordes repartidos por nueve archivos, y lo que cada uno sostiene.

No es un capítulo ni una pieza: es lo que queda cuando las piezas grandes están cerradas.
Son guardas de una línea, brazos de recursión, topes de desborde y vueltas de bucle, y
tienen en común que **ninguno se recorre con una petición ordenada**. Lo que los agrupa aquí
no es el tema sino la forma de fallar: casi todos fallan en silencio, devolviendo algo
plausible en lugar de lo correcto.

Cuatro clases, y conviene distinguirlas porque lo que prueban es distinto:

* **Topes de desborde** (`core/metricas.py`): protegen la memoria del proceso de una
  explosión de cardinalidad. Si no funcionan, no hay error: hay una serie por cada ruta
  inventada que alguien pida, y el proceso crece hasta que lo mata el contenedor.
* **Brazos de recursión** (`derechos_del_titular.py`): el mapa de supresión recorre JSON
  anidado. Un brazo que no baja a las listas deja datos de una persona dentro de un `extra`
  que nadie vuelve a mirar, y la supresión queda **declarada y no hecha**.
* **Bordes de texto** (`core/redes.py`): lo que se reparte por WhatsApp o LinkedIn. Un
  enlace recortado no lleva a ninguna parte, y eso lo ve quien pulsa, no quien publica.
* **Redes de último recurso** (`core/audit.py`, `ciclo_de_publicaciones.py`): el `rollback`
  que falla después de que ya falló algo, y el `IntegrityError` que se reintenta. Solo se
  recorren cuando algo está ya roto.
"""
import datetime
import logging
import uuid

import pytest
from app.core import audit as audit_mod
from app.core import metricas, observabilidad, redes
from app.core.security import CurrentUser, UserRole
from app.models.entities import ActivityType, Campaign, Lead, UnmatchedEvent
from app.services import ciclo_de_publicaciones as ciclo
from app.services import derechos_del_titular as derechos

# ==============================================================================
# core/redes.py — lo que se reparte, y lo que cede cuando no cabe
# ==============================================================================

@pytest.mark.parametrize("red", [None, "", "telepatia", "MySpace"])
def test_sin_una_red_reconocida_el_enlace_va_limpio(red):
    """
    Una red que no se reconoce no añade parámetro: el enlace sale como el de la página.

    El parámetro `?r=` es una etiqueta de analítica, no una llave. Añadirlo con un valor
    inventado metería basura en la columna de red de cada visita —`red` forma parte de la
    clave del contador desde el capítulo 27— y las filas del informe dejarían de sumar el
    total por culpa de un enlace mal escrito a mano.
    """
    enlace = redes.enlace_de_red("mi-publicacion", red)

    assert enlace == redes.enlace_publico("mi-publicacion")
    assert "?" not in enlace


def test_una_red_reconocida_etiqueta_el_enlace():
    """La mitad de enfrente, para que las dos se lean juntas."""
    alguna = next(iter(redes.REDES))

    enlace = redes.enlace_de_red("mi-publicacion", alguna)

    assert enlace.endswith(f"?{redes.PARAMETRO_DE_RED}={alguna}")


@pytest.mark.parametrize("maximo,esperado", [(0, ""), (1, "…")])
def test_un_tope_de_una_letra_o_de_ninguna_no_devuelve_media_palabra(maximo, esperado):
    """
    El borde del recorte: con uno o cero caracteres de tope, no hay resumen posible.

    Sin esta salida, el cálculo de abajo haría `texto[:maximo - 1]` con `maximo = 0`, que en
    Python es `texto[:-1]` —el texto entero menos la última letra— y devolvería un texto
    larguísimo justo donde el tope era cero. Es la clase de error que no revienta: produce
    un valor plausible y equivocado.
    """
    assert redes._recortar("una descripción que no cabe de ninguna manera", maximo) == esperado


def test_hoy_todas_las_redes_declaran_su_tope():
    """
    El `maximo` es opcional en la declaración, y hoy ninguna red lo deja sin poner.

    Lo que había aquí era una prueba de la rama «red sin tope» que se saltaba siempre: una
    prueba que no puede correr no es una prueba, es un renglón verde. La rama existe —el
    campo es `Optional`— y se recorre por el otro lado, con una red que no está en la tabla
    (`test_una_red_desconocida_recibe_el_texto_entero_sin_recortar`), que es la mitad
    alcanzable de la misma condición.

    Lo que sí vale la pena sujetar es esto: que la lista esté completa. Una red nueva sin
    tope repartiría el texto entero donde la red lo corta, y el enlace —que va al final—
    sería lo que se pierde. Si alguien añade una así, se decide aquí.
    """
    sin_tope = [nombre for nombre, entrada in redes.REDES.items() if entrada.maximo is None]

    assert sin_tope == [], f"estas redes no declaran tope: {sin_tope}"


def test_si_ni_el_enlace_cabe_en_el_tope_se_manda_el_enlace_solo():
    """
    **El enlace nunca se recorta**, y esta es la rama que lo sostiene.

    Cuando el tope de la red no da ni para el enlace, lo que cede es la descripción entera:
    un texto cortado sigue diciendo algo y un enlace cortado no lleva a ninguna parte. Es
    preferible pasarse en una red que repartir un enlace roto, y la prueba lo comprueba
    forzando un tope imposible sobre una red de verdad.
    """
    alguna = next(nombre for nombre, e in redes.REDES.items() if e.maximo is not None)
    enlace = redes.enlace_de_red("slug-largo-de-verdad", alguna)

    class ToperaMinuscula:
        maximo = 5

    original = redes.REDES[alguna]
    redes.REDES[alguna] = ToperaMinuscula()
    try:
        texto = redes.texto_para(alguna, "Una descripción que no va a caber.", "slug-largo-de-verdad")
    finally:
        redes.REDES[alguna] = original

    assert texto == enlace, "cede la descripción, no el enlace"


def test_sin_descripcion_se_reparte_el_enlace_y_nada_mas():
    alguna = next(iter(redes.REDES))

    for vacia in (None, "", "   "):
        assert redes.texto_para(alguna, vacia, "slug-2") == redes.enlace_de_red("slug-2", alguna)


def test_los_textos_por_red_salen_uno_por_red_activa():
    """El envoltorio: una entrada por red activa y ninguna más."""
    activas = list(redes.REDES)[:2]

    textos = redes.textos_por_red("Descripción corta.", "slug-3", activas)

    assert sorted(textos) == sorted(activas)
    for red, texto in textos.items():
        assert redes.enlace_de_red("slug-3", red) in texto


# ==============================================================================
# derechos_del_titular.py — la supresión que recorre JSON anidado
# ==============================================================================

def test_una_tabla_que_no_tiene_modelo_se_dice_en_voz_alta():
    """
    El mapa de supresión se deriva del esquema, y una tabla sin modelo es un error de verdad.

    Devolver `None` aquí dejaría una tabla del mapa sin recorrer, y la supresión de una
    ficha pasaría por encima de ella sin tocarla: datos de una persona que consta borrada.
    Un `LookupError` ruidoso es exactamente lo que se quiere, porque solo puede pasar si
    alguien añade un nombre al mapa que no corresponde a ninguna tabla.
    """
    with pytest.raises(LookupError) as fallo:
        derechos._modelo_de_tabla("una_tabla_que_no_existe")

    assert "una_tabla_que_no_existe" in str(fallo.value)


def test_cada_tabla_del_mapa_tiene_su_modelo():
    """La premisa del de arriba: hoy todas resuelven, y si una deja de hacerlo se ve aquí."""
    for tabla in derechos.tablas_que_apuntan_a_leads():
        assert derechos._modelo_de_tabla(tabla) is not None, tabla


def test_el_retirado_baja_a_las_listas_y_a_los_diccionarios_anidados():
    """
    Un dato identificativo escondido dentro de una lista dentro de un diccionario también se va.

    Es el brazo de recursión que no se recorría, y el que más importa de los tres: los
    `activity_data` y los `event_metadata` del sistema son JSON de forma libre que llega de
    fuera, así que un correo puede estar a cualquier profundidad y dentro de una lista. Un
    brazo que no baje ahí deja la supresión **declarada y no hecha**, que es peor que no
    tenerla: consta por escrito que se borró.
    """
    identificativos = ["ana@ejemplo.mx", "+525512345678"]
    dentro = {
        "nivel1": [
            {"correo": "ana@ejemplo.mx"},
            ["+525512345678", "nada que ver"],
            {"profundo": {"lista": ["Ana@Ejemplo.MX"]}},
        ],
        "intacto": "una cadena cualquiera",
        "numero": 42,
    }

    limpio = derechos._retirar(dentro, identificativos)

    assert limpio["nivel1"][0]["correo"] == derechos.SUPRIMIDO
    assert limpio["nivel1"][1][0] == derechos.SUPRIMIDO
    assert limpio["nivel1"][1][1] == "nada que ver"
    # Y con otra caja de letras: la comparación es en minúsculas.
    assert limpio["nivel1"][2]["profundo"]["lista"][0] == derechos.SUPRIMIDO
    assert limpio["intacto"] == "una cadena cualquiera"
    assert limpio["numero"] == 42


def test_el_contiene_encuentra_el_correo_a_cualquier_profundidad():
    """
    Los tres brazos de `_contiene`, que es lo que decide si una ingesta sin vincular es de alguien.

    Si solo mirara cadenas, una ingesta del CRM cuyo cuerpo lleva el correo dentro de una
    lista no se asociaría a esa persona y se quedaría fuera de su expediente: la respuesta a
    «qué consta sobre mí» saldría incompleta, que es justo el derecho que esto atiende.
    """
    email = "ana@ejemplo.mx"

    assert derechos._contiene("  Ana@Ejemplo.MX  ", email) is True
    assert derechos._contiene({"a": {"b": "ana@ejemplo.mx"}}, email) is True
    assert derechos._contiene(["x", ["y", "ana@ejemplo.mx"]], email) is True
    assert derechos._contiene({"a": ["x", "y"]}, email) is False
    assert derechos._contiene(1234, email) is False
    assert derechos._contiene("diana@ejemplo.mx", email) is False


def test_una_ficha_sin_correo_ni_telefono_no_arrastra_eventos_de_nadie():
    """
    Sin nada con que comparar, la consulta no se hace: se devuelve vacío.

    Sin esa salida, `or_(*[])` es una condición vacía que SQLAlchemy traduce a verdadero, y
    la consulta devolvería **todos** los eventos sin asociar de la base. En el expediente de
    una persona eso serían los datos de contacto de todas las demás, que es la peor
    equivocación posible en la función que atiende «qué consta sobre mí».
    """
    sin_nada = Lead(first_name="Sin", last_name="Datos", email=None, phone=None)

    assert derechos._eventos_sin_asociar(None, sin_nada) == []


# ==============================================================================
# core/metricas.py — los topes que protegen la memoria del proceso
# ==============================================================================

def test_una_ruta_mas_alla_del_tope_se_agrupa_en_una_sola_serie(monkeypatch):
    """
    El tope de cardinalidad, que es lo que impide que `/metrics` haga crecer el proceso.

    Una ruta no plantillada —o un atacante pidiendo `/a`, `/b`, `/c`…— crearía una serie por
    cada valor distinto, y las series viven en memoria del proceso para siempre. No hay
    error: el contenedor crece hasta que lo mata el orquestador, y el síntoma es un
    reinicio sin causa aparente. Pasado el tope, todo lo nuevo cae en una etiqueta común.
    """
    monkeypatch.setattr(metricas, "MAXIMO_DE_SERIES", 2)
    metricas.reiniciar()

    metricas.observar_peticion("GET", "/una", 200, 0.01)
    metricas.observar_peticion("GET", "/dos", 200, 0.01)
    metricas.observar_peticion("GET", "/tres", 200, 0.01)
    metricas.observar_peticion("GET", "/cuatro", 200, 0.01)

    texto = metricas.render()
    assert metricas.ETIQUETA_DESBORDE in texto
    assert "/tres" not in texto and "/cuatro" not in texto
    # Las dos primeras siguen nombradas: el tope agrupa lo nuevo, no lo borra.
    assert "/una" in texto and "/dos" in texto


def test_una_categoria_de_score_mas_alla_del_tope_tambien_se_agrupa(monkeypatch):
    """El mismo tope sobre el otro contador con etiqueta variable."""
    monkeypatch.setattr(metricas, "MAXIMO_DE_SERIES", 1)
    metricas.reiniciar()

    metricas.contar_score("HOT")
    metricas.contar_score("COLD")

    texto = metricas.render()
    assert metricas.ETIQUETA_DESBORDE in texto


def test_si_la_base_no_responde_las_metricas_lo_dicen_con_un_indicador(monkeypatch):
    """
    `/metrics` tiene que contestar aunque la base no conteste, y decir que no contestó.

    Es lo que lee un recolector, así que propagar el error haría que la métrica de
    disponibilidad desapareciera justo cuando hace falta: el panel mostraría «sin datos»,
    que se parece a un problema de red. En su lugar publica
    `plurione_base_de_datos_accesible 0`, que es una alerta accionable.
    """
    class SesionCaida:
        def query(self, *_a, **_k):
            raise RuntimeError("la base no responde")

    texto = metricas.render(db=SesionCaida())

    assert "plurione_base_de_datos_accesible 0" in texto
    assert "las metricas derivadas se omiten" in texto


def test_sin_sesion_las_metricas_del_proceso_salen_igual():
    """
    `db=None` es el caso normal cuando `/metrics` se sirve sin dependencia de base.

    Lo que se comprueba es que las del proceso siguen ahí: una respuesta vacía se leería
    como «el servicio no publica métricas» y el recolector dejaría de preguntar.
    """
    texto = metricas.render(db=None)

    assert "plurione_worker_info" in texto
    assert "plurione_base_de_datos_accesible" not in texto


# ==============================================================================
# core/audit.py — el asiento que falla, y el rollback que también falla
# ==============================================================================

def test_un_asiento_que_no_se_puede_escribir_sin_commit_no_deshace_la_sesion(monkeypatch, caplog):
    """
    Con `commit=False`, el asiento que falla NO toca la transacción de quien llama.

    Es la diferencia entre «no se pudo auditar» y «se perdió la operación»: cuando el
    asiento forma parte de una transacción mayor, deshacerla por un fallo de auditoría
    descartaría el cambio de negocio que sí era válido. Quien llama con `commit=False` es
    dueño de su transacción y decide él.
    """
    class SesionQueNoEscribe:
        def __init__(self):
            self.deshecha = False

        def add(self, *_a, **_k):
            raise RuntimeError("la tabla de auditoría no acepta la fila")

        def rollback(self):
            self.deshecha = True

        def commit(self):
            pass

    sesion = SesionQueNoEscribe()
    with caplog.at_level(logging.ERROR):
        audit_mod.registrar_evento(
            sesion, accion="prueba.cola_larga", entidad="prueba", commit=False
        )

    assert sesion.deshecha is False, "sin commit, la transacción de quien llama no se toca"
    assert any("asiento de auditoría" in r.getMessage() for r in caplog.records)


def test_si_tampoco_se_puede_deshacer_tras_el_fallo_de_auditoria_queda_dicho(caplog):
    """
    El `rollback` que falla después de que ya falló el asiento. No se propaga nada.

    Con `commit=True` el asiento es la operación, así que deshacer la sesión es lo correcto;
    si ni eso se puede, lo único que queda es dejar los dos apuntes. Propagarlo convertiría
    un fallo de auditoría en un 500 sobre una operación que pudo haber ido bien.
    """
    class SesionQueNoAdmiteNada:
        def add(self, *_a, **_k):
            raise RuntimeError("no se pudo escribir el asiento")

        def rollback(self):
            raise RuntimeError("y tampoco se puede deshacer")

        def commit(self):
            pass

    with caplog.at_level(logging.ERROR):
        audit_mod.registrar_evento(
            SesionQueNoAdmiteNada(), accion="prueba.cola_larga", entidad="prueba", commit=True
        )

    mensajes = " | ".join(r.getMessage() for r in caplog.records)
    assert "asiento de auditoría" in mensajes
    assert "deshacer la sesión" in mensajes


# ==============================================================================
# ciclo_de_publicaciones.py — el estado que no existe y la visita que compite
# ==============================================================================

def test_un_estado_de_publicacion_que_no_existe_se_rechaza_nombrandolo():
    """
    Los estados son un vocabulario cerrado, y uno inventado es un error de programación.

    Sin la comprobación, `campana.estado` aceptaría cualquier cadena y `is_active` saldría
    falso: la publicación quedaría en un estado que ninguna pantalla sabe dibujar y que
    ninguna consulta encuentra, sin que nada falle.
    """
    campana = Campaign(name="Prueba", channel="LinkedIn")

    with pytest.raises(ValueError) as fallo:
        ciclo.fijar_estado(campana, "en-remojo")

    assert "en-remojo" in str(fallo.value)


def test_reactivar_no_sobrescribe_la_direccion_con_la_que_se_publico():
    """
    `url_base_publicada` se escribe UNA vez, al activar, y reactivar no la toca.

    De esa columna cuelga la pregunta «¿el enlace que la gente ya tiene lleva aquí?», y
    quien lo tiene lo copió la primera vez. Sobrescribirla al reactivar borraría justo la
    prueba de que el enlace repartido caducó: el aviso del panel diría que todo está bien.
    """
    campana = Campaign(name="Prueba", channel="LinkedIn")

    ciclo.fijar_estado(campana, ciclo.ACTIVA)
    primera = campana.url_base_publicada
    assert primera is not None

    campana.url_base_publicada = "https://una-direccion-de-antes.example"
    ciclo.fijar_estado(campana, ciclo.ACTIVA)

    assert campana.url_base_publicada == "https://una-direccion-de-antes.example"


def test_una_publicacion_sin_fecha_de_fin_no_vence_nunca():
    """`vencida` sobre una publicación sin fin es falso, no un error de comparación."""
    sin_fin = Campaign(name="Prueba", channel="LinkedIn", end_date=None)
    ya_paso = Campaign(
        name="Prueba", channel="LinkedIn",
        end_date=datetime.datetime(2020, 1, 1),
    )

    assert ciclo.vencida(sin_fin) is False
    assert ciclo.vencida(ya_paso) is True


def test_el_nombre_de_una_copia_se_recorta_para_que_quepa_con_el_sufijo(db_session):
    """
    `name` son 200 caracteres. Duplicar una publicación con nombre al límite los pasaría.

    Sin el recorte, el `INSERT` muere con un error del motor sobre una columna, sesenta
    líneas por debajo de «duplicar»: quien pulsa el botón ve un 500 y nadie relaciona la
    causa con la longitud del nombre. Y se recorta el nombre, no el sufijo, porque el sufijo
    es lo que distingue la copia del original en el listado.
    """
    largo = "P" * 200
    original = Campaign(name=largo, channel="LinkedIn", description="Texto")
    db_session.add(original)
    db_session.commit()

    copia = ciclo.duplicar(db_session, original)

    assert len(copia.name) <= 200
    assert copia.name.endswith(ciclo.SUFIJO_DE_COPIA)
    assert copia.estado != ciclo.ACTIVA, "una copia sale en borrador"


# ==============================================================================
# core/observabilidad.py — el formato del registro y el mapa de rutas
# ==============================================================================

@pytest.mark.parametrize("ajuste,esperado", [("json", "json"), ("TEXT", "text"), ("  Json  ", "json")])
def test_un_formato_de_registro_escrito_a_mano_gana_sobre_el_automatico(monkeypatch, ajuste, esperado):
    """
    `LOG_FORMAT` explícito manda; `auto` decide por el entorno.

    Importa porque el modo automático acierta casi siempre y se equivoca justo cuando más
    molesta: depurar un incidente en producción con texto plano es notablemente más cómodo
    que con JSON por línea, y al revés para un recolector. Fijarlo a mano gana siempre, y si
    el ajuste se ignorara nadie lo notaría hasta estar dentro del incidente.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "LOG_FORMAT", ajuste)
    assert observabilidad.formato_de_registro() == esperado


def test_un_extra_que_no_sabe_serializarse_no_tumba_el_evento():
    """
    Un objeto cualquiera en un `extra` se convierte en su texto, no rompe el renglón.

    El formateador JSON escribe los `extra` tal cual, y un objeto sin serializar haría que
    se perdiera el evento **entero** —justo el que alguien quiso enriquecer con contexto—.
    Se degrada a `str` y el renglón sale.
    """
    class CosaRara:
        def __str__(self):
            return "una cosa rara"

    assert observabilidad._serializable("texto") == "texto"
    assert observabilidad._serializable(7) == 7
    assert observabilidad._serializable(None) is None
    assert observabilidad._serializable(CosaRara()) == "una cosa rara"


def test_el_formateador_json_incluye_la_pila_cuando_la_hay():
    """
    `stack_info` entra como campo propio, en una línea y escapado.

    Es lo que hace que `jq` pueda leer el renglón: una pila con saltos de línea de verdad
    partiría el evento en varios renglones y el recolector los leería como eventos distintos
    y mal formados.
    """
    registro = logging.LogRecord(
        name="prueba", level=logging.ERROR, pathname=__file__, lineno=1,
        msg="algo pasó", args=(), exc_info=None,
    )
    registro.stack_info = "Stack (most recent call last):\n  linea de pila"

    salida = observabilidad.FormateadorJson().format(registro)

    assert "\n" not in salida, "un evento, un renglón"
    assert "linea de pila" in salida
    assert '"pila"' in salida


def test_el_mapa_de_rutas_baja_a_los_routers_incluidos_y_a_los_montajes():
    """
    Las plantillas de ruta se derivan de la aplicación, no de una lista escrita a mano.

    De ese mapa sale la etiqueta `ruta` de las métricas, y es lo que impide que
    `/api/v1/leads/7` y `/api/v1/leads/8` sean dos series distintas. Si no bajara a los
    routers incluidos, todas las rutas de la API —que viven en routers con prefijo— se
    quedarían sin plantilla y la cardinalidad explotaría por el camino que el tope de
    `metricas.py` solo puede contener.
    """
    from app.main import app

    mapa = {}
    observabilidad._recolectar_plantillas(app.routes, "", mapa)

    plantillas = set(mapa.values())

    # Una plantilla CON parámetro y de dentro de un router incluido. Las dos condiciones
    # juntas, y no por separado, porque el arnés enseñó que por separado no comprueban
    # nada: `/api/v1/openapi.json` es una ruta de primer nivel —no hace falta bajar a
    # ningún router para verla— y el comodín de la SPA, `/{full_path:path}`, también lo es
    # y además lleva parámetro. Con `any(p.startswith("/api/v1/"))` y
    # `any("{" in p)` sueltas, neutralizar la recursión dejaba la prueba en verde.
    assert "/api/v1/leads/{lead_id}" in plantillas, sorted(plantillas)


# ==============================================================================
# sin_asociar.py — las dos puertas que pueden no encontrar nada
# ==============================================================================

def test_vincular_un_evento_sin_asociar_que_no_existe_es_404(client, admin_headers):
    """
    404 y no un 500 sobre un atributo de `None`. Son dos endpoints y los dos pasan por aquí.

    La bandeja de eventos sin asociar la vacían dos personas a la vez: quien vincula y quien
    descarta. Que el identificador ya no esté es lo normal, no un error del servidor.
    """
    inexistente = 99_999_999

    vincular = client.post(
        f"/api/v1/eventos-sin-asociar/{inexistente}/vincular",
        headers=admin_headers, json={"lead_id": 1},
    )
    descartar = client.delete(f"/api/v1/eventos-sin-asociar/{inexistente}", headers=admin_headers)

    assert vincular.status_code == 404, vincular.text
    assert descartar.status_code == 404, descartar.text
    assert str(inexistente) in vincular.json()["detail"]


def test_vincular_a_un_prospecto_que_no_existe_dice_que_es_el_prospecto(
    client, admin_headers, db_session
):
    """
    Dos 404 distintos en el mismo endpoint, y el mensaje dice cuál de los dos es.

    Quien vacía la bandeja necesita distinguir «ese evento ya no está» de «esa ficha no
    existe»: lo primero significa que otro lo atendió y lo segundo que se equivocó de ficha.
    Un mismo texto para los dos convierte una bandeja compartida en un juego de adivinanzas.
    """
    ahora = datetime.datetime.now(datetime.timezone.utc)
    pendiente = UnmatchedEvent(
        source="whatsapp",
        external_event_id=f"wamid.{uuid.uuid4().hex}",
        activity_type=ActivityType.WHATSAPP_MESSAGE,
        channel="WhatsApp",
        contact_email=f"nadie-{uuid.uuid4().hex[:8]}@ejemplo.mx",
        occurred_at=ahora,
        received_at=ahora,
    )
    db_session.add(pendiente)
    db_session.commit()

    respuesta = client.post(
        f"/api/v1/eventos-sin-asociar/{pendiente.id}/vincular",
        headers=admin_headers, json={"lead_id": 99_999_999},
    )

    assert respuesta.status_code == 404, respuesta.text
    assert "Prospecto" in respuesta.json()["detail"]


# ==============================================================================
# core/audit.py — el asiento de la peticion, con y sin actor
# ==============================================================================

class _SesionDeMentira:
    """Una sesion que anota lo que se le pide y puede negarse a algo concreto."""

    def __init__(self, falla_en=()):
        self.falla_en = set(falla_en)
        self.anadidas = []
        self.confirmada = False
        self.deshecha = 0

    def add(self, fila):
        if "add" in self.falla_en:
            raise RuntimeError("no se pudo escribir el asiento")
        self.anadidas.append(fila)

    def rollback(self):
        self.deshecha += 1
        if "rollback" in self.falla_en:
            raise RuntimeError("la sesion no admite deshacer")

    def commit(self):
        if "commit" in self.falla_en:
            raise RuntimeError("no se pudo confirmar")
        self.confirmada = True


def test_un_asiento_sin_actor_se_escribe_igual_y_sin_dueno():
    """
    Hay asientos que no los hace nadie: la pagina publica, un barrido, una tarea de fondo.

    El actor es opcional a proposito y la rama que lo salta no se recorria. Lo que importa
    es que el asiento SE ESCRIBE: un registro que solo guardara lo que hace una persona con
    sesion dejaria fuera justo las escrituras anonimas -la unica ruta sin sesion que escribe
    es la pagina de interes- y la bitacora diria que nadie toco nada.
    """
    sesion = _SesionDeMentira()
    asiento = audit_mod.AsientoDeAuditoria(
        accion="prueba.sin_actor", entidad="prueba", db=sesion, actor=None
    )

    asiento.anotar(entidad_id=7, detalle="algo")
    asiento.persistir()

    assert len(sesion.anadidas) == 1
    fila = sesion.anadidas[0]
    assert fila.actor_id is None
    assert fila.entity_id == "7"


def test_un_actor_cuyo_identificador_no_es_un_numero_no_impide_el_asiento():
    """
    Un `sub` que no es entero deja el asiento sin dueno, pero deja el asiento.

    Es el mismo «fallar cerrado» del alcance de cartera, por el otro lado: ahi un
    identificador irresoluble no ve nada, y aqui no firma nada. Propagar el `ValueError`
    seria perder el asiento de la operacion justo cuando el testigo viene raro, que es
    cuando mas interesa que quede escrita.
    """
    sesion = _SesionDeMentira()
    actor = CurrentUser(
        user_id="no-soy-un-numero", email="raro@plurione.com",
        name="Raro", role=UserRole.COMMERCIAL_EXECUTIVE,
    )
    asiento = audit_mod.AsientoDeAuditoria(
        accion="prueba.actor_raro", entidad="prueba", db=sesion, actor=actor
    )

    asiento.persistir()

    assert len(sesion.anadidas) == 1
    assert sesion.anadidas[0].actor_id is None


def test_si_la_sesion_no_admite_el_rollback_previo_el_asiento_se_abandona_con_apunte(caplog):
    """
    El `rollback` previo existe para que el asiento del ERROR sea el que si se escribe.

    Cuando el endpoint lanza, la sesion queda en estado fallido y el `add` siguiente moriria
    con `PendingRollbackError`: el asiento mas interesante -el del fallo- seria justo el que
    se pierde. Por eso se limpia antes. Y si ni eso se puede, se abandona con su apunte en
    lugar de propagar: esto corre en la dependencia que cierra la peticion, y lanzar ahi
    convertiria un error ya contestado en un 500 distinto.
    """
    sesion = _SesionDeMentira(falla_en=("rollback",))
    asiento = audit_mod.AsientoDeAuditoria(
        accion="prueba.sin_rollback", entidad="prueba", db=sesion, actor=None
    )

    with caplog.at_level(logging.ERROR):
        asiento.persistir()

    assert sesion.anadidas == [], "no se intenta escribir sobre una sesion que no se pudo limpiar"
    assert any("rollback previo" in r.getMessage() for r in caplog.records)


# ==============================================================================
# core/observabilidad.py — el manejador y el mapa de rutas con montajes
# ==============================================================================

def test_con_formato_json_el_manejador_instalado_escribe_json(monkeypatch):
    """
    `configurar_logging` elige el formateador, y la rama de JSON no se instalaba nunca.

    En un entorno endurecido el registro sale en JSON por linea porque es lo que un
    recolector sabe leer. Si esa rama instalara el formateador de texto, los renglones del
    servidor llegarian al recolector como texto libre: se guardan, no se consultan, y el
    problema no se ve hasta que alguien busca un incidente y no encuentra nada.

    Se restauran los manejadores al salir, porque esta funcion los SUSTITUYE en el root y
    dejarlos puestos cambiaria el registro del resto de la suite.
    """
    from app.core.config import settings

    raiz = logging.getLogger()
    antes = list(raiz.handlers)
    monkeypatch.setattr(settings, "LOG_FORMAT", "json")
    try:
        observabilidad.configurar_logging()
        instalado = logging.getLogger().handlers[0]
        assert isinstance(instalado.formatter, observabilidad.FormateadorJson)
    finally:
        raiz.handlers = antes

    monkeypatch.setattr(settings, "LOG_FORMAT", "text")
    try:
        observabilidad.configurar_logging()
        instalado = logging.getLogger().handlers[0]
        assert not isinstance(instalado.formatter, observabilidad.FormateadorJson)
    finally:
        raiz.handlers = antes


def test_el_mapa_de_rutas_baja_tambien_a_una_subaplicacion_montada():
    """
    Un montaje -archivos estaticos- es una subaplicacion, y sus rutas tambien necesitan plantilla.

    El endpoint que ve el `scope` de una peticion a un montaje es la subaplicacion, no la
    ruta del padre. Sin bajar ahi, cada archivo servido seria una serie distinta en las
    metricas: `/assets/index-a1b2.js` es un nombre con huella, asi que cada despliegue
    crearia series nuevas que no caducan nunca.

    Se monta una aplicacion de juguete en lugar de usar la del sistema porque el montaje de
    `/assets` del sistema solo existe si hay un `frontend/dist` compilado en el disco, y eso
    depende del entorno: en el CI no lo hay. Una prueba que dependiera de eso pasaria aqui y
    no alla.
    """
    from fastapi import FastAPI

    hija = FastAPI()

    @hija.get("/fichero/{nombre}")
    def _un_fichero(nombre: str):  # pragma: no cover - no se invoca, solo se declara
        return nombre

    padre = FastAPI()
    padre.mount("/estaticos", hija)

    @padre.get("/propia/{identificador}")
    def _propia(identificador: str):  # pragma: no cover - idem
        return identificador

    mapa = {}
    observabilidad._recolectar_plantillas(padre.routes, "", mapa)

    plantillas = set(mapa.values())
    assert "/propia/{identificador}" in plantillas
    # La plantilla de DENTRO del montaje, con el prefijo del padre delante. Comprobar solo
    # que algo empieza por «/estaticos» no distinguía bajar a la subaplicación de apuntar
    # el montaje como hoja: un `Mount` tiene `.app`, así que sin la recursión se habría
    # registrado igual con su propio camino. Lo dijo el arnés.
    assert "/estaticos/fichero/{nombre}" in plantillas, sorted(plantillas)


# ==============================================================================
# core/redes.py — una red que no esta en la tabla
# ==============================================================================

def test_una_red_desconocida_recibe_el_texto_entero_sin_recortar():
    """
    Sin entrada en la tabla no hay tope que aplicar, asi que no se recorta.

    Recortar por un tope inventado seria peor que no recortar: el texto saldria mutilado por
    una regla que no existe. Y la rama se alcanza de verdad -no es defensiva- porque
    `texto_para` recibe la red tal como venga: una publicacion con una red que se retiro de
    la tabla sigue en la base con ese valor.
    """
    descripcion = "Una descripcion larga de verdad, con bastantes palabras, que no se recorta."

    texto = redes.texto_para("una-red-retirada", descripcion, "slug-4")

    assert texto.startswith(descripcion)
    assert texto.endswith(redes.enlace_publico("slug-4"))
    assert "\n\n" in texto


# ==============================================================================
# ciclo_de_publicaciones.py — la visita que compite con otra visita
# ==============================================================================

def test_dos_visitas_simultaneas_al_mismo_dia_y_red_suman_dos(db_session, monkeypatch):
    """
    La carrera del contador de visitas, provocada metiendo la fila en el hueco.

    `registrar_visita` suma primero y crea solo si no habia fila. Entre comprobar que no hay
    y crearla caben dos visitas: la pagina de interes es publica y la abren varias personas
    a la vez. La segunda inserccion choca con la clave y lo que hace el `except` es volver a
    SUMAR, no suponer nada.

    Sin ese reintento, una de las dos visitas se perderia -que seria tolerable- pero ademas
    el `IntegrityError` subiria hasta la peticion y la pagina publica contestaria un 500 a
    quien solo queria leerla. Eso no es tolerable: es la unica ruta sin sesion del sistema.

    La fila que compite se mete al construir la nueva, que es el instante exacto en que lo
    haria otra peticion.
    """
    campana = Campaign(name=f"Carrera {uuid.uuid4().hex[:6]}", channel="LinkedIn")
    db_session.add(campana)
    db_session.commit()
    # El dia es el de UTC y NO el local, porque es el que escribe `registrar_visita`. Con
    # `date.today()` esta prueba pasaba dieciocho horas al dia y fallaba las otras seis: a
    # las 22:57 en un huso UTC-6 el dia local es el 7 y el de la fila es el 8. La escribi
    # con el local y la vi fallar al anochecer, que es exactamente la forma en que una
    # prueba con la hora mal elegida engana -verde toda la jornada de trabajo-.
    hoy = ciclo.utc_now().date()
    Visita = ciclo.VisitaDePublicacion

    # La fila de la otra visita ya esta: es la que gano la carrera.
    ciclo.registrar_visita(db_session, campana)
    assert db_session.query(Visita).filter(Visita.campaign_id == campana.id).one().visitas == 1

    # Y la suma de ESTA pasada falla una vez, que es lo que le pasa a la peticion que corrio
    # su UPDATE antes de que la otra confirmara: no encuentra fila, intenta crearla, y
    # choca. Fallar la comprobacion previa UNA sola vez es el procedimiento que ya usa
    # `test_la_red_del_alta_tambien_nombra_el_campo`; el `except` que se mide es intacto.
    ejecutar = db_session.execute
    fallos = {"restantes": 1}

    class SinFilas:
        rowcount = 0

    def no_encuentra_la_primera_vez(sentencia, *args, **kwargs):
        if fallos["restantes"] and getattr(sentencia, "is_update", False):
            fallos["restantes"] -= 1
            return SinFilas()
        return ejecutar(sentencia, *args, **kwargs)

    monkeypatch.setattr(db_session, "execute", no_encuentra_la_primera_vez)

    ciclo.registrar_visita(db_session, campana)

    assert fallos["restantes"] == 0, "la suma tiene que haber fallado una vez"
    monkeypatch.undo()
    total = db_session.query(Visita).filter(
        Visita.campaign_id == campana.id, Visita.dia == hoy
    ).one()
    assert total.visitas == 2, "se suma sobre la fila de la otra, no se pierde la visita"


def test_un_aviso_que_el_embudo_rechaza_devuelve_la_fila_a_la_bandeja(
    client, admin_headers, db_session, sample_lead
):
    """
    Vincular un aviso que el embudo rechaza es 422, y el aviso SIGUE en la bandeja.

    `vincular_evento_sin_asociar` retira la fila antes de registrar -si no, el propio aviso
    contaria como duplicado de si mismo- y todo va en la misma transaccion. Esa decision
    solo significa algo si el rechazo deshace la retirada, y ese camino no lo recorria nadie:
    un aviso que se pierde al intentar vincularlo es un dato de contacto que llego de fuera y
    desaparece sin quedar en ninguna parte.

    Se provoca con una fecha en el futuro, que es uno de los catorce rechazos del embudo y
    el unico que se puede escribir en la bandeja sin tocar nada mas.
    """
    manana = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=2)
    pendiente = UnmatchedEvent(
        source="whatsapp",
        external_event_id=f"wamid.{uuid.uuid4().hex}",
        activity_type=ActivityType.WHATSAPP_MESSAGE,
        channel="WhatsApp",
        contact_phone="+525599998888",
        occurred_at=manana,
        received_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(pendiente)
    db_session.commit()
    identificador = pendiente.id

    respuesta = client.post(
        f"/api/v1/eventos-sin-asociar/{identificador}/vincular",
        headers=admin_headers, json={"lead_id": sample_lead.id},
    )

    assert respuesta.status_code == 422, respuesta.text
    detalle = respuesta.json()["detail"]
    assert "campo" in detalle and "motivo" in detalle
    # Y la fila no se perdio: la transaccion la devolvio a la bandeja.
    db_session.expire_all()
    assert db_session.get(UnmatchedEvent, identificador) is not None


def test_el_mapa_de_rutas_salta_lo_que_no_sabe_leer_y_sigue():
    """
    Un objeto de ruta que no tiene ni endpoint ni camino se salta, no revienta el mapa.

    Las clases de ruta de Starlette cambian entre versiones -`Mount`, `WebSocketRoute`, los
    envoltorios de `include_router`- y esta funcion las lee con `getattr` precisamente para
    no depender de cuales existan hoy. La rama que salta lo desconocido es lo que hace que
    una version nueva de la biblioteca no deje el sistema sin metricas: sin ella, un tipo de
    ruta inesperado seria un `AttributeError` en el arranque.

    Y se comprueba que el bucle SIGUE despues del salto: con una ruta legible detras de una
    ilegible, la legible tiene que acabar en el mapa.
    """
    from fastapi import FastAPI

    legible = FastAPI()

    @legible.get("/despues/{algo}")
    def _despues(algo: str):  # pragma: no cover - solo se declara
        return algo

    mapa = {}
    observabilidad._recolectar_plantillas(
        [object(), *legible.routes], "", mapa
    )

    assert "/despues/{algo}" in set(mapa.values())


# ==============================================================================
# services/desenlaces.py — los bordes del panel de desenlaces
# ==============================================================================

def test_un_cierre_anterior_al_alta_del_prospecto_se_rechaza(db_session, sample_lead):
    """
    No se puede cerrar una venta antes de que la ficha exista.

    La fecha de cierre la escribe una persona en un formulario, asi que un dedazo en el ano
    es lo normal. Y de esta fecha cuelgan las etiquetas de entrenamiento del modelo: un
    cierre con fecha anterior al alta produce un caso cuyo vector de entrada se capturo
    DESPUES del desenlace que lo etiqueta, que es exactamente la fuga temporal que invalida
    un modelo entrenado con el.
    """
    from app.schemas.desenlaces import CierreDelProspecto
    from app.services.desenlaces import CierreInvalido, registrar_cierre

    sample_lead.created_at = datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc)
    db_session.commit()
    cierre = CierreDelProspecto(
        resultado="perdido", motivo="precio",
        cerrado_el=datetime.date(2026, 1, 15),
    )

    with pytest.raises(CierreInvalido) as fallo:
        registrar_cierre(db_session, sample_lead, cierre)

    assert "anterior al alta" in str(fallo.value)


def test_el_alta_de_una_ficha_no_puede_faltar(db_session, sample_lead):
    """
    La premisa del `pragma` de `registrar_cierre`, derivada de la columna y no escrita a mano.

    La prueba que se quiso escribir aqui era la otra salida de `if alta is not None` —cerrar
    una ficha sin fecha de alta—, y **no se puede escribir**: `leads.created_at` es
    `NOT NULL`, asi que el motor rechaza el `UPDATE` que la pondria a nulo. La rama no es
    codigo muerto -la comparacion de debajo con un `None` seria un `TypeError` dentro del
    cierre, que es lo que escribe las etiquetas del modelo- pero no hay forma de recorrerla
    sin romper el esquema, asi que queda marcada con su motivo y la premisa queda aqui.

    Se deriva de la columna: si alguien la hiciera opcional, esto se pone rojo y entonces hay
    que decidir si la marca sigue valiendo o si la rama necesita prueba.
    """
    from app.models.entities import Lead as ModeloLead
    from sqlalchemy.exc import IntegrityError

    assert ModeloLead.__table__.c.created_at.nullable is False

    sample_lead.created_at = None
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
