"""Security Settings Admin API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from typing import List, Optional
from datetime import datetime, UTC, timedelta

from app.core.database import get_db
from app.api.deps import get_current_active_admin
from app.models.user import User
from app.models.audit_log import AuditLog, SecurityEvent
from app.models.login_history import LoginHistory
from app.models.system import SystemConfig

router = APIRouter()


# ============================================================================
# Security Dashboard (aggregate view)
# ============================================================================

@router.get("/dashboard")
def security_dashboard(
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
):
    """Aggregated security dashboard for admin UI."""
    now = datetime.now(UTC)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)

    # ── Audit log stats (single query) ──
    audit_today = session.exec(
        select(func.count(AuditLog.id)).where(AuditLog.timestamp >= today)
    ).one() or 0

    # ── Security events breakdown (single aggregation query) ──
    se_rows = session.exec(
        select(
            func.count(SecurityEvent.id).label("total"),
            func.count(SecurityEvent.id).filter(SecurityEvent.is_resolved == False).label("unresolved"),
            func.count(SecurityEvent.id).filter(
                SecurityEvent.severity == "critical",
                SecurityEvent.is_resolved == False,
            ).label("critical"),
            func.count(SecurityEvent.id).filter(SecurityEvent.timestamp >= week_ago).label("this_week"),
        )
    ).one()
    total_events, unresolved_events, critical_events, events_this_week = se_rows

    # Recent events
    recent = session.exec(
        select(SecurityEvent)
        .order_by(SecurityEvent.timestamp.desc())
        .limit(5)
    ).all()

    return {
        "audit_logs": {
            "today": audit_today,
        },
        "security_events": {
            "total": total_events or 0,
            "unresolved": unresolved_events or 0,
            "critical_unresolved": critical_events or 0,
            "this_week": events_this_week or 0,
        },
        "threat_level": "critical" if (critical_events or 0) > 0 else "normal",
        "recent_events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "severity": e.severity,
                "details": e.details,
                "timestamp": e.timestamp,
                "is_resolved": e.is_resolved,
            }
            for e in recent
        ],
    }


# ============================================================================
# Fraud Alerts
# ============================================================================

@router.get("/fraud-alerts")
def list_fraud_alerts(
    session: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
    severity: Optional[str] = None,
    current_user: User = Depends(get_current_active_admin),
):
    """List security events flagged as fraud-related."""
    fraud_types = [
        "suspicious_login", "brute_force", "account_takeover",
        "unusual_transaction", "velocity_check_failed", "ip_anomaly",
        "device_fingerprint_mismatch", "fraud",
    ]
    filters = [SecurityEvent.event_type.in_(fraud_types)]
    if severity:
        filters.append(SecurityEvent.severity == severity)

    total = session.exec(
        select(func.count(SecurityEvent.id)).where(*filters)
    ).one() or 0
    alerts = session.exec(
        select(SecurityEvent).where(*filters)
        .order_by(SecurityEvent.timestamp.desc()).offset(skip).limit(limit)
    ).all()

    return {
        "items": [
            {
                "id": a.id,
                "event_type": a.event_type,
                "severity": a.severity,
                "details": a.details,
                "source_ip": a.source_ip,
                "user_id": a.user_id,
                "timestamp": a.timestamp,
                "is_resolved": a.is_resolved,
            }
            for a in alerts
        ],
        "total_count": total,
    }

# ============================================================================
# Audit Logs (enhanced)
# ============================================================================

@router.get("/audit-logs")
def list_audit_logs(
    session: Session = Depends(get_db),
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    user_id: Optional[int] = None,
    days: int = Query(30, description="Days of history"),
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_active_admin),
):
    since = datetime.now(UTC) - timedelta(days=days)

    # Build a shared WHERE clause so count and data queries match
    filters = [AuditLog.timestamp >= since]
    if action:
        filters.append(AuditLog.action == action)
    if resource_type:
        filters.append(AuditLog.resource_type == resource_type)
    if user_id:
        filters.append(AuditLog.user_id == user_id)

    total = session.exec(select(func.count(AuditLog.id)).where(*filters)).one()
    logs = session.exec(
        select(AuditLog).where(*filters)
        .order_by(AuditLog.timestamp.desc())
        .offset(skip).limit(limit)
    ).all()

    return {
        "items": [
            {
                "id": log.id, "user_id": log.user_id, "action": log.action,
                "resource_type": log.resource_type, "resource_id": log.resource_id,
                "details": log.details, "ip_address": log.ip_address,
                "user_agent": log.user_agent, "timestamp": log.timestamp,
                "old_value": log.old_value, "new_value": log.new_value,
            }
            for log in logs
        ],
        "total_count": total,
    }


@router.get("/login-activity")
def list_login_activity(
    session: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = Query(None, description="Filter by login status"),
    current_user: User = Depends(get_current_active_admin),
):
    filters = []
    if status:
        filters.append(LoginHistory.status == status)

    total = session.exec(
        select(func.count(LoginHistory.id)).where(*filters)
    ).one()

    rows = session.exec(
        select(LoginHistory, User)
        .join(User, User.id == LoginHistory.user_id)
        .where(*filters)
        .order_by(LoginHistory.timestamp.desc())
        .offset(skip)
        .limit(limit)
    ).all()

    return {
        "items": [
            {
                "id": log.id,
                "timestamp": log.timestamp,
                "user_id": user.id,
                "user_name": user.full_name or user.email or f"User #{user.id}",
                "email": user.email,
                "role_name": user.role.name if user.role else user.user_type.value,
                "ip_address": log.ip_address,
                "device_browser": log.user_agent,
                "status": log.status,
                "is_success": log.status.lower() == "success",
            }
            for log, user in rows
        ],
        "total_count": total,
    }


@router.get("/audit-logs/stats")
def audit_stats(
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
):
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)

    today_count = session.exec(
        select(func.count(AuditLog.id)).where(AuditLog.timestamp >= today)
    ).one()
    week_count = session.exec(
        select(func.count(AuditLog.id)).where(AuditLog.timestamp >= week_ago)
    ).one()

    # Action breakdown (last 30 days only to avoid full table scan)
    month_ago = today - timedelta(days=30)
    actions = {}
    rows = session.exec(
        select(AuditLog.action, func.count(AuditLog.id))
        .where(AuditLog.timestamp >= month_ago)
        .group_by(AuditLog.action)
    ).all()
    for action, count in rows:
        actions[action] = count

    return {
        "today": today_count,
        "this_week": week_count,
        "by_action": actions,
    }


# ============================================================================
# Security Events
# ============================================================================

@router.get("/security-events")
def list_security_events(
    session: Session = Depends(get_db),
    severity: Optional[str] = None,
    event_type: Optional[str] = None,
    is_resolved: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_active_admin),
):
    query = select(SecurityEvent)
    filters = []
    if severity:
        filters.append(SecurityEvent.severity == severity)
    if event_type:
        filters.append(SecurityEvent.event_type == event_type)
    if is_resolved is not None:
        filters.append(SecurityEvent.is_resolved == is_resolved)
    if filters:
        query = query.where(*filters)

    total = session.exec(
        select(func.count(SecurityEvent.id)).where(*filters) if filters
        else select(func.count(SecurityEvent.id))
    ).one()
    events = session.exec(query.order_by(SecurityEvent.timestamp.desc()).offset(skip).limit(limit)).all()

    return {
        "items": [
            {
                "id": e.id, "event_type": e.event_type, "severity": e.severity,
                "details": e.details, "source_ip": e.source_ip,
                "user_id": e.user_id, "timestamp": e.timestamp,
                "is_resolved": e.is_resolved,
            }
            for e in events
        ],
        "total_count": total,
    }


@router.patch("/security-events/{event_id}/resolve")
def resolve_security_event(
    event_id: int,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
):
    event = session.get(SecurityEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    event.is_resolved = True
    session.add(event)
    session.commit()
    return {"message": "Security event resolved"}


# ============================================================================
# Security Settings
# ============================================================================

@router.get("/security-settings")
def get_security_settings(
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
):
    """Get platform security configuration."""
    # Read from SystemConfig or return defaults
    keys = ["2fa_enabled", "session_timeout_minutes", "max_login_attempts",
            "ip_whitelist_enabled", "password_min_length", "password_expiry_days"]
    configs = session.exec(select(SystemConfig).where(SystemConfig.key.in_(keys))).all()
    config_map = {c.key: c.value for c in configs}

    return {
        "two_factor_auth": {
            "enabled": config_map.get("2fa_enabled", "false") == "true",
            "enforcement": "optional",
        },
        "session_management": {
            "timeout_minutes": int(config_map.get("session_timeout_minutes", "60")),
            "max_concurrent_sessions": 3,
        },
        "login_security": {
            "max_attempts": int(config_map.get("max_login_attempts", "5")),
            "lockout_duration_minutes": 30,
        },
        "password_policy": {
            "min_length": int(config_map.get("password_min_length", "8")),
            "require_uppercase": True,
            "require_numbers": True,
            "require_special_chars": True,
            "expiry_days": int(config_map.get("password_expiry_days", "90")),
        },
        "ip_whitelist": {
            "enabled": config_map.get("ip_whitelist_enabled", "false") == "true",
            "addresses": [],
        },
    }


@router.patch("/security-settings")
def update_security_settings(
    session: Session = Depends(get_db),
    two_factor_enabled: Optional[bool] = None,
    session_timeout: Optional[int] = None,
    max_login_attempts: Optional[int] = None,
    password_min_length: Optional[int] = None,
    current_user: User = Depends(get_current_active_admin),
):
    updates = {}
    if two_factor_enabled is not None:
        updates["2fa_enabled"] = str(two_factor_enabled).lower()
    if session_timeout is not None:
        updates["session_timeout_minutes"] = str(session_timeout)
    if max_login_attempts is not None:
        updates["max_login_attempts"] = str(max_login_attempts)
    if password_min_length is not None:
        updates["password_min_length"] = str(password_min_length)

    for key, value in updates.items():
        config = session.exec(select(SystemConfig).where(SystemConfig.key == key)).first()
        if config:
            config.value = value
            session.add(config)
        else:
            session.add(SystemConfig(key=key, value=value, description=f"Security: {key}"))

    session.commit()
    return {"message": "Security settings updated", "updated_keys": list(updates.keys())}
