"""
Admin Audit Logs API — Read-only endpoints for Super Admins.

Provides filtered querying and summary statistics of the audit trail.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select, func

from app.api.deps import get_current_active_superuser
from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User

router = APIRouter()


@router.get("/")
def list_audit_logs(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action type (e.g. LOGIN, CREATE_USER)"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type (e.g. USER, BATTERY)"),
    date_from: Optional[datetime] = Query(None, description="Start of date range (UTC)"),
    date_to: Optional[datetime] = Query(None, description="End of date range (UTC)"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=200, description="Pagination limit"),
):
    """
    List audit log entries with optional filters.
    Requires Super Admin access.
    """
    query = select(AuditLog)

    # Apply filters
    if user_id is not None:
        query = query.where(AuditLog.user_id == user_id)
    if action is not None:
        query = query.where(AuditLog.action == action)
    if resource_type is not None:
        query = query.where(AuditLog.resource_type == resource_type)
    if date_from is not None:
        query = query.where(AuditLog.timestamp >= date_from)
    if date_to is not None:
        query = query.where(AuditLog.timestamp <= date_to)

    # Get total count (before pagination)
    count_query = select(func.count()).select_from(query.subquery())
    total = db.exec(count_query).one()

    # Order and paginate
    query = query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit)
    logs = db.exec(query).all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": logs,
    }


@router.get("/stats")
def audit_log_stats(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    date_from: Optional[datetime] = Query(None, description="Start of date range (UTC)"),
    date_to: Optional[datetime] = Query(None, description="End of date range (UTC)"),
):
    """
    Get audit log summary statistics.
    Returns total count, top actions, and top resource types.
    Requires Super Admin access.
    """
    # Base filter
    base_query = select(AuditLog)
    if date_from is not None:
        base_query = base_query.where(AuditLog.timestamp >= date_from)
    if date_to is not None:
        base_query = base_query.where(AuditLog.timestamp <= date_to)

    # Total count
    total = db.exec(select(func.count()).select_from(base_query.subquery())).one()

    # Top 10 actions
    action_stats = db.exec(
        select(AuditLog.action, func.count(AuditLog.id).label("count"))
        .where(
            *([AuditLog.timestamp >= date_from] if date_from else []),
            *([AuditLog.timestamp <= date_to] if date_to else []),
        )
        .group_by(AuditLog.action)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
    ).all()

    # Top 10 resource types
    resource_stats = db.exec(
        select(AuditLog.resource_type, func.count(AuditLog.id).label("count"))
        .where(
            *([AuditLog.timestamp >= date_from] if date_from else []),
            *([AuditLog.timestamp <= date_to] if date_to else []),
        )
        .group_by(AuditLog.resource_type)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
    ).all()

    return {
        "total_logs": total,
        "top_actions": [{"action": a, "count": c} for a, c in action_stats],
        "top_resource_types": [{"resource_type": r, "count": c} for r, c in resource_stats],
    }
