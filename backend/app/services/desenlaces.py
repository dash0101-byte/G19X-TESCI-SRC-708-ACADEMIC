"""
Cerrar un prospecto, y leer lo que dicen los cierres (capítulo 30).

Qué cierra este servicio
------------------------
Un prospecto pasa a ganado o perdido **por aquí y por ningún otro sitio**. La edición de
la ficha (`PUT /leads/{id}`) rechaza esas dos etapas con un 422 que dice dónde hay que ir.
Es el mismo razonamiento que llevó el alcance de cartera al repositorio en el capítulo 15 y
las reglas a un barrido en el 28: una obligación que se comprueba en cuatro sitios es una
obligación que el quinto camino se salta sin que nadie reciba un error. Aquí ese quinto
camino habría producido exactamente lo que este capítulo existe para evitar: cierres sin
motivo, es decir, etiquetas de entrenamiento sin nada que las explique.

Lo que el cierre hace, en una transacción
------------------------------------------
1. mueve la etapa del prospecto a `WON` o `LOST`;
2. guarda el desenlace con su motivo, su fecha y —si se ganó— su tramo;
3. copia el score y la categoría **del momento**, que es lo único con lo que después se
   puede responder «¿el score acertaba?»;
4. ata el desenlace a la instantánea de entrada y anota con qué versión del vector se
   tomó, para que el extractor del dataset la use tal cual o la descarte a sabiendas;
5. descarta las tareas abiertas de ese prospecto: nadie tiene que llamar a quien ya cerró.

Lo que el cierre NO hace
------------------------
**No recalcula el score.** Sería lo natural —cualquier otro cambio de la ficha lo hace— y
aquí está mal: el número que el panel pregunta es el que el sistema decía cuando se tomó la
decisión, y recalcular en ese instante lo sobrescribiría con uno que ya incorpora el
desenlace. **No reentrena nada**, no escribe en el registro de modelos y no toca el
artefacto: eso queda fuera del capítulo, y la guarda del CI lo comprueba.

El panel
--------
Totales por motivo, por tramo, por publicación, por red y por categoría de score al
cerrarse. Ni una fila con nombre. Es una vista de dirección, como la comparativa de
publicaciones y por la misma razón: los cierres de un solo asesor comparados entre
publicaciones dan un orden que no es el real, y un número de negocio mal calculado hace más
daño que no publicarlo.

Una advertencia sobre la atribución
------------------------------------
El informe de una publicación cuenta a una persona en **todas** las publicaciones a las que
respondió: la pregunta de allí es qué trajo cada post. Aquí cada cierre cuenta **una sola
vez**, en la publicación de su primera solicitud, porque la pregunta es otra —de dónde
salen los tratos que se ganan— y porque si no las filas no sumarían el total y el panel
tendría dos números distintos para lo mismo.
"""
import datetime
import logging
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.desenlaces import (
    ETAPA_DEL_RESULTADO,
    GANADO,
    MINIMO_DE_CASOS,
    MINIMO_POR_CLASE,
    MOTIVOS,
    PERDIDO,
    RESULTADOS,
    TRAMOS,
    etiqueta_de_motivo,
    etiqueta_de_resultado,
    tasa,
)
from app.core.publicaciones import CANAL_LINKEDIN
from app.core.redes import ORDEN as ORDEN_DE_REDES
from app.core.redes import SIN_RED
from app.core.redes import etiqueta_de as etiqueta_de_red
from app.core.vector_del_modelo import (
    CLAVE_DE_VERSION,
    VERSION_DEL_VECTOR,
    es_instantanea_vigente,
    instantanea_utilizable,
)
from app.models.entities import (
    Campaign,
    Desenlace,
    Lead,
    LeadActivity,
    LeadStatus,
    ScoreCategory,
    ScoreHistory,
    utc_now,
)
from app.schemas.desenlaces import (
    CierreDelProspecto,
    DesenlaceRegistrado,
    FilaDeAcierto,
    FilaDeMotivo,
    FilaDeTramo,
    FilaPorPublicacion,
    FilaPorRed,
    OpcionDeMotivo,
    OpcionDeResultado,
    OpcionDeTramo,
    OpcionesDeCierre,
    PanelDeDesenlaces,
    ProgresoDelReentrenamiento,
    ResumenDeDesenlaces,
)
from app.services import informe_de_publicaciones
from app.services.pagina_de_interes import FUENTE
from app.services.retencion_service import consulta_instantanea_de_entrada

