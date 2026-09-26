"""
La agenda del día: leer la bandeja, la campana y los HOT que se enfrían (capítulo 28).

El motor (`motor_de_reglas.py`) decide qué hay que hacer; esto solo lo enseña y lo cierra.
Están separados a propósito: las reglas corren una vez al día sin nadie delante, y estas
consultas corren cada vez que alguien abre el panel. Mezclarlos habría acabado con una
pantalla que crea tareas al mirarla, y entonces «cuántas tareas hay» dependería de cuánta
gente hubiera entrado esa mañana.

El alcance
----------
Un asesor ve **sus** tareas. El líder y el administrador ven las de la cartera entera, que
es lo que ya significaba su alcance en el resto del sistema (`app/core/autorizacion.py`).
Una tarea que no se alcanza responde 404 y no 403, por lo mismo que un prospecto ajeno:
distinguir «no existe» de «no es tuya» permite contar el trabajo de los demás recorriendo
identificadores.

Marcar hecha es otra cosa
-------------------------
Verla y decir «ya la hice» no son el mismo permiso. Lo segundo es una afirmación sobre el
trabajo de una persona concreta, así que solo la cierra su dueño, aunque el líder la vea.

Lo cerrado no sale aquí (capítulo 30)
--------------------------------------
La bandeja y la campana preguntan además si del prospecto queda algo que hacer, con la
**misma** condición que usan las reglas (`motor_de_reglas.en_seguimiento`). Es una segunda
defensa y no la principal: al cerrar un prospecto sus tareas abiertas se descartan en el
acto, y este filtro cubre lo que se cerró antes de que existiera el desenlace o por algún
camino que no pasara por él. El contador de avisos sin leer lleva el mismo filtro que la
lista; que el número dijera tres y la campana enseñara uno es el defecto que ya costó un
capítulo corregir en el contador de prospectos sin asesor.
"""
import datetime
from typing import Dict, List, Optional, Sequence

from sqlalchemy import case
from sqlalchemy.orm import Session, contains_eager

from app.core.agenda import ABIERTA, HECHA, HOT_SIN_CONTACTO, HOT_SIN_CONTACTO_LIDER, etiqueta_de_regla
from app.core.autorizacion import AlcanceDeCartera
from app.core.config import settings
from app.models.entities import Aviso, Lead, Tarea, User, utc_now
from app.schemas.agenda import (
    AvisoDeLaAgenda,
    BandejaDeHoy,
    Campana,
    HotQueSeEnfria,
    HotQueSeEnfrian,
    ProspectoDeLaAgenda,
    TareaDeLaAgenda,
)
from app.services.motor_de_reglas import (
    Contexto,
    aware,
    en_seguimiento,
    hot_desatendidos,
)

# Cuántos avisos devuelve la campana. No es una paginación: es el reconocimiento de que
# nadie lee el aviso número cuarenta. Los que no caben siguen contando en `sin_leer`.
MAX_AVISOS = 30

# Qué es «hoy» en esta bandeja: lo vencido, más lo que vence en las próximas 24 horas.
#
# La primera versión cortaba por el día natural —lo que vence antes de medianoche— y estaba
# mal por una razón que solo se ve al juntarlo con el motor: la pasada corre de madrugada y
# da 24 horas de plazo, así que una tarea creada a las 03:00 del lunes vence a las 03:00 del
# martes. Con el corte por día natural, el lunes entero esa tarea contaba como «más
# adelante» y la bandeja aparecía vacía **justo el día en que había que hacerla**; solo se
# asomaba el martes, ya vencida. Una bandeja que solo enseña lo que ya llega tarde no dice
# qué hacer hoy: dice qué se hizo tarde ayer.
#
# Como efecto secundario, deja de depender de la hora a la que alguien abra el panel: a las
# nueve de la mañana y a las once de la noche se ve el mismo trabajo.
HORIZONTE_HORAS = 24


