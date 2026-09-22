from app.core.database import get_db
from app.core.rate_limit import limiter, predict_limit
from app.core.security import CurrentUser, get_current_user
from app.schemas.score import ScorePredictRequest, ScoreResult
from app.services.scoring_service import ScoringService
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

router = APIRouter()


@router.post("/predict", response_model=ScoreResult)
@limiter.limit(predict_limit)
async def predict_lead_score(
    request: Request,
    response: Response,
    payload: ScorePredictRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Simula e infiere en tiempo real la calificación inteligente y explicabilidad de un
    prospecto sin necesidad de persistirlo previamente en la base de datos.

    Es la ruta más cara del sistema —ejecuta inferencia y generación de texto en cada
    llamada— y basta un token válido para invocarla en bucle, de ahí el límite por IP.

    El cuerpo se llama `payload` y no `request` porque ese nombre lo reclama slowapi para
    el objeto `Request` de Starlette; `response` también es suyo, para inyectar las
    cabeceras `X-RateLimit-*` con el cupo restante.
    """
    scoring_svc = ScoringService(db)
    return await scoring_svc.predict_standalone(payload.model_dump())
