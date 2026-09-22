"""
La pila de despliegue tiene que arrancar sobre una base vacía.

Estas pruebas nacen de levantar `docker compose up` de verdad, por primera vez, sobre un
volumen recién creado. La pila **no arrancaba**: el backend comprueba al iniciar que el
esquema esté sellado por Alembic y aborta si no lo está —una guarda deliberada, que se
queda—, pero ningún servicio aplicaba las migraciones. El fallo no se veía en ninguna
comprobación anterior porque `docker compose config` valida la sintaxis, no el arranque,
y porque las pruebas manuales se habían hecho siempre sobre una base ya migrada a mano.

Es el mismo patrón que esta fase persigue en el código: algo que se da por resuelto
porque nadie lo ejecutó nunca en las condiciones en que falla.

Lo que se comprueba aquí es el archivo, no el arranque: montar Docker dentro de la suite
la haría lenta e inestable. La prueba de verdad —volumen vacío, `up`, backend sano— se
hizo a mano y está documentada en el capítulo correspondiente. Esto es la regresión que
impide que el arreglo desaparezca sin que nadie se entere.
"""
import pathlib

import pytest
import yaml

RAIZ_DEL_REPOSITORIO = pathlib.Path(__file__).resolve().parents[2]
COMPOSE = RAIZ_DEL_REPOSITORIO / "devops" / "docker-compose.yml"


@pytest.fixture(scope="module")
def pila() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def test_la_pila_incluye_un_servicio_que_aplica_las_migraciones(pila):
    servicios = pila["services"]
    assert "migrate" in servicios, (
        "La pila no tiene servicio de migración. Sin él, `docker compose up` sobre un "
        "volumen vacío deja el backend abortando en bucle: se niega a servir con el "
        "esquema sin sellar, y con razón."
    )

    orden = servicios["migrate"].get("command")
    assert orden == ["alembic", "upgrade", "head"], (
        f"El servicio de migración debe ejecutar `alembic upgrade head` y ejecuta {orden!r}."
    )


def test_el_backend_espera_a_que_la_migracion_termine_bien(pila):
    """
    `service_started` no sirve: el backend arrancaría mientras Alembic aún trabaja.

    La condición tiene que ser que el contenedor haya SALIDO CON ÉXITO. Es la diferencia
    entre una dependencia declarada y una dependencia que se cumple.
    """
    dependencias = pila["services"]["backend"].get("depends_on", {})
    assert "migrate" in dependencias, (
        "El backend no espera al servicio de migración; el orden de arranque quedaría al azar."
    )
    condicion = dependencias["migrate"].get("condition")
    assert condicion == "service_completed_successfully", (
        f"El backend debe esperar a `service_completed_successfully` y espera a {condicion!r}. "
        "Con cualquier otra condición arrancaría con las migraciones a medias."
    )


def test_la_migracion_corre_con_la_misma_imagen_que_el_backend(pila):
    """
    Migrar con una imagen distinta a la que sirve es aplicar un esquema que el código
    que va a usarlo no conoce necesariamente. Deben ser el mismo artefacto.
    """
    servicios = pila["services"]
    assert servicios["migrate"].get("image") == servicios["backend"].get("image"), (
        "El servicio de migración y el backend deben compartir imagen: mismo código, "
        "mismas migraciones, mismas dependencias."
    )


def test_la_migracion_no_publica_puertos_ni_depende_de_redis(pila):
    """
    Un contenedor de un solo disparo no debe ampliar la superficie de la pila. Aplicar
    migraciones no necesita Redis ni escuchar en ningún puerto.
    """
    migrate = pila["services"]["migrate"]
    assert "ports" not in migrate, "El servicio de migración no debe publicar puertos."
    assert set(migrate.get("depends_on", {})) == {"postgres"}, (
        "El servicio de migración solo necesita la base de datos."
    )
    assert migrate.get("restart") in ("no", False), (
        "El servicio de migración debe salir y quedarse fuera; reiniciarlo lo pondría a "
        "aplicar migraciones en bucle."
    )
