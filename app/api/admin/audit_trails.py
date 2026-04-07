from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func, text, case
from typing import Any, Optional
from datetime import datetime, UTC, timedelta
from app.api import deps
from app.models.inventory_audit import InventoryAuditLog
from app.models.user import User
from app.core.database import get_db
from app.core.config import settings
from app.utils.runtime_cache import cached_call

router = APIRouter()


@router.get("/stats")
def get_audit_stats(
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """Get summary statistics for inventory audit trail."""
    def _load():
        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)

        row = db.exec(
            select(
                func.count(InventoryAuditLog.id),
                func.coalesce(func.sum(case((InventoryAuditLog.timestamp >= today_start, 1), else_=0)), 0),
                func.coalesce(func.sum(case((InventoryAuditLog.timestamp >= week_ago, 1), else_=0)), 0),
                func.coalesce(func.sum(case((InventoryAuditLog.action_type == "transfer", 1), else_=0)), 0),
                func.coalesce(func.sum(case((InventoryAuditLog.action_type == "disposal", 1), else_=0)), 0),
                func.coalesce(func.sum(case((InventoryAuditLog.action_type == "status_change", 1), else_=0)), 0),
                func.coalesce(func.sum(case((InventoryAuditLog.action_type == "manual_entry", 1), else_=0)), 0),
            )
        ).one()

        return {
            "total_entries": int(row[0]),
            "today_count": int(row[1]),
            "week_count": int(row[2]),
            "transfers": int(row[3]),
            "disposals": int(row[4]),
            "status_changes": int(row[5]),
            "manual_entries": int(row[6]),
        }

    return cached_call("admin-audit", "stats", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_load)


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
