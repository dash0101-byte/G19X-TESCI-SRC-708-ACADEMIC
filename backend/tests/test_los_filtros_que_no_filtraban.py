"""
Doce filtros que nadie había ejercitado, en tres archivos distintos.

Un filtro sin probar falla siempre hacia el mismo lado: **devuelve más de lo que debería**.
No hay error, no hay traza y la pantalla se pinta igual; lo único que cambia es que la lista
trae filas que no se pidieron. En los tres sitios donde viven esos filtros, lo que se cuela
es distinto y lo tres tienen el mismo síntoma —ninguno—:

* **La bitácora** (`/audit`) tiene siete filtros y solo `action` estaba probado. Es la única
  lectura del registro de auditoría que existe, y el rol que la usa es el de administración:
  si `entity_id` no filtra, la pregunta «quién tocó esta ficha» se contesta con los asientos
  de todas las demás, y quien busca un abuso en diez mil filas no lo encuentra.
* **El listado de prospectos** tiene siete filtros y cuatro no se ejercitaban: `status`,
  `industry`, `min_score` y `max_score`. Los dos del score son los que usan los asesores
  para decidir a quién llaman hoy.
* **El listado de cuentas** y el de asesores tienen un interruptor de cuentas inactivas y un
  filtro por rol. Una baja que sigue apareciendo en el selector de reparto es una ficha
  asignada a alguien que ya no está.

Y el primer filtro de todos, que no es un filtro sino el alcance: un asesor cuyo
identificador no se puede resolver no ve nada. La comparación natural con `NULL` habría
devuelto «los prospectos sin asignar», que es el peor valor por defecto posible.
"""
import datetime
import uuid

import pytest
from app.core.autorizacion import AlcanceDeCartera
from app.core.security import CurrentUser, UserRole
from app.models.entities import AuditLog, Lead, LeadStatus, ScoreCategory, User, utc_now
from app.repositories.lead_repository import LeadRepository
from app.schemas.lead import LeadListFilter
from tests.conftest import TEST_ACCOUNTS

AUDIT = "/api/v1/audit"
USUARIOS = "/api/v1/users"
ASESORES = "/api/v1/sales-reps"


# ==============================================================================
# La bitácora: siete filtros, uno probado
# ==============================================================================

@pytest.fixture
def dos_asientos(db_session):
    """
    Dos asientos que se diferencian en todo lo que se puede filtrar.

    Con uno solo, un filtro roto devolvería ese mismo asiento y la prueba pasaría: hace
    falta que exista el que NO tiene que salir.
    """
    marca = uuid.uuid4().hex[:8]
    ayer = utc_now() - datetime.timedelta(days=1)
    anteayer = utc_now() - datetime.timedelta(days=3)
    buscado = AuditLog(
        actor_email=f"buscada-{marca}@plurione.com",
        actor_role="System_Admin",
        action=f"prueba.buscada.{marca}",
        entity=f"entidad-buscada-{marca}",
        entity_id=f"id-buscado-{marca}",
        outcome="OK",
        occurred_at=ayer,
    )
    otro = AuditLog(
        actor_email=f"otra-{marca}@plurione.com",
        actor_role="Sales_Lead",
        action=f"prueba.otra.{marca}",
        entity=f"entidad-otra-{marca}",
        entity_id=f"id-otro-{marca}",
        outcome="HTTP_403",
        occurred_at=anteayer,
    )
    db_session.add_all([buscado, otro])
    db_session.commit()
    db_session.refresh(buscado)
    db_session.refresh(otro)
    return marca, buscado, otro


def _asientos(client, admin_headers, **filtros):
    respuesta = client.get(AUDIT, params={"limit": 200, **filtros}, headers=admin_headers)
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()["items"]


@pytest.mark.parametrize(
    "filtro",
    ["actor_email", "entity", "entity_id", "outcome"],
)
def test_cada_filtro_de_la_bitacora_deja_fuera_lo_que_no_pide(
    client, admin_headers, dos_asientos, filtro
):
    """
    Uno por uno, y comprobando las dos mitades: que el buscado sale y que el otro no.

    Comprobar solo que el buscado sale no distingue un filtro que funciona de uno que no
    filtra nada, que es exactamente la forma en la que esto se rompe.
    """
    _, buscado, otro = dos_asientos
    valor = getattr(buscado, filtro)

    vistos = _asientos(client, admin_headers, **{filtro: valor})

    identificadores = {asiento["id"] for asiento in vistos}
    assert buscado.id in identificadores
    assert otro.id not in identificadores


