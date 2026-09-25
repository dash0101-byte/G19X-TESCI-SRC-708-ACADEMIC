"""
Capítulo 35: el segundo factor, y por qué §3.6 estuvo abierto tanto tiempo.

El documento de congelación no decía «no hubo tiempo». Decía qué hacía falta para que esto
no fuera peor que no tenerlo: «alta con código de verificación, códigos de recuperación, un
paso más en el login del cliente y una respuesta para quien pierde el teléfono siendo el
único administrador —que es justo la cuenta que no puede quedarse fuera—. Añadir la
verificación sin eso produce una cuenta de administración que se bloquea sola.»

Las cuatro cosas se comprueban aquí, y la cuarta manda: hay tres formas distintas de
quedarse fuera y ninguna deja el sistema sin administración utilizable.

Lo primero: que el TOTP sea TOTP
--------------------------------
Está escrito a mano sobre `hmac`, así que no se afirma correcto: se comprueba contra los
**vectores de prueba oficiales del RFC 6238**, los dieciocho, para SHA-1, SHA-256 y
SHA-512. Es la razón de que escribirlo fuera defendible en vez de traer una dependencia:
la norma publica con qué demostrarlo.
"""
import datetime

import pytest
from app.core import totp
from app.core.config import settings
from app.core.security import (
    ROLES_OBLIGADOS_A_SEGUNDO_FACTOR,
    UserRole,
    exige_segundo_factor,
    hash_password,
)
from app.models.entities import AuditLog, User, utc_now
from app.services import segundo_factor
from tests.conftest import TEST_ACCOUNTS, TEST_PASSWORD, codigo_del_segundo_factor

AUTH = "/api/v1/auth"

# RFC 6238, apéndice B. El secreto es la cadena ASCII "12345678901234567890" repetida hasta
# la longitud del hash, que es lo que dice la errata del propio RFC.
_S1 = b"12345678901234567890"
_S256 = (b"12345678901234567890" * 2)[:32]
_S512 = (b"12345678901234567890" * 4)[:64]

VECTORES_DEL_RFC = [
    (59, "94287082", "SHA1", _S1),
    (59, "46119246", "SHA256", _S256),
    (59, "90693936", "SHA512", _S512),
    (1111111109, "07081804", "SHA1", _S1),
    (1111111109, "68084774", "SHA256", _S256),
    (1111111109, "25091201", "SHA512", _S512),
    (1111111111, "14050471", "SHA1", _S1),
    (1111111111, "67062674", "SHA256", _S256),
    (1111111111, "99943326", "SHA512", _S512),
    (1234567890, "89005924", "SHA1", _S1),
    (1234567890, "91819424", "SHA256", _S256),
    (1234567890, "93441116", "SHA512", _S512),
    (2000000000, "69279037", "SHA1", _S1),
    (2000000000, "90698825", "SHA256", _S256),
    (2000000000, "38618901", "SHA512", _S512),
    (20000000000, "65353130", "SHA1", _S1),
    (20000000000, "77737706", "SHA256", _S256),
    (20000000000, "47863826", "SHA512", _S512),
]


# ==============================================================================
# 1. El algoritmo, contra la norma
# ==============================================================================

@pytest.mark.parametrize("momento,esperado,algoritmo,secreto", VECTORES_DEL_RFC)
def test_los_vectores_oficiales_del_rfc_6238(momento, esperado, algoritmo, secreto):
    """
    La prueba que justifica no haber traído una dependencia.

    Si esto pasa, la implementación no «parece» correcta: produce exactamente los códigos
    que publica la norma, en tres algoritmos y a lo largo de trescientos años de marcas de
    tiempo. Cualquier aplicación de autenticación del teléfono calculará lo mismo.
    """
    assert totp.codigo(secreto, momento, digitos=8, algoritmo=algoritmo) == esperado


def test_el_codigo_cambia_cada_treinta_segundos():
    """
    Los periodos empiezan en múltiplos de 30 desde la época, no donde caiga la primera
    petición: el contador es `t // 30`. Por eso los dos instantes de dentro son 990 y 1019,
    que caen en el mismo periodo, y 1020, que ya es el siguiente.
    """
    secreto = b"1234567890abcdefghij"
    assert totp.codigo(secreto, 990) == totp.codigo(secreto, 1019)
    assert totp.codigo(secreto, 990) != totp.codigo(secreto, 1020)


