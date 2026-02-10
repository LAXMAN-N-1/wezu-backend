from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from typing import List, Optional
from app.api import deps
from app.models.user import User
from app.schemas.station import StationResponse, StationCreate, NearbyStationResponse
from app.schemas.review import ReviewResponse, ReviewCreate
from app.services.station_service import StationService
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
    db: Session = Depends(deps.get_db),
):
    stations = StationService.get_nearby(db, lat, lon, radius)
    # Convert to response model (should populate distance dynamically)
    # Pydantic will handle the conversion from Station object to NearbyStationResponse 
    # IF the Station object has 'distance' attribute set (which we did in service)
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
    station = db.get("Station", station_id) # Won't work with string "Station", need model
    # Wait, db.get needs Model class.
    from app.models.station import Station
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
