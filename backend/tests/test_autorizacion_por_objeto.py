"""
N-3: el rol decide qué verbos, la propiedad decide sobre qué.

El sistema tenía control de acceso por endpoint y ninguno por objeto. Un asesor comercial
autenticado veía la cartera completa de la empresa: podía listar todos los prospectos,
abrir la ficha de cualquiera y leer los KPIs consolidados de todo el pipeline. El rol
decidía qué operaciones podía invocar, nunca sobre qué datos.

Estas pruebas están escritas para fallar si alguien revierte el arreglo, y por eso casi
todas usan `cartera_repartida`: hace falta que en la misma base existan a la vez
prospectos del asesor y prospectos ajenos. Con una cartera de un solo dueño, una prueba
pasaría igual con el filtro completamente roto.
"""
import pytest
from app.core.autorizacion import AlcanceDeCartera, FueraDeAlcance
from app.core.security import CurrentUser, UserRole
from app.models.entities import AuditLog, Lead, User
from app.repositories.lead_repository import LeadRepository
from tests.conftest import TEST_ACCOUNTS

LEADS = "/api/v1/leads"


def _usuario(db, rol: str) -> User:
    return db.query(User).filter(User.email == TEST_ACCOUNTS[rol][0]).first()


# ==============================================================================
# El alcance en sí
# ==============================================================================

def test_el_asesor_solo_alcanza_lo_suyo():
    alcance = AlcanceDeCartera.de(
        CurrentUser(user_id="7", email="a@b.c", name="A", role=UserRole.COMMERCIAL_EXECUTIVE)
    )
    assert alcance.alcanza(7)
    assert not alcance.alcanza(8)
    assert not alcance.alcanza(None), (
        "Un prospecto sin dueño no es de nadie, y menos aún de quien pregunta."
    )
    assert not alcance.puede_reasignar()


@pytest.mark.parametrize("rol", [UserRole.SALES_LEAD, UserRole.SYSTEM_ADMIN])
def test_quien_dirige_la_cartera_la_alcanza_entera(rol):
    alcance = AlcanceDeCartera.de(
        CurrentUser(user_id="1", email="a@b.c", name="A", role=rol)
    )
    assert alcance.alcanza(999)
    assert alcance.alcanza(None)
    assert alcance.puede_reasignar()


def test_un_identificador_irresoluble_no_alcanza_nada():
    """
    Fallar cerrado. Si el `sub` del token no es un entero, no hay dueño con el que
    comparar; devolver «todo» ahí convertiría un token malformado en acceso total.
    """
    alcance = AlcanceDeCartera.de(
        CurrentUser(user_id="no-soy-un-id", email="a@b.c", name="A",
                    role=UserRole.COMMERCIAL_EXECUTIVE)
    )
    assert alcance.usuario_id is None
    assert not alcance.alcanza(1)
    assert not alcance.alcanza(None)


def test_el_alcance_de_sistema_exige_un_motivo():
    """
    Es la única puerta que ve la cartera completa sin un token detrás. Que cueste una
    frase escribirla es justo lo que se pretende: aparece en la revisión.
    """
    with pytest.raises(ValueError):
        AlcanceDeCartera.del_sistema("")
    with pytest.raises(ValueError):
        AlcanceDeCartera.del_sistema("   ")
    assert AlcanceDeCartera.del_sistema("ingesta del CRM").toda_la_cartera


def test_el_repositorio_no_se_construye_sin_alcance(db_session):
    """
    La prueba que sostiene todas las demás.

    Si `LeadRepository(db)` volviera a ser válido, el filtro dejaría de aplicarse en cuanto
    alguien escribiera un endpoint sin acordarse, y ese olvido no produce ningún error
    visible: produce una consulta que devuelve de más.
    """
    with pytest.raises(TypeError):
        LeadRepository(db_session)


# ==============================================================================
# El repositorio filtra
# ==============================================================================

def test_el_listado_solo_trae_lo_propio(client, executive_headers, cartera_repartida):
    propios, ajenos = cartera_repartida
    cuerpo = client.get(LEADS, headers=executive_headers).json()

    assert cuerpo["total"] == len(propios), (
        "El total debe contar lo que ve quien pregunta. Devolver el total global junto a "
        "una página filtrada delata el tamaño de la cartera ajena en la propia respuesta."
    )
    devueltos = {item["id"] for item in cuerpo["items"]}
    assert devueltos == {lead.id for lead in propios}
    assert devueltos.isdisjoint({lead.id for lead in ajenos})