def test_el_correo_del_actor_se_busca_como_lo_escriba_quien_pregunta(
    client, admin_headers, dos_asientos
):
    """
    Los correos se guardan en minúsculas y quien busca teclea como le sale.

    Sin la normalización, buscar «Ana@Plurione.com» en la bitácora devuelve cero asientos y
    el administrador concluye que esa cuenta no hizo nada.
    """
    _, buscado, _ = dos_asientos

    vistos = _asientos(client, admin_headers, actor_email=f"  {buscado.actor_email.upper()}  ")

    assert buscado.id in {asiento["id"] for asiento in vistos}


def test_los_dos_filtros_de_fecha_de_la_bitacora_acotan_la_ventana(
    client, admin_headers, dos_asientos
):
    """
    `desde` y `hasta`, que son los que contestan «qué pasó aquella tarde».

    Se comprueban juntos porque juntos es como se usan y porque una ventana es el único caso
    donde los dos tienen que estar bien: con uno solo roto, la ventana se abre por ese lado
    y trae meses de asientos sin que se note.
    """
    _, buscado, otro = dos_asientos
    hace_dos_dias = utc_now() - datetime.timedelta(days=2)

    desde = {a["id"] for a in _asientos(client, admin_headers, desde=hace_dos_dias.isoformat())}
    assert buscado.id in desde
    assert otro.id not in desde

    hasta = {a["id"] for a in _asientos(client, admin_headers, hasta=hace_dos_dias.isoformat())}
    assert otro.id in hasta
    assert buscado.id not in hasta


# ==============================================================================
# El listado de prospectos: cuatro filtros sin ejercitar
# ==============================================================================

@pytest.fixture
def dos_prospectos(db_session):
    """Dos fichas que se diferencian en estado, industria y score."""
    marca = uuid.uuid4().hex[:8]
    caliente = Lead(
        first_name="Buscada", last_name=marca, email=f"buscada-{marca}@ejemplo.mx",
        company="Empresa Buscada", job_title="CTO", industry="Tecnología",
        company_size="201-500", source="Website", country="México", city="CDMX",
        current_score=88.0, score_category=ScoreCategory.HOT,
        status=LeadStatus.QUALIFIED, raw_metadata={},
    )
    frio = Lead(
        first_name="Otra", last_name=marca, email=f"otra-{marca}@ejemplo.mx",
        company="Empresa Otra", job_title="Becario", industry="Educación",
        company_size="1-10", source="Organic Search", country="México", city="Monterrey",
        current_score=12.0, score_category=ScoreCategory.COLD,
        status=LeadStatus.NEW, raw_metadata={},
    )
    db_session.add_all([caliente, frio])
    db_session.commit()
    db_session.refresh(caliente)
    db_session.refresh(frio)
    return caliente, frio


def _alcance_completo() -> AlcanceDeCartera:
    return AlcanceDeCartera.de(
        CurrentUser(
            user_id="1",
            email=TEST_ACCOUNTS["System_Admin"][0],
            name="Administración",
            role=UserRole.SYSTEM_ADMIN,
        )
    )


@pytest.mark.parametrize(
    "filtro, valor",
    [
        ("status", LeadStatus.QUALIFIED),
        ("industry", "tecno"),
        ("min_score", 80.0),
        ("max_score", 50.0),
    ],
    ids=["por etapa", "por industria", "con un suelo de score", "con un techo de score"],
)
def test_cada_filtro_del_listado_de_prospectos_acota_de_verdad(
    db_session, dos_prospectos, filtro, valor
):
    """
    Los cuatro que no se ejercitaban. `max_score` es el único donde sale el frío.

    La industria se compara en minúsculas y por coincidencia parcial: «tecno» tiene que
    encontrar «Tecnología», porque es lo que se escribe en una caja de búsqueda.
    """
    caliente, frio = dos_prospectos
    repositorio = LeadRepository(db_session, alcance=_alcance_completo())

    fichas, _ = repositorio.list_leads(LeadListFilter(limit=200, **{filtro: valor}))

    identificadores = {ficha.id for ficha in fichas}
    esperado, descartado = (frio, caliente) if filtro == "max_score" else (caliente, frio)
    assert esperado.id in identificadores
    assert descartado.id not in identificadores


