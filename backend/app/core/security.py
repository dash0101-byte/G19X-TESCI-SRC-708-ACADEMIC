"""
Autenticación y autorización del Sistema Inteligente de Lead Scoring.

Modelo de confianza: la identidad del usuario procede EXCLUSIVAMENTE de un JWT firmado
con `SECRET_KEY` (HS256) que este backend emitió en `POST /api/v1/auth/login`. Las
cabeceras `X-User-*` / `X-Entra-*` que existían antes eran auto-declaradas por el cliente
—cualquiera podía enviarse a sí mismo `X-User-Role: System_Admin`— y ya no se leen en
ningún punto del sistema.
"""
import datetime
import enum
import hashlib
import hmac
import logging
import uuid
from typing import List, Optional

import bcrypt
import jwt
from app.core.config import settings
from app.core.database import get_db
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import PyJWTError
from pydantic import BaseModel
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# bcrypt trunca silenciosamente por encima de 72 bytes: se valida explícitamente
# para que una contraseña larga nunca quede recortada sin que nadie se entere.
BCRYPT_MAX_PASSWORD_BYTES = 72

TOKEN_TYPE_ACCESS = "access"   # noqa: S105  valor del claim `typ`, no una contraseña
TOKEN_TYPE_REFRESH = "refresh"  # noqa: S105  valor del claim `typ`, no una contraseña

# `auto_error=False` para poder devolver un 401 propio con `WWW-Authenticate`
# en lugar del 403 genérico de Starlette cuando falta la cabecera.
_bearer_scheme = HTTPBearer(auto_error=False)


class UserRole(str, enum.Enum):
    COMMERCIAL_EXECUTIVE = "Commercial_Executive"  # Asesor comercial: consulta leads, registra actividades
    SALES_LEAD = "Sales_Lead"                      # Líder comercial: asignación, analíticas, edición
    SYSTEM_ADMIN = "System_Admin"                  # Administrador TI: recálculos masivos, eliminación, config


class CurrentUser(BaseModel):
    """
    Identidad del solicitante, derivada exclusivamente del token firmado.

    No lleva `tenant_id`. El sistema declaraba uno y lo incluía en cada token, pero ninguna
    consulta filtraba por él: `leads`, `campaigns` y `sales_reps` no tienen esa columna, de
    modo que cualquier usuario veía la cartera completa con independencia del valor. Un
    identificador de inquilino que no aísla nada es peor que no tenerlo, porque induce a
    creer que la separación existe. Si en el futuro se necesita multi-tenencia de verdad,
    hay que añadir la columna a las tablas de negocio y filtrar en el repositorio; el
    Capítulo 11 de la memoria técnica recoge la decisión.
    """

    user_id: str
    email: str
    name: str
    role: UserRole
    is_authenticated: bool = True


# ==============================================================================
# Hashing de contraseñas (bcrypt)
# ==============================================================================

