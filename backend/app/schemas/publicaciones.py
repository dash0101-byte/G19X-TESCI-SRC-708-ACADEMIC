"""
Lo que se enseña de una publicación por dentro: de dónde llegó una ficha y qué dio cada post.

Son esquemas de **lectura**. Ninguno entra por el cuerpo de una petición, así que no llevan
validadores de entrada: lo que traen ya pasó por el registro de actividad o por el alta de
la campaña.

Dos decisiones que se ven en los campos:

* `de_otros_asesores` es un número y nunca una lista. Un asesor ve sus prospectos y cuántos
  más hay; los nombres del resto de la cartera no salen del servidor, ni siquiera
  recortados. Un nombre y una empresa bastan para reconstruir a quién atiende la
  competencia interna, y ese era justo el agujero que cerró el alcance de cartera.
* La tarjeta «Llegó por» no tiene versión «vacía». Cuando no hay solicitudes es `None` y la
  ficha no pinta nada, en lugar de una tarjeta con guiones que hace pensar que se perdió un
  dato.
"""
import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.entities import LeadStatus, ScoreCategory


class SolicitudDeLaFicha(BaseModel):
    """
    Una solicitud recibida por una publicación, tal como se le enseña al asesor.

    `aviso_aceptado_en` es el de **esta** solicitud, no el de la ficha. La ficha guarda el
    primero (no se pisa nunca); aquí interesa el de cada envío, porque cada uno se hizo
    aceptando el aviso por separado y esa es la pregunta que llega desde fuera: «¿cuándo
    consintió esta persona que le escribiéramos por esto?».
    """
    publicacion_id: Optional[int] = None
    titulo: Optional[str] = None
    enlace: Optional[str] = None
    recibida_en: datetime.datetime
    necesidad: Optional[str] = None
    aviso_aceptado_en: Optional[datetime.datetime] = None
    # Por dónde llegó esta solicitud: «WhatsApp», «Facebook»… o «Sin red» cuando no consta.
    # Es de cada envío, como la necesidad: la misma persona puede volver por otra red.
    red: str = "Sin red"


class LlegoPor(BaseModel):
    """
    De dónde salió esta ficha. Solo existe si hubo al menos una solicitud por la página.

    El perfil de LinkedIn va aquí y no en cada solicitud porque es de la persona, no del
    envío: la ficha guarda el que llegó primero y los envíos posteriores no lo pisan
    (`actualiza_prospecto=False`). Enseñar uno por fila sugeriría un historial de perfiles
    que el sistema no tiene.
    """
    perfil_de_linkedin: Optional[str] = None
    solicitudes: List[SolicitudDeLaFicha] = Field(default_factory=list)


class PublicacionDelInforme(BaseModel):
    id: int
    titulo: str
    enlace: str
    activa: bool
    estado: str = "activa"
    # El post ya publicado en LinkedIn, comprobado como de linkedin.com al guardarlo.
    url_del_post: Optional[str] = None
    responsable: Optional[str] = None


class ResumenDePublicacion(BaseModel):
    """
    La cabecera del informe, **calculada sobre lo que ve quien pregunta**.

    Para el líder y el administrador eso es la publicación entera. Para un asesor son sus
    prospectos, y `de_otros_asesores` dice cuántos más hay sin decir quiénes. La alternativa
    —enseñarle la media global— repetiría el fallo que ya se corrigió en el resumen del
    tablero: un total y una media describen el tamaño y la salud de la cartera ajena sin
    abrir una sola ficha.
    """
    perfiles_recibidos: int
    avanzaron_de_etapa: int
    # `None` sin perfiles recibidos, por lo mismo que `tasa_de_envio` es `None`
    # sin visitas: la media de un conjunto vacío no es un cero, y las dos cifras
    # van una al lado de la otra.
    score_medio: Optional[float] = None
    de_otros_asesores: int = 0
    alcance_completo: bool = True
    # Totales de la publicación en el periodo, sin nombres: cuántas veces se abrió la página
    # y cuántas solicitudes se enviaron **desde que se cuentan visitas**. `tasa_de_envio` es
    # envíos entre visitas, en tanto por ciento; `None` sin visitas, porque dividir entre cero
    # no es un 0 %. Puede pasar de 100: quien corrige un error y vuelve a enviar lo hace sin
    # volver a abrir la página.
    visitas: int = 0
    envios: int = 0
    tasa_de_envio: Optional[float] = None


