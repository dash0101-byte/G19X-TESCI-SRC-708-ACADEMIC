"""
Gestión de cuentas y de asesores comerciales. Solo `System_Admin`.

Hasta ahora las cuentas solo existían si alguien ejecutaba `seed_data.py` contra la base.
Dar de alta a una persona nueva, retirar a quien se marchó o cambiarle el rol a alguien
exigía acceso al servidor y a la línea de comandos, así que en la práctica lo hacía quien
tuviera ese acceso, sin dejar rastro y con las tres cuentas de demostración compartidas
por todo el equipo. Un sistema de roles cuidadosamente diseñado no protege nada si la
forma normal de trabajar es que varias personas usen la misma cuenta.

Tres decisiones que conviene justificar:

**No hay borrado, hay baja.** `DELETE /users/{id}` desactiva; no elimina la fila. Un
borrado real dejaría huérfanos los asientos de auditoría de esa persona y los prospectos
que atendió, justo cuando más falta hace poder reconstruir quién hizo qué. Y la respuesta
a «se fue de la empresa» es que deje de entrar, no que desaparezca de la historia.

**Un administrador no puede quitarse a sí mismo.** Ni desactivarse, ni bajarse de rol. No
es una cortesía: si el último `System_Admin` se degrada por error, nadie puede volver a
subirlo y el sistema queda sin quien lo administre. La comprobación cuenta cuántos
administradores activos quedarían.

**Restablecer una contraseña obliga a cambiarla.** Quien la fija la conoce, y una
credencial que conoce otra persona no identifica a nadie. La cuenta queda marcada con
`must_change_password` y sus sesiones vivas se revocan.
"""
import logging
from typing import List, Optional

from app.core import integridad
from app.core.audit import (
    ACCION_CARTERA_REPARTIR,
    ACCION_USUARIO_ACTUALIZAR,
    ACCION_USUARIO_CAMBIO_DE_ROL,
    ACCION_USUARIO_CREAR,
    ACCION_USUARIO_DESACTIVAR,
    ACCION_USUARIO_REACTIVAR,
    ACCION_USUARIO_RESET_CONTRASENA,
    ENTIDAD_USUARIO,
    AsientoDeAuditoria,
    auditar,
)
from app.core.database import get_db
from app.core.passwords import ContrasenaDebil, exigir
from app.core.security import CurrentUser, UserRole, hash_password, require_roles
from app.models.entities import Lead, User
from app.schemas.user import (
    AsesorResponse,
    ListaDeAsesores,
    ListaDeUsuarios,
    RepartoDeCartera,
    RestablecerContrasena,
    ResultadoDeReparto,
    UsuarioCreate,
    UsuarioResponse,
    UsuarioUpdate,
)
from app.services.session_service import cerrar_sesiones_del_usuario
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter()

MOTIVO_CONTRASENA_RESTABLECIDA = "PASSWORD_RESET"  # noqa: S105  motivo de revocación
MOTIVO_CUENTA_DESACTIVADA = "ACCOUNT_DISABLED"
MOTIVO_ROL_CAMBIADO = "ROLE_CHANGED"

CAPACIDAD_POR_DEFECTO = 50


# ==============================================================================
# Utilidades
# ==============================================================================

def _detalle_de_contrasena(exc: ContrasenaDebil) -> HTTPException:
    """
    422 con **todos** los motivos.

    Devolver solo el primero obliga a descubrir la política a base de intentos, y cada
    rechazo empuja un poco más hacia poner lo primero que se acepte.
    """
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "mensaje": "La contraseña no cumple la política del sistema.",
            "motivos": exc.motivos,
        },
    )


def _buscar(db: Session, user_id: int) -> User:
    usuario = db.query(User).filter(User.id == user_id).first()
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe la cuenta {user_id}.",
        )
    return usuario


