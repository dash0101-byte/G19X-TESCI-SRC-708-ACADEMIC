"""
Las dieciocho claves ajenas del esquema, y lo que cada una dice que pasa al borrar.

Hasta el capítulo 42 ninguna prueba de la aplicación las ejercitaba, y no por descuido: el
motor no las comprobaba. `PRAGMA foreign_keys` nace apagado en SQLite y hay que encenderlo
en cada conexión, y el único sitio del repositorio donde estaba escrito eran tres pruebas de
migración. La suite entera daba el mismo resultado con el pragma y sin él —1587 pasadas y 2
omitidas—, que es la forma más silenciosa que tiene una clase de fallo de no existir para
nadie: ninguna prueba escribía una clave que no apuntara a nada, así que nadie notaba que
tampoco se podía.

Lo que se comprueba aquí
------------------------
1. Que el motor de la suite las comprueba. Es una línea y es la que sostiene el resto del
   archivo: si alguien quitara el `event.listens_for` de `app.core.database`, estas pruebas
   seguirían pasando **sin comprobar nada**, que es la peor forma de guarda que hay.
2. Que las dieciocho siguen siendo dieciocho y declarando lo que declaran. La lista sale del
   esquema y se compara con el inventario de abajo: una tabla nueva, una clave ajena nueva o
   un `ondelete` cambiado nacen en rojo, y entonces alguien decide.
3. Que el motor hace lo que la cláusula dice, clave por clave y construyendo las filas desde
   la propia tabla. Varias llevan la frase escrita en el modelo —«si la cuenta desaparece, su
   lista de tareas se va con ella»— y hasta ahora era una frase.
4. Que el borrado de una ficha no depende de ninguna de las dieciocho: pasa por el mapa de
   `derechos_del_titular`, que la Fase 14 escribió precisamente porque fiarse de las cascadas
   dejaba atrás las entregas de webhook y el correo dentro de la bitácora.
"""
import datetime

import pytest
import sqlalchemy as sa
from app.core import integridad
from app.core.database import Base, engine
from app.models.entities import Campaign, Lead, ScoreCategory, ScoreHistory, User

# Clave ajena → qué dice que pasa cuando se borra la fila a la que apunta.
#
# Escrito a mano **a propósito**, y es el único sitio de este capítulo donde algo se escribe
# a mano: una lista derivada del esquema y comparada con el esquema no comprueba nada. Lo que
# esto fija es la decisión, para que cambiarla sea un cambio visible en una revisión.
CLAUSULAS = {
    ("avisos", "usuario_id"): "CASCADE",
    ("avisos", "lead_id"): "CASCADE",
    ("campaigns", "responsable_id"): "SET NULL",
    ("crm_integration_logs", "lead_id"): "CASCADE",
    ("desenlaces", "lead_id"): "CASCADE",
    ("desenlaces", "score_history_id"): "SET NULL",
    ("desenlaces", "registrado_por_id"): "SET NULL",
    ("lead_activities", "lead_id"): "CASCADE",
    ("leads", "assigned_rep_id"): "SET NULL",
    ("leads", "campaign_id"): "SET NULL",
    ("refresh_tokens", "user_id"): "CASCADE",
    ("score_histories", "lead_id"): "CASCADE",
    ("score_history_monthly", "lead_id"): "CASCADE",
    ("tareas", "lead_id"): "CASCADE",
    ("tareas", "asesor_id"): "CASCADE",
    ("tareas", "cerrada_por_id"): "SET NULL",
    ("visitas_de_publicacion", "campaign_id"): "CASCADE",
    ("webhook_deliveries", "lead_id"): "SET NULL",
}


def claves_del_esquema():
    """Cada clave ajena de cada tabla, como `(tabla, columna, destino, ondelete)`."""
    encontradas = []
    for tabla in Base.metadata.sorted_tables:
        for columna in tabla.columns:
            for ajena in columna.foreign_keys:
                encontradas.append(
                    (tabla.name, columna.name, ajena.column.table.name, ajena.ondelete)
                )
    return sorted(encontradas)


