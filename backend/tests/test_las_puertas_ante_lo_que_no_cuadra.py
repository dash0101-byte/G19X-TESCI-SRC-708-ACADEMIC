"""
Lo que hacen las puertas cuando el token, el hash o la entrega no cuadran.

Las tres puertas del sistema —la resolución de identidad, el refresco de sesión y la
verificación de una entrega firmada— están probadas por el camino bueno y por los rechazos
más visibles. Lo que no estaba probado son los bordes, y un borde sin probar en una puerta
no se nota hasta que alguien lo encuentra:

* **bcrypt corta a 72 bytes.** Una contraseña más larga se resumiría por sus primeros 72:
  dos contraseñas distintas que compartan ese prefijo serían la misma credencial. La
  función se niega en vez de resumir, y nadie lo comprobaba.
* **Un hash corrupto en la base** —una fila escrita a mano, una fixture, una migración a
  medias— tiene que dar credenciales inválidas, no un 500 que delata que esa cuenta existe.
* **El tope de tamaño del webhook se comprueba dos veces**, y la segunda es la que importa:
  una entrega con `Transfer-Encoding: chunked` no declara `Content-Length` y esquivaría la
  primera. Esa segunda comprobación no la ejercitaba ninguna prueba.
* **La rotación de refresco** distingue un token que no está registrado, uno que venció,
  uno sin identificador de emisión y uno cuyo `jti` pertenece a otra cuenta. El último es
  manipulación y tira la familia entera; era el único de los cuatro sin prueba.
* **El segundo factor** tiene dos caminos de error en el alta —no iniciada y código
  equivocado— que el servicio sí probaba y el endpoint no: son un 409 y un 422, y lo que ve
  quien está delante de la pantalla es eso.

Tres pruebas llaman al endpoint directamente en vez de pasar por HTTP. Es a propósito y es
lo único que se puede hacer: la rama que cubren es la de «la cuenta del token ya no existe»,
y por HTTP no se llega nunca, porque la dependencia que resuelve la identidad ya ha leído
esa fila y habría devuelto 401. Para que el cuerpo del endpoint la vea en None haría falta
que la fila desapareciera entre la dependencia y el cuerpo. La rama se queda porque eso es
exactamente lo que pasa con una cuenta borrada en otra pestaña mientras la petición vuela.
"""
import datetime
import uuid

import jwt
import pytest
from app.api.v1.endpoints import auth as endpoints_auth
from app.core import security as modulo_seguridad
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import (
    BCRYPT_MAX_PASSWORD_BYTES,
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_DESAFIO,
    TOKEN_TYPE_REFRESH,
    CurrentUser,
    UserRole,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.entities import AuditLog, RefreshToken, User, utc_now
from app.services import session_service
from app.services.session_service import (
    MOTIVO_REUTILIZADO,
    ReutilizacionDetectada,
    abrir_sesion,
    rotar_sesion,
)
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response
from tests.conftest import (
    TEST_ACCOUNTS,
    TEST_PASSWORD,
    codigo_del_segundo_factor,
    sign_webhook,
)

AUTH = "/api/v1/auth"
PROTEGIDA = "/api/v1/leads"
WEBHOOK = "/api/v1/crm/webhook"


def _cuenta(db, correo=None, rol="Commercial_Executive", activa=True) -> User:
    usuario = User(
        email=correo or f"puerta-{uuid.uuid4().hex[:8]}@plurione.com",
        full_name="Cuenta de prueba",
        role=rol,
        hashed_password=hash_password(TEST_PASSWORD),
        is_active=activa,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def _claims(usuario, tipo=TOKEN_TYPE_ACCESS, **cambios) -> dict:
    ahora = datetime.datetime.now(datetime.timezone.utc)
    claims = {
        "sub": str(usuario.id),
        "typ": tipo,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": int(ahora.timestamp()),
        "nbf": int(ahora.timestamp()),
        "exp": int((ahora + datetime.timedelta(minutes=10)).timestamp()),
        "jti": uuid.uuid4().hex,
        "ver": usuario.token_version,
    }
    claims.update(cambios)
    return claims


def _firmar(claims: dict) -> str:
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _identidad(usuario) -> CurrentUser:
    return CurrentUser(
        user_id=str(usuario.id),
        email=usuario.email,
        name=usuario.full_name,
        role=UserRole(usuario.role),
    )


def _peticion() -> Request:
    """Lo mínimo que necesitan los endpoints que se llaman directamente: cliente y cabeceras."""
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "query_string": b"",
            "headers": [(b"user-agent", b"prueba")],
            "client": ("203.0.113.7", 1234),
        }
    )


