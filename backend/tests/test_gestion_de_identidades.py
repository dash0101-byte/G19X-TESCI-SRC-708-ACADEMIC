"""
N-4: dar de alta, dar de baja y cambiar de rol desde la aplicación, con rastro.

Antes las cuentas solo existían si alguien ejecutaba `seed_data.py` contra la base. Añadir
a una persona, retirar a quien se marchó o cambiarle el rol exigía acceso al servidor, así
que en la práctica lo hacía quien tuviera ese acceso, sin dejar constancia, y el equipo
compartía las tres cuentas de demostración. Un sistema de roles no protege nada si la
forma normal de trabajar es que varias personas usen la misma cuenta.

Las comprobaciones que más importan aquí no son las de «funciona», sino las tres que
impiden dejar el sistema en un estado del que no se puede salir: no quedarse sin
administrador, no poder degradarse a uno mismo, y que un cambio de permisos cierre las
sesiones que llevaban los permisos antiguos dentro del token.
"""
import pytest
from app.models.entities import AuditLog, RefreshToken, User
from tests.conftest import TEST_ACCOUNTS, TEST_PASSWORD

USERS = "/api/v1/users"
ASESORES = "/api/v1/sales-reps"
CONTRASENA_VALIDA = "Rinoceronte-Marino-77"
OTRA_VALIDA = "Bicicleta-Turquesa-2026"


def _usuario(db, rol: str) -> User:
    return db.query(User).filter(User.email == TEST_ACCOUNTS[rol][0]).first()


def _crear(client, admin_headers, **extra):
    cuerpo = {
        "email": "nueva.persona@plurione.com",
        "full_name": "Nueva Persona",
        "role": "Commercial_Executive",
        "password": CONTRASENA_VALIDA,
    }
    cuerpo.update(extra)
    return client.post(USERS, headers=admin_headers, json=cuerpo)


# ==============================================================================
# Quién puede
# ==============================================================================

@pytest.mark.parametrize("rol", ["Sales_Lead", "Commercial_Executive"])
def test_la_gestion_de_cuentas_es_solo_del_administrador(client, auth_headers, rol):
    """
    Ni siquiera el líder comercial. Quien puede cambiar roles puede darse permisos, y
    quien puede restablecer contraseñas puede entrar como otra persona.
    """
    headers = auth_headers(rol)
    assert client.get(USERS, headers=headers).status_code == 403
    assert client.post(USERS, headers=headers, json={}).status_code == 403


def test_el_equipo_comercial_lo_ve_quien_lo_dirige(client, auth_headers):
    """`/sales-reps` sí lo lee el líder: es su equipo y necesita repartir cartera."""
    assert client.get(ASESORES, headers=auth_headers("Sales_Lead")).status_code == 200
    assert client.get(ASESORES, headers=auth_headers("System_Admin")).status_code == 200
    assert client.get(ASESORES, headers=auth_headers("Commercial_Executive")).status_code == 403


def test_ninguna_respuesta_lleva_el_hash(client, admin_headers):
    """
    La comprobación aburrida que evita el desastre silencioso.

    Serializar la entidad `User` sin lista explícita de campos habría publicado
    `hashed_password` en cuanto alguien añadiera un endpoint.
    """
    cuerpo = client.get(USERS, headers=admin_headers).json()
    assert cuerpo["items"]
    for item in cuerpo["items"]:
        assert "hashed_password" not in item
        assert "password" not in item


# ==============================================================================
# Alta
# ==============================================================================

def test_alta_de_una_cuenta(client, admin_headers, db_session):
    respuesta = _crear(client, admin_headers, is_sales_rep=True, capacity=30)
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["email"] == "nueva.persona@plurione.com"
    assert cuerpo["is_sales_rep"] is True
    assert cuerpo["capacity"] == 30
    assert cuerpo["must_change_password"] is True, (
        "El administrador que crea la cuenta conoce esa contraseña; mientras la conozca "
        "otra persona, la cuenta no identifica a nadie."
    )


def test_una_cuenta_que_no_atiende_cartera_no_lleva_capacidad(
    client, admin_headers
):
    """Una capacidad en quien no atiende cartera es un número que nadie usa."""
    cuerpo = _crear(client, admin_headers, is_sales_rep=False, capacity=99).json()
    assert cuerpo["capacity"] is None


