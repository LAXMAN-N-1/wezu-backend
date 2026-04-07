from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File
from sqlmodel import Session, select
from typing import List, Optional
from app.api import deps
from app.core.audit import audit_log
from app.models.user import User
from app.schemas.station import (
    StationResponse, StationCreate, NearbyStationResponse,
    StationUpdate, StationPerformanceResponse, StationMapResponse,
    HeatmapPoint
)
from app.schemas.review import ReviewResponse, ReviewCreate, ReviewUpdate
from app.schemas.battery import BatteryResponse
from app.services.station_service import StationService
from app.services.maintenance_service import MaintenanceService
from app.services.review_service import ReviewService
from app.models.station import StationStatus, Station, StationImage
from app.models.battery import Battery
from app.models.favorite import Favorite
from datetime import datetime, UTC

router = APIRouter()

@router.get("/", response_model=List[StationResponse])
async def read_stations(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.require_permission("station:read")),
    db: Session = Depends(deps.get_db),
):
    """
    Retrieve stations. Dealers see only their own stations.
    """
    from app.models.roles import RoleEnum
    
    query = select(Station)
    
    # Row-level filtering: Dealers only see their own stations using Request Context Role
    user_role = getattr(request.state, 'user_role', None)

    if user_role == RoleEnum.DEALER and current_user.dealer_profile:
        query = query.where(Station.dealer_id == current_user.dealer_profile.id)
    
    stations = db.exec(query.offset(skip).limit(limit)).all()
    return stations

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
@audit_log("CREATE_STATION", "STATION")
async def create_station(
    request: Request,
    station_in: StationCreate,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    """Admin: create a new station record."""
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

@router.put("/{station_id}", response_model=StationResponse)
async def update_station(
    station_id: int,
    station_in: StationUpdate,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    """Update station details."""
    station = StationService.update_station(db, station_id, station_in)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    return station

@router.delete("/{station_id}")
async def delete_station(
    station_id: int,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    """Deactivate or archive a station."""
    success = StationService.deactivate_station(db, station_id)
    if not success:
        raise HTTPException(status_code=404, detail="Station not found")
    return {"status": "success", "message": "Station deactivated"}

@router.put("/{station_id}/status", response_model=StationResponse)
async def update_station_status(
    station_id: int,
    status: StationStatus,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    """Change station operational status."""
    station = db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    station.status = status
    station.updated_at = datetime.now(UTC)
    db.add(station)
    db.commit()
    db.refresh(station)
    return station

@router.get("/{station_id}/performance", response_model=StationPerformanceResponse)
async def read_station_performance(
    station_id: int,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    """Station metrics: daily rentals, revenue, avg duration, etc."""
    return StationService.get_performance_metrics(db, station_id)

@router.get("/{station_id}/rental-history")
async def read_station_rental_history(
    station_id: int,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
    limit: int = Query(50, le=100)
):
    """All rentals that originated from this station."""
    return StationService.get_rental_history(db, station_id, limit)

@router.post("/{station_id}/photos")
async def upload_station_photo(
    station_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    """Upload station photos."""
    # Assuming storage service logic or just direct DB update for mock
    image = StationImage(station_id=station_id, url=f"/media/stations/{file.filename}")
    db.add(image)
    db.commit()
    db.refresh(image)
    return image

@router.delete("/{station_id}/photos/{photo_id}")
async def delete_station_photo(
    station_id: int,
    photo_id: int,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    """Remove a station photo."""
    image = db.get(StationImage, photo_id)
    if not image or image.station_id != station_id:
        raise HTTPException(status_code=404, detail="Photo not found")
    db.delete(image)
    db.commit()
    return {"status": "success"}

@router.get("/{station_id}/maintenance-schedule")
async def read_station_maintenance_schedule(
    station_id: int,
    db: Session = Depends(deps.get_db),
):
    """View upcoming and past maintenance for station."""
    return MaintenanceService.get_maintenance_schedule(db, station_id)

@router.post("/{station_id}/maintenance-schedule")
async def create_station_maintenance_task(
    station_id: int,
    data: "MaintenanceTaskCreate",
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    from app.schemas.input_contracts import MaintenanceTaskCreate
    task_data = data.model_dump(exclude_unset=True)
    task_data.update({"entity_type": "station", "entity_id": station_id})
    return MaintenanceService.record_maintenance(db, current_user.id, task_data)

@router.put("/{station_id}/maintenance-schedule/{task_id}")
async def update_station_maintenance_task(
    station_id: int,
    task_id: int,
    status: str,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    """Mark maintenance task complete or update it."""
    from app.models.maintenance import MaintenanceRecord
    task = db.get(MaintenanceRecord, task_id)
    if not task or task.entity_id != station_id or task.entity_type != "station":
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.status = status
    task.performed_at = datetime.now(UTC)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

@router.get("/map", response_model=List[StationMapResponse])
async def get_stations_map(
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(deps.get_db),
):
    """Return station coordinates and status for map rendering."""
    stations = db.exec(select(Station).offset(skip).limit(limit)).all()
    return stations

@router.get("/heatmap", response_model=List[HeatmapPoint])
async def get_stations_heatmap(
    db: Session = Depends(deps.get_db),
):
    """Demand heatmap data aggregated by geography."""
    return StationService.get_heatmap_data(db)

@router.get("/{station_id}/reviews", response_model=List[ReviewResponse])
async def read_station_reviews(
    station_id: int,
    skip: int = Query(0),
    limit: int = Query(50),
    db: Session = Depends(deps.get_db),
):
    return ReviewService.get_by_station(db, station_id, skip, limit)

@router.post("/{station_id}/reviews", response_model=ReviewResponse)
async def create_review(
    station_id: int,
    review_in: ReviewCreate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    review_in.station_id = station_id
    return ReviewService.create_review(db, current_user.id, review_in)

@router.put("/{station_id}/reviews/{review_id}", response_model=ReviewResponse)
async def update_review(
    station_id: int,
    review_id: int,
    review_in: ReviewUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Edit own review"""
    return ReviewService.update_review(db, review_id, current_user.id, review_in.model_dump(exclude_unset=True))

@router.delete("/{station_id}/reviews/{review_id}")
async def delete_review(
    station_id: int,
    review_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Delete own review"""
    ReviewService.delete_review(db, review_id, current_user.id)
    return {"status": "success", "message": "Review deleted"}

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
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(deps.get_db),
):
    try:
        query = select(Battery).where(Battery.station_id == station_id).offset(skip).limit(limit)
        results = db.exec(query).all()
        return results
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("fetch_station_batteries_failed", extra={"station_id": station_id})
        raise HTTPException(status_code=500, detail="Failed to fetch station batteries")
