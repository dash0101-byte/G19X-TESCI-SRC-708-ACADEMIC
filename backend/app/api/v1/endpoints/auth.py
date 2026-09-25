import datetime
import logging
from typing import Union

from app.core import codigo_qr
from app.core.audit import (
    ACCION_CONTRASENA_PROPIA,
    ACCION_LOGIN,
    ACCION_LOGIN_FALLIDO,
    ACCION_LOGOUT,
    ACCION_REFRESH_REUTILIZADO,
    ACCION_SEGUNDO_FACTOR_ACTIVADO,
    ACCION_SEGUNDO_FACTOR_ALTA,
    ACCION_SEGUNDO_FACTOR_DESACTIVADO,
    ACCION_SEGUNDO_FACTOR_FALLIDO,
    ACCION_SEGUNDO_FACTOR_USADO,
    ENTIDAD_SESION,
    ENTIDAD_USUARIO,
    registrar_evento,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.passwords import ContrasenaDebil, exigir
from app.core.proxy import ip_del_cliente
from app.core.rate_limit import limiter, login_limit
from app.core.security import (
    TOKEN_TYPE_DESAFIO,
    TOKEN_TYPE_REFRESH,
    CurrentUser,
    create_access_token,
    create_desafio_token,
    decode_token,
    dummy_verify,
    exige_segundo_factor,
    get_current_user,
    get_current_user_con_contrasena_prestada,
    get_current_user_sin_segundo_factor,
    hash_password,
    verify_password,
)
from app.models.entities import User, utc_now
from app.schemas.auth import (
    AltaDeSegundoFactor,
    CodigoDelSegundoFactor,
    DesafioDeSegundoFactor,
    EstadoDelSegundoFactor,
    LoginRequest,
    SegundoFactorDelLogin,
    TokenResponse,
    UserResponse,
)
from app.schemas.user import CambiarContrasenaPropia, ResultadoDeContrasena
from app.services import segundo_factor
from app.services.session_service import (
    ReutilizacionDetectada,
    abrir_sesion,
    cerrar_sesiones_del_usuario,
    rotar_sesion,
)
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from limits import parse
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter()

# Motivo con el que se revocan las sesiones al cambiar la contraseña. Se distingue de
# LOGOUT en la bitácora a propósito: "cerró sesión" y "cambió su credencial y por eso se
# cerraron todas" son hechos distintos, y el segundo suele significar que alguien sospecha
# algo.
MOTIVO_CONTRASENA_CAMBIADA = "PASSWORD_CHANGED"  # noqa: S105  motivo de revocación

# Credenciales inválidas: un único mensaje para email inexistente, contraseña incorrecta
# y cuenta desactivada. Distinguirlos permitiría enumerar cuentas válidas del sistema.
INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Email o contraseña incorrectos.",
    headers={"WWW-Authenticate": "Bearer"},
)


def _set_refresh_cookie(response: Response, token: str) -> None:
    """
    Deja el refresh token en una cookie HttpOnly.

    `httponly` lo aísla de cualquier XSS, `samesite=strict` impide que un sitio externo
    dispare el refresco, y `path` lo restringe a las rutas de autenticación para que no
    se adjunte a ninguna otra llamada de la API.
    """
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite="strict",
        path=f"{settings.API_V1_STR}/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite="strict",
        path=f"{settings.API_V1_STR}/auth",
    )


def _respuesta_de_sesion(response: Response, user: User, refresh_token: str) -> TokenResponse:
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(
        access_token=create_access_token(user),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=Union[TokenResponse, DesafioDeSegundoFactor])
