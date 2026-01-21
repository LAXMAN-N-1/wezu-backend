from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from app.db.session import get_session
from app.models.swap import SwapRequest, SwapHistory
from app.models.station import Station
from app.services.swap_service import SwapService
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import DataResponse
from pydantic import BaseModel

router = APIRouter()

class SwapCreate(BaseModel):
    rental_id: int
    station_id: int

class SwapExecute(BaseModel):
    station_id: int
    old_battery_sn: str
    new_battery_sn: str

@router.post("/stations", response_model=DataResponse[List[Station]])
def find_swap_stations(
    lat: float, 
    lng: float, 
    session: Session = Depends(get_session)
):
    stations = SwapService.get_stations_with_batteries(lat, lng)
    return DataResponse(data=stations)

@router.post("/request", response_model=DataResponse[SwapRequest])
def request_swap(
    req: SwapCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    try:
        swap = SwapService.request_swap(req.rental_id, req.station_id)
        return DataResponse(data=swap)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/execute", response_model=DataResponse[SwapHistory])
def execute_swap(
    req: SwapExecute,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Called by the device or user (via scan) to confirm physical swap.
    """
    try:
        history = SwapService.execute_swap(current_user.id, req.station_id, req.old_battery_sn, req.new_battery_sn)
        return DataResponse(data=history)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Swap Enhancements
from app.models.swap_suggestion import SwapSuggestion, SwapPreference

@router.get("/{rental_id}/suggestions", response_model=List[SwapSuggestion])
def get_swap_suggestions(
    rental_id: int,
    lat: float,
    lng: float,
    battery_soc: float,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get ML-based swap station suggestions"""
    from app.models.rental import Rental
    from sqlmodel import select
    
    rental = session.get(Rental, rental_id)
    if not rental or rental.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rental not found")
    
    # Get user preferences
    preference = session.exec(
        select(SwapPreference).where(SwapPreference.user_id == current_user.id)
    ).first()
    
    # Get nearby stations
    stations = SwapService.get_stations_with_batteries(lat, lng)
    
    # Create suggestions with scoring
    suggestions = []
    for idx, station in enumerate(stations[:5]):  # Top 5 stations
        # Calculate distance (simplified)
        import math
        distance = math.sqrt((station.latitude - lat)**2 + (station.longitude - lng)**2) * 111  # Rough km
        
        # Calculate scores
        availability_score = min(station.available_batteries / 10.0 * 100, 100) if hasattr(station, 'available_batteries') else 50
        preference_score = 80 if preference and preference.prefer_nearby > 5 else 50
        
        # Total score (weighted)
        total_score = (
            (10 - distance) * 10 +  # Distance weight
            availability_score * 0.3 +
            preference_score * 0.2
        )
        
        suggestion = SwapSuggestion(
            user_id=current_user.id,
            rental_id=rental_id,
            current_battery_soc=battery_soc,
            current_location_lat=lat,
            current_location_lng=lng,
            suggested_station_id=station.id,
            priority_rank=idx + 1,
            distance_km=distance,
            estimated_travel_time_minutes=int(distance * 3),  # Rough estimate
            station_availability_score=availability_score,
            station_rating=station.rating if hasattr(station, 'rating') else 4.5,
            preference_match_score=preference_score,
            total_score=total_score
        )
        session.add(suggestion)
        suggestions.append(suggestion)
    
    session.commit()
    return suggestions

@router.get("/{rental_id}/history", response_model=List[SwapHistory])
def get_swap_history(
    rental_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get swap history for a rental"""
    from app.models.rental import Rental
    from sqlmodel import select
    
    rental = session.get(Rental, rental_id)
    if not rental or rental.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rental not found")
    
    history = session.exec(
        select(SwapHistory)
        .where(SwapHistory.rental_id == rental_id)
        .order_by(SwapHistory.timestamp.desc())
    ).all()
    
    return history

@router.post("/preferences", response_model=SwapPreference)
def set_swap_preferences(
    preferences: dict,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Set user swap preferences"""
    from sqlmodel import select
    
    existing = session.exec(
        select(SwapPreference).where(SwapPreference.user_id == current_user.id)
    ).first()
    
    if existing:
        # Update existing
        for key, value in preferences.items():
            if hasattr(existing, key):
                setattr(existing, key, value)
        existing.updated_at = datetime.utcnow()
        session.add(existing)
    else:
        # Create new
        pref = SwapPreference(user_id=current_user.id, **preferences)
        session.add(pref)
    
    session.commit()
    session.refresh(existing if existing else pref)
    return existing if existing else pref

@router.get("/preferences", response_model=SwapPreference)
def get_swap_preferences(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get user swap preferences"""
    from sqlmodel import select
    
    pref = session.exec(
        select(SwapPreference).where(SwapPreference.user_id == current_user.id)
    ).first()
    
    if not pref:
        # Return defaults
        pref = SwapPreference(
            user_id=current_user.id,
            prefer_nearby=8,
            prefer_fast_charging=5,
            prefer_high_rated=6,
            prefer_low_wait=7,
            max_acceptable_distance_km=10.0,
            notify_when_battery_below=20,
            notify_suggestion_radius_km=5.0
        )
        session.add(pref)
        session.commit()
        session.refresh(pref)
    
    return pref
