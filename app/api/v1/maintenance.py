from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime
from app.api import deps
from app.models.user import User
from app.models.maintenance import MaintenanceRecord, StationDowntime, MaintenanceSchedule, MaintenanceTemplate
from app.services.maintenance_service import MaintenanceService
from app.schemas.maintenance import (
    MaintenanceRecordCreate, 
    MaintenanceRecordResponse,
    MaintenanceTemplateCreate,
    MaintenanceTemplateUpdate,
    MaintenanceTemplateResponse,
    MaintenanceScheduleCreate,
    MaintenanceScheduleUpdate,
    MaintenanceScheduleResponse,
    CalendarViewResponse,
    OverdueAlertResponse
)

router = APIRouter()

# --- Maintenance Templates ---

@router.post("/templates", response_model=MaintenanceTemplateResponse)
def create_template(
    template_in: MaintenanceTemplateCreate,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db),
):
    import json
    db_template = MaintenanceTemplate(
        name=template_in.name,
        entity_type=template_in.entity_type,
        station_type=template_in.station_type,
        maintenance_type=template_in.maintenance_type,
        description=template_in.description,
        checklist=json.dumps(template_in.checklist),
        version=template_in.version,
        is_active=template_in.is_active
    )
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    tdict = db_template.dict()
    tdict["checklist"] = json.loads(tdict["checklist"])
    return tdict

@router.get("/templates", response_model=List[MaintenanceTemplateResponse])
def get_templates(
    entity_type: Optional[str] = None,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    query = select(MaintenanceTemplate)
    if entity_type:
        query = query.where(MaintenanceTemplate.entity_type == entity_type)
    templates = db.exec(query).all()
    res = []
    import json
    for t in templates:
        tdict = t.dict()
        try:
            tdict["checklist"] = json.loads(tdict.get("checklist", "[]"))
        except:
            tdict["checklist"] = []
        res.append(tdict)
    return res
@router.put("/templates/{id}", response_model=MaintenanceTemplateResponse)
def update_template(
    id: int,
    template_in: MaintenanceTemplateUpdate,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db),
):
    import json
    db_template = db.get(MaintenanceTemplate, id)
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    update_data = template_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field == "checklist" and value is not None:
            value = json.dumps(value)
        setattr(db_template, field, value)
    
    db_template.updated_at = datetime.utcnow()
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    tdict = db_template.dict()
    try:
        tdict["checklist"] = json.loads(tdict.get("checklist") or "[]")
    except:
        tdict["checklist"] = []
    return tdict

@router.delete("/templates/{id}", response_model=dict)
def delete_template(
    id: int,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db),
):
    db_template = db.get(MaintenanceTemplate, id)
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(db_template)
    db.commit()
    return {"status": "deleted"}

# --- Maintenance Records & Submissions ---

@router.post("/schedule", response_model=MaintenanceScheduleResponse)
def create_schedule(
    schedule_in: MaintenanceScheduleCreate,
    current_user: User = Depends(deps.check_permission("maintenance", "create")),
    db: Session = Depends(deps.get_db),
):
    return MaintenanceService.create_schedule(db, schedule_in.dict())

@router.put("/schedule/{id}", response_model=MaintenanceScheduleResponse)
def update_schedule(
    id: int,
    schedule_in: MaintenanceScheduleUpdate,
    current_user: User = Depends(deps.check_permission("maintenance", "update")),
    db: Session = Depends(deps.get_db),
):
    return MaintenanceService.update_schedule(db, id, schedule_in.dict(exclude_unset=True))

@router.delete("/schedule/{id}", response_model=dict)
def delete_schedule(
    id: int,
    current_user: User = Depends(deps.check_permission("maintenance", "delete")),
    db: Session = Depends(deps.get_db),
):
    schedule = db.get(MaintenanceSchedule, id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(schedule)
    db.commit()
    return {"status": "deleted", "id": id}

@router.get("/calendar", response_model=List[CalendarViewResponse])
def get_calendar(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.check_permission("maintenance", "view")),
):
    return MaintenanceService.get_calendar_view(db)

@router.get("/alerts/overdue", response_model=List[OverdueAlertResponse])
def get_overdue_alerts(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.check_permission("maintenance", "view")),
):
    return MaintenanceService.get_overdue_alerts(db)

# --- Submissions ---

@router.post("/record", response_model=MaintenanceRecordResponse)
def create_maintenance_record(
    record_in: MaintenanceRecordCreate,
    current_user: User = Depends(deps.check_permission("maintenance", "create")),
    db: Session = Depends(deps.get_db),
):
    record = MaintenanceService.record_maintenance(db, current_user.id, record_in.dict())
    rdict = record.dict()
    import json
    for field in ["checklist_result", "parts_replaced"]:
        try:
            rdict[field] = json.loads(rdict.get(field) or ("{}" if "result" in field else "[]"))
        except:
            rdict[field] = {} if "result" in field else []
    try:
        rdict["checklist_submission"] = json.loads(rdict.get("checklist_submission") or "[]")
    except:
        rdict["checklist_submission"] = []
    
    return rdict

@router.delete("/record/{id}", response_model=dict)
def delete_maintenance_record(
    id: int,
    current_user: User = Depends(deps.check_permission("maintenance", "delete")),
    db: Session = Depends(deps.get_db),
):
    record = db.get(MaintenanceRecord, id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    db.delete(record)
    db.commit()
    return {"status": "deleted", "id": id}

@router.get("/submissions", response_model=List[MaintenanceRecordResponse])
def get_maintenance_submissions(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.check_permission("maintenance", "view")),
):
    """Fetch history of completed maintenance tasks (submissions)"""
    records = MaintenanceService.get_all_submissions(db, skip=skip, limit=limit)
    res = []
    import json
    for r in records:
        rdict = r.dict()
        for field in ["checklist_result", "parts_replaced", "checklist_submission"]:
            try:
                rdict[field] = json.loads(rdict.get(field) or ("{}" if "result" in field else "[]"))
            except:
                rdict[field] = {} if "result" in field else []
        res.append(rdict)
    return res

@router.get("/history", response_model=List[MaintenanceRecordResponse])
def get_maintenance_history(
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.check_permission("maintenance", "view")),
):
    query = select(MaintenanceRecord)
    if entity_type:
        query = query.where(MaintenanceRecord.entity_type == entity_type)
    if entity_id:
        query = query.where(MaintenanceRecord.entity_id == entity_id)
        
    query = query.offset(skip).limit(limit).order_by(MaintenanceRecord.performed_at.desc())
    records = db.exec(query).all()
    res = []
    import json
    for r in records:
        rdict = r.dict()
        for field in ["checklist_result", "parts_replaced", "checklist_submission"]:
            try:
                rdict[field] = json.loads(rdict.get(field) or ("{}" if "result" in field else "[]"))
            except:
                rdict[field] = {} if "result" in field else []
        res.append(rdict)
    return res

@router.post("/downtime", response_model=dict)
def report_downtime(
    station_id: int,
    reason: str,
    current_user: User = Depends(deps.check_permission("maintenance", "create")),
    db: Session = Depends(deps.get_db),
):
    MaintenanceService.report_downtime(db, station_id, reason)
    return {"status": "recorded"}
