import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.entities import JobStatus


class RecalculationJobRequest(BaseModel):
    """Parámetros con los que se lanza un recálculo masivo."""

    model_config = ConfigDict(extra="forbid")

    batch_size: int = Field(
        default=100,
        ge=1,
        le=1000,
        description=(
            "Prospectos por lote y por transacción. Más grande reduce viajes a la base "
            "pero alarga los bloqueos y tira más trabajo hecho si un lote falla."
        ),
    )


class RecalculationJobStatus(BaseModel):
    """Estado de un trabajo de recálculo, tal como lo ve quien lo consulta."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    job_type: str
    status: JobStatus
    total_leads: int
    processed_leads: int
    failed_leads: int
    batch_size: int
    requested_by: Optional[str] = None
    # Solo se rellena cuando el trabajo termina en FAILED; en el resto de estados es nulo.
    error_message: Optional[str] = None
    created_at: datetime.datetime
    started_at: Optional[datetime.datetime] = None
    finished_at: Optional[datetime.datetime] = None

    # --- Señales de vida ---
    # Se publican porque son lo único que distingue «avanzando despacio» de «muerto hace
    # media hora», y esa distinción la tiene que poder hacer quien mira, no solo el
    # barrido interno. `worker_id` dice además en qué contenedor mirar.
    heartbeat_at: Optional[datetime.datetime] = None
    lease_until: Optional[datetime.datetime] = None
    worker_id: Optional[str] = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def progress_percentage(self) -> float:
        """
        Avance en porcentaje, calculado aquí y no guardado en la tabla.

        Es `computed_field` y no un `property` a secas para que salga en la respuesta:
        un `property` normal en Pydantic v2 se queda fuera del serializado, y el cliente
        que consulta el estado tendría que dividir los dos contadores por su cuenta.

        Sin prospectos que recorrer el trabajo está completo por definición, no al 0 %.
        """
        if self.total_leads <= 0:
            return 100.0
        return round(self.processed_leads / self.total_leads * 100.0, 1)
