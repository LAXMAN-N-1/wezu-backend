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

# Redundant routes moved to specific modules
     
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

# --- Advanced Analytics ---
from datetime import datetime, timedelta
from app.models.battery_catalog import BatteryCatalog

@router.get("/inventory/forecast")
async def get_inventory_forecast(
    days_ahead: int = 30,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    """
    FR-ADMIN-INV-003: Inventory Forecasting & Reorder Alerts
    Calculates demand based on last 30 days of rentals and predicts future needs.
    """
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # 1. Total battery rentals strictly over last 30 days (rental velocity)
    rentals_last_month = db.exec(
        select(Rental).where(Rental.start_time >= thirty_days_ago)
    ).all()
    
    # 2. Get battery mapping to match velocity per SKU
    rental_velocity = {}
    for r in rentals_last_month:
        b = db.get(Battery, r.battery_id)
        if b and b.sku_id:
            rental_velocity[b.sku_id] = rental_velocity.get(b.sku_id, 0) + 1
            
    # 3. Calculate forecast and reorder suggestions for each catalog SKU
    forecasts = []
    catalogs = db.exec(select(BatteryCatalog)).all()
    
    for catalog in catalogs:
        # Average daily velocity over past 30 days
        velocity_30d = rental_velocity.get(catalog.id, 0)
        daily_run_rate = velocity_30d / 30.0
        
        # Predicted demand over `days_ahead`
        predicted_demand = int(daily_run_rate * days_ahead)
        
        # Current actual stock that is not actively rented
        available_stock = len(db.exec(
            select(Battery).where(
                Battery.sku_id == catalog.id, 
                Battery.status.in_(["available", "in_station", "warehouse"])
            )
        ).all())
        
        # Suggest new stock if predicted demand outpaces availability (+20% safety buffer)
        suggested_reorder = max(0, int((predicted_demand * 1.2) - available_stock))
        
        forecasts.append({
            "sku_id": catalog.id,
            "sku_name": catalog.name,
            "available_stock": available_stock,
            "past_30d_rentals": velocity_30d,
            "predicted_demand_next_period": predicted_demand,
            "suggested_reorder_quantity": suggested_reorder
        })
        
    return {
        "forecast_period_days": days_ahead,
        "predictions": forecasts
    }

@router.get("/analytics/battery-health")
async def get_battery_health_distribution(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    """
    FR-ADMIN-DASH-004: Battery Health Distribution
    Aggregates batteries into health buckets and flags those needing maintenance.
    """
    batteries = db.exec(select(Battery)).all()
    
    distribution = {
        "excellent_90_100": 0,
        "good_80_89": 0,
        "fair_70_79": 0,
        "poor_under_70": 0
    }
    
    maintenance_required = []
    
    for b in batteries:
        health = b.health_percentage if b.health_percentage else 100.0
        
        if health >= 90:
            distribution["excellent_90_100"] += 1
        elif health >= 80:
            distribution["good_80_89"] += 1
        elif health >= 70:
            distribution["fair_70_79"] += 1
        else:
            distribution["poor_under_70"] += 1
            
        # Flag severely degraded batteries or those explicitly marked for maintenance
        if health < 70 or b.health_status == "needs_maintenance":
            maintenance_required.append({
                "id": b.id,
                "serial_number": b.serial_number,
                "health_percentage": health,
                "current_status": b.status,
                "location_type": b.location_type,
                "location_id": b.location_id
            })
            
    return {
        "total_batteries": len(batteries),
        "health_distribution": distribution,
        "maintenance_required": maintenance_required,
        "maintenance_count": len(maintenance_required)
    }
