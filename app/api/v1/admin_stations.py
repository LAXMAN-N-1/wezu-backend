from fastapi import APIRouter, Depends, HTTPException, Query
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
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(deps.get_db),
    current_user: Any = Depends(get_current_user)
):
    """
    Get real-time health statistics for all stations.
    Uses batch queries instead of N+1 per-station loop.
    """
    try:
        stations = session.exec(select(Station).offset(skip).limit(limit)).all()
        if not stations:
            return StationHealthListResponse(stations=[])

        threshold_24h = datetime.now(UTC) - timedelta(hours=24)
        max_hbs = 24 * 60  # 1hb per minute

        station_ids = [s.id for s in stations]

        # Batch: heartbeat counts per station (1 query instead of N)
        hb_counts_raw = session.exec(
            select(
                StationHeartbeat.station_id,
                func.count(StationHeartbeat.id).label("hb_count"),
            )
            .where(
                StationHeartbeat.station_id.in_(station_ids),
                StationHeartbeat.timestamp >= threshold_24h,
            )
            .group_by(StationHeartbeat.station_id)
        ).all()
        hb_counts = {row[0]: row[1] for row in hb_counts_raw}

        # Batch: avg latency per station (1 query instead of N)
        avg_lat_raw = session.exec(
            select(
                StationHeartbeat.station_id,
                func.avg(
                    cast(
                        func.json_extract_path_text(
                            cast(StationHeartbeat.metrics, JSON), "network_latency"
                        ),
                        Float,
                    )
                ).label("avg_latency"),
            )
            .where(
                StationHeartbeat.station_id.in_(station_ids),
                StationHeartbeat.timestamp >= threshold_24h,
            )
            .group_by(StationHeartbeat.station_id)
        ).all()
        avg_lats = {row[0]: row[1] or 0.0 for row in avg_lat_raw}

        results = []
        for s in stations:
            hb_count = hb_counts.get(s.id, 0)
            uptime = (hb_count / max_hbs * 100) if hb_count < max_hbs else 100.0
            avg_lat = avg_lats.get(s.id, 0.0)
            downtime_minutes = (max_hbs - hb_count) if hb_count < max_hbs else 0

            results.append(StationHealthStatus(
                station_id=str(s.id),
                status="ONLINE" if s.status == "active" else "OFFLINE",
                last_heartbeat=s.updated_at,
                uptime_percentage=uptime,
                avg_response_time=avg_lat,
                total_downtime_minutes=downtime_minutes,
            ))

        return StationHealthListResponse(stations=results)
    except Exception as e:
        logger.exception("station_health_stats_failed")
        raise HTTPException(status_code=500, detail="Failed to retrieve station health stats")

@router.get("/{station_id}/alerts")
def get_station_alerts(
    station_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(deps.get_db)
):
    """Get alerts for a specific station."""
    alerts = session.exec(
        select(Alert)
        .where(Alert.station_id == station_id)
        .order_by(Alert.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()
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
