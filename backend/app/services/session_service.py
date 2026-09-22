"""
Ciclo de vida de las sesiones: emisión, rotación y revocación de refresh tokens.

El problema que resuelve
------------------------
La rotación era nominal. `/auth/refresh` entregaba una cookie nueva, pero la anterior
seguía siendo válida hasta expirar: lo único que se comprobaba era `token_version`, que
solo cambia al cerrar sesión. Quien robara la cookie —copia de un backup, acceso físico
al equipo, un proxy mal configurado— disponía de siete días de acceso renovable, y el
robo era invisible: víctima y atacante refrescaban en paralelo, cada uno con su cadena,
sin estorbarse.

Aquí cada emisión queda registrada con un `jti` propio y una `family_id` común a toda la
cadena nacida de un mismo login. Refrescar consume el token presentado y emite otro de la
misma familia. Presentar uno ya consumido significa que dos partes tienen la misma cookie;
como no hay manera de distinguir cuál es la legítima, se revoca la familia entera y ambas
vuelven a autenticarse. El robo pasa a costar una sesión en lugar de una semana.

La carrera honesta
------------------
Dos pestañas del mismo navegador pueden refrescar a la vez: cada una tiene su propio
módulo de API y la deduplicación del cliente no cruza pestañas. La segunda llegaría con
un token recién consumido y, con una detección estricta, cerraría la sesión de un usuario
que no hizo nada malo. Por eso hay una ventana de gracia breve: un token consumido hace
menos de `REFRESH_ROTATION_GRACE_SECONDS` se trata como esa carrera y se rota con
normalidad. Vuelve a abrir la ventana de robo, sí, pero de segundos frente a los siete
días de antes, y es lo que separa una medida de seguridad de una que se acaba desactivando
porque expulsa a la gente de su sesión.
"""
import datetime
import logging
import uuid
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_refresh_token
from app.models.entities import RefreshToken, utc_now

logger = logging.getLogger(__name__)

# Motivos de revocación. Se guardan para poder distinguir, al investigar, un token
# simplemente consumido de uno tumbado por una reutilización.
MOTIVO_ROTADO = "ROTATED"
MOTIVO_REUTILIZADO = "REUSE_DETECTED"
MOTIVO_LOGOUT = "LOGOUT"
MOTIVO_FAMILIA_REVOCADA = "FAMILY_REVOKED"


class ReutilizacionDetectada(Exception):
    """
    Se presentó un refresh token ya consumido fuera de la ventana de gracia.

    Es una excepción propia y no un 401 directo porque el endpoint tiene que hacer dos
    cosas distintas con ella —borrar la cookie y responder con un mensaje que explique
    por qué la sesión se cerró sola—, y porque a la capa de servicio no le corresponde
    conocer códigos HTTP.
    """

    def __init__(self, family_id: str, tokens_revocados: int):
        self.family_id = family_id
        self.tokens_revocados = tokens_revocados
        super().__init__(
            f"Refresh token reutilizado; se revocó la familia {family_id} "
            f"({tokens_revocados} token(s))."
        )


def _aware(momento: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
    """
    Normaliza a UTC con zona explícita.

    SQLite no tiene tipo con zona horaria y devuelve lo que guardó como *naive*. Comparar
    ese valor con un `datetime` con zona es un `TypeError` en Python, así que la suite
    fallaría donde producción funciona —o al revés—, que es la peor forma de descubrirlo.
    """
    if momento is None:
        return None
    if momento.tzinfo is None:
        return momento.replace(tzinfo=datetime.timezone.utc)
    return momento


def _revocar(registro: RefreshToken, motivo: str, momento: datetime.datetime) -> None:
    """Marca un token como no utilizable, respetando la primera revocación."""
    if registro.revoked_at is None:
        registro.revoked_at = momento
        registro.revoked_reason = motivo


def _emitir(
    db: Session,
    user,
    family_id: str,
    ip: Optional[str],
    reemplaza_a: Optional[str] = None,
) -> str:
    """
    Emite un refresh token de la familia indicada y deja exactamente uno vigente en ella.

    Revocar de paso cualquier otro token vivo de la familia es lo que sostiene el
    invariante del que depende la detección: si una familia pudiera tener dos tokens
    vigentes, presentar uno consumido dejaría de ser prueba de nada.
    """
    ahora = utc_now()
    jti = uuid.uuid4().hex

    vivos = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.family_id == family_id,
            RefreshToken.revoked_at.is_(None),
        )
        .all()
    )
    for anterior in vivos:
        _revocar(anterior, MOTIVO_ROTADO, ahora)
        anterior.replaced_by_jti = jti

    db.add(
        RefreshToken(
            jti=jti,
            family_id=family_id,
            user_id=user.id,
            issued_at=ahora,
            expires_at=ahora + datetime.timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            issued_ip=ip,
        )
    )
    if reemplaza_a:
        logger.debug("Refresh token %s reemplazado por %s.", reemplaza_a, jti)

    return create_refresh_token(user, jti=jti, family_id=family_id)


def abrir_sesion(db: Session, user, ip: Optional[str] = None) -> str:
    """
    Inicia una familia nueva y devuelve su primer refresh token.

    Cada login abre su propia familia: revocar la sesión de un portátil comprometido no
    debe cerrar la del teléfono, y eso solo es posible si las cadenas son independientes.
    """
    family_id = uuid.uuid4().hex
    token = _emitir(db, user, family_id, ip)
    db.commit()
    logger.info("Sesión abierta para %s (familia %s).", user.email, family_id)
    return token


