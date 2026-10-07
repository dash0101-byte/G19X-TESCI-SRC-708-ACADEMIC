"""
El sello que impide servir sobre una base sin migrar, y la sesión que abre cada petición.

`core/database.py` era el peor archivo medido del paquete —50,6 % contando ramas— y lo que
le faltaba no era decoración: `verificar_esquema`, `revision_aplicada`, `revision_esperada`
y `_directorio_alembic` no aparecían en una sola prueba de las 1743. Son lo que sustituye a
`create_all()` en producción: si dejan de funcionar, el backend arranca contra una base de
otra revisión, sirve tráfico y falla con `UndefinedColumn` en la primera petición que toque
la columna que falta —a veces horas después y solo en un endpoint—. Eso es exactamente el
fallo que el sello existe para convertir en un mensaje único al arrancar.

Y `get_db()` no se ejecutaba nunca: `conftest.py` la sustituye por una fixture en
`dependency_overrides`, así que la dependencia real de todas las peticiones de la
aplicación —la que abre la sesión y la cierra— no la probaba nadie. Una sesión que no se
cierra retiene su conexión del pool; con el pool acotado de la pila, eso es el servicio
parado tras unos cientos de peticiones.

Las dos revisiones que se usan aquí para comparar (`aplicada` y `esperada`) se sustituyen
por sus valores, nunca la función que las compara: lo que se prueba es la decisión, no una
copia de la decisión.
"""
import logging
import re
from pathlib import Path

import pytest
from app.core import database
from app.core.config import settings
from app.core.database import (
    EsquemaDesactualizado,
    get_db,
    revision_aplicada,
    revision_esperada,
    verificar_esquema,
)
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

VERSIONES = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _base_aparte():
    """Una base en memoria propia, para no tocar la que comparte el resto de la suite."""
    return create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )


# ==============================================================================
# La dependencia que abre y cierra la sesión de cada petición
# ==============================================================================

def test_la_dependencia_de_sesion_entrega_una_sesion_viva_y_la_cierra_al_salir():
    """
    Lo que recibe cada endpoint, y lo que pasa cuando la petición termina.

    Se comprueba sobre la transacción de la propia sesión: abierta mientras se usa, cerrada
    al agotar el generador. Si el `finally` desapareciera, la sesión seguiría viva con su
    conexión retenida y nada en la respuesta lo delataría.
    """
    generador = get_db()
    sesion = next(generador)

    assert isinstance(sesion, Session)
    assert sesion.execute(text("SELECT 1")).scalar() == 1
    assert sesion.get_transaction() is not None

    with pytest.raises(StopIteration):
        next(generador)

    assert sesion.get_transaction() is None, "la sesión se quedó abierta al terminar"


def test_la_dependencia_de_sesion_cierra_tambien_cuando_la_peticion_revienta():
    """
    El `finally` está para el camino malo, que es el que importa.

    Un 500 en un endpoint propaga la excepción a través del generador de la dependencia. Si
    el cierre colgara del camino feliz, cada error dejaría una conexión retenida: el
    servicio se degradaría justo cuando ya está fallando.
    """
    generador = get_db()
    sesion = next(generador)
    sesion.execute(text("SELECT 1"))

    with pytest.raises(RuntimeError):
        generador.throw(RuntimeError("la petición falló"))

    assert sesion.get_transaction() is None


# ==============================================================================
# Dónde están las migraciones: el árbol de fuentes y la imagen no coinciden
# ==============================================================================

def test_el_directorio_de_migraciones_se_encuentra_en_el_arbol_de_fuentes():
    """Sin patch de ninguna clase: la disposición real del repositorio tiene que valer."""
    encontrado = Path(database._directorio_alembic())

    assert encontrado.name == "alembic"
    assert (encontrado / "versions").is_dir()


