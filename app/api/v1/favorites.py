from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import List, Optional
from app.api import deps
from app.models.user import User
from app.models.favorite import Favorite
from app.models.station import Station
from app.schemas.station import StationResponse, NearbyStationResponse
from sqlalchemy import func

router = APIRouter()

@router.get("/stations", response_model=List[NearbyStationResponse])
async def get_favorite_stations(
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """List user's favorited stations with distance and availability"""
    # Join Favorite and Station
    query = select(Station).join(Favorite).where(Favorite.user_id == current_user.id)
    stations = db.exec(query).all()
    
    from app.services.station_service import StationService
    from app.schemas.station import StationImageResponse
    
    results = []
    for station in stations:
        # Distance
        dist = 0.0
        if lat is not None and lon is not None:
            dist = StationService.haversine(lon, lat, station.longitude, station.latitude)
            
        # Availability
        from app.models.station import StationSlot
        available_count = db.exec(
            select(func.count(StationSlot.id))
            .where(StationSlot.station_id == station.id, StationSlot.status == "ready")
        ).one()
        
        station_data = station.model_dump()
        images = [StationImageResponse(url=img.url, is_primary=img.is_primary) for img in station.images]
        
        results.append(NearbyStationResponse(
            **station_data,
            images=images,
            distance=dist,
            available_batteries=available_count
        ))
        
    return results

@router.post("/stations/{station_id}", response_model=dict)
async def add_favorite_station(
    station_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Add a station to favorites"""
    existing = db.exec(select(Favorite).where(Favorite.user_id == current_user.id, Favorite.station_id == station_id)).first()
    if existing:
        return {"status": "already_favorited"}
        
    fav = Favorite(user_id=current_user.id, station_id=station_id)
    db.add(fav)
    db.commit()
    return {"status": "added"}

@router.delete("/stations/{station_id}", response_model=dict)
async def remove_favorite_station(
    station_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Remove a station from favorites"""
    fav = db.exec(select(Favorite).where(Favorite.user_id == current_user.id, Favorite.station_id == station_id)).first()
    if not fav:
        raise HTTPException(status_code=404, detail="Favorite not found")
        
    db.delete(fav)
    db.commit()
    return {"status": "removed"}