def _administradores_activos_restantes(db: Session, excepto_id: int) -> int:
    return (
        db.query(func.count(User.id))
        .filter(
            User.role == UserRole.SYSTEM_ADMIN.value,
            User.is_active.is_(True),
            User.id != excepto_id,
        )
        .scalar()
        or 0
    )


def _exigir_que_quede_un_administrador(db: Session, usuario: User, accion: str) -> None:
    """
    Impide dejar el sistema sin nadie que pueda administrarlo.

    El caso que cierra no es hipotético: es el administrador que se cambia el rol para
    «probar cómo lo ve un asesor». Sin esta comprobación, la operación funciona, y a
    partir de ese momento no queda nadie con permiso para deshacerla — la única salida es
    editar la base de datos a mano.
    """
    if usuario.role != UserRole.SYSTEM_ADMIN.value or not usuario.is_active:
        return
    if _administradores_activos_restantes(db, usuario.id) == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"No se puede {accion}: es la única cuenta de administración activa y el "
                "sistema quedaría sin nadie capaz de gestionarlo. Cree o active otro "
                "administrador antes."
            ),
        )


def _no_sobre_uno_mismo(actor: CurrentUser, usuario: User, accion: str) -> None:
    if str(usuario.id) == str(actor.user_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"No puede {accion} su propia cuenta. Pídaselo a otro administrador: es "
                "lo que evita quedarse fuera del sistema por un descuido."
            ),
        )


# ==============================================================================
# Consulta
# ==============================================================================

@router.get("", response_model=ListaDeUsuarios)
def listar_usuarios(
    incluir_inactivos: bool = Query(False, description="Incluye también las cuentas dadas de baja."),
    rol: Optional[UserRole] = Query(None, description="Filtra por rol."),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles([UserRole.SYSTEM_ADMIN])),
):
    """Cuentas del sistema. Nunca incluye el hash de la contraseña."""
    consulta = db.query(User)
    if not incluir_inactivos:
        consulta = consulta.filter(User.is_active.is_(True))
    if rol is not None:
        consulta = consulta.filter(User.role == rol.value)

    total = consulta.count()
    filas = consulta.order_by(User.full_name.asc(), User.id.asc()).offset(offset).limit(limit).all()
    return ListaDeUsuarios(total=total, items=filas)


@router.get("/{user_id}", response_model=UsuarioResponse)
def obtener_usuario(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles([UserRole.SYSTEM_ADMIN])),
):
    return _buscar(db, user_id)


# ==============================================================================
# Alta y modificación
# ==============================================================================

@router.post("", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
def crear_usuario(
    datos: UsuarioCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles([UserRole.SYSTEM_ADMIN])),
    auditoria: AsientoDeAuditoria = Depends(auditar(ACCION_USUARIO_CREAR, ENTIDAD_USUARIO)),
):
    """Da de alta una cuenta. La contraseña pasa por la política antes de guardarse."""
    correo = datos.email.lower().strip()
    try:
        exigir(datos.password, email=correo, nombre=datos.full_name)
    except ContrasenaDebil as exc:
        raise _detalle_de_contrasena(exc) from None

    if db.query(User.id).filter(func.lower(User.email) == correo).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una cuenta con el correo '{correo}'.",
        )

    es_asesor = datos.is_sales_rep
    usuario = User(
        email=correo,
        full_name=datos.full_name,
        role=datos.role.value,
        hashed_password=hash_password(datos.password),
        is_active=True,
        is_sales_rep=es_asesor,
        phone=datos.phone,
        # Una capacidad en alguien que no atiende cartera sería un número que nadie usa.
        capacity=(datos.capacity or CAPACIDAD_POR_DEFECTO) if es_asesor else None,
        # El administrador que crea la cuenta conoce esta contraseña. Mientras la conozca
        # otra persona, la cuenta no identifica a nadie.
        must_change_password=True,
    )
    # Lo que se intenta escribir, antes del `commit`: después de un `rollback` los objetos de
    # la sesión caducan y leerlos devuelve lo que la base tiene, no lo que se intentó.
    valores = {columna.name: getattr(usuario, columna.name, None) for columna in User.__table__.columns}
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # La carrera del correo sigue contestándose con la frase que esta red tenía escrita,
        # y lo demás deja de contestarse con ella: `users` tiene una restricción única y
        # nueve columnas obligatorias, así que esta línea nombraba el correo también cuando
        # la base había rechazado otra cosa (punto 26 de §6.4).
        rechazo = integridad.motivo_del_rechazo(db, User, valores)
        if rechazo.clase == integridad.REPETIDO:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe una cuenta con el correo '{correo}'.",
            ) from exc
        codigo, detalle = integridad.respuesta(rechazo)
        raise HTTPException(status_code=codigo, detail=detalle) from exc
    db.refresh(usuario)

    auditoria.anotar(
        entidad_id=usuario.id,
        email=usuario.email,
        rol=usuario.role,
        es_asesor=usuario.is_sales_rep,
    )
    logger.info("Cuenta %s creada por %s", usuario.email, current_user.email)
    return usuario


