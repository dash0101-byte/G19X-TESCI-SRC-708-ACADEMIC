"""
El ciclo de vida de una publicación y lo que la rodea: estado, cierre por fecha, responsable,
visitas y duplicado (capítulo 26).

Vive aparte de `pagina_de_interes` (lo que ve el interesado) y de `informe_de_publicaciones`
(lo que ve el equipo) porque lo usan los dos y el alta de campañas.
"""
import datetime
import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.publicaciones import ACTIVA, BORRADOR, CERRADA, CIERRAN_POR_FECHA, ESTADOS
from app.core.redes import SIN_RED
from app.models.entities import Campaign, User, VisitaDePublicacion, utc_now

logger = logging.getLogger(__name__)

SUFIJO_DE_COPIA = " (copia)"


def _aware(momento: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
    """SQLite devuelve las fechas sin zona; todas se guardan en UTC."""
    if momento is not None and momento.tzinfo is None:
        return momento.replace(tzinfo=datetime.timezone.utc)
    return momento


# ------------------------------------------------------------------------------ estado
def fijar_estado(campana: Campaign, estado: str) -> None:
    """
    El único sitio que cambia el estado: `is_active` va siempre con él.

    Desde el capítulo 34 también anota **bajo qué dirección pública** se repartió el enlace.
    Activar es el instante exacto en que ese enlace se vuelve repartible —antes es un
    borrador que nadie ha visto—, así que es el único momento en que el dato es cierto.

    Se escribe una sola vez. Reactivar una publicación pausada bajo otra dirección NO lo
    reescribe, y esa es la decisión que hace útil el dato: lo que hay que poder contestar es
    «¿el enlace que la gente ya tiene lleva aquí?», y quien lo tiene lo copió la primera vez.
    Sobrescribirlo al reactivar borraría justo la prueba de que el enlace repartido caducó.
    """
    if estado not in ESTADOS:
        raise ValueError(f"Estado desconocido: {estado}")
    campana.estado = estado
    campana.is_active = estado == ACTIVA
    if estado == ACTIVA and campana.url_base_publicada is None:
        campana.url_base_publicada = settings.PUBLICACIONES_URL_BASE


def vencida(campana: Campaign, ahora: Optional[datetime.datetime] = None) -> bool:
    fin = _aware(campana.end_date)
    return fin is not None and fin <= (ahora or utc_now())


def cerrar_vencidas(db: Session, ahora: Optional[datetime.datetime] = None) -> int:
    """
    Cierra las publicaciones activas o pausadas cuya fecha de cierre ya pasó.

    Se llama antes de contestar a quien mira —la página, la lista, el informe—, así que no
    hace falta ninguna tarea programada: una página vencida no se sirve nunca, aunque nadie
    haya abierto el panel desde entonces. Es una sola sentencia y no toca nada si no hay
    vencidas.
    """
    ahora = ahora or utc_now()
    resultado = db.execute(
        update(Campaign)
        .where(
            Campaign.estado.in_(CIERRAN_POR_FECHA),
            Campaign.end_date.isnot(None),
            Campaign.end_date <= ahora,
        )
        .values(estado=CERRADA, is_active=False)
        .execution_options(synchronize_session="fetch")
    )
    if resultado.rowcount:
        db.commit()
        logger.info("Cerradas por fecha: %s publicación(es).", resultado.rowcount)
    return resultado.rowcount or 0


def comprobar_transicion(campana: Campaign, estado_nuevo: str, fin_nuevo) -> None:
    """Activar o reanudar algo cuya fecha de cierre ya pasó lo volvería a cerrar al instante."""
    fin = _aware(fin_nuevo)
    if estado_nuevo in CIERRAN_POR_FECHA and fin is not None and fin <= utc_now():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La fecha de cierre ya pasó: cámbiela antes de activar o pausar la publicación.",
        )


# -------------------------------------------------------------------------- responsable
def comprobar_responsable(db: Session, responsable_id: Optional[int]) -> None:
    """Solo un asesor activo puede ser responsable: los prospectos se le asignan a él."""
    if responsable_id is None:
        return
    usuario = db.query(User).filter(User.id == responsable_id).first()
    if usuario is None or not usuario.is_active or not usuario.is_sales_rep:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El responsable tiene que ser un asesor comercial activo.",
        )


