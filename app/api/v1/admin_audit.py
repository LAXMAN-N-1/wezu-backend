"""
Admin Audit Logs API — Read-only endpoints for Super Admins.

Provides filtered querying, summary statistics, and CSV/JSON export.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, JSONResponse
from sqlmodel import Session, select, func

from app.api.deps import get_current_active_superuser
from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.audit_service import AuditService

router = APIRouter()


@router.get("/")
async def list_audit_logs(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action type (e.g. AUTH_LOGIN)"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type (e.g. USER, BATTERY)"),
    target_id: Optional[int] = Query(None, description="Filter by target entity ID"),
    date_from: Optional[datetime] = Query(None, description="Start of date range (UTC)"),
    date_to: Optional[datetime] = Query(None, description="End of date range (UTC)"),
    level: Optional[str] = Query(None, description="Filter by severity level (INFO, WARNING, CRITICAL)"),
    is_suspicious: Optional[bool] = Query(None, description="Filter for suspicious events"),
    ip_address: Optional[str] = Query(None, description="Filter by source IP address"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=200, description="Pagination limit"),
):
    """
    List audit log entries with advanced forensic filters and pagination.
    Requires Super Admin access.
    """
    audit_service = AuditService()
    result = await audit_service.get_logs_advanced(
        db=db,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        target_id=target_id,
        date_from=date_from,
        date_to=date_to,
        level=level,
        is_suspicious=is_suspicious,
        ip_address=ip_address,
        page=(skip // limit) + 1,
        limit=limit
    )

    return {
        "total": result["total_count"],
        "skip": skip,
        "limit": limit,
        "data": result["logs"],
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
    """
    base_query = select(AuditLog)
    if date_from is not None:
        base_query = base_query.where(AuditLog.timestamp >= date_from)
    if date_to is not None:
        base_query = base_query.where(AuditLog.timestamp <= date_to)

    total = db.exec(select(func.count()).select_from(base_query.subquery())).one()

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


@router.get("/export/csv")
def export_audit_csv(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    user_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    target_id: Optional[int] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
):
    """Export filtered audit logs as CSV download."""
    csv_content = AuditService.export_logs_csv(
        db,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        target_id=target_id,
        date_from=date_from,
        date_to=date_to,
    )
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
    )


@router.get("/export/json")
def export_audit_json(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    user_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    target_id: Optional[int] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
):
    """Export filtered audit logs as JSON download."""
    json_data = AuditService.export_logs_json(
        db,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        target_id=target_id,
        date_from=date_from,
        date_to=date_to,
    )
    return JSONResponse(
        content=json_data,
        headers={"Content-Disposition": "attachment; filename=audit_logs.json"},
    )
