"""
Advanced Analytics API
TimescaleDB analytics and ML fraud detection
"""
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session
from pydantic import BaseModel
from datetime import datetime, timedelta

from app.api import deps
from app.db.session import get_session
from app.models.user import User
from app.services.timescale_service import timescale_service
from app.services.ml_fraud_service import MLFraudDetectionService
from app.schemas.common import DataResponse

router = APIRouter()

# TimescaleDB Endpoints
@router.get("/timeseries/battery-health/{battery_id}", response_model=DataResponse[list])
def get_battery_health_timeseries(
    battery_id: int,
    hours: int = Query(24, ge=1, le=168),
    interval: str = Query("1 hour", regex="^(1 hour|6 hours|1 day)$"),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get battery health time-series data
    Aggregated by specified interval
    """
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)
    
    data = timescale_service.get_battery_health_timeseries(
        battery_id=battery_id,
        start_time=start_time,
        end_time=end_time,
        interval=interval
    )
    
    return DataResponse(
        success=True,
        data=data
    )

@router.get("/realtime/system-stats", response_model=DataResponse[dict])
def get_realtime_stats(current_user: User = Depends(deps.get_current_user)):
    """
    Get real-time system statistics
    Active rentals, revenue, battery health, etc.
    """
    stats = timescale_service.get_realtime_analytics()
    
    return DataResponse(
        success=True,
        data=stats
    )

# ML Fraud Detection Endpoints
@router.get("/fraud/risk-score", response_model=DataResponse[dict])
def get_user_risk_score(
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """
    Get fraud risk score for current user
    Returns risk level and contributing factors
    """
    risk_assessment = MLFraudDetectionService.calculate_risk_score(
        current_user.id,
        session
    )
    
    return DataResponse(
        success=True,
        data=risk_assessment
    )

@router.get("/fraud/anomalies", response_model=DataResponse[list])
def detect_user_anomalies(
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """
    Detect behavioral anomalies for current user
    Returns list of detected anomalies
    """
    anomalies = MLFraudDetectionService.detect_anomalies(
        current_user.id,
        session
    )
    
    return DataResponse(
        success=True,
        data=anomalies
    )