logger = logging.getLogger(__name__)

SIN_PUBLICACION = "Sin publicación"


class CierreInvalido(ValueError):
    """El cierre no se puede registrar. La capa HTTP lo traduce a 422."""


# ==============================================================================
# Las opciones
# ==============================================================================

def opciones() -> OpcionesDeCierre:
    """Las listas cerradas, tal como las ofrece el formulario."""
    return OpcionesDeCierre(
        resultados=[
            OpcionDeResultado(
                clave=resultado,
                etiqueta=etiqueta_de_resultado(resultado),
                motivos=[
                    OpcionDeMotivo(clave=m.clave, etiqueta=m.etiqueta, descripcion=m.descripcion)
                    for m in MOTIVOS[resultado]
                ],
                pide_tramo=resultado == GANADO,
            )
            for resultado in RESULTADOS
        ],
        tramos=[OpcionDeTramo(clave=t.clave, etiqueta=t.etiqueta) for t in TRAMOS],
    )


# ==============================================================================
# Cerrar
# ==============================================================================

def _instantanea_de_entrada(db: Session, lead_id: int):
    """
    La instantánea con la que el prospecto entró al embudo, o `None`.

    El criterio lo define `retencion_service`, igual que el extractor del dataset: es la
    fila que la purga del historial tiene prohibido borrar, y tres copias del mismo
    criterio acabarían señalando tres filas distintas.
    """
    return consulta_instantanea_de_entrada(db, lead_id).first()


def _version_de(instantanea) -> Optional[int]:
    if instantanea is None:
        return None
    datos = instantanea.feature_snapshot or {}
    version = datos.get(CLAVE_DE_VERSION)
    # Las instantáneas de la versión 1 no declaran versión: la ausencia **es** el 1, y
    # devolver `None` las confundiría con las que no existen.
    return int(version) if isinstance(version, int) else 1


def registrar_cierre(
    db: Session,
    lead: Lead,
    cierre: CierreDelProspecto,
    *,
    usuario_id: Optional[int] = None,
    ahora: Optional[datetime.datetime] = None,
) -> DesenlaceRegistrado:
    """
    Cierra el prospecto con su motivo. Reescribe el desenlace si ya había uno.

    Corregir un cierre —se marcó ganado y era perdido— reescribe la fila en lugar de añadir
    otra. Guardar el historial de correcciones sonaba más completo y habría obligado a
    decidir cuál es «el» desenlace cada vez que el panel o el extractor preguntan; quién
    corrigió qué y cuándo ya queda en la bitácora, que es donde vive esa pregunta.
    """
    ahora = ahora or utc_now()

    alta = lead.created_at
    if alta is not None:
        dia_de_alta = alta.date() if isinstance(alta, datetime.datetime) else alta
        if cierre.cerrado_el < dia_de_alta:
            raise CierreInvalido(
                f"La fecha de cierre ({cierre.cerrado_el.isoformat()}) es anterior al alta del "
                f"prospecto ({dia_de_alta.isoformat()})."
            )

    instantanea = _instantanea_de_entrada(db, lead.id)
    version = _version_de(instantanea)

    lead.status = LeadStatus(ETAPA_DEL_RESULTADO[cierre.resultado])
    # Un prospecto cerrado no está dormido: la marca dice «nadie lo toca» y a partir de
    # ahora nadie debe tocarlo. Dejarla puesta habría hecho que la ficha enseñara «lleva
    # dormido desde marzo» sobre un trato que se ganó en marzo.
    lead.dormido_desde = None

    desenlace = db.query(Desenlace).filter(Desenlace.lead_id == lead.id).first()
    if desenlace is None:
        desenlace = Desenlace(lead_id=lead.id)
        db.add(desenlace)

    desenlace.resultado = cierre.resultado
    desenlace.motivo = cierre.motivo
    desenlace.cerrado_el = cierre.cerrado_el
    desenlace.tramo = cierre.tramo
    desenlace.score_al_cierre = float(lead.current_score or 0.0)
    desenlace.categoria_al_cierre = lead.score_category
    desenlace.score_history_id = instantanea.id if instantanea is not None else None
    desenlace.version_del_vector = version
    desenlace.registrado_en = ahora
    desenlace.registrado_por_id = usuario_id

    # Import local: `motor_de_reglas` importa de este módulo el recuento de desenlaces
    # utilizables —lo necesita su regla del aviso—, y hacerlo también al revés al cargar
    # el módulo cerraría el círculo y ninguno de los dos llegaría a importarse.
    from app.services.motor_de_reglas import descartar_por_desenlace

    descartadas = descartar_por_desenlace(db, lead, ahora=ahora)
    db.commit()
    db.refresh(desenlace)
    utilizable = es_utilizable(desenlace, instantanea)

    logger.info(
        "Prospecto %s cerrado como %s (motivo %s); %s tarea(s) descartada(s).",
        lead.id, cierre.resultado, cierre.motivo, descartadas,
    )
    return _registrado(lead, desenlace, descartadas, utilizable)


