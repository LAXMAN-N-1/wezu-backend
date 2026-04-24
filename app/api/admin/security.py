from __future__ import annotations
"""Security Settings Admin API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from sqlalchemy import case, or_
from typing import Optional
from datetime import datetime, timedelta, timezone; UTC = timezone.utc

from app.core.database import get_db
from app.api.deps import get_current_active_admin
from app.models.user import User
from app.models.audit_log import AuditLog, SecurityEvent
from app.models.system import SystemConfig

router = APIRouter()


def _failed_login_predicate():
    lowered_details = func.lower(func.coalesce(AuditLog.details, ""))
    return or_(
        AuditLog.action == "FAILED_LOGIN",
        lowered_details.like("%status: failure%"),
        lowered_details.like("%failed%"),
        lowered_details.like("%failure%"),
    )


def _classify_origin(ip_address: str) -> tuple[str, str, str]:
    ip = (ip_address or "").strip()
    if not ip or ip.lower() == "unknown":
        return "UNK", "Unknown", "🌐"
    if ip.startswith("127.") or ip in {"::1", "localhost"}:
        return "LOCAL", "Localhost", "🏠"

    try:
        first_octet = int(ip.split(".")[0])
    except (TypeError, ValueError, IndexError):
        return "UNK", "Unknown", "🌐"

    if first_octet < 50:
        return "NA", "North America", "🌎"
    if first_octet < 100:
        return "EU", "Europe", "🌍"
    if first_octet < 150:
        return "AS", "Asia", "🌏"
    if first_octet < 200:
        return "AF", "Africa", "🌍"
    return "OC", "Oceania", "🌏"


def _origin_layout_seed(seed_value: str) -> tuple[float, float]:
    seed = sum(ord(char) for char in seed_value)
    angle = round((seed % 360) * 3.141592653589793 / 180.0, 6)
    dist = round(0.25 + ((seed * 17) % 60) / 100.0, 3)
    return angle, dist


def _build_origin_metrics(session: Session, since: datetime, limit: int) -> list[dict]:
    failed_case = case((_failed_login_predicate(), 1), else_=0)
    rows = session.exec(
        select(
            AuditLog.ip_address,
            func.count(AuditLog.id),
            func.coalesce(func.sum(failed_case), 0),
        )
        .where(AuditLog.timestamp >= since)
        .group_by(AuditLog.ip_address)
        .order_by(func.count(AuditLog.id).desc())
        .limit(limit)
    ).all()

    items: list[dict] = []
    for index, row in enumerate(rows):
        ip_address = (row[0] or "unknown").strip() if row[0] else "unknown"
        attempts = int(row[1] or 0)
        failed = int(row[2] or 0)
        successful = max(attempts - failed, 0)
        success_rate = round((successful / attempts) * 100.0, 1) if attempts else 0.0

        code, country, flag = _classify_origin(ip_address)
        risk = (
            "critical"
            if failed >= 100 or success_rate < 40
            else "warning"
            if failed >= 25 or success_rate < 70
            else "low"
        )
        angle, dist = _origin_layout_seed(f"{ip_address}:{index}:{code}")

        items.append(
            {
                "code": code,
                "country": country,
                "flag": flag,
                "attempts": attempts,
                "failed": failed,
                "rate": success_rate,
                "risk": risk,
                "blocked": False,
                "angle": angle,
                "dist": dist,
                "ip_address": ip_address,
            }
        )

    return items

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
    query = select(AuditLog).where(AuditLog.timestamp >= since)
    if action:
        query = query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)

    total = session.exec(select(func.count(AuditLog.id)).where(AuditLog.timestamp >= since)).one()
    logs = session.exec(query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit)).all()

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


@router.get("/audit-logs/stats")
def audit_stats(
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
):
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)

    total = session.exec(select(func.count(AuditLog.id))).one()
    today_count = session.exec(
        select(func.count(AuditLog.id)).where(AuditLog.timestamp >= today)
    ).one()
    week_count = session.exec(
        select(func.count(AuditLog.id)).where(AuditLog.timestamp >= week_ago)
    ).one()

    # Action breakdown
    actions = {}
    logs = session.exec(select(AuditLog.action, func.count(AuditLog.id)).group_by(AuditLog.action)).all()
    for action, count in logs:
        actions[action] = count

    return {
        "total": total,
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
    if severity:
        query = query.where(SecurityEvent.severity == severity)
    if event_type:
        query = query.where(SecurityEvent.event_type == event_type)
    if is_resolved is not None:
        query = query.where(SecurityEvent.is_resolved == is_resolved)

    events = session.exec(query.order_by(SecurityEvent.timestamp.desc()).offset(skip).limit(limit)).all()
    total = session.exec(select(func.count(SecurityEvent.id))).one()

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


@router.get("/dashboard/origins")
def get_security_dashboard_origins(
    session: Session = Depends(get_db),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(12, ge=1, le=50),
    current_user: User = Depends(get_current_active_admin),
):
    since = datetime.now(UTC) - timedelta(days=days)
    return {"items": _build_origin_metrics(session, since, limit)}


@router.get("/dashboard")
def get_security_dashboard(
    session: Session = Depends(get_db),
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_current_active_admin),
):
    now = datetime.now(UTC)
    since_days = now - timedelta(days=days)
    since_24h = now - timedelta(hours=24)
    failed_predicate = _failed_login_predicate()

    total_events = session.exec(select(func.count(SecurityEvent.id))).one()
    unresolved_events = session.exec(
        select(func.count(SecurityEvent.id)).where(SecurityEvent.is_resolved.is_(False))
    ).one()
    critical_events = session.exec(
        select(func.count(SecurityEvent.id)).where(func.lower(SecurityEvent.severity) == "critical")
    ).one()
    total_audit_24h = session.exec(
        select(func.count(AuditLog.id)).where(AuditLog.timestamp >= since_24h)
    ).one()
    failed_logins_24h = session.exec(
        select(func.count(AuditLog.id))
        .where(AuditLog.timestamp >= since_24h)
        .where(failed_predicate)
    ).one()

    return {
        "generated_at": now.isoformat(),
        "period_days": days,
        "kpis": {
            "total_events": total_events,
            "critical_events": critical_events,
            "unresolved_events": unresolved_events,
            "failed_logins_24h": failed_logins_24h,
            "total_audit_24h": total_audit_24h,
        },
        "origins": _build_origin_metrics(session, since_days, 5),
    }


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
