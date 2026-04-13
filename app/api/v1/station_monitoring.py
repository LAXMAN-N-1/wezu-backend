from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from typing import List
from app.models.station_heartbeat import StationHeartbeat
from app.schemas.station_monitoring import (
    HeartbeatRequestV2, OptimizedQueueResponse, 
    ChargingOptimizationRequest
)
from app.schemas.common import DataResponse
from app.services.station_service import StationService
from app.services.charging_service import ChargingService
from app.api import deps

router = APIRouter()

@router.post("/heartbeat", response_model=DataResponse[StationHeartbeat])
def record_heartbeat(
    heartbeat_in: HeartbeatRequestV2,
    session: Session = Depends(deps.get_db)
):
    """Record a heartbeat from a station with detailed metrics."""
    try:
        heartbeat = StationService.record_heartbeat(
            session, 
            int(heartbeat_in.station_id), 
            heartbeat_in.status, 
            heartbeat_in.metrics.dict()
        )
        return DataResponse(data=heartbeat, message="Heartbeat received", station_status=heartbeat_in.status)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/charging/prioritize", response_model=OptimizedQueueResponse)
def prioritize_charging(
    request: ChargingOptimizationRequest,
    session: Session = Depends(deps.get_db)
):
    """Get optimized charging priority list for a station."""
    queue = ChargingService.prioritize_charging(session, int(request.station_id), request.batteries)
    return OptimizedQueueResponse(optimized_queue=queue)

@router.patch("/charging/reprioritize", response_model=DataResponse[OptimizedQueueResponse])
def reprioritize_charging(
    station_id: str = "",
    urgent_battery_ids: List[str] = [],
    session: Session = Depends(deps.get_db)
):
    """Dynamically re-prioritize charging queue."""
    if not station_id or not urgent_battery_ids:
        raise HTTPException(status_code=422, detail="station_id and urgent_battery_ids are required")
    queue = ChargingService.reprioritize_queue(session, int(station_id), urgent_battery_ids)
    return DataResponse(data=OptimizedQueueResponse(optimized_queue=queue), message="Charging queue updated successfully")