def test_el_lider_ve_la_cartera_entera(client, lead_headers, cartera_repartida):
    propios, ajenos = cartera_repartida
    cuerpo = client.get(LEADS, headers=lead_headers).json()
    assert cuerpo["total"] == len(propios) + len(ajenos)


def test_un_filtro_por_otro_asesor_no_abre_la_cartera(client, executive_headers, cartera_repartida):
    """
    El parámetro `assigned_rep_id` no es una puerta: filtra DENTRO del alcance.

    Es el intento evidente —pedir explícitamente los prospectos de otra persona— y falla
    porque el filtro del repositorio se aplica después, no en lugar de este.
    """
    _, ajenos = cartera_repartida
    ajeno = ajenos[0]
    cuerpo = client.get(
        LEADS, params={"assigned_rep_id": ajeno.assigned_rep_id}, headers=executive_headers
    ).json()
    assert cuerpo["total"] == 0
    assert cuerpo["items"] == []


def test_la_busqueda_por_texto_tampoco_cruza_la_frontera(client, executive_headers, cartera_repartida):
    """Buscar por nombre no es otra vía: pasa por el mismo repositorio acotado."""
    _, ajenos = cartera_repartida
    cuerpo = client.get(
        LEADS, params={"search": ajenos[0].last_name}, headers=executive_headers
    ).json()
    assert cuerpo["total"] == 0


def test_un_prospecto_ajeno_responde_404(client, executive_headers, cartera_repartida):
    _, ajenos = cartera_repartida
    respuesta = client.get(f"{LEADS}/{ajenos[0].id}", headers=executive_headers)
    assert respuesta.status_code == 404
    assert "no encontrado" in respuesta.json()["detail"]


def test_el_404_de_lo_ajeno_es_indistinguible_del_de_lo_inexistente(
    client, executive_headers, cartera_repartida
):
    """
    La respuesta no puede delatar que el identificador existe.

    Si «no es tuyo» respondiera 403 y «no existe» 404, recorrer identificadores dibujaría
    el tamaño y la forma de la cartera ajena sin ver un solo dato.
    """
    _, ajenos = cartera_repartida
    ajeno = client.get(f"{LEADS}/{ajenos[0].id}", headers=executive_headers)
    fantasma = client.get(f"{LEADS}/99999", headers=executive_headers)

    assert ajeno.status_code == fantasma.status_code == 404
    # Ni siquiera la forma del cuerpo puede diferir.
    assert set(ajeno.json()) == set(fantasma.json())


def test_el_intento_sobre_cartera_ajena_queda_en_la_bitacora(
    client, executive_headers, cartera_repartida, db_session
):
    """
    Hacia fuera, 404 indistinguible; hacia dentro, la diferencia sí se conserva.

    Un 404 aislado es un enlace viejo. Una tanda seguida de la misma cuenta contra
    identificadores que no le corresponden es alguien tanteando, y eso solo se ve si queda
    escrito.
    """
    _, ajenos = cartera_repartida
    client.get(f"{LEADS}/{ajenos[0].id}", headers=executive_headers)
    client.get(f"{LEADS}/99999", headers=executive_headers)

    asientos = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "acceso.fuera_de_alcance")
        .all()
    )
    assert len(asientos) == 1, (
        "Debe registrarse el intento sobre un prospecto REAL y ajeno, y solo ese: un 404 "
        "por identificador inexistente no dice nada de nadie."
    )
    asiento = asientos[0]
    assert asiento.entity_id == str(ajenos[0].id)
    assert asiento.actor_email == TEST_ACCOUNTS["Commercial_Executive"][0]
    assert asiento.outcome == "HTTP_404"


# ==============================================================================
# Escritura
# ==============================================================================

