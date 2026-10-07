"""
Las guardas de «esto ya estaba así», y la coherencia de la capacidad.

Cinco operaciones sobre una cuenta llevan escrita una salida temprana para cuando no hay
nada que cambiar, y ninguna de las cinco se ejercitaba. No son adorno: cada una evita un
efecto que no se ve en la respuesta pero sí en quien está trabajando.

* **Cambiar el rol al que ya tiene** cerraría todas las sesiones de esa persona y le subiría
  la versión del token. Un administrador que pulsa dos veces, o una pantalla que manda el
  formulario completo, echaría del sistema a alguien sin cambiarle nada.
* **Desactivar una cuenta ya desactivada** volvería a cerrar sesiones que no existen y a
  subir el contador.
* **Reactivar una cuenta que está activa** le pondría `must_change_password`: a quien está
  trabajando le saldría de pronto la pantalla de cambio obligatorio de contraseña.
* **Una edición con el cuerpo vacío** —lo que manda un formulario del que no se tocó nada—
  no tiene que escribir nada ni anotar campos cambiados.

Y la coherencia de la capacidad, que es la otra mitad sin probar de la edición: quien deja
de ser asesor no conserva un número de huecos que ya no significa nada, y quien pasa a
serlo necesita uno. El reparto automático ordena por esa columna, así que una capacidad
heredada por una cuenta que ya no atiende cartera es un hueco fantasma en el reparto.

El rol, además, no se podía cambiar desde la edición en ninguna prueba: `PUT /users/{id}`
acepta `role` y ese camino —con su cierre de sesiones y su anotación del rol resultante—
estaba entero sin recorrer, aunque el endpoint dedicado sí lo estuviera.
"""
import uuid

import pytest

# La capacidad por omisión se importa en vez de escribirse: aquí no se comprueba cuánto
# vale, se comprueba la regla de coherencia —asesor con capacidad, no asesor sin ella—. Si
# alguien decide que son 40 en lugar de 50, esta prueba no tiene por qué ponerse roja.
from app.api.v1.endpoints.users import CAPACIDAD_POR_DEFECTO
from app.core.security import UserRole
from app.models.entities import AuditLog, User
from app.services.session_service import abrir_sesion

USUARIOS = "/api/v1/users"


@pytest.fixture
def cuenta(db_session):
    """Una cuenta cualquiera que no es la de nadie que esté haciendo la petición."""
    marca = uuid.uuid4().hex[:8]
    usuario = User(
        email=f"operada-{marca}@plurione.com",
        full_name=f"Cuenta Operada {marca}",
        role=UserRole.COMMERCIAL_EXECUTIVE.value,
        hashed_password="!sin-contrasena:fixture",
        is_active=True,
        is_sales_rep=False,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    return usuario


def test_pedir_una_cuenta_que_no_existe_es_404(client, admin_headers):
    """
    Lo que contesta `_buscar`, que es por donde pasan seis endpoints de este archivo.

    Sin ella, el `None` seguiría adelante y el fallo saldría más abajo como un 500 sobre un
    atributo de `None`, en cualquiera de los seis.
    """
    respuesta = client.get(f"{USUARIOS}/9000001", headers=admin_headers)

    assert respuesta.status_code == 404
    assert "9000001" in respuesta.json()["detail"]


def test_una_edicion_sin_nada_dentro_no_cambia_nada(client, admin_headers, cuenta, db_session):
    """
    El cuerpo vacío es lo que manda un formulario del que no se tocó ningún campo.

    Lo observable de la salida temprana está en la **bitácora**: sin ella se recorre todo lo
    demás con `datos` vacío y el asiento queda anotado con `campos: []` y
    `sesiones_cerradas: 0`, de modo que abrir y cerrar la pantalla de una cuenta deja escrito
    que esa cuenta se modificó. Lo que se guarda en un registro que no se puede borrar
    conviene que sea verdad.
    """
    version_antes = cuenta.token_version
    nombre_antes = cuenta.full_name

    respuesta = client.put(f"{USUARIOS}/{cuenta.id}", json={}, headers=admin_headers)

    assert respuesta.status_code == 200
    db_session.refresh(cuenta)
    assert cuenta.full_name == nombre_antes
    assert cuenta.token_version == version_antes

    asiento = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_id == str(cuenta.id))
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert asiento is not None, "la consulta queda registrada aunque no cambie nada"
    assert "campos" not in (asiento.event_metadata or {})


