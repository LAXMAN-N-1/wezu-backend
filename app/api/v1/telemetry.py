from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from datetime import datetime, timedelta
from sqlmodel import Session, select
from pydantic import BaseModel, Field
from app.api import deps
from app.models.rental import Rental
from app.models.battery import Battery
from app.models.user import User
from app.services.gps_service import GPSTrackingService
from app.schemas.common import DataResponse
import random

router = APIRouter()

# --- SCHEMAS ---
class TelemetryResponse(BaseModel):
    voltage: float
    temperature: float
    health: float
    charge: float
    latitude: float
    longitude: float
    last_updated: datetime
    status: str # normal, warning, critical

class LocationPoint(BaseModel):
    latitude: float
    longitude: float
    timestamp: datetime

class LocationUpdateRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy: Optional[float] = Field(None, gt=0)

# --- ENDPOINTS ---
@router.post("/rentals/{rental_id}/location", response_model=DataResponse[dict])
def update_location(
    rental_id: int,
    request: LocationUpdateRequest,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(deps.get_db)
):
    """Update GPS location for active rental"""
    rental = session.get(Rental, rental_id)
    if not rental or rental.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    gps_log = GPSTrackingService.log_location(
        rental_id=rental_id,
        latitude=request.latitude,
        longitude=request.longitude,
        accuracy=request.accuracy,
        session=session
    )
    
    return DataResponse(
        success=True, 
        data={"log_id": gps_log.id, "timestamp": gps_log.timestamp.isoformat()}
    )

@router.get("/rentals/{rental_id}/telemetry", response_model=TelemetryResponse)
def get_rental_telemetry(
    rental_id: int,
    session: Session = Depends(deps.get_db)
):
    """Mock/Real-time data for dashboard"""
    rental = session.get(Rental, rental_id)
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")
        
    battery = rental.battery
    if not battery:
        raise HTTPException(status_code=404, detail="Battery not found")
        
    now = datetime.utcnow()
    # Logic for voltage/temp simulation...
    voltage = 72.0 + random.uniform(-1.5, 1.5)
    temp = 32.0 + (datetime.now().minute % 10) 
    
    return TelemetryResponse(
        voltage=round(voltage, 2),
        temperature=round(temp, 1),
        health=battery.health_percentage,
        charge=battery.current_charge or 100.0,
        latitude=battery.last_latitude or 17.3850,
        longitude=battery.last_longitude or 78.4867,
        last_updated=now,
        status="normal"
    )

@router.get("/rentals/{rental_id}/location-history", response_model=List[LocationPoint])
def get_location_history_points(
    rental_id: int,
    session: Session = Depends(deps.get_db)
):
    """Get points for path visualization"""
    history = GPSTrackingService.get_location_history(rental_id=rental_id, limit=100, session=session)
    return [
        LocationPoint(latitude=log.latitude, longitude=log.longitude, timestamp=log.timestamp)
        for log in history
    ]

@router.get("/rentals/{rental_id}/travel-path", response_model=DataResponse[dict])
def get_travel_path(
    rental_id: int,
    session: Session = Depends(deps.get_db)
):
    """Get travel statistics and path"""
    path_data = GPSTrackingService.get_travel_path(rental_id, session)
    return DataResponse(success=True, data=path_data)

@router.get("/rentals/{rental_id}/geofence-status", response_model=DataResponse[dict])
def get_geofence_status(
    rental_id: int,
    session: Session = Depends(deps.get_db)
):
    """Check if rental is within allowed boundaries"""
    from app.models.geofence import Geofence
    from app.services.geofence_service import GeofenceService
    
    location = GPSTrackingService.get_current_location(rental_id, session)
    if not location:
         raise HTTPException(status_code=404, detail="No location data")
         
    geofences = session.exec(select(Geofence).where(Geofence.is_active == True)).all()
    violations = []
    for g in geofences:
        if not GeofenceService.check_boundary(location.latitude, location.longitude, g):
             violations.append({"id": g.id, "name": g.name, "type": g.type})
             
    return DataResponse(success=True, data={"has_violations": len(violations) > 0, "violations": violations})