def asesor_para(db: Session, campana: Campaign) -> Optional[int]:
    """
    A quién se asigna un prospecto nuevo de esta publicación, o `None`.

    Se vuelve a comprobar al llegar cada prospecto: si el responsable se dio de baja o dejó de
    ser asesor después de elegirlo, el prospecto llega sin asesor al líder, como si la
    publicación no tuviera responsable, en lugar de caer en una cartera que nadie abre.
    """
    if campana.responsable_id is None:
        return None
    usuario = db.query(User).filter(User.id == campana.responsable_id).first()
    if usuario is None or not usuario.is_active or not usuario.is_sales_rep:
        logger.warning(
            "La publicación %s tiene un responsable que ya no es un asesor activo; "
            "el prospecto llega sin asesor.", campana.id,
        )
        return None
    return usuario.id


# ------------------------------------------------------------------------------ visitas
def registrar_visita(
    db: Session,
    campana: Campaign,
    *,
    red: Optional[str] = None,
    dia: Optional[datetime.date] = None,
) -> None:
    """
    Suma una visita al día de hoy y a su red. Solo el número: nada de quién, desde dónde ni
    con qué. La red es por dónde se repartió el enlace, no un dato de quien lo abrió.

    `red` es `None` cuando el enlace llegó sin parámetro, con uno inventado o manipulado; se
    cuenta en `sin_red`, que es una fila más y nunca un rechazo.

    Los dos van con nombre a propósito. Antes del capítulo 27 el tercer argumento era el día,
    y al meter la red delante una llamada antigua habría pasado una fecha donde ahora va una
    red: sin error, contando visitas de una red llamada «2026-09-21».

    Primero se intenta sumar a la fila del día; si no existe, se crea. Si otra visita la
    creó a la vez, la inserción choca con la clave primaria y se vuelve a sumar.
    """
    dia = dia or utc_now().date()
    red = red or SIN_RED
    suma = (
        update(VisitaDePublicacion)
        .where(
            VisitaDePublicacion.campaign_id == campana.id,
            VisitaDePublicacion.dia == dia,
            VisitaDePublicacion.red == red,
        )
        .values(visitas=VisitaDePublicacion.visitas + 1)
    )
    if db.execute(suma).rowcount:
        db.commit()
        return
    try:
        db.add(VisitaDePublicacion(campaign_id=campana.id, dia=dia, red=red, visitas=1))
        db.commit()
    except IntegrityError:
        # El séptimo `except IntegrityError` del sistema, y el único que no tiene que
        # averiguar nada: no traduce el rechazo a ningún mensaje ni decide si la fila existía,
        # vuelve a ejecutar la suma. Si la fila la acaba de crear otra visita, ahora suma
        # sobre ella; si el rechazo fuera otro, el `UPDATE` no encuentra nada y lo que se
        # pierde es el recuento de una visita, que es la única cosa del sistema que puede
        # perderse sin que nadie tenga que enterarse. Queda inventariado así en la guarda del
        # capítulo 42 precisamente para que se vea que la excepción es deliberada.
        db.rollback()
        db.execute(suma)
        db.commit()


# ----------------------------------------------------------------------------- duplicar
def duplicar(db: Session, original: Campaign) -> Campaign:
    """
    Una publicación nueva con el mismo texto, público, opciones, redes y responsable. Sale
    en **borrador**, con enlace propio y sin post, fechas ni visitas: es otro post, y lo que
    trajo el original sigue siendo del original.
    """
    nombre = original.name
    if len(nombre) + len(SUFIJO_DE_COPIA) > 200:
        nombre = nombre[: 200 - len(SUFIJO_DE_COPIA)]
    copia = Campaign(
        name=f"{nombre}{SUFIJO_DE_COPIA}",
        channel=original.channel,
        description=original.description,
        target_audience=original.target_audience,
        budget=original.budget,
        utm_source=original.utm_source,
        utm_medium=original.utm_medium,
        utm_campaign=original.utm_campaign,
        necesidades=list(original.necesidades) if original.necesidades else None,
        redes=list(original.redes) if original.redes else None,
        responsable_id=original.responsable_id,
    )
    fijar_estado(copia, BORRADOR)
    db.add(copia)
    db.commit()
    db.refresh(copia)
    return copia
