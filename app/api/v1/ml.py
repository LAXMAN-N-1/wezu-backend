from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.api import deps
from typing import Any

router = APIRouter()

@router.get("/battery-health/{battery_id}/predict")
def predict_battery_health(
    battery_id: int,
    db: Session = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Predict SoH and failure risk for a specific battery using ML.
    """
    from app.services.ml_service import MLService

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
    from app.services.ml_service import MLService

    return MLService.get_demand_forecast(db, station_id)