def rotar_sesion(db: Session, user, payload: dict, ip: Optional[str] = None) -> str:
    """
    Consume el refresh token presentado y emite el siguiente de su familia.

    Lanza `ReutilizacionDetectada` cuando el token ya se había consumido fuera de la
    ventana de gracia, tras revocar la familia completa. Lanza `ValueError` cuando el
    token es coherente en su firma pero no está registrado o ya venció: se distingue del
    caso anterior porque no hay familia que revocar ni indicio de robo, solo una cookie
    que dejó de servir.
    """
    jti = payload.get("jti")
    if not jti:
        raise ValueError("El refresh token no lleva identificador de emisión.")

    registro = db.query(RefreshToken).filter(RefreshToken.jti == jti).first()
    if registro is None:
        # Firma válida pero sin registro: es un token emitido antes de que existiera esta
        # tabla, o uno cuya familia se purgó. No hay nada que revocar y tampoco prueba de
        # abuso; se invalida y se obliga a iniciar sesión.
        raise ValueError("El refresh token presentado no está registrado.")

    if registro.user_id != user.id:
        # El `sub` del token y el dueño registrado del `jti` no coinciden. No debería
        # ocurrir nunca; si ocurre, es manipulación y la familia cae.
        revocados = revocar_familia(db, registro.family_id, MOTIVO_REUTILIZADO)
        db.commit()
        raise ReutilizacionDetectada(registro.family_id, revocados)

    ahora = utc_now()

    if registro.revoked_at is not None:
        revocado_en = _aware(registro.revoked_at)
        dentro_de_gracia = (
            registro.revoked_reason == MOTIVO_ROTADO
            and (ahora - revocado_en).total_seconds() <= settings.REFRESH_ROTATION_GRACE_SECONDS
        )
        if not dentro_de_gracia:
            revocados = revocar_familia(db, registro.family_id, MOTIVO_REUTILIZADO)
            db.commit()
            logger.warning(
                "Reutilización de refresh token detectada para %s (familia %s, motivo previo %s): "
                "se revocaron %s token(s) y la sesión queda cerrada.",
                user.email,
                registro.family_id,
                registro.revoked_reason,
                revocados,
            )
            raise ReutilizacionDetectada(registro.family_id, revocados)

        logger.info(
            "Refrescos simultáneos para %s dentro de la ventana de gracia (familia %s); "
            "se trata como carrera del cliente, no como reutilización.",
            user.email,
            registro.family_id,
        )

    if _aware(registro.expires_at) <= ahora:
        raise ValueError("El refresh token presentado ya venció.")

    _revocar(registro, MOTIVO_ROTADO, ahora)
    token = _emitir(db, user, registro.family_id, ip, reemplaza_a=jti)
    db.commit()
    return token


def revocar_familia(db: Session, family_id: str, motivo: str = MOTIVO_FAMILIA_REVOCADA) -> int:
    """
    Revoca todos los tokens vigentes de una familia. Devuelve cuántos cayeron.

    No hace `commit`: quien la llama decide si esto forma parte de una transacción mayor.
    """
    ahora = utc_now()
    vigentes = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.family_id == family_id,
            RefreshToken.revoked_at.is_(None),
        )
        .all()
    )
    for registro in vigentes:
        _revocar(registro, motivo, ahora)
    return len(vigentes)


def cerrar_sesiones_del_usuario(db: Session, user_id: int, motivo: str = MOTIVO_LOGOUT) -> int:
    """
    Revoca todas las familias vivas de un usuario. Devuelve cuántos tokens cayeron.

    Es lo que hace el logout, junto con incrementar `token_version`. Las dos cosas se
    solapan a propósito: `token_version` cierra la sesión aunque el registro fallara, y el
    registro explica *cuándo y por qué* se cerró, que es lo que un contador no cuenta.
    """
    ahora = utc_now()
    vigentes = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .all()
    )
    for registro in vigentes:
        _revocar(registro, motivo, ahora)
    return len(vigentes)


def consulta_tokens_caducados(db: Session, corte: datetime.datetime):
    """Los registros que vencieron antes de `corte`. La purga borra esto y la simulación lo cuenta."""
    return db.query(RefreshToken).filter(RefreshToken.expires_at < corte)


def purgar_tokens_caducados(
    db: Session, margen_dias: int = 30, ahora: Optional[datetime.datetime] = None
) -> int:
    """
    Borra los registros ya vencidos hace tiempo. Devuelve cuántas filas se eliminaron.

    El margen existe porque un token vencido revocado por reutilización sigue siendo la
    prueba de un incidente; borrarlo el mismo día en que caduca destruiría el rastro justo
    cuando alguien podría estar buscándolo.

    Existía desde la Fase 9 y nada la llamaba (§20.5). Desde el capítulo 22 la invoca la
    pasada diaria de `scripts/retencion_historial.py`, con `CONSERVACION_SESIONES_DIAS`.
    """
    corte = (ahora or utc_now()) - datetime.timedelta(days=margen_dias)
    borrados = consulta_tokens_caducados(db, corte).delete(synchronize_session=False)
    db.commit()
    if borrados:
        logger.info("Purga de refresh tokens: %s registro(s) vencidos eliminados.", borrados)
    return borrados


def estado_de_la_familia(db: Session, family_id: str) -> Tuple[int, int]:
    """Cuántos tokens tiene una familia y cuántos siguen vigentes. Útil en pruebas y soporte."""
    tokens = db.query(RefreshToken).filter(RefreshToken.family_id == family_id).all()
    return len(tokens), sum(1 for t in tokens if t.revoked_at is None)