class DiaDelInforme(BaseModel):
    """Un día del gráfico: perfiles recibidos (los que ve quien pregunta) y visitas."""
    dia: datetime.date
    perfiles: int = 0
    visitas: int = 0


class FilaDeRed(BaseModel):
    """
    Una red en el informe: qué trajo por sí sola.

    `visitas` es de la publicación entera —un contador agregado no sabe de carteras—, pero
    `perfiles` y `score_medio` se calculan **sobre lo que ve quien pregunta**, igual que el
    resumen. Para un asesor eso son los suyos, así que su tasa por red describe su parte y
    no la del equipo; `alcance_completo` en el resumen dice cuál de las dos está viendo.
    """
    red: str
    etiqueta: str
    visitas: int = 0
    perfiles: int = 0
    envios: int = 0
    tasa_de_envio: Optional[float] = None
    score_medio: Optional[float] = None


class FilaDelInforme(BaseModel):
    lead_id: int
    nombre: str
    empresa: Optional[str] = None
    cargo: Optional[str] = None
    score: float
    categoria: ScoreCategory
    etapa: LeadStatus
    asesor: Optional[str] = None
    recibida_en: datetime.datetime
    # Lo que dijo necesitar en su última solicitud a esta publicación. Informa; no puntúa.
    necesidad: Optional[str] = None


class InformeDePublicacion(BaseModel):
    publicacion: PublicacionDelInforme
    resumen: ResumenDePublicacion
    filas: List[FilaDelInforme] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
    # Perfiles recibidos por día. Como mucho los últimos `MAX_DIAS_DEL_GRAFICO`; si el
    # periodo es más largo, `grafico_recortado` lo dice.
    por_dia: List[DiaDelInforme] = Field(default_factory=list)
    grafico_recortado: bool = False
    # Una fila por red de difusión, y una más para «Sin red» si algo llegó sin ella. Es la
    # comparativa entre redes de esta publicación: cuál trajo visitas y cuál trajo perfiles,
    # que no siempre son la misma.
    por_red: List[FilaDeRed] = Field(default_factory=list)


class FilaDeComparativa(BaseModel):
    publicacion_id: int
    titulo: str
    activa: bool
    estado: str = "activa"
    perfiles_recibidos: int
    avanzaron_de_etapa: int
    score_medio: Optional[float] = None
    visitas: int = 0
    envios: int = 0
    tasa_de_envio: Optional[float] = None


class ComparativaDePublicaciones(BaseModel):
    items: List[FilaDeComparativa] = Field(default_factory=list)


class NuevosSinAsesor(BaseModel):
    """
    Cuántos prospectos de LinkedIn están esperando a que alguien los atienda.

    Es el contador del líder: la página de interés crea fichas sin asesor a propósito
    —repartir cartera es una decisión suya, no del formulario— y sin este número nadie se
    entera de que hay trabajo sin repartir hasta que alguien mira el listado.
    """
    total: int


class EstadoDeLaDireccionPublica(BaseModel):
    """
    Si la dirección pública configurada sigue llevando aquí (capítulo 34).

    `responde` tiene tres valores y el tercero importa: `None` es «no se ha preguntado»,
    que es lo que devuelve un despliegue con la comprobación apagada —desarrollo, la
    suite—. Colapsarlo en `False` encendería una alarma permanente en pantallas donde no
    hay nada que avisar, y una alarma siempre encendida deja de leerse.
    """

    base: str = Field(description="La dirección configurada, que es la que llevan los enlaces.")
    responde: Optional[bool] = Field(
        None, description="True, False, o None si la comprobación está apagada."
    )
    comprobada_en: Optional[datetime.datetime] = None
    detalle: Optional[str] = Field(
        None, description="Código de respuesta o tipo de error; nunca el cuerpo."
    )
    # Cuántas publicaciones llevan un enlace repartido que ya no lleva aquí. Va junto al
    # estado y no en el listado porque es la cifra que hace falta para decidir: una sola
    # caducada puede ser una prueba vieja; catorce es que la dirección cambió y hay que
    # volver a repartir.
    publicaciones_con_enlace_caducado: int = 0