def test_el_directorio_de_migraciones_se_busca_tambien_en_la_disposicion_de_la_imagen(
    monkeypatch, tmp_path
):
    """
    Dos candidatos porque la imagen no replica el árbol: en ella `app` cuelga de `/app` y
    las migraciones quedan en `/app/alembic`; en el repositorio cuelgan de `backend/`.

    Se comprueba que el segundo candidato se llega a mirar, que es lo que se rompe si el
    bucle se convierte en una sola comprobación: funcionaría en local y fallaría al
    arrancar la imagen.
    """
    sin_migraciones = tmp_path / "primero"
    sin_migraciones.mkdir()
    con_migraciones = tmp_path / "segundo"
    (con_migraciones / "versions").mkdir(parents=True)
    monkeypatch.setattr(
        database, "_CANDIDATOS_ALEMBIC", (str(sin_migraciones), str(con_migraciones))
    )

    assert database._directorio_alembic() == str(con_migraciones)


def test_si_no_hay_migraciones_en_ningun_candidato_se_dice_donde_se_busco(monkeypatch, tmp_path):
    """
    El mensaje lleva las dos rutas miradas.

    Es lo único que hay para diagnosticar una imagen mal construida: sin las rutas, el
    error dice que no encuentra las migraciones y no dice dónde las buscó.
    """
    candidatos = (str(tmp_path / "ni-aqui"), str(tmp_path / "ni-aqui-tampoco"))
    monkeypatch.setattr(database, "_CANDIDATOS_ALEMBIC", candidatos)

    with pytest.raises(RuntimeError) as fallo:
        database._directorio_alembic()

    for candidato in candidatos:
        assert candidato in str(fallo.value)


# ==============================================================================
# Las dos revisiones que se comparan
# ==============================================================================

def test_una_base_sin_migrar_dice_que_no_tiene_ninguna_revision():
    """
    La base de la suite se crea con `create_all`, así que no tiene tabla de versiones.

    Es el caso que distingue «base nueva» de «base vieja», y el que decide cuál de los dos
    mensajes de ayuda se da.
    """
    assert revision_aplicada() is None


def test_la_revision_aplicada_se_lee_de_la_base_y_no_de_una_constante(monkeypatch):
    """
    Sobre una base propia con la tabla de versiones escrita a mano.

    Si esta función devolviera algo fijo —o siempre None—, el sello compararía mal y dejaría
    pasar justo lo que tiene que parar. La única forma de comprobar que lee de verdad es
    escribir una revisión que no exista en el repositorio y pedir que la devuelva.
    """
    motor = _base_aparte()
    with motor.begin() as conexion:
        conexion.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        conexion.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0ffc1a1')"))
    monkeypatch.setattr(database, "engine", motor)

    try:
        assert revision_aplicada() == "0ffc1a1"
    finally:
        motor.dispose()


def _cabezas_escritas_en_el_repositorio() -> set:
    """
    Las cabezas de la cadena, derivadas de los ficheros y no de una lista escrita a mano.

    Una cabeza es una revisión que ningún otro fichero declara como su `down_revision`.
    """
    revisiones, anteriores = set(), set()
    for fichero in VERSIONES.glob("*.py"):
        texto = fichero.read_text(encoding="utf-8")
        propia = re.search(r"^revision(?::[^=]+)?\s*=\s*[\"']([^\"']+)[\"']", texto, re.M)
        if propia:
            revisiones.add(propia.group(1))
        anterior = re.search(r"^down_revision(?::[^=]+)?\s*=\s*[\"']([^\"']+)[\"']", texto, re.M)
        if anterior:
            anteriores.add(anterior.group(1))
    return revisiones - anteriores


def test_el_codigo_espera_la_unica_cabeza_escrita_en_las_migraciones():
    """
    Dos cosas de una vez: que la cadena tenga una sola cabeza y que sea la que se espera.

    Con dos cabezas, `get_current_head()` no devuelve ninguna: levanta `MultipleHeads` y el
    arranque de un entorno endurecido muere ahí, con un error de Alembic que no menciona
    esta función. Pasa con dos ramas de trabajo que escriben una migración cada una sobre
    la misma anterior, y no lo nota nadie hasta el despliegue.
    """
    cabezas = _cabezas_escritas_en_el_repositorio()

    assert len(cabezas) == 1, f"la cadena de migraciones tiene {len(cabezas)} cabezas: {cabezas}"
    assert revision_esperada() == cabezas.pop()