@limiter.limit(login_limit)
def login(
    request: Request,
    credentials: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Autentica a un usuario y abre sesión.

    Devuelve un access token de vida corta en el cuerpo (el cliente lo mantiene en memoria)
    y deja el refresh token en una cookie HttpOnly. Cada login abre una **familia** de
    tokens propia: revocar la sesión de un equipo comprometido no cierra la del resto.

    Limitado por IP: bcrypt encarece cada intento, pero sin un tope por minuto nada impide
    encadenar miles de comprobaciones contra un diccionario de contraseñas. `request` es
    obligatorio aquí —slowapi lo necesita para identificar al cliente—, no un parámetro
    sin usar.
    """
    email = credentials.email.strip().lower()
    ip = ip_del_cliente(request)
    agente = request.headers.get("user-agent")
    user = db.query(User).filter(User.email == email).first()

    def _registrar_fallo(motivo: str) -> None:
        # El correo tecleado va en los metadatos y no en `actor_email`: esa columna
        # identifica a una cuenta del sistema, y en un intento fallido puede no existir
        # ninguna. Distinguirlo evita que un barrido de correos inventados quede
        # registrado como si fueran usuarios reales.
        registrar_evento(
            db,
            accion=ACCION_LOGIN_FALLIDO,
            entidad=ENTIDAD_SESION,
            resultado="HTTP_401",
            actor_id=user.id if user is not None else None,
            actor_email=user.email if user is not None else None,
            actor_role=user.role if user is not None else None,
            ip=ip,
            user_agent=agente,
            metadatos={"email_intentado": email, "motivo": motivo},
        )

    if user is None:
        # Se consume un ciclo de bcrypt igualmente: sin esto, la ausencia de usuario
        # respondería mucho más rápido y delataría qué emails existen.
        dummy_verify()
        logger.warning("Intento de login para un email no registrado.")
        _registrar_fallo("email_no_registrado")
        raise INVALID_CREDENTIALS

    if not verify_password(credentials.password, user.hashed_password):
        logger.warning("Intento de login fallido para el usuario %s.", user.email)
        _registrar_fallo("contrasena_incorrecta")
        raise INVALID_CREDENTIALS

    if not user.is_active:
        logger.warning("Intento de login sobre la cuenta desactivada %s.", user.email)
        _registrar_fallo("cuenta_desactivada")
        raise INVALID_CREDENTIALS

    # Segundo factor (capítulo 35). La contraseña era buena; lo que falta es el segundo
    # paso, así que **no se abre sesión todavía**: ni refresh token, ni cookie, ni
    # `last_login_at`, que significa «entró» y aquí todavía no ha entrado.
    #
    # Se responde 200 y no un error. Es el camino normal de una cuenta con segundo factor, y
    # devolver 401 obligaría al cliente a tratar el caso corriente dentro de su rama de
    # fallos, que es donde se acaban tragando los errores de verdad. El discriminador `tipo`
    # es lo que permite distinguir las dos respuestas sin adivinar por los campos.
    if user.totp_activo:
        logger.info("Primer paso correcto, falta el segundo factor: %s.", user.email)
        return DesafioDeSegundoFactor(
            desafio=create_desafio_token(user),
            expira_en=settings.SEGUNDO_FACTOR_DESAFIO_MINUTOS * 60,
            codigos_de_recuperacion_restantes=segundo_factor.codigos_restantes(user),
        )

    user.last_login_at = utc_now()
    db.commit()
    db.refresh(user)

    refresh_token = abrir_sesion(db, user, ip)

    registrar_evento(
        db,
        accion=ACCION_LOGIN,
        entidad=ENTIDAD_SESION,
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        ip=ip,
        user_agent=agente,
    )

    logger.info("Login correcto: %s (rol %s).", user.email, user.role)
    return _respuesta_de_sesion(response, user, refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh_session(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Emite un nuevo access token a partir del refresh token de la cookie HttpOnly, y rota
    también el propio refresh token.

    La rotación es real, no nominal. Antes se entregaba una cookie nueva pero la anterior
    seguía valiendo hasta expirar, de modo que una cookie robada daba siete días de acceso
    renovable sin dejar rastro. Ahora cada emisión se registra y se consume: presentar una
    ya consumida solo puede significar que dos partes tienen la misma cookie, y como no hay
    forma de saber cuál es la legítima, se revoca la sesión entera y ambas vuelven a
    autenticarse.
    """
    expired = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sesión expirada. Vuelva a iniciar sesión.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not token:
        raise expired

    payload = decode_token(token, TOKEN_TYPE_REFRESH)

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        # `from None`: el detalle del `sub` malformado ya se registra; encadenarlo
        # arrastraría información interna a la traza del 401.
        raise expired from None

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        _clear_refresh_cookie(response)
        raise expired

    # `token_version` sube en cada logout: invalida de golpe las sesiones de todos los
    # dispositivos. Se conserva junto al registro de emisiones, no en su lugar: sigue
    # cerrando la sesión aunque la tabla fallara, y es una comprobación de una sola lectura.
    if payload.get("ver") != user.token_version:
        logger.warning("Refresh token revocado presentado por %s.", user.email)
        _clear_refresh_cookie(response)
        raise expired

    ip = ip_del_cliente(request)

    try:
        nuevo_refresh = rotar_sesion(db, user, payload, ip)
    except ReutilizacionDetectada as reutilizacion:
        _clear_refresh_cookie(response)
        registrar_evento(
            db,
            accion=ACCION_REFRESH_REUTILIZADO,
            entidad=ENTIDAD_SESION,
            entidad_id=reutilizacion.family_id,
            resultado="HTTP_401",
            actor_id=user.id,
            actor_email=user.email,
            actor_role=user.role,
            ip=ip,
            user_agent=request.headers.get("user-agent"),
            metadatos={"tokens_revocados": reutilizacion.tokens_revocados},
        )
        # Mensaje distinto del genérico a propósito: el usuario legítimo se acaba de
        # quedar fuera sin haber hecho nada, y merece saber que fue una medida de
        # seguridad y no un fallo del sistema.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "La sesión se cerró por seguridad: se detectó el uso de un token de "
                "refresco ya utilizado. Vuelva a iniciar sesión."
            ),
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except ValueError:
        _clear_refresh_cookie(response)
        raise expired from None

    return _respuesta_de_sesion(response, user, nuevo_refresh)


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user_con_contrasena_prestada),
):
    """
    Cierra la sesión: borra la cookie de refresco e invalida los refresh tokens emitidos.

    Se hacen las dos cosas —revocar las familias vivas e incrementar `token_version`—
    porque cubren fallos distintos: el contador cierra la sesión aunque la escritura en
    `refresh_tokens` fallara, y el registro deja constancia de cuándo y por qué se cerró,
    que es lo que un contador no cuenta.

    Desde el capítulo 23 el contador corta también los access tokens ya emitidos: llevan
    `ver`, y la resolución de identidad la compara en cada petición. Antes seguían valiendo
    hasta expirar, y un token robado sobrevivía al logout de su víctima.
    """
    user = db.query(User).filter(User.id == int(current_user.user_id)).first()
    revocados = 0
    if user is not None:
        revocados = cerrar_sesiones_del_usuario(db, user.id)
        user.token_version += 1
        db.commit()

    registrar_evento(
        db,
        accion=ACCION_LOGOUT,
        entidad=ENTIDAD_SESION,
        actor_id=user.id if user is not None else None,
        actor_email=current_user.email,
        actor_role=current_user.role.value,
        ip=ip_del_cliente(request),
        user_agent=request.headers.get("user-agent"),
        metadatos={"tokens_revocados": revocados},
    )

    _clear_refresh_cookie(response)
    logger.info("Cierre de sesión de %s (%s token(s) revocados).", current_user.email, revocados)
    return {"status": "success", "message": "Sesión cerrada correctamente."}