# ==============================================================================
# El motor de la suite
# ==============================================================================

def test_el_motor_de_las_pruebas_comprueba_las_claves_ajenas(db_session):
    """
    La línea de la que depende todo lo demás de este archivo.

    Sin ella, SQLite acepta una ficha que apunta a una campaña que no existe y no arrastra
    ningún hijo al borrar un padre: las pruebas de abajo pasarían igual y no comprobarían
    nada. Es el caso del capítulo 41 al revés —allí una guarda que no se podía hacer fallar;
    aquí una comprobación que el motor no hacía— y la lección es la misma.
    """
    assert db_session.execute(sa.text("PRAGMA foreign_keys")).scalar() == 1


def test_una_fila_no_puede_apuntar_a_una_que_no_existe(db_session):
    lead = Lead(
        first_name="Clave", last_name="Ajena", email="clave.ajena@ejemplo.com",
        source="Website", campaign_id=999999,
    )
    db_session.add(lead)
    with pytest.raises(sa.exc.IntegrityError):
        db_session.commit()
    db_session.rollback()


# ==============================================================================
# El inventario
# ==============================================================================

def test_las_claves_ajenas_del_esquema_son_las_inventariadas():
    del_esquema = {(tabla, columna) for tabla, columna, _, _ in claves_del_esquema()}
    assert del_esquema == set(CLAUSULAS), (
        "El esquema y el inventario de este archivo no dicen lo mismo. Una clave ajena "
        "nueva necesita una decisión sobre qué pasa al borrar su destino, y una que "
        "desaparece necesita que alguien compruebe que nada dependía de ella."
    )


@pytest.mark.parametrize("tabla,columna,destino,ondelete", claves_del_esquema())
def test_cada_clave_declara_la_clausula_inventariada(tabla, columna, destino, ondelete):
    assert ondelete == CLAUSULAS[(tabla, columna)], (
        f"{tabla}.{columna} apunta a {destino} con ondelete={ondelete}, y el inventario "
        f"dice {CLAUSULAS[(tabla, columna)]}."
    )


def test_el_numero_no_cambia_sin_que_se_vea():
    """
    Dieciocho, once en cascada y siete a nulo.

    El número está escrito en el Reporte 40 y en §6.4, y un número en un informe que nadie
    comprueba envejece sin avisar.
    """
    clausulas = list(CLAUSULAS.values())
    assert len(CLAUSULAS) == 18
    assert clausulas.count("CASCADE") == 11
    assert clausulas.count("SET NULL") == 7


# ==============================================================================
# Lo que la cláusula dice que pasa
# ==============================================================================

def _valor_sintetico(columna):
    """
    Algo que quepa en esa columna, mirando su tipo.

    Las filas de estas pruebas se construyen desde la tabla y no a mano: son diecinueve
    claves ajenas en dieciséis tablas, y una fila escrita a mano por cada una envejece en la
    primera columna obligatoria que se añada. Lo que importa de la fila no es su contenido,
    es que exista y apunte a donde apunta.
    """
    tipo = columna.type
    if isinstance(tipo, sa.Enum):
        return tipo.enums[0]
    if isinstance(tipo, (sa.String, sa.Text)):
        return "x"
    if isinstance(tipo, sa.Boolean):
        return False
    if isinstance(tipo, sa.Integer):
        return 1
    if isinstance(tipo, (sa.Float, sa.Numeric)):
        return 0.0
    if isinstance(tipo, sa.DateTime):
        return datetime.datetime.now(datetime.timezone.utc)
    if isinstance(tipo, sa.Date):
        return datetime.date.today()
    if isinstance(tipo, sa.JSON):
        return {}
    raise AssertionError(f"Falta un valor sintético para {columna.name}: {tipo!r}")