@router.put("/{user_id}", response_model=UsuarioResponse)
def actualizar_usuario(
    user_id: int,
    cambios: UsuarioUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles([UserRole.SYSTEM_ADMIN])),
    auditoria: AsientoDeAuditoria = Depends(auditar(ACCION_USUARIO_ACTUALIZAR, ENTIDAD_USUARIO)),
):
    """
    Cambia atributos de una cuenta: nombre, rol, actividad, marca de asesor, capacidad.

    Un cambio de rol revoca las sesiones vivas. El rol viaja dentro del token ya emitido,
    así que sin revocar, quien acaba de perder permisos los conserva hasta que su token
    caduque: un usuario degradado seguiría administrando durante los siguientes quince
    minutos, que es tiempo de sobra.
    """
    usuario = _buscar(db, user_id)
    auditoria.anotar(entidad_id=user_id, email=usuario.email)

    datos = cambios.model_dump(exclude_unset=True)
    if not datos:
        return usuario

    rol_nuevo = datos.get("role")
    if rol_nuevo is not None:
        rol_nuevo = rol_nuevo.value if isinstance(rol_nuevo, UserRole) else str(rol_nuevo)

    baja = datos.get("is_active") is False
    degradacion = rol_nuevo is not None and rol_nuevo != usuario.role

    if baja or (degradacion and rol_nuevo != UserRole.SYSTEM_ADMIN.value):
        _exigir_que_quede_un_administrador(
            db, usuario, "desactivar" if baja else "cambiar el rol de esta cuenta"
        )
    if baja or degradacion:
        _no_sobre_uno_mismo(actor=current_user, usuario=usuario, accion="degradar ni desactivar")

    cambiados = []
    for campo in ("full_name", "is_active", "is_sales_rep", "phone", "capacity"):
        if campo in datos:
            setattr(usuario, campo, datos[campo])
            cambiados.append(campo)
    if rol_nuevo is not None:
        usuario.role = rol_nuevo
        cambiados.append("role")

    # Coherencia: quien deja de ser asesor no conserva una capacidad que ya no significa
    # nada, y quien pasa a serlo necesita una.
    if usuario.is_sales_rep and usuario.capacity is None:
        usuario.capacity = CAPACIDAD_POR_DEFECTO
    if not usuario.is_sales_rep:
        usuario.capacity = None

    sesiones = 0
    if degradacion or baja:
        motivo = MOTIVO_CUENTA_DESACTIVADA if baja else MOTIVO_ROL_CAMBIADO
        sesiones = cerrar_sesiones_del_usuario(db, usuario.id, motivo=motivo)
        usuario.token_version += 1

    db.commit()
    db.refresh(usuario)

    auditoria.anotar(campos=sorted(cambiados), sesiones_cerradas=sesiones)
    if degradacion:
        auditoria.anotar(rol_resultante=usuario.role)
    logger.info(
        "Cuenta %s modificada por %s (campos: %s)",
        usuario.email, current_user.email, ", ".join(sorted(cambiados)) or "ninguno",
    )
    return usuario


