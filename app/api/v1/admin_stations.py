from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from sqlalchemy import cast, JSON, Float
from app.api.deps import get_current_user
from app.models.station import Station
from app.models.station_heartbeat import StationHeartbeat
from app.schemas.common import DataResponse
from typing import List, Any
from datetime import datetime, UTC, timedelta

router = APIRouter()

from app.schemas.station_monitoring import StationHealthListResponse, StationHealthStatus, OptimizedQueueResponse, ChargingQueueResponse
from app.models.alert import Alert
from app.services.charging_service import ChargingService
from app.api import deps
import logging

logger = logging.getLogger(__name__)

@router.get("/health", response_model=StationHealthListResponse)
def get_station_health_stats(
    session: Session = Depends(deps.get_db),
    current_user: Any = Depends(get_current_user)
):
    """
    Get real-time health statistics for all stations.
    """
    try:
        stations = session.exec(select(Station)).all()
        results = []
        
        threshold_24h = datetime.now(UTC) - timedelta(hours=24)
        max_hbs = 24 * 60 # 1hb per minute
        
        for s in stations:
            # Calculate Uptime
            hb_count = session.exec(
                select(func.count(StationHeartbeat.id))
                .where(StationHeartbeat.station_id == s.id, StationHeartbeat.timestamp >= threshold_24h)
            ).one()
            uptime = (hb_count / max_hbs * 100) if hb_count < max_hbs else 100.0
            
            # Calculate Avg Latency
            avg_lat = session.exec(
                select(func.avg(cast(func.json_extract_path_text(cast(StationHeartbeat.metrics, JSON), 'network_latency'), Float)))
                .where(StationHeartbeat.station_id == s.id, StationHeartbeat.timestamp >= threshold_24h)
            ).one() or 0.0
            
            # Downtime (approximation)
            downtime_minutes = (max_hbs - hb_count) if hb_count < max_hbs else 0
    
            results.append(StationHealthStatus(
                station_id=str(s.id),
                status="ONLINE" if s.status == "active" else "OFFLINE",
                last_heartbeat=s.updated_at,
                uptime_percentage=uptime,
                avg_response_time=avg_lat,
                total_downtime_minutes=downtime_minutes
            ))
        
        return StationHealthListResponse(stations=results)
    except Exception as e:
        logger.exception(f"Error in get_station_health_stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{station_id}/alerts")
def get_station_alerts(
    station_id: int,
    session: Session = Depends(deps.get_db)
):
    """Get alerts for a specific station."""
    alerts = session.exec(select(Alert).where(Alert.station_id == station_id).order_by(Alert.created_at.desc())).all()
    return {"alerts": [
        {
            "alert_id": str(a.id),
            "alert_type": a.alert_type,
            "severity": a.severity,
            "message": a.message,
            "created_at": a.created_at,
            "acknowledged_at": a.acknowledged_at
        } for a in alerts
    ]}

@router.get("/{station_id}/charging-queue", response_model=ChargingQueueResponse)
def get_station_charging_queue(
    station_id: int,
    session: Session = Depends(deps.get_db)
):
    """View current charging queue for station."""
    station = session.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
        
    queue = ChargingService.get_charging_queue(session, station_id)
    return ChargingQueueResponse(
        station_id=str(station_id),
        capacity=station.total_slots,
        current_queue=queue
    )
