from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List
from app.api import deps
from app.models.user import User
from app.schemas.support import NotificationResponse
from app.services.support_service import NotificationService

router = APIRouter()

@router.get("/", response_model=List[NotificationResponse])
async def read_notifications(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    return NotificationService.get_user_notifications(db, current_user.id)

@router.put("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    NotificationService.mark_read(db, notification_id, current_user.id)
    return {"status": "ok"}
