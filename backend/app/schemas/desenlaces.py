"""
Lo que viaja al cerrar un prospecto y lo que devuelve el panel de desenlaces (capítulo 30).

Dos decisiones gobiernan este esquema:

**Ningún campo de texto libre.** No es una omisión: es la regla del capítulo. El cierre se
describe con tres claves de listas cerradas (`resultado`, `motivo`, `tramo`) y una fecha.
Un `comentario` opcional habría sido cómodo de añadir y habría llevado el nombre de una
persona, o lo que dijo por teléfono, a la tabla que alimenta al modelo. La guarda del CI
comprueba que este esquema no gana campos de texto sin que nadie lo note.

**El panel no lleva a nadie dentro.** Todo lo que devuelve son totales: por motivo, por
tramo, por publicación, por red y por categoría de score. Ni un nombre, ni un correo, ni
una fila con un prospecto. Quien necesita ver a las personas concretas tiene el listado y
la ficha, donde ese acceso queda registrado como lo que es.
"""
import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, computed_field, model_validator

from app.core.desenlaces import (
    GANADO,
    RESULTADOS,
    es_motivo_de,
    es_resultado,
    es_tramo,
    etiqueta_de_motivo,
    etiqueta_de_resultado,
    etiqueta_de_tramo,
    motivos_de,
)
from app.models.entities import LeadStatus, ScoreCategory

# ============================================================================
# Las opciones que ofrece el formulario
# ============================================================================

class OpcionDeMotivo(BaseModel):
    clave: str
    etiqueta: str
    descripcion: str


class OpcionDeResultado(BaseModel):
    clave: str
    etiqueta: str
    motivos: List[OpcionDeMotivo]
    # Si este resultado pide además el tramo del acuerdo. Lo dice el servidor y no lo
    # deduce el cliente de que la clave sea «ganado»: la misma regla la aplica la
    # validación de entrada, y dos copias acabarían discrepando.
    pide_tramo: bool


class OpcionDeTramo(BaseModel):
    clave: str
    etiqueta: str


class OpcionesDeCierre(BaseModel):
    """
    Las listas cerradas, servidas por el servidor.

    El cliente no se las sabe de memoria a propósito. Cuando el formulario llevaba sus
    propias listas —como pasó con las necesidades de las publicaciones hasta el capítulo
    26—, añadir un motivo exigía tocar dos sitios y olvidarse de uno no rompía nada: el
    panel simplemente dejaba de ver esa opción.
    """
    resultados: List[OpcionDeResultado]
    tramos: List[OpcionDeTramo]


# ============================================================================
# El cierre
# ============================================================================

class CierreDelProspecto(BaseModel):
    """
    Lo que hay que decir para cerrar un prospecto.

    La validación cruzada vive aquí y no en el servicio porque es una propiedad de la
    forma del dato —un perdido no tiene tamaño de acuerdo—, y ponerla aquí la convierte en
    un 422 que señala el campo en lugar de un 400 con una frase. Lo que sí queda para el
    servicio es lo que necesita la base: que la fecha de cierre no sea anterior al alta del
    prospecto.
    """
    resultado: str = Field(..., description="«ganado» o «perdido».")
    motivo: str = Field(..., description="Clave de la lista cerrada de ese resultado.")
    cerrado_el: datetime.date = Field(..., description="El día en que se cerró, no el de hoy.")
    tramo: Optional[str] = Field(
        None, description="Tramo del acuerdo. Obligatorio en los ganados, ausente en los perdidos."
    )

    @model_validator(mode="after")
    def _comprobar(self) -> "CierreDelProspecto":
        if not es_resultado(self.resultado):
            raise ValueError(
                f"«{self.resultado}» no es un desenlace. Los desenlaces son: {', '.join(RESULTADOS)}."
            )
        if not es_motivo_de(self.resultado, self.motivo):
            validos = ", ".join(m.clave for m in motivos_de(self.resultado))
            raise ValueError(
                f"«{self.motivo}» no es un motivo de un prospecto {etiqueta_de_resultado(self.resultado).lower()}. "
                f"Los motivos son: {validos}."
            )

        # Una fecha de cierre en el futuro no es un caso de negocio: es una errata de
        # teclado. Se rechaza aquí y no se recorta a hoy en silencio, porque recortar
        # dejaría en la base una fecha que nadie escribió.
        if self.cerrado_el > datetime.datetime.now(datetime.timezone.utc).date():
            raise ValueError("La fecha de cierre no puede ser posterior a hoy.")

        if self.resultado == GANADO:
            if not self.tramo:
                raise ValueError(
                    "Un prospecto ganado necesita el tramo del acuerdo. Si todavía no se "
                    "sabe, el tramo es «no_consta»: eso es un dato, y una cifra inventada no."
                )
            if not es_tramo(self.tramo):
                raise ValueError(f"«{self.tramo}» no es un tramo de la lista.")
        elif self.tramo:
            raise ValueError(
                "Un prospecto perdido no tiene tamaño de acuerdo. Anotar «lo que habríamos "
                "facturado» sería una previsión de ingresos inventada."
            )
        return self