def hash_password(plain_password: str) -> str:
    """Deriva el hash bcrypt de una contraseña en claro."""
    password_bytes = plain_password.encode("utf-8")
    if len(password_bytes) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(
            f"La contraseña excede el máximo de {BCRYPT_MAX_PASSWORD_BYTES} bytes admitido por bcrypt."
        )
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Comprueba una contraseña contra su hash almacenado.

    Devuelve False ante cualquier hash malformado en lugar de propagar la excepción,
    para que un registro corrupto se traduzca en credenciales inválidas y no en un 500.
    """
    try:
        password_bytes = plain_password.encode("utf-8")
        if len(password_bytes) > BCRYPT_MAX_PASSWORD_BYTES:
            return False
        return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def dummy_verify() -> None:
    """
    Consume un ciclo de bcrypt cuando el email no existe.

    Iguala el tiempo de respuesta entre "usuario inexistente" y "contraseña incorrecta",
    impidiendo enumerar cuentas válidas midiendo la latencia del login.
    """
    bcrypt.checkpw(
        b"tiempo-constante",
        b"$2b$12$C6UzMDM.H6dfI/f/IKcEe.rHkBBnBiKcgAWM2ZmSTBEXVKGYGN0Qy",
    )


# ==============================================================================
# Emisión y verificación de JWT
# ==============================================================================

def _create_token(
    *,
    subject: str,
    token_type: str,
    expires_delta: datetime.timedelta,
    extra_claims: Optional[dict] = None,
    jti: Optional[str] = None,
) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": subject,
        "typ": token_type,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        # El refresh token trae el suyo, porque queda registrado en `refresh_tokens` y el
        # emisor necesita conocerlo antes de firmar. El access token no se registra —es de
        # vida corta y se verifica solo por firma—, así que le basta un valor nuevo.
        "jti": jti or uuid.uuid4().hex,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user) -> str:
    """
    Emite el access token de vida corta que el frontend mantiene solo en memoria.

    Lleva `ver`, la `token_version` de la cuenta al emitirlo (capítulo 23). La resolución
    de identidad ya lee la cuenta de la base en cada petición; comparar `ver` ahí no cuesta
    ninguna consulta más y hace que cerrar sesión, cambiar o restablecer la contraseña,
    cambiar el rol o desactivar la cuenta invaliden también los access tokens ya emitidos,
    y no solo la capacidad de renovarlos.
    """
    return _create_token(
        subject=str(user.id),
        token_type=TOKEN_TYPE_ACCESS,
        expires_delta=datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        extra_claims={
            "email": user.email,
            "role": user.role,
            "name": user.full_name,
            "ver": user.token_version,
        },
    )


def create_refresh_token(user, *, jti: str, family_id: str) -> str:
    """
    Emite el refresh token de vida larga que viaja en cookie HttpOnly.

    `jti` y `family_id` son obligatorios y los asigna `app.services.session_service`, que
    es quien lleva el registro de emisiones. Se exigen como argumentos con nombre, sin
    valor por defecto, para que no se pueda emitir un token sin registrar: un refresh
    token que no esté en la tabla no se puede consumir, y uno emitido "por comodidad"
    desde otro punto del código dejaría al usuario con una cookie que nunca funciona.

    Claims propios:

    * `jti` — identifica esta emisión concreta. Al refrescar se marca como consumida, y
      presentarla de nuevo es lo que delata que dos partes tienen la misma cookie.
    * `fid` — la familia, común a toda la cadena de refrescos de una misma sesión. Es la
      unidad que se revoca en bloque cuando se detecta una reutilización.
    * `ver` — se compara contra `User.token_version`, que sube al cerrar sesión. Se
      conserva junto al registro y no en su lugar: sigue funcionando aunque la tabla
      falle, y cierra la sesión en todos los dispositivos de una sola vez.
    """
    return _create_token(
        subject=str(user.id),
        token_type=TOKEN_TYPE_REFRESH,
        expires_delta=datetime.timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        extra_claims={"ver": user.token_version, "fid": family_id},
        jti=jti,
    )


def decode_token(token: str, expected_type: str) -> dict:
    """
    Verifica firma, emisor, audiencia y expiración de un token, y que su tipo sea el esperado.

    `expected_type` impide que un refresh token se presente como access token (y viceversa):
    sin esa comprobación, la cookie de refresco de vida larga serviría para llamar a la API.
    Lanza HTTPException 401 ante cualquier fallo, sin distinguir la causa hacia el cliente.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas o sesión expirada.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # PyJWT solo comprueba un claim si viene; `require` hace que falte uno sea también un
        # rechazo. Son los que esta aplicación pone en todos sus tokens, así que ninguno
        # legítimo carece de ellos, y uno fabricado sin `exp` no vale para siempre.
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            options={"require": ["exp", "iat", "nbf", "iss", "aud", "sub", "jti"]},
        )
    except PyJWTError as exc:
        logger.info("Token rechazado: %s", exc)
        raise credentials_error from None

    if payload.get("typ") != expected_type:
        logger.warning(
            "Token de tipo '%s' presentado donde se esperaba '%s'.", payload.get("typ"), expected_type
        )
        raise credentials_error from None
    if not payload.get("sub"):
        raise credentials_error from None
    return payload


# ==============================================================================
# Dependencias de FastAPI
# ==============================================================================

# Código que acompaña al 403 de una cuenta con contraseña prestada. Va en el cuerpo, y no
# solo en el texto, para que el cliente distinga «cambie su contraseña» de «su rol no
# llega» sin comparar cadenas, que se rompen en cuanto alguien reescribe un mensaje.
CODIGO_CAMBIO_OBLIGATORIO = "cambio_de_contrasena_obligatorio"