def test_no_se_repite_el_correo(client, admin_headers):
    assert _crear(client, admin_headers).status_code == 201
    assert _crear(client, admin_headers).status_code == 409


def test_el_alta_aplica_la_politica_de_contrasenas(client, admin_headers):
    respuesta = _crear(client, admin_headers, password="1234")
    assert respuesta.status_code == 422
    detalle = respuesta.json()["detail"]
    assert detalle["motivos"], "debe decir TODOS los motivos, no solo el primero"


def test_el_alta_queda_en_la_bitacora(
    client, admin_headers, db_session
):
    _crear(client, admin_headers)
    asiento = (
        db_session.query(AuditLog).filter(AuditLog.action == "usuario.crear").first()
    )
    assert asiento is not None
    assert asiento.actor_email == TEST_ACCOUNTS["System_Admin"][0]
    assert asiento.event_metadata["email"] == "nueva.persona@plurione.com"
    assert "password" not in str(asiento.event_metadata).lower(), (
        "El asiento registra que hubo un alta, no cuál fue la credencial."
    )


# ==============================================================================
# Las tres puertas que no se pueden cerrar por dentro
# ==============================================================================

def test_no_se_puede_dejar_el_sistema_sin_administrador(client, admin_headers, db_session):
    """
    El caso no es hipotético: es el administrador que se cambia el rol «para ver cómo lo
    ve un asesor». Sin esta comprobación funciona, y a partir de ese momento no queda
    nadie con permiso para deshacerlo — la única salida es editar la base a mano.
    """
    admin = _usuario(db_session, "System_Admin")
    respuesta = client.post(
        f"{USERS}/{admin.id}/role", params={"rol": "Commercial_Executive"}, headers=admin_headers
    )
    assert respuesta.status_code == 409
    assert "única cuenta de administración activa" in respuesta.json()["detail"]

    db_session.expire_all()
    assert _usuario(db_session, "System_Admin").role == "System_Admin"


def test_tampoco_desactivandose(client, admin_headers, db_session):
    admin = _usuario(db_session, "System_Admin")
    respuesta = client.delete(f"{USERS}/{admin.id}", headers=admin_headers)
    assert respuesta.status_code == 409
    db_session.expire_all()
    assert _usuario(db_session, "System_Admin").is_active is True


def test_con_otro_administrador_activo_si_se_puede(
    client, admin_headers, db_session
):
    """
    La comprobación anterior no debe ser un bloqueo permanente: cuenta administradores,
    no prohíbe la operación.
    """
    suplente = _crear(
        client, admin_headers, email="suplente@plurione.com", role="System_Admin"
    ).json()
    assert suplente["role"] == "System_Admin"

    respuesta = client.post(
        f"{USERS}/{suplente['id']}/role",
        params={"rol": "Commercial_Executive"},
        headers=admin_headers,
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["role"] == "Commercial_Executive"


# ==============================================================================
# Un cambio de permisos cierra las sesiones que los llevaban dentro
# ==============================================================================

def test_degradar_a_alguien_cierra_sus_sesiones(client, admin_headers, db_session):
    """
    El rol viaja dentro del token ya emitido.

    Sin revocar, quien acaba de perder permisos los conserva hasta que su token caduque:
    un usuario degradado seguiría administrando durante los siguientes quince minutos, que
    es tiempo de sobra para hacer justo aquello por lo que se le degradó.
    """
    victima = _usuario(db_session, "Sales_Lead")
    entrada = client.post(
        "/api/v1/auth/login",
        json={"email": victima.email, "password": TEST_PASSWORD},
    )
    assert entrada.status_code == 200
    version_previa = victima.token_version

    vivos_antes = (
        db_session.query(RefreshToken)
        .filter(RefreshToken.user_id == victima.id, RefreshToken.revoked_at.is_(None))
        .count()
    )
    assert vivos_antes >= 1

    respuesta = client.post(
        f"{USERS}/{victima.id}/role",
        params={"rol": "Commercial_Executive"},
        headers=admin_headers,
    )
    assert respuesta.status_code == 200

    db_session.expire_all()
    vivos_despues = (
        db_session.query(RefreshToken)
        .filter(RefreshToken.user_id == victima.id, RefreshToken.revoked_at.is_(None))
        .count()
    )
    assert vivos_despues == 0, "las sesiones con el rol antiguo deben cerrarse"
    assert _usuario(db_session, "Sales_Lead").token_version > version_previa



def test_el_cambio_de_rol_tiene_asiento_propio(client, admin_headers, db_session):
    """
    Existe aparte de `PUT /users/{id}` para que buscar «quién ha cambiado roles este mes»
    no obligue a abrir cada `usuario.actualizar` a ver si tocó ese campo.
    """
    victima = _usuario(db_session, "Commercial_Executive")
    client.post(
        f"{USERS}/{victima.id}/role", params={"rol": "Sales_Lead"}, headers=admin_headers
    )
    asiento = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "usuario.cambio_de_rol")
        .first()
    )
    assert asiento is not None
    assert asiento.event_metadata["rol_anterior"] == "Commercial_Executive"
    assert asiento.event_metadata["rol_nuevo"] == "Sales_Lead"



