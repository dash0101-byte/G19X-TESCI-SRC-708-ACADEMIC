"""
Qué dio cada publicación, y de qué publicación vino cada ficha.

Quién entra en el informe de una publicación
--------------------------------------------
Dos caminos llevan a la misma publicación y los dos cuentan:

* la ficha está **atribuida** a la campaña (`leads.campaign_id`), que es lo que hace el
  registro al crearla desde la página de interés y lo que ya usaba el informe de
  rendimiento por campaña;
* la persona **envió su perfil** por el enlace de esa publicación, aunque su ficha ya
  existiera y estuviera atribuida a otra.

El segundo camino no es un adorno. `campaign_id` se fija al **crear** la ficha y no se
vuelve a tocar —pisarlo reescribiría la atribución del primer post con la del último—, así
que quien responde a tres publicaciones seguiría contando solo en la primera. Con las
solicitudes, cada publicación ve a quien le respondió, y la ficha enseña las tres.

Las solicitudes se reconocen por el prefijo del identificador externo de la actividad
(`<slug>:<uuid>`), que es como lo escribe `pagina_de_interes.construir_evento`. Se busca por
prefijo y no por el JSON `activity_data` porque el JSON se consulta de forma distinta en
cada motor y esto tiene que dar lo mismo en PostgreSQL y en el SQLite de las pruebas.

Qué es «avanzar de etapa»
-------------------------
Salir de `NEW`. Una ficha que se perdió (`LOST`) o que se descartó (`UNQUALIFIED`) también
avanzó: alguien la trabajó y el resultado se conoce. Contar solo las que siguen vivas
convertiría el número en una medida de la cartera actual y no de lo que trajo el post, que
es lo que se compara aquí.

Alcance
-------
El mismo criterio que en el resto del sistema, y por la misma razón: un total y una media
describen la cartera ajena sin abrir una ficha. Un asesor ve los suyos y **un número** con
el resto; el líder y el administrador, todo.
"""
import datetime
import logging
from typing import Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import case, false, func, or_
from sqlalchemy.orm import Session

from app.core.autorizacion import AlcanceDeCartera
from app.core.publicaciones import CANAL_LINKEDIN, base_publica, enlace_publico
from app.core.redes import CANALES_DE_PUBLICACION, ORDEN, REDES, SIN_RED, redes_de
from app.core.redes import etiqueta_de as etiqueta_de_red
from app.models.entities import Campaign, Lead, LeadActivity, LeadStatus, User, VisitaDePublicacion
from app.schemas.interes import NECESIDADES
from app.schemas.publicaciones import (
    ComparativaDePublicaciones,
    DiaDelInforme,
    FilaDeComparativa,
    FilaDelInforme,
    FilaDeRed,
    InformeDePublicacion,
    LlegoPor,
    PublicacionDelInforme,
    ResumenDePublicacion,
    SolicitudDeLaFicha,
)
from app.services import ciclo_de_publicaciones as ciclo
from app.services.pagina_de_interes import FUENTE

logger = logging.getLogger(__name__)

# La etapa con la que nace una ficha. Salir de aquí es «avanzar».
ETAPA_INICIAL = LeadStatus.NEW

NO_ES_UNA_PUBLICACION = "No existe la publicación solicitada."

# El gráfico de perfiles por día enseña como mucho tantos días, los últimos del periodo.
# Una barra por día en tres meses todavía se lee; en un año, no.
MAX_DIAS_DEL_GRAFICO = 90


def _avanzo():
    """Expresión SQL: 1 si la ficha salió de la etapa inicial, 0 si no."""
    return case((Lead.status != ETAPA_INICIAL, 1), else_=0)


def _redondear(valor) -> float:
    return round(float(valor or 0.0), 1)


