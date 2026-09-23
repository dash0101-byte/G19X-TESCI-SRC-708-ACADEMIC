import logging
from typing import Optional

from app.core.audit import (
    ACCION_ACCESO_FUERA_DE_ALCANCE,
    ACCION_LEAD_ACTIVIDAD,
    ACCION_LEAD_ACTUALIZAR,
    ACCION_LEAD_CREAR,
    ACCION_LEAD_ELIMINAR,
    ACCION_LEAD_EXPORTAR,
    ACCION_RECALCULO_MASIVO,
    ENTIDAD_LEAD,
    ENTIDAD_TRABAJO,
    AsientoDeAuditoria,
    auditar,
    registrar_evento,
)
from app.core.autorizacion import AlcanceDeCartera, FueraDeAlcance, alcance_actual
from app.core.database import get_db
from app.core.proxy import ip_del_cliente
from app.core.security import CurrentUser, UserRole, get_current_user, require_roles
from app.models.entities import LeadStatus, ScoreCategory, ScoringJob, utc_now
from app.repositories.lead_repository import LeadEmailAlreadyExists, LeadRepository
from app.schemas.activity import ActividadRegistradaResponse, ActivityCreate
from app.schemas.job import RecalculationJobRequest, RecalculationJobStatus
from app.schemas.lead import (
    LeadCreate,
    LeadDetailResponse,
    LeadListFilter,
    LeadListResponse,
    LeadResponse,
    LeadUpdate,
)
from app.schemas.score import ScoreResult
from app.services import informe_de_publicaciones, registro_de_actividad
from app.services.derechos_del_titular import (
    exportar_prospecto,
    huella_del_titular,
    suprimir_prospecto,
)
from app.services.recalculation_service import (
    RecalculoEnCurso,
    crear_trabajo_de_recalculo,
    ejecutar_recalculo,
)
from app.services.scoring_service import ScoringService
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter()


def _no_encontrado(lead_id: int) -> HTTPException:
    """
    Un prospecto que no es suyo responde exactamente igual que uno que no existe.

    La alternativa —403 cuando existe pero es ajeno, 404 cuando no existe— convierte el
    endpoint en un oráculo: recorrer identificadores devuelve el mapa de la cartera
    completa (cuántos prospectos hay, qué identificadores están ocupados) sin ver un solo
    dato. La distinción sí se conserva, pero en la bitácora, que es donde sirve.
    """
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Prospecto con ID {lead_id} no encontrado.",
    )


def _anotar_tanteo(
    request: Request,
    db: Session,
    repo: LeadRepository,
    current_user: CurrentUser,
    lead_id: int,
) -> None:
    """
    Deja constancia de que se pidió un prospecto real que pertenece a otra persona.

    Se escribe aquí y no en una dependencia porque la petición no falla por permisos —el
    rol es correcto y el endpoint se ejecuta—; lo que no encaja es el objeto, y eso solo
    se sabe después de consultarlo. Un 404 suelto es un enlace viejo; una tanda seguida de
    la misma cuenta es alguien recorriendo identificadores.
    """
    if not repo.existe_fuera_del_alcance(lead_id):
        return
    registrar_evento(
        db,
        accion=ACCION_ACCESO_FUERA_DE_ALCANCE,
        entidad=ENTIDAD_LEAD,
        entidad_id=str(lead_id),
        resultado="HTTP_404",
        actor_id=current_user.user_id,
        actor_email=current_user.email,
        actor_role=current_user.role.value,
        ip=ip_del_cliente(request),
        user_agent=request.headers.get("user-agent"),
        metadatos={"ruta": request.url.path},
    )


@router.get("", response_model=LeadListResponse)
def get_leads(
    score_category: Optional[ScoreCategory] = None,
    status_filter: Optional[LeadStatus] = Query(None, alias="status"),
    industry: Optional[str] = None,
    search: Optional[str] = None,
    assigned_rep_id: Optional[int] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    alcance: AlcanceDeCartera = Depends(alcance_actual),
):
    """
    Lista y filtra prospectos comerciales con paginación y ordenamiento por score.

    `total` cuenta lo que ve **quien pregunta**, no lo que hay en la tabla. Devolver el
    total global junto a una página filtrada habría delatado el tamaño de la cartera ajena
    en el mismo cuerpo de la respuesta, que es la forma más discreta de no arreglar nada.

    Un asesor comercial ve solo los prospectos que tiene asignados; un líder comercial y un
    administrador, la cartera completa. El filtro no está aquí sino en el repositorio: si
    estuviera aquí, el siguiente endpoint que consulte prospectos nacería sin él.
    """
    repo = LeadRepository(db, alcance)
    filters = LeadListFilter(
        score_category=score_category,
        status=status_filter,
        industry=industry,
        search=search,
        assigned_rep_id=assigned_rep_id,
        min_score=min_score,
        max_score=max_score,
        limit=limit,
        offset=offset,
    )
    leads, total = repo.list_leads(filters)
    return LeadListResponse(items=leads, total=total, limit=limit, offset=offset)