def _registrado(
    lead: Lead, desenlace: Desenlace, descartadas: int, utilizable: bool
) -> DesenlaceRegistrado:
    # Las columnas se copian de la fila y las etiquetas las resuelve el esquema: es el
    # mismo cálculo que hace la ficha 360, y por eso no está escrito dos veces.
    return DesenlaceRegistrado(
        lead_id=lead.id,
        etapa=lead.status,
        resultado=desenlace.resultado,
        motivo=desenlace.motivo,
        cerrado_el=desenlace.cerrado_el,
        tramo=desenlace.tramo,
        score_al_cierre=desenlace.score_al_cierre,
        categoria_al_cierre=desenlace.categoria_al_cierre,
        version_del_vector=desenlace.version_del_vector,
        utilizable_para_reentrenar=utilizable,
        tareas_descartadas=descartadas,
        registrado_en=desenlace.registrado_en,
    )


# ==============================================================================
# El contador del reentrenamiento
# ==============================================================================

def es_utilizable(desenlace: Desenlace, instantanea=None) -> bool:
    """
    ¿Sirve este cierre tal cual como ejemplo de entrenamiento?

    Hacen falta dos cosas: que haya instantánea de entrada —sin ella no hay vector que
    etiquetar— y que esa instantánea sea **utilizable** según el criterio del vector, es
    decir, de la versión vigente y completa. Una instantánea de la versión 1 no dice qué
    mensajes eran de LinkedIn ni cuántas llamadas quedaron sin respuesta; traducirla
    exigiría inventar las dos cosas, y el extractor la descarta.

    El criterio es **una** función, `vector_del_modelo.instantanea_utilizable`, y no una
    copia suya. Con dos, el contador prometería doscientos ejemplos y el extractor traería
    ciento ochenta sin que nada señalara de dónde sale la diferencia; la guarda del CI
    compara los dos números precisamente porque una copia parecía suficiente.
    """
    if desenlace.score_history_id is None:
        return False
    datos = (instantanea.feature_snapshot if instantanea is not None else None) or {}
    return instantanea_utilizable(datos)


def progreso_del_reentrenamiento(db: Session) -> ProgresoDelReentrenamiento:
    """
    Cuántos cierres hay, cuántos sirven y cuántos faltan.

    **No se acota por fechas**, a diferencia del resto del panel: el reentrenamiento se
    alimenta de todo lo que hay, y un contador que respondiera al filtro de un trimestre
    diría que faltan ciento noventa ejemplos cuando en la base hay trescientos.

    Se lee la instantánea y no solo la versión que el desenlace copió al cerrarse. La
    columna `version_del_vector` sigue sirviendo para el desglose —decir *de qué versión*
    era— pero no para decidir: una instantánea puede ser de la versión vigente y estar
    incompleta, y entonces el extractor la descarta aunque la columna diga que es la buena.
    """
    filas = (
        db.query(
            Desenlace.resultado, Desenlace.score_history_id, ScoreHistory.feature_snapshot
        )
        .outerjoin(ScoreHistory, ScoreHistory.id == Desenlace.score_history_id)
        .all()
    )

    cerrados = len(filas)
    utilizables = ganados = perdidos = 0
    sin_instantanea = de_un_vector_anterior = 0

    for resultado, score_history_id, instantanea in filas:
        datos = instantanea or {}
        if score_history_id is None or not datos:
            sin_instantanea += 1
            continue
        if not es_instantanea_vigente(datos):
            de_un_vector_anterior += 1
            continue
        if not instantanea_utilizable(datos):
            # De la versión vigente y aun así incompleta: le faltan variables. Cuenta con
            # las que no tienen instantánea porque el efecto es el mismo —no hay vector que
            # etiquetar— y porque el manifiesto del extractor las agrupa igual.
            sin_instantanea += 1
            continue
        utilizables += 1
        if resultado == GANADO:
            ganados += 1
        else:
            perdidos += 1

    alcanzado = (
        utilizables >= MINIMO_DE_CASOS
        and min(ganados, perdidos) >= MINIMO_POR_CLASE
    )
    return ProgresoDelReentrenamiento(
        cerrados=cerrados,
        utilizables=utilizables,
        ganados_utilizables=ganados,
        perdidos_utilizables=perdidos,
        sin_instantanea=sin_instantanea,
        de_un_vector_anterior=de_un_vector_anterior,
        version_del_vector=VERSION_DEL_VECTOR,
        minimo_de_casos=MINIMO_DE_CASOS,
        minimo_por_clase=MINIMO_POR_CLASE,
        alcanzado=alcanzado,
        faltan_casos=max(0, MINIMO_DE_CASOS - utilizables),
        faltan_ganados=max(0, MINIMO_POR_CLASE - ganados),
        faltan_perdidos=max(0, MINIMO_POR_CLASE - perdidos),
    )