class TareaFueraDeAlcance(Exception):
    """Esta tarea no existe para quien la pide. La capa HTTP la traduce a 404."""

    def __init__(self, tarea_id: int):
        self.tarea_id = tarea_id
        super().__init__(f"La tarea {tarea_id} no está al alcance de quien la solicita.")


def _prospecto(lead: Lead) -> ProspectoDeLaAgenda:
    nombre = " ".join(filter(None, [lead.first_name, lead.last_name])).strip()
    return ProspectoDeLaAgenda(
        id=lead.id,
        nombre=nombre,
        empresa=lead.company,
        score=lead.current_score,
        categoria=lead.score_category,
        dormido_desde=lead.dormido_desde,
    )


def _tarea(tarea: Tarea, ahora: datetime.datetime) -> TareaDeLaAgenda:
    return TareaDeLaAgenda(
        id=tarea.id,
        regla=tarea.regla,
        regla_etiqueta=etiqueta_de_regla(tarea.regla),
        motivo=tarea.motivo,
        estado=tarea.estado,
        vence_el=tarea.vence_el,
        vencida=aware(tarea.vence_el) < ahora,
        creada_en=tarea.creada_en,
        prospecto=_prospecto(tarea.lead),
    )


def asesor_visible(alcance: AlcanceDeCartera, asesor_id: Optional[int]) -> int:
    """
    De quién es la bandeja que se está pidiendo.

    Sin `asesor_id`, la propia. Con él, solo si quien pregunta alcanza la cartera entera;
    un asesor que pide la de otro recibe un 404, no un 403, para que recorrer identificadores
    no diga cuántas personas hay ni cuáles tienen trabajo.
    """
    if asesor_id is None or asesor_id == alcance.usuario_id:
        return alcance.usuario_id
    if not alcance.toda_la_cartera:
        raise TareaFueraDeAlcance(asesor_id)
    return asesor_id


def bandeja_de_hoy(
    db: Session,
    alcance: AlcanceDeCartera,
    *,
    asesor_id: Optional[int] = None,
    ahora: Optional[datetime.datetime] = None,
) -> BandejaDeHoy:
    """
    Lo pendiente que ya toca, ordenado por score.

    «Ya toca» es lo vencido más lo que vence en las próximas `HORIZONTE_HORAS`. Ordenar por
    score y no por fecha es la decisión de fondo: una bandeja por fecha pone arriba lo más
    viejo, que suele ser también lo más frío, y deja al prospecto que más vale para después
    de comer.
    """
    ahora = ahora or utc_now()
    de_quien = asesor_visible(alcance, asesor_id)
    horizonte = ahora + datetime.timedelta(hours=HORIZONTE_HORAS)

    # `contains_eager` y no solo el `join`: cada tarea enseña el nombre, la empresa, el score
    # y la categoría de su prospecto, y sin esto SQLAlchemy los iba a buscar **tarea a
    # tarea**. Con cuarenta tareas abiertas eran cuarenta consultas más —medido en
    # `tests/test_rendimiento_con_volumen.py`, que es donde se encontró—, y ese coste no se
    # ve en una suite de seis prospectos ni en una bandeja de dos tareas: crece justo cuando
    # la bandeja empieza a servir para algo.
    #
    # Se usa `contains_eager` y no `joinedload` porque el `join` ya está hecho, para el
    # filtro y para el orden. `joinedload` añadiría un SEGUNDO `join` a la misma tabla.
    abiertas = (
        db.query(Tarea)
        .join(Lead, Lead.id == Tarea.lead_id)
        .options(contains_eager(Tarea.lead))
        .filter(Tarea.asesor_id == de_quien, Tarea.estado == ABIERTA, en_seguimiento())
        .order_by(Lead.current_score.desc(), Tarea.vence_el.asc(), Tarea.id.asc())
        .all()
    )

    bandeja = BandejaDeHoy(asesor_id=de_quien)
    for tarea in abiertas:
        vence = aware(tarea.vence_el)
        if vence > horizonte:
            bandeja.mas_adelante += 1
            continue
        bandeja.tareas.append(_tarea(tarea, ahora))
        if vence < ahora:
            bandeja.vencidas += 1
        else:
            bandeja.para_hoy += 1
    return bandeja