class DesenlaceDeLaFicha(BaseModel):
    """
    Cómo acabó un prospecto, resuelto para la pantalla.

    Los campos son **exactamente** las columnas de la tabla, y las etiquetas se calculan
    aquí a partir de las claves. Eso es lo que permite que la ficha 360 lo rellene sola al
    validar el prospecto —la relación se llama igual que el campo— en lugar de tener que
    acordarse de pedirlo en cada endpoint que devuelve una ficha. El día que apareciera un
    tercer sitio que devuelve fichas, el desenlace viajaría en él sin tocar nada.

    Las etiquetas no se guardan: se resuelven. Una lista que cambia de nombre no puede
    exigir una migración de datos, que es el mismo criterio de las reglas de la agenda, las
    necesidades de una publicación y las redes de difusión.
    """
    resultado: str
    motivo: str
    cerrado_el: datetime.date
    tramo: Optional[str] = None
    score_al_cierre: float
    categoria_al_cierre: ScoreCategory
    registrado_en: datetime.datetime

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def resultado_etiqueta(self) -> str:
        return etiqueta_de_resultado(self.resultado)

    @computed_field
    @property
    def motivo_etiqueta(self) -> str:
        """
        El nombre del motivo, o su clave si este código no la conoce.

        Una clave desconocida —una fila escrita por una versión posterior, o por una lista
        que se recortó— se enseña tal cual en lugar de dejar un hueco: un hueco se lee como
        un dato perdido.
        """
        return etiqueta_de_motivo(self.resultado, self.motivo)

    @computed_field
    @property
    def tramo_etiqueta(self) -> Optional[str]:
        return etiqueta_de_tramo(self.tramo) if self.tramo else None


class DesenlaceRegistrado(DesenlaceDeLaFicha):
    """
    Lo mismo, más lo que solo significa algo en el segundo exacto del cierre.

    Hereda en lugar de repetir los campos porque las etiquetas tienen que resolverse igual
    en los dos sitios: dos copias de «cómo se llama este motivo» acabarían discrepando el
    día que una lista cambie.
    """
    lead_id: int
    etapa: LeadStatus
    version_del_vector: Optional[int] = None
    # Si este cierre sirve tal cual como ejemplo de entrenamiento: hay instantánea de
    # entrada y es de la versión vigente del vector. Se dice aquí, en el momento de
    # cerrar, y no solo en el panel, porque es cuando alguien puede hacer algo al respecto.
    utilizable_para_reentrenar: bool
    # Cuántas tareas abiertas dejaron de tener sentido al cerrar. Se devuelve para que la
    # pantalla pueda decirlo: si no, el asesor ve desaparecer trabajo de su bandeja sin
    # ninguna explicación.
    tareas_descartadas: int = 0


