"""
Endurecimiento de los contenedores y copias de seguridad (N-12 y N-13).

Los contenedores arrancaban con los valores de fábrica de Docker: sin techo de memoria
—un recálculo desbocado se lleva por delante también a la base de datos—, con la quincena
de capacidades del núcleo que trae cualquier imagen, con el sistema de ficheros escribible
y con un registro que crece sin límite hasta llenar el disco donde vive PostgreSQL.

Y no había copias. Ni copias ni, sobre todo, forma de saber si servirían: una copia que
nadie ha restaurado nunca no es una copia, es un archivo.

Como en `test_pila_de_despliegue.py`, lo que se comprueba aquí es la DECLARACIÓN, no el
arranque: montar Docker dentro de la suite la haría lenta e inestable. El ensayo real está
documentado en el capítulo correspondiente. Esto impide que el arreglo desaparezca sin que
nadie se entere.
"""
import pathlib

import pytest
import yaml

RAIZ_DEL_REPOSITORIO = pathlib.Path(__file__).resolve().parents[2]
COMPOSE = RAIZ_DEL_REPOSITORIO / "devops" / "docker-compose.yml"
BACKUP = RAIZ_DEL_REPOSITORIO / "devops" / "backup"

# Servicios que quedan en marcha. Los de respaldo van aparte: son de un disparo y se
# invocan a mano.
SERVICIOS_PERMANENTES = ("postgres", "backend", "redis", "frontend")
SERVICIOS_DE_RESPALDO = ("respaldo", "prueba-de-restauracion", "restaurar")
TODOS = SERVICIOS_PERMANENTES + ("migrate",) + SERVICIOS_DE_RESPALDO


@pytest.fixture(scope="module")
def pila() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def directivas(guion: str) -> str:
    """
    El guion sin sus comentarios.

    Existe porque la primera versión de estas pruebas no servía. Buscaban la opción en el
    archivo entero, y todas las opciones que importan aparecen DOS veces: en la orden y en
    el comentario que explica por qué hace falta. Quitarla de la orden dejaba el comentario
    —y la prueba seguía pasando—. Se comprobó reintroduciendo el defecto: retirar
    `--exit-on-error` del `pg_restore` real no hizo fallar ni una prueba de las 535.

    Es el mismo error que ya apareció en el pipeline con `$proxy_add_x_forwarded_for` y con
    `hashed_password`: el comentario que documenta un arreglo termina siendo lo único que
    sostiene la guarda de ese arreglo.
    """
    return "\n".join(
        linea for linea in guion.splitlines() if not linea.lstrip().startswith("#")
    )


def texto(nombre: str) -> str:
    return (BACKUP / nombre).read_text(encoding="utf-8")


def ordenes(nombre: str) -> str:
    return directivas(texto(nombre))


# ==============================================================================
# N-12 — Privilegios, recursos y registros
# ==============================================================================

@pytest.mark.parametrize("nombre", TODOS)
def test_ningun_servicio_puede_ganar_privilegios(pila, nombre):
    """
    `no-new-privileges` es lo que convierte «entré como usuario sin privilegios» en un
    callejón sin salida en lugar de en un primer paso: sin él, un binario con setuid
    dentro de la imagen sigue siendo una vía para volver a root.
    """
    opciones = pila["services"][nombre].get("security_opt") or []
    assert "no-new-privileges:true" in opciones, (
        f"El servicio '{nombre}' no declara no-new-privileges."
    )


@pytest.mark.parametrize("nombre", TODOS)
def test_ningun_servicio_conserva_las_capacidades_de_fabrica(pila, nombre):
    """
    Se parte de cero y se añade lo justo. Al revés —quitar las que molestan— siempre
    quedan las que nadie se paró a mirar.
    """
    servicio = pila["services"][nombre]
    assert servicio.get("cap_drop") == ["ALL"], (
        f"El servicio '{nombre}' no descarta todas las capacidades del núcleo."
    )


@pytest.mark.parametrize("nombre", SERVICIOS_PERMANENTES + ("migrate",))
def test_cada_servicio_tiene_techo_de_cpu_y_memoria(pila, nombre):
    """
    Sin techo, el proceso que se desmadra consume la memoria del anfitrión y se lleva por
    delante a los demás contenedores, incluida la base de datos. Con techo, muere él solo.
    """
    limites = (
        pila["services"][nombre].get("deploy", {}).get("resources", {}).get("limits", {})
    )
    assert limites.get("cpus"), f"El servicio '{nombre}' no declara techo de CPU."
    assert limites.get("memory"), f"El servicio '{nombre}' no declara techo de memoria."