@router.post("/{user_id}/role", response_model=UsuarioResponse)
def cambiar_rol(
    user_id: int,
    rol: UserRole = Query(..., description="Rol que pasa a tener la cuenta."),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles([UserRole.SYSTEM_ADMIN])),
    auditoria: AsientoDeAuditoria = Depends(auditar(ACCION_USUARIO_CAMBIO_DE_ROL, ENTIDAD_USUARIO)),
):
    """
    Cambia el rol de una cuenta y cierra sus sesiones.

    Existe aparte de `PUT /users/{id}` para que un cambio de permisos tenga su propia
    entrada en la bitácora. Buscar «quién ha cambiado roles este mes» no debería obligar a
    abrir cada `usuario.actualizar` para ver si tocó ese campo.
    """
    usuario = _buscar(db, user_id)
    auditoria.anotar(entidad_id=user_id, email=usuario.email, rol_anterior=usuario.role, rol_nuevo=rol.value)

    if usuario.role == rol.value:
        return usuario

    if rol != UserRole.SYSTEM_ADMIN:
        _exigir_que_quede_un_administrador(db, usuario, "cambiar el rol de esta cuenta")
        _no_sobre_uno_mismo(actor=current_user, usuario=usuario, accion="degradar")

    usuario.role = rol.value
    sesiones = cerrar_sesiones_del_usuario(db, usuario.id, motivo=MOTIVO_ROL_CAMBIADO)
    usuario.token_version += 1
    db.commit()
    db.refresh(usuario)

    auditoria.anotar(sesiones_cerradas=sesiones)
    logger.info("Rol de %s cambiado a %s por %s", usuario.email, rol.value, current_user.email)
    return usuario


@router.delete("/{user_id}", response_model=UsuarioResponse)
def desactivar_usuario(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles([UserRole.SYSTEM_ADMIN])),
    auditoria: AsientoDeAuditoria = Depends(auditar(ACCION_USUARIO_DESACTIVAR, ENTIDAD_USUARIO)),
):
    """
    Baja lógica: la cuenta deja de entrar y de recibir prospectos, pero no se borra.

    Es un `DELETE` que no borra, y esa incoherencia aparente es la decisión. Borrar la fila
    dejaría sin sujeto los asientos de auditoría de esa persona —el registro de quién
    eliminó qué se convertiría en un identificador que ya no resuelve— y pondría a NULL el
    asesor de todos sus prospectos sin dejar constancia de a quién pertenecían.

    Sus prospectos **se conservan asignados a ella**. Reasignarlos automáticamente al
    desactivar la cuenta repartiría cartera sin que nadie lo decidiera; el líder comercial
    los ve y los reparte.
    """
    usuario = _buscar(db, user_id)
    auditoria.anotar(entidad_id=user_id, email=usuario.email, rol=usuario.role)

    _no_sobre_uno_mismo(actor=current_user, usuario=usuario, accion="desactivar")
    _exigir_que_quede_un_administrador(db, usuario, "desactivar")

    if not usuario.is_active:
        return usuario

    usuario.is_active = False
    sesiones = cerrar_sesiones_del_usuario(db, usuario.id, motivo=MOTIVO_CUENTA_DESACTIVADA)
    usuario.token_version += 1

    pendientes = (
        db.query(func.count(Lead.id)).filter(Lead.assigned_rep_id == usuario.id).scalar() or 0
    )
    db.commit()
    db.refresh(usuario)

    auditoria.anotar(sesiones_cerradas=sesiones, prospectos_que_atendia=pendientes)
    logger.info(
        "Cuenta %s desactivada por %s; conserva %s prospectos asignados",
        usuario.email, current_user.email, pendientes,
    )
    return usuario