def _insertar(db, tabla, padres, *, destacada=None, otros=None):
    """
    Una fila mínima en `tabla`, con cada clave ajena apuntando al padre que le toque.

    Devuelve su clave primaria. Las columnas con valor por omisión se dejan en paz: el
    motor y el modelo ya saben qué poner, y sobrescribirlas sería inventar.

    `destacada` y `otros` existen por un caso que el esquema tiene y que al escribir esto no
    estaba previsto: una tabla puede apuntar **dos veces a la misma tabla** con cláusulas
    distintas. `tareas` apunta a `users` con `asesor_id` en cascada y con `cerrada_por_id` a
    nulo, así que borrar la cuenta se lleva la tarea entera por la primera y no deja ver lo
    que hace la segunda. Con `otros`, las demás claves apuntan a otra familia de filas y la
    que se está probando queda sola frente al borrado.
    """
    valores = {}
    for columna in tabla.columns:
        # Una clave primaria de una sola columna la pone el motor. `autoincrement` no sirve
        # para decidirlo —vale `'auto'` y no `True`—, y darle un valor sintético chocaba con
        # la fila que el fixture acababa de crear. Una clave compuesta es otra cosa y hay que
        # escribirla entera: la de `visitas_de_publicacion` es `(campaign_id, dia, red)`, y
        # ninguna de las tres la pone nadie.
        if columna.primary_key and len(tabla.primary_key.columns) == 1:
            continue
        if columna.foreign_keys:
            destino = next(iter(columna.foreign_keys)).column.table.name
            de_quien = padres if (otros is None or columna.name == destacada) else otros
            valores[columna.name] = de_quien[destino]
            continue
        if columna.nullable or columna.default is not None or columna.server_default is not None:
            continue
        valores[columna.name] = _valor_sintetico(columna)
    resultado = db.execute(sa.insert(tabla).values(**valores))
    db.commit()
    clave = list(tabla.primary_key.columns)[0]
    if resultado.inserted_primary_key and resultado.inserted_primary_key[0] is not None:
        return resultado.inserted_primary_key[0]
    return db.execute(sa.select(clave).order_by(clave.desc()).limit(1)).scalar()


def _familia(db, etiqueta):
    """
    Una fila en cada tabla a la que apunta alguna clave ajena, para colgar hijos de ellas.

    Se crean con el ORM —no con los `INSERT` de arriba— porque son las cuatro tablas con
    valores por omisión del modelo y con la lógica de arranque de una fila de verdad.
    """
    usuario = User(
        email=f"cascada.{etiqueta}@plurione.com", full_name=f"Cascada {etiqueta}",
        role="Commercial_Executive", hashed_password="!sin-contrasena:prueba",
        is_sales_rep=True,
    )
    campana = Campaign(name=f"Cascada {etiqueta}", channel="Organic", budget=0.0)
    db.add_all([usuario, campana])
    db.commit()
    lead = Lead(
        first_name="Cascada", last_name=etiqueta, email=f"cascada.{etiqueta}@ejemplo.com",
        source="Website", assigned_rep_id=usuario.id, campaign_id=campana.id,
    )
    db.add(lead)
    db.commit()
    historial = ScoreHistory(lead_id=lead.id, score=50.0, score_category=ScoreCategory.WARM)
    db.add(historial)
    db.commit()
    return {
        "users": usuario.id,
        "campaigns": campana.id,
        "leads": lead.id,
        "score_histories": historial.id,
    }


@pytest.fixture
def padres(db_session):
    return _familia(db_session, "una")


@pytest.fixture
def otra_familia(db_session):
    """
    Un segundo juego de padres, para las claves que conviven con otra hacia la misma tabla.

    Ver el porqué en `_insertar`: sin esto, la cláusula `SET NULL` de `tareas.cerrada_por_id`
    no se puede observar, porque la cascada de `asesor_id` se lleva la fila antes.
    """
    return _familia(db_session, "otra")


def _cuantas(db, tabla, columna, valor):
    return db.execute(
        sa.select(sa.func.count()).select_from(tabla).where(tabla.c[columna] == valor)
    ).scalar()


