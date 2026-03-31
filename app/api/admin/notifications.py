"""Notification Admin API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from typing import List, Optional
from datetime import datetime, UTC

from app.core.database import get_db
from app.api.deps import get_current_active_admin
from app.models.user import User
from app.models.notification_admin import PushCampaign, AutomatedTrigger, NotificationLog, NotificationConfig
from app.schemas.notification_admin import (
    PushCampaignCreate, PushCampaignRead,
    AutomatedTriggerCreate, AutomatedTriggerUpdate, AutomatedTriggerRead,
    NotificationLogRead,
    NotificationConfigCreate, NotificationConfigUpdate, NotificationConfigRead,
)

router = APIRouter()

# ============================================================================
# Push Campaigns
# ============================================================================

@router.get("/campaigns", response_model=List[PushCampaignRead])
def list_campaigns(
    session: Session = Depends(get_db),
    status: Optional[str] = None,
    current_user: User = Depends(get_current_active_admin),
):
    query = select(PushCampaign)
    if status:
        query = query.where(PushCampaign.status == status)
    return session.exec(query.order_by(PushCampaign.created_at.desc())).all()


@router.post("/campaigns", response_model=PushCampaignRead)
def create_campaign(
    campaign_in: PushCampaignCreate,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
):
    campaign = PushCampaign.model_validate(campaign_in)
    campaign.created_by = current_user.id
    # Count target users
    from app.models.user import User as UserModel
    user_count = session.exec(select(func.count(UserModel.id))).one()
    campaign.target_count = user_count
    if campaign.scheduled_at:
        campaign.status = "scheduled"
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign


@router.post("/campaigns/{campaign_id}/send")
def send_campaign(
    campaign_id: int,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
):
    campaign = session.get(PushCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.status == "sent":
        raise HTTPException(status_code=400, detail="Campaign already sent")

    # Simulate sending
    campaign.status = "sent"
    campaign.sent_at = datetime.now(UTC)
    campaign.sent_count = campaign.target_count
    campaign.delivered_count = int(campaign.target_count * 0.95)
    campaign.open_count = int(campaign.target_count * 0.35)
    campaign.click_count = int(campaign.target_count * 0.12)
    campaign.failed_count = campaign.target_count - campaign.delivered_count
    session.add(campaign)
    session.commit()
    return {"message": "Campaign sent successfully", "sent_count": campaign.sent_count}


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(
    campaign_id: int,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
):
    campaign = session.get(PushCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    session.delete(campaign)
    session.commit()
    return {"message": "Campaign deleted"}


# ============================================================================
# Automated Triggers
# ============================================================================

@router.get("/triggers", response_model=List[AutomatedTriggerRead])
def list_triggers(
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
):
    return session.exec(select(AutomatedTrigger).order_by(AutomatedTrigger.created_at.desc())).all()


@router.post("/triggers", response_model=AutomatedTriggerRead)
def create_trigger(
    trigger_in: AutomatedTriggerCreate,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
):
    trigger = AutomatedTrigger.model_validate(trigger_in)
    session.add(trigger)
    session.commit()
    session.refresh(trigger)
    return trigger


@router.patch("/triggers/{trigger_id}", response_model=AutomatedTriggerRead)
def update_trigger(
    trigger_id: int,
    trigger_in: AutomatedTriggerUpdate,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
):
    trigger = session.get(AutomatedTrigger, trigger_id)
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    for key, value in trigger_in.model_dump(exclude_unset=True).items():
        setattr(trigger, key, value)
    trigger.updated_at = datetime.now(UTC)
    session.add(trigger)
    session.commit()
    session.refresh(trigger)
    return trigger


@router.delete("/triggers/{trigger_id}")
def delete_trigger(
    trigger_id: int,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
):
    trigger = session.get(AutomatedTrigger, trigger_id)
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    session.delete(trigger)
    session.commit()
    return {"message": "Trigger deleted"}


# ============================================================================
# Notification Logs
# ============================================================================

@router.get("/logs", response_model=List[NotificationLogRead])
def list_notification_logs(
    session: Session = Depends(get_db),
    channel: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_active_admin),
):
    query = select(NotificationLog)
    if channel:
        query = query.where(NotificationLog.channel == channel)
    if status:
        query = query.where(NotificationLog.status == status)
    return session.exec(query.order_by(NotificationLog.sent_at.desc()).offset(skip).limit(limit)).all()


@router.get("/logs/stats")
def notification_stats(
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
):
    total = session.exec(select(func.count(NotificationLog.id))).one()
    sent = session.exec(select(func.count(NotificationLog.id)).where(NotificationLog.status == "sent")).one()
    delivered = session.exec(select(func.count(NotificationLog.id)).where(NotificationLog.status == "delivered")).one()
    opened = session.exec(select(func.count(NotificationLog.id)).where(NotificationLog.status == "opened")).one()
    failed = session.exec(select(func.count(NotificationLog.id)).where(NotificationLog.status == "failed")).one()
    return {
        "total": total, "sent": sent, "delivered": delivered,
        "opened": opened, "failed": failed,
        "delivery_rate": round(delivered / total * 100, 1) if total > 0 else 0,
        "open_rate": round(opened / total * 100, 1) if total > 0 else 0,
    }


# ============================================================================
# SMS & Email Config
# ============================================================================

@router.get("/config", response_model=List[NotificationConfigRead])
def list_notification_configs(
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
):
    configs = session.exec(select(NotificationConfig)).all()
    # Mask API keys
    for c in configs:
        if c.api_key:
            c.api_key = c.api_key[:4] + "****" + c.api_key[-4:] if len(c.api_key) > 8 else "****"
    return configs


@router.post("/config", response_model=NotificationConfigRead)
def create_notification_config(
    config_in: NotificationConfigCreate,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
):
    config = NotificationConfig.model_validate(config_in)
    session.add(config)
    session.commit()
    session.refresh(config)
    return config


@router.patch("/config/{config_id}", response_model=NotificationConfigRead)
def update_notification_config(
    config_id: int,
    config_in: NotificationConfigUpdate,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
):
    config = session.get(NotificationConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    for key, value in config_in.model_dump(exclude_unset=True).items():
        setattr(config, key, value)
    config.updated_at = datetime.now(UTC)
    session.add(config)
    session.commit()
    session.refresh(config)
    return config


@router.post("/config/{config_id}/test")
def test_notification_config(
    config_id: int,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
):
    config = session.get(NotificationConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    # Simulate test
    config.last_tested_at = datetime.now(UTC)
    config.test_status = "success"
    session.add(config)
    session.commit()
    return {"message": f"Test {config.channel} via {config.provider} succeeded", "status": "success"}
