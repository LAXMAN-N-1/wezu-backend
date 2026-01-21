from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime
from app.api import deps
from app.models.user import User
from app.models.maintenance import MaintenanceRecord, StationDowntime, MaintenanceSchedule
from app.services.maintenance_service import MaintenanceService
from pydantic import BaseModel

router = APIRouter()

class MaintenanceRecordCreate(BaseModel):
    entity_type: str
    entity_id: int
    maintenance_type: str
    description: str
    cost: Optional[float] = 0.0
    parts_replaced: Optional[str] = None
    status: str = "completed"

class DowntimeReport(BaseModel):
    station_id: int
    reason: str

@router.post("/record", response_model=MaintenanceRecord)
def create_maintenance_record(
    record_in: MaintenanceRecordCreate,
    current_user: User = Depends(deps.get_current_active_superuser), # Technician/Admin
    db: Session = Depends(deps.get_db),
):
    # Pass dict
    return MaintenanceService.record_maintenance(current_user.id, record_in.dict())

@router.post("/downtime", response_model=dict)
def report_downtime(
    report_in: DowntimeReport,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    MaintenanceService.report_downtime(report_in.station_id, report_in.reason)
    return {"status": "recorded"}

@router.get("/history", response_model=List[MaintenanceRecord])
def get_maintenance_history(
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
):
    query = select(MaintenanceRecord)
    if entity_type:
        query = query.where(MaintenanceRecord.entity_type == entity_type)
    if entity_id:
        query = query.where(MaintenanceRecord.entity_id == entity_id)
        
    query = query.offset(skip).limit(limit).order_by(MaintenanceRecord.performed_at.desc())
    return db.exec(query).all()
