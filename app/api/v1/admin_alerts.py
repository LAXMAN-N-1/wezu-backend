from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.api.deps import get_current_user
from app.services.alert_service import AlertService
from app.schemas.common import DataResponse
from app.api import deps
from typing import Any

router = APIRouter()

@router.patch("/{alert_id}/acknowledge", response_model=DataResponse[Any])
def acknowledge_alert(
    alert_id: int,
    session: Session = Depends(deps.get_db),
    current_user: Any = Depends(get_current_user)
):
    """Acknowledge an alert."""
    alert = AlertService.acknowledge_alert(session, alert_id, current_user.id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return DataResponse(message="Alert acknowledged successfully")