# ==============================================================================
# Baja lógica
# ==============================================================================

def test_la_baja_no_borra_la_fila(
    client, admin_headers, db_session
):
    """
    Es un `DELETE` que no borra, y esa incoherencia aparente es la decisión.

    Borrar la fila dejaría sin sujeto los asientos de auditoría de esa persona: el registro
    de quién eliminó qué se convertiría en un identificador que ya no resuelve a nadie.
    """
    creado = _crear(client, admin_headers).json()
    respuesta = client.delete(f"{USERS}/{creado['id']}", headers=admin_headers)
    assert respuesta.status_code == 200
    assert respuesta.json()["is_active"] is False

    db_session.expire_all()
    sigue = db_session.query(User).filter(User.id == creado["id"]).first()
    assert sigue is not None, "la cuenta debe seguir existiendo, desactivada"


def test_la_baja_conserva_los_prospectos_asignados(
    client, admin_headers, db_session, cartera_repartida
):
    """
    Reasignar automáticamente al desactivar repartiría cartera sin que nadie lo decidiera.
    El líder los ve y los reparte.
    """
    from app.models.entities import Lead

    _, ajenos = cartera_repartida
    dueno_id = ajenos[0].assigned_rep_id

    respuesta = client.delete(f"{USERS}/{dueno_id}", headers=admin_headers)
    assert respuesta.status_code == 200

    db_session.expire_all()
    siguen = db_session.query(Lead).filter(Lead.assigned_rep_id == dueno_id).count()
    assert siguen == len(ajenos)

    asiento = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "usuario.desactivar")
        .first()
    )
    assert asiento.event_metadata["prospectos_que_atendia"] == len(ajenos)


def test_una_cuenta_desactivada_no_entra(
    client, admin_headers, db_session
):
    creado = _crear(client, admin_headers).json()
    client.delete(f"{USERS}/{creado['id']}", headers=admin_headers)
    respuesta = client.post(
        "/api/v1/auth/login",
        json={"email": creado["email"], "password": CONTRASENA_VALIDA},
    )
    assert respuesta.status_code == 401


def test_reactivar_obliga_a_cambiar_la_contrasena(
    client, admin_headers
):
    """
    Entre la baja y la reactivación pudo pasar cualquier cosa con esa credencial, y
    reactivar con la contraseña antigua intacta es la vía cómoda para reabrir el acceso de
    alguien que ya no debería tenerlo.
    """
    creado = _crear(client, admin_headers).json()
    client.delete(f"{USERS}/{creado['id']}", headers=admin_headers)
    respuesta = client.post(f"{USERS}/{creado['id']}/activate", headers=admin_headers)
    assert respuesta.status_code == 200
    assert respuesta.json()["is_active"] is True
    assert respuesta.json()["must_change_password"] is True


# ==============================================================================
# Restablecimiento por un administrador
# ==============================================================================