def marcar_hecha(
    db: Session,
    alcance: AlcanceDeCartera,
    tarea_id: int,
    *,
    ahora: Optional[datetime.datetime] = None,
) -> Tarea:
    """
    Su dueño dice que ya la hizo.

    Solo su dueño, y da igual el rol: el líder ve el trabajo de su equipo y no lo firma por
    ellos. Una tarea ya cerrada se devuelve como está en lugar de fallar —pulsar dos veces
    no es un error— y la fecha de cierre no se mueve: la primera es la que ocurrió.
    """
    ahora = ahora or utc_now()
    tarea = (
        db.query(Tarea)
        .filter(Tarea.id == tarea_id, Tarea.asesor_id == alcance.usuario_id)
        .first()
    )
    if tarea is None:
        raise TareaFueraDeAlcance(tarea_id)
    if tarea.estado == ABIERTA:
        tarea.estado = HECHA
        tarea.cerrada_en = ahora
        tarea.cerrada_por_id = alcance.usuario_id
        db.commit()
    return tarea


def campana(
    db: Session,
    alcance: AlcanceDeCartera,
    *,
    solo_sin_leer: bool = False,
    limite: int = MAX_AVISOS,
) -> Campana:
    """Los avisos de quien pregunta. Siempre los suyos: un aviso tiene un destinatario."""
    # Lo mismo que en la bandeja: cada aviso enseña a su prospecto. Aquí el daño estaba
    # acotado por `MAX_AVISOS`, así que eran diez consultas de más y no cuarenta; se arregla
    # igual porque es el mismo defecto y la campana se abre en todas las pantallas.
    consulta = (
        db.query(Aviso)
        .join(Lead, Lead.id == Aviso.lead_id)
        .options(contains_eager(Aviso.lead))
        .filter(Aviso.usuario_id == alcance.usuario_id, en_seguimiento())
    )
    if solo_sin_leer:
        consulta = consulta.filter(Aviso.leido_en.is_(None))

    # El contador se cuenta con el MISMO filtro que la lista. Que el numerito dijera tres
    # y la campana enseñara uno es exactamente el defecto que el capítulo 29 corrigió en el
    # contador de prospectos sin asesor, y repetirlo aquí habría sido reincidir.
    sin_leer = (
        db.query(Aviso)
        .join(Lead, Lead.id == Aviso.lead_id)
        .filter(Aviso.usuario_id == alcance.usuario_id, Aviso.leido_en.is_(None), en_seguimiento())
        .count()
    )
    # Los que no se han leído primero, y dentro de cada grupo los más nuevos: la campana se
    # abre para ver lo que falta, no para repasar lo que ya se vio.
    filas = (
        consulta.order_by(
            case((Aviso.leido_en.is_(None), 0), else_=1),
            Aviso.creado_en.desc(),
            Aviso.id.desc(),
        )
        .limit(limite)
        .all()
    )
    return Campana(
        sin_leer=sin_leer,
        avisos=[
            AvisoDeLaAgenda(
                id=aviso.id,
                regla=aviso.regla,
                regla_etiqueta=etiqueta_de_regla(aviso.regla),
                texto=aviso.texto,
                creado_en=aviso.creado_en,
                leido_en=aviso.leido_en,
                prospecto=_prospecto(aviso.lead),
            )
            for aviso in filas
        ],
    )