@router.post("/{user_id}/activate", response_model=UsuarioResponse)
def reactivar_usuario(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles([UserRole.SYSTEM_ADMIN])),
    auditoria: AsientoDeAuditoria = Depends(auditar(ACCION_USUARIO_REACTIVAR, ENTIDAD_USUARIO)),
):
    """
    Reactiva una cuenta dada de baja.

    Vuelve con `must_change_password`: entre la baja y la reactivación pudo pasar
    cualquier cosa con esa credencial, y reactivar con la contraseña antigua intacta es
    justo la vía cómoda para reabrir el acceso de alguien que ya no debería tenerlo.
    """
    usuario = _buscar(db, user_id)
    auditoria.anotar(entidad_id=user_id, email=usuario.email)

    if usuario.is_active:
        return usuario

    usuario.is_active = True
    usuario.must_change_password = True
    db.commit()
    db.refresh(usuario)

    logger.info("Cuenta %s reactivada por %s", usuario.email, current_user.email)
    return usuario


@router.post("/{user_id}/reset-password", response_model=UsuarioResponse)
def restablecer_contrasena(
    user_id: int,
    datos: RestablecerContrasena,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles([UserRole.SYSTEM_ADMIN])),
    auditoria: AsientoDeAuditoria = Depends(
        auditar(ACCION_USUARIO_RESET_CONTRASENA, ENTIDAD_USUARIO)
    ),
):
    """
    Fija una contraseña nueva para otra persona.

    Tres efectos, y los tres son necesarios juntos: se aplica la política, se marca la
    cuenta para que la cambie en el primer uso y se revocan todas sus sesiones. Sin lo
    tercero, quien tuviera una sesión abierta con la credencial anterior seguiría dentro,
    y el restablecimiento —que suele hacerse justo porque se sospecha de esa credencial—
    no habría cerrado nada.

    La contraseña **no se devuelve** en la respuesta ni se escribe en la bitácora: el
    asiento registra que hubo un restablecimiento, no cuál fue el valor.
    """
    usuario = _buscar(db, user_id)
    auditoria.anotar(entidad_id=user_id, email=usuario.email)

    try:
        exigir(datos.nueva_contrasena, email=usuario.email, nombre=usuario.full_name)
    except ContrasenaDebil as exc:
        raise _detalle_de_contrasena(exc) from None

    usuario.hashed_password = hash_password(datos.nueva_contrasena)
    usuario.must_change_password = True
    usuario.password_changed_at = func.now()
    sesiones = cerrar_sesiones_del_usuario(db, usuario.id, motivo=MOTIVO_CONTRASENA_RESTABLECIDA)
    usuario.token_version += 1
    db.commit()
    db.refresh(usuario)

    auditoria.anotar(sesiones_cerradas=sesiones)
    logger.info("Contraseña de %s restablecida por %s", usuario.email, current_user.email)
    return usuario


# ==============================================================================
# Asesores comerciales
# ==============================================================================

asesores_router = APIRouter()