CASCADAS = sorted(clave for clave, modo in CLAUSULAS.items() if modo == "CASCADE")
A_NULO = sorted(clave for clave, modo in CLAUSULAS.items() if modo == "SET NULL")


@pytest.mark.parametrize("tabla,columna", CASCADAS)
def test_borrar_el_destino_se_lleva_la_fila(db_session, padres, tabla, columna):
    """La cláusula dice CASCADE; se borra el padre y se cuenta."""
    hija = Base.metadata.tables[tabla]
    destino = next(iter(hija.c[columna].foreign_keys)).column
    valor = padres[destino.table.name]
    _insertar(db_session, hija, padres)
    # «Al menos una» y no «exactamente una»: alguna de estas tablas ya tiene su fila por el
    # fixture —el historial de puntuación del prospecto—, y lo que se comprueba es que al
    # borrar el padre no quede ninguna.
    assert _cuantas(db_session, hija, columna, valor) >= 1

    db_session.execute(sa.delete(destino.table).where(destino == valor))
    db_session.commit()
    assert _cuantas(db_session, hija, columna, valor) == 0


@pytest.mark.parametrize("tabla,columna", A_NULO)
def test_borrar_el_destino_deja_la_columna_en_nulo(
    db_session, padres, otra_familia, tabla, columna
):
    """La cláusula dice SET NULL; la fila sobrevive y pierde la referencia."""
    hija = Base.metadata.tables[tabla]
    destino = next(iter(hija.c[columna].foreign_keys)).column
    clave_de_la_hija = _insertar(
        db_session, hija, padres, destacada=columna, otros=otra_familia
    )
    valor = padres[destino.table.name]

    db_session.execute(sa.delete(destino.table).where(destino == valor))
    db_session.commit()

    columna_clave = list(hija.primary_key.columns)[0]
    quedo = db_session.execute(
        sa.select(hija.c[columna]).where(columna_clave == clave_de_la_hija)
    ).first()
    assert quedo is not None, f"{tabla} no debía desaparecer: su cláusula es SET NULL."
    assert quedo[0] is None


# ==============================================================================
# El borrado de una ficha no usa ninguna de las diecinueve
# ==============================================================================

def test_suprimir_una_ficha_no_depende_de_las_cascadas(client, admin_headers, db_session, padres):
    """
    El borrado recorre el mapa de `derechos_del_titular`, y por eso se lleva también lo que
    ninguna cascada se llevaría: las entregas de webhook, que declaran `SET NULL`.

    La Fase 14 lo cambió en el endpoint y dejó `LeadRepository.delete` con el borrado
    retirado, que es el resto que el capítulo 42 recoge. Esta prueba sirve para las dos
    puertas: el endpoint usa el mapa, y el método del repositorio delega en él.
    """
    from app.models.entities import WebhookDelivery

    lead_id = padres["leads"]
    ahora = datetime.datetime.now(datetime.timezone.utc)
    db_session.add(WebhookDelivery(
        signature="firma-de-la-cascada", idempotency_key="clave-de-la-cascada",
        crm_platform="HubSpot", event="lead.created", lead_id=lead_id,
        received_at=ahora, expires_at=ahora + datetime.timedelta(hours=1), response_data={},
    ))
    db_session.commit()
    entregas = Base.metadata.tables["webhook_deliveries"]
    assert _cuantas(db_session, entregas, "lead_id", lead_id) == 1

    respuesta = client.delete(f"/api/v1/leads/{lead_id}", headers=admin_headers)
    assert respuesta.status_code == 204
    db_session.expire_all()
    assert _cuantas(db_session, entregas, "lead_id", lead_id) == 0