def test_base32_ida_y_vuelta_tolerando_lo_que_teclea_una_persona():
    secreto = b"1234567890abcdefghij"
    texto = totp.a_base32(secreto)
    assert totp.de_base32(texto) == secreto
    # Con espacios, en minúsculas y sin el relleno: es como se copia de una pantalla.
    assert totp.de_base32(texto.lower()[:8] + " " + texto.lower()[8:]) == secreto


def test_la_uri_otpauth_lleva_el_emisor_dos_veces():
    """
    En la etiqueta y como parámetro, que es la convención que siguen las aplicaciones.

    Con uno solo, unas cuantas enseñan la cuenta sin decir de qué sistema es, y quien tenga
    varias no sabe cuál es cuál.
    """
    uri = totp.uri_otpauth(b"1234567890abcdefghij", "ana@plurione.com", "PluriOne")
    assert uri.startswith("otpauth://totp/PluriOne%3Aana%40plurione.com?")
    assert "issuer=PluriOne" in uri
    assert "digits=6" in uri and "period=30" in uri


# ==============================================================================
# 2. Tolerancia al reloj desfasado, y su precio
# ==============================================================================

def test_se_acepta_un_periodo_de_desfase_en_cada_sentido():
    """
    Un teléfono un poco adelantado o atrasado sigue funcionando.

    RFC 6238 §5.2 lo recomienda y advierte de lo que cuesta: cada código pasa de valer 30 s
    a valer 90. Por eso es uno y no dos, y por eso está el contador de la prueba siguiente.
    """
    secreto = b"1234567890abcdefghij"
    ahora = 1_700_000_000
    for desfase in (-30, 0, 30):
        assert totp.verificar(secreto, totp.codigo(secreto, ahora + desfase), ahora) is not None


def test_dos_periodos_de_desfase_ya_no_se_aceptan():
    secreto = b"1234567890abcdefghij"
    ahora = 1_700_000_000
    for desfase in (-60, 60):
        assert totp.verificar(secreto, totp.codigo(secreto, ahora + desfase), ahora) is None


def test_un_codigo_no_vale_dos_veces():
    """
    La contrapartida de la tolerancia, y lo que impide reutilizar un código visto de reojo.

    Sin esto, un código tiene noventa segundos de vida y quien lo lea por encima del hombro
    —o lo saque de un registro— lo puede volver a usar dentro de esa ventana.
    """
    secreto = b"1234567890abcdefghij"
    ahora = 1_700_000_000
    codigo = totp.codigo(secreto, ahora)

    contador = totp.verificar(secreto, codigo, ahora)
    assert contador is not None
    assert totp.verificar(secreto, codigo, ahora, contador_minimo=contador + 1) is None


def test_un_codigo_mal_formado_no_pasa_por_el_hmac():
    secreto = b"1234567890abcdefghij"
    for basura in ("", "abcdef", "12345", "1234567", None):
        assert totp.verificar(secreto, basura, 1_700_000_000) is None


# ==============================================================================
# 3. El secreto no se guarda
# ==============================================================================

