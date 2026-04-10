from fastapi import APIRouter, Depends, Query, Body, HTTPException
from sqlmodel import Session
from app.api import deps
from app.core.database import get_db
from app.models.user import User
from app.models.fraud_alert import FraudAlert, FraudAlertStatus
from app.services.admin_fraud_service import AdminFraudService
from typing import List, Optional

router = APIRouter()

@router.get("/alerts")
async def list_fraud_alerts(
    status: Optional[str] = Query(None, description="Filter by alert status (OPEN, UNDER_INVESTIGATION, etc.)"),
    alert_type: Optional[str] = Query(None, description="Filter by alert type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """Fetch paginated lists of fraud alerts for mission-control."""
    return AdminFraudService.list_alerts(db, status=status, alert_type=alert_type, skip=skip, limit=limit)

@router.post("/alerts/{alert_id}/investigate")
async def investigate_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """Mark a fraud alert as 'UNDER_INVESTIGATION'."""
    return AdminFraudService.update_alert_status(db, alert_id, FraudAlertStatus.UNDER_INVESTIGATION, current_user)

@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    status: str = Body(..., embed=True), # RESOLVED or FALSE_POSITIVE
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """Move alert to a terminal state (Resolved/False Positive)."""
    if status not in [FraudAlertStatus.RESOLVED, FraudAlertStatus.FALSE_POSITIVE]:
        raise HTTPException(status_code=400, detail="Terminal status must be RESOLVED or FALSE_POSITIVE")
    return AdminFraudService.update_alert_status(db, alert_id, status, current_user)

@router.post("/alerts/{alert_id}/note")
async def add_investigation_note(
    alert_id: str,
    note: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """Add admin forensics notes to a fraud alert."""
    return AdminFraudService.add_investigation_note(db, alert_id, note, current_user)

@router.get("/users/{user_id}/forensics")
async def get_user_forensic_timeline(
    user_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """Fetch detailed user activity timeline for forensics investigation."""
    return AdminFraudService.get_user_activity_timeline(db, user_id, limit=limit)
