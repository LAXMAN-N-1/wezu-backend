import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func, case
from typing import Any, List, Optional
from datetime import datetime, UTC
from pydantic import BaseModel
from app.api import deps
from app.models.station import Station, StationStatus, StationSlot
from app.models.maintenance import MaintenanceRecord, StationDowntime
from app.models.maintenance_checklist import (
    MaintenanceChecklistSubmission,
    MaintenanceChecklistTemplate,
)
from app.models.user import User
from app.core.database import get_db
from app.core.config import settings
from app.utils.runtime_cache import cached_call

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


class ChecklistTemplateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    station_type: Optional[str] = "standard"
    maintenance_type: str = "routine"
    tasks: Optional[List[dict[str, Any]]] = None
    items: Optional[List[Any]] = None
    version: Optional[int] = None
    is_active: bool = True


class ChecklistSubmissionRequest(BaseModel):
    event_id: Optional[str] = None
    template_id: str
    template_version: int = 1
    completed_tasks: List[dict[str, Any]]
    submitted_by: Optional[str] = None
    submitted_at: Optional[datetime] = None
    is_final: bool = False


def _normalize_checklist_tasks(
    *,
    tasks: Optional[List[dict[str, Any]]] = None,
    items: Optional[List[Any]] = None,
) -> List[dict[str, Any]]:
    normalized: List[dict[str, Any]] = []

    if tasks:
        for index, task in enumerate(tasks):
            title = str(task.get("title") or "").strip()
            if not title:
                continue
            normalized.append(
                {
                    "id": str(task.get("id") or f"task_{index + 1}"),
                    "title": title,
                    "description": str(task.get("description") or ""),
                    "is_required": bool(task.get("is_required", True)),
                    "is_completed": bool(task.get("is_completed", False)),
                    "note": task.get("note"),
                    "photo_paths": task.get("photo_paths") or [],
                }
            )
        return normalized

    for index, item in enumerate(items or []):
        title = str(item).strip()
        if not title:
            continue
        normalized.append(
            {
                "id": f"task_{index + 1}",
                "title": title,
                "description": "",
                "is_required": True,
                "is_completed": False,
                "note": None,
                "photo_paths": [],
            }
        )
    return normalized


def _serialize_template(template: MaintenanceChecklistTemplate) -> dict[str, Any]:
    return {
        "id": str(template.id),
        "name": template.name,
        "description": template.description or "",
        "station_type": template.station_type,
        "maintenance_type": template.maintenance_type,
        "tasks": template.tasks or [],
        "version": template.version,
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
        "is_active": template.is_active,
    }


def _serialize_submission(submission: MaintenanceChecklistSubmission) -> dict[str, Any]:
    return {
        "id": str(submission.id),
        "event_id": str(submission.maintenance_record_id) if submission.maintenance_record_id is not None else "",
        "template_id": str(submission.template_id),
        "template_version": submission.template_version,
        "completed_tasks": submission.completed_tasks or [],
        "submitted_by": submission.submitted_by_name or "Unknown",
        "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None,
        "is_final": submission.is_final,
    }


# ---- STATION LISTING & CRUD ----