@pytest.mark.parametrize("nombre", TODOS)
def test_cada_servicio_rota_sus_registros(pila, nombre):
    """
    Por defecto el driver `json-file` crece SIN LÍMITE.

    Importa más desde esta fase que antes: los registros pasaron a ser un objeto JSON por
    petición, que llena un disco bastante más rápido que una línea por evento. Y el disco
    que se llena es el mismo en el que vive PostgreSQL, que es el peor sitio por el que
    quedarse sin espacio.
    """
    registro = pila["services"][nombre].get("logging") or {}
    opciones = registro.get("options") or {}
    assert registro.get("driver") == "json-file", (
        f"El servicio '{nombre}' no fija driver de registro."
    )
    assert opciones.get("max-size"), f"El servicio '{nombre}' no acota el tamaño del registro."
    assert opciones.get("max-file"), f"El servicio '{nombre}' no acota el número de ficheros."


@pytest.mark.parametrize("nombre", ("backend", "migrate", "redis", "frontend") + SERVICIOS_DE_RESPALDO)
def test_los_servicios_que_no_escriben_van_en_solo_lectura(pila, nombre):
    """
    Un sistema de ficheros de solo lectura no impide una intrusión: impide que lo que el
    atacante deje escrito sobreviva al reinicio del contenedor.
    """
    servicio = pila["services"][nombre]
    assert servicio.get("read_only") is True, (
        f"El servicio '{nombre}' no monta su sistema de ficheros en solo lectura."
    )
    assert servicio.get("tmpfs"), (
        f"El servicio '{nombre}' está en solo lectura pero no declara ningún tmpfs; "
        "lo poco que sí escribe tiene que ir a memoria o el proceso falla al arrancar."
    )


def test_el_endurecimiento_esta_en_las_directivas_y_no_solo_en_la_cabecera(pila):
    """
    La cabecera del compose explica los cuatro mecanismos y los nombra literalmente.

    Cualquier comprobación por texto sobre el archivo entero —incluida la del pipeline—
    quedaría satisfecha por esa explicación aunque no quedara un solo servicio endurecido.
    Aquí se cuenta sobre la estructura ya interpretada, que es la única forma de saber que
    lo declarado existe de verdad.
    """
    servicios = pila["services"]
    con_privilegios = [n for n, s in servicios.items()
                       if "no-new-privileges:true" not in (s.get("security_opt") or [])]
    sin_capacidades = [n for n, s in servicios.items() if s.get("cap_drop") != ["ALL"]]
    sin_rotacion = [n for n, s in servicios.items()
                    if not ((s.get("logging") or {}).get("options") or {}).get("max-size")]

    assert not con_privilegios, f"Servicios sin no-new-privileges: {con_privilegios}"
    assert not sin_capacidades, f"Servicios que conservan capacidades: {sin_capacidades}"
    assert not sin_rotacion, f"Servicios sin rotación de registros: {sin_rotacion}"

    # Al menos los que pueden, en solo lectura. PostgreSQL es la excepción razonada.
    en_solo_lectura = [n for n, s in servicios.items() if s.get("read_only") is True]
    assert len(en_solo_lectura) >= len(servicios) - 1, (
        f"Solo {len(en_solo_lectura)} de {len(servicios)} servicios van en solo lectura; "
        "la única excepción prevista es postgres."
    )


def test_postgres_es_la_excepcion_declarada_y_no_un_olvido(pila):
    """
    PostgreSQL no puede ir en solo lectura: su entrypoint ajusta permisos y escribe fuera
    del volumen al inicializar, y una base de datos es por definición un proceso que
    escribe. La excepción se comprueba explícitamente para que quede claro que es una
    decisión y no un servicio que se saltó la revisión.
    """
    postgres = pila["services"]["postgres"]
    assert postgres.get("read_only") is not True
    assert postgres.get("cap_drop") == ["ALL"]
    assert "ports" not in postgres, "La base sigue sin publicar puerto."


def test_nginx_conserva_solo_lo_que_necesita_para_escuchar(pila):
    """El maestro arranca como root para atarse al 80 y baja los workers; nada más."""
    capacidades = set(pila["services"]["frontend"].get("cap_add") or [])
    assert "NET_BIND_SERVICE" in capacidades
    assert capacidades <= {"CHOWN", "SETGID", "SETUID", "NET_BIND_SERVICE", "DAC_OVERRIDE"}


