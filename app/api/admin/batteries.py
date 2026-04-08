from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import ORJSONResponse
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select, func, or_, and_
from typing import List, Optional
from datetime import datetime, UTC, timedelta
import csv
import io

from app.core.database import get_db
from app.core.config import settings
from app.models.battery import Battery, BatteryStatus, BatteryAuditLog, BatteryHealthHistory, LocationType, BatteryLifecycleEvent
from app.schemas.battery import (
    BatteryResponse, BatteryCreate, BatteryUpdate, BatteryDetailResponse,
    BatteryUtilizationResponse, BatteryAuditLogResponse, BatteryListResponse,
    BatteryBulkUpdateRequest, BatteryHealthHistoryResponse
)
from app.api.deps import get_current_active_admin
from app.models.user import User
from app.utils.runtime_cache import cached_call

router = APIRouter(default_response_class=ORJSONResponse)

@router.get("", response_model=BatteryListResponse)
def list_batteries(
    session: Session = Depends(get_db),
    status: Optional[str] = None,
    location_type: Optional[str] = None,
    battery_type: Optional[str] = None,
    min_health: Optional[float] = None,
    max_health: Optional[float] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = Query("created_at", description="Sort column"),
    sort_order: Optional[str] = Query("desc", description="asc or desc"),
    offset: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_active_admin)
):
    def _load():
        from sqlalchemy.orm import selectinload
        query = select(Battery).options(
            selectinload(Battery.sku),
            selectinload(Battery.iot_device)
        )
        count_query = select(func.count(Battery.id))

        nonlocal status, location_type, battery_type, min_health, max_health, search

        # Apply filters to both queries
        if status:
            query = query.where(Battery.status == status)
            count_query = count_query.where(Battery.status == status)
        if location_type:
            query = query.where(Battery.location_type == location_type)
            count_query = count_query.where(Battery.location_type == location_type)
        if battery_type:
            query = query.where(Battery.battery_type == battery_type)
            count_query = count_query.where(Battery.battery_type == battery_type)
        if min_health is not None:
            query = query.where(Battery.health_percentage >= min_health)
            count_query = count_query.where(Battery.health_percentage >= min_health)
        if max_health is not None:
            query = query.where(Battery.health_percentage <= max_health)
            count_query = count_query.where(Battery.health_percentage <= max_health)
        if search:
            search_filter = or_(
                Battery.serial_number.ilike(f"%{search}%"),
                Battery.manufacturer.ilike(f"%{search}%"),
                Battery.notes.ilike(f"%{search}%")
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        # Sorting
        sort_column = getattr(Battery, sort_by, Battery.created_at)
        if sort_order == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        total_count = session.exec(count_query).one()
        items = session.exec(query.offset(offset).limit(limit)).all()

        return {"items": [item.model_dump() for item in items], "total_count": total_count}

    return cached_call(
        "admin-batteries", "list",
        status or "", location_type or "", battery_type or "",
        str(min_health or ""), str(max_health or ""),
        search or "", sort_by or "created_at", sort_order or "desc",
        offset, limit,
        ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS,
        call=_load,
    )

@router.get("/summary", response_model=BatteryUtilizationResponse)
def get_battery_summary(
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    def _load():
        stmt = select(
            func.count(Battery.id).label("total"),
            func.count(Battery.id).filter(Battery.status == BatteryStatus.AVAILABLE).label("available"),
            func.count(Battery.id).filter(Battery.status == BatteryStatus.RENTED).label("rented"),
            func.count(Battery.id).filter(Battery.status == BatteryStatus.MAINTENANCE).label("maintenance"),
            func.count(Battery.id).filter(Battery.status == BatteryStatus.RETIRED).label("retired")
        )

        result = session.exec(stmt).one()
        total = result.total
        rented = result.rented
        utilization = (rented / total * 100) if total > 0 else 0

        return {
            "total_batteries": total,
            "available_count": result.available,
            "rented_count": rented,
            "maintenance_count": result.maintenance,
            "retired_count": result.retired,
            "utilization_percentage": round(utilization, 2)
        }

    return cached_call("admin-batteries", "summary", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_load)

@router.get("/export")
def export_batteries(
    session: Session = Depends(get_db),
    status: Optional[str] = None,
    location_type: Optional[str] = None,
    battery_type: Optional[str] = None,
    min_health: Optional[float] = None,
    max_health: Optional[float] = None,
    current_user: User = Depends(get_current_active_admin)
):
    """Export batteries as CSV download."""
    query = select(Battery)
    if status:
        query = query.where(Battery.status == status)
    if location_type:
        query = query.where(Battery.location_type == location_type)
    if battery_type:
        query = query.where(Battery.battery_type == battery_type)
    if min_health is not None:
        query = query.where(Battery.health_percentage >= min_health)
    if max_health is not None:
        query = query.where(Battery.health_percentage <= max_health)

    batteries = session.exec(query.order_by(Battery.created_at.desc())).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Serial Number", "Status", "Health %", "Location Type",
        "Battery Type", "Manufacturer", "Cycle Count", "Total Cycles",
        "Warranty Expiry", "Created At", "Updated At", "Notes"
    ])
    for b in batteries:
        writer.writerow([
            b.serial_number, b.status, b.health_percentage, b.location_type,
            b.battery_type or "", b.manufacturer or "", b.cycle_count, b.total_cycles,
            b.warranty_expiry.isoformat() if b.warranty_expiry else "",
            b.created_at.isoformat(), b.updated_at.isoformat(),
            b.notes or ""
        ])

    output.seek(0)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=batteries_export_{timestamp}.csv"}
    )

