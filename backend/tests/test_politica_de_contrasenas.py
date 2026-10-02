"""
Política de contraseñas y cambio de la propia.

Dos huecos que se cierran aquí. El primero: no había política. El login exigía ocho
caracteres y nada más, así que `password` era una contraseña válida del sistema. El
segundo, y más grave en la práctica: **no había forma de cambiar la contraseña**. Hacerlo
—lo primero que hay que hacer con una recibida de otra persona, y lo urgente cuando se
sospecha que se filtró— exigía que un administrador entrara en el servidor a ejecutar el
script de sembrado, que además reescribía las tres cuentas a la vez. En la práctica eso
significa que las contraseñas no se cambiaban nunca.

Sobre los criterios de la política, que no son la receta habitual: se pide longitud antes
que ceremonia. Exigir mayúscula, número y símbolo produce `Verano2026!` —que cumple las
cuatro reglas y es de las primeras que prueba un diccionario— mientras rechaza
`caballo grapa batería correcta`. Estas pruebas comprueban justamente eso.
"""
import pytest
from app.core.passwords import ContrasenaDebil, evaluar, exigir
from app.models.entities import AuditLog, RefreshToken, User
from tests.conftest import TEST_ACCOUNTS, TEST_PASSWORD

CAMBIO = "/api/v1/auth/change-password"
LOGIN = "/api/v1/auth/login"


def _usuario(db, rol: str) -> User:
    return db.query(User).filter(User.email == TEST_ACCOUNTS[rol][0]).first()


# ==============================================================================
# La política
# ==============================================================================

@pytest.mark.parametrize(
    "contrasena",
    [
        "Rinoceronte-Marino-77",
        "caballo grapa bateria correcta",   # larga: no necesita variedad
        "Zx9!kLmQ2rTv",                     # 12 con cuatro clases
        "café con leche y pan tostado",
    ],
)
def test_contrasenas_que_deben_aceptarse(contrasena):
    assert evaluar(contrasena) == [], f"{contrasena!r} debería valer: {evaluar(contrasena)}"


@pytest.mark.parametrize(
    ("contrasena", "razon"),
    [
        ("corta1!", "menos de 12 caracteres"),
        ("password", "está en la lista de las primeras que se prueban"),
        ("plurione2026", "contiene el nombre del producto"),
        ("aaaaaaaaaaaaaaa", "repite el mismo carácter"),
        ("contraseñalarga", "15 caracteres con una sola clase de carácter"),
        ("  Rinoceronte-77  ", "espacios en los extremos"),
    ],
)
def test_contrasenas_que_deben_rechazarse(contrasena, razon):
    assert evaluar(contrasena), f"{contrasena!r} debería rechazarse: {razon}"


def test_la_ceremonia_no_gana_a_la_longitud():
    """
    El caso que justifica la forma de esta política.

    `Verano2026!` cumple las cuatro reglas clásicas —mayúscula, minúscula, dígito y
    símbolo— y es una de las primeras que prueba cualquier diccionario. La frase larga no
    cumple ninguna salvo la longitud, y es incomparablemente más fuerte.
    """
    assert evaluar("Verano2026!"), "una contraseña de 11 con ceremonia no debe pasar"
    assert evaluar("mi perro se llama tomas") == []


def test_no_se_admite_el_propio_nombre_ni_el_correo():
    motivos = evaluar("elena.ruiz.segura.2026", email="elena.ruiz@fintechmx.com")
    assert motivos
    assert any("su propio nombre" in m for m in motivos)


def test_el_maximo_se_mide_en_bytes():
    """
    bcrypt trunca a 72 BYTES. Una contraseña llena de acentos ocupa más de lo que aparenta,
    y aceptarla dejaría fuera un trozo sin que nadie se enterara: quien la eligió creería
    tener una protección que no tiene.
    """
    con_acentos = "á" * 40  # 80 bytes en UTF-8, 40 caracteres
    assert len(con_acentos) < 72
    motivos = evaluar(con_acentos)
    assert any("bytes" in m for m in motivos)


def test_se_devuelven_todos_los_motivos_no_el_primero():
    """
    Dar uno solo obliga a descubrir la política a base de intentos, y cada rechazo empuja
    un poco más hacia poner lo primero que se acepte.
    """
    with pytest.raises(ContrasenaDebil) as excinfo:
        exigir("abc", email="ana@plurione.com", nombre="Ana")
    assert len(excinfo.value.motivos) >= 2


# ==============================================================================
# Cambio de la propia contraseña
# ==============================================================================