def _resolver_identidad(
    credentials: Optional[HTTPAuthorizationCredentials],
    db: Session,
    *,
    admitir_contrasena_prestada: bool,
) -> CurrentUser:
    """
    Resuelve la identidad autenticada a partir del `Authorization: Bearer <jwt>`.

    El rol NO se toma del token sin más: se recarga desde la base de datos en cada
    petición, de modo que una degradación de privilegios surte efecto de inmediato
    y no queda congelada hasta que expire el token.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Se requiere autenticación mediante token Bearer.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or not credentials.credentials:
        raise credentials_error from None

    payload = decode_token(credentials.credentials, TOKEN_TYPE_ACCESS)

    # Import local: evita un ciclo de importación entre entities y core.security
    from app.models.entities import User

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise credentials_error from None

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        logger.warning("Token válido para un usuario inexistente o desactivado (sub=%s).", payload.get("sub"))
        raise credentials_error from None

    # Revocación inmediata (§14.7, capítulo 23). Hasta aquí, cerrar sesión, cambiar la
    # contraseña o degradar una cuenta cortaba la renovación, pero el access token ya
    # emitido seguía valiendo sus quince minutos: un token robado sobrevivía al logout de
    # su víctima. La cuenta ya se lee en cada petición —es la consulta de arriba—, así que
    # comparar la versión no añade ninguna. Un token sin `ver` es anterior a este cambio y
    # tampoco vale: caducaría solo en minutos, y aceptarlo reabriría el hueco.
    if payload.get("ver") != user.token_version:
        logger.info("Access token revocado presentado por %s.", user.email)
        raise credentials_error from None

    try:
        user_role = UserRole(user.role)
    except ValueError:
        logger.error("Usuario %s tiene un rol no reconocido en base de datos: '%s'.", user.email, user.role)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El rol asignado a su cuenta no es válido. Contacte al administrador.",
        ) from None

    # La contraseña prestada —la que fijó un administrador al dar de alta, restablecer o
    # reactivar la cuenta— la conoce al menos otra persona. Mientras siga siendo esa, la
    # cuenta no identifica a quien la usa, y todo lo que esta aplicación protege por
    # identidad —la cartera de cada asesor, la bitácora, la gestión de cuentas— cuelga de
    # eso. Hasta la Fase 13 la marca se anotaba y la interfaz la enseñaba, pero el servidor
    # dejaba operar igual (§15.8): una marca que se registra y no se impone es un valor que
    # cierra una pregunta que sigue abierta.
    #
    # Se comprueba AQUÍ, en la resolución de identidad, y no con una lista de rutas
    # bloqueadas. Así un endpoint nuevo nace cerrado para estas cuentas sin que nadie tenga
    # que acordarse; la excepción hay que pedirla por su nombre
    # (`get_current_user_con_contrasena_prestada`), y solo la piden tres rutas.
    if user.must_change_password and not admitir_contrasena_prestada:
        logger.info("Petición de %s rechazada hasta que cambie la contraseña prestada.", user.email)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "codigo": CODIGO_CAMBIO_OBLIGATORIO,
                "mensaje": (
                    "Esta cuenta tiene una contraseña fijada por otra persona. Cámbiela "
                    "antes de seguir: hasta entonces solo puede consultar su perfil, "
                    "cambiarla o cerrar la sesión."
                ),
            },
        )

    return CurrentUser(
        user_id=str(user.id),
        email=user.email,
        name=user.full_name,
        role=user_role,
        is_authenticated=True,
    )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """
    Identidad autenticada de una cuenta que puede operar.

    Es la dependencia de todos los endpoints —directamente, o a través de `require_roles`,
    `auditar` y `alcance_actual`—. Además de lo que rechaza cualquier autenticación,
    rechaza a las cuentas que siguen con la contraseña que les fijó otra persona.
    """
    return _resolver_identidad(credentials, db, admitir_contrasena_prestada=False)


def get_current_user_con_contrasena_prestada(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """
    La excepción, pedida por su nombre: admite cuentas con contraseña prestada.

    Solo para lo que esa cuenta necesita para dejar de estarlo: saber quién es
    (`/auth/me`), cambiarla (`/auth/change-password`) y salir (`/auth/logout`). Una prueba
    enumera las rutas que la usan y falla si aparece una cuarta.
    """
    return _resolver_identidad(credentials, db, admitir_contrasena_prestada=True)


def require_roles(allowed_roles: List[UserRole]):
    """
    Fábrica de dependencias de autorización RBAC.
    Verifica que el usuario autenticado posea uno de los roles autorizados.

    La denegación se escribe en la bitácora de auditoría además de en el log de texto.
    Se hace aquí y no en la dependencia `auditar(...)` porque el 403 nace en este punto,
    antes de que el endpoint —y por tanto su asiento— llegue a ejecutarse: si esperáramos
    al desmontaje de aquella dependencia, la única operación que nunca quedaría registrada
    sería precisamente la que alguien intentó hacer sin permiso.
    """
    def role_checker(
        request: Request,
        db: Session = Depends(get_db),
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if current_user.role not in allowed_roles and current_user.role != UserRole.SYSTEM_ADMIN:
            logger.warning(
                f"Acceso denegado a {current_user.email} con rol {current_user.role.value}. "
                f"Se requiere: {[r.value for r in allowed_roles]}"
            )
            # Import local: `app.core.audit` importa de este módulo (CurrentUser,
            # get_current_user), así que hacerlo arriba cerraría el ciclo.
            from app.core.audit import (
                ACCION_ACCESO_DENEGADO,
                ENTIDAD_ENDPOINT,
                registrar_evento,
            )
            from app.core.proxy import ip_del_cliente

            registrar_evento(
                db,
                accion=ACCION_ACCESO_DENEGADO,
                entidad=ENTIDAD_ENDPOINT,
                entidad_id=request.url.path,
                resultado="HTTP_403",
                actor_id=int(current_user.user_id) if current_user.user_id.isdigit() else None,
                actor_email=current_user.email,
                actor_role=current_user.role.value,
                ip=ip_del_cliente(request),
                user_agent=request.headers.get("user-agent"),
                metadatos={
                    "metodo": request.method,
                    "roles_requeridos": [r.value for r in allowed_roles],
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso restringido. Su rol ({current_user.role.value}) no tiene privilegios suficientes para esta operación.",
            )
        return current_user

    return role_checker


# ==============================================================================
# Autenticación del webhook CRM (HMAC-SHA256 + anti-replay)
# ==============================================================================

SIGNATURE_HEADER = "X-PluriOne-Signature"
TIMESTAMP_HEADER = "X-PluriOne-Timestamp"


def build_webhook_signature(timestamp: str, body: bytes, secret: str) -> str:
    """
    Calcula la firma esperada sobre `<timestamp>.<cuerpo crudo>`.

    Incluir el timestamp DENTRO del mensaje firmado es lo que impide reutilizar una
    captura antigua: cambiar la marca de tiempo invalida la firma, y conservarla la
    deja fuera de la ventana de tolerancia.
    """
    message = timestamp.encode("utf-8") + b"." + body
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


INTEGRACION_NO_DISPONIBLE = "Integración no disponible."


async def verify_crm_webhook(request: Request) -> bytes:
    """
    Autentica una petición de webhook CRM y devuelve su cuerpo crudo ya validado.

    Desde la Fase 15 el CRM tiene interruptor propio, como el resto de integraciones
    (`INTEGRACION_CRM_ACTIVA`). Apagado responde 404, igual que una integración que no
    existe: quien no tiene por qué saber que hay un CRM conectado no lo averigua por aquí.
    """
    if not settings.INTEGRACION_CRM_ACTIVA:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=INTEGRACION_NO_DISPONIBLE)
    return await verificar_firma_de_entrega(request, settings.CRM_WEBHOOK_SECRET, "CRM")


async def verificar_firma_de_entrega(request: Request, secret: str, etiqueta: str) -> bytes:
    """
    Autentica una entrega firmada y devuelve su cuerpo crudo ya validado.

    Comprueba, en este orden: que exista un secreto configurado, que el cuerpo no exceda
    el tope de tamaño, que la marca de tiempo esté dentro de la ventana anti-replay y que
    la firma HMAC-SHA256 coincida (comparada en tiempo constante).

    El secreto lo elige quien llama: cada integración firma con el suyo, de modo que
    revocar uno —o filtrarse— no afecta a las demás.
    """
    if not secret:
        logger.error("Entrega de '%s' recibida sin secreto configurado; se rechaza.", etiqueta)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La ingesta por webhook no está habilitada en este despliegue.",
        )

    auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Firma de webhook inválida o ausente.",
    )

    # Rechazo temprano por Content-Length antes siquiera de leer el cuerpo
    declared_length = request.headers.get("content-length")
    if declared_length is not None:
        try:
            declared = int(declared_length)
        except ValueError:
            raise auth_error from None
        if declared > settings.CRM_WEBHOOK_MAX_BODY_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="El cuerpo del webhook excede el tamaño máximo permitido.",
            )

    body = await request.body()
    if len(body) > settings.CRM_WEBHOOK_MAX_BODY_BYTES:
        # Segunda comprobación: cubre peticiones con Transfer-Encoding: chunked, que no
        # declaran Content-Length y esquivarían el control anterior.
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="El cuerpo del webhook excede el tamaño máximo permitido.",
        )

    signature = request.headers.get(SIGNATURE_HEADER)
    timestamp = request.headers.get(TIMESTAMP_HEADER)
    if not signature or not timestamp:
        logger.warning("Entrega de '%s' sin cabeceras de firma o marca de tiempo.", etiqueta)
        raise auth_error from None

    try:
        sent_at = int(timestamp)
    except ValueError:
        logger.warning("Entrega de '%s' con marca de tiempo no numérica.", etiqueta)
        raise auth_error from None

    now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    # abs(): descarta tanto repeticiones antiguas como marcas de tiempo futuras
    if abs(now - sent_at) > settings.CRM_WEBHOOK_TOLERANCE_SECONDS:
        logger.warning(
            "Entrega de '%s' fuera de la ventana anti-replay (desfase de %ss).", etiqueta, now - sent_at
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La marca de tiempo del webhook está fuera de la ventana permitida.",
        )

    expected = build_webhook_signature(timestamp, body, secret)
    if not hmac.compare_digest(expected, signature):
        logger.warning("Entrega de '%s' con firma HMAC no coincidente.", etiqueta)
        raise auth_error from None

    return body
