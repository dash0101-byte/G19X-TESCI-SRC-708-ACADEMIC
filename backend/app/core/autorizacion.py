"""
Alcance de cartera: qué prospectos puede ver y tocar quien está pidiendo.

El sistema tenía control de acceso por **endpoint** —quién puede llamar a `PUT
/leads/{id}`— y ninguno por **objeto**: cuál de todos los prospectos. Un asesor comercial
autenticado veía la cartera completa de la empresa y podía abrir el detalle de cualquier
prospecto ajeno. El rol decidía qué verbos podía usar, no sobre qué.

La decisión de fondo de este módulo es *dónde* se aplica el filtro. Ponerlo en cada
endpoint funciona hasta que alguien añade el siguiente y se olvida, y ese olvido no
produce ningún error: produce una consulta que devuelve de más. Los fallos de
autorización son silenciosos por naturaleza —nadie recibe un 500 porque le enseñaron
datos ajenos—, así que el único sitio donde ponerlo es aquel por el que hay que pasar
obligatoriamente para llegar a los datos. Aquí eso es el repositorio.

De ahí la forma del constructor de `LeadRepository`: el alcance es un argumento
**obligatorio**. No hay valor por defecto y no puede haberlo. Un `alcance=None` que
significara «toda la cartera» convertiría el olvido en acceso total, que es exactamente
el fallo que este módulo existe para impedir. Quien olvida el alcance recibe un
`TypeError` en la primera línea, no datos de más.

Las tareas que no tienen usuario detrás —el webhook del CRM, el recálculo masivo— usan
`AlcanceDeCartera.del_sistema(motivo)`, que sí ve todo. Es explícito y pide un motivo por
escrito precisamente para que abrirlo cueste una frase y se note en la revisión.
"""
from __future__ import annotations

from typing import Optional

from app.core.security import CurrentUser, UserRole, get_current_user
from fastapi import Depends

# Roles que trabajan sobre la cartera completa. `Commercial_Executive` no está: atiende a
# los suyos.
ROLES_CON_CARTERA_COMPLETA = frozenset({UserRole.SALES_LEAD, UserRole.SYSTEM_ADMIN})


class AlcanceDeCartera:
    """
    Franja de prospectos accesible para quien hace la petición.

    Solo dos formas: la de una persona (`de`) y la de un proceso sin persona detrás
    (`del_sistema`). No se construye a mano desde el código de negocio.
    """

    __slots__ = ("usuario_id", "toda_la_cartera", "motivo")

    def __init__(self, *, usuario_id: Optional[int], toda_la_cartera: bool, motivo: str):
        self.usuario_id = usuario_id
        self.toda_la_cartera = toda_la_cartera
        self.motivo = motivo

    # ------------------------------------------------------------------ fábricas
    @classmethod
    def de(cls, actor: CurrentUser) -> "AlcanceDeCartera":
        """Alcance derivado del token de quien pide. Es el camino normal."""
        completo = actor.role in ROLES_CON_CARTERA_COMPLETA
        try:
            usuario_id = int(actor.user_id)
        except (TypeError, ValueError):
            # Un `sub` que no es un entero no puede corresponder a ningún dueño. Se deja
            # en None y, sin cartera completa, el alcance no alcanza a nada: fallar
            # cerrado es la única opción defendible cuando no se sabe quién pregunta.
            usuario_id = None
        return cls(
            usuario_id=usuario_id,
            toda_la_cartera=completo,
            motivo=f"{actor.email} ({actor.role.value})",
        )

    @classmethod
    def del_sistema(cls, motivo: str) -> "AlcanceDeCartera":
        """
        Alcance sin persona detrás: ingesta del CRM, recálculos masivos, sembrado.

        Pide un motivo por escrito a propósito. Es la única puerta que ve toda la cartera
        sin un token que lo justifique, y quien la use tiene que decir para qué.
        """
        if not motivo or not motivo.strip():
            raise ValueError(
                "Un alcance de sistema necesita un motivo escrito: es la única vía que "
                "ve la cartera completa sin un usuario que responda por ella."
            )
        return cls(usuario_id=None, toda_la_cartera=True, motivo=f"sistema: {motivo}")

    # ------------------------------------------------------------------ consultas
    def alcanza(self, assigned_rep_id: Optional[int]) -> bool:
        """¿Entra este prospecto en el alcance?"""
        if self.toda_la_cartera:
            return True
        if self.usuario_id is None:
            return False
        return assigned_rep_id == self.usuario_id

    def puede_reasignar(self) -> bool:
        """
        Cambiar de dueño un prospecto es repartir trabajo, no atenderlo.

        Un asesor que pudiera reasignar podría quitarse de encima lo que no le apetece o
        apropiarse de lo ajeno, y en ambos casos el prospecto sale de la vista de quien
        respondía por él.
        """
        return self.toda_la_cartera

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        franja = "toda la cartera" if self.toda_la_cartera else f"usuario {self.usuario_id}"
        return f"<AlcanceDeCartera({franja}; {self.motivo})>"


class FueraDeAlcance(Exception):
    """
    El prospecto existe pero no pertenece a quien lo pide.

    La capa HTTP la traduce a **404**, no a 403. Un 403 confirmaría que ese identificador
    corresponde a un prospecto real, y recorrer los identificadores es barato: distinguir
    «no existe» de «no es tuyo» permite reconstruir el tamaño y la forma de la cartera
    ajena sin ver un solo dato. Hacia fuera, un prospecto que no es tuyo no existe.

    Hacia dentro sí se distingue: el intento queda en la bitácora con su acción propia,
    porque un asesor tanteando identificadores que no le corresponden es justo lo que hay
    que poder ver después.
    """

    def __init__(self, lead_id: Optional[int] = None):
        self.lead_id = lead_id
        super().__init__(f"El prospecto {lead_id} no está en el alcance de quien lo solicita.")


def alcance_actual(
    current_user: CurrentUser = Depends(get_current_user),
) -> AlcanceDeCartera:
    """
    Dependencia de FastAPI: el alcance de quien hace esta petición.

    Se declara junto a `AlcanceDeCartera` y no en cada módulo de endpoints para que haya
    una sola forma de obtenerlo. Un endpoint que construyera el suyo a mano podría
    construirlo mal, y el fallo sería invisible.
    """
    return AlcanceDeCartera.de(current_user)
