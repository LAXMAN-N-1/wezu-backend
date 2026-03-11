from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List
from app.api import deps
from app.models.station import Station
from app.models.maintenance import MaintenanceRecord
from app.schemas.station import StationSpecsResponse, StationSpecsUpdate
from app.schemas.common import DataResponse

router = APIRouter()

@router.get("/{station_id}/specs", response_model=StationSpecsResponse)
async def get_station_specs(
    station_id: int,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_superuser),
):
    """
    SRS Requirement: Detailed station specifications display.
    """
    station = db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    
    return StationSpecsResponse(
        station_id=station.id,
        total_slots=station.total_slots,
        station_type=station.station_type,
        power_rating_kw=station.power_rating_kw,
        max_capacity=station.max_capacity,
        charger_type=station.charger_type,
        temperature_control=station.temperature_control,
        safety_features=station.safety_features
    )

@router.put("/{station_id}/specs", response_model=StationSpecsResponse)
async def update_station_specs(
    station_id: int,
    specs_in: StationSpecsUpdate,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_superuser),
):
    """
    SRS Requirement: Configure station capacity & specs.
    """
    station = db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    
    update_data = specs_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(station, key, value)
    
    db.add(station)
    db.commit()
    db.refresh(station)
    
    return StationSpecsResponse(
        station_id=station.id,
        total_slots=station.total_slots,
        station_type=station.station_type,
        power_rating_kw=station.power_rating_kw,
        max_capacity=station.max_capacity,
        charger_type=station.charger_type,
        temperature_control=station.temperature_control,
        safety_features=station.safety_features
    )

@router.get("/maintenance", response_model=List[MaintenanceRecord])
async def list_all_maintenance(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_superuser),
):
    """
    SRS Requirement: Platform-wide maintenance view for Admin.
    """
    records = db.exec(select(MaintenanceRecord).offset(skip).limit(limit).order_by(MaintenanceRecord.performed_at.desc())).all()
    return records

@router.delete("/{station_id}/maintenance/{task_id}")
async def delete_maintenance_record(
    station_id: int,
    task_id: int,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_superuser),
):
    """
    Delete a specific maintenance record.
    """
    record = db.get(MaintenanceRecord, task_id)
    if not record or record.entity_id != station_id or record.entity_type != "station":
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    
    db.delete(record)
    db.commit()
    return {"status": "success", "message": "Maintenance record deleted"}

@router.get("/{station_id}/maintenance")
async def read_station_maintenance_admin(
    station_id: int,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_superuser),
):
    """
    SRS Match: GET /admin/stations/{id}/maintenance
    """
    from app.services.maintenance_service import MaintenanceService
    return MaintenanceService.get_maintenance_schedule(db, station_id)

@router.post("/{station_id}/maintenance")
async def create_station_maintenance_admin(
    station_id: int,
    data: dict,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_superuser),
):
    """
    SRS Match: POST /admin/stations/{id}/maintenance
    """
    from app.services.maintenance_service import MaintenanceService
    data.update({"entity_type": "station", "entity_id": station_id})
    return MaintenanceService.record_maintenance(db, current_user.id, data)

@router.put("/{station_id}/maintenance/{task_id}")
async def update_station_maintenance_admin(
    station_id: int,
    task_id: int,
    status: str,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_superuser),
):
    """
    Update status of a maintenance task.
    """
    record = db.get(MaintenanceRecord, task_id)
    if not record or record.entity_id != station_id or record.entity_type != "station":
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    
    record.status = status
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