# ==============================================================================
# El tope de bcrypt y los hashes que no son hashes
# ==============================================================================

@pytest.mark.parametrize(
    "contrasena",
    [
        "a" * (BCRYPT_MAX_PASSWORD_BYTES + 1),
        # Veinticinco caracteres de tres bytes: setenta y cinco bytes con menos letras que el
        # tope, que es la forma de pasarse sin darse cuenta.
        "ñ" * 40,
    ],
    ids=["setenta y tres letras", "cuarenta letras de dos bytes"],
)
def test_una_contrasena_por_encima_del_tope_de_bcrypt_no_se_resume(contrasena):
    """
    bcrypt corta a 72 bytes en silencio, y resumir es peor que negarse.

    Con el corte, dos contraseñas que compartan los primeros 72 bytes son la misma
    credencial: quien conozca una entra con la otra. Y la persona que eligió una de 90
    caracteres creería tener una de 90.
    """
    assert len(contrasena.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES

    with pytest.raises(ValueError) as fallo:
        hash_password(contrasena)

    # El mensaje, y no solo el tipo. La biblioteca también se niega —desde bcrypt 4—, con un
    # texto en inglés que acabaría en la cara de quien eligió la contraseña: quitar esta
    # guarda no cambia el resultado, cambia lo que se lee. Eso es lo que aquí se fija.
    assert "La contraseña excede el máximo" in str(fallo.value)
    assert str(BCRYPT_MAX_PASSWORD_BYTES) in str(fallo.value)


def test_una_contrasena_por_encima_del_tope_no_llega_a_bcrypt(monkeypatch):
    """
    Al comprobar no se puede lanzar —sería un 500 en el login en vez de un 401— y tampoco se
    le puede entregar entera a bcrypt.

    Lo que se mide es que **no se llame**. La versión instalada se niega, pero bcrypt 3.x
    truncaba en silencio, y con el truncado una contraseña equivocada que comparta los
    primeros 72 bytes con la buena entra. Comprobar solo el valor devuelto no distingue las
    dos implementaciones, porque las dos acaban en False: la de ahora porque lanza y el
    `except` lo recoge, la de antes porque compararía el prefijo. Con la llamada vigilada sí
    se distinguen, y es la única forma de que esto siga valiendo si la biblioteca cambia.
    """
    guardado = hash_password("a" * BCRYPT_MAX_PASSWORD_BYTES)
    llamadas = []
    de_verdad = modulo_seguridad.bcrypt.checkpw

    def _vigilada(contrasena, resumen):
        llamadas.append(len(contrasena))
        return de_verdad(contrasena, resumen)

    monkeypatch.setattr(modulo_seguridad.bcrypt, "checkpw", _vigilada)

    assert verify_password("a" * BCRYPT_MAX_PASSWORD_BYTES, guardado) is True
    assert llamadas == [BCRYPT_MAX_PASSWORD_BYTES]

    assert verify_password("a" * (BCRYPT_MAX_PASSWORD_BYTES + 1), guardado) is False
    assert llamadas == [BCRYPT_MAX_PASSWORD_BYTES], "la contraseña larga llegó a bcrypt"


@pytest.mark.parametrize(
    "guardado",
    ["", "no-es-un-hash", "$2b$12$demasiado-corto", "!sin-contrasena:fixture"],
)
def test_un_hash_que_no_es_un_hash_son_credenciales_invalidas_y_no_un_500(guardado):
    """
    Una fila con el hash corrupto existe: la escribe una fixture, una carga de datos o una
    migración a medias. El valor `!sin-contrasena:...` es justamente lo que este repositorio
    pone en las cuentas que no tienen que poder entrar.

    Si la excepción saliera, el login contestaría 500 para esa cuenta y 401 para una
    inexistente: la diferencia dice qué correos están dados de alta.
    """
    assert verify_password(TEST_PASSWORD, guardado) is False


# ==============================================================================
# La resolución de identidad
# ==============================================================================

def test_un_token_sin_sujeto_no_pasa_de_la_decodificacion(db_session):
    """
    `sub` vacío pasa la firma —la firma es nuestra— y no identifica a nadie.

    Se comprueba sobre `decode_token` y no a través de una ruta a propósito: por la ruta
    protegida el rechazo saldría igual, porque `int("")` falla unas líneas más abajo, así que
    una prueba de extremo a extremo no mide esta guarda. Y `decode_token` tiene cuatro usos
    —identidad, refresco, desafío del segundo factor y la página de interés—; solo uno de
    ellos convierte el sujeto a entero. Los otros tres son lo que esta guarda cubre.
    """
    usuario = _cuenta(db_session)
    token = _firmar(_claims(usuario, sub=""))

    with pytest.raises(HTTPException) as fallo:
        decode_token(token, TOKEN_TYPE_ACCESS)

    assert fallo.value.status_code == 401


def test_un_token_cuyo_sujeto_no_es_un_numero_no_vale(client, db_session):
    """
    El `sub` se convierte a entero para buscar la cuenta, y la conversión puede fallar.

    Un token firmado con `sub: "admin"` es un token legítimo en todo lo demás: lo que lo
    rechaza es esta conversión, y sin ella el `ValueError` saldría como 500.
    """
    usuario = _cuenta(db_session)
    token = _firmar(_claims(usuario, sub="admin"))

    respuesta = client.get(PROTEGIDA, headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 401


def test_una_cuenta_con_un_rol_que_ya_no_existe_recibe_un_403_explicado(client, db_session):
    """
    El rol se guarda como texto y se convierte al enumerado en cada petición.

    Pasa al retirar un rol del sistema con cuentas que lo tenían, o con una fila cargada a
    mano. Lo que no puede pasar es un 500: la persona tiene que leer qué hacer, y queda un
    error en el registro con el correo y el rol para poder arreglar la fila.
    """
    usuario = _cuenta(db_session, rol="Jefe_Supremo")
    token = _firmar(_claims(usuario))

    respuesta = client.get(PROTEGIDA, headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 403
    assert "rol asignado" in respuesta.json()["detail"]


# ==============================================================================
# La verificación de una entrega firmada
# ==============================================================================

def test_con_la_integracion_del_crm_apagada_el_webhook_no_existe(client, monkeypatch):
    """
    404 y no 403: quien no tiene por qué saber que hay un CRM conectado no lo averigua aquí.

    Es la misma respuesta que da una ruta que no existe, y la misma que dan las otras cuatro
    integraciones cuando están apagadas.
    """
    monkeypatch.setattr(settings, "INTEGRACION_CRM_ACTIVA", False)
    body, headers = sign_webhook({"event": "lead.created", "data": {}})

    respuesta = client.post(WEBHOOK, content=body, headers=headers)

    assert respuesta.status_code == 404


def test_un_content_length_que_no_es_un_numero_se_rechaza(client):
    """
    La cabecera la escribe quien llama, así que puede no ser un número.

    Sin la conversión protegida, el `ValueError` saldría como 500 desde una ruta a la que se
    llega sin autenticarse: eso es un corte de servicio a coste cero para quien lo mande.
    """
    body, headers = sign_webhook({"event": "lead.created", "data": {}})
    headers["content-length"] = "muchos"

    respuesta = client.post(WEBHOOK, content=body, headers=headers)

    assert respuesta.status_code == 401


def test_un_cuerpo_excesivo_sin_declarar_su_tamano_tambien_se_corta(client):
    """
    La segunda mitad del tope de tamaño, que es la que de verdad protege.

    La primera comprobación mira `Content-Length`, y una entrega con
    `Transfer-Encoding: chunked` no lo manda: pasaría el primer control y el cuerpo se
    leería entero en memoria. Se envía con un generador, que es lo que hace que el cliente
    no declare el tamaño.
    """
    exceso = b"A" * (settings.CRM_WEBHOOK_MAX_BODY_BYTES + 2048)

    def _por_trozos():
        yield exceso

    _, headers = sign_webhook({"event": "lead.created", "data": {}})
    headers.pop("content-length", None)

    respuesta = client.post(WEBHOOK, content=_por_trozos(), headers=headers)

    assert respuesta.status_code == 413


# ==============================================================================
# La rotación del refresco
# ==============================================================================

def test_normalizar_una_fecha_sin_zona_no_toca_la_que_ya_la_trae():
    """
    SQLite devuelve las fechas sin zona y PostgreSQL con ella: las dos ramas son reales.

    La suite corre sobre SQLite, así que la rama que se ejercita siempre es la de añadir la
    zona; la otra —devolver tal cual lo que ya viene con zona— es la que se recorre en
    producción en cada refresco. Comparar un `datetime` con zona contra uno sin ella es un
    `TypeError` en Python, de modo que equivocar esto rompe el refresco justo donde no se
    mide.
    """
    assert session_service._aware(None) is None

    sin_zona = datetime.datetime(2026, 10, 7, 12, 0, 0)
    con_zona = datetime.datetime(2026, 10, 7, 12, 0, 0, tzinfo=datetime.timezone.utc)

    assert session_service._aware(sin_zona) == con_zona
    assert session_service._aware(con_zona) is con_zona


def test_un_refresco_sin_identificador_de_emision_no_rota(db_session):
    """
    El `jti` es lo que ata la cookie a su fila de `refresh_tokens`.

    Un token firmado sin él es anterior al registro de emisiones o está fabricado: no hay
    forma de saber si ya se consumió, que es toda la defensa contra la reutilización.
    """
    usuario = _cuenta(db_session)

    with pytest.raises(ValueError) as fallo:
        rotar_sesion(db_session, usuario, {"sub": str(usuario.id)}, ip="203.0.113.7")

    assert "identificador de emisión" in str(fallo.value)


def test_un_refresco_registrado_a_nombre_de_otra_cuenta_tira_la_familia(db_session):
    """
    El `sub` del token dice una cuenta y el dueño registrado del `jti` dice otra.

    No debería ocurrir nunca: significa que alguien compuso una cookie con el identificador
    de emisión de otra sesión. Se trata como manipulación, igual que una reutilización, y
    cae la familia completa en vez de solo rechazar la petición.
    """
    duena = _cuenta(db_session)
    otra = _cuenta(db_session)
    token_de_la_duena = abrir_sesion(db_session, duena, ip="203.0.113.7")
    payload = jwt.decode(
        token_de_la_duena,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        audience=settings.JWT_AUDIENCE,
        issuer=settings.JWT_ISSUER,
    )

    with pytest.raises(ReutilizacionDetectada) as fallo:
        rotar_sesion(db_session, otra, payload, ip="203.0.113.7")

    registro = (
        db_session.query(RefreshToken).filter(RefreshToken.jti == payload["jti"]).one()
    )
    assert registro.revoked_reason == MOTIVO_REUTILIZADO
    assert fallo.value.tokens_revocados >= 1


def test_un_refresco_que_ya_vencio_no_rota(db_session):
    """
    Vencido no es reutilizado: no hay indicio de robo y no cae ninguna familia.

    Se distingue porque la respuesta es distinta —volver a iniciar sesión frente a cerrar
    todas las sesiones del usuario—, y confundirlos cerraría la sesión de todos los
    dispositivos de alguien cada vez que su cookie caduca.
    """
    usuario = _cuenta(db_session)
    token = abrir_sesion(db_session, usuario, ip="203.0.113.7")
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        audience=settings.JWT_AUDIENCE,
        issuer=settings.JWT_ISSUER,
    )
    registro = db_session.query(RefreshToken).filter(RefreshToken.jti == payload["jti"]).one()
    registro.expires_at = utc_now() - datetime.timedelta(seconds=1)
    db_session.commit()

    with pytest.raises(ValueError) as fallo:
        rotar_sesion(db_session, usuario, payload, ip="203.0.113.7")

    assert "venció" in str(fallo.value)
    assert registro.revoked_reason != MOTIVO_REUTILIZADO


# ==============================================================================
# El refresco visto desde la puerta
# ==============================================================================

def test_un_refresco_con_un_sujeto_que_no_es_un_numero_caduca_la_sesion(client, db_session):
    """Mismo borde que en la identidad, en la otra puerta: aquí el `sub` también se convierte."""
    usuario = _cuenta(db_session)
    cookie = _firmar(_claims(usuario, tipo=TOKEN_TYPE_REFRESH, sub="admin"))

    respuesta = client.post(AUTH + "/refresh", cookies={settings.REFRESH_COOKIE_NAME: cookie})

    assert respuesta.status_code == 401


def test_el_refresco_de_una_cuenta_desactivada_se_rechaza(client, db_session):
    """
    Desactivar una cuenta corta también lo que ya estaba en vuelo.

    El refresco es lo que convierte una sesión de quince minutos en una de siete días, así
    que es la puerta que de verdad cierra una baja: el access token que la cuenta tuviera
    caduca solo.

    **Y una cosa que esta prueba descubrió y no arregla.** El endpoint llama a
    `_clear_refresh_cookie(response)` antes de levantar el 401, en cuatro de sus caminos de
    rechazo, y esa cabecera no llega al navegador: cuando el manejador lanza una excepción,
    FastAPI construye la respuesta de error por su cuenta y descarta las cabeceras puestas
    en la respuesta inyectada. Medido aquí: el 401 vuelve sin `Set-Cookie`. El efecto es que
    el navegador conserva una cookie que ya no sirve y reintenta el refresco en cada carga
    —un 401 por pestaña abierta, no un agujero—. No se toca: cambiar la forma de esos cuatro
    rechazos es cambiar lo que la API contesta, y queda anotado en el documento de
    congelación.
    """
    usuario = _cuenta(db_session)
    # Una sesión de verdad, con su fila en `refresh_tokens`: con una cookie fabricada el
    # rechazo vendría de «no está registrada» y esta comprobación no se estaría midiendo.
    cookie = abrir_sesion(db_session, usuario, ip="203.0.113.7")
    usuario.is_active = False
    db_session.commit()

    respuesta = client.post(AUTH + "/refresh", cookies={settings.REFRESH_COOKIE_NAME: cookie})

    assert respuesta.status_code == 401


# ==============================================================================
# Los endpoints a los que se llama directamente: la cuenta que ya no está
# ==============================================================================

def test_la_identidad_de_una_cuenta_que_ya_no_existe_es_404(db_session):
    """Un token válido para una fila borrada: la respuesta es 404, no un 500 al validar el modelo."""
    usuario = _cuenta(db_session)
    identidad = _identidad(usuario)
    db_session.delete(usuario)
    db_session.commit()

    with pytest.raises(HTTPException) as fallo:
        endpoints_auth.read_current_user(db=db_session, current_user=identidad)

    assert fallo.value.status_code == 404
    assert "ya no existe" in fallo.value.detail


def test_cambiar_la_contrasena_de_una_cuenta_que_ya_no_existe_es_404(db_session):
    """El mismo caso en la ruta que escribe: antes de tocar nada, la cuenta tiene que estar."""
    from app.schemas.user import CambiarContrasenaPropia

    usuario = _cuenta(db_session)
    identidad = _identidad(usuario)
    db_session.delete(usuario)
    db_session.commit()

    with pytest.raises(HTTPException) as fallo:
        endpoints_auth.cambiar_contrasena_propia(
            request=_peticion(),
            response=Response(),
            datos=CambiarContrasenaPropia(
                contrasena_actual=TEST_PASSWORD, nueva_contrasena="Otra-Mas-Larga-2026!"
            ),
            db=db_session,
            current_user=identidad,
        )

    assert fallo.value.status_code == 404


def test_el_cierre_de_sesion_de_una_cuenta_que_ya_no_existe_queda_en_la_bitacora(db_session):
    """
    Cerrar sesión no puede fallar porque la cuenta ya no esté: la cookie hay que borrarla.

    Y el asiento se escribe igual, con el correo que venía en el token y sin actor: es la
    única constancia de que esa sesión se cerró, y la bitácora no se puede quedar con el
    hueco.
    """
    usuario = _cuenta(db_session)
    identidad = _identidad(usuario)
    db_session.delete(usuario)
    db_session.commit()

    resultado = endpoints_auth.logout(
        request=_peticion(), response=Response(), db=db_session, current_user=identidad
    )

    assert resultado["status"] == "success"
    asiento = (
        db_session.query(AuditLog)
        .filter(AuditLog.actor_email == identidad.email)
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert asiento is not None
    assert asiento.actor_id is None
    assert asiento.event_metadata["tokens_revocados"] == 0


# ==============================================================================
# El segundo paso del acceso
# ==============================================================================

def _desafio_de(usuario, **cambios) -> str:
    return _firmar(_claims(usuario, tipo=TOKEN_TYPE_DESAFIO, **cambios))


def test_un_desafio_con_un_sujeto_que_no_es_un_numero_no_abre_sesion(client, db_session):
    """El mismo borde en la tercera puerta, y con el mismo mensaje que un código equivocado."""
    usuario = _cuenta(db_session, rol="System_Admin")

    respuesta = client.post(
        AUTH + "/login/segundo-factor",
        json={"desafio": _desafio_de(usuario, sub="admin"), "codigo": "000000"},
    )

    assert respuesta.status_code == 401


def test_un_desafio_emitido_antes_de_un_cierre_de_sesion_no_sirve(client, db_session):
    """
    El desafío lleva la versión de la cuenta, igual que el access token.

    Sin compararla, un desafío capturado seguiría valiendo después de cerrar sesión en todos
    los dispositivos: justo lo que ese cierre tiene que cortar.

    Con el código **bueno** a propósito. Con uno inventado el rechazo llegaría de todas
    formas —el código no cuadra— y no se estaría midiendo nada: la cuenta de administración
    de la suite tiene su segundo factor activo, así que aquí lo único que falla es la versión.
    """
    email, _ = TEST_ACCOUNTS["System_Admin"]
    usuario = db_session.query(User).filter(User.email == email).one()

    respuesta = client.post(
        AUTH + "/login/segundo-factor",
        json={
            "desafio": _desafio_de(usuario, ver=usuario.token_version + 1),
            "codigo": codigo_del_segundo_factor(email),
        },
    )

    assert respuesta.status_code == 401
    assert "no es válido" in respuesta.json()["detail"]


def test_agotar_los_intentos_de_un_desafio_da_429_y_no_bloquea_la_cuenta(client, db_session):
    """
    El contador vive en el desafío, no en la cuenta.

    Contar por cuenta significa bloquearla, y bloquear la de administración por intentos
    fallidos le regala a cualquiera una forma de dejar al sistema sin administrador: basta
    con fallar contra su correo. Contando por desafío, agotarlos solo obliga a volver a
    escribir la contraseña.

    La suite apaga el limitador en todas las pruebas, así que este camino no se recorría
    nunca: hay que encenderlo a mano, que es lo que hace esto.
    """
    usuario = _cuenta(db_session, rol="System_Admin")
    desafio = _desafio_de(usuario)
    limiter.enabled = True
    limiter.reset()
    try:
        vistos = []
        for _ in range(settings.SEGUNDO_FACTOR_INTENTOS + 1):
            vistos.append(
                client.post(
                    AUTH + "/login/segundo-factor",
                    json={"desafio": desafio, "codigo": "000000"},
                ).status_code
            )
    finally:
        limiter.enabled = False
        limiter.reset()

    assert vistos[-1] == 429
    assert 401 in vistos, "los primeros intentos tienen que contestar como un código malo"
    # La cuenta sigue entrando: lo que se agotó es el desafío.
    assert usuario.is_active is True


# ==============================================================================
# Alta y baja del segundo factor, vistas desde el endpoint
# ==============================================================================

def _token_de(client, usuario) -> dict:
    respuesta = client.post(
        AUTH + "/login", json={"email": usuario.email, "password": TEST_PASSWORD}
    )
    cuerpo = respuesta.json()
    if "access_token" in cuerpo:
        return {"Authorization": f"Bearer {cuerpo['access_token']}"}
    segundo = client.post(
        AUTH + "/login/segundo-factor",
        json={"desafio": cuerpo["desafio"], "codigo": codigo_del_segundo_factor(usuario.email)},
    )
    return {"Authorization": f"Bearer {segundo.json()['access_token']}"}


def test_activar_el_segundo_factor_sin_haberlo_dado_de_alta_es_un_conflicto(client, db_session):
    """
    409 y no 422: no es que el código esté mal, es que no hay nada que activar.

    Se distinguen porque lo que hay que hacer es distinto —pedir el alta frente a volver a
    teclear— y el cliente pinta un mensaje por cada uno.
    """
    usuario = _cuenta(db_session, rol="Sales_Lead")
    cabeceras = _token_de(client, usuario)

    respuesta = client.post(
        AUTH + "/segundo-factor/activar", json={"codigo": "000000"}, headers=cabeceras
    )

    assert respuesta.status_code == 409


def test_activar_el_segundo_factor_con_un_codigo_equivocado_no_lo_activa(client, db_session):
    """
    El 422 lleva dentro la causa más frecuente: la hora del teléfono.

    Y lo que importa de la rama: deshace la transacción. Sin el `rollback`, el alta a medias
    quedaría escrita y la cuenta se encontraría con un segundo factor que no sabe usar.
    """
    usuario = _cuenta(db_session, rol="Sales_Lead")
    cabeceras = _token_de(client, usuario)
    assert client.post(AUTH + "/segundo-factor/alta", headers=cabeceras).status_code == 200

    respuesta = client.post(
        AUTH + "/segundo-factor/activar", json={"codigo": "000000"}, headers=cabeceras
    )

    assert respuesta.status_code == 422
    assert "hora del teléfono" in respuesta.json()["detail"]
    db_session.refresh(usuario)
    assert usuario.totp_activo is False


def test_darse_de_baja_del_segundo_factor_con_un_codigo_equivocado_no_lo_quita(client, db_session):
    """
    Para la baja se pide un código y no la contraseña, y un código malo no quita nada.

    Quien deja una sesión abierta en un equipo ajeno tiene ahí la contraseña guardada en el
    navegador mucho más a menudo que el teléfono.
    """
    usuario = _cuenta(db_session, rol="Sales_Lead")
    cabeceras = _token_de(client, usuario)
    client.post(AUTH + "/segundo-factor/alta", headers=cabeceras)
    client.post(
        AUTH + "/segundo-factor/activar",
        json={"codigo": codigo_del_segundo_factor(usuario.email)},
        headers=cabeceras,
    )
    db_session.refresh(usuario)
    assert usuario.totp_activo is True

    respuesta = client.post(
        AUTH + "/segundo-factor/baja", json={"codigo": "000000"}, headers=cabeceras
    )

    assert respuesta.status_code == 422
    db_session.refresh(usuario)
    assert usuario.totp_activo is True


def test_todo_token_lleva_los_siete_claims_que_la_puerta_exige(db_session):
    """
    El sobre comun de los tres tipos de token, comprobado sobre el constructor interno.

    Las tres funciones publicas -acceso, refresco y desafio- pasan claims propios, asi que
    el camino sin claims extra solo existe desde aqui. Lo que fija esta prueba es la base
    que las tres heredan: `decode_token` exige `exp`, `iat`, `nbf` y `jti` presentes, y un
    token emitido sin alguno de ellos se rechaza sin decir por que. La suite ya comprueba
    ese rechazo; esto comprueba el otro lado, que el emisor los ponga.
    """
    usuario = _cuenta(db_session)
    token = modulo_seguridad._create_token(
        subject=str(usuario.id),
        token_type=TOKEN_TYPE_ACCESS,
        expires_delta=datetime.timedelta(minutes=5),
    )

    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        audience=settings.JWT_AUDIENCE,
        issuer=settings.JWT_ISSUER,
    )

    assert set(payload) == {"sub", "typ", "iss", "aud", "iat", "nbf", "exp", "jti"}
    assert payload["sub"] == str(usuario.id)
    assert payload["typ"] == TOKEN_TYPE_ACCESS
    assert len(payload["jti"]) == 32