def test_el_metodo_del_repositorio_borra_por_el_mismo_sitio(db_session, padres):
    """
    Y se comprueba con la entrega de webhook, que es lo que distingue los dos borrados.

    El arnés de reintroducción encontró que devolver este método a su `db.delete(lead)` no
    ponía nada rojo mientras la prueba mirara las tareas: con las claves ajenas encendidas, la
    cascada del motor también se las lleva. Lo que **ninguna cascada** se lleva es la entrega
    de webhook, porque su cláusula es `SET NULL`: la fila sobrevive con el prospecto a nulo.
    Es exactamente lo que la Fase 14 encontró al escribir el mapa —«el borrado dejaba cosas
    atrás: las entregas de webhook»—, así que es lo que hay que mirar para saber por dónde
    pasó el borrado.
    """
    from app.core.autorizacion import AlcanceDeCartera
    from app.models.entities import WebhookDelivery
    from app.repositories.lead_repository import LeadRepository

    lead_id = padres["leads"]
    tareas = Base.metadata.tables["tareas"]
    entregas = Base.metadata.tables["webhook_deliveries"]
    _insertar(db_session, tareas, padres)
    ahora = datetime.datetime.now(datetime.timezone.utc)
    db_session.add(WebhookDelivery(
        signature="firma-del-repositorio", idempotency_key="clave-del-repositorio",
        crm_platform="HubSpot", event="lead.created", lead_id=lead_id,
        received_at=ahora, expires_at=ahora + datetime.timedelta(hours=1), response_data={},
    ))
    db_session.commit()
    assert _cuantas(db_session, tareas, "lead_id", lead_id) == 1
    assert _cuantas(db_session, entregas, "lead_id", lead_id) == 1

    repo = LeadRepository(db_session, AlcanceDeCartera.del_sistema("prueba de la cascada"))
    assert repo.delete(lead_id) is True
    db_session.expire_all()
    assert _cuantas(db_session, tareas, "lead_id", lead_id) == 0
    assert _cuantas(db_session, Base.metadata.tables["leads"], "id", lead_id) == 0
    assert db_session.execute(sa.select(sa.func.count()).select_from(entregas)).scalar() == 0, (
        "La entrega de webhook sigue ahí con el prospecto a nulo: este borrado se fió de "
        "las cascadas en vez de recorrer el mapa de los derechos del titular."
    )


def test_borrar_lo_que_no_esta_dice_que_no_esta(db_session):
    from app.core.autorizacion import AlcanceDeCartera
    from app.repositories.lead_repository import LeadRepository

    repo = LeadRepository(db_session, AlcanceDeCartera.del_sistema("prueba de la cascada"))
    assert repo.delete(999999) is False


# ==============================================================================
# Lo que el módulo de integridad saca del esquema
# ==============================================================================

def test_toda_tabla_de_destino_tiene_nombre_en_castellano():
    """
    El mensaje de «no existe» lo lee una persona, así que la tabla necesita un nombre.

    Sin esta prueba, una clave ajena nueva hacia una tabla sin nombre reventaría con un
    `KeyError` dentro del `except` que estaba explicando otro error, que es el peor sitio
    posible para fallar.
    """
    destinos = {destino for _, _, destino, _ in claves_del_esquema()}
    assert destinos <= set(integridad.NOMBRE_DE_LA_TABLA)


def test_el_motor_no_acepta_lo_que_el_esquema_declara_unico(db_session, padres):
    """
    Las restricciones únicas sí se comprobaban, y conviene que esto quede escrito al lado.

    Es la diferencia que hacía que el `except` de la edición pareciera suficiente: la única
    regla que el motor hacía cumplir en las pruebas era justo la que ese `except` suponía.
    """
    ya_registrado = db_session.execute(
        sa.select(Base.metadata.tables["leads"].c.email).where(
            Base.metadata.tables["leads"].c.id == padres["leads"]
        )
    ).scalar()
    db_session.add(Lead(
        first_name="Repetida", last_name="Prueba", email=ya_registrado, source="Website",
    ))
    with pytest.raises(sa.exc.IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_el_pragma_vale_para_todas_las_conexiones_del_motor():
    """
    No solo para la de la sesión de pruebas: el pragma es por conexión y el oyente está
    atado al motor, que es lo que hace que no haya que acordarse en cada sitio.
    """
    with engine.connect() as conexion:
        assert conexion.execute(sa.text("PRAGMA foreign_keys")).scalar() == 1