@router.get("", include_in_schema=False)
@router.get("/")
def list_stations(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    status: Optional[str] = None,
    city: Optional[str] = None,
    station_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """List all stations with pagination, search, and filters."""
    def _load():
        filters = []
        if search:
            filters.append(
                (Station.name.ilike(f"%{search}%")) |
                (Station.address.ilike(f"%{search}%")) |
                (Station.city.ilike(f"%{search}%"))
            )
        if status:
            filters.append(Station.status == status)
        if city:
            filters.append(Station.city.ilike(f"%{city}%"))
        if station_type:
            filters.append(Station.station_type == station_type)

        total_count = db.exec(select(func.count(Station.id)).where(*filters)).one() or 0

        statement = select(Station).where(*filters).order_by(Station.created_at.desc()).offset(skip).limit(limit)
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

    return cached_call(
        "admin-stations", "list",
        skip, limit, search or "", status or "", city or "", station_type or "",
        ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS,
        call=_load,
    )


@router.get("/stats")
def get_station_stats(
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """Get station network statistics."""
    def _load():
        row = db.exec(
            select(
                func.count(Station.id),
                func.coalesce(func.sum(case((Station.status == StationStatus.OPERATIONAL, 1), else_=0)), 0),
                func.coalesce(func.sum(case((Station.status == StationStatus.MAINTENANCE, 1), else_=0)), 0),
                func.coalesce(func.sum(case((Station.status == StationStatus.OFFLINE, 1), else_=0)), 0),
                func.coalesce(func.sum(case((Station.status == StationStatus.CLOSED, 1), else_=0)), 0),
                func.coalesce(func.sum(case((Station.status == StationStatus.ERROR, 1), else_=0)), 0),
                func.coalesce(func.sum(Station.total_slots), 0),
                func.coalesce(func.sum(Station.available_batteries), 0),
                func.coalesce(func.avg(Station.rating), 0.0),
            )
        ).one()
        return {
            "total_stations": int(row[0]),
            "operational": int(row[1]),
            "maintenance": int(row[2]),
            "offline": int(row[3]),
            "closed": int(row[4]),
            "error": int(row[5]),
            "total_slots": int(row[6]),
            "total_available_batteries": int(row[7]),
            "avg_rating": round(float(row[8]), 2),
        }

    return cached_call("admin-stations", "stats", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_load)


@router.post("/")
def create_station(
    request: StationCreateRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
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
    current_user: Any = Depends(deps.get_current_active_admin),
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
    current_user: Any = Depends(deps.get_current_active_admin),
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

    station.updated_at = datetime.now(UTC)
    db.add(station)
    db.commit()
    db.refresh(station)
    return {"status": "success", "message": f"Station '{station.name}' updated"}


@router.delete("/{station_id}")
def delete_station(
    station_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
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
    current_user: Any = Depends(deps.get_current_active_admin),
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
    current_user: Any = Depends(deps.get_current_active_admin),
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
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """List all maintenance records with filters."""
    statement = select(MaintenanceRecord).where(MaintenanceRecord.entity_type == entity_type)

    if status:
        statement = statement.where(MaintenanceRecord.status == status)

    count_stmt = select(func.count()).select_from(statement.subquery())
    total_count = db.exec(count_stmt).one()

    statement = statement.order_by(MaintenanceRecord.performed_at.desc()).offset(skip).limit(limit)
    records = db.exec(statement).all()

    station_ids = {r.entity_id for r in records if r.entity_type == "station"}
    station_map = {s.id: s.name for s in db.exec(select(Station).where(Station.id.in_(station_ids))).all()} if station_ids else {}

    result = []
    for r in records:
        # Get station name
        station_name = None
        if r.entity_type == "station":
            station_name = station_map.get(r.entity_id, f"Station #{r.entity_id}")

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
    period: str = Query("30d"),
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
):
    """Get maintenance statistics."""
    def _load():
        row = db.exec(
            select(
                func.count(MaintenanceRecord.id),
                func.coalesce(func.sum(case((MaintenanceRecord.status == "completed", 1), else_=0)), 0),
                func.coalesce(func.sum(case((MaintenanceRecord.status == "scheduled", 1), else_=0)), 0),
                func.coalesce(func.sum(case((MaintenanceRecord.status == "in_progress", 1), else_=0)), 0),
                func.coalesce(func.sum(MaintenanceRecord.cost), 0.0),
            ).where(MaintenanceRecord.entity_type == "station")
        ).one()

        stations_in_maintenance = db.exec(
            select(func.count()).where(Station.status == StationStatus.MAINTENANCE)
        ).one()

        return {
            "total_records": int(row[0]),
            "completed": int(row[1]),
            "scheduled": int(row[2]),
            "in_progress": int(row[3]),
            "total_cost": round(float(row[4]), 2),
            "stations_in_maintenance": stations_in_maintenance,
        }

    return cached_call("admin-stations", "maintenance-stats", period, ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_load)


@router.post("/maintenance/create")
def create_maintenance_record(
    request: MaintenanceCreateRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
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
    current_user: Any = Depends(deps.get_current_active_admin),
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


@router.get("/maintenance/checklists/templates")
def list_checklist_templates(
    station_type: Optional[str] = None,
    maintenance_type: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    statement = select(MaintenanceChecklistTemplate)

    if active_only:
        statement = statement.where(MaintenanceChecklistTemplate.is_active == True)
    if station_type:
        statement = statement.where(
            func.lower(MaintenanceChecklistTemplate.station_type) == station_type.lower()
        )
    if maintenance_type:
        statement = statement.where(
            func.lower(MaintenanceChecklistTemplate.maintenance_type) == maintenance_type.lower()
        )

    templates = db.exec(
        statement.order_by(MaintenanceChecklistTemplate.updated_at.desc())
    ).all()
    return {"items": [_serialize_template(template) for template in templates]}


@router.post("/maintenance/checklists/templates")
def create_checklist_template(
    request: ChecklistTemplateRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    tasks = _normalize_checklist_tasks(tasks=request.tasks, items=request.items)
    if not tasks:
        raise HTTPException(status_code=400, detail="Checklist template must contain at least one task")

    template = MaintenanceChecklistTemplate(
        name=request.name.strip(),
        description=(request.description or "").strip() or None,
        station_type=(request.station_type or "standard").strip().lower(),
        maintenance_type=request.maintenance_type.strip().lower(),
        tasks=tasks,
        version=request.version or 1,
        is_active=request.is_active,
        created_by_user_id=current_user.id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return _serialize_template(template)


@router.put("/maintenance/checklists/templates/{template_id}")
def update_checklist_template(
    template_id: int,
    request: ChecklistTemplateRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    template = db.get(MaintenanceChecklistTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Checklist template not found")

    tasks = _normalize_checklist_tasks(tasks=request.tasks, items=request.items)
    if not tasks:
        raise HTTPException(status_code=400, detail="Checklist template must contain at least one task")

    template.name = request.name.strip()
    template.description = (request.description or "").strip() or None
    template.station_type = (request.station_type or template.station_type).strip().lower()
    template.maintenance_type = request.maintenance_type.strip().lower()
    template.tasks = tasks
    template.version = request.version or (template.version + 1)
    template.is_active = request.is_active
    template.updated_at = datetime.now(UTC)

    db.add(template)
    db.commit()
    db.refresh(template)
    return _serialize_template(template)


@router.delete("/maintenance/checklists/templates/{template_id}")
def delete_checklist_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    template = db.get(MaintenanceChecklistTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Checklist template not found")

    template.is_active = False
    template.updated_at = datetime.now(UTC)
    db.add(template)
    db.commit()
    return {"status": "success", "message": "Checklist template archived"}


@router.get("/maintenance/checklists/submissions")
def list_checklist_submissions(
    event_id: Optional[str] = None,
    template_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    statement = select(MaintenanceChecklistSubmission)
    if event_id and event_id.isdigit():
        statement = statement.where(
            MaintenanceChecklistSubmission.maintenance_record_id == int(event_id)
        )
    if template_id:
        statement = statement.where(MaintenanceChecklistSubmission.template_id == template_id)

    submissions = db.exec(
        statement.order_by(MaintenanceChecklistSubmission.submitted_at.desc())
    ).all()
    return {"items": [_serialize_submission(submission) for submission in submissions]}


@router.post("/maintenance/checklists/submissions")
def create_checklist_submission(
    request: ChecklistSubmissionRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    template_id = int(request.template_id)
    template = db.get(MaintenanceChecklistTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Checklist template not found")

    maintenance_record_id = None
    if request.event_id:
        if not request.event_id.isdigit():
            raise HTTPException(status_code=400, detail="event_id must be numeric")
        maintenance_record_id = int(request.event_id)
        if not db.get(MaintenanceRecord, maintenance_record_id):
            raise HTTPException(status_code=404, detail="Maintenance record not found")

    submission = MaintenanceChecklistSubmission(
        maintenance_record_id=maintenance_record_id,
        template_id=template_id,
        template_version=request.template_version or template.version,
        completed_tasks=_normalize_checklist_tasks(tasks=request.completed_tasks),
        submitted_by_user_id=current_user.id,
        submitted_by_name=request.submitted_by or current_user.full_name or current_user.email or "Admin",
        submitted_at=request.submitted_at or datetime.now(UTC),
        is_final=request.is_final,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    if maintenance_record_id and request.is_final:
        record = db.get(MaintenanceRecord, maintenance_record_id)
        if record:
            record.status = "completed"
            db.add(record)
            db.commit()

    return _serialize_submission(submission)


# ---- LEGACY ENDPOINTS (kept for backward compat) ----

@router.get("/{station_id}/specs")
def get_station_specs(
    station_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
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
    current_user: Any = Depends(deps.get_current_active_admin),
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