def test_un_asesor_sin_identificador_resoluble_no_ve_nada(db_session, dos_prospectos):
    """
    Fallar cerrado, y la razón por la que la condición está escrita a mano.

    El alcance de un asesor filtra por `assigned_rep_id == <su id>`. Cuando ese
    identificador no se puede resolver, la comparación natural sería
    `assigned_rep_id == None`, que en SQL no es «ninguno»: es **los prospectos sin
    asignar**. Quien no se sabe quién es vería justo la bolsa de fichas que todavía no
    tienen dueño.
    """
    sin_identificador = AlcanceDeCartera.de(
        CurrentUser(
            user_id="no-soy-un-numero",
            email="raro@plurione.com",
            name="Sin identificador",
            role=UserRole.COMMERCIAL_EXECUTIVE,
        )
    )
    assert sin_identificador.usuario_id is None
    assert sin_identificador.toda_la_cartera is False

    repositorio = LeadRepository(db_session, alcance=sin_identificador)
    fichas, total = repositorio.list_leads(LeadListFilter(limit=200))

    assert fichas == []
    assert total == 0


def test_con_la_cartera_completa_no_se_pregunta_si_algo_queda_fuera(db_session, dos_prospectos):
    """
    `existe_fuera_del_alcance` sirve para distinguir en la bitácora un tanteo de
    identificadores de una petición a algo que no existe.

    Con la cartera completa esa pregunta no tiene sentido —nada queda fuera— y además la
    consulta no se hace: contestar True habría anotado como «tanteo» cada 404 de un
    administrador.
    """
    caliente, _ = dos_prospectos
    completo = LeadRepository(db_session, alcance=_alcance_completo())

    assert completo.existe_fuera_del_alcance(caliente.id) is False
    assert completo.existe_fuera_del_alcance(10_000_000) is False


# ==============================================================================
# El listado de cuentas y el de asesores: las bajas
# ==============================================================================

@pytest.fixture
def una_cuenta_de_baja(db_session):
    marca = uuid.uuid4().hex[:8]
    cuenta = User(
        email=f"de-baja-{marca}@plurione.com",
        full_name=f"Cuenta De Baja {marca}",
        role="Commercial_Executive",
        hashed_password="!sin-contrasena:fixture",
        is_active=False,
        is_sales_rep=True,
        capacity=10,
    )
    db_session.add(cuenta)
    db_session.commit()
    db_session.refresh(cuenta)
    return cuenta


def test_las_cuentas_de_baja_solo_salen_si_se_piden(client, admin_headers, una_cuenta_de_baja):
    """
    Por omisión no salen, y con el interruptor sí. Las dos mitades.

    Si el interruptor no hiciera nada, una baja seguiría apareciendo en la lista de cuentas
    como si operara.
    """
    sin_pedirlas = client.get(USUARIOS, params={"limit": 200}, headers=admin_headers).json()
    assert una_cuenta_de_baja.id not in {u["id"] for u in sin_pedirlas["items"]}

    pidiendolas = client.get(
        USUARIOS, params={"limit": 200, "incluir_inactivos": True}, headers=admin_headers
    ).json()
    assert una_cuenta_de_baja.id in {u["id"] for u in pidiendolas["items"]}


def test_el_listado_de_cuentas_filtra_por_rol(client, admin_headers):
    """
    El filtro por rol de la pantalla de administración.

    Sin él, pedir «los asesores» devuelve también a la administración: la lista es correcta
    y la respuesta a la pregunta no.
    """
    respuesta = client.get(
        USUARIOS,
        params={"limit": 200, "rol": UserRole.SYSTEM_ADMIN.value},
        headers=admin_headers,
    )

    assert respuesta.status_code == 200, respuesta.text
    roles = {cuenta["role"] for cuenta in respuesta.json()["items"]}
    assert roles == {UserRole.SYSTEM_ADMIN.value}


def test_el_selector_de_asesores_tampoco_trae_las_bajas_si_no_se_piden(
    client, admin_headers, una_cuenta_de_baja
):
    """
    Esta es la que tiene consecuencia escrita: el selector de reparto.

    Una cuenta de baja en ese selector termina en fichas asignadas a alguien que ya no
    entra, y esas fichas no aparecen en la cartera de nadie.
    """
    sin_pedirlas = client.get(
        ASESORES, params={}, headers=admin_headers
    ).json()
    assert una_cuenta_de_baja.id not in {a["id"] for a in sin_pedirlas["items"]}

    pidiendolas = client.get(
        ASESORES, params={"incluir_inactivos": True}, headers=admin_headers
    ).json()
    assert una_cuenta_de_baja.id in {a["id"] for a in pidiendolas["items"]}
