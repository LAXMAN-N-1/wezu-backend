from __future__ import annotations
"""
Enhanced Notification Endpoints
Additional notification operations including read/unread management and device tokens
"""
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlmodel import Session, select

from app.api import deps
from app.db.session import get_session
from app.models.device import Device
from app.models.notification import Notification
from app.models.user import User
from app.repositories.notification_repository import notification_repository

router = APIRouter()


class DeviceTokenRequest(BaseModel):
    token: str = Field(min_length=20, max_length=4096)
    platform: Literal["ios", "android", "web"]
    device_id: Optional[str] = Field(default=None, min_length=1, max_length=255)
    app_scope: Optional[str] = Field(default=None, min_length=1, max_length=64)

    @field_validator("token")
    @classmethod
    def _normalize_token(cls, value: str) -> str:
        token = value.strip()
        if not token:
            raise ValueError("token cannot be blank")
        return token

    @field_validator("device_id")
    @classmethod
    def _normalize_device_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        device_id = value.strip()
        return device_id or None

    @field_validator("app_scope")
    @classmethod
    def _normalize_app_scope(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        app_scope = value.strip().lower().replace("-", "_").replace(" ", "_")
        return app_scope or None


class DeviceTokenUnregisterRequest(BaseModel):
    token: Optional[str] = Field(default=None, min_length=20, max_length=4096)
    device_id: Optional[str] = Field(default=None, min_length=1, max_length=255)
    app_scope: Optional[str] = Field(default=None, min_length=1, max_length=64)

    @field_validator("token")
    @classmethod
    def _normalize_token(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        token = value.strip()
        return token or None

    @field_validator("device_id")
    @classmethod
    def _normalize_device_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        device_id = value.strip()
        return device_id or None

    @field_validator("app_scope")
    @classmethod
    def _normalize_app_scope(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        app_scope = value.strip().lower().replace("-", "_").replace(" ", "_")
        return app_scope or None

    @model_validator(mode="after")
    def _ensure_selector(self) -> "DeviceTokenUnregisterRequest":
        if not self.token and not self.device_id:
            raise ValueError("Provide token or device_id")
        return self


@router.patch("/{notification_id:int}/read")
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """Mark a single notification as read"""
    notification = notification_repository.get(db, notification_id)

    if not notification or notification.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification_repository.mark_as_read(db, notification_id)

    return {"message": "Notification marked as read"}


@router.patch("/read-all")
def mark_all_notifications_read(
    app_scope: Optional[str] = Query(default=None, description="Limit read-all to a specific app scope"),
    include_global: bool = Query(default=True, description="Include app-agnostic notifications"),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """Mark all notifications as read"""
    count = notification_repository.mark_all_as_read(
        db,
        current_user.id,
        app_scope=app_scope,
        include_global=include_global,
    )

    return {"message": f"{count} notifications marked as read", "count": count}


@router.post("/device-token")
def register_device_token(
    request: DeviceTokenRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """Register device token for push notifications"""
    now = datetime.utcnow()
    resolved_device_id = request.device_id or f"token:{request.token[:48]}"

    # One token should not stay active across multiple users.
    same_token_any_user = db.exec(
        select(Device).where(Device.fcm_token == request.token)
    ).all()
    for device in same_token_any_user:
        if device.user_id != current_user.id and device.is_active:
            device.is_active = False
            device.last_active_at = now
            db.add(device)

    existing_for_user = db.exec(
        select(Device).where(
            Device.user_id == current_user.id,
            Device.device_id == resolved_device_id,
        )
    ).first()

    if existing_for_user:
        existing_for_user.fcm_token = request.token
        existing_for_user.device_type = request.platform
        existing_for_user.app_scope = request.app_scope
        existing_for_user.is_active = True
        existing_for_user.last_active_at = now
        db.add(existing_for_user)
    else:
        existing_same_token = db.exec(
            select(Device).where(
                Device.user_id == current_user.id,
                Device.fcm_token == request.token,
            )
        ).first()
        if existing_same_token:
            existing_same_token.device_id = resolved_device_id
            existing_same_token.device_type = request.platform
            existing_same_token.app_scope = request.app_scope
            existing_same_token.is_active = True
            existing_same_token.last_active_at = now
            db.add(existing_same_token)
        else:
            db.add(
                Device(
                    user_id=current_user.id,
                    fcm_token=request.token,
                    app_scope=request.app_scope,
                    device_type=request.platform,
                    device_id=resolved_device_id,
                    is_active=True,
                    last_active_at=now,
                )
            )

    db.commit()

    return {
        "message": "Device token registered successfully",
        "platform": request.platform,
        "device_id": resolved_device_id,
        "app_scope": request.app_scope,
    }


@router.delete("/device-token")
def unregister_device_token(
    request: DeviceTokenUnregisterRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """Unregister device token"""
    statement = select(Device).where(Device.user_id == current_user.id)
    if request.token:
        statement = statement.where(Device.fcm_token == request.token)
    if request.device_id:
        statement = statement.where(Device.device_id == request.device_id)
    if request.app_scope:
        statement = statement.where(Device.app_scope == request.app_scope)
    matched_devices = db.exec(statement).all()

    now = datetime.utcnow()
    for device in matched_devices:
        device.is_active = False
        device.last_active_at = now
        db.add(device)
    db.commit()

    return {
        "message": "Device token unregistered successfully",
        "count": len(matched_devices),
    }


@router.delete("/{notification_id:int}")
def delete_notification(
    notification_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """Delete a single notification"""
    notification = notification_repository.get(db, notification_id)

    if not notification or notification.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Notification not found")

    db.delete(notification)
    db.commit()

    return {"message": "Notification deleted"}


@router.delete("")
def clear_all_notifications(
    app_scope: Optional[str] = Query(default=None, description="Limit clear-all to a specific app scope"),
    include_global: bool = Query(default=True, description="Include app-agnostic notifications"),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """Clear all notifications"""
    query = select(Notification).where(Notification.user_id == current_user.id)
    if app_scope:
        normalized = app_scope.strip().lower().replace("-", "_").replace(" ", "_")
        if include_global:
            query = query.where(
                (Notification.app_scope == normalized) | (Notification.app_scope.is_(None))
            )
        else:
            query = query.where(Notification.app_scope == normalized)
    notifications = db.exec(query).all()

    for notification in notifications:
        db.delete(notification)

    db.commit()

    return {"message": f"{len(notifications)} notifications cleared", "count": len(notifications)}
