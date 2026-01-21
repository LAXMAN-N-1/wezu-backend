from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from app.api import deps
from app.models.user import User
from app.models.station import Station
from app.models.battery import Battery
from app.models.rental import Rental
from app.models.kyc import KYCDocument
from app.schemas.station import StationCreate, StationResponse
from app.schemas.battery import BatteryCreate, BatteryResponse
from app.schemas.user import UserResponse
from app.schemas.kyc import KYCDocumentResponse
from app.services.station_service import StationService
from app.services.battery_service import BatteryService

router = APIRouter()

# --- Stats ---
@router.get("/stats")
async def get_admin_stats(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    total_users = len(db.exec(select(User)).all())
    total_stations = len(db.exec(select(Station)).all())
    total_batteries = len(db.exec(select(Battery)).all())
    active_rentals = len(db.exec(select(Rental).where(Rental.status == "active")).all())
    pending_kyc = len(db.exec(select(KYCDocument).where(KYCDocument.status == "pending")).all())
    
    return {
        "total_users": total_users,
        "total_stations": total_stations,
        "total_batteries": total_batteries,
        "active_rentals": active_rentals,
        "pending_kyc": pending_kyc
    }

# --- Stations ---
@router.post("/stations", response_model=StationResponse)
async def create_station_admin(
    station_in: StationCreate,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    return StationService.create_station(db, station_in)

# --- Batteries ---
@router.post("/batteries", response_model=BatteryResponse)
async def create_battery_admin(
    battery_in: BatteryCreate,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
     return BatteryService.create_battery(db, battery_in)
     
# --- KYC ---
@router.get("/kyc/pending", response_model=List[KYCDocumentResponse])
async def get_pending_kyc(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    return db.exec(select(KYCDocument).where(KYCDocument.status == "pending")).all()

@router.put("/kyc/{kyc_id}/approve")
async def approve_kyc(
    kyc_id: int,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    doc = db.get(KYCDocument, kyc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="KYC not found")
    
    doc.status = "approved"
    # Also update User status if needed
    # doc.user.kyc_status = "verified"
    db.add(doc)
    db.commit()
    return {"status": "approved"}

# --- Geofences ---
from app.models.geofence import Geofence
from app.services.geofence_service import GeofenceService
from pydantic import BaseModel

class GeofenceCreate(BaseModel):
    name: str
    latitude: float
    longitude: float
    radius_meters: float
    type: str = "safe_zone"
    polygon_coords: str = None # Optional JSON

@router.post("/geofences", response_model=Geofence)
async def create_geofence(
    geo_in: GeofenceCreate,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    # Mapping to service arg style or direct create
    # Service expects individual args in `create_geofence`
    # Refactoring or calling directly
    
    # Let's use direct model creation for Admin simplicity or update service
    # Using service is better but signature was `create_geofence(db, name, lat, lon, radius)`
    # It misses `type`. I should update service or just do logic here. 
    # I'll update via direct DB add for now to save Service refactor time, OR just use `GeofenceService` if I update it? 
    # I haven't updated `create_geofence` in `GeofenceService`.
    # I'll do it manually here.
    
    geofence = Geofence(
        name=geo_in.name, 
        latitude=geo_in.latitude, 
        longitude=geo_in.longitude, 
        radius_meters=geo_in.radius_meters, 
        type=geo_in.type,
        polygon_coords=geo_in.polygon_coords
    )
    db.add(geofence)
    db.commit()
    db.refresh(geofence)
    return geofence

@router.get("/geofences", response_model=List[Geofence])
async def list_geofences(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    return db.exec(select(Geofence)).all()