def test_el_reset_cierra_las_sesiones_de_la_victima(
    client, admin_headers, db_session
):
    """
    Sin esto, quien tuviera una sesión abierta con la credencial anterior seguiría dentro,
    y el restablecimiento —que suele hacerse justo porque se sospecha de esa credencial—
    no habría cerrado nada.
    """
    creado = _crear(client, admin_headers).json()
    entrada = client.post(
        "/api/v1/auth/login",
        json={"email": creado["email"], "password": CONTRASENA_VALIDA},
    )
    assert entrada.status_code == 200

    respuesta = client.post(
        f"{USERS}/{creado['id']}/reset-password",
        headers=admin_headers,
        json={"nueva_contrasena": OTRA_VALIDA},
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["must_change_password"] is True

    db_session.expire_all()
    vivos = (
        db_session.query(RefreshToken)
        .filter(RefreshToken.user_id == creado["id"], RefreshToken.revoked_at.is_(None))
        .count()
    )
    assert vivos == 0

    # La contraseña antigua deja de valer y la nueva entra.
    assert client.post(
        "/api/v1/auth/login",
        json={"email": creado["email"], "password": CONTRASENA_VALIDA},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"email": creado["email"], "password": OTRA_VALIDA},
    ).status_code == 200


def test_el_reset_aplica_la_politica(client, admin_headers, db_session):
    creado = _crear(client, admin_headers).json()
    respuesta = client.post(
        f"{USERS}/{creado['id']}/reset-password",
        headers=admin_headers,
        json={"nueva_contrasena": "plurione2026"},
    )
    assert respuesta.status_code == 422


def test_el_reset_no_escribe_la_contrasena_en_la_bitacora(
    client, admin_headers, db_session
):
    creado = _crear(client, admin_headers).json()
    client.post(
        f"{USERS}/{creado['id']}/reset-password",
        headers=admin_headers,
        json={"nueva_contrasena": OTRA_VALIDA},
    )
    asientos = db_session.query(AuditLog).all()
    for asiento in asientos:
        assert OTRA_VALIDA not in str(asiento.event_metadata or "")


# ==============================================================================
# El equipo comercial y su carga
# ==============================================================================

def test_los_asesores_traen_su_carga_en_una_sola_consulta(
    client, lead_headers, cartera_repartida, db_session
):
    """
    El conteo sale de una consulta agregada.

    La pantalla de administración lo pedía antes con una petición por asesor contra el
    listado de prospectos —una consulta por persona del equipo, cada una trayendo una
    página entera para leer un total—, y encima contra identificadores fijos escritos en
    el propio componente.
    """
    propios, ajenos = cartera_repartida
    cuerpo = client.get(ASESORES, headers=lead_headers).json()

    por_correo = {item["email"]: item for item in cuerpo["items"]}
    asesor = por_correo[TEST_ACCOUNTS["Commercial_Executive"][0]]
    assert asesor["leads_asignados"] == len(propios)
    assert por_correo["otra.asesora@plurione.com"]["leads_asignados"] == len(ajenos)


def test_un_asesor_sin_cartera_sigue_apareciendo(client, lead_headers, sales_reps):
    """
    El `LEFT JOIN` es deliberado: es precisamente a quien hay que ver para repartirle
    trabajo. Con un JOIN interno desaparecería justo cuando más interesa.
    """
    cuerpo = client.get(ASESORES, headers=lead_headers).json()
    correos = {item["email"]: item["leads_asignados"] for item in cuerpo["items"]}
    assert correos.get("ana.torres@plurione.com") == 0
    assert correos.get("luis.prado@plurione.com") == 0


def test_quien_no_atiende_cartera_no_sale_como_asesor(client, lead_headers, db_session):
    """
    Ser asesor no es un rol: `Sales_Lead` describe qué puede hacer, `is_sales_rep` si se le
    asignan prospectos. Un administrador de TI puede todo y no atiende a nadie.
    """
    admin = _usuario(db_session, "System_Admin")
    admin.is_sales_rep = False
    db_session.commit()

    cuerpo = client.get(ASESORES, headers=lead_headers).json()
    correos = {item["email"] for item in cuerpo["items"]}
    assert TEST_ACCOUNTS["System_Admin"][0] not in correos