@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    lead_in: LeadCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    alcance: AlcanceDeCartera = Depends(alcance_actual),
    auditoria: AsientoDeAuditoria = Depends(auditar(ACCION_LEAD_CREAR, ENTIDAD_LEAD)),
):
    """
    Crea un prospecto y ejecuta el pipeline de scoring y explicabilidad.

    Cualquier rol registrado puede crear. Lo que cambia según el rol es el dueño: un asesor
    comercial crea prospectos **suyos** y no puede asignárselos a otra persona. Sin esa
    regla, un asesor que creara un prospecto sin dueño lo perdería de vista en el mismo
    instante, porque quedaría fuera de su propio alcance.
    """
    repo = LeadRepository(db, alcance)
    # Comprobación deliberadamente NO acotada: `leads.email` es único en toda la tabla, así
    # que mirar solo dentro de la cartera propia dejaría pasar un duplicado ajeno hasta el
    # INSERT y lo convertiría en un 500. Devuelve un booleano; nunca la ficha del otro.
    if repo.email_ya_registrado(lead_in.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un prospecto registrado con el email '{lead_in.email}'.",
        )

    # La actividad inicial se valida ANTES de dar de alta la ficha: un tipo que el registro
    # rechaza —una propuesta, que se registra cambiando la etapa, o una llamada sin su
    # resultado— no puede dejar un prospecto creado sin la actividad con la que llegó.
    inicial = None
    if lead_in.initial_activity_type:
        inicial = registro_de_actividad.Evento(
            fuente="manual",
            tipo=lead_in.initial_activity_type,
            notas=lead_in.initial_notes,
        )
        try:
            registro_de_actividad.validar_evento(inicial)
        except registro_de_actividad.EventoInvalido as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.como_detalle()
            ) from exc

    try:
        lead = repo.create(lead_in)
    except FueraDeAlcance as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "No puede asignar un prospecto a otra persona. Repartir cartera es una "
                "decisión del líder comercial."
            ),
        ) from exc

    if lead_in.privacy_notice_accepted:
        lead.privacy_notice_accepted_at = utc_now()
        lead.privacy_notice_source = "manual"
        db.commit()

    # La actividad inicial pasa por el mismo registro que cualquier otra, y ese registro
    # recalcula el score. Sin actividad inicial, se puntúa aquí.
    scoring_svc = ScoringService(db)
    if inicial is not None:
        await registro_de_actividad.registrar_evento(db, inicial, lead=lead, scoring=scoring_svc)
    else:
        await scoring_svc.calculate_and_persist_score(lead, generate_ai_text=True)

    logger.info(f"Prospecto {lead.id} creado por {current_user.email} (rol: {current_user.role.value})")
    db.refresh(lead)
    auditoria.anotar(entidad_id=lead.id, email=lead.email, empresa=lead.company, origen=lead.source)
    return lead


@router.get("/{lead_id}", response_model=LeadDetailResponse)
def get_lead_by_id(
    request: Request,
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    alcance: AlcanceDeCartera = Depends(alcance_actual),
):
    """
    Ficha 360 del prospecto: actividades, historial de scores y explicabilidad.

    Un prospecto ajeno responde 404, igual que uno inexistente. La diferencia queda en la
    bitácora, no en la respuesta.
    """
    repo = LeadRepository(db, alcance)
    lead = repo.get_by_id(lead_id)
    if not lead:
        _anotar_tanteo(request, db, repo, current_user, lead_id)
        raise _no_encontrado(lead_id)

    latest_explanation = None
    if lead.score_histories:
        latest_explanation = lead.score_histories[0].ai_explanation

    response_data = LeadDetailResponse.model_validate(lead)
    response_data.latest_explanation = latest_explanation
    response_data.llego_por = informe_de_publicaciones.llego_por(db, lead)
    return response_data