# ==============================================================================
# El panel
# ==============================================================================

def _media(valores: List[float]) -> Optional[float]:
    return round(sum(valores) / len(valores), 1) if valores else None


def _cerrados(db: Session, desde: Optional[datetime.date], hasta: Optional[datetime.date]):
    consulta = db.query(Desenlace, Lead).join(Lead, Lead.id == Desenlace.lead_id)
    if desde is not None:
        consulta = consulta.filter(Desenlace.cerrado_el >= desde)
    if hasta is not None:
        # Inclusivo: `hasta` es un día entero, no su primer instante. Es el mismo criterio
        # que el informe de publicaciones, y la razón es que quien escribe una fecha en un
        # filtro espera que ese día cuente.
        consulta = consulta.filter(Desenlace.cerrado_el <= hasta)
    return consulta.order_by(Desenlace.cerrado_el.asc(), Desenlace.id.asc()).all()


def _atribucion(db: Session, lead_ids: List[int]) -> Dict[int, Tuple[Optional[str], str]]:
    """
    Por cada prospecto, `(slug de la publicación, red)` de la solicitud que lo trajo.

    La **primera** solicitud, no la última: la pregunta es de dónde salió esta persona, y
    quien respondió después a otros dos posts sigue habiendo llegado por el primero. El
    informe de cada publicación usa el criterio contrario —allí cada post ve a todo el que
    le respondió— y eso es correcto en los dos sitios porque son dos preguntas distintas;
    lo que no podía ser es que las dos respuestas se llamaran igual.

    Se recorre en Python en lugar de agrupar por el JSON en SQL: `activity_data` se
    consulta de forma distinta en PostgreSQL y en el SQLite de las pruebas, y esto tiene
    que dar lo mismo en los dos. Son las solicitudes de los prospectos **cerrados**, no las
    de la base entera.
    """
    if not lead_ids:
        return {}
    actividades = (
        db.query(LeadActivity)
        .filter(LeadActivity.source == FUENTE, LeadActivity.lead_id.in_(lead_ids))
        .order_by(LeadActivity.occurred_at.asc(), LeadActivity.id.asc())
        .all()
    )
    atribucion: Dict[int, Tuple[Optional[str], str]] = {}
    for actividad in actividades:
        if actividad.lead_id in atribucion:
            continue
        atribucion[actividad.lead_id] = (
            informe_de_publicaciones.slug_de(actividad),
            informe_de_publicaciones.red_de(actividad.activity_data or {}),
        )
    return atribucion


def _titulos(db: Session, slugs: List[str]) -> Dict[str, Campaign]:
    if not slugs:
        return {}
    return {
        c.public_slug: c
        for c in db.query(Campaign)
        .filter(Campaign.public_slug.in_(slugs), Campaign.channel == CANAL_LINKEDIN)
        .all()
    }


class _Cuenta:
    """Ganados, perdidos y scores de un grupo. Un acumulador, no una fila de la respuesta."""

    __slots__ = ("ganados", "perdidos", "scores")

    def __init__(self) -> None:
        self.ganados = 0
        self.perdidos = 0
        self.scores: List[float] = []

    def sumar(self, resultado: str, score: float) -> None:
        if resultado == GANADO:
            self.ganados += 1
        else:
            self.perdidos += 1
        self.scores.append(score)

    @property
    def total(self) -> int:
        return self.ganados + self.perdidos


