"""
Guardas del script de siembra (A-2).

`seed_data.py` no añade datos: vacía las tablas de negocio y las regenera. Lo hacía sin
preguntar, sin decir contra qué base, y el pipeline de CI lo ejecutaba. Bastaba con un
`DATABASE_URL` heredado de otra terminal —o con que alguien lo lanzara en el servidor
equivocado— para perder todos los prospectos, actividades e historiales del sistema.

El destino es un borrado, así que la confirmación tiene que ser explícita y el entorno
endurecido queda fuera de alcance por completo. La única operación que sí tiene sentido
sobre datos reales —crear o restablecer las cuentas de acceso— se separa en su propia
bandera y no borra nada.
"""
import importlib.util
import os
import subprocess
import sys

import pytest
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.entities import Lead

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RUTA_SCRIPT = os.path.join(RAIZ, "backend", "scripts", "seed_data.py")


def _cargar_script():
    """Carga `seed_data.py` como módulo: vive en `scripts/`, que no es un paquete."""
    spec = importlib.util.spec_from_file_location("seed_data_bajo_prueba", RUTA_SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def seed():
    return _cargar_script()


# ============================================================================
# El entorno endurecido queda fuera de alcance
# ============================================================================

@pytest.mark.parametrize("entorno", ["production", "PRODUCTION", "staging", "preprod"])
def test_se_niega_a_sembrar_en_entornos_endurecidos(seed, entorno, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", entorno)
    with pytest.raises(seed.SiembraRechazada) as excinfo:
        seed.seed_database()
    mensaje = str(excinfo.value)
    assert entorno in mensaje
    # El mensaje debe ofrecer la salida legítima, no solo negarse.
    assert "--solo-usuarios" in mensaje


def test_solo_usuarios_si_esta_permitido_en_produccion(seed, sample_leads, monkeypatch):
    """
    Las cuentas de operación sí hacen falta en producción. Ese camino no borra nada, así
    que no está sujeto a la prohibición: negarlo obligaría a crear los accesos a mano.

    `init_db` se sustituye porque en un entorno endurecido exige una base migrada por
    Alembic, y la suite corre sobre un esquema creado con `create_all`. Lo que se
    comprueba aquí es la guarda de entorno, no la verificación de esquema, que tiene sus
    propias pruebas.
    """
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(seed, "init_db", lambda: None)
    llamadas = []
    monkeypatch.setattr(seed, "seed_users", lambda db: llamadas.append(db))

    db = SessionLocal()
    try:
        antes = db.query(Lead).count()
        assert antes > 0

        seed.seed_database(solo_usuarios=True)  # no debe lanzar

        assert len(llamadas) == 1, "debía crear las cuentas"
        db.expire_all()
        assert db.query(Lead).count() == antes, "no debía borrar datos de negocio"
    finally:
        db.close()


# ============================================================================
# Sin --force no se borra nada
# ============================================================================

def test_aborta_si_ya_hay_datos_y_no_se_confirma(seed, sample_leads, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    with pytest.raises(seed.SiembraRechazada) as excinfo:
        seed.seed_database(forzar=False)
    mensaje = str(excinfo.value)
    assert "--force" in mensaje
    # Debe enumerar lo que está en juego: un número concreto convence más que una advertencia.
    assert "Se borrarían" in mensaje
    assert "Prospectos" in mensaje


def test_el_aborto_no_toca_ni_una_fila(seed, sample_leads, monkeypatch):
    """La comprobación que de verdad importa: que el rechazo sea anterior al borrado."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    db = SessionLocal()
    try:
        antes = db.query(Lead).count()
        assert antes > 0
        with pytest.raises(seed.SiembraRechazada):
            seed.seed_database(forzar=False)
        db.expire_all()
        assert db.query(Lead).count() == antes
    finally:
        db.close()


# ============================================================================
# El destino se muestra sin la contraseña
# ============================================================================

def test_el_destino_oculta_la_contrasena(seed, monkeypatch):
    """
    Se imprime la base de destino antes de borrar —es la información que evita el error—
    pero la URL de PostgreSQL lleva la contraseña dentro, y estos scripts se ejecutan en
    consolas cuyo historial queda grabado.
    """
    monkeypatch.setattr(
        settings,
        "DATABASE_URL",
        "postgresql+psycopg2://plurione:contrasena-secreta@db.interno:5432/lead_scoring",
    )
    destino = seed.destino_de_la_base()
    assert "contrasena-secreta" not in destino
    assert "plurione" in destino
    assert "db.interno:5432/lead_scoring" in destino


# ============================================================================
# El contrato de la línea de órdenes
# ============================================================================

def test_la_orden_sin_force_termina_con_codigo_de_error(tmp_path):
    """
    Se ejecuta el script de verdad, como lo ejecutaría un pipeline: lo que evita el
    desastre automatizado es el código de salida, no el texto en pantalla.
    """
    entorno = dict(os.environ)
    entorno["ENVIRONMENT"] = "production"
    entorno["DATABASE_URL"] = f"sqlite:///{tmp_path / 'destino.db'}"
    entorno["SECRET_KEY"] = "clave-de-pruebas-suficientemente-larga-para-pasar-el-minimo"
    entorno["CORS_ORIGINS"] = '["https://app.plurione.com"]'

    resultado = subprocess.run(  # noqa: S603
        [sys.executable, RUTA_SCRIPT],
        capture_output=True,
        text=True,
        env=entorno,
        cwd=RAIZ,
        timeout=120,
    )

    assert resultado.returncode == 2, resultado.stdout + resultado.stderr
    assert "SIEMBRA ABORTADA" in resultado.stdout
    # Y no llegó a crear el archivo de base de datos que se le indicó.
    assert not (tmp_path / "destino.db").exists()


def test_se_vacia_todo_lo_que_cuelga_de_una_campana_antes_que_la_campana(seed):
    """
    Las campañas se borran y vuelven a crearse, y SQLite reutiliza sus ids. Una tabla que
    cuelga de `campaigns` y no se vacía antes deja sus filas colgadas del id viejo, y la
    campaña nueva que lo herede las hereda: la publicación de ejemplo de la prueba con
    personas empezaba con las visitas de la anterior (capítulo 26).
    """
    from app.core.database import Base

    tablas = [modelo.__tablename__ for _, modelo in seed.TABLAS_A_VACIAR]
    posicion_de_campanas = tablas.index("campaigns")
    dependientes = {
        tabla.name
        for tabla in Base.metadata.sorted_tables
        for fk in tabla.foreign_keys
        if fk.column.table.name == "campaigns"
    }
    for dependiente in dependientes:
        assert dependiente in tablas, f"«{dependiente}» cuelga de campaigns y la resiembra no la vacía"
        assert tablas.index(dependiente) < posicion_de_campanas