def test_la_revision_esperada_sale_de_los_ficheros_y_no_de_una_constante(monkeypatch, tmp_path):
    """
    Sobre una cadena de dos revisiones inventadas, en un directorio aparte.

    Comparar contra la cabeza real del repositorio no distingue entre leer el directorio y
    devolver la cadena de hoy escrita a mano: las dos cosas aciertan hasta que alguien
    añade una migración. Con una cadena que no existe en ningún sitio, acertar solo es
    posible leyéndola.
    """
    versiones = tmp_path / "alembic" / "versions"
    versiones.mkdir(parents=True)
    (versiones / "primera.py").write_text(
        'revision = "a0a0a0a0"\ndown_revision = None\n'
        "def upgrade(): pass\ndef downgrade(): pass\n",
        encoding="utf-8",
    )
    (versiones / "segunda.py").write_text(
        'revision = "b1b1b1b1"\ndown_revision = "a0a0a0a0"\n'
        "def upgrade(): pass\ndef downgrade(): pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(database, "_directorio_alembic", lambda: str(tmp_path / "alembic"))

    assert revision_esperada() == "b1b1b1b1"


# ==============================================================================
# El sello: lo que decide si se sirve o no se sirve
# ==============================================================================

def test_una_base_al_dia_pasa_la_verificacion_y_lo_deja_apuntado(monkeypatch, caplog):
    """La revisión queda en el registro: es con lo que se empieza a diagnosticar cualquier cosa."""
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(database, "revision_aplicada", lambda: "d8b3e5f09a71")
    monkeypatch.setattr(database, "revision_esperada", lambda: "d8b3e5f09a71")

    verificar_esquema()

    assert any("d8b3e5f09a71" in r.getMessage() for r in caplog.records)


def test_una_base_sin_migrar_no_se_sirve_y_dice_las_dos_ordenes_posibles(monkeypatch):
    """
    Base nueva y base anterior a Alembic no se arreglan igual, y el mensaje distingue.

    `upgrade head` sobre una base que ya tiene las tablas falla a mitad; `stamp head` sobre
    una base vacía la marca como migrada sin crear nada. Dar una sola de las dos órdenes
    rompe uno de los dos casos, así que el mensaje nombra las dos y dice cuándo es cada una.
    """
    monkeypatch.setattr(database, "revision_aplicada", lambda: None)
    monkeypatch.setattr(database, "revision_esperada", lambda: "d8b3e5f09a71")

    with pytest.raises(EsquemaDesactualizado) as fallo:
        verificar_esquema()

    dicho = str(fallo.value)
    assert "ninguna migración aplicada" in dicho
    assert "alembic upgrade head" in dicho
    assert "alembic stamp head" in dicho


def test_una_base_en_otra_revision_no_se_sirve_y_nombra_las_dos(monkeypatch):
    """
    El mensaje lleva la revisión que hay y la que se espera.

    Sin las dos, el operador sabe que algo no cuadra y no sabe si le falta una migración o
    le sobra: es la diferencia entre `upgrade head` y revisar qué código está desplegado.
    """
    monkeypatch.setattr(database, "revision_aplicada", lambda: "c1d9f4b72a08")
    monkeypatch.setattr(database, "revision_esperada", lambda: "d8b3e5f09a71")

    with pytest.raises(EsquemaDesactualizado) as fallo:
        verificar_esquema()

    dicho = str(fallo.value)
    assert "c1d9f4b72a08" in dicho
    assert "d8b3e5f09a71" in dicho
    assert "alembic upgrade head" in dicho


# ==============================================================================
# `init_db`: lo que se hace al arrancar, según el entorno
# ==============================================================================

def test_en_un_entorno_endurecido_no_se_crea_nada_y_solo_se_verifica(monkeypatch):
    """
    `create_all()` en producción es lo que se quitó, y por qué.

    No borra ni altera lo que existe, así que parecía inofensivo, pero es incapaz de
    evacuar un cambio: renombrar una columna, cambiar un tipo o añadir un índice sobre
    datos ya escritos no lo ve. Dejándolo puesto, la base se queda en la forma del primer
    día mientras parece mantenerse sola.

    Se comprueba lo que NO pasa, que es lo difícil de ver: que la creación del esquema no
    se llega a invocar. Y el `return` importa tanto como la condición: sin él, un entorno
    endurecido verificaría y crearía a continuación.
    """
    verificado = []
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(database, "verificar_esquema", lambda: verificado.append(True))

    def _no_deberia_crear_nada(*args, **kwargs):
        raise AssertionError("se intentó crear el esquema en un entorno endurecido")

    monkeypatch.setattr(database.Base.metadata, "create_all", _no_deberia_crear_nada)

    database.init_db()

    assert verificado == [True]


def test_fuera_de_produccion_el_esquema_se_crea_detras_del_cerrojo_consultivo(monkeypatch, caplog):
    """
    El camino de PostgreSQL, que la suite no puede ejercitar con su propio motor.

    `create_all(checkfirst=True)` mira qué existe y luego lo crea, y entre esas dos cosas no
    hay atomicidad: con varios workers arrancando a la vez, dos entran, los dos ven la base
    vacía y el segundo revienta con `duplicate key ... pg_type_typname_nsp_index` al crear un
    tipo ENUM que el primero acababa de crear. El cerrojo consultivo serializa esa sección.

    Lo que se comprueba —sobre una base propia, con `pg_advisory_xact_lock` registrada como
    función de SQLite para que la sentencia se pueda ejecutar— es que el cerrojo se pide
    **antes** de crear nada, con el identificador fijo, y que la transacción se confirma.
    Esto último no se puede comprobar mirando si las tablas quedan: el driver de SQLite
    confirma las sentencias de definición por su cuenta, así que quedan igual sin
    confirmar nada —se intentó, y el mutante sobrevivió—. Lo que lo distingue es el cierre:
    `engine.begin()` confirma y `engine.connect()` deshace, y de eso sí avisa el motor.

    Lo que NO se comprueba aquí, porque SQLite no serializa nada, es que dos arranques
    simultáneos se esperen: eso solo lo hace PostgreSQL. La sentencia que se le manda es la
    que se ejecuta aquí, no una copia parecida.
    """
    caplog.set_level(logging.DEBUG)
    sucesos = []
    motor = _base_aparte()

    @event.listens_for(motor, "connect")
    def _registrar_el_cerrojo(conexion_dbapi, _registro):
        conexion_dbapi.create_function(
            "pg_advisory_xact_lock", 1, lambda clave: sucesos.append(("cerrojo", clave))
        )

    def _apuntar_el_esquema(_metadata, _conexion, **kw):
        sucesos.append(("esquema", len(kw.get("tables") or ())))

    @event.listens_for(motor, "commit")
    def _apuntar_la_confirmacion(_conexion):
        sucesos.append(("confirmada", True))

    @event.listens_for(motor, "rollback")
    def _apuntar_el_deshecho(_conexion):
        sucesos.append(("deshecha", True))

    event.listen(database.Base.metadata, "after_create", _apuntar_el_esquema)
    monkeypatch.setattr(database, "engine", motor)
    monkeypatch.setattr(database, "IS_SQLITE", False)

    try:
        database.init_db()
    finally:
        event.remove(database.Base.metadata, "after_create", _apuntar_el_esquema)

    try:
        assert [suceso for suceso, _ in sucesos] == ["cerrojo", "esquema", "confirmada"]
        assert sucesos[0][1] == database.SCHEMA_LOCK_ID
        assert sucesos[1][1] == len(database.Base.metadata.tables)
        assert "leads" in inspect(motor).get_table_names()
        assert any("verificado y listo" in r.getMessage() for r in caplog.records)
    finally:
        motor.dispose()