# ============================================================================
# El panel
# ============================================================================

class ResumenDeDesenlaces(BaseModel):
    cerrados: int = 0
    ganados: int = 0
    perdidos: int = 0
    # `None` sin base: «ninguno de cero» no es un cero por ciento.
    tasa_de_ganados: Optional[float] = None
    score_medio_de_los_ganados: Optional[float] = None
    score_medio_de_los_perdidos: Optional[float] = None


class FilaDeMotivo(BaseModel):
    resultado: str
    resultado_etiqueta: str
    motivo: str
    motivo_etiqueta: str
    casos: int
    # Sobre el total de **su** resultado, no sobre todos los cierres: la pregunta es «de lo
    # que perdemos, cuánto se va por precio», y dividir entre ganados y perdidos juntos
    # daría un número que no responde a ninguna pregunta.
    porcentaje: Optional[float] = None
    score_medio: Optional[float] = None


class FilaDeTramo(BaseModel):
    tramo: str
    etiqueta: str
    casos: int


class FilaPorPublicacion(BaseModel):
    publicacion_id: Optional[int] = None
    titulo: str
    ganados: int = 0
    perdidos: int = 0
    tasa_de_ganados: Optional[float] = None
    score_medio_al_cierre: Optional[float] = None


class FilaPorRed(BaseModel):
    red: str
    etiqueta: str
    ganados: int = 0
    perdidos: int = 0
    tasa_de_ganados: Optional[float] = None
    score_medio_al_cierre: Optional[float] = None


class FilaDeAcierto(BaseModel):
    """
    Cuántos se ganaron y cuántos se perdieron en cada categoría **del momento del cierre**.

    Es la respuesta a «¿el score acertaba?», y es una tabla y no un veredicto a propósito:
    con doce cierres cualquier conclusión sobre la calidad del modelo sería una anécdota
    con decimales. Por eso cada tasa viaja con el número de casos que hay detrás.
    """
    categoria: ScoreCategory
    casos: int = 0
    ganados: int = 0
    perdidos: int = 0
    tasa_de_ganados: Optional[float] = None


class ProgresoDelReentrenamiento(BaseModel):
    """
    Cuántos cierres hay y cuántos exige el reentrenamiento.

    Un contador, no un botón. Este capítulo **no reentrena**: no toca el artefacto, no
    escribe en el registro de modelos y no genera el CSV. Lo único que hace es dejar de ser
    imposible saber cuánto falta.
    """
    cerrados: int = 0
    # De los cerrados, los que sirven tal cual como ejemplo: con instantánea de entrada de
    # la versión vigente del vector.
    utilizables: int = 0
    ganados_utilizables: int = 0
    perdidos_utilizables: int = 0
    # Parte de los cerrados que no son utilizables, desglosada para que la merma se vea.
    sin_instantanea: int = 0
    de_un_vector_anterior: int = 0
    version_del_vector: int
    minimo_de_casos: int
    minimo_por_clase: int
    alcanzado: bool = False
    faltan_casos: int = 0
    faltan_ganados: int = 0
    faltan_perdidos: int = 0


class PanelDeDesenlaces(BaseModel):
    desde: Optional[datetime.date] = None
    hasta: Optional[datetime.date] = None
    resumen: ResumenDeDesenlaces
    por_motivo: List[FilaDeMotivo] = Field(default_factory=list)
    por_tramo: List[FilaDeTramo] = Field(default_factory=list)
    por_publicacion: List[FilaPorPublicacion] = Field(default_factory=list)
    por_red: List[FilaPorRed] = Field(default_factory=list)
    acierto_del_score: List[FilaDeAcierto] = Field(default_factory=list)
    # El contador NO se acota por el periodo del panel, y el campo lleva su propia
    # explicación porque la diferencia se presta a confusión: filtrar por fechas responde
    # «cómo fue este trimestre», y el reentrenamiento se alimenta de todo lo que hay.
    reentrenamiento: ProgresoDelReentrenamiento