def test_el_backend_no_necesita_ninguna_capacidad(pila):
    """
    Es la comprobación que más dice de la imagen: el proceso corre como `plurione`
    (uid 1001) y escucha en el 8000, por encima de los puertos privilegiados, así que no
    hace falta devolverle nada de lo que se le quitó.
    """
    assert not pila["services"]["backend"].get("cap_add")


def test_el_techo_de_redis_deja_sitio_a_su_propia_politica(pila):
    """
    `--maxmemory 128mb` acota lo que Redis guarda; el techo del contenedor acota el proceso
    entero. Si el segundo no fuera mayor, el núcleo mataría el proceso antes de que
    `allkeys-lru` llegara a desalojar una sola clave: la política de desalojo no llegaría a
    ejecutarse nunca.
    """
    redis = pila["services"]["redis"]
    orden = " ".join(redis["command"])
    assert "--maxmemory 128mb" in orden

    techo = redis["deploy"]["resources"]["limits"]["memory"]
    # El valor por defecto viaja dentro de la interpolación `${VAR:-256m}`.
    assert "256m" in techo


# ==============================================================================
# N-13 — Copias de seguridad
# ==============================================================================

@pytest.mark.parametrize(
    "guion", ["respaldo.sh", "prueba_de_restauracion.sh", "restaurar.sh"]
)
def test_los_guiones_de_respaldo_existen(guion):
    assert (BACKUP / guion).is_file(), f"Falta devops/backup/{guion}."


@pytest.mark.parametrize("nombre", SERVICIOS_DE_RESPALDO)
def test_los_servicios_de_respaldo_no_arrancan_con_la_pila(pila, nombre):
    """
    Van con perfil: `docker compose up` no debe lanzar una restauración ni un volcado.

    Aquí sí se usa `profiles:` —y no un archivo aparte como con pgAdmin— porque ninguno
    declara variables obligatorias con `:?`, que era lo que hacía que un perfil inactivo
    bloqueara el arranque de la pila entera.
    """
    assert pila["services"][nombre].get("profiles") == ["respaldo"]


def test_los_respaldos_viven_en_un_volumen_distinto_del_de_la_base(pila):
    """
    Tener las copias en el mismo volumen que protegen es la definición de no tener copias:
    un `docker compose down -v` para reinicializar la base se las llevaría también.
    """
    assert "pgrespaldos" in pila["volumes"]
    montajes = pila["services"]["respaldo"]["volumes"]
    assert any(str(m).startswith("pgrespaldos:") for m in montajes)
    assert not any(str(m).startswith("pgdata:") for m in montajes)


def test_el_respaldo_usa_la_misma_version_que_el_servidor(pila):
    """
    `pg_dump` se niega a volcar un servidor más nuevo que él, y esa negativa aparece el día
    que alguien actualiza PostgreSQL y no el cliente. Compartir imagen lo hace imposible.
    """
    for nombre in SERVICIOS_DE_RESPALDO:
        assert pila["services"][nombre]["image"] == pila["services"]["postgres"]["image"]


def test_el_volcado_se_comprueba_antes_de_darlo_por_bueno():
    """
    Que `pg_dump` termine no significa que el archivo sirva.

    Un volcado escrito a medias —disco lleno, contenedor detenido— pesa lo suyo y parece
    bueno hasta el día que hace falta. Y una base vacía por error produce un volcado
    perfectamente legible de unos kilobytes, que pasaría la comprobación de lectura.
    """
    guion = ordenes("respaldo.sh")

    assert "pg_restore --list" in guion, "No se comprueba que el volcado sea legible."
    assert "TAMANO_MINIMO_BYTES" in guion, "No se comprueba que el volcado no sea vacío."
    assert "sha256sum" in guion, "No se deja huella del volcado."


def test_un_volcado_interrumpido_no_hereda_el_nombre_de_uno_bueno():
    """
    Se escribe como `.parcial` y se renombra al final.

    Sin eso, un volcado cortado a la mitad queda con el nombre definitivo, la retención lo
    trata como una copia válida y puede acabar siendo la única que queda.
    """
    guion = ordenes("respaldo.sh")

    assert "PARCIAL=" in guion
    assert 'mv "$PARCIAL" "$DESTINO"' in guion


