from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.api import deps
from typing import Any

router = APIRouter()


def _get_ml_service():
    try:
        from app.services.ml_service import MLService
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="ML features are unavailable in this deployment",
        ) from exc
    return MLService


@router.get("/battery-health/{battery_id}/predict")
def predict_battery_health(
    battery_id: int,
    db: Session = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Predict SoH and failure risk for a specific battery using ML.
    """
    MLService = _get_ml_service()

    prediction = MLService.get_battery_health_prediction(db, battery_id)
    if "error" in prediction:
        raise HTTPException(status_code=404, detail=prediction["error"])
    return prediction

@router.get("/demand/forecast/{station_id}")
def forecast_demand(
    station_id: int,
    db: Session = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Generate a 7-day demand forecast for a station.
    """
    MLService = _get_ml_service()

    return MLService.get_demand_forecast(db, station_id)
