from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select, func
from app.api import deps
from app.core.database import get_db
from app.models.user import User
from app.models.audit_log import AuditLog
from app.services.audit_service import AuditService
from datetime import datetime, UTC, timedelta
from typing import List, Dict, Any

router = APIRouter()

@router.get("/dashboard/stats")
async def get_audit_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """Fetch counts for the 4 top status cards."""
    return AuditService.get_dashboard_counts(db)

@router.get("/dashboard/activity-chart")
async def get_activity_chart_data(
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """Fetch time-series data for the fl_chart LineChart (API Requests vs Failed Logins)."""
    end_date = datetime.now(UTC).date()
    start_date = end_date - timedelta(days=days-1)
    
    # We aggregate by day
    # In production, this would be a single complex GROUP BY query
    # For now, we iterate to match the chart format requirements
    data = []
    for i in range(days):
        date = start_date + timedelta(days=i)
        
        api_requests = db.exec(
            select(func.count(AuditLog.id))
            .where(func.date(AuditLog.timestamp) == date)
        ).one()
        
        failed_logins = db.exec(
            select(func.count(AuditLog.id))
            .where(func.date(AuditLog.timestamp) == date)
            .where(AuditLog.action == "AUTH_LOGIN")
            .where(AuditLog.status == "failure")
        ).one()
        
        data.append({
            "date": date.isoformat(),
            "api_requests": api_requests,
            "failed_logins": failed_logins
        })
        
    return data

@router.get("/dashboard/categories")
async def get_category_distribution(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """Fetch data for the fl_chart DonutChart (Event Categories)."""
    # Categories: Auth Events | Data Changes | System Events | Security Threats (Critical)
    
    auth_events = db.exec(
        select(func.count(AuditLog.id)).where(AuditLog.module == "auth")
    ).one()
    
    data_changes = db.exec(
        select(func.count(AuditLog.id)).where(AuditLog.action == "DATA_MODIFICATION")
    ).one()
    
    security_threats = db.exec(
        select(func.count(AuditLog.id)).where(AuditLog.level == "CRITICAL")
    ).one()
    
    total = db.exec(select(func.count(AuditLog.id))).one()
    system_events = max(0, total - auth_events - data_changes - security_threats)
    
    return [
        {"category": "Auth Events", "count": auth_events},
        {"category": "Data Changes", "count": data_changes},
        {"category": "Security Threats", "count": security_threats},
        {"category": "System Events", "count": system_events}
    ]

@router.get("/dashboard/recent-critical")
async def get_recent_critical_events(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """Fetch the last 10 'High Severity' events for the scrolling tracker."""
    return db.exec(
        select(AuditLog)
        .where(AuditLog.level == "CRITICAL")
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
    ).all()