# --------------------------------------------------------------------------- publicación
def buscar_publicacion(db: Session, campaign_id: int) -> Campaign:
    """
    La campaña, si es una publicación.

    Una campaña de otro canal responde 404 y no 403: hacia fuera, lo que no es una
    publicación no existe como tal. Una publicación **desactivada** sí se consulta, a
    diferencia de la página pública: se desactiva para dejar de recibir perfiles, no para
    borrar lo que trajo, y su informe es justo lo que se mira cuando la campaña terminó.
    """
    ciclo.cerrar_vencidas(db)
    publicacion = (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id, Campaign.channel == CANAL_LINKEDIN)
        .first()
    )
    if publicacion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NO_ES_UNA_PUBLICACION)
    return publicacion


def _descripcion(publicacion: Campaign) -> PublicacionDelInforme:
    return PublicacionDelInforme(
        id=publicacion.id,
        titulo=publicacion.name,
        enlace=enlace_publico(publicacion.public_slug),
        activa=bool(publicacion.is_active),
        estado=publicacion.estado,
        url_del_post=publicacion.url_del_post,
        responsable=publicacion.responsable.full_name if publicacion.responsable else None,
    )


def etiqueta_de_necesidad(datos: dict) -> Optional[str]:
    """
    La necesidad tal como la vio la persona. Desde el capítulo 26 la actividad guarda la
    etiqueta con la clave, porque cada publicación tiene sus opciones y pueden cambiar
    después; las anteriores solo tienen la clave, y sus opciones eran las de siempre.
    """
    etiqueta = datos.get("necesidad_etiqueta")
    if etiqueta:
        return str(etiqueta)
    return NECESIDADES.get(datos.get("necesidad"))


# ------------------------------------------------------------------ tarjeta «Llegó por»
def _solicitudes_del_prospecto(db: Session, lead_id: int) -> List[LeadActivity]:
    return (
        db.query(LeadActivity)
        .filter(LeadActivity.lead_id == lead_id, LeadActivity.source == FUENTE)
        .order_by(LeadActivity.occurred_at.desc(), LeadActivity.id.desc())
        .all()
    )


def slug_de(actividad: LeadActivity) -> Optional[str]:
    """
    De qué publicación es esta solicitud.

    Pública desde el capítulo 30: el panel de desenlaces atribuye cada cierre a la
    publicación por la que llegó esa persona, y necesita **este** criterio y no una copia
    suya. Dos formas de leer el slug —una que mira los datos y otra que solo mira el
    identificador externo— darían dos atribuciones distintas para las fichas antiguas.
    """
    datos = actividad.activity_data or {}
    slug = datos.get("publicacion")
    if slug:
        return str(slug)
    # Fichas anteriores a que la actividad guardara el slug en sus datos: el identificador
    # externo lo lleva delante desde el primer día (`<slug>:<uuid>`).
    if actividad.external_event_id and ":" in actividad.external_event_id:
        return actividad.external_event_id.split(":", 1)[0]
    return None


def llego_por(db: Session, lead: Lead) -> Optional[LlegoPor]:
    """
    La tarjeta de la ficha 360, o `None` si esta persona no llegó por una publicación.

    Devolver `None` y no una tarjeta vacía es la diferencia entre «no vino de ahí» y «vino
    de ahí y no sabemos de cuál», que no es lo mismo para quien va a llamar.
    """
    actividades = _solicitudes_del_prospecto(db, lead.id)
    if not actividades:
        return None

    slugs = {slug for slug in (slug_de(a) for a in actividades) if slug}
    campanas: Dict[str, Campaign] = {}
    if slugs:
        campanas = {
            c.public_slug: c
            for c in db.query(Campaign).filter(Campaign.public_slug.in_(slugs)).all()
        }

    solicitudes = []
    for actividad in actividades:
        datos = actividad.activity_data or {}
        campana = campanas.get(slug_de(actividad) or "")
        solicitudes.append(
            SolicitudDeLaFicha(
                publicacion_id=campana.id if campana else None,
                titulo=campana.name if campana else None,
                enlace=enlace_publico(campana.public_slug) if campana else None,
                recibida_en=actividad.occurred_at,
                necesidad=etiqueta_de_necesidad(datos),
                # Por dónde llegó: «Llegó por la publicación X, vía WhatsApp». Se enseña la
                # etiqueta guardada con el envío, no la que tenga hoy la clave, por lo mismo
                # que la necesidad: lo que pasó no cambia porque cambie una lista.
                red=str(datos.get("red_etiqueta") or etiqueta_de_red(datos.get("red"))),
                # El aviso se acepta en cada envío y se guarda con él. Las solicitudes
                # anteriores a que se anotara caen en su propia fecha, que es cuándo se
                # envió el formulario: sin aceptar el aviso no había envío.
                aviso_aceptado_en=_fecha_del_aviso(datos, actividad),
            )
        )

    metadatos = lead.raw_metadata or {}
    return LlegoPor(
        perfil_de_linkedin=metadatos.get("perfil_de_linkedin"),
        solicitudes=solicitudes,
    )