@router.post("/bulk-update")
def bulk_update_batteries(
    req: BatteryBulkUpdateRequest,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """Bulk update battery status using optimized batch operations."""
    if not req.battery_ids:
        return {"updated_count": 0, "total_requested": 0}

    # Retrieve current statuses to log old_value correctly before updating
    current_batteries = session.exec(select(Battery.id, Battery.status).where(Battery.id.in_(req.battery_ids))).all()
    battery_map = {b.id: b.status for b in current_batteries}
    
    if not battery_map:
        return {"updated_count": 0, "total_requested": len(req.battery_ids)}

    from sqlalchemy import update
    stmt = update(Battery).where(Battery.id.in_(battery_map.keys())).values(
        status=req.status,
        updated_at=datetime.now(UTC)
    )
    session.exec(stmt)

    audit_logs = [
        BatteryAuditLog(
            battery_id=bid,
            changed_by=current_user.id,
            field_changed="status",
            old_value=str(old_status),
            new_value=req.status,
            reason="Bulk update by admin"
        ) for bid, old_status in battery_map.items()
    ]
    if audit_logs:
        session.add_all(audit_logs)

    session.commit()
    return {"updated_count": len(battery_map), "total_requested": len(req.battery_ids)}

@router.get("/{battery_id}", response_model=BatteryDetailResponse)
def get_battery_detail(
    battery_id: int,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    battery = session.get(Battery, battery_id)
    if not battery:
        raise HTTPException(status_code=404, detail="Battery not found")
    return battery

@router.get("/{battery_id}/history", response_model=List[BatteryAuditLogResponse])
def get_battery_audit_logs(
    battery_id: int,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    return session.exec(
        select(BatteryAuditLog)
        .where(BatteryAuditLog.battery_id == battery_id)
        .order_by(BatteryAuditLog.timestamp.desc())
    ).all()

@router.get("/{battery_id}/health-history", response_model=List[BatteryHealthHistoryResponse])
def get_battery_health_history(
    battery_id: int,
    days: int = Query(90, description="Number of days of history"),
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    since = datetime.now(UTC) - timedelta(days=days)
    return session.exec(
        select(BatteryHealthHistory)
        .where(BatteryHealthHistory.battery_id == battery_id)
        .where(BatteryHealthHistory.recorded_at >= since)
        .order_by(BatteryHealthHistory.recorded_at.asc())
    ).all()

@router.post("", response_model=BatteryResponse)
def create_battery(
    battery_in: BatteryCreate,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    existing = session.exec(select(Battery).where(Battery.serial_number == battery_in.serial_number)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Serial number already exists")

    db_battery = Battery.model_validate(battery_in)
    db_battery.created_by = current_user.id
    session.add(db_battery)
    session.flush()

    audit_log = BatteryAuditLog(
        battery_id=db_battery.id,
        changed_by=current_user.id,
        field_changed="created",
        new_value=db_battery.serial_number,
        reason="Initial Creation"
    )
    session.add(audit_log)
    session.commit()
    session.refresh(db_battery)
    return db_battery

@router.patch("/{battery_id}", response_model=BatteryResponse)
def update_battery(
    battery_id: int,
    battery_in: BatteryUpdate,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    db_battery = session.get(Battery, battery_id)
    if not db_battery:
        raise HTTPException(status_code=404, detail="Battery not found")

    update_data = battery_in.dict(exclude_unset=True)

    for key, value in update_data.items():
        if key == 'description':
            continue
        old_val = getattr(db_battery, key)
        if old_val != value:
            audit_log = BatteryAuditLog(
                battery_id=battery_id,
                changed_by=current_user.id,
                field_changed=key,
                old_value=str(old_val),
                new_value=str(value),
                reason=battery_in.description or "Manual Admin Update"
            )
            session.add(audit_log)
            setattr(db_battery, key, value)

    db_battery.updated_at = datetime.now(UTC)
    session.add(db_battery)
    session.commit()
    session.refresh(db_battery)
    return db_battery

@router.post("/import")
async def import_batteries(
    file: UploadFile = File(...),
    dry_run: bool = Query(False),
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    content = await file.read()
    decoded = content.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(decoded))

    items = []
    errors = []

    for row in reader:
        serial = row.get('serial_number')
        if not serial:
            errors.append({"row": row, "error": "Missing serial_number"})
            continue

        existing = session.exec(select(Battery).where(Battery.serial_number == serial)).first()
        if existing:
            errors.append({"serial": serial, "error": "Already exists"})
            continue

        battery_data = {
            "serial_number": serial,
            "battery_type": row.get('battery_type', '48V/30Ah'),
            "manufacturer": row.get('manufacturer'),
            "status": row.get('status', 'available'),
            "location_type": row.get('location_type', 'warehouse')
        }
        items.append(battery_data)

        if not dry_run:
            new_battery = Battery(**battery_data)
            new_battery.created_by = current_user.id
            session.add(new_battery)

    if not dry_run:
        session.commit()

    return {
        "imported_count": len(items),
        "error_count": len(errors),
        "errors": errors if dry_run else []
    }