def test_cambiar_el_rol_desde_la_edicion_cierra_las_sesiones(
    client, admin_headers, cuenta, db_session
):
    """
    El camino del rol dentro de `PUT /users/{id}`, que no recorría ninguna prueba.

    Lo que importa de este camino no es que la columna cambie: es que la sesión abierta de
    quien acaba de perder permisos deje de valer. Sin el cierre y sin la subida de la
    versión, un asesor degradado conserva sus permisos hasta que caduque su token.
    """
    abrir_sesion(db_session, cuenta, ip="203.0.113.7")
    version_antes = cuenta.token_version

    respuesta = client.put(
        f"{USUARIOS}/{cuenta.id}",
        json={"role": UserRole.SALES_LEAD.value},
        headers=admin_headers,
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["role"] == UserRole.SALES_LEAD.value
    db_session.refresh(cuenta)
    assert cuenta.role == UserRole.SALES_LEAD.value
    assert cuenta.token_version == version_antes + 1


def test_quien_pasa_a_ser_asesor_recibe_una_capacidad_y_quien_deja_de_serlo_la_pierde(
    client, admin_headers, cuenta, db_session
):
    """
    Las dos mitades de la coherencia, en una cuenta y en los dos sentidos.

    El reparto automático ordena a los asesores por su capacidad. Una cuenta que ya no
    atiende cartera y conserva «25 huecos» es un destino posible para el reparto de una
    ficha; y una que pasa a atenderla sin capacidad declarada no entra en ningún reparto,
    que es el mismo fallo visto del revés.
    """
    assert cuenta.is_sales_rep is False
    assert cuenta.capacity is None

    client.put(f"{USUARIOS}/{cuenta.id}", json={"is_sales_rep": True}, headers=admin_headers)
    db_session.refresh(cuenta)
    assert cuenta.capacity == CAPACIDAD_POR_DEFECTO

    client.put(f"{USUARIOS}/{cuenta.id}", json={"is_sales_rep": False}, headers=admin_headers)
    db_session.refresh(cuenta)
    assert cuenta.capacity is None


def test_cambiar_el_rol_al_que_ya_tiene_no_echa_a_nadie(client, admin_headers, cuenta, db_session):
    """
    Pulsar dos veces, o mandar el formulario completo sin tocar el rol.

    Sin la salida temprana, la segunda vez cierra las sesiones y sube la versión del token:
    la persona se encuentra fuera del sistema y nada ha cambiado. El asiento de la bitácora
    se escribe de todas formas —la intención queda registrada—, y eso es correcto: lo que no
    debe ocurrir es el efecto.
    """
    abrir_sesion(db_session, cuenta, ip="203.0.113.7")
    version_antes = cuenta.token_version
    mismo_rol = cuenta.role

    respuesta = client.post(
        f"{USUARIOS}/{cuenta.id}/role", params={"rol": mismo_rol}, headers=admin_headers
    )

    assert respuesta.status_code == 200, respuesta.text
    db_session.refresh(cuenta)
    assert cuenta.role == mismo_rol
    assert cuenta.token_version == version_antes


def test_ascender_a_administracion_cierra_igual_las_sesiones(
    client, admin_headers, cuenta, db_session
):
    """
    Ascender a administración es el único cambio de rol que se salta las dos comprobaciones
    —«que quede un administrador» y «no sobre uno mismo»—, y no tenía ninguna prueba.

    Ese salto no tiene hoy consecuencia observable: la primera comprobación se retira sola
    cuando la cuenta afectada no es un administrador activo, y a la segunda no se llega
    ascendiendo a otra persona. Así que lo que esta prueba fija no es el salto, es lo que sí
    se puede romper: **un cambio de rol cierra las sesiones abiertas**. Un token emitido
    antes lleva la versión anterior; sin subirla, la sesión que había sigue viva con permisos
    distintos de los que tenía cuando se abrió.
    """
    abrir_sesion(db_session, cuenta, ip="203.0.113.7")
    version_antes = cuenta.token_version

    respuesta = client.post(
        f"{USUARIOS}/{cuenta.id}/role",
        params={"rol": UserRole.SYSTEM_ADMIN.value},
        headers=admin_headers,
    )

    assert respuesta.status_code == 200, respuesta.text
    db_session.refresh(cuenta)
    assert cuenta.role == UserRole.SYSTEM_ADMIN.value
    assert cuenta.token_version == version_antes + 1


def test_desactivar_una_cuenta_ya_desactivada_no_vuelve_a_cerrar_nada(
    client, admin_headers, cuenta, db_session
):
    """La segunda baja no tiene efecto, y la versión del token lo demuestra."""
    primera = client.delete(f"{USUARIOS}/{cuenta.id}", headers=admin_headers)
    assert primera.status_code == 200, primera.text
    db_session.refresh(cuenta)
    assert cuenta.is_active is False
    version_tras_la_baja = cuenta.token_version

    segunda = client.delete(f"{USUARIOS}/{cuenta.id}", headers=admin_headers)

    assert segunda.status_code == 200
    db_session.refresh(cuenta)
    assert cuenta.is_active is False
    assert cuenta.token_version == version_tras_la_baja


def test_reactivar_una_cuenta_que_esta_activa_no_le_pide_cambiar_la_contrasena(
    client, admin_headers, cuenta, db_session
):
    """
    Reactivar fuerza el cambio de contraseña a propósito: entre la baja y la vuelta pudo
    pasar cualquier cosa con esa credencial.

    Pero sobre una cuenta que nunca se fue, ese efecto es una pantalla de cambio obligatorio
    que le aparece a alguien que está trabajando, sin que nadie haya tocado su cuenta.
    """
    assert cuenta.is_active is True
    assert cuenta.must_change_password is False

    respuesta = client.post(f"{USUARIOS}/{cuenta.id}/activate", headers=admin_headers)

    assert respuesta.status_code == 200, respuesta.text
    db_session.refresh(cuenta)
    assert cuenta.is_active is True
    assert cuenta.must_change_password is False