def _fecha_del_aviso(datos: dict, actividad: LeadActivity) -> Optional[datetime.datetime]:
    marca = datos.get("aviso_aceptado_en")
    if not marca:
        return actividad.occurred_at
    try:
        return datetime.datetime.fromisoformat(str(marca))
    except ValueError:
        logger.warning(
            "Actividad %s con un aviso de privacidad ilegible; se usa su fecha de envío.",
            actividad.id,
        )
        return actividad.occurred_at


# ---------------------------------------------------------------------------- el informe
def _recibidas_por(db: Session, slug: str):
    """
    Subconsulta: por cada ficha que envió su perfil a esta publicación, cuándo lo hizo la
    primera vez. `startswith(autoescape=True)` porque el slug lleva `_` y `-`, y un `_`
    sin escapar en un LIKE comodinea un carácter cualquiera.
    """
    return (
        db.query(
            LeadActivity.lead_id.label("lead_id"),
            func.min(LeadActivity.occurred_at).label("recibida_en"),
        )
        .filter(
            LeadActivity.source == FUENTE,
            LeadActivity.external_event_id.startswith(f"{slug}:", autoescape=True),
        )
        .group_by(LeadActivity.lead_id)
        .subquery()
    )


def _limites_del_dia(
    desde: Optional[datetime.date], hasta: Optional[datetime.date]
) -> Tuple[Optional[datetime.datetime], Optional[datetime.datetime]]:
    """De días a instantes: `hasta` incluye el día entero, no su medianoche."""
    inicio = (
        datetime.datetime.combine(desde, datetime.time.min, tzinfo=datetime.timezone.utc)
        if desde
        else None
    )
    fin = (
        datetime.datetime.combine(hasta, datetime.time.min, tzinfo=datetime.timezone.utc)
        + datetime.timedelta(days=1)
        if hasta
        else None
    )
    return inicio, fin