@asesores_router.get("", response_model=ListaDeAsesores)
def listar_asesores(
    incluir_inactivos: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles([UserRole.SALES_LEAD, UserRole.SYSTEM_ADMIN])
    ),
):
    """
    Equipo comercial con su carga real de trabajo.

    Ya no es una tabla aparte: un asesor es un usuario con `is_sales_rep`. El conteo de
    prospectos sale de **una sola consulta agregada**. La pantalla de administración lo
    pedía antes con una petición por asesor contra el listado de prospectos —una consulta
    por persona del equipo, cada una trayendo una página entera para leer un total—, y
    encima contra unos identificadores fijos escritos en el propio componente.

    El `LEFT JOIN` es deliberado: un asesor sin cartera debe salir con cero, no
    desaparecer del listado. Es precisamente a quien hay que ver para repartirle trabajo.
    """
    consulta = (
        db.query(User, func.count(Lead.id).label("asignados"))
        .outerjoin(Lead, Lead.assigned_rep_id == User.id)
        .filter(User.is_sales_rep.is_(True))
        .group_by(User.id)
        .order_by(User.full_name.asc())
    )
    if not incluir_inactivos:
        consulta = consulta.filter(User.is_active.is_(True))

    filas = consulta.all()
    items: List[AsesorResponse] = [
        AsesorResponse(
            **UsuarioResponse.model_validate(usuario).model_dump(),
            leads_asignados=int(asignados or 0),
        )
        for usuario, asignados in filas
    ]

    # Sin filtrar por `is_sales_rep`: quien dejó de atender cartera y luego fue dado de
    # baja puede conservar prospectos igual, y esos son los que menos se ven.
    en_cuentas_de_baja = (
        db.query(func.count(Lead.id))
        .join(User, Lead.assigned_rep_id == User.id)
        .filter(User.is_active.is_(False))
        .scalar()
        or 0
    )
    return ListaDeAsesores(
        total=len(items),
        items=items,
        prospectos_en_cuentas_de_baja=int(en_cuentas_de_baja),
    )


@asesores_router.post("/{user_id}/cartera", response_model=ResultadoDeReparto)
def repartir_cartera(
    user_id: int,
    datos: RepartoDeCartera,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles([UserRole.SALES_LEAD, UserRole.SYSTEM_ADMIN])
    ),
    auditoria: AsientoDeAuditoria = Depends(auditar(ACCION_CARTERA_REPARTIR, ENTIDAD_USUARIO)),
):
    """
    Traspasa todos los prospectos de una cuenta a otra que atienda cartera.

    Es la otra mitad de la baja. Desactivar una cuenta conserva sus prospectos a su nombre
    —repartirlos solos sería decidir sin nadie que decida—, pero después no había forma de
    repartirlos salvo editando prospecto a prospecto, y ningún aviso recordaba que estaban
    ahí (§15.8). Un prospecto caliente asignado a quien ya no entra no lo atiende nadie, y
    la autoasignación no lo rescata: solo reparte los que no tienen dueño.

    Lo hace también el líder comercial, no solo el administrador: repartir trabajo es una
    decisión comercial.
    """
    origen = _buscar(db, user_id)
    auditoria.anotar(entidad_id=user_id, email=origen.email, destino_id=datos.destino_id)

    if datos.destino_id == origen.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El destino es la misma cuenta: no hay nada que repartir.",
        )

    destino = db.query(User).filter(User.id == datos.destino_id).first()
    if destino is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La cuenta de destino no existe.",
        )
    if not destino.is_active or not destino.is_sales_rep:
        # A una cuenta de baja, el traspaso movería el problema en vez de resolverlo; a
        # quien no atiende cartera, dejaría los prospectos fuera de toda vista de asesor.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El destino tiene que ser una cuenta activa que atienda cartera.",
        )

    movidos = (
        db.query(Lead)
        .filter(Lead.assigned_rep_id == origen.id)
        .update({Lead.assigned_rep_id: destino.id}, synchronize_session=False)
    )
    db.commit()

    carga = (
        db.query(func.count(Lead.id)).filter(Lead.assigned_rep_id == destino.id).scalar() or 0
    )
    supera = bool(destino.capacity) and carga > destino.capacity

    auditoria.anotar(
        destino_email=destino.email,
        movidos=int(movidos),
        carga_del_destino=int(carga),
        supera_capacidad=supera,
    )
    logger.info(
        "%s traspasó %s prospectos de %s a %s",
        current_user.email, movidos, origen.email, destino.email,
    )
    return ResultadoDeReparto(
        origen_id=origen.id,
        destino_id=destino.id,
        movidos=int(movidos),
        carga_del_destino=int(carga),
        supera_capacidad=supera,
    )