def marcar_leidos(
    db: Session,
    alcance: AlcanceDeCartera,
    ids: Optional[Sequence[int]] = None,
    *,
    ahora: Optional[datetime.datetime] = None,
) -> int:
    """
    Marca como leídos los avisos indicados, o todos los del usuario si no se indica ninguno.

    Siempre acotado al destinatario: un identificador ajeno no marca nada y no lo dice, que
    es la misma respuesta que daría si no existiera.
    """
    ahora = ahora or utc_now()
    consulta = db.query(Aviso).filter(
        Aviso.usuario_id == alcance.usuario_id, Aviso.leido_en.is_(None)
    )
    if ids is not None:
        consulta = consulta.filter(Aviso.id.in_(list(ids)))
    leidos = consulta.update({Aviso.leido_en: ahora}, synchronize_session=False)
    db.commit()
    return leidos


def hot_que_se_enfrian(
    db: Session,
    *,
    ahora: Optional[datetime.datetime] = None,
) -> HotQueSeEnfrian:
    """
    Los HOT que llevan demasiado sin que nadie los toque, y con qué asesor están.

    Es la vista del líder, y la única de este capítulo que cruza carteras: el trabajo de una
    persona es suyo, pero un prospecto caliente enfriándose es un problema del equipo. Usa
    la **misma consulta** que la regla que avisa (`_hot_desatendidos`) y no una copia: dos
    definiciones de «desatendido» acabarían discrepando, y el líder vería en su pantalla una
    lista distinta de la que generó los avisos que está recibiendo.
    """
    ahora = ahora or utc_now()
    ctx = Contexto(db=db, ahora=ahora)
    leads = hot_desatendidos(ctx, settings.REGLA_HOT_SIN_CONTACTO_HORAS)

    nombres: Dict[int, str] = {
        fila.id: fila.full_name
        for fila in db.query(User.id, User.full_name)
        .filter(User.id.in_([lead.assigned_rep_id for lead in leads if lead.assigned_rep_id]))
        .all()
    }
    avisados = _avisados_por_regla(db, [lead.id for lead in leads])

    filas: List[HotQueSeEnfria] = []
    for lead in leads:
        desde = aware(lead.last_activity_at or lead.created_at)
        filas.append(
            HotQueSeEnfria(
                prospecto=_prospecto(lead),
                asesor_id=lead.assigned_rep_id,
                asesor=nombres.get(lead.assigned_rep_id),
                horas_sin_contacto=int((ahora - desde).total_seconds() // 3600),
                avisado_al_asesor=HOT_SIN_CONTACTO in avisados.get(lead.id, set()),
                avisado_al_lider=HOT_SIN_CONTACTO_LIDER in avisados.get(lead.id, set()),
            )
        )
    # El que lleva más tiempo enfriándose, arriba: aquí la urgencia es el tiempo, no el
    # score, porque todos son HOT.
    filas.sort(key=lambda fila: fila.horas_sin_contacto, reverse=True)
    return HotQueSeEnfrian(total=len(filas), filas=filas)


def _avisados_por_regla(db: Session, ids: List[int]) -> Dict[int, set]:
    if not ids:
        return {}
    avisados: Dict[int, set] = {}
    for lead_id, regla in db.query(Aviso.lead_id, Aviso.regla).filter(Aviso.lead_id.in_(ids)).all():
        avisados.setdefault(lead_id, set()).add(regla)
    return avisados


def hay_hot_enfriandose(db: Session, *, ahora: Optional[datetime.datetime] = None) -> bool:
    """Atajo para el panel: si no hay ninguno, la tarjeta del líder no se pinta."""
    ahora = ahora or utc_now()
    return bool(hot_desatendidos(Contexto(db=db, ahora=ahora), settings.REGLA_HOT_SIN_CONTACTO_HORAS))


__all__ = [
    "MAX_AVISOS",
    "TareaFueraDeAlcance",
    "bandeja_de_hoy",
    "campana",
    "hay_hot_enfriandose",
    "hot_que_se_enfrian",
    "marcar_hecha",
    "marcar_leidos",
]