def test_el_asesor_edita_lo_suyo(client, executive_headers, cartera_repartida):
    """
    La contrapartida del filtro: un asesor sí edita su propia cartera.

    Antes no podía editar ninguna, ni la suya, lo que empujaba a pedirle cada cambio de
    teléfono al líder comercial —o a repartir el rol de líder para que la aplicación
    fuera usable, que es como una restricción demasiado gruesa acaba produciendo permisos
    de más—.
    """
    propios, _ = cartera_repartida
    respuesta = client.put(
        f"{LEADS}/{propios[0].id}", headers=executive_headers, json={"job_title": "Directora de TI"}
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["job_title"] == "Directora de TI"


def test_el_asesor_no_edita_lo_ajeno(client, executive_headers, cartera_repartida):
    _, ajenos = cartera_repartida
    respuesta = client.put(
        f"{LEADS}/{ajenos[0].id}", headers=executive_headers, json={"job_title": "X"}
    )
    assert respuesta.status_code == 404


def test_el_asesor_no_reasigna_ni_los_suyos(client, executive_headers, cartera_repartida, db_session):
    """
    Reasignar es repartir trabajo, no atenderlo.

    Sin esta regla, un asesor podría quitarse de encima lo que no le apetece o apropiarse
    de lo ajeno, y en ambos casos el prospecto sale de la vista de quien respondía por él.
    """
    propios, ajenos = cartera_repartida
    otro_id = ajenos[0].assigned_rep_id
    respuesta = client.put(
        f"{LEADS}/{propios[0].id}",
        headers=executive_headers,
        json={"assigned_rep_id": otro_id},
    )
    assert respuesta.status_code == 403
    db_session.expire_all()
    sigue = db_session.query(Lead).filter(Lead.id == propios[0].id).first()
    assert sigue.assigned_rep_id != otro_id, "el prospecto no debió cambiar de dueño"


def test_el_lider_si_reasigna(client, lead_headers, cartera_repartida, db_session):
    propios, ajenos = cartera_repartida
    destino = ajenos[0].assigned_rep_id
    respuesta = client.put(
        f"{LEADS}/{propios[0].id}", headers=lead_headers, json={"assigned_rep_id": destino}
    )
    assert respuesta.status_code == 200
    db_session.expire_all()
    assert db_session.query(Lead).filter(Lead.id == propios[0].id).first().assigned_rep_id == destino


def test_el_prospecto_que_crea_un_asesor_queda_suyo(client, executive_headers, db_session):
    """
    Sin esto, un asesor que creara un prospecto sin dueño lo perdería de vista en el mismo
    instante: quedaría fuera de su propio alcance y no podría volver a abrirlo.
    """
    asesor = _usuario(db_session, "Commercial_Executive")
    asesor.is_sales_rep = True
    db_session.commit()

    respuesta = client.post(
        LEADS,
        headers=executive_headers,
        json={
            "first_name": "Nuevo", "last_name": "Prospecto",
            "email": "nuevo.prospecto@empresa.mx", "company": "Empresa",
        },
    )
    assert respuesta.status_code == 201
    assert respuesta.json()["assigned_rep_id"] == asesor.id

    # Y lo puede volver a abrir, que es la comprobación que da sentido a la anterior.
    creado = respuesta.json()["id"]
    assert client.get(f"{LEADS}/{creado}", headers=executive_headers).status_code == 200


def test_un_asesor_no_endosa_prospectos_a_otro(client, executive_headers, cartera_repartida):
    _, ajenos = cartera_repartida
    respuesta = client.post(
        LEADS,
        headers=executive_headers,
        json={
            "first_name": "Regalo", "last_name": "Envenenado",
            "email": "regalo@empresa.mx",
            "assigned_rep_id": ajenos[0].assigned_rep_id,
        },
    )
    assert respuesta.status_code == 403


def test_el_duplicado_de_correo_se_detecta_aunque_sea_de_otro(
    client, executive_headers, cartera_repartida
):
    """
    La comprobación de duplicados NO se acota, y es deliberado.

    `leads.email` es único en toda la tabla: mirar solo dentro de la cartera propia dejaría
    pasar un correo ajeno hasta el INSERT y lo convertiría en un 500. Un 400 explicativo es
    mejor que un error del servidor, que además revela lo mismo.
    """
    _, ajenos = cartera_repartida
    respuesta = client.post(
        LEADS,
        headers=executive_headers,
        json={"first_name": "Choque", "last_name": "De Correo", "email": ajenos[0].email},
    )
    assert respuesta.status_code == 400
    # No debe filtrarse nada del prospecto ajeno más allá de que el correo está tomado.
    detalle = respuesta.json()["detail"]
    assert ajenos[0].company not in detalle
    assert ajenos[0].last_name not in detalle


def test_registrar_actividad_sobre_cartera_ajena_no_procede(
    client, executive_headers, cartera_repartida
):
    """
    Escribir sobre cartera ajena no es solo leerla: una actividad sube el score y puede
    disparar la reasignación automática de un prospecto caliente.
    """
    _, ajenos = cartera_repartida
    respuesta = client.post(
        f"{LEADS}/{ajenos[0].id}/activities",
        headers=executive_headers,
        json={"activity_type": "PHONE_CALL", "channel": "Teléfono"},
    )
    assert respuesta.status_code == 404


def test_el_recalculo_individual_tambien_esta_acotado(client, executive_headers, cartera_repartida):
    """El resultado incluye el desglose y la explicación: es la ficha contada de otra manera."""
    _, ajenos = cartera_repartida
    respuesta = client.post(
        f"{LEADS}/{ajenos[0].id}/recalculate-score", headers=executive_headers
    )
    assert respuesta.status_code == 404


def test_el_lider_borra_cualquier_prospecto_de_la_cartera(
    client, lead_headers, cartera_repartida, db_session
):
    """
    Contrapartida de la acotación: quien dirige la cartera la dirige entera.

    Importa comprobarlo porque el filtro nuevo pasa por el mismo repositorio: si estuviera
    mal escrito, podría acotar también a quien no debe y romper la gestión sin que ninguna
    prueba de «no ve lo ajeno» se enterara.
    """
    _, ajenos = cartera_repartida
    victima_id = ajenos[0].id  # se guarda ANTES: tras el borrado la instancia no resuelve
    assert client.delete(f"{LEADS}/{victima_id}", headers=lead_headers).status_code == 204
    db_session.expire_all()
    assert db_session.query(Lead).filter(Lead.id == victima_id).first() is None


def test_el_repositorio_acotado_no_borra_fuera_de_alcance(db_session, cartera_repartida):
    """Directo contra el repositorio, sin pasar por HTTP: el filtro vive ahí."""
    _, ajenos = cartera_repartida
    asesor = _usuario(db_session, "Commercial_Executive")
    alcance = AlcanceDeCartera(
        usuario_id=asesor.id, toda_la_cartera=False, motivo="prueba"
    )
    repo = LeadRepository(db_session, alcance)

    assert repo.delete(ajenos[0].id) is False
    db_session.expire_all()
    assert db_session.query(Lead).filter(Lead.id == ajenos[0].id).first() is not None


def test_el_repositorio_rechaza_actualizar_una_entidad_ajena(db_session, cartera_repartida):
    """
    Comprobación de cierre: aunque alguien cargue el prospecto por otra vía y lo pase al
    repositorio, la actualización se niega.
    """
    from app.schemas.lead import LeadUpdate

    _, ajenos = cartera_repartida
    asesor = _usuario(db_session, "Commercial_Executive")
    repo = LeadRepository(
        db_session,
        AlcanceDeCartera(usuario_id=asesor.id, toda_la_cartera=False, motivo="prueba"),
    )
    ajeno = db_session.query(Lead).filter(Lead.id == ajenos[0].id).first()
    with pytest.raises(FueraDeAlcance):
        repo.update(ajeno, LeadUpdate(job_title="X"))


# ==============================================================================
# Analíticas
# ==============================================================================

def test_el_resumen_cuenta_solo_la_cartera_propia(client, executive_headers, cartera_repartida):
    """
    Un agregado también revela la cartera ajena.

    Filtrar el listado y dejar el resumen contando la empresa entera sería arreglar la
    puerta y dejar la ventana: sin abrir una sola ficha, un total y una media dicen el
    tamaño y la salud del pipeline completo.
    """
    propios, ajenos = cartera_repartida
    resumen = client.get("/api/v1/analytics/summary", headers=executive_headers).json()

    assert resumen["total_leads"] == len(propios)
    assert resumen["total_leads"] < len(propios) + len(ajenos), (
        "Si el resumen contara la cartera entera, esta comprobación no distinguiría nada: "
        "hace falta que existan prospectos ajenos y que NO estén en el total."
    )
    # La distribución del pipeline es otra vía para el mismo dato.
    assert sum(resumen["pipeline_distribution"].values()) == len(propios)


def test_el_resumen_del_lider_abarca_todo(client, lead_headers, cartera_repartida):
    propios, ajenos = cartera_repartida
    resumen = client.get("/api/v1/analytics/summary", headers=lead_headers).json()
    assert resumen["total_leads"] == len(propios) + len(ajenos)


def test_el_informe_por_campana_es_de_direccion(client, executive_headers, lead_headers):
    """
    No se acota: se restringe.

    Acotarlo daría una rentabilidad falsa —los prospectos de una persona divididos por el
    presupuesto entero de la campaña—, y publicar un número de negocio mal calculado hace
    más daño que no publicarlo.
    """
    assert client.get("/api/v1/analytics/campaigns", headers=executive_headers).status_code == 403
    assert client.get("/api/v1/analytics/campaigns", headers=lead_headers).status_code == 200