@router.get("/me", response_model=UserResponse)
def read_current_user(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user_con_contrasena_prestada),
):
    """Devuelve la identidad autenticada, resuelta desde la firma del token y la base de datos."""
    user = db.query(User).filter(User.id == int(current_user.user_id)).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La cuenta asociada al token ya no existe.",
        )
    return UserResponse.model_validate(user)


@router.post("/change-password", response_model=ResultadoDeContrasena)
def cambiar_contrasena_propia(
    request: Request,
    response: Response,
    datos: CambiarContrasenaPropia,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user_con_contrasena_prestada),
):
    """
    Cambia la contraseña de la cuenta autenticada.

    Antes no existía. Cambiar una contraseña —lo primero que hay que hacer con una recibida
    de otra persona, y lo urgente cuando se sospecha que se filtró— exigía que un
    administrador entrara en el servidor a ejecutar el script de sembrado, que además
    reescribía las tres cuentas de demostración a la vez. En la práctica eso significa que
    las contraseñas no se cambiaban.

    Tres cosas que hace y conviene explicar:

    **Pide la contraseña actual** aunque la sesión ya esté autenticada. Un token robado, o
    un equipo que alguien dejó abierto, permite todo lo que la aplicación permita sin
    volver a preguntar; exigir la credencial actual es lo único que impide convertir ese
    acceso prestado en un acceso permanente cambiándola. Si el token bastara, el robo de
    una sesión de quince minutos se transformaría en la pérdida definitiva de la cuenta.

    **Rechaza repetir la contraseña anterior.** «Cambiarla» por la misma no cambia nada, y
    devolver un 200 haría creer que sí.

    **Cierra todas las sesiones, incluida la que hizo el cambio.** Es incómodo —hay que
    volver a entrar— y es la parte que más importa: quien cambia su contraseña casi siempre
    lo hace porque cree que alguien más la tiene, y dejar vivas las sesiones abiertas con
    la credencial anterior deja dentro precisamente a quien se quería echar. Cerrar solo
    «las demás» tampoco vale: no hay forma de saber cuál de las dos sesiones es la legítima.
    """
    usuario = db.query(User).filter(User.id == int(current_user.user_id)).first()
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La cuenta asociada al token ya no existe.",
        )

    if not verify_password(datos.contrasena_actual, usuario.hashed_password):
        registrar_evento(
            db,
            accion=ACCION_CONTRASENA_PROPIA,
            entidad=ENTIDAD_SESION,
            entidad_id=str(usuario.id),
            resultado="HTTP_401",
            actor_id=usuario.id,
            actor_email=usuario.email,
            actor_role=usuario.role,
            ip=ip_del_cliente(request),
            user_agent=request.headers.get("user-agent"),
            metadatos={"motivo": "contrasena_actual_incorrecta"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La contraseña actual no es correcta.",
        )

    if verify_password(datos.nueva_contrasena, usuario.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La contraseña nueva no puede ser igual a la actual.",
        )

    try:
        exigir(datos.nueva_contrasena, email=usuario.email, nombre=usuario.full_name)
    except ContrasenaDebil as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "mensaje": "La contraseña no cumple la política del sistema.",
                "motivos": exc.motivos,
            },
        ) from None

    usuario.hashed_password = hash_password(datos.nueva_contrasena)
    usuario.must_change_password = False
    usuario.password_changed_at = datetime.datetime.now(datetime.timezone.utc)
    revocadas = cerrar_sesiones_del_usuario(db, usuario.id, motivo=MOTIVO_CONTRASENA_CAMBIADA)
    usuario.token_version += 1
    db.commit()

    registrar_evento(
        db,
        accion=ACCION_CONTRASENA_PROPIA,
        entidad=ENTIDAD_SESION,
        entidad_id=str(usuario.id),
        actor_id=usuario.id,
        actor_email=usuario.email,
        actor_role=usuario.role,
        ip=ip_del_cliente(request),
        user_agent=request.headers.get("user-agent"),
        metadatos={"sesiones_cerradas": revocadas},
    )

    _clear_refresh_cookie(response)
    logger.info(
        "%s cambió su contraseña; %s sesión(es) revocadas.", usuario.email, revocadas
    )
    return ResultadoDeContrasena(
        mensaje=(
            "Contraseña actualizada. Se han cerrado todas las sesiones, incluida esta: "
            "vuelva a iniciar sesión con la contraseña nueva."
        ),
        sesiones_cerradas=revocadas,
    )


