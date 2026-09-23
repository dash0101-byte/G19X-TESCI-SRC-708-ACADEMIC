"""
Lo que el panel recibe de la agenda del día (capítulo 28).

De cada prospecto viaja lo justo para poder decidir y para poder abrirlo: nombre, empresa,
score y su identificador. Ni el correo ni el teléfono: la bandeja es una lista de trabajo,
no un directorio, y quien necesita llamar abre la ficha, donde ese acceso ya queda
registrado como acceso a la ficha.
"""
import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.entities import ScoreCategory


class ProspectoDeLaAgenda(BaseModel):
    """El prospecto, visto desde la lista de trabajo."""
    id: int
    nombre: str
    empresa: Optional[str] = None
    score: float
    categoria: ScoreCategory
    # Para poder decir «lleva dormido desde…» sin volver a preguntar.
    dormido_desde: Optional[datetime.datetime] = None


class TareaDeLaAgenda(BaseModel):
    id: int
    regla: str
    # La etiqueta viaja resuelta: el cliente no tiene que saberse el vocabulario, y una
    # regla que este código no conoce se enseña por su clave en vez de dejar un hueco.
    regla_etiqueta: str
    motivo: str
    estado: str
    vence_el: datetime.datetime
    # Calculado en el servidor: «vencida» depende de la hora de ahora, y dos relojes —el del
    # navegador y el del servidor— darían dos respuestas distintas a la misma pregunta.
    vencida: bool
    creada_en: datetime.datetime
    prospecto: ProspectoDeLaAgenda


class BandejaDeHoy(BaseModel):
    """Lo que le toca hoy a una persona, ordenado por score."""
    asesor_id: int
    tareas: List[TareaDeLaAgenda] = Field(default_factory=list)
    vencidas: int = 0
    para_hoy: int = 0
    # Abiertas que todavía no tocan. Se cuentan pero no se enseñan: saber que hay trabajo
    # más adelante tranquiliza; verlo hoy, en cambio, convierte la bandeja en otra lista
    # larga que nadie termina.
    mas_adelante: int = 0


class AvisoDeLaAgenda(BaseModel):
    id: int
    regla: str
    regla_etiqueta: str
    texto: str
    creado_en: datetime.datetime
    leido_en: Optional[datetime.datetime] = None
    prospecto: ProspectoDeLaAgenda


class Campana(BaseModel):
    """La campana: cuántos sin leer y los últimos, leídos o no."""
    sin_leer: int = 0
    avisos: List[AvisoDeLaAgenda] = Field(default_factory=list)


class HotQueSeEnfria(BaseModel):
    """Un HOT que lleva demasiado sin contacto, y con quién está."""
    prospecto: ProspectoDeLaAgenda
    asesor_id: Optional[int] = None
    asesor: Optional[str] = None
    horas_sin_contacto: int
    avisado_al_asesor: bool
    avisado_al_lider: bool


class HotQueSeEnfrian(BaseModel):
    total: int = 0
    filas: List[HotQueSeEnfria] = Field(default_factory=list)


class TareaCerrada(BaseModel):
    id: int
    estado: str
    cerrada_en: datetime.datetime


class AvisosLeidos(BaseModel):
    leidos: int