def test_cambiar_la_contrasena_propia(client, db_session, auth_headers):
    usuario = _usuario(db_session, "Commercial_Executive")
    nueva = "Girasol-Nocturno-31"

    respuesta = client.post(
        CAMBIO,
        headers=auth_headers("Commercial_Executive"),
        json={"contrasena_actual": TEST_PASSWORD, "nueva_contrasena": nueva},
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["sesiones_cerradas"] >= 0

    assert client.post(
        LOGIN, json={"email": usuario.email, "password": nueva}
    ).status_code == 200
    assert client.post(
        LOGIN, json={"email": usuario.email, "password": TEST_PASSWORD}
    ).status_code == 401



def test_sin_la_contrasena_actual_no_se_cambia(client, executive_headers):
    """
    La comprobación central de este endpoint.

    Un token robado, o un equipo que alguien dejó abierto, permite todo lo que la
    aplicación permita sin volver a preguntar. Exigir la credencial actual es lo único que
    impide convertir ese acceso prestado en un acceso permanente: si el token bastara, el
    robo de una sesión de quince minutos se transformaría en la pérdida definitiva de la
    cuenta.
    """
    respuesta = client.post(
        CAMBIO,
        headers=executive_headers,
        json={"contrasena_actual": "loQueSea123!", "nueva_contrasena": "Girasol-Nocturno-31"},
    )
    assert respuesta.status_code == 401


def test_el_intento_fallido_queda_registrado(client, executive_headers, db_session):
    client.post(
        CAMBIO,
        headers=executive_headers,
        json={"contrasena_actual": "loQueSea123!", "nueva_contrasena": "Girasol-Nocturno-31"},
    )
    asiento = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "usuario.cambio_de_contrasena_propia")
        .first()
    )
    assert asiento is not None
    assert asiento.outcome == "HTTP_401"
    assert asiento.event_metadata["motivo"] == "contrasena_actual_incorrecta"


def test_no_vale_repetir_la_misma(client, executive_headers):
    """«Cambiarla» por la misma no cambia nada, y un 200 haría creer que sí."""
    respuesta = client.post(
        CAMBIO,
        headers=executive_headers,
        json={"contrasena_actual": TEST_PASSWORD, "nueva_contrasena": TEST_PASSWORD},
    )
    assert respuesta.status_code == 422
    assert "igual a la actual" in str(respuesta.json()["detail"])