@router.put("/{lead_id}", response_model=LeadDetailResponse)
async def update_lead(
    request: Request,
    lead_id: int,
    lead_in: LeadUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    alcance: AlcanceDeCartera = Depends(alcance_actual),
    auditoria: AsientoDeAuditoria = Depends(auditar(ACCION_LEAD_ACTUALIZAR, ENTIDAD_LEAD)),
):
    """
    Actualiza los atributos del prospecto y recalcula su score.

    El permiso ya no lo da el rol sino la propiedad del objeto: **un asesor comercial
    edita los prospectos que atiende**. Antes no podía editar ninguno, ni siquiera los
    suyos, lo que empujaba a pedirle cada cambio de teléfono al líder comercial —o a
    repartir el rol de líder para que la aplicación fuera usable, que es como una
    restricción demasiado gruesa acaba produciendo permisos de más—.

    Lo que sigue reservado a quien dirige la cartera es **reasignar**: cambiar el dueño de
    un prospecto es repartir trabajo, no atenderlo.
    """
    auditoria.anotar(entidad_id=lead_id)
    repo = LeadRepository(db, alcance)
    lead = repo.get_by_id(lead_id, include_relations=True)
    if not lead:
        _anotar_tanteo(request, db, repo, current_user, lead_id)
        raise _no_encontrado(lead_id)
    # Solo los campos que el cliente envió, no el objeto entero: la bitácora dice qué se
    # tocó, no vuelve a guardar el prospecto. Los valores no se copian —un cambio de
    # teléfono o de correo acabaría duplicado en una tabla que se consulta con otro
    # criterio de acceso que la de negocio—.
    auditoria.anotar(campos=sorted(lead_in.model_dump(exclude_unset=True).keys()))
    etapa_anterior = lead.status
    try:
        updated_lead = repo.update(lead, lead_in)
    except LeadEmailAlreadyExists as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except FueraDeAlcance as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "No puede cambiar el asesor asignado. Reasignar cartera es una decisión "
                "del líder comercial."
            ),
        ) from exc

    logger.info(f"Prospecto {lead_id} actualizado por {current_user.email} (rol: {current_user.role.value})")

    # Pasar a «Propuesta enviada» o «Reunión agendada» registra la actividad por sí mismo:
    # el asesor ya no la declara aparte. Ese registro recalcula el score; si la etapa no
    # registra nada, se recalcula aquí con los nuevos atributos.
    scoring_svc = ScoringService(db)
    registro = await registro_de_actividad.registrar_cambio_de_etapa(
        db, updated_lead, etapa_anterior, scoring=scoring_svc
    )
    if registro is None:
        await scoring_svc.calculate_and_persist_score(updated_lead, generate_ai_text=True)
    else:
        auditoria.anotar(actividad_del_pipeline=registro.actividad.id)

    # Recargar prospecto con relaciones actualizadas
    fresh_lead = repo.get_by_id(lead_id, include_relations=True)
    latest_explanation = None
    if fresh_lead and fresh_lead.score_histories:
        latest_explanation = fresh_lead.score_histories[0].ai_explanation

    response_data = LeadDetailResponse.model_validate(fresh_lead)
    response_data.latest_explanation = latest_explanation
    response_data.llego_por = informe_de_publicaciones.llego_por(db, fresh_lead)
    return response_data



@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles([UserRole.SYSTEM_ADMIN, UserRole.SALES_LEAD])),
    alcance: AlcanceDeCartera = Depends(alcance_actual),
    auditoria: AsientoDeAuditoria = Depends(auditar(ACCION_LEAD_ELIMINAR, ENTIDAD_LEAD)),
):
    """
    Suprime un prospecto: la persona y todo lo que el sistema guarda de ella (R-11).

    Sigue requiriendo Sales_Lead o System_Admin, y es una asimetría deliberada frente a la
    edición: un asesor edita lo suyo pero no lo borra. Editar es reversible y queda en el
    historial de scores; suprimir no se recupera.

    Hasta la Fase 14 el borrado seguía las cascadas del ORM y dejaba atrás las entregas de
    webhook, los registros de ingesta revertida sin `lead_id` y el correo de la persona
    dentro de la bitácora. Ahora recorre el mapa de `derechos_del_titular`, que la suite
    contrasta con las claves foráneas del esquema.

    El asiento de este borrado ya no guarda el correo, y es un cambio de criterio respecto
    al capítulo 14, que lo anotaba para que el asiento no fuera «solo un número». Guardar el
    correo de quien pidió ser borrado era no borrarlo. El asiento guarda en su lugar cuántas
    filas salieron de cada tabla y una huella con clave del correo, que permite comprobar
    si una persona concreta fue suprimida sin que la bitácora se lo diga a quien no la
    conoce.
    """
    auditoria.anotar(entidad_id=lead_id)
    repo = LeadRepository(db, alcance)

    condenado = repo.get_by_id(lead_id, include_relations=False)
    if condenado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prospecto con ID {lead_id} no encontrado.",
        )

    huella = huella_del_titular(condenado.email)
    score = condenado.current_score
    recuento = suprimir_prospecto(db, condenado)
    auditoria.anotar(huella_del_titular=huella, score=score, supresion=recuento)
    return None


