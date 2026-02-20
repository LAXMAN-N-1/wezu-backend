from app.models.station import Station
from app.models.favorite import Favorite
from app.models.battery import Battery
from app.schemas.battery import BatteryResponse
from sqlmodel import Session, select
from typing import List, Optional
from app.api import deps
from app.models.user import User
from app.schemas.station import StationResponse, StationCreate, NearbyStationResponse
from app.schemas.review import ReviewResponse, ReviewCreate
from app.services.station_service import StationService
from fastapi import APIRouter, Depends, HTTPException, Query
from app.services.review_service import ReviewService

router = APIRouter()

@router.get("/", response_model=List[StationResponse])
async def read_stations(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(deps.get_db),
):
    return StationService.get_stations(db, skip=skip, limit=limit)

@router.get("/nearby", response_model=List[NearbyStationResponse])
async def search_nearby_stations(
    lat: float,
    lon: float,
    radius: float = 50.0,
    min_rating: Optional[float] = Query(None, description="Minimum rating (1-5)"),
    status: Optional[str] = Query(None, description="Station status (active, maintenance)"),
    is_24x7: Optional[bool] = Query(None, description="Filter only 24x7 stations"),
    sort_by: str = Query("distance", description="Sort by: distance, rating, availability"),
    
    # Advanced Battery Filters (FR-MOB-DISC-002)
    battery_type: Optional[str] = Query(None, description="Filter by battery type (e.g., lithium_ion, lfp)"),
    min_capacity: Optional[int] = Query(None, description="Minimum battery capacity (mAh)"),
    max_price: Optional[float] = Query(None, description="Maximum daily rental price"),
    
    db: Session = Depends(deps.get_db),
):
    """
    Find nearby stations, optionally filtered by available battery specs.
    """
    stations = StationService.get_nearby(
        db, lat, lon, radius,
        min_rating=min_rating, status=status, is_24x7=is_24x7, sort_by=sort_by,
        battery_type=battery_type, min_capacity=min_capacity, max_price=max_price
    )
    return stations

@router.post("/", response_model=StationResponse)
async def create_station(
    station_in: StationCreate,
    current_user: User = Depends(deps.check_permission("stations", "create")),
    db: Session = Depends(deps.get_db),
):
    return StationService.create_station(db, station_in)

@router.get("/{station_id}", response_model=StationResponse)
async def read_station(
    station_id: int,
    db: Session = Depends(deps.get_db),
):
    station = db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    return station

@router.get("/{station_id}/reviews", response_model=List[ReviewResponse])
async def read_station_reviews(
    station_id: int,
    db: Session = Depends(deps.get_db),
):
    return ReviewService.get_by_station(db, station_id)

@router.post("/{station_id}/reviews", response_model=ReviewResponse)
async def create_review(
    station_id: int,
    review_in: ReviewCreate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    review_in.station_id = station_id
    return ReviewService.create_review(db, current_user.id, review_in)

@router.post("/{station_id}/favorite", response_model=dict)
async def favorite_station(
    station_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    existing = db.exec(select(Favorite).where(Favorite.user_id == current_user.id, Favorite.station_id == station_id)).first()
    if existing:
        return {"status": "already_favorited"}
    fav = Favorite(user_id=current_user.id, station_id=station_id)
    db.add(fav)
    db.commit()
    return {"status": "favorited"}

@router.delete("/{station_id}/favorite", response_model=dict)
async def unfavorite_station(
    station_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    fav = db.exec(select(Favorite).where(Favorite.user_id == current_user.id, Favorite.station_id == station_id)).first()
    if not fav:
         raise HTTPException(status_code=404, detail="Favorite not found")
    db.delete(fav)
    db.commit()
    return {"status": "unfavorited"}

@router.get("/{station_id}/batteries", response_model=List[BatteryResponse])
async def read_station_batteries(
    station_id: int,
    db: Session = Depends(deps.get_db),
):
    try:
        # Assuming we just need to query by station_id since location_id doesn't exist anymore
        query = select(Battery).where(Battery.station_id == station_id)
        results = db.exec(query).all()
        return results
    except Exception as e:
        import logging
        logging.error(f"DATABASE_ERROR: Failed to fetch batteries for station {station_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
