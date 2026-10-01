"""
Infraestructura compartida de las pruebas.

La suite corre íntegramente contra **SQLite en memoria**. Antes operaba sobre
`lead_scoring.db`, el mismo archivo que usa el desarrollo local: las pruebas creaban
prospectos reales que quedaban ahí para siempre, dependían de que `seed_data.py` se
hubiera ejecutado antes —de ahí que el CI fuera rojo cuando el orden se invertía— y
podían borrar datos de alguien. Además el resultado dependía del estado acumulado del
archivo, así que "pasa en mi máquina" no significaba nada.

Ahora:

* `DATABASE_URL` se fija a `sqlite://` **antes** de importar nada de `app`, de modo que
  ni el motor del módulo ni el `init_db()` del arranque llegan a abrir un archivo.
* `dependency_overrides[get_db]` inyecta la sesión de pruebas en cada petición.
* Un fixture autouse vacía las tablas de negocio después de cada test.
* Los datos que un test necesita se piden explícitamente (`sample_leads`, `sales_reps`…),
  no se heredan del sembrado de demostración.
"""
import datetime
import hashlib
import hmac
import json
import os

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Entorno de pruebas. Debe fijarse ANTES del primer import de `app.*`, porque
# `app.core.config` construye `settings` —y `app.core.database` el motor— en el
# momento de importarse.
# ---------------------------------------------------------------------------
os.environ["DATABASE_URL"] = "sqlite://"          # SQLite en memoria, nunca un archivo
os.environ["ENVIRONMENT"] = "test"
# Clave fija para la suite: con una aleatoria por proceso, los tokens forjados a mano de
# las pruebas de seguridad no serían reproducibles entre ejecuciones.
os.environ["SECRET_KEY"] = "clave-exclusiva-de-la-suite-de-pruebas-no-usada-en-ningun-despliegue"
os.environ["REFRESH_COOKIE_SECURE"] = "false"
# La comprobación de contraseñas filtradas contra el servicio público (capítulo 37) va
# ENCENDIDA por defecto en el producto y APAGADA aquí. No es que la suite no la pruebe —hay
# un archivo entero para ella—: es que no debe probarla saliendo a internet. Una suite que
# depende de un tercero falla los días que ese tercero tiene un mal día, y entonces el rojo
# del CI deja de significar «el código está mal».
#
# `filtradas_remotas.consultar` lleva además una segunda guarda, para el caso de que alguien
# encienda esto en una prueba: con ENVIRONMENT=test se niega a abrir un socket si no se le
# ha inyectado una sonda.
os.environ["COMPROBAR_CONTRASENAS_FILTRADAS"] = "false"

from app.core.config import settings  # noqa: E402  (requiere el entorno de arriba)
from app.core.database import Base, SessionLocal, engine, get_db  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.core.security import (  # noqa: E402
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    exige_segundo_factor,
    hash_password,
)
from app.main import app  # noqa: E402
from app.models.entities import (  # noqa: E402
    Campaign,
    Lead,
    LeadStatus,
    QualificationStatus,
    ScoreCategory,
    User,
)

# Credenciales exclusivas de la suite: no coinciden con las que siembra seed_data.py,
# para que un cambio en el sembrado de demo no altere lo que las pruebas verifican.
TEST_PASSWORD = "PruebaSegura2026!"
TEST_ACCOUNTS = {
    "System_Admin": ("test.admin@plurione.com", "Admin de Pruebas"),
    "Sales_Lead": ("test.lider@plurione.com", "Líder de Pruebas"),
    "Commercial_Executive": ("test.asesor@plurione.com", "Asesor de Pruebas"),
}

# Secreto del webhook usado durante la suite. Se inyecta en `settings` porque el
# despliegue real lo recibe por variable de entorno y aquí no hay ninguna configurada.
TEST_WEBHOOK_SECRET = "secreto-de-pruebas-para-firmar-webhooks-crm"

# Las cuentas sobreviven al vaciado entre tests: crearlas cuesta un hash bcrypt cada una
# —deliberadamente lento— y rehacerlas 150 veces multiplicaría la duración de la suite
# sin añadir cobertura. Todo lo demás se borra.
PRESERVED_TABLES = {"users"}