def panel(
    db: Session,
    *,
    desde: Optional[datetime.date] = None,
    hasta: Optional[datetime.date] = None,
) -> PanelDeDesenlaces:
    """Los cierres del periodo, agrupados de las cinco maneras en que se preguntan."""
    filas = _cerrados(db, desde, hasta)
    lead_ids = [lead.id for _, lead in filas]
    atribucion = _atribucion(db, lead_ids)
    campanas = _titulos(db, sorted({slug for slug, _ in atribucion.values() if slug}))

    # Las fichas atribuidas a una campaña que nunca pasaron por la página de interés
    # —altas del CRM sobre una campaña, por ejemplo— también vienen de una publicación.
    # Se resuelven por `campaign_id`, que es el otro de los dos caminos que reconoce el
    # informe de publicaciones desde el capítulo 25.
    por_id = {
        c.id: c
        for c in db.query(Campaign).filter(Campaign.channel == CANAL_LINKEDIN).all()
    } if filas else {}

    por_motivo: Dict[Tuple[str, str], _Cuenta] = defaultdict(_Cuenta)
    por_tramo: Dict[str, int] = defaultdict(int)
    por_publicacion: Dict[Optional[int], _Cuenta] = defaultdict(_Cuenta)
    por_red: Dict[str, _Cuenta] = defaultdict(_Cuenta)
    por_categoria: Dict[ScoreCategory, _Cuenta] = defaultdict(_Cuenta)

    ganados: List[float] = []
    perdidos: List[float] = []

    for desenlace, lead in filas:
        score = float(desenlace.score_al_cierre or 0.0)
        resultado = desenlace.resultado

        por_motivo[(resultado, desenlace.motivo)].sumar(resultado, score)
        por_categoria[desenlace.categoria_al_cierre].sumar(resultado, score)
        if resultado == GANADO:
            ganados.append(score)
            if desenlace.tramo:
                por_tramo[desenlace.tramo] += 1
        else:
            perdidos.append(score)

        slug, red = atribucion.get(lead.id, (None, SIN_RED))
        campana = campanas.get(slug or "")
        if campana is None and lead.campaign_id in por_id:
            campana = por_id[lead.campaign_id]
        por_publicacion[campana.id if campana else None].sumar(resultado, score)
        # La red solo significa algo cuando la persona llegó por una publicación. Un
        # prospecto que entró por el CRM no llegó «sin red»: no llegó por ninguna red, y
        # meterlo en la misma fila que a quien abrió un enlace con el parámetro borrado
        # mezclaría dos cosas distintas bajo la misma etiqueta.
        if campana is not None or slug is not None:
            por_red[red].sumar(resultado, score)

    return PanelDeDesenlaces(
        desde=desde,
        hasta=hasta,
        resumen=ResumenDeDesenlaces(
            cerrados=len(filas),
            ganados=len(ganados),
            perdidos=len(perdidos),
            tasa_de_ganados=tasa(len(ganados), len(filas)),
            score_medio_de_los_ganados=_media(ganados),
            score_medio_de_los_perdidos=_media(perdidos),
        ),
        por_motivo=_filas_de_motivo(por_motivo, len(ganados), len(perdidos)),
        por_tramo=[
            FilaDeTramo(tramo=t.clave, etiqueta=t.etiqueta, casos=por_tramo.get(t.clave, 0))
            for t in TRAMOS
            if por_tramo.get(t.clave, 0)
        ],
        por_publicacion=_filas_por_publicacion(por_publicacion, por_id),
        por_red=_filas_por_red(por_red),
        acierto_del_score=_filas_de_acierto(por_categoria),
        reentrenamiento=progreso_del_reentrenamiento(db),
    )