def informe(
    db: Session,
    alcance: AlcanceDeCartera,
    publicacion: Campaign,
    *,
    etapa: Optional[LeadStatus] = None,
    desde: Optional[datetime.date] = None,
    hasta: Optional[datetime.date] = None,
    limit: int = 50,
    offset: int = 0,
) -> InformeDePublicacion:
    """Perfiles de una publicación, ordenados por score y acotados a quien pregunta."""
    recibidas = _recibidas_por(db, publicacion.public_slug)
    # La fecha del informe: cuándo llegó el perfil. Las fichas atribuidas a la campaña que
    # no pasaron por la página no tienen solicitud, y para ellas la fecha es la del alta.
    fecha = func.coalesce(recibidas.c.recibida_en, Lead.created_at)

    base = (
        db.query(Lead, fecha.label("recibida_en"), User.full_name.label("asesor"))
        .outerjoin(recibidas, recibidas.c.lead_id == Lead.id)
        .outerjoin(User, User.id == Lead.assigned_rep_id)
        .filter(or_(Lead.campaign_id == publicacion.id, recibidas.c.lead_id.isnot(None)))
    )

    if etapa is not None:
        base = base.filter(Lead.status == etapa)
    inicio, fin = _limites_del_dia(desde, hasta)
    if inicio is not None:
        base = base.filter(fecha >= inicio)
    if fin is not None:
        base = base.filter(fecha < fin)

    propios, ajenos = _condiciones_de_alcance(alcance)
    visibles = base if propios is None else base.filter(propios)

    total, avanzaron, media = visibles.with_entities(
        func.count(Lead.id), func.sum(_avanzo()), func.avg(Lead.current_score)
    ).one()
    de_otros = 0 if ajenos is None else (base.filter(ajenos).with_entities(func.count(Lead.id)).scalar() or 0)

    filas = (
        visibles.order_by(Lead.current_score.desc(), Lead.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    necesidades = _necesidades(db, publicacion.public_slug, [lead.id for lead, _, _ in filas])

    fechas_visibles = [f for (f,) in visibles.with_entities(fecha).all()]
    visitas_por_dia = _visitas_por_dia(db, publicacion.id, desde, hasta)
    visitas = sum(visitas_por_dia.values())
    primer_dia = _primer_dia_contado(db, publicacion.id)
    envios = _envios(db, publicacion.public_slug, inicio, fin, desde_el_dia=primer_dia)
    por_dia, recortado = _serie(fechas_visibles, visitas_por_dia, desde, hasta)
    scores_visibles = {
        lead_id: float(score or 0.0)
        for lead_id, score in visibles.with_entities(Lead.id, Lead.current_score).all()
    }
    por_red = _por_red(db, publicacion, scores_visibles, desde, hasta, inicio, fin, primer_dia)

    return InformeDePublicacion(
        publicacion=_descripcion(publicacion),
        resumen=ResumenDePublicacion(
            perfiles_recibidos=int(total or 0),
            avanzaron_de_etapa=int(avanzaron or 0),
            score_medio=_redondear(media),
            de_otros_asesores=int(de_otros),
            alcance_completo=alcance.toda_la_cartera,
            visitas=visitas,
            envios=envios,
            tasa_de_envio=tasa(envios, visitas),
        ),
        por_dia=por_dia,
        grafico_recortado=recortado,
        por_red=por_red,
        filas=[
            _fila(lead, recibida_en, asesor, necesidades.get(lead.id))
            for lead, recibida_en, asesor in filas
        ],
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )


def tasa(envios: int, visitas: int) -> Optional[float]:
    """Envíos entre visitas, en tanto por ciento. Sin visitas no hay tasa, no un 0 %."""
    return round(100.0 * envios / visitas, 1) if visitas else None


def _visitas_filtradas(
    db: Session, campaign_id: int, desde: Optional[datetime.date], hasta: Optional[datetime.date]
):
    consulta = db.query(VisitaDePublicacion).filter(
        VisitaDePublicacion.campaign_id == campaign_id
    )
    if desde:
        consulta = consulta.filter(VisitaDePublicacion.dia >= desde)
    if hasta:
        consulta = consulta.filter(VisitaDePublicacion.dia <= hasta)
    return consulta


def _visitas_por_dia(
    db: Session, campaign_id: int, desde: Optional[datetime.date], hasta: Optional[datetime.date]
) -> Dict[datetime.date, int]:
    """
    Visitas de cada día, **sumando todas las redes**. Desde el capítulo 27 hay una fila por
    red y día; sin el `SUM` el gráfico enseñaría solo la última red de cada día.
    """
    filas = (
        _visitas_filtradas(db, campaign_id, desde, hasta)
        .with_entities(VisitaDePublicacion.dia, func.sum(VisitaDePublicacion.visitas))
        .group_by(VisitaDePublicacion.dia)
        .all()
    )
    return {dia: int(suma or 0) for dia, suma in filas}


def _visitas_por_red(
    db: Session, campaign_id: int, desde: Optional[datetime.date], hasta: Optional[datetime.date]
) -> Dict[str, int]:
    filas = (
        _visitas_filtradas(db, campaign_id, desde, hasta)
        .with_entities(VisitaDePublicacion.red, func.sum(VisitaDePublicacion.visitas))
        .group_by(VisitaDePublicacion.red)
        .all()
    )
    return {str(red): int(suma or 0) for red, suma in filas}


def red_de(datos: dict) -> str:
    """
    La red de llegada de una solicitud. Las anteriores al capítulo 27 no la llevan y se
    quedan en «sin red», que es la verdad: se registraron cuando no se miraba.
    """
    red = (datos or {}).get("red")
    return str(red) if red in REDES else SIN_RED


def _por_red(
    db: Session,
    publicacion: Campaign,
    scores_visibles: Dict[int, float],
    desde: Optional[datetime.date],
    hasta: Optional[datetime.date],
    inicio,
    fin,
    desde_el_dia: Optional[datetime.date],
) -> List[FilaDeRed]:
    """
    Una fila por red: visitas, perfiles, envíos, tasa y score medio.

    Se recorren las solicitudes de esta publicación en Python en lugar de agrupar por el
    JSON en SQL. `activity_data` se consulta de forma distinta en PostgreSQL y en el SQLite
    de las pruebas, y esto tiene que dar lo mismo en los dos; son las solicitudes de **una**
    publicación, no las de la base entera.

    Salen las redes activas de la publicación, más cualquier otra que haya traído algo:
    desactivar una red no borra lo que trajo mientras estuvo activa, y esconderlo dejaría un
    informe cuyas filas no suman el total.
    """
    visitas = _visitas_por_red(db, publicacion.id, desde, hasta)
    envios: Dict[str, int] = {}
    fichas: Dict[str, set] = {}

    if desde_el_dia is not None:
        primero = _desde_el_dia(_dia(desde_el_dia))
        desde = max(inicio, primero) if inicio is not None else primero
        consulta = db.query(
            LeadActivity.lead_id, LeadActivity.activity_data, LeadActivity.occurred_at
        ).filter(
            LeadActivity.source == FUENTE,
            LeadActivity.external_event_id.startswith(f"{publicacion.public_slug}:", autoescape=True),
            LeadActivity.occurred_at >= desde,
        )
        if fin is not None:
            consulta = consulta.filter(LeadActivity.occurred_at < fin)
        for lead_id, datos, _ocurrido in consulta:
            red = red_de(datos)
            envios[red] = envios.get(red, 0) + 1
            if lead_id in scores_visibles:
                fichas.setdefault(red, set()).add(lead_id)

    claves = [c for c in ORDEN if c in set(redes_de(publicacion.redes))]
    for red in list(visitas) + list(envios):
        if red not in claves:
            claves.append(red)

    filas = []
    for red in claves:
        de_esta = fichas.get(red, set())
        valores = [scores_visibles[f] for f in de_esta]
        filas.append(
            FilaDeRed(
                red=red,
                etiqueta=etiqueta_de_red(red),
                visitas=visitas.get(red, 0),
                perfiles=len(de_esta),
                envios=envios.get(red, 0),
                tasa_de_envio=tasa(envios.get(red, 0), visitas.get(red, 0)),
                score_medio=_redondear(sum(valores) / len(valores)) if valores else 0.0,
            )
        )
    return filas


def _primer_dia_contado(db: Session, campaign_id: int) -> Optional[datetime.date]:
    return db.query(func.min(VisitaDePublicacion.dia)).filter(VisitaDePublicacion.campaign_id == campaign_id).scalar()


def _desde_el_dia(dia: datetime.date) -> datetime.datetime:
    return datetime.datetime.combine(dia, datetime.time.min, tzinfo=datetime.timezone.utc)


def _envios(db: Session, slug: str, inicio, fin, desde_el_dia: Optional[datetime.date] = None) -> int:
    """
    Solicitudes enviadas por la página de esta publicación en el periodo. Cuenta envíos, no
    personas. Un total, sin nombres.

    Solo **desde el primer día con visitas contadas**. Las visitas se cuentan desde el
    capítulo 26; una publicación anterior tiene envíos de antes sin ninguna visita detrás, y
    dividir unos entre otras daba tasas del 200 %. Sin visitas contadas no hay tasa, así que
    tampoco hay envíos que contar para ella.
    """
    if desde_el_dia is None:
        return 0
    primero = _desde_el_dia(_dia(desde_el_dia))
    inicio = max(inicio, primero) if inicio is not None else primero
    consulta = db.query(func.count(LeadActivity.id)).filter(
        LeadActivity.source == FUENTE,
        LeadActivity.external_event_id.startswith(f"{slug}:", autoescape=True),
    )
    if inicio is not None:
        consulta = consulta.filter(LeadActivity.occurred_at >= inicio)
    if fin is not None:
        consulta = consulta.filter(LeadActivity.occurred_at < fin)
    return int(consulta.scalar() or 0)


def _aware(momento: datetime.datetime) -> datetime.datetime:
    return momento.replace(tzinfo=datetime.timezone.utc) if momento.tzinfo is None else momento


def _dia(momento) -> datetime.date:
    if isinstance(momento, datetime.datetime):
        return momento.date() if momento.tzinfo is None else momento.astimezone(datetime.timezone.utc).date()
    if isinstance(momento, datetime.date):
        return momento
    return datetime.datetime.fromisoformat(str(momento)).date()


def _serie(
    fechas: List,
    visitas_por_dia: Dict[datetime.date, int],
    desde: Optional[datetime.date],
    hasta: Optional[datetime.date],
) -> Tuple[List[DiaDelInforme], bool]:
    """
    Un día por barra, con los días sin nada a cero: un hueco en el gráfico se leería como
    un día que falta, no como un día sin perfiles. El periodo es el del filtro o, sin él,
    del primer día con algo al último.
    """
    perfiles: Dict[datetime.date, int] = {}
    for momento in fechas:
        dia = _dia(momento)
        perfiles[dia] = perfiles.get(dia, 0) + 1
    dias_con_algo = set(perfiles) | set(visitas_por_dia)
    if not dias_con_algo and not (desde and hasta):
        return [], False
    primero = desde or min(dias_con_algo)
    ultimo = hasta or max(dias_con_algo)
    if ultimo < primero:
        return [], False
    recortado = (ultimo - primero).days + 1 > MAX_DIAS_DEL_GRAFICO
    if recortado:
        primero = ultimo - datetime.timedelta(days=MAX_DIAS_DEL_GRAFICO - 1)
    serie = []
    dia = primero
    while dia <= ultimo:
        serie.append(DiaDelInforme(dia=dia, perfiles=perfiles.get(dia, 0), visitas=visitas_por_dia.get(dia, 0)))
        dia += datetime.timedelta(days=1)
    return serie, recortado


def _condiciones_de_alcance(alcance: AlcanceDeCartera):
    """
    Devuelve (lo mío, lo del resto). `(None, None)` para quien ve la cartera completa.

    «Lo del resto» incluye lo que no tiene dueño: un prospecto sin asesor no es de nadie,
    y desde luego no de quien pregunta.
    """
    if alcance.toda_la_cartera:
        return None, None
    if alcance.usuario_id is None:
        return false(), None
    mio = Lead.assigned_rep_id == alcance.usuario_id
    del_resto = or_(
        Lead.assigned_rep_id.is_(None), Lead.assigned_rep_id != alcance.usuario_id
    )
    return mio, del_resto


def _necesidades(db: Session, slug: str, lead_ids: List[int]) -> Dict[int, str]:
    """
    Por cada ficha de la página, la necesidad de su **última** solicitud a esta publicación:
    si alguien volvió a escribir porque ahora quiere una demo, eso es lo que el asesor tiene
    que leer. Solo de las filas que se devuelven, no de toda la publicación.
    """
    if not lead_ids:
        return {}
    actividades = (
        db.query(LeadActivity.lead_id, LeadActivity.activity_data)
        .filter(
            LeadActivity.source == FUENTE,
            LeadActivity.lead_id.in_(lead_ids),
            LeadActivity.external_event_id.startswith(f"{slug}:", autoescape=True),
        )
        .order_by(LeadActivity.occurred_at.asc(), LeadActivity.id.asc())
        .all()
    )
    necesidades: Dict[int, str] = {}
    for lead_id, datos in actividades:
        etiqueta = etiqueta_de_necesidad(datos or {})
        if etiqueta:
            necesidades[lead_id] = etiqueta
    return necesidades


def _fila(lead: Lead, recibida_en, asesor: Optional[str], necesidad: Optional[str]) -> FilaDelInforme:
    return FilaDelInforme(
        lead_id=lead.id,
        nombre=f"{lead.first_name} {lead.last_name}".strip(),
        empresa=lead.company,
        cargo=lead.job_title,
        score=lead.current_score,
        categoria=lead.score_category,
        etapa=lead.status,
        asesor=asesor,
        recibida_en=recibida_en,
        necesidad=necesidad,
    )


# ------------------------------------------------------------------------- la comparativa
def comparativa(db: Session) -> ComparativaDePublicaciones:
    """
    Las publicaciones una al lado de otra.

    No se acota por cartera —y por eso el endpoint es del líder y del administrador—, por
    la misma razón que el rendimiento por campaña: los prospectos de una sola persona
    comparados entre publicaciones dan un orden que no es el real, y un número de negocio
    mal calculado hace más daño que no publicarlo.

    Se resuelve en tres consultas y no en una por publicación: las solicitudes de todas las
    publicaciones de una vez, las fichas atribuidas de una vez, y los datos de las fichas
    resultantes de una vez.
    """
    publicaciones = (
        db.query(Campaign)
        .filter(Campaign.channel == CANAL_LINKEDIN)
        .order_by(Campaign.id.asc())
        .all()
    )
    if not publicaciones:
        return ComparativaDePublicaciones(items=[])
    ciclo.cerrar_vencidas(db)

    por_slug = {p.public_slug: p.id for p in publicaciones}
    fichas_por_publicacion: Dict[int, set] = {p.id: set() for p in publicaciones}
    envios_por_publicacion: Dict[int, int] = {p.id: 0 for p in publicaciones}
    visitas_por_publicacion: Dict[int, int] = {}
    primer_dia: Dict[int, datetime.datetime] = {}
    for campaign_id, suma, dia in (
        db.query(VisitaDePublicacion.campaign_id, func.sum(VisitaDePublicacion.visitas), func.min(VisitaDePublicacion.dia))
        .group_by(VisitaDePublicacion.campaign_id)
        .all()
    ):
        visitas_por_publicacion[campaign_id] = int(suma or 0)
        primer_dia[campaign_id] = _desde_el_dia(_dia(dia))

    for lead_id, externo, datos, ocurrido in db.query(
        LeadActivity.lead_id, LeadActivity.external_event_id, LeadActivity.activity_data, LeadActivity.occurred_at
    ).filter(LeadActivity.source == FUENTE):
        slug = (datos or {}).get("publicacion")
        if not slug and externo and ":" in externo:
            slug = externo.split(":", 1)[0]
        publicacion_id = por_slug.get(slug)
        if publicacion_id is not None:
            fichas_por_publicacion[publicacion_id].add(lead_id)
            # Como en el informe: solo los envíos desde que se cuentan visitas.
            desde = primer_dia.get(publicacion_id)
            if desde is not None and _aware(ocurrido) >= desde:
                envios_por_publicacion[publicacion_id] += 1

    for lead_id, campaign_id in db.query(Lead.id, Lead.campaign_id).filter(
        Lead.campaign_id.in_(fichas_por_publicacion.keys())
    ):
        fichas_por_publicacion[campaign_id].add(lead_id)

    todas = {lead_id for fichas in fichas_por_publicacion.values() for lead_id in fichas}
    estado_por_ficha = {
        lead_id: (etapa, score)
        for lead_id, etapa, score in db.query(Lead.id, Lead.status, Lead.current_score).filter(
            Lead.id.in_(todas)
        )
    } if todas else {}

    items = []
    for publicacion in publicaciones:
        fichas = fichas_por_publicacion[publicacion.id]
        items.append(
            FilaDeComparativa(
                publicacion_id=publicacion.id,
                titulo=publicacion.name,
                activa=bool(publicacion.is_active),
                estado=publicacion.estado,
                perfiles_recibidos=len(fichas),
                avanzaron_de_etapa=_cuentan_avance(fichas, estado_por_ficha),
                score_medio=_media(fichas, estado_por_ficha),
                visitas=int(visitas_por_publicacion.get(publicacion.id) or 0),
                envios=envios_por_publicacion[publicacion.id],
                tasa_de_envio=tasa(
                    envios_por_publicacion[publicacion.id],
                    int(visitas_por_publicacion.get(publicacion.id) or 0),
                ),
            )
        )
    return ComparativaDePublicaciones(items=items)


def _cuentan_avance(fichas: Iterable[int], estados: Dict[int, tuple]) -> int:
    return sum(1 for f in fichas if estados.get(f, (ETAPA_INICIAL, 0.0))[0] != ETAPA_INICIAL)


def _media(fichas, estados: Dict[int, tuple]) -> float:
    valores = [estados[f][1] or 0.0 for f in fichas if f in estados]
    return _redondear(sum(valores) / len(valores)) if valores else 0.0


# -------------------------------------------------------------------------- el contador
def nuevos_sin_asesor(db: Session) -> int:
    """
    Fichas llegadas por una publicación que todavía no tienen a nadie detrás.

    Se buscan por **todos** los canales que escribe la página de interés, no solo por
    «LinkedIn». Desde el capítulo 27 una ficha de la misma publicación puede llegar como
    «WhatsApp» o «Facebook»; con el filtro de antes, el líder habría dejado de ver a la
    mayoría de los que están esperando justo cuando empezaron a llegar por más sitios.

    La misma condición que marca las fichas en el listado (`es_de_publicacion`), para que
    el número y la lista no puedan discrepar.
    """
    return (
        db.query(func.count(Lead.id))
        .filter(Lead.source.in_(CANALES_DE_PUBLICACION), Lead.assigned_rep_id.is_(None))
        .scalar()
        or 0
    )


def contar_enlaces_caducados(db: Session) -> int:
    """
    Cuántas publicaciones llevan un enlace repartido que ya no lleva aquí (capítulo 34).

    Es la misma comparación que hace `CampanaResponse.enlace_caducado`, en una sola consulta
    y sin traerse las filas: el panel necesita la cifra antes de dibujar la lista, para
    decidir si enseña el aviso de arriba o no.

    Cuenta solo las que **tienen** dirección anotada. Las anteriores al capítulo 34 están a
    `NULL` —no consta bajo qué dirección salieron— y contarlas como caducadas inventaría el
    dato que la cifra existe para medir.
    """
    return (
        db.query(func.count(Campaign.id))
        .filter(
            Campaign.channel == CANAL_LINKEDIN,
            Campaign.url_base_publicada.isnot(None),
            Campaign.url_base_publicada != base_publica(),
        )
        .scalar()
        or 0
    )