# ==============================================================================
# Segundo factor (capítulo 35)
# ==============================================================================
# Cierra §3.6 de la congelación. El orden de las rutas sigue el de la vida de un segundo
# factor: se usa al entrar, se consulta, se da de alta, se activa y se da de baja.


def _intentos_agotados(desafio: dict) -> bool:
    """
    ¿Se han gastado ya los intentos de ESTE desafío?

    Se cuenta por desafío y no por cuenta, y es la decisión que evita el escenario que §3.6
    daba como motivo para no hacer nada. Contar por cuenta significa bloquearla, y bloquear
    la cuenta de administración por intentos fallidos le regala a cualquiera una forma de
    dejar al sistema sin administrador: basta con fallar cinco veces contra su correo.

    Contando por desafío, agotar los intentos solo obliga a volver a escribir la contraseña,
    y la cuenta nunca queda inaccesible. El contador vive lo que vive el desafío y se limpia
    solo, así que tampoco hay nada que desbloquear a mano.
    """
    if not limiter.enabled:
        return False
    return not limiter.limiter.hit(
        parse(f"{settings.SEGUNDO_FACTOR_INTENTOS}/{settings.SEGUNDO_FACTOR_DESAFIO_MINUTOS}minute"),
        "segundo-factor",
        desafio["jti"],
    )