def pytest_configure(config):
    """Comprobación de seguridad: si la suite apuntara a una base real, no arranca."""
    url = str(engine.url)
    if "memory" not in url and url not in ("sqlite://", "sqlite:///"):
        raise pytest.UsageError(
            f"La suite debe correr sobre SQLite en memoria y el motor apunta a '{url}'. "
            "Revise que conftest.py se importe antes que cualquier módulo de `app`."
        )


# ==============================================================================
# Esquema, sesión y sustitución de la dependencia de base de datos
# ==============================================================================

@pytest.fixture(scope="session", autouse=True)
def prepare_environment(tmp_path_factory):
    """Crea el esquema en memoria, las cuentas de prueba y habilita el webhook firmado."""
    Base.metadata.create_all(bind=engine)
    settings.CRM_WEBHOOK_SECRET = TEST_WEBHOOK_SECRET

    # El plazo del conjunto de realimentación (capítulo 32) BORRA ARCHIVOS del disco, y sin
    # esta línea el directorio por defecto sería `ml_pipeline/data` del propio árbol: correr
    # la suite en el portátil de quien tuviera un `leads_reales.csv` extraído le borraría el
    # suyo. Es el mismo argumento por el que la base va en memoria y no en `lead_scoring.db`.
    # Quien quiera probar la purga de verdad apunta este ajuste a su propio `tmp_path`.
    settings.REALIMENTACION_DIR = str(tmp_path_factory.mktemp("realimentacion-de-la-suite"))

    hashed = hash_password(TEST_PASSWORD)
    db = SessionLocal()
    try:
        for role, (email, full_name) in TEST_ACCOUNTS.items():
            cuenta = User(
                email=email,
                full_name=full_name,
                role=role,
                hashed_password=hashed,
            )
            # La cuenta de administración nace con el segundo factor ya activo, como la de
            # un administrador de verdad que acaba de darse de alta (capítulo 35). Sin
            # esto, toda la suite chocaría contra la exigencia en cuanto usara
            # `admin_headers`, y la tentación sería apagar la exigencia en las pruebas: el
            # camino que recorren dejaría de ser el que recorre un administrador real.
            if exige_segundo_factor(role):
                cuenta.totp_sal = "sal-fija-de-la-suite"
                cuenta.totp_activo = True
                cuenta.totp_codigos_de_recuperacion = []
            db.add(cuenta)
        db.commit()
    finally:
        db.close()

    # La aplicación recibe siempre una sesión del motor en memoria.
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()


def _override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def limitador_desactivado():
    """
    Apaga la limitación de tasa salvo donde se prueba explícitamente.

    La suite hace decenas de logins e inferencias contra la misma IP ficticia; con los
    límites de producción activos empezaría a recibir 429 por su propio volumen y los
    fallos no dirían nada sobre el código. `test_rate_limiting.py` lo reactiva y estrecha
    los límites para comprobar que el corte existe de verdad.
    """
    limiter.enabled = False
    limiter.reset()
    yield
    limiter.enabled = False
    limiter.reset()


# Estado al que vuelven las tres cuentas de la suite después de cada prueba. Se declara
# aquí, junto al vaciado, porque es la otra mitad del mismo mecanismo.
_HASH_DE_LA_SUITE = None


def _hash_de_la_suite() -> str:
    """
    Hash de `TEST_PASSWORD`, calculado una sola vez en toda la ejecución.

    bcrypt es lento a propósito: unos 100 ms por hash. Rehacerlo para tres cuentas al
    final de cada prueba añadiría minutos a la suite sin comprobar nada.
    """
    global _HASH_DE_LA_SUITE
    if _HASH_DE_LA_SUITE is None:
        _HASH_DE_LA_SUITE = hash_password(TEST_PASSWORD)
    return _HASH_DE_LA_SUITE


ESTADO_LIMPIO_DE_CUENTA = {
    # Desde el capítulo 23 el access token lleva `token_version` y se rechaza si no
    # coincide. Las cabeceras de `auth_headers` se cachean para toda la sesión: una prueba
    # que cierra sesión o cambia la contraseña sube la versión, y sin volver a 0 dejaría
    # inservible el token que la siguiente prueba reutiliza.
    "token_version": 0,
    "is_active": True,
    "is_sales_rep": False,
    "capacity": None,
    "phone": None,
    "must_change_password": False,
}