@router.get("/{lead_id}/exportar")
def exportar_datos_del_prospecto(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles([UserRole.SYSTEM_ADMIN, UserRole.SALES_LEAD])),
    alcance: AlcanceDeCartera = Depends(alcance_actual),
    auditoria: AsientoDeAuditoria = Depends(auditar(ACCION_LEAD_EXPORTAR, ENTIDAD_LEAD)),
):
    """
    Todo lo que el sistema sabe de esta persona, en un único documento JSON (R-11).

    Datos del prospecto, actividades, cada puntuación con su vector de variables y su
    explicación, los resúmenes mensuales, las integraciones con el CRM —también las que
    no llegaron a vincularse—, qué se hizo con sus datos y cuándo, cuánto tiempo se
    conservan y qué copias existen fuera de la base.

    Mismos roles que la supresión: la petición la tramita quien dirige la cartera, no el
    asesor que atiende a la persona. Se descarga como adjunto y sin caché, porque lo que
    lleva dentro es exactamente lo que no debe quedarse en un proxy intermedio.
    """
    auditoria.anotar(entidad_id=lead_id)
    repo = LeadRepository(db, alcance)
    lead = repo.get_by_id(lead_id, include_relations=False)
    if lead is None:
        raise _no_encontrado(lead_id)

    documento = exportar_prospecto(db, lead)
    # En el asiento, cuántos registros se entregaron de cada sección; nunca su contenido.
    auditoria.anotar(
        secciones={clave: len(valor) for clave, valor in documento.items() if isinstance(valor, list)}
    )
    return JSONResponse(
        content=documento,
        headers={
            "Content-Disposition": f'attachment; filename="prospecto-{lead_id}.json"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/{lead_id}/activities", response_model=ActividadRegistradaResponse, status_code=status.HTTP_201_CREATED)
async def add_lead_activity(
    request: Request,
    lead_id: int,
    activity_in: ActivityCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    alcance: AlcanceDeCartera = Depends(alcance_actual),
    auditoria: AsientoDeAuditoria = Depends(auditar(ACCION_LEAD_ACTIVIDAD, ENTIDAD_LEAD)),
):
    """
    Registra una interacción y recalcula el score del prospecto.

    Cualquier rol puede registrar actividades, pero solo sobre prospectos que alcanza. Una
    actividad sube el score y puede disparar la reasignación automática de un prospecto
    caliente: escribir sobre cartera ajena no es solo leerla, es moverla.

    Pasa por `registrar_evento`, como el webhook del CRM y los conectores. La respuesta trae
    el score de antes y el de después: el cambio real, no una promesa de puntos.
    """
    repo = LeadRepository(db, alcance)
    lead = repo.get_by_id(lead_id)
    if not lead:
        _anotar_tanteo(request, db, repo, current_user, lead_id)
        raise _no_encontrado(lead_id)

    evento = registro_de_actividad.Evento(
        fuente="manual",
        tipo=activity_in.activity_type,
        ocurrido_en=activity_in.occurred_at,
        direccion=activity_in.direction,
        resultado_de_llamada=activity_in.call_outcome,
        canal=activity_in.channel,
        notas=activity_in.notes,
        # Con el mismo nombre que manda Calendly: el recordatorio de la víspera lee un solo
        # dato, venga de una integración o del asesor.
        datos=(
            {"inicio_de_la_reunion": activity_in.inicio_de_la_reunion.isoformat()}
            if activity_in.inicio_de_la_reunion is not None
            else {}
        ),
    )
    try:
        resultado = await registro_de_actividad.registrar_evento(db, evento, lead=lead)
    except registro_de_actividad.EventoInvalido as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.como_detalle()
        ) from exc

    actividad = resultado.actividad
    logger.info(
        "Actividad %s en lead %s registrada por %s",
        actividad.activity_type.value, lead_id, current_user.email,
    )
    auditoria.anotar(
        entidad_id=lead_id,
        tipo_de_actividad=actividad.activity_type.value,
        actividad_id=actividad.id,
    )
    return ActividadRegistradaResponse.desde_registro(resultado)


@router.post("/{lead_id}/recalculate-score", response_model=ScoreResult)
async def recalculate_lead_score(
    request: Request,
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    alcance: AlcanceDeCartera = Depends(alcance_actual),
):
    """
    Recalcula bajo demanda el score del prospecto con el decaimiento temporal actual.

    Acotado como el resto: el resultado incluye el desglose del score y la explicación
    generada, que es la ficha comercial del prospecto contada de otra manera.
    """
    repo = LeadRepository(db, alcance)
    lead = repo.get_by_id(lead_id)
    if not lead:
        _anotar_tanteo(request, db, repo, current_user, lead_id)
        raise _no_encontrado(lead_id)

    scoring_svc = ScoringService(db)
    score_result = await scoring_svc.calculate_and_persist_score(lead, generate_ai_text=True)
    return score_result


@router.post(
    "/batch/recalculate-all",
    response_model=RecalculationJobStatus,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "Ya hay un recálculo masivo en curso; se devuelve cuál."
        }
    },
)
async def recalculate_all_scores(
    background_tasks: BackgroundTasks,
    # Opcional y no una instancia por defecto compartida: ese objeto se crearía una sola
    # vez al importar el módulo y viviría entre peticiones.
    payload: Optional[RecalculationJobRequest] = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles([UserRole.SYSTEM_ADMIN, UserRole.SALES_LEAD])),
    auditoria: AsientoDeAuditoria = Depends(auditar(ACCION_RECALCULO_MASIVO, ENTIDAD_TRABAJO)),
):
    """
    Encola el recálculo de todos los prospectos y responde 202 con el identificador.

    Antes el recorrido entero ocurría dentro de la petición: el cliente esperaba con la
    conexión abierta mientras se ejecutaba una inferencia por prospecto, y con unos pocos
    miles el tiempo se iba por encima de lo que aguantan el navegador y el `proxy_read_timeout`
    de nginx (60 s). Al cortarse, el trabajo quedaba a medias sin dejar rastro de por dónde.

    Ahora la respuesta es inmediata y el avance se consulta en
    `GET /leads/batch/jobs/{job_id}`. Requiere rol Sales_Lead o System_Admin.

    **Uno a la vez.** Dos recorridos simultáneos sobre la misma tabla no son «el doble de
    rápido»: recalculan los mismos prospectos, se pisan al escribir y multiplican la carga
    de inferencia justo cuando la base ya está ocupada. Si el turno está tomado se
    responde 409 diciendo cuál lo tiene y por dónde va, para que quien lo pidió sepa si
    esperar o si lo que hay atascado es un trabajo muerto.
    """
    parametros = payload or RecalculationJobRequest()
    try:
        trabajo = crear_trabajo_de_recalculo(
            db,
            solicitado_por=current_user.email,
            batch_size=parametros.batch_size,
        )
    except RecalculoEnCurso as conflicto:
        # No se anota en la bitácora: no es un intento de saltarse nada, es el segundo clic
        # de alguien autorizado. Lo que sí queda es el trabajo que ya estaba, que es donde
        # hay que mirar.
        en_curso = conflicto.trabajo
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "mensaje": (
                    "Ya hay un recálculo masivo en curso. Espere a que termine o "
                    "consulte su avance antes de lanzar otro."
                ),
                "job_id": en_curso.id,
                "estado": en_curso.status,
                "procesados": en_curso.processed_leads,
                "total": en_curso.total_leads,
                "solicitado_por": en_curso.requested_by,
            },
        ) from conflicto

    # La tarea recibe solo el identificador, no la sesión ni los objetos: para cuando se
    # ejecute, FastAPI ya habrá cerrado la sesión de esta petición.
    background_tasks.add_task(ejecutar_recalculo, trabajo.id)

    logger.info(
        f"Recálculo masivo {trabajo.id} encolado por {current_user.email} "
        f"({trabajo.total_leads} prospectos, lotes de {trabajo.batch_size})"
    )
    auditoria.anotar(
        entidad_id=trabajo.id,
        prospectos=trabajo.total_leads,
        tamano_de_lote=trabajo.batch_size,
    )
    return trabajo


@router.get("/batch/jobs/{job_id}", response_model=RecalculationJobStatus)
def get_recalculation_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles([UserRole.SYSTEM_ADMIN, UserRole.SALES_LEAD])),
):
    """
    Devuelve el estado y el avance de un recálculo masivo.

    El estado se lee de la base y no de la memoria del proceso, así que responde igual lo
    atienda el worker que lanzó el trabajo o cualquier otro.
    """
    trabajo = db.query(ScoringJob).filter(ScoringJob.id == job_id).first()
    if trabajo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trabajo de recálculo '{job_id}' no encontrado.",
        )
    return trabajo
