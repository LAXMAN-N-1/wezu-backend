from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func, text
from typing import Any, Optional
from datetime import datetime, timedelta, timezone; UTC = timezone.utc
from app.api import deps
from app.models.inventory_audit import InventoryAuditLog
from app.models.user import User
from app.core.database import get_db

router = APIRouter()
_inventory_audit_table_supported: bool | None = None


def _has_inventory_audit_table(db: Session) -> bool:
    global _inventory_audit_table_supported
    if _inventory_audit_table_supported is not None:
        return _inventory_audit_table_supported

    try:
        result = db.exec(
            text("SELECT 1 FROM information_schema.tables WHERE table_name='inventory_audit_logs' LIMIT 1")
        ).first()
        _inventory_audit_table_supported = result is not None
    except Exception:
        _inventory_audit_table_supported = False

    return _inventory_audit_table_supported


@router.get("/stats")
def get_audit_stats(
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """Get summary statistics for inventory audit trail."""
    if not _has_inventory_audit_table(db):
        return {
            "total_entries": 0,
            "today_count": 0,
            "week_count": 0,
            "transfers": 0,
            "disposals": 0,
            "status_changes": 0,
            "manual_entries": 0,
        }

    total = db.exec(select(func.count(InventoryAuditLog.id))).one()

    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = db.exec(
        select(func.count(InventoryAuditLog.id)).where(InventoryAuditLog.timestamp >= today_start)
    ).one()

    # Count by action type
    transfers = db.exec(
        select(func.count(InventoryAuditLog.id)).where(InventoryAuditLog.action_type == "transfer")
    ).one()
    disposals = db.exec(
        select(func.count(InventoryAuditLog.id)).where(InventoryAuditLog.action_type == "disposal")
    ).one()
    status_changes = db.exec(
        select(func.count(InventoryAuditLog.id)).where(InventoryAuditLog.action_type == "status_change")
    ).one()
    manual_entries = db.exec(
        select(func.count(InventoryAuditLog.id)).where(InventoryAuditLog.action_type == "manual_entry")
    ).one()

    # Last 7 days trend
    week_ago = datetime.now(UTC) - timedelta(days=7)
    week_count = db.exec(
        select(func.count(InventoryAuditLog.id)).where(InventoryAuditLog.timestamp >= week_ago)
    ).one()

    return {
        "total_entries": total,
        "today_count": today_count,
        "week_count": week_count,
        "transfers": transfers,
        "disposals": disposals,
        "status_changes": status_changes,
        "manual_entries": manual_entries,
    }


@router.get("/")
def list_audit_trails(
    skip: int = 0,
    limit: int = 50,
    action_type: Optional[str] = None,
    battery_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """List inventory audit logs with filters."""
    if not _has_inventory_audit_table(db):
        return {
            "entries": [],
            "total_count": 0,
            "page": skip // limit + 1 if limit > 0 else 1,
            "page_size": limit,
        }

    statement = select(InventoryAuditLog)

    if action_type:
        statement = statement.where(InventoryAuditLog.action_type == action_type)

    if battery_id:
        statement = statement.where(InventoryAuditLog.battery_id == battery_id)

    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            statement = statement.where(InventoryAuditLog.timestamp >= dt_from)
        except ValueError:
            pass

    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            statement = statement.where(InventoryAuditLog.timestamp <= dt_to)
        except ValueError:
            pass

    if search:
        statement = statement.where(InventoryAuditLog.notes.ilike(f"%{search}%"))

    count_stmt = select(func.count()).select_from(statement.subquery())
    total_count = db.exec(count_stmt).one()

    statement = statement.order_by(InventoryAuditLog.timestamp.desc()).offset(skip).limit(limit)
    logs = db.exec(statement).all()

    actor_ids = {log.actor_id for log in logs if log.actor_id}
    actor_map = {u.id: u for u in db.exec(select(User).where(User.id.in_(actor_ids))).all()} if actor_ids else {}

    result = []
    for log in logs:
        actor = actor_map.get(log.actor_id) if log.actor_id else None
        result.append({
            "id": log.id,
            "battery_id": log.battery_id,
            "action_type": log.action_type,
            "from_location_type": log.from_location_type,
            "from_location_id": log.from_location_id,
            "to_location_type": log.to_location_type,
            "to_location_id": log.to_location_id,
            "actor_id": log.actor_id,
            "actor_name": actor.full_name if actor else "System",
            "notes": log.notes,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        })

    return {
        "entries": result,
        "total_count": total_count,
        "page": skip // limit + 1 if limit > 0 else 1,
        "page_size": limit,
    }


@router.get("/{entry_id}")
def get_audit_detail(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """Get a single audit log entry detail."""
    if not _has_inventory_audit_table(db):
        raise HTTPException(status_code=404, detail="Audit log entry not found")

    log = db.get(InventoryAuditLog, entry_id)
    if not log:
        raise HTTPException(status_code=404, detail="Audit log entry not found")

    actor = db.get(User, log.actor_id) if log.actor_id else None

    return {
        "id": log.id,
        "battery_id": log.battery_id,
        "action_type": log.action_type,
        "from_location_type": log.from_location_type,
        "from_location_id": log.from_location_id,
        "to_location_type": log.to_location_type,
        "to_location_id": log.to_location_id,
        "actor_id": log.actor_id,
        "actor_name": actor.full_name if actor else "System",
        "notes": log.notes,
        "timestamp": log.timestamp.isoformat() if log.timestamp else None,
    }
