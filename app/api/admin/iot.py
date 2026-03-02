from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from typing import List, Optional
from datetime import datetime, timedelta
from app.api import deps
from app.models.user import User
from app.models.battery import Battery
from app.models.station import Station
from app.models.telemetry import Telemetry
from app.db.session import get_session

router = APIRouter()

@router.get("/batteries/health")
def get_battery_health_overview(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(get_session),
):
    """Get health status distribution of all batteries."""
    # Group by status or health range
    # Mock aggregation for brevity, actual SQL would use func.count
    batteries = db.exec(select(Battery)).all()
    health_summary = {
        "total": len(batteries),
        "healthy": len([b for b in batteries if b.health_percentage >= 80]),
        "warning": len([b for b in batteries if 50 <= b.health_percentage < 80]),
        "critical": len([b for b in batteries if b.health_percentage < 50]),
    }
    return health_summary

@router.get("/stations/status")
def get_stations_status(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(get_session),
):
    """Get real-time status of all charging stations."""
    stations = db.exec(select(Station)).all()
    return stations

@router.get("/telematics/{battery_id}")
def get_battery_telematics(
    battery_id: int,
    hours: int = 24,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(get_session),
):
    """Get historical telematics for a specific battery."""
    since = datetime.utcnow() - timedelta(hours=hours)
    statement = select(Telemetry).where(
        Telemetry.battery_id == battery_id,
        Telemetry.timestamp >= since
    ).order_by(Telemetry.timestamp.desc())
    
    logs = db.exec(statement).all()
    return logs
