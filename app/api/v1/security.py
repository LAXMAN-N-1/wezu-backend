from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from typing import List, Optional
from app.api import deps
from app.models.user import User
from app.services.security_service import SecurityService
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class SecurityEventSummary(BaseModel):
    severity_counts: dict
    unresolved_count: int

class SecurityEventResponse(BaseModel):
    id: int
    event_type: str
    severity: str
    details: Optional[str]
    source_ip: Optional[str]
    user_id: Optional[int]
    timestamp: datetime
    is_resolved: bool

    class Config:
        from_attributes = True

@router.get("/events", response_model=List[SecurityEventResponse])
def get_security_events(
    skip: int = 0,
    limit: int = 100,
    unresolved_only: bool = False,
    severity: Optional[str] = None,
    db: Session = Depends(deps.get_db),
    current_admin: User = Depends(deps.get_current_active_superuser)
):
    """
    Get all security events. Restricted to superusers.
    """
    return SecurityService.get_events(
        db, skip=skip, limit=limit, unresolved_only=unresolved_only, severity=severity
    )

@router.post("/events/{event_id}/resolve", response_model=SecurityEventResponse)
def resolve_security_event(
    event_id: int,
    db: Session = Depends(deps.get_db),
    current_admin: User = Depends(deps.get_current_active_superuser)
):
    """
    Mark a security event as resolved.
    """
    event = SecurityService.resolve_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Security event not found")
    return event

@router.get("/stats", response_model=SecurityEventSummary)
def get_security_stats(
    db: Session = Depends(deps.get_db),
    current_admin: User = Depends(deps.get_current_active_superuser)
):
    """
    Get security event statistics.
    """
    return SecurityService.get_event_stats(db)

@router.post("/log-mock", response_model=SecurityEventResponse)
def log_mock_event(
    event_type: str = "manual_test",
    severity: str = "low",
    details: str = "Manual security event log",
    db: Session = Depends(deps.get_db),
    current_admin: User = Depends(deps.get_current_active_superuser)
):
    """
    Log a mock security event for testing.
    """
    return SecurityService.log_event(
        db, event_type=event_type, severity=severity, details=details, user_id=current_admin.id
    )
