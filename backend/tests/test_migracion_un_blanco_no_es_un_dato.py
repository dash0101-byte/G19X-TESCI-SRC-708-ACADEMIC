"""
La migración del capítulo 41 (`d8b3e5f09a71`), ida y vuelta.

Como las de los capítulos 25 a 32: Alembic de verdad, en un proceso aparte y sobre una SQLite
en fichero temporal. La suite nunca toca la base real.

Lo que tiene que cumplirse, y por qué cada cosa
------------------------------------------------
**Las tres formas del blanco se igualan.** `''`, `' '` y `'   '` son lo mismo y pasan a `NULL`.
Son las tres que llegaban: la cadena vacía de un campo que nadie tocó, el espacio que queda al
borrar lo escrito y el par de espacios de un copiado y pegado.

**Un dato de verdad no se toca, ni siquiera si tiene espacios alrededor.** Un `' Monterrey '`
no se recorta aquí: lo que esta migración corrige es un vacío con dos representaciones, no el
formato de lo que alguien escribió. Recortarlo sería un cambio de datos que nadie pidió, y a
partir de este capítulo lo recorta el esquema al guardarlo.

**Lo obligatorio no se toca y se cuenta.** Un nombre no se puede inventar —el capítulo 25
quitó de este sistema los «Prospecto» y «Empresa no identificada»— y en una ficha el nombre
vacío puede ser el vacío deliberado del webhook. Se comprueba que siguen ahí **y** que la
migración los nombra en su salida, que es lo único que permite ir a corregirlos.

**La lista de columnas sale de los esquemas y de las tablas, no de la migración.** Es la mitad
que evita que esta corrección caduque: una columna de texto nueva que un cuerpo de petición
nombre aparece en la comprobación de abajo el día que se declara, y si no está en la migración,
en rojo. Es la misma disciplina que `CAMPOS_QUE_NO_ADMITEN_VACIO` del capítulo 33, aplicada a
una lista que en una revisión de Alembic no puede ser derivada: una migración tiene que seguir
haciendo lo mismo dentro de diez versiones del modelo, así que sus columnas van escritas y lo
que se deriva es la comprobación.

**La reversión no escribe nada, y se comprueba que no escribe nada.** Un `NULL` que fue `''` no
se distingue de uno que siempre fue `NULL`.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import sqlalchemy as sa

ANTERIOR = "c3f18b6a02d7"
ESTA = "d8b3e5f09a71"

_SONDA = r"""
import json, os
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
import sqlalchemy as sa

url = os.environ["DATABASE_URL"]
cfg = Config()
cfg.set_main_option("script_location", os.environ["ALEMBIC_DIR"])
cfg.set_main_option("sqlalchemy.url", url)
motor = sa.create_engine(url)
resultado = {}

AHORA = "2026-10-01 08:00:00"

def fichas():
    with motor.connect() as c:
        return {f[0]: list(f[1:]) for f in c.execute(sa.text(
            "SELECT email, company, job_title, industry, company_size, country, city, phone, "
            "first_name, last_name, source FROM leads ORDER BY id")).fetchall()}

def cuentas():
    with motor.connect() as c:
        return {f[0]: list(f[1:]) for f in c.execute(sa.text(
            "SELECT email, phone, full_name FROM users ORDER BY id")).fetchall()}

def publicaciones():
    with motor.connect() as c:
        return {f[0]: list(f[1:]) for f in c.execute(sa.text(
            "SELECT name, description, target_audience, utm_source, utm_medium, utm_campaign, "
            "url_del_post, channel FROM campaigns ORDER BY id")).fetchall()}

# --- antes ------------------------------------------------------------------------------
command.upgrade(cfg, os.environ["ANTERIOR"])