def _filas_de_motivo(
    cuentas: Dict[Tuple[str, str], _Cuenta], ganados: int, perdidos: int
) -> List[FilaDeMotivo]:
    """
    Una fila por motivo con casos, en el orden de la lista cerrada.

    Solo los motivos que ocurrieron: una tabla con nueve filas a cero enseña la lista, no
    los datos, y el ojo se va a los huecos. Los que este código ya no conoce —una lista que
    se recortó— salen al final por su clave, porque esconderlos dejaría una tabla cuyas
    filas no suman el total.
    """
    filas: List[FilaDeMotivo] = []
    vistos = set()
    base = {GANADO: ganados, PERDIDO: perdidos}

    for resultado in RESULTADOS:
        for motivo in MOTIVOS[resultado]:
            cuenta = cuentas.get((resultado, motivo.clave))
            if cuenta is None:
                continue
            vistos.add((resultado, motivo.clave))
            filas.append(
                FilaDeMotivo(
                    resultado=resultado,
                    resultado_etiqueta=etiqueta_de_resultado(resultado),
                    motivo=motivo.clave,
                    motivo_etiqueta=motivo.etiqueta,
                    casos=cuenta.total,
                    porcentaje=tasa(cuenta.total, base.get(resultado, 0)),
                    score_medio=_media(cuenta.scores),
                )
            )

    for (resultado, clave), cuenta in sorted(cuentas.items()):
        if (resultado, clave) in vistos:
            continue
        filas.append(
            FilaDeMotivo(
                resultado=resultado,
                resultado_etiqueta=etiqueta_de_resultado(resultado),
                motivo=clave,
                motivo_etiqueta=etiqueta_de_motivo(resultado, clave),
                casos=cuenta.total,
                porcentaje=tasa(cuenta.total, base.get(resultado, 0)),
                score_medio=_media(cuenta.scores),
            )
        )
    return filas


def _filas_por_publicacion(
    cuentas: Dict[Optional[int], _Cuenta], campanas: Dict[int, Campaign]
) -> List[FilaPorPublicacion]:
    filas = [
        FilaPorPublicacion(
            publicacion_id=publicacion_id,
            titulo=(
                campanas[publicacion_id].name
                if publicacion_id in campanas
                else SIN_PUBLICACION
            ),
            ganados=cuenta.ganados,
            perdidos=cuenta.perdidos,
            tasa_de_ganados=tasa(cuenta.ganados, cuenta.total),
            score_medio_al_cierre=_media(cuenta.scores),
        )
        for publicacion_id, cuenta in cuentas.items()
    ]
    # Por ganados y después por total: la primera pregunta del líder es de dónde salen los
    # tratos. «Sin publicación» al final, aunque sea la fila más grande: es el resto, no un
    # origen.
    filas.sort(key=lambda f: (f.publicacion_id is None, -f.ganados, -(f.ganados + f.perdidos)))
    return filas


def _filas_por_red(cuentas: Dict[str, _Cuenta]) -> List[FilaPorRed]:
    claves = [c for c in ORDEN_DE_REDES if c in cuentas]
    claves += [c for c in sorted(cuentas) if c not in claves]
    return [
        FilaPorRed(
            red=clave,
            etiqueta=etiqueta_de_red(clave),
            ganados=cuentas[clave].ganados,
            perdidos=cuentas[clave].perdidos,
            tasa_de_ganados=tasa(cuentas[clave].ganados, cuentas[clave].total),
            score_medio_al_cierre=_media(cuentas[clave].scores),
        )
        for clave in claves
    ]


def _filas_de_acierto(cuentas: Dict[ScoreCategory, _Cuenta]) -> List[FilaDeAcierto]:
    """
    Las tres categorías, siempre, aunque alguna esté vacía.

    Aquí sí se enseñan las filas a cero, al revés que en los motivos: la pregunta es si los
    HOT se ganan más que los COLD, y una tabla a la que le falta la fila de los COLD invita
    a leer la comparación que precisamente no se puede hacer.
    """
    return [
        FilaDeAcierto(
            categoria=categoria,
            casos=cuentas[categoria].total if categoria in cuentas else 0,
            ganados=cuentas[categoria].ganados if categoria in cuentas else 0,
            perdidos=cuentas[categoria].perdidos if categoria in cuentas else 0,
            tasa_de_ganados=(
                tasa(cuentas[categoria].ganados, cuentas[categoria].total)
                if categoria in cuentas
                else None
            ),
        )
        for categoria in (ScoreCategory.HOT, ScoreCategory.WARM, ScoreCategory.COLD)
    ]


__all__ = [
    "CierreInvalido",
    "SIN_PUBLICACION",
    "es_utilizable",
    "opciones",
    "panel",
    "progreso_del_reentrenamiento",
    "registrar_cierre",
]