@router.post(
    "/login/segundo-factor",
    response_model=TokenResponse,
    responses={401: {"description": "El desafío no vale, o el código no es correcto."}},
)
def completar_login(
    request: Request,
    datos: SegundoFactorDelLogin,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Segundo paso del acceso: el código del teléfono, o uno de recuperación.

    El desafío que trae el cuerpo es lo único que acredita haber superado el primer paso, y
    es de un **tipo propio**: no sirve como `Authorization`, así que no hay forma de llegar
    aquí —ni a ninguna otra ruta— sin haber acertado antes la contraseña.

    El mensaje de error es el mismo para un desafío caducado, uno de otra cuenta y un código
    equivocado. Distinguirlos le diría a quien está probando cuál de las dos mitades ya
    tiene.
    """
    ip = ip_del_cliente(request)
    agente = request.headers.get("user-agent")
    invalido = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="El código no es válido o el acceso ha caducado. Vuelva a iniciar sesión.",
    )

    desafio = decode_token(datos.desafio, TOKEN_TYPE_DESAFIO)
    if _intentos_agotados(desafio):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos. Vuelva a iniciar sesión para obtener un acceso nuevo.",
        )

    try:
        user_id = int(desafio["sub"])
    except (TypeError, ValueError, KeyError):
        raise invalido from None

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active or desafio.get("ver") != user.token_version:
        raise invalido from None

    try:
        forma, restantes = segundo_factor.comprobar(user, datos.codigo)
    except segundo_factor.SegundoFactorInvalido:
        # La comprobación pudo haber tocado el contador; se descarta para no dejar la cuenta
        # con un estado escrito a medias por un intento fallido.
        db.rollback()
        registrar_evento(
            db,
            accion=ACCION_SEGUNDO_FACTOR_FALLIDO,
            entidad=ENTIDAD_SESION,
            resultado="HTTP_401",
            actor_id=user.id,
            actor_email=user.email,
            actor_role=user.role,
            ip=ip,
            user_agent=agente,
        )
        logger.warning("Segundo factor incorrecto para %s.", user.email)
        raise invalido from None

    user.last_login_at = utc_now()
    db.commit()
    db.refresh(user)

    refresh_token = abrir_sesion(db, user, ip)
    registrar_evento(
        db,
        accion=ACCION_SEGUNDO_FACTOR_USADO,
        entidad=ENTIDAD_SESION,
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        ip=ip,
        user_agent=agente,
        # Nunca el código. `forma` distingue el teléfono de un código de recuperación, que
        # es lo que hay que poder ver sin cruzar tablas: gastar uno significa que alguien
        # perdió el teléfono, y dos en una semana significa otra cosa.
        metadatos={"forma": forma, "codigos_de_recuperacion_restantes": restantes},
    )
    registrar_evento(
        db,
        accion=ACCION_LOGIN,
        entidad=ENTIDAD_SESION,
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        ip=ip,
        user_agent=agente,
    )
    logger.info("Login con segundo factor (%s): %s.", forma, user.email)
    return _respuesta_de_sesion(response, user, refresh_token)


@router.get("/segundo-factor", response_model=EstadoDelSegundoFactor)
def estado_del_segundo_factor(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user_sin_segundo_factor),
):
    """Lo que el panel necesita para dibujar la pantalla de seguridad."""
    user = db.query(User).filter(User.id == int(current_user.user_id)).first()
    return EstadoDelSegundoFactor(
        activo=bool(user.totp_activo),
        obligatorio=exige_segundo_factor(user.role),
        activado_en=user.totp_activado_en,
        codigos_de_recuperacion_restantes=segundo_factor.codigos_restantes(user),
    )


@router.post("/segundo-factor/alta", response_model=AltaDeSegundoFactor)
def alta_del_segundo_factor(
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user_sin_segundo_factor),
):
    """
    Genera el secreto y los códigos, y los devuelve **una sola vez**.

    No activa nada: hasta que `/segundo-factor/activar` compruebe un código de verdad, la
    cuenta sigue entrando con la contraseña. Es lo que impide que alguien se quede fuera por
    haber escaneado mal el QR.

    Volver a llamarla descarta el alta anterior y empieza otra. Es a propósito: un alta a
    medias —un QR escaneado en un teléfono que ya no se tiene— se rehace sin pasar por un
    administrador.
    """
    user = db.query(User).filter(User.id == int(current_user.user_id)).first()
    if user.totp_activo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Esta cuenta ya tiene segundo factor activo. Para cambiar de teléfono, "
                "dese de baja primero."
            ),
        )

    alta = segundo_factor.iniciar_alta(user)
    db.commit()

    registrar_evento(
        db,
        accion=ACCION_SEGUNDO_FACTOR_ALTA,
        entidad=ENTIDAD_USUARIO,
        entidad_id=str(user.id),
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        ip=ip_del_cliente(request),
        user_agent=request.headers.get("user-agent"),
        # Ni el secreto, ni la sal, ni los códigos. La bitácora registra que hubo un alta,
        # que es el hecho auditable; lo demás convertiría la tabla de auditoría en el sitio
        # donde sí está guardado el secreto que esta implementación no guarda.
        metadatos={"codigos_emitidos": len(alta.codigos_de_recuperacion)},
    )
    return AltaDeSegundoFactor(
        uri_otpauth=alta.uri_otpauth,
        qr_svg=codigo_qr.svg(alta.uri_otpauth),
        secreto_en_base32=alta.secreto_en_base32,
        codigos_de_recuperacion=alta.codigos_de_recuperacion,
    )


@router.post("/segundo-factor/activar", response_model=EstadoDelSegundoFactor)
def activar_el_segundo_factor(
    request: Request,
    datos: CodigoDelSegundoFactor,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user_sin_segundo_factor),
):
    """
    Comprueba un código del teléfono y activa el segundo factor.

    A partir de aquí, entrar exige los dos pasos.
    """
    user = db.query(User).filter(User.id == int(current_user.user_id)).first()
    try:
        segundo_factor.activar(user, datos.codigo)
    except segundo_factor.AltaNoIniciada as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except segundo_factor.SegundoFactorInvalido:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Ese código no coincide. Compruebe que la hora del teléfono sea la correcta "
                "y vuelva a intentarlo con el código que se vea ahora."
            ),
        ) from None
    db.commit()
    db.refresh(user)

    registrar_evento(
        db,
        accion=ACCION_SEGUNDO_FACTOR_ACTIVADO,
        entidad=ENTIDAD_USUARIO,
        entidad_id=str(user.id),
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        ip=ip_del_cliente(request),
        user_agent=request.headers.get("user-agent"),
    )
    logger.info("Segundo factor activado por %s.", user.email)
    return EstadoDelSegundoFactor(
        activo=True,
        obligatorio=exige_segundo_factor(user.role),
        activado_en=user.totp_activado_en,
        codigos_de_recuperacion_restantes=segundo_factor.codigos_restantes(user),
    )


@router.post("/segundo-factor/baja", response_model=EstadoDelSegundoFactor)
def baja_del_segundo_factor(
    request: Request,
    datos: CodigoDelSegundoFactor,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Quita el segundo factor de la propia cuenta, demostrando que se tiene.

    Con una salvaguarda que es justo lo que §3.6 pedía resolver: **la última cuenta de
    administración con segundo factor no se lo puede quitar**. Una cuenta de administración
    sin segundo factor no puede operar, así que darse de baja siendo el único que lo tiene
    activo dejaría el sistema sin administración utilizable hasta volver a darse de alta.
    """
    user = db.query(User).filter(User.id == int(current_user.user_id)).first()
    try:
        segundo_factor.comprobar(user, datos.codigo)
    except segundo_factor.SegundoFactorInvalido:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Ese código no coincide.",
        ) from None

    ultimo = (
        exige_segundo_factor(user.role)
        and segundo_factor.administradores_con_segundo_factor(db, excluyendo=user.id) == 0
    )
    if ultimo:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Es la única cuenta de administración con segundo factor activo. Active el "
                "de otra cuenta de administración antes de quitar el suyo, o el sistema se "
                "queda sin administración utilizable."
            ),
        )

    segundo_factor.desactivar(user)
    db.commit()

    registrar_evento(
        db,
        accion=ACCION_SEGUNDO_FACTOR_DESACTIVADO,
        entidad=ENTIDAD_USUARIO,
        entidad_id=str(user.id),
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        ip=ip_del_cliente(request),
        user_agent=request.headers.get("user-agent"),
        metadatos={"por": "el_titular"},
    )
    logger.info("Segundo factor desactivado por su titular: %s.", user.email)
    return EstadoDelSegundoFactor(
        activo=False,
        obligatorio=exige_segundo_factor(user.role),
        codigos_de_recuperacion_restantes=0,
    )