def test_la_nueva_pasa_por_la_politica(client, executive_headers):
    respuesta = client.post(
        CAMBIO,
        headers=executive_headers,
        json={"contrasena_actual": TEST_PASSWORD, "nueva_contrasena": "plurione"},
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["detail"]["motivos"]


def test_el_cambio_cierra_todas_las_sesiones(client, db_session, auth_headers):
    """
    Incluida la que hizo el cambio, y eso es lo importante.

    Quien cambia su contraseña casi siempre lo hace porque cree que alguien más la tiene;
    dejar vivas las sesiones abiertas con la credencial anterior deja dentro precisamente a
    quien se quería echar. Cerrar solo «las demás» tampoco vale: no hay forma de saber cuál
    de dos sesiones es la legítima.
    """
    usuario = _usuario(db_session, "Sales_Lead")
    client.post(LOGIN, json={"email": usuario.email, "password": TEST_PASSWORD})
    client.post(LOGIN, json={"email": usuario.email, "password": TEST_PASSWORD})

    vivas_antes = (
        db_session.query(RefreshToken)
        .filter(RefreshToken.user_id == usuario.id, RefreshToken.revoked_at.is_(None))
        .count()
    )
    assert vivas_antes >= 2, "hacen falta varias sesiones para que la prueba diga algo"

    nueva = "Estanteria-Violeta-88"
    respuesta = client.post(
        CAMBIO,
        headers=auth_headers("Sales_Lead"),
        json={"contrasena_actual": TEST_PASSWORD, "nueva_contrasena": nueva},
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["sesiones_cerradas"] >= vivas_antes

    db_session.expire_all()
    vivas_despues = (
        db_session.query(RefreshToken)
        .filter(RefreshToken.user_id == usuario.id, RefreshToken.revoked_at.is_(None))
        .count()
    )
    assert vivas_despues == 0



def test_el_cambio_propio_retira_la_marca_de_contrasena_prestada(
    client, db_session, auth_headers
):
    """`must_change_password` se pone al recibirla de otro y se quita al hacerla propia."""
    usuario = _usuario(db_session, "Commercial_Executive")
    usuario.must_change_password = True
    db_session.commit()

    nueva = "Escalera-Naranja-42"
    respuesta = client.post(
        CAMBIO,
        headers=auth_headers("Commercial_Executive"),
        json={"contrasena_actual": TEST_PASSWORD, "nueva_contrasena": nueva},
    )
    assert respuesta.status_code == 200

    db_session.expire_all()
    fila = db_session.query(User).filter(User.id == usuario.id).first()
    assert fila.must_change_password is False
    assert fila.password_changed_at is not None



def test_el_endpoint_exige_estar_autenticado(client):
    respuesta = client.post(
        CAMBIO,
        json={"contrasena_actual": "x" * 12, "nueva_contrasena": "Girasol-Nocturno-31"},
    )
    assert respuesta.status_code == 401


# ==============================================================================
# La forma de cada rechazo, que es lo que la pantalla lee (capítulo 43)
# ==============================================================================
#
# Las pruebas de arriba comprueban el código de estado y, en un caso, que el detalle lleve
# `motivos`. Esta comprueba la **forma completa de las tres respuestas**, y existe porque el
# cliente depende de ella de una manera que no se ve desde aquí.
#
# Ninguno de estos tres rechazos es un 422 de Pydantic, así que ninguno trae `loc`: son
# `HTTPException` escritas en el endpoint. El panel necesita saber de qué campo habla cada
# una para marcarlo y llevar el foco, y como no lo puede leer, lo sabe por el contrato:
# `erroresDeLaContrasena` —en `frontend/src/components/erroresDeFormulario.js`— manda el 401
# a la contraseña actual y el 422 a la nueva. Si alguien cambiara aquí un código o moviera
# los motivos a otra clave, esa pantalla señalaría el campo equivocado o dejaría de enseñar
# lo que falla, y nada de este lado se pondría rojo. Ahora sí.
#
# Y el motivo por el que esto no se descubrió antes vale la pena: la lista de `motivos`
# **nunca llegó a la pantalla**. `parseApiError` se quedaba con el titular del detalle
# estructurado y tiraba la lista, y las dos pruebas de cliente que decían comprobarlo
# fabricaban el mensaje con los motivos ya dentro, una capa por debajo de donde estaba el
# fallo. Las tres capas tienen hoy su prueba: aquí la forma, en `services/api.test.js` la
# lectura, y en los dos formularios el reparto.

def test_la_contrasena_actual_incorrecta_contesta_401_con_un_detalle_de_texto(
    client, executive_headers
):
    respuesta = client.post(
        CAMBIO,
        headers=executive_headers,
        json={"contrasena_actual": "loQueSea123!", "nueva_contrasena": "Girasol-Nocturno-31"},
    )
    assert respuesta.status_code == 401
    detalle = respuesta.json()["detail"]
    assert isinstance(detalle, str), "el cliente lo enseña tal cual: si fuera un objeto, no"
    assert "actual" in detalle


def test_la_politica_contesta_422_con_mensaje_y_motivos(client, executive_headers):
    respuesta = client.post(
        CAMBIO,
        headers=executive_headers,
        json={"contrasena_actual": TEST_PASSWORD, "nueva_contrasena": "plurione"},
    )
    assert respuesta.status_code == 422
    detalle = respuesta.json()["detail"]
    assert isinstance(detalle, dict)
    # Las dos claves, con estos nombres: el cliente enseña el mensaje y, detrás, un renglón
    # por motivo. Son los que explican qué hay que corregir.
    assert isinstance(detalle["mensaje"], str) and detalle["mensaje"]
    assert isinstance(detalle["motivos"], list) and detalle["motivos"]
    assert all(isinstance(m, str) and m for m in detalle["motivos"])
    # Y no trae `loc`: por eso el campo lo sabe el cliente y no lo lee.
    assert "loc" not in detalle


def test_repetir_la_misma_contesta_422_con_mensaje_y_sin_motivos(client, executive_headers):
    respuesta = client.post(
        CAMBIO,
        headers=executive_headers,
        json={"contrasena_actual": TEST_PASSWORD, "nueva_contrasena": TEST_PASSWORD},
    )
    assert respuesta.status_code == 422
    detalle = respuesta.json()["detail"]
    # Este llega como texto, no como objeto, y el cliente lo trata igual: un 422 de esta
    # puerta habla de la contraseña nueva en los dos casos.
    assert isinstance(detalle, str)
    assert "igual a la actual" in detalle


def test_el_restablecimiento_de_otra_cuenta_rechaza_con_la_misma_forma(
    client, admin_headers, db_session
):
    """
    El panel de administración fija la contraseña de otra persona por esta puerta.

    Hasta el capítulo 43 la pedía con un `window.prompt` —en claro, sin repetición y sin
    sitio donde enseñar estos motivos—. Ahora es un formulario de la página que los pone
    debajo del campo, y para eso necesita que este rechazo tenga la misma forma que el otro.
    """
    usuario = _usuario(db_session, "Commercial_Executive")
    respuesta = client.post(
        f"/api/v1/users/{usuario.id}/reset-password",
        headers=admin_headers,
        json={"nueva_contrasena": "plurione"},
    )
    assert respuesta.status_code == 422
    detalle = respuesta.json()["detail"]
    assert isinstance(detalle, dict)
    assert detalle["mensaje"]
    assert detalle["motivos"]
