from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List
from datetime import datetime, timedelta

from app.core.database import get_db
from app.api import deps
from app.models.user import User
from app.models.rental import Rental
from app.models.battery_health import BatteryHealthAlert
from app.models.user_alert_config import UserAlertConfig
from app.schemas.battery_alert import AlertConfigSchema, BatteryAlertResponse

router = APIRouter()

@router.get("", response_model=List[BatteryAlertResponse])
def get_active_battery_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    active_rentals = db.exec(
        select(Rental).where(Rental.user_id == current_user.id, Rental.status == "active")
    ).all()
    battery_ids = [r.battery_id for r in active_rentals]
    if not battery_ids:
        return []

    alerts = db.exec(
        select(BatteryHealthAlert).where(
            BatteryHealthAlert.battery_id.in_(battery_ids),
            BatteryHealthAlert.is_resolved == False
        ).order_by(BatteryHealthAlert.created_at.desc())
    ).all()
    return alerts

@router.get("/config", response_model=AlertConfigSchema)
def get_alert_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    config = db.exec(select(UserAlertConfig).where(UserAlertConfig.user_id == current_user.id)).first()
    if not config:
        return AlertConfigSchema() # returns defaults
    return config

@router.put("/config", response_model=AlertConfigSchema)
def update_alert_config(
    config_in: AlertConfigSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    config = db.exec(select(UserAlertConfig).where(UserAlertConfig.user_id == current_user.id)).first()
    if not config:
        config = UserAlertConfig(user_id=current_user.id)
        db.add(config)
    
    config.low_charge_percent = config_in.low_charge_percent
    config.low_health_percent = config_in.low_health_percent
    config.high_temp_celsius = config_in.high_temp_celsius
    config.maintenance_reminder_days = config_in.maintenance_reminder_days
    config.alerts_enabled = config_in.alerts_enabled
    
    db.commit()
    db.refresh(config)
    return config

@router.post("/{alert_id}/dismiss")
def dismiss_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    alert = db.get(BatteryHealthAlert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    rental = db.exec(
        select(Rental).where(
            Rental.user_id == current_user.id,
            Rental.battery_id == alert.battery_id
        )
    ).first()
    
    if not rental:
        raise HTTPException(status_code=403, detail="Not authorized to dismiss this alert")
        
    if not alert.is_resolved:
        alert.is_resolved = True
        alert.resolved_by = current_user.id
        alert.resolved_at = datetime.utcnow()
        alert.resolution_reason = "Dismissed by user"
        db.add(alert)
        db.commit()
        
    return {"status": "success", "message": "Alert dismissed"}

@router.get("/history", response_model=List[BatteryAlertResponse])
def get_alert_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    past_90_days = datetime.utcnow() - timedelta(days=90)
    
    rentals = db.exec(
        select(Rental).where(Rental.user_id == current_user.id)
    ).all()
    
    battery_ids = [r.battery_id for r in rentals]
    if not battery_ids:
        return []

    alerts = db.exec(
        select(BatteryHealthAlert).where(
            BatteryHealthAlert.battery_id.in_(battery_ids),
            BatteryHealthAlert.created_at >= past_90_days
        ).order_by(BatteryHealthAlert.created_at.desc())
    ).all()
    
    return alerts