def test_la_prueba_de_restauracion_falla_cuando_la_restauracion_falla():
    """
    Sin `--exit-on-error`, `pg_restore` informa de los errores y termina con código 0.

    Es la opción que separa una prueba de un ritual: sin ella, una restauración a medias se
    leería como un éxito y el informe diría que las copias funcionan.
    """
    guion = ordenes("prueba_de_restauracion.sh")

    assert "--exit-on-error" in guion, (
        "El `pg_restore` de la prueba no lleva --exit-on-error. Sin esa opción informa de "
        "los errores y termina con código 0: una restauración a medias se leería como un "
        "éxito. (Se mira la ORDEN, no el archivo: el comentario que explica la opción la "
        "nombra también, y buscarla en el texto entero hacía que esta prueba pasara con la "
        "opción quitada.)"
    )


def test_la_prueba_compara_el_contenido_y_no_solo_que_termine():
    """Restaurar sin comparar solo demuestra que el archivo se deja leer."""
    guion = ordenes("prueba_de_restauracion.sh")

    assert "listar_recuentos" in guion
    assert "diff" in guion


def test_la_prueba_se_niega_a_usar_la_base_real_como_desechable():
    """
    El nombre de la base desechable es configurable. Una errata que lo hiciera coincidir con
    la real haría que la PRUEBA de restauración borrara producción antes de restaurar.
    """
    guion = ordenes("prueba_de_restauracion.sh")

    assert 'if [ "$BASE_DE_PRUEBA" = "$PGDATABASE" ]' in guion


def test_la_base_desechable_se_retira_tambien_cuando_la_prueba_falla():
    """
    Con `set -e`, un `pg_restore` que falla aborta el guion antes del DROP final.

    Se vio ejecutando la prueba contra un volcado corrompido a propósito: la base
    `lead_scoring_prueba_de_restauracion` quedaba en el servidor con la restauración a
    medias dentro. Y es justo el caso que más se repite —el que se reintenta mientras se
    investiga—, así que cada intento dejaba otra base huérfana en el servidor de
    producción. La retirada tiene que colgar de un `trap`, no del final del guion.
    """
    guion = ordenes("prueba_de_restauracion.sh")

    assert "trap retirar_base_desechable EXIT" in guion, (
        "La base desechable solo se retira en la salida feliz."
    )


def test_el_listado_de_volcados_no_se_traga_su_propia_salida():
    """
    `2>/dev/null >&2` descartaba el listado entero.

    El orden importa: primero stderr va a /dev/null y DESPUÉS stdout se apunta a stderr,
    que ya es /dev/null. Quien pedía una restauración sin nombrar el archivo recibía
    «Disponibles:» y una línea en blanco, justo cuando necesitaba saber qué volcados hay.
    Leyendo el guion no salta a la vista; ejecutándolo, sí.
    """
    guion = texto("restaurar.sh")

    for linea in guion.splitlines():
        limpia = linea.strip()
        if limpia.startswith("#") or "ls -1t" not in limpia:
            continue
        assert "2>/dev/null >&2" not in limpia, (
            "El listado de volcados se redirige a /dev/null por el orden de las "
            "redirecciones: use `>&2 2>/dev/null`."
        )


def test_la_restauracion_real_exige_confirmacion_y_archivo_exacto():
    """
    Las dos guardas son distintas y las dos hacen falta.

    La confirmación evita el `run` tecleado por inercia. Exigir el archivo evita algo más
    sutil: coger «el más reciente» automáticamente puede ser coger justo el volcado que ya
    contiene el borrado del que se quiere volver.
    """
    guion = ordenes("restaurar.sh")

    assert 'CONFIRMO_SOBRESCRIBIR:-' in guion
    assert "--single-transaction" in guion, (
        "Sin transacción única, una restauración que falla a mitad deja la base como una "
        "mezcla de dos versiones, que es el estado más difícil de arreglar."
    )


@pytest.mark.parametrize(
    "guion", ["respaldo.sh", "prueba_de_restauracion.sh", "restaurar.sh"]
)
def test_la_contrasena_nunca_viaja_en_la_linea_de_ordenes(guion):
    """
    Los argumentos de un proceso los lee cualquiera con `ps` dentro del contenedor.

    Se usa `PGPASSWORD` del entorno; ni `--password` ni `-W`, que además abriría un aviso
    interactivo en un contenedor sin terminal y dejaría la copia colgada para siempre.
    """
    contenido = ordenes(guion)

    assert "PGPASSWORD" in contenido
    assert "--password" not in contenido
    for linea in contenido.splitlines():
        assert " -W" not in linea, f"{guion}: petición interactiva de contraseña."
