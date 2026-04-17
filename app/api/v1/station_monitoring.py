from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from typing import List, Optional
from app.models.station import Station, StationCamera
from app.models.station_heartbeat import StationHeartbeat
from app.schemas.station_monitoring import (
    HeartbeatRequestV2, OptimizedQueueResponse, 
    ChargingOptimizationRequest,
    StationCameraRead, StationCameraCreate, StationCameraUpdate
)
from app.schemas.common import DataResponse
from app.services.station_service import StationService
from app.services.charging_service import ChargingService
from app.api import deps
from app.models.user import User

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

# ─── Camera Monitoring Endpoints ───

@router.get("/{station_id}/cameras", response_model=DataResponse[List[StationCameraRead]])
def get_station_cameras(
    station_id: int,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_permission("station:read"))
):
    """List all monitoring cameras for a station."""
    cameras = session.query(StationCamera).filter(StationCamera.station_id == station_id).all()
    return DataResponse(data=cameras)

@router.post("/{station_id}/cameras", response_model=DataResponse[StationCameraRead])
def add_station_camera(
    station_id: int,
    camera_in: StationCameraCreate,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin)
):
    """Register a new monitoring camera for a station."""
    station = session.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
        
    camera = StationCamera(**camera_in.dict(), station_id=station_id)
    session.add(camera)
    session.commit()
    session.refresh(camera)
    return DataResponse(data=camera, message="Camera registered successfully")

@router.get("/{station_id}/cameras/{camera_id}/preview")
def get_camera_preview(
    station_id: int,
    camera_id: int,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_permission("station:read"))
):
    """Get preview/stream information for the camera."""
    camera = session.query(StationCamera).filter(
        StationCamera.id == camera_id, 
        StationCamera.station_id == station_id
    ).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
        
    return {
        "camera_id": camera.id,
        "name": camera.name,
        "rtsp_url": camera.rtsp_url,
        "status": camera.status
    }

@router.patch("/{station_id}/cameras/{camera_id}", response_model=DataResponse[StationCameraRead])
def update_station_camera(
    station_id: int,
    camera_id: int,
    camera_in: StationCameraUpdate,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin)
):
    """Update camera details or status."""
    camera = session.query(StationCamera).filter(
        StationCamera.id == camera_id, 
        StationCamera.station_id == station_id
    ).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
        
    update_data = camera_in.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(camera, key, value)
    
    session.add(camera)
    session.commit()
    session.refresh(camera)
    return DataResponse(data=camera, message="Camera updated successfully")

@router.delete("/{station_id}/cameras/{camera_id}", response_model=DataResponse)
def delete_station_camera(
    station_id: int,
    camera_id: int,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin)
):
    """Remove a camera from a station."""
    camera = session.query(StationCamera).filter(
        StationCamera.id == camera_id, 
        StationCamera.station_id == station_id
    ).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
        
    session.delete(camera)
    session.commit()
    return DataResponse(message="Camera deleted successfully")