# (correo, company, job_title, industry, company_size, country, city, phone, first, last, source)
FICHAS = [
    # Las tres formas del blanco, repartidas por los campos que admiten vacio.
    ("blancos@empresa.com", "", "   ", " ", "  ", "", "   ", " ", "Ana", "Perez", "Website"),
    # Un dato de verdad, con espacios alrededor: no se toca.
    ("datos@empresa.com", " ACME ", "CTO", "FinTech", "11-50", "Mexico", " Monterrey ",
     "+525512345678", "Ana", "Perez", "LinkedIn"),
    # Ya estaba bien: nulos de los de verdad.
    ("nulos@empresa.com", None, None, None, None, None, None, None, "Ana", "Perez", "Website"),
    # Lo obligatorio en blanco: no se puede vaciar, se cuenta. El nombre vacio es el que
    # escribe el webhook de un CRM que no lo manda (capitulo 25).
    ("obligatorios@empresa.com", None, None, None, None, None, None, None, "   ", "", "  "),
]
CUENTAS = [
    ("blanco@plurione.com", "  ", "Persona Con Nombre"),
    ("numero@plurione.com", "+525598765432", "Persona Con Nombre"),
    ("sin_nombre@plurione.com", None, "   "),
]
# (name, description, target_audience, utm_source, utm_medium, utm_campaign, url_del_post, channel)
PUBLICACIONES = [
    ("Con blancos", "", "   ", " ", "  ", "", "   ", "LinkedIn"),
    ("Con datos", "Una descripcion", "Lideres de TI", "linkedin", "social", "q4",
     "https://example.com/post", "LinkedIn"),
    ("   ", None, None, None, None, None, None, "  "),
]

with motor.begin() as c:
    c.execute(sa.text("PRAGMA foreign_keys = ON"))
    for fila in FICHAS:
        c.execute(sa.text(
            "INSERT INTO leads (email, company, job_title, industry, company_size, country, "
            "city, phone, first_name, last_name, source, status, qualification_status, "
            "current_score, score_category, conversion_probability, last_score_update, "
            "last_activity_at, created_at, updated_at) "
            "VALUES (:e, :co, :jt, :ind, :cs, :pa, :ci, :ph, :fn, :ln, :src, 'NEW', 'INCOMING', "
            "10.0, 'COLD', 0.1, :t, :t, :t, :t)"
        ), dict(zip(
            ["e", "co", "jt", "ind", "cs", "pa", "ci", "ph", "fn", "ln", "src"], fila
        ), t=AHORA))
    for correo, telefono, nombre in CUENTAS:
        c.execute(sa.text(
            # `totp_activo` va explicito: el capitulo 35 lo creo con `server_default` y lo
            # retiro despues, asi que una fila nueva tiene que traerlo.
            "INSERT INTO users (email, hashed_password, full_name, role, is_active, "
            "token_version, is_sales_rep, must_change_password, totp_activo, phone, "
            "password_changed_at, created_at, updated_at) "
            "VALUES (:e, '!x', :n, 'Commercial_Executive', 1, 0, 1, 0, 0, :p, :t, :t, :t)"
        ), {"e": correo, "n": nombre, "p": telefono, "t": AHORA})
    for indice, fila in enumerate(PUBLICACIONES, start=1):
        c.execute(sa.text(
            "INSERT INTO campaigns (name, description, target_audience, utm_source, utm_medium, "
            "utm_campaign, url_del_post, channel, public_slug, budget, is_active, estado, "
            "created_at) "
            "VALUES (:n, :de, :ta, :us, :um, :uc, :up, :ch, :slug, 0.0, 1, 'activa', :t)"
        ), dict(zip(
            ["n", "de", "ta", "us", "um", "uc", "up", "ch"], fila
        ), slug="slug%d" % indice, t=AHORA))

resultado["fichas_antes"] = fichas()
resultado["cuentas_antes"] = cuentas()
resultado["publicaciones_antes"] = publicaciones()

# --- hacia delante -----------------------------------------------------------------------
command.upgrade(cfg, os.environ["ESTA"])
resultado["fichas_despues"] = fichas()
resultado["cuentas_despues"] = cuentas()
resultado["publicaciones_despues"] = publicaciones()

# --- hacia atras --------------------------------------------------------------------------
command.downgrade(cfg, os.environ["ANTERIOR"])
resultado["fichas_tras_revertir"] = fichas()
resultado["cuentas_tras_revertir"] = cuentas()

# --- y otra vez hacia delante, hasta el final ----------------------------------------------
command.upgrade(cfg, "head")

import sys
sys.path.insert(0, os.environ["BACKEND"])
from app.core.database import Base
import app.models.entities  # noqa: F401
with motor.connect() as c:
    diferencias = compare_metadata(MigrationContext.configure(c), Base.metadata)
resultado["diferencias"] = [repr(d) for d in diferencias]
print("__RESULTADO__" + json.dumps(resultado))
"""


def _ciclo(tmp_path: Path) -> dict:
    raiz = Path(__file__).resolve().parents[2]
    base = tmp_path / "migracion_capitulo_41.db"
    entorno = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{base.as_posix()}",
        "ALEMBIC_DIR": str(raiz / "backend" / "alembic"),
        "BACKEND": str(raiz / "backend"),
        "ANTERIOR": ANTERIOR,
        "ESTA": ESTA,
        "PYTHONPATH": str(raiz / "backend") + os.pathsep + str(raiz),
        "PYTHONIOENCODING": "utf-8",
    }
    proceso = subprocess.run(  # noqa: S603  intérprete propio y script literal, sin entrada externa
        [sys.executable, "-c", _SONDA],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(raiz),
        env=entorno,
        timeout=300,
    )
    assert proceso.returncode == 0, proceso.stderr
    linea = next(s for s in proceso.stdout.splitlines() if s.startswith("__RESULTADO__"))
    datos = json.loads(linea.removeprefix("__RESULTADO__"))
    datos["salida"] = proceso.stdout
    return datos


# Posición de cada columna en lo que devuelve `fichas()`.
F = {
    "company": 0, "job_title": 1, "industry": 2, "company_size": 3, "country": 4,
    "city": 5, "phone": 6, "first_name": 7, "last_name": 8, "source": 9,
}
P = {
    "description": 0, "target_audience": 1, "utm_source": 2, "utm_medium": 3,
    "utm_campaign": 4, "url_del_post": 5, "channel": 6,
}


def test_ciclo_completo_de_la_migracion(tmp_path):
    r = _ciclo(tmp_path)

    # --- antes: el defecto está ahí, y se comprueba ----------------------------------
    # Sin esto, la prueba podría pasar sobre una base que nunca tuvo blancos.
    antes = r["fichas_antes"]["blancos@empresa.com"]
    assert [antes[F[c]] for c in ("company", "job_title", "city")] == ["", "   ", "   "]

    # --- las tres formas del blanco se igualan ---------------------------------------
    despues = r["fichas_despues"]["blancos@empresa.com"]
    for columna in ("company", "job_title", "industry", "company_size", "country", "city", "phone"):
        assert despues[F[columna]] is None, f"{columna} quedó en {despues[F[columna]]!r}"

    # --- un dato de verdad no se toca, ni siquiera sus espacios ----------------------
    con_datos = r["fichas_despues"]["datos@empresa.com"]
    assert con_datos[F["city"]] == " Monterrey ", (
        "esta migración iguala vacíos; recortar lo que alguien escribió es otro cambio, y a "
        "partir del capítulo 41 lo hace el esquema al guardarlo"
    )
    assert con_datos[F["company"]] == " ACME "

    # --- lo que ya era nulo sigue siendo nulo ----------------------------------------
    nulos = r["fichas_despues"]["nulos@empresa.com"]
    assert all(nulos[F[c]] is None for c in ("company", "job_title", "country", "city"))

    # --- lo obligatorio no se toca ---------------------------------------------------
    obligatorios = r["fichas_despues"]["obligatorios@empresa.com"]
    assert obligatorios[F["first_name"]] == "   "
    assert obligatorios[F["last_name"]] == ""
    assert obligatorios[F["source"]] == "  "

    # --- las cuentas y las publicaciones, lo mismo -----------------------------------
    assert r["cuentas_despues"]["blanco@plurione.com"][0] is None
    assert r["cuentas_despues"]["numero@plurione.com"][0] == "+525598765432"
    assert r["cuentas_despues"]["sin_nombre@plurione.com"][1] == "   ", "el nombre es obligatorio"

    con_blancos = r["publicaciones_despues"]["Con blancos"]
    for columna in ("description", "target_audience", "utm_source", "utm_medium",
                    "utm_campaign", "url_del_post"):
        assert con_blancos[P[columna]] is None, f"{columna} quedó en {con_blancos[P[columna]]!r}"
    assert r["publicaciones_despues"]["Con datos"][P["description"]] == "Una descripcion"
    assert "   " in r["publicaciones_despues"], "el nombre de una publicación es obligatorio"

    # --- la migración dice qué no pudo arreglar --------------------------------------
    # Es lo único que permite ir a corregirlo a mano. Una migración que cuenta y no lo dice
    # deja el trabajo hecho a medias y sin nadie enterado.
    assert "Columnas obligatorias EN BLANCO" in r["salida"]
    for esperado in ("leads.first_name: 1", "leads.source: 1", "users.full_name: 1",
                     "campaigns.name: 1", "campaigns.channel: 1"):
        assert esperado in r["salida"], f"la migración no nombra {esperado}"

    # --- la reversión no escribe nada ------------------------------------------------
    assert r["fichas_tras_revertir"] == r["fichas_despues"], (
        "revertir no puede devolver los blancos: un NULL que fue '' no se distingue de uno "
        "que siempre fue NULL"
    )
    assert r["cuentas_tras_revertir"] == r["cuentas_despues"]

    # --- y el esquema sigue siendo el del modelo -------------------------------------
    assert r["diferencias"] == []


def test_la_lista_de_columnas_sale_de_los_esquemas_y_de_las_tablas():
    """
    La mitad que impide que la corrección caduque.

    La migración lleva sus columnas escritas, y tiene que ser así: una revisión de Alembic
    describe la base **de su momento** y seguirá ejecutándose dentro de diez versiones del
    modelo, así que derivar la lista del modelo actual la haría cambiar con él. Lo que se deriva
    es esta comprobación: las columnas de texto que admiten nulo de las tres tablas que un
    cuerpo de petición escribe, cruzadas con los campos que esos cuerpos declaran.

    Si alguien añade una columna de texto a `leads`, `users` o `campaigns` y la expone en una
    entrada, esto se pone rojo y la migración se queda corta **antes** de que la base tenga dos
    formas de decir lo mismo otra vez.
    """
    from app.core.texto import columnas_de_texto
    from app.models.entities import Campaign, Lead, User

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    revision = _cargar_la_revision()

    from tests.test_un_blanco_no_es_un_dato import _campos_de_texto, esquemas_de_entrada

    nombrados = set()
    for esquema in esquemas_de_entrada().values():
        nombrados.update(campo for campo, _info in _campos_de_texto(esquema))

    for modelo, tabla in ((Lead, "leads"), (User, "users"), (Campaign, "campaigns")):
        esperadas = set(columnas_de_texto(modelo, obligatorias=False)) & nombrados
        assert set(revision.COLUMNAS_QUE_SE_IGUALAN[tabla]) == esperadas, (
            f"{tabla}: la migración iguala {sorted(revision.COLUMNAS_QUE_SE_IGUALAN[tabla])} y "
            f"las columnas de texto que admiten nulo y una entrada nombra son "
            f"{sorted(esperadas)}"
        )

        obligatorias = set(columnas_de_texto(modelo, obligatorias=True)) & nombrados
        # `email` queda fuera de las que se cuentan: `EmailStr` nunca ha admitido un blanco, así
        # que no puede haber ninguno, y contar una columna donde no cabe el defecto sugeriría
        # que sí cabe. Las enumeraciones (`status`, `role`…) tampoco: su valor sale de una lista.
        assert set(revision.COLUMNAS_QUE_SOLO_SE_CUENTAN[tabla]) <= obligatorias
        assert "email" not in revision.COLUMNAS_QUE_SOLO_SE_CUENTAN[tabla]


def _cargar_la_revision():
    """La revisión como módulo. No es importable por su ruta: el nombre empieza por un dígito."""
    import importlib.util

    ruta = (
        Path(__file__).resolve().parents[1]
        / "alembic" / "versions" / f"{ESTA}_un_blanco_no_es_un_dato.py"
    )
    especificacion = importlib.util.spec_from_file_location("revision_41", ruta)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


def test_la_revision_se_encadena_con_la_anterior():
    """Una revisión suelta no se ejecuta nunca, y nadie lo nota hasta que falta una columna."""
    revision = _cargar_la_revision()
    assert revision.revision == ESTA
    assert revision.down_revision == ANTERIOR


def test_la_condicion_del_update_deja_fuera_los_nulos():
    """
    `TRIM(NULL) = ''` es nulo, no verdadero, así que las filas que ya estaban bien no se
    reescriben.

    Se comprueba contra el motor y no de memoria: es la diferencia entre una migración que toca
    cuatro filas y una que reescribe la tabla entera, y en PostgreSQL eso es un bloqueo de
    escritura sobre `leads` en producción.
    """
    motor = sa.create_engine("sqlite://")
    with motor.begin() as conexion:
        conexion.execute(sa.text("CREATE TABLE t (c TEXT)"))
        conexion.execute(sa.text("INSERT INTO t (c) VALUES (NULL), (''), ('  '), ('dato')"))
        afectadas = conexion.execute(
            sa.text("UPDATE t SET c = NULL WHERE TRIM(c) = ''")
        ).rowcount
    assert afectadas == 2, "solo la cadena vacía y los espacios; el nulo y el dato se quedan"