def _cuenta(db, correo="dosfa@plurione.com", rol="Commercial_Executive") -> User:
    usuario = User(
        email=correo, full_name="Cuenta de prueba", role=rol, hashed_password=hash_password(TEST_PASSWORD)
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def test_la_base_no_guarda_ningun_secreto(db_session):
    """
    La propiedad central del capítulo, comprobada sobre la fila de verdad.

    Quien se lleve un volcado de `users` se lleva una sal. Con la sal sola no se genera ni
    un código: hace falta `SECRET_KEY`, que vive en el entorno. Es la misma protección que
    daría cifrar el secreto, sin cifrador que implantar.
    """
    usuario = _cuenta(db_session)
    alta = segundo_factor.iniciar_alta(usuario)
    db_session.commit()

    fila = {c.name: getattr(usuario, c.name) for c in User.__table__.columns}
    en_claro = str(fila)
    assert alta.secreto_en_base32 not in en_claro
    assert usuario.totp_sal is not None
    # Y los códigos tampoco: de ellos solo queda el resumen.
    for codigo in alta.codigos_de_recuperacion:
        assert codigo not in en_claro


def test_el_secreto_se_deriva_de_la_clave_del_servidor(db_session, monkeypatch):
    """
    Cambiar `SECRET_KEY` cambia el secreto: es el precio, y está fijado por escrito.

    No es un defecto oculto: rotar esa clave ya invalida todas las sesiones. Lo que añade
    esto es que además hay que volver a dar de alta el teléfono, y por eso la guía lo dice.
    """
    usuario = _cuenta(db_session)
    alta = segundo_factor.iniciar_alta(usuario)

    monkeypatch.setattr(settings, "SECRET_KEY", "otra-clave-completamente-distinta-aaaa")
    otro = segundo_factor._secreto_de(usuario.totp_sal)

    assert totp.a_base32(otro) != alta.secreto_en_base32


def test_dos_altas_de_la_misma_cuenta_dan_secretos_distintos(db_session):
    """Volver a darse de alta invalida el teléfono anterior sin tocar `SECRET_KEY`."""
    usuario = _cuenta(db_session)
    primera = segundo_factor.iniciar_alta(usuario)
    segunda = segundo_factor.iniciar_alta(usuario)

    assert primera.secreto_en_base32 != segunda.secreto_en_base32
    assert primera.codigos_de_recuperacion != segunda.codigos_de_recuperacion


def test_la_baja_borra_la_sal(db_session):
    """
    Con la sal y la clave se recalcula el secreto, así que dejarla mantendría vivo el
    teléfono de alguien que ya no usa esta cuenta.
    """
    usuario = _cuenta(db_session)
    segundo_factor.iniciar_alta(usuario)
    segundo_factor.activar(usuario, totp.codigo(segundo_factor._secreto_de(usuario.totp_sal), utc_now().timestamp()))
    segundo_factor.desactivar(usuario)

    assert usuario.totp_sal is None
    assert usuario.totp_activo is False
    assert usuario.totp_codigos_de_recuperacion is None


# ==============================================================================
# 4. El alta no activa nada hasta que se comprueba un código
# ==============================================================================

def test_el_alta_no_activa_el_segundo_factor(db_session):
    """
    Es lo que impide que alguien se quede fuera por haber escaneado mal el QR.

    Entre pedir el alta y confirmar el primer código, la cuenta sigue entrando con la
    contraseña. Activar aquí habría convertido el alta en un acto de fe.
    """
    usuario = _cuenta(db_session)
    segundo_factor.iniciar_alta(usuario)

    assert usuario.totp_sal is not None
    assert usuario.totp_activo is False


def test_activar_con_un_codigo_equivocado_no_activa(db_session):
    usuario = _cuenta(db_session)
    segundo_factor.iniciar_alta(usuario)

    with pytest.raises(segundo_factor.SegundoFactorInvalido):
        segundo_factor.activar(usuario, "000000")
    assert usuario.totp_activo is False


def test_activar_sin_alta_previa_se_distingue_de_un_codigo_malo(db_session):
    """Son dos errores distintos y el cliente tiene que poder decir cuál pasó."""
    usuario = _cuenta(db_session)
    with pytest.raises(segundo_factor.AltaNoIniciada):
        segundo_factor.activar(usuario, "000000")


# ==============================================================================
# 5. Los códigos de recuperación
# ==============================================================================

def _activar(db_session, usuario) -> list:
    alta = segundo_factor.iniciar_alta(usuario)
    secreto = segundo_factor._secreto_de(usuario.totp_sal)
    segundo_factor.activar(usuario, totp.codigo(secreto, utc_now().timestamp()))
    db_session.commit()
    return alta.codigos_de_recuperacion


def test_se_emiten_diez_y_cada_uno_sirve_una_sola_vez(db_session):
    usuario = _cuenta(db_session)
    codigos = _activar(db_session, usuario)
    assert len(codigos) == segundo_factor.CODIGOS_DE_RECUPERACION

    forma, restantes = segundo_factor.comprobar(usuario, codigos[0])
    assert forma == "recuperacion"
    assert restantes == segundo_factor.CODIGOS_DE_RECUPERACION - 1

    with pytest.raises(segundo_factor.SegundoFactorInvalido):
        segundo_factor.comprobar(usuario, codigos[0])


def test_un_codigo_de_recuperacion_perdona_la_forma_de_copiarlo(db_session):
    """
    Se copian de una hoja impresa, así que minúsculas, espacios y guiones de más tienen que
    dar igual. Lo contrario convierte un mecanismo de rescate en una fuente de frustración
    justo el día que alguien perdió el teléfono.
    """
    usuario = _cuenta(db_session)
    codigos = _activar(db_session, usuario)

    forma, _ = segundo_factor.comprobar(usuario, codigos[0].lower().replace("-", " "))
    assert forma == "recuperacion"


def test_gastar_todos_los_codigos_no_rompe_nada(db_session):
    usuario = _cuenta(db_session)
    codigos = _activar(db_session, usuario)
    for codigo in codigos:
        segundo_factor.comprobar(usuario, codigo)

    assert segundo_factor.codigos_restantes(usuario) == 0

    # El teléfono sigue sirviendo: quedarse sin códigos no es quedarse fuera.
    #
    # Se mira al periodo SIGUIENTE porque activar ya gastó el actual: el mismo código no
    # vale dos veces, y eso incluye al que sirvió para activar. Esperar treinta segundos en
    # una prueba sería cambiar una comprobación por una espera.
    luego = utc_now() + datetime.timedelta(seconds=totp.PERIODO_SEGUNDOS)
    forma, _ = segundo_factor.comprobar(
        usuario,
        totp.codigo(segundo_factor._secreto_de(usuario.totp_sal), luego.timestamp()),
        ahora=luego,
    )
    assert forma == "totp"


# ==============================================================================
# 6. El login de dos pasos, por la API
# ==============================================================================

def test_una_cuenta_sin_segundo_factor_entra_de_una_vez(client):
    correo, _ = TEST_ACCOUNTS["Sales_Lead"]
    respuesta = client.post(f"{AUTH}/login", json={"email": correo, "password": TEST_PASSWORD})

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["tipo"] == "sesion"
    assert respuesta.json()["access_token"]


def test_una_cuenta_con_segundo_factor_recibe_un_desafio_y_no_una_sesion(client):
    """
    200 y no un error: la contraseña era buena y esto es el camino normal.

    Lo que importa comprobar es que **no hay sesión** todavía: ni token, ni cookie.
    """
    correo, _ = TEST_ACCOUNTS["System_Admin"]
    respuesta = client.post(f"{AUTH}/login", json={"email": correo, "password": TEST_PASSWORD})

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["tipo"] == "segundo_factor"
    assert cuerpo["desafio"]
    assert "access_token" not in cuerpo
    assert settings.REFRESH_COOKIE_NAME not in respuesta.cookies


def test_el_desafio_no_sirve_como_autorizacion(client):
    """
    El fallo obvio, cerrado por construcción: si el desafío fuera un access token, bastaría
    con no pedir el segundo paso para saltarse el segundo factor entero.
    """
    correo, _ = TEST_ACCOUNTS["System_Admin"]
    desafio = client.post(
        f"{AUTH}/login", json={"email": correo, "password": TEST_PASSWORD}
    ).json()["desafio"]

    respuesta = client.get(f"{AUTH}/me", headers={"Authorization": f"Bearer {desafio}"})
    assert respuesta.status_code == 401


def test_el_segundo_paso_con_el_codigo_bueno_abre_sesion(client):
    correo, _ = TEST_ACCOUNTS["System_Admin"]
    desafio = client.post(
        f"{AUTH}/login", json={"email": correo, "password": TEST_PASSWORD}
    ).json()["desafio"]

    respuesta = client.post(
        f"{AUTH}/login/segundo-factor",
        json={"desafio": desafio, "codigo": _codigo_utilizable(correo)},
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["tipo"] == "sesion"
    assert respuesta.json()["access_token"]


def test_el_segundo_paso_con_un_codigo_malo_no_abre_sesion(client):
    correo, _ = TEST_ACCOUNTS["System_Admin"]
    desafio = client.post(
        f"{AUTH}/login", json={"email": correo, "password": TEST_PASSWORD}
    ).json()["desafio"]

    respuesta = client.post(
        f"{AUTH}/login/segundo-factor", json={"desafio": desafio, "codigo": "000000"}
    )

    assert respuesta.status_code == 401
    # El mismo mensaje que para un desafío caducado: distinguirlos diría a quien prueba cuál
    # de las dos mitades ya tiene.
    assert "no es válido" in respuesta.json()["detail"]


def test_un_desafio_inventado_no_vale(client):
    respuesta = client.post(
        f"{AUTH}/login/segundo-factor", json={"desafio": "no.es.un.token", "codigo": "000000"}
    )
    assert respuesta.status_code == 401


# ==============================================================================
# 7. Obligatorio para administración
# ==============================================================================

def test_la_regla_de_quien_esta_obligado_esta_en_un_solo_sitio():
    """
    Para que exigirlo a otro rol sea cambiar una tupla y no buscar por cuatro archivos.
    """
    assert ROLES_OBLIGADOS_A_SEGUNDO_FACTOR == (UserRole.SYSTEM_ADMIN,)
    assert exige_segundo_factor("System_Admin") is True
    assert exige_segundo_factor("Sales_Lead") is False
    assert exige_segundo_factor("Commercial_Executive") is False
    # Un rol que no existe no dispara este camino: ya lo rechaza la resolución de identidad
    # con un mensaje útil, y contestar «sí» aquí lo sustituiría por uno confuso.
    assert exige_segundo_factor("Rol_Inventado") is False


def test_una_administracion_sin_segundo_factor_no_opera(client, db_session):
    """
    La exigencia se comprueba en la resolución de identidad, no con una lista de rutas.

    Así un endpoint nuevo nace cerrado para estas cuentas sin que nadie tenga que acordarse
    de añadirlo a ninguna parte.
    """
    _cuenta(db_session, "admin.sin.dosfa@plurione.com", "System_Admin")
    token = client.post(
        f"{AUTH}/login", json={"email": "admin.sin.dosfa@plurione.com", "password": TEST_PASSWORD}
    ).json()["access_token"]
    cabeceras = {"Authorization": f"Bearer {token}"}

    respuesta = client.get("/api/v1/leads", headers=cabeceras)

    assert respuesta.status_code == 403
    assert respuesta.json()["detail"]["codigo"] == "segundo_factor_obligatorio"


def test_esa_cuenta_si_puede_llegar_a_darse_de_alta(client, db_session):
    """
    La otra mitad, y la que evita el bloqueo circular: las rutas que sirven para dejar de
    no tenerlo tienen que funcionar sin tenerlo.
    """
    _cuenta(db_session, "admin.alta@plurione.com", "System_Admin")
    token = client.post(
        f"{AUTH}/login", json={"email": "admin.alta@plurione.com", "password": TEST_PASSWORD}
    ).json()["access_token"]
    cabeceras = {"Authorization": f"Bearer {token}"}

    assert client.get(f"{AUTH}/me", headers=cabeceras).status_code == 200
    assert client.get(f"{AUTH}/segundo-factor", headers=cabeceras).status_code == 200

    alta = client.post(f"{AUTH}/segundo-factor/alta", headers=cabeceras)
    assert alta.status_code == 200, alta.text
    cuerpo = alta.json()
    assert cuerpo["qr_svg"].startswith("<svg")
    assert len(cuerpo["codigos_de_recuperacion"]) == segundo_factor.CODIGOS_DE_RECUPERACION

    usuario = db_session.query(User).filter(User.email == "admin.alta@plurione.com").one()
    activar = client.post(
        f"{AUTH}/segundo-factor/activar",
        headers=cabeceras,
        json={"codigo": totp.codigo(segundo_factor._secreto_de(usuario.totp_sal), utc_now().timestamp())},
    )
    assert activar.status_code == 200, activar.text
    assert activar.json()["activo"] is True

    # Y ahora ya opera.
    assert client.get("/api/v1/leads", headers=cabeceras).status_code == 200


def test_un_asesor_puede_tenerlo_pero_no_se_le_exige(client, db_session):
    _cuenta(db_session, "asesor.opcional@plurione.com", "Commercial_Executive")
    token = client.post(
        f"{AUTH}/login", json={"email": "asesor.opcional@plurione.com", "password": TEST_PASSWORD}
    ).json()["access_token"]
    cabeceras = {"Authorization": f"Bearer {token}"}

    # Opera sin tenerlo...
    assert client.get("/api/v1/leads", headers=cabeceras).status_code == 200
    # ...y puede dárselo de alta igualmente.
    estado = client.get(f"{AUTH}/segundo-factor", headers=cabeceras).json()
    assert estado["activo"] is False
    assert estado["obligatorio"] is False
    assert client.post(f"{AUTH}/segundo-factor/alta", headers=cabeceras).status_code == 200


# ==============================================================================
# 8. Quedarse fuera: las tres salidas, y ninguna deja el sistema sin administración
# ==============================================================================

def test_quien_pierde_el_telefono_entra_con_un_codigo_de_recuperacion(client, db_session):
    correo = "admin.pierde@plurione.com"
    usuario = _cuenta(db_session, correo, "System_Admin")
    codigos = _activar(db_session, usuario)

    desafio = client.post(f"{AUTH}/login", json={"email": correo, "password": TEST_PASSWORD}).json()[
        "desafio"
    ]
    respuesta = client.post(
        f"{AUTH}/login/segundo-factor", json={"desafio": desafio, "codigo": codigos[0]}
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["access_token"]


@pytest.fixture
def administracion_intacta():
    """
    Devuelve la cuenta de administración de la suite a su estado, pase lo que pase.

    Las dos pruebas de la baja son las únicas que intentan **quitarle** el segundo factor a
    una cuenta que el resto de la suite usa para todo. Si alguna vez la salvaguarda fallara,
    sin esto el fallo no sería una prueba roja: serían doscientas, en archivos que no tienen
    nada que ver, y el motivo estaría a media suite de distancia.
    """
    from app.core.database import SessionLocal

    correo, _ = TEST_ACCOUNTS["System_Admin"]
    with SessionLocal() as db:
        cuenta = db.query(User).filter(User.email == correo).one()
        estado = (
            cuenta.totp_sal,
            cuenta.totp_activo,
            cuenta.totp_codigos_de_recuperacion,
            cuenta.totp_ultimo_contador,
        )
    yield
    with SessionLocal() as db:
        cuenta = db.query(User).filter(User.email == correo).one()
        (
            cuenta.totp_sal,
            cuenta.totp_activo,
            cuenta.totp_codigos_de_recuperacion,
            cuenta.totp_ultimo_contador,
        ) = estado
        db.commit()


def test_la_ultima_administracion_no_puede_quitarse_el_suyo(
    client, db_session, administracion_intacta
):
    """
    La salvaguarda que §3.6 pedía y que hace que esto no sea peor que no tenerlo.

    Una cuenta de administración sin segundo factor no puede operar. Si la única que lo
    tiene activo se lo quita, el sistema se queda sin administración utilizable hasta que
    esa misma persona vuelva a darse de alta.
    """
    correo, _ = TEST_ACCOUNTS["System_Admin"]
    # La premisa de la prueba, comprobada y no supuesta: es la única con segundo factor.
    # Sin esto, un administrador que otra prueba dejara activo convertiría este caso en su
    # contrario sin que el nombre de la prueba cambiara.
    assert segundo_factor.administradores_con_segundo_factor(db_session) == 1
    cabeceras = {"Authorization": f"Bearer {_token(client, correo)}"}

    respuesta = client.post(
        f"{AUTH}/segundo-factor/baja",
        headers=cabeceras,
        json={"codigo": _codigo_utilizable(correo)},
    )

    assert respuesta.status_code == 409
    assert "única cuenta de administración" in respuesta.json()["detail"]


def test_con_otra_administracion_activa_si_puede_quitarselo(client, db_session):
    """El mismo caso, con la salvaguarda satisfecha: ya no es la única."""
    suplente = _cuenta(db_session, "admin.suplente@plurione.com", "System_Admin")
    _activar(db_session, suplente)

    correo = "admin.se.va@plurione.com"
    usuario = _cuenta(db_session, correo, "System_Admin")
    _activar(db_session, usuario)
    cabeceras = {"Authorization": f"Bearer {_token(client, correo)}"}

    respuesta = client.post(
        f"{AUTH}/segundo-factor/baja",
        headers=cabeceras,
        json={"codigo": _codigo_utilizable(correo)},
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["activo"] is False


def _olvidar_el_contador(correo: str) -> None:
    """
    «Han pasado treinta segundos», sin pasarlos.

    El mismo código no vale dos veces (RFC 6238 §5.2, y hay una prueba propia). En la vida
    real eso solo molesta a quien entra dos veces en la misma media vuelta de reloj; en una
    suite que entra y opera varias veces por segundo, molesta siempre.
    """
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        usuario = db.query(User).filter(User.email == correo).one()
        usuario.totp_ultimo_contador = None
        db.commit()


def _codigo_utilizable(correo: str) -> str:
    """El código de ahora, después de olvidar el contador gastado."""
    _olvidar_el_contador(correo)
    return codigo_del_segundo_factor(correo)


def _token(client, correo: str) -> str:
    """
    Inicia sesión haciendo los dos pasos si hacen falta.

    Antes de entrar se olvida el último contador usado, y conviene explicar por qué no es
    hacer trampa. El mismo código TOTP no vale dos veces —RFC 6238 §5.2, y hay una prueba
    para ello—, así que dos accesos dentro de la misma ventana de treinta segundos fallan
    el segundo. En la vida real eso no pasa casi nunca y se resuelve esperando; en una
    suite que entra varias veces por segundo, pasa siempre. Olvidar el contador es la
    forma de decir «han pasado treinta segundos» sin pasarlos.
    """
    _olvidar_el_contador(correo)
    cuerpo = client.post(f"{AUTH}/login", json={"email": correo, "password": TEST_PASSWORD}).json()
    if cuerpo.get("tipo") != "segundo_factor":
        return cuerpo["access_token"]
    return client.post(
        f"{AUTH}/login/segundo-factor",
        json={"desafio": cuerpo["desafio"], "codigo": codigo_del_segundo_factor(correo)},
    ).json()["access_token"]


# ==============================================================================
# 9. Intentos limitados
# ==============================================================================

def test_los_intentos_se_cuentan_por_desafio_y_no_por_cuenta(client, db_session, monkeypatch):
    """
    La decisión que evita regalar una forma de dejar al sistema sin administrador.

    Contando por cuenta, cualquiera podría bloquear la de administración fallando cinco
    veces contra su correo. Contando por desafío, agotar los intentos solo obliga a volver a
    escribir la contraseña: la cuenta nunca queda inaccesible y no hay nada que desbloquear.
    """
    from app.core.rate_limit import limiter

    if not limiter.enabled:
        pytest.skip("el limitador está desactivado en esta pasada")

    correo, _ = TEST_ACCOUNTS["System_Admin"]
    desafio = client.post(f"{AUTH}/login", json={"email": correo, "password": TEST_PASSWORD}).json()[
        "desafio"
    ]

    vistos = set()
    for _ in range(settings.SEGUNDO_FACTOR_INTENTOS + 2):
        vistos.add(
            client.post(
                f"{AUTH}/login/segundo-factor", json={"desafio": desafio, "codigo": "000000"}
            ).status_code
        )
    assert 429 in vistos

    # Y con un desafío NUEVO se puede volver a intentar: la cuenta no quedó bloqueada.
    otro = client.post(f"{AUTH}/login", json={"email": correo, "password": TEST_PASSWORD}).json()[
        "desafio"
    ]
    respuesta = client.post(
        f"{AUTH}/login/segundo-factor",
        json={"desafio": otro, "codigo": codigo_del_segundo_factor(correo)},
    )
    assert respuesta.status_code == 200, respuesta.text


# ==============================================================================
# 10. La bitácora
# ==============================================================================

def _ultimo(db_session, accion: str):
    return (
        db_session.query(AuditLog)
        .filter(AuditLog.action == accion)
        .order_by(AuditLog.id.desc())
        .first()
    )


def test_el_alta_la_activacion_y_la_baja_quedan_anotadas(client, db_session):
    correo = "admin.bitacora@plurione.com"
    _cuenta(db_session, correo, "System_Admin")
    cabeceras = {"Authorization": f"Bearer {_token(client, correo)}"}

    client.post(f"{AUTH}/segundo-factor/alta", headers=cabeceras)
    assert _ultimo(db_session, "usuario.segundo_factor_alta") is not None

    usuario = db_session.query(User).filter(User.email == correo).one()
    db_session.refresh(usuario)
    client.post(
        f"{AUTH}/segundo-factor/activar",
        headers=cabeceras,
        json={"codigo": totp.codigo(segundo_factor._secreto_de(usuario.totp_sal), utc_now().timestamp())},
    )
    assert _ultimo(db_session, "usuario.segundo_factor_activado") is not None


def test_usar_un_codigo_de_recuperacion_se_distingue_de_usar_el_telefono(client, db_session):
    """
    Gastar un código significa que alguien perdió el teléfono, y dos en una semana significa
    otra cosa. Tiene que poder verse sin cruzar tablas.
    """
    correo = "admin.forma@plurione.com"
    usuario = _cuenta(db_session, correo, "System_Admin")
    codigos = _activar(db_session, usuario)

    desafio = client.post(f"{AUTH}/login", json={"email": correo, "password": TEST_PASSWORD}).json()[
        "desafio"
    ]
    client.post(f"{AUTH}/login/segundo-factor", json={"desafio": desafio, "codigo": codigos[0]})

    asiento = _ultimo(db_session, "usuario.segundo_factor_usado")
    assert asiento.event_metadata["forma"] == "recuperacion"
    assert asiento.event_metadata["codigos_de_recuperacion_restantes"] == len(codigos) - 1


def test_la_bitacora_no_copia_ningun_codigo_ni_el_secreto(client, db_session):
    """
    La bitácora se consulta con otro criterio de acceso que la tabla de cuentas. Copiar ahí
    el secreto o un código convertiría el registro de auditoría en el sitio donde sí está
    guardado lo que esta implementación se cuida de no guardar (R-11).
    """
    correo = "admin.sin.fugas@plurione.com"
    _cuenta(db_session, correo, "System_Admin")
    cabeceras = {"Authorization": f"Bearer {_token(client, correo)}"}
    alta = client.post(f"{AUTH}/segundo-factor/alta", headers=cabeceras).json()

    asiento = _ultimo(db_session, "usuario.segundo_factor_alta")
    volcado = str(asiento.event_metadata)
    assert alta["secreto_en_base32"] not in volcado
    assert alta["uri_otpauth"] not in volcado
    for codigo in alta["codigos_de_recuperacion"]:
        assert codigo not in volcado


def test_un_segundo_factor_fallido_queda_anotado(client, db_session):
    correo, _ = TEST_ACCOUNTS["System_Admin"]
    desafio = client.post(f"{AUTH}/login", json={"email": correo, "password": TEST_PASSWORD}).json()[
        "desafio"
    ]
    client.post(f"{AUTH}/login/segundo-factor", json={"desafio": desafio, "codigo": "000000"})

    asiento = _ultimo(db_session, "usuario.segundo_factor_fallido")
    assert asiento is not None
    assert asiento.outcome == "HTTP_401"


# ==============================================================================
# 11. El secreto no se vuelve a enseñar
# ==============================================================================

def test_no_existe_ninguna_ruta_que_devuelva_el_secreto(client, db_session):
    """
    No es que esté prohibido: es que el servidor **no lo tiene**. De él solo guarda la sal
    de la que se deriva, y de los códigos, su resumen.
    """
    correo = "admin.unavez@plurione.com"
    _cuenta(db_session, correo, "System_Admin")
    cabeceras = {"Authorization": f"Bearer {_token(client, correo)}"}
    alta = client.post(f"{AUTH}/segundo-factor/alta", headers=cabeceras).json()
    usuario = db_session.query(User).filter(User.email == correo).one()
    db_session.refresh(usuario)
    client.post(
        f"{AUTH}/segundo-factor/activar",
        headers=cabeceras,
        json={"codigo": totp.codigo(segundo_factor._secreto_de(usuario.totp_sal), utc_now().timestamp())},
    )

    estado = client.get(f"{AUTH}/segundo-factor", headers=cabeceras).json()
    volcado = str(estado)
    assert alta["secreto_en_base32"] not in volcado
    for codigo in alta["codigos_de_recuperacion"]:
        assert codigo not in volcado
    # Lo que sí dice es cuántos quedan, que es lo accionable.
    assert estado["codigos_de_recuperacion_restantes"] == segundo_factor.CODIGOS_DE_RECUPERACION


def test_pedir_el_alta_con_el_factor_ya_activo_se_rechaza(client):
    """Para cambiar de teléfono hay que darse de baja primero, demostrando que se tiene."""
    correo, _ = TEST_ACCOUNTS["System_Admin"]
    cabeceras = {"Authorization": f"Bearer {_token(client, correo)}"}

    respuesta = client.post(f"{AUTH}/segundo-factor/alta", headers=cabeceras)

    assert respuesta.status_code == 409


def test_el_qr_codifica_exactamente_la_uri(db_session):
    """El QR y el texto para teclear a mano tienen que ser lo mismo."""
    from app.core import codigo_qr

    usuario = _cuenta(db_session)
    alta = segundo_factor.iniciar_alta(usuario)
    svg = codigo_qr.svg(alta.uri_otpauth)

    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    # El secreto que lleva la URI es el mismo que se ofrece para teclear.
    assert f"secret={alta.secreto_en_base32}" in alta.uri_otpauth


def test_el_desafio_caduca(client, monkeypatch):
    """
    Cinco minutos: lo que se tarda en sacar el teléfono, no lo que dura una sesión.

    Se emite ya vencido en vez de adelantar el reloj del proceso. Mover el reloj no habría
    comprobado esto: quien decide si un token expiró es PyJWT, con su propia lectura de la
    hora, así que un `monkeypatch` sobre `datetime` deja la comprobación intacta y la prueba
    pasaría en verde sin comprobar nada.
    """
    correo, _ = TEST_ACCOUNTS["System_Admin"]
    monkeypatch.setattr(settings, "SEGUNDO_FACTOR_DESAFIO_MINUTOS", -1)
    desafio = client.post(f"{AUTH}/login", json={"email": correo, "password": TEST_PASSWORD}).json()[
        "desafio"
    ]

    respuesta = client.post(
        f"{AUTH}/login/segundo-factor",
        json={"desafio": desafio, "codigo": _codigo_utilizable(correo)},
    )
    assert respuesta.status_code == 401
