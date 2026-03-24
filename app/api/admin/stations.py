from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from typing import Any, List, Optional
from datetime import datetime
from pydantic import BaseModel
from app.api import deps
from app.models.station import Station, StationStatus, StationSlot
from app.models.maintenance import MaintenanceRecord, StationDowntime
from app.core.database import get_db

router = APIRouter()


class StationCreateRequest(BaseModel):
    name: str
    address: str
    latitude: float
    longitude: float
    city: Optional[str] = None
    station_type: str = "automated"
    total_slots: int = 0
    power_rating_kw: Optional[float] = None
    contact_phone: Optional[str] = None
    operating_hours: Optional[str] = None
    is_24x7: bool = False


class StationUpdateRequest(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: Optional[str] = None
    station_type: Optional[str] = None
    total_slots: Optional[int] = None
    power_rating_kw: Optional[float] = None
    contact_phone: Optional[str] = None
    operating_hours: Optional[str] = None
    is_24x7: Optional[bool] = None


class MaintenanceCreateRequest(BaseModel):
    entity_type: str = "station"
    entity_id: int
    maintenance_type: str = "preventive"
    description: str
    cost: float = 0.0
    parts_replaced: Optional[str] = None
    status: str = "scheduled"


# ---- STATION LISTING & CRUD ----

@router.get("/")
def list_stations(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    status: Optional[str] = None,
    city: Optional[str] = None,
    station_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """List all stations with pagination, search, and filters."""
    statement = select(Station)

    if search:
        statement = statement.where(
            (Station.name.ilike(f"%{search}%")) |
            (Station.address.ilike(f"%{search}%")) |
            (Station.city.ilike(f"%{search}%"))
        )

    if status:
        statement = statement.where(Station.status == status)

    if city:
        statement = statement.where(Station.city.ilike(f"%{city}%"))

    if station_type:
        statement = statement.where(Station.station_type == station_type)

    count_stmt = select(func.count()).select_from(statement.subquery())
    total_count = db.exec(count_stmt).one()

    statement = statement.order_by(Station.created_at.desc()).offset(skip).limit(limit)
    stations = db.exec(statement).all()

    result = []
    for s in stations:
        result.append({
            "id": s.id,
            "name": s.name,
            "address": s.address,
            "city": s.city,
            "latitude": s.latitude,
            "longitude": s.longitude,
            "status": s.status.value if hasattr(s.status, 'value') else str(s.status),
            "station_type": s.station_type,
            "total_slots": s.total_slots,
            "available_batteries": s.available_batteries,
            "available_slots": s.available_slots,
            "power_rating_kw": s.power_rating_kw,
            "rating": s.rating,
            "total_reviews": s.total_reviews,
            "contact_phone": s.contact_phone,
            "operating_hours": s.operating_hours,
            "is_24x7": s.is_24x7,
            "image_url": s.image_url,
            "last_heartbeat": s.last_heartbeat.isoformat() if s.last_heartbeat else None,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })

    return {
        "stations": result,
        "total_count": total_count,
        "page": skip // limit + 1 if limit > 0 else 1,
        "page_size": limit,
    }


@router.get("/stats")
def get_station_stats(
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """Get station network statistics."""
    total = db.exec(select(func.count()).select_from(Station)).one()
    operational = db.exec(select(func.count()).where(Station.status == StationStatus.OPERATIONAL)).one()
    maintenance = db.exec(select(func.count()).where(Station.status == StationStatus.MAINTENANCE)).one()
    offline = db.exec(select(func.count()).where(Station.status == StationStatus.OFFLINE)).one()
    closed = db.exec(select(func.count()).where(Station.status == StationStatus.CLOSED)).one()
    error = db.exec(select(func.count()).where(Station.status == StationStatus.ERROR)).one()

    total_slots = db.exec(select(func.coalesce(func.sum(Station.total_slots), 0))).one()
    total_available = db.exec(select(func.coalesce(func.sum(Station.available_batteries), 0))).one()

    avg_rating = db.exec(select(func.coalesce(func.avg(Station.rating), 0.0))).one()

    return {
        "total_stations": total,
        "operational": operational,
        "maintenance": maintenance,
        "offline": offline,
        "closed": closed,
        "error": error,
        "total_slots": total_slots,
        "total_available_batteries": total_available,
        "avg_rating": round(float(avg_rating), 2),
    }


@router.post("/")
def create_station(
    request: StationCreateRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """Create a new station."""
    station = Station(
        name=request.name,
        address=request.address,
        city=request.city,
        latitude=request.latitude,
        longitude=request.longitude,
        station_type=request.station_type,
        total_slots=request.total_slots,
        power_rating_kw=request.power_rating_kw,
        contact_phone=request.contact_phone,
        operating_hours=request.operating_hours,
        is_24x7=request.is_24x7,
        status=StationStatus.OPERATIONAL,
        available_slots=request.total_slots,
    )
    db.add(station)
    db.commit()
    db.refresh(station)
    return {"status": "success", "station_id": station.id, "message": f"Station '{station.name}' created"}


@router.get("/{station_id}")
def get_station_detail(
    station_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """Get detailed station info."""
    station = db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    # Get slot details
    slots = db.exec(select(StationSlot).where(StationSlot.station_id == station_id)).all()
    slot_data = [{
        "id": sl.id,
        "slot_number": sl.slot_number,
        "status": sl.status,
        "is_locked": sl.is_locked,
        "battery_id": sl.battery_id,
        "current_power_w": sl.current_power_w,
    } for sl in slots]

    return {
        "id": station.id,
        "name": station.name,
        "address": station.address,
        "city": station.city,
        "latitude": station.latitude,
        "longitude": station.longitude,
        "status": station.status.value if hasattr(station.status, 'value') else str(station.status),
        "station_type": station.station_type,
        "total_slots": station.total_slots,
        "available_batteries": station.available_batteries,
        "available_slots": station.available_slots,
        "power_rating_kw": station.power_rating_kw,
        "rating": station.rating,
        "total_reviews": station.total_reviews,
        "contact_phone": station.contact_phone,
        "operating_hours": station.operating_hours,
        "is_24x7": station.is_24x7,
        "image_url": station.image_url,
        "last_heartbeat": station.last_heartbeat.isoformat() if station.last_heartbeat else None,
        "created_at": station.created_at.isoformat() if station.created_at else None,
        "slots": slot_data,
    }


@router.put("/{station_id}")
def update_station(
    station_id: int,
    request: StationUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """Update a station."""
    station = db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "status":
            setattr(station, key, StationStatus(value) if value else station.status)
        else:
            setattr(station, key, value)

    station.updated_at = datetime.utcnow()
    db.add(station)
    db.commit()
    db.refresh(station)
    return {"status": "success", "message": f"Station '{station.name}' updated"}


@router.delete("/{station_id}")
def delete_station(
    station_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """Delete a station."""
    station = db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    db.delete(station)
    db.commit()
    return {"status": "success", "message": f"Station '{station.name}' deleted"}


# ---- PERFORMANCE ----

@router.get("/{station_id}/performance")
def get_station_performance(
    station_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """Get performance metrics for a station."""
    station = db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    # Calculate utilization
    total = station.total_slots or 1
    occupied = total - (station.available_slots or 0)
    utilization = round((occupied / total) * 100, 1) if total > 0 else 0

    return {
        "station_id": station.id,
        "station_name": station.name,
        "utilization_percentage": utilization,
        "total_slots": station.total_slots,
        "occupied_slots": occupied,
        "available_batteries": station.available_batteries,
        "rating": station.rating,
        "total_reviews": station.total_reviews,
        "status": station.status.value if hasattr(station.status, 'value') else str(station.status),
        "power_rating_kw": station.power_rating_kw,
    }


@router.get("/performance/all")
def get_all_station_performance(
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """Get performance overview for all stations."""
    stations = db.exec(select(Station).order_by(Station.rating.desc())).all()

    result = []
    for s in stations:
        total = s.total_slots or 1
        occupied = total - (s.available_slots or 0)
        utilization = round((occupied / total) * 100, 1) if total > 0 else 0

        result.append({
            "station_id": s.id,
            "station_name": s.name,
            "city": s.city,
            "status": s.status.value if hasattr(s.status, 'value') else str(s.status),
            "utilization_percentage": utilization,
            "total_slots": s.total_slots,
            "occupied_slots": occupied,
            "available_batteries": s.available_batteries,
            "rating": s.rating,
            "total_reviews": s.total_reviews,
            "power_rating_kw": s.power_rating_kw,
        })

    # Aggregate stats
    avg_utilization = round(sum(r["utilization_percentage"] for r in result) / max(len(result), 1), 1)
    avg_rating = round(sum(r["rating"] for r in result) / max(len(result), 1), 2)
    total_batteries = sum(r["available_batteries"] for r in result)

    return {
        "stations": result,
        "summary": {
            "total_stations": len(result),
            "avg_utilization": avg_utilization,
            "avg_rating": avg_rating,
            "total_available_batteries": total_batteries,
        },
    }


# ---- MAINTENANCE ----

@router.get("/maintenance/all")
def list_all_maintenance(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    entity_type: str = "station",
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """List all maintenance records with filters."""
    statement = select(MaintenanceRecord).where(MaintenanceRecord.entity_type == entity_type)

    if status:
        statement = statement.where(MaintenanceRecord.status == status)

    count_stmt = select(func.count()).select_from(statement.subquery())
    total_count = db.exec(count_stmt).one()

    statement = statement.order_by(MaintenanceRecord.performed_at.desc()).offset(skip).limit(limit)
    records = db.exec(statement).all()

    result = []
    for r in records:
        # Get station name
        station_name = None
        if r.entity_type == "station":
            station = db.get(Station, r.entity_id)
            station_name = station.name if station else f"Station #{r.entity_id}"

        result.append({
            "id": r.id,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "entity_name": station_name,
            "technician_id": r.technician_id,
            "maintenance_type": r.maintenance_type,
            "description": r.description,
            "cost": r.cost,
            "parts_replaced": r.parts_replaced,
            "status": r.status,
            "performed_at": r.performed_at.isoformat() if r.performed_at else None,
        })

    return {
        "records": result,
        "total_count": total_count,
        "page": skip // limit + 1 if limit > 0 else 1,
        "page_size": limit,
    }


@router.get("/maintenance/stats")
def get_maintenance_stats(
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """Get maintenance statistics."""
    total = db.exec(
        select(func.count()).where(MaintenanceRecord.entity_type == "station")
    ).one()
    completed = db.exec(
        select(func.count()).where(
            MaintenanceRecord.entity_type == "station",
            MaintenanceRecord.status == "completed"
        )
    ).one()
    scheduled = db.exec(
        select(func.count()).where(
            MaintenanceRecord.entity_type == "station",
            MaintenanceRecord.status == "scheduled"
        )
    ).one()
    in_progress = db.exec(
        select(func.count()).where(
            MaintenanceRecord.entity_type == "station",
            MaintenanceRecord.status == "in_progress"
        )
    ).one()
    total_cost = db.exec(
        select(func.coalesce(func.sum(MaintenanceRecord.cost), 0.0)).where(
            MaintenanceRecord.entity_type == "station"
        )
    ).one()

    # Stations currently in maintenance status
    stations_in_maintenance = db.exec(
        select(func.count()).where(Station.status == StationStatus.MAINTENANCE)
    ).one()

    return {
        "total_records": total,
        "completed": completed,
        "scheduled": scheduled,
        "in_progress": in_progress,
        "total_cost": round(float(total_cost), 2),
        "stations_in_maintenance": stations_in_maintenance,
    }


@router.post("/maintenance/create")
def create_maintenance_record(
    request: MaintenanceCreateRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """Create a new maintenance record."""
    # Verify station exists
    if request.entity_type == "station":
        station = db.get(Station, request.entity_id)
        if not station:
            raise HTTPException(status_code=404, detail="Station not found")

    record = MaintenanceRecord(
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        technician_id=current_user.id,
        maintenance_type=request.maintenance_type,
        description=request.description,
        cost=request.cost,
        parts_replaced=request.parts_replaced,
        status=request.status,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {"status": "success", "record_id": record.id, "message": "Maintenance record created"}


@router.put("/maintenance/{record_id}/status")
def update_maintenance_status(
    record_id: int,
    new_status: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """Update maintenance record status."""
    record = db.get(MaintenanceRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Maintenance record not found")

    record.status = new_status
    db.add(record)
    db.commit()
    db.refresh(record)

    return {"status": "success", "message": f"Maintenance record updated to '{new_status}'"}


# ---- LEGACY ENDPOINTS (kept for backward compat) ----

@router.get("/{station_id}/specs")
def get_station_specs(
    station_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """Get station hardware specs."""
    station = db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    return {
        "station_id": station.id,
        "total_slots": station.total_slots,
        "station_type": station.station_type,
        "power_rating_kw": station.power_rating_kw,
        "max_capacity": station.max_capacity,
        "charger_type": station.charger_type,
        "temperature_control": station.temperature_control,
        "safety_features": station.safety_features,
    }


@router.get("/{station_id}/maintenance")
def get_station_maintenance(
    station_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """Get maintenance records for a specific station."""
    records = db.exec(
        select(MaintenanceRecord).where(
            MaintenanceRecord.entity_type == "station",
            MaintenanceRecord.entity_id == station_id
        ).order_by(MaintenanceRecord.performed_at.desc())
    ).all()

    return [{
        "id": r.id,
        "maintenance_type": r.maintenance_type,
        "description": r.description,
        "cost": r.cost,
        "status": r.status,
        "performed_at": r.performed_at.isoformat() if r.performed_at else None,
    } for r in records]
