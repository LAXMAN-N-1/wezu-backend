"""
GPS Tracking and Location API
Endpoints for location updates and history
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timedelta

from app.api import deps
from app.db.session import get_session
from app.models.user import User
from app.models.rental import Rental
from app.services.gps_service import GPSTrackingService
from app.schemas.common import DataResponse

router = APIRouter()

# Schemas
class LocationUpdateRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy: Optional[float] = Field(None, gt=0)
    altitude: Optional[float] = None
    speed: Optional[float] = Field(None, ge=0)
    heading: Optional[float] = Field(None, ge=0, lt=360)
    provider: Optional[str] = "GPS"

class LocationHistoryRequest(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(100, ge=1, le=1000)

# Endpoints
@router.post("/{rental_id}/location", response_model=DataResponse[dict])
def update_location(
    rental_id: int,
    request: LocationUpdateRequest,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """
    Update GPS location for active rental
    Called by mobile app every 5 seconds during rental
    """
    # Verify rental belongs to user
    rental = session.get(Rental, rental_id)
    if not rental:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rental not found"
        )
    
    if rental.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this rental"
        )
    
    # Log location
    try:
        gps_log = GPSTrackingService.log_location(
            rental_id=rental_id,
            latitude=request.latitude,
            longitude=request.longitude,
            accuracy=request.accuracy,
            session=session
        )
        
        return DataResponse(
            success=True,
            data={
                "log_id": gps_log.id,
                "timestamp": gps_log.timestamp.isoformat(),
                "message": "Location updated successfully"
            }
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/{rental_id}/location/current", response_model=DataResponse[dict])
def get_current_location(
    rental_id: int,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Get most recent location for rental"""
    # Verify rental belongs to user
    rental = session.get(Rental, rental_id)
    if not rental or rental.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )
    
    location = GPSTrackingService.get_current_location(rental_id, session)
    
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No location data available"
        )
    
    return DataResponse(
        success=True,
        data={
            "latitude": location.latitude,
            "longitude": location.longitude,
            "accuracy": location.accuracy,
            "timestamp": location.timestamp.isoformat()
        }
    )

@router.post("/{rental_id}/location/history", response_model=DataResponse[list])
def get_location_history(
    rental_id: int,
    request: LocationHistoryRequest,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Get location history for rental"""
    # Verify rental belongs to user
    rental = session.get(Rental, rental_id)
    if not rental or rental.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )
    
    history = GPSTrackingService.get_location_history(
        rental_id=rental_id,
        start_time=request.start_time,
        end_time=request.end_time,
        limit=request.limit,
        session=session
    )
    
    return DataResponse(
        success=True,
        data=[
            {
                "latitude": log.latitude,
                "longitude": log.longitude,
                "accuracy": log.accuracy,
                "timestamp": log.timestamp.isoformat()
            }
            for log in history
        ]
    )

@router.get("/{rental_id}/location/path", response_model=DataResponse[dict])
def get_travel_path(
    rental_id: int,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Get complete travel path with distance calculation"""
    # Verify rental belongs to user
    rental = session.get(Rental, rental_id)
    if not rental or rental.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )
    
    path_data = GPSTrackingService.get_travel_path(rental_id, session)
    
    return DataResponse(
        success=True,
        data=path_data
    )

@router.get("/{rental_id}/location/stats", response_model=DataResponse[dict])
def get_location_stats(
    rental_id: int,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Get location tracking statistics"""
    # Verify rental belongs to user
    rental = session.get(Rental, rental_id)
    if not rental or rental.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )
    
    stats = GPSTrackingService.get_location_stats(rental_id, session)
    
    return DataResponse(
        success=True,
        data=stats
    )

@router.get("/{rental_id}/geofence/status", response_model=DataResponse[dict])
def get_geofence_status(
    rental_id: int,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Check current geofence status"""
    # Verify rental belongs to user
    rental = session.get(Rental, rental_id)
    if not rental or rental.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )
    
    # Get current location
    location = GPSTrackingService.get_current_location(rental_id, session)
    
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No location data available"
        )
    
    # Check geofences
    from app.services.geofence_service import GeofenceService
    evaluation = GeofenceService.evaluate_location(session, location.latitude, location.longitude)
    violations = []
    for violation in evaluation.get("violations", []):
        zone_type = str(violation.get("type", "")).strip().lower()
        violations.append(
            {
                "geofence_id": violation.get("geofence_id"),
                "name": violation.get("name"),
                "type": violation.get("type"),
                "severity": "HIGH" if zone_type == "restricted_zone" else "MEDIUM",
                "reason": violation.get("reason"),
            }
        )
    
    return DataResponse(
        success=True,
        data={
            "has_violations": len(violations) > 0,
            "violation_count": len(violations),
            "violations": violations,
            "outside_safe_zone": bool(evaluation.get("outside_safe_zone", False)),
            "current_location": {
                "latitude": location.latitude,
                "longitude": location.longitude
            }
        }
    )