@pytest.fixture(autouse=True)
def clean_business_tables():
    """
    Vacía las tablas de negocio y devuelve las cuentas a su estado inicial tras cada test.

    Se ejecuta en el desmontaje y no en el montaje para que, si una prueba falla, el
    estado siga disponible mientras se depura dentro del propio test. El orden inverso de
    `sorted_tables` borra primero las hijas, respetando las claves foráneas.

    Las cuentas de `TEST_ACCOUNTS` sobreviven al vaciado —crearlas cuesta un hash bcrypt,
    deliberadamente lento, y rehacerlas en cada prueba multiplicaría la duración de la
    suite—, pero esa supervivencia dejó de ser inocua en cuanto aparecieron pruebas que
    cambian roles, contraseñas y la marca de asesor. Una prueba que degradaba a un usuario
    para comprobar que sus sesiones se cerraban dejaba a ese usuario degradado, y la
    siguiente que esperaba un 403 recibía un 401 sin que nada apuntara a la causa.
    Restaurarlas explícitamente convierte esa optimización en algo seguro en vez de frágil.

    Cualquier OTRA cuenta —las que crean las pruebas de gestión de identidades— se borra:
    no forma parte del estado base.
    """
    yield
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            if table.name not in PRESERVED_TABLES:
                connection.execute(table.delete())

    correos = {email for email, _ in TEST_ACCOUNTS.values()}
    db = SessionLocal()
    try:
        for usuario in db.query(User).all():
            if usuario.email not in correos:
                db.delete(usuario)
                continue
            rol_esperado = next(
                rol for rol, (email, _) in TEST_ACCOUNTS.items() if email == usuario.email
            )
            usuario.role = rol_esperado
            usuario.hashed_password = _hash_de_la_suite()
            for campo, valor in ESTADO_LIMPIO_DE_CUENTA.items():
                setattr(usuario, campo, valor)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def db_session():
    """
    Sesión directa contra la base en memoria, para comprobar el estado persistido.

    Sustituye a los `SessionLocal()` sueltos que abrían los tests: aquellos apuntaban a la
    base real y nadie garantizaba que se cerraran.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


# ==============================================================================
# Autenticación
# ==============================================================================

@pytest.fixture(scope="session")
def login():
    """
    Devuelve una función que inicia sesión y entrega el access token de un rol.

    Desde el capítulo 35 hace los **dos pasos** cuando la cuenta tiene segundo factor, que
    es siempre el caso de `System_Admin`: el rol lo tiene obligatorio y la suite lo da de
    alta al preparar la base (`_dar_de_alta_el_segundo_factor`).

    Podría haberse evitado apagando la exigencia en las pruebas, y sería un error: el camino
    que recorre toda la suite dejaría de ser el que recorre un administrador de verdad, y el
    día que el segundo paso se rompiera lo diría una sola prueba en lugar de todas.
    """
    def _login(role: str) -> str:
        email, _ = TEST_ACCOUNTS[role]
        # El mismo código TOTP no vale dos veces (RFC 6238 §5.2, con prueba propia en
        # `test_segundo_factor.py`), así que dos accesos dentro de la misma ventana de
        # treinta segundos fallan el segundo. En la vida real eso casi no ocurre y se
        # resuelve esperando; en una suite que entra varias veces por segundo, ocurre
        # siempre. Olvidar el contador es decir «han pasado treinta segundos» sin pasarlos.
        with SessionLocal() as db:
            cuenta = db.query(User).filter(User.email == email).first()
            if cuenta is not None and cuenta.totp_ultimo_contador is not None:
                cuenta.totp_ultimo_contador = None
                db.commit()
        with TestClient(app) as anon:
            response = anon.post(
                "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
            )
            assert response.status_code == 200, response.text
            cuerpo = response.json()
            if cuerpo.get("tipo") == "segundo_factor":
                response = anon.post(
                    "/api/v1/auth/login/segundo-factor",
                    json={"desafio": cuerpo["desafio"], "codigo": codigo_del_segundo_factor(email)},
                )
                assert response.status_code == 200, response.text
                cuerpo = response.json()
        return cuerpo["access_token"]

    return _login


def codigo_del_segundo_factor(email: str) -> str:
    """
    El código que enseñaría el teléfono de esa cuenta ahora mismo.

    Se deriva igual que lo hace el servidor —de `SECRET_KEY` y la sal guardada—, así que la
    suite no necesita conocer ningún secreto: lee la sal de la base, que es pública, y
    calcula. Es exactamente lo que hace la aplicación al comprobar.
    """
    from app.core import totp
    from app.models.entities import User, utc_now
    from app.services.segundo_factor import _secreto_de

    with SessionLocal() as db:
        usuario = db.query(User).filter(User.email == email).one()
        return totp.codigo(_secreto_de(usuario.totp_sal), utc_now().timestamp())


@pytest.fixture(scope="session")
def auth_headers(login):
    """
    Fábrica de cabeceras `Authorization: Bearer <jwt>` por rol.

    Los tokens se cachean por rol: bcrypt es deliberadamente lento y volver a iniciar
    sesión en cada test multiplicaría la duración de la suite sin aportar cobertura.
    """
    cache = {}

    def _headers(role: str = "Sales_Lead") -> dict:
        if role not in cache:
            cache[role] = {"Authorization": f"Bearer {login(role)}"}
        return cache[role]

    return _headers


@pytest.fixture
def admin_headers(auth_headers):
    return auth_headers("System_Admin")


@pytest.fixture
def lead_headers(auth_headers):
    return auth_headers("Sales_Lead")


@pytest.fixture
def executive_headers(auth_headers):
    return auth_headers("Commercial_Executive")


# ==============================================================================
# Datos de negocio
# ==============================================================================

def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


@pytest.fixture
def sales_reps(db_session):
    """
    Dos asesores comerciales activos, destino de la auto-asignación de prospectos HOT.

    Son `User`, no filas de una tabla de asesores aparte. Ya no existe tal tabla: un asesor
    es una cuenta con `is_sales_rep`, y esa unificación es lo que permite comparar de quién
    es un prospecto con quién lo está pidiendo.

    Se crean con un hash inutilizable porque estas dos cuentas nunca inician sesión en las
    pruebas: solo reciben cartera. Las que sí entran son las de `TEST_ACCOUNTS`.
    """
    reps = [
        User(
            email="ana.torres@plurione.com",
            full_name="Ana Torres",
            role="Commercial_Executive",
            hashed_password="!sin-contrasena:fixture",
            is_sales_rep=True,
            capacity=60,
        ),
        User(
            email="luis.prado@plurione.com",
            full_name="Luis Prado",
            role="Commercial_Executive",
            hashed_password="!sin-contrasena:fixture",
            is_sales_rep=True,
            capacity=40,
        ),
    ]
    db_session.add_all(reps)
    db_session.commit()
    for rep in reps:
        db_session.refresh(rep)
    return reps
    # No hace falta limpiarlas aquí: `clean_business_tables` borra al terminar cada prueba
    # toda cuenta que no sea una de `TEST_ACCOUNTS`.


@pytest.fixture
def campaigns(db_session):
    campaigns = [
        Campaign(name="LinkedIn Q1", channel="LinkedIn Ads", budget=120000.0),
        Campaign(name="Orgánico", channel="Organic", budget=0.0),
    ]
    db_session.add_all(campaigns)
    db_session.commit()
    for campaign in campaigns:
        db_session.refresh(campaign)
    return campaigns


# Perfiles fijos: los scores se escriben directamente en lugar de ejecutar el pipeline de
# scoring, que es asíncrono y carga el modelo. Las pruebas que necesitan un score
# *calculado* llaman al endpoint correspondiente; estas solo necesitan datos que listar.
SAMPLE_LEAD_SPECS = [
    ("Elena", "Ruiz", "elena.ruiz@fintechmx.com", "FinTech MX", "CTO", "FinTech",
     "1000+", "LinkedIn Ads", 92.4, ScoreCategory.HOT, LeadStatus.QUALIFIED, QualificationStatus.SQL),
    ("Marco", "Díaz", "marco.diaz@bancocentro.mx", "Banco del Centro", "CIO", "Banking",
     "1000+", "Referral", 84.1, ScoreCategory.HOT, LeadStatus.ENGAGED, QualificationStatus.SQL),
    ("Sofía", "Lara", "sofia.lara@retailmx.com", "Retail MX", "Gerente de Talento", "Retail",
     "201-1000", "Website", 63.7, ScoreCategory.WARM, LeadStatus.CONTACTED, QualificationStatus.MQL),
    ("Iván", "Beltrán", "ivan.beltran@logimx.com", "Logística MX", "Director de Operaciones", "Logistics",
     "51-200", "Website", 51.2, ScoreCategory.WARM, LeadStatus.NEW, QualificationStatus.MQL),
    ("Rosa", "Núñez", "rosa.nunez@universidad.mx", "Universidad del Valle", "Docente", "Educación",
     "201-1000", "Organic", 28.5, ScoreCategory.COLD, LeadStatus.NEW, QualificationStatus.INCOMING),
    ("Hugo", "Salas", "hugo.salas@microtaller.mx", "Micro Taller", "Practicante", "Manufactura",
     "1-10", "Organic", 14.0, ScoreCategory.COLD, LeadStatus.UNQUALIFIED, QualificationStatus.DISQUALIFIED),
]


@pytest.fixture
def sample_leads(db_session):
    """
    Seis prospectos con scores, categorías, industrias y orígenes variados.

    Cubren los tres tramos (HOT/WARM/COLD) y varios estados del pipeline, que es lo que
    necesitan los listados ordenados, las analíticas y el recálculo por lotes.
    """
    now = _utc_now()
    leads = [
        Lead(
            first_name=first, last_name=last, email=email, company=company,
            job_title=job_title, industry=industry, company_size=size, source=source,
            annual_revenue=1_000_000.0, country="México", city="CDMX",
            current_score=score, score_category=category, status=status,
            qualification_status=qualification, conversion_probability=score / 100.0,
            last_score_update=now, last_activity_at=now, created_at=now, updated_at=now,
            raw_metadata={},
        )
        for (first, last, email, company, job_title, industry, size, source,
             score, category, status, qualification) in SAMPLE_LEAD_SPECS
    ]
    db_session.add_all(leads)
    db_session.commit()
    for lead in leads:
        db_session.refresh(lead)
    return leads


@pytest.fixture
def sample_lead(sample_leads):
    """El prospecto de mayor score, para las pruebas que solo necesitan uno."""
    return sample_leads[0]


@pytest.fixture
def cartera_repartida(db_session, sample_leads):
    """
    Reparte los seis prospectos entre el asesor de pruebas y otra persona.

    Es el escenario mínimo para comprobar la autorización por objeto: hace falta que
    existan prospectos que el asesor SÍ puede tocar y prospectos que NO, en la misma base y
    a la vez. Una prueba con cartera de un solo dueño pasaría igual con el filtro roto.

    Devuelve `(propios, ajenos)`.
    """
    asesor = (
        db_session.query(User)
        .filter(User.email == TEST_ACCOUNTS["Commercial_Executive"][0])
        .first()
    )
    otro = User(
        email="otra.asesora@plurione.com",
        full_name="Otra Asesora",
        role="Commercial_Executive",
        hashed_password="!sin-contrasena:fixture",
        is_sales_rep=True,
        capacity=50,
    )
    db_session.add(otro)
    db_session.commit()
    db_session.refresh(otro)

    asesor.is_sales_rep = True
    asesor.capacity = 50

    propios = sample_leads[:2]
    ajenos = sample_leads[2:]
    for lead in propios:
        lead.assigned_rep_id = asesor.id
    for lead in ajenos:
        lead.assigned_rep_id = otro.id
    db_session.commit()
    for lead in sample_leads:
        db_session.refresh(lead)

    # La cuenta de "otra asesora" la retira `clean_business_tables` al terminar la prueba,
    # junto con cualquier otra que no sea una de `TEST_ACCOUNTS`.
    return propios, ajenos


# ==============================================================================
# Firma de webhooks CRM
# ==============================================================================

def sign_webhook(payload: dict, secret: str = TEST_WEBHOOK_SECRET, timestamp: int = None):
    """
    Serializa y firma un payload de webhook tal y como lo haría el CRM emisor.

    Devuelve `(body, headers)`: el cuerpo debe enviarse con `content=body` —no con
    `json=`— porque el HMAC cubre los bytes exactos, y una reserialización distinta
    (espaciado, orden de claves) invalidaría la firma.
    """
    if timestamp is None:
        timestamp = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    body = json.dumps(payload).encode("utf-8")
    ts = str(timestamp)
    signature = hmac.new(
        secret.encode("utf-8"), ts.encode("utf-8") + b"." + body, hashlib.sha256
    ).hexdigest()
    headers = {
        "Content-Type": "application/json",
        SIGNATURE_HEADER: signature,
        TIMESTAMP_HEADER: ts,
    }
    return body, headers
