"""
Admin CRUD endpoints for the Promotional Campaign Engine
"""
from typing import Any, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.api import deps
from app.models.user import User
from app.schemas.campaign import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    CampaignListResponse,
    CampaignAnalyticsResponse,
)
from app.services.campaign_service import AdminCampaignService

router = APIRouter()


@router.post("/", response_model=CampaignResponse)
def create_campaign(
    *,
    db: Session = Depends(deps.get_db),
    payload: CampaignCreate,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Create a new campaign (saved as draft by default)."""
    campaign = AdminCampaignService.create_campaign(db, payload, current_user.id)
    return campaign


@router.get("/", response_model=List[CampaignListResponse])
def list_campaigns(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status: draft, scheduled, active, completed, paused"),
) -> Any:
    """List all campaigns with pagination and status filter."""
    return AdminCampaignService.list_campaigns(db, skip=skip, limit=limit, status_filter=status)


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign(
    *,
    db: Session = Depends(deps.get_db),
    campaign_id: UUID,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Get full details of a specific campaign."""
    return AdminCampaignService.get_campaign(db, campaign_id)


@router.put("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(
    *,
    db: Session = Depends(deps.get_db),
    campaign_id: UUID,
    payload: CampaignUpdate,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Update campaign content, schedule, or targeting criteria (draft/paused only)."""
    return AdminCampaignService.update_campaign(db, campaign_id, payload)


@router.delete("/{campaign_id}")
def delete_campaign(
    *,
    db: Session = Depends(deps.get_db),
    campaign_id: UUID,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Delete a draft or paused campaign."""
    return AdminCampaignService.delete_campaign(db, campaign_id)


@router.post("/{campaign_id}/activate", response_model=CampaignResponse)
def activate_campaign(
    *,
    db: Session = Depends(deps.get_db),
    campaign_id: UUID,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Activate a draft campaign — schedules it for sending."""
    return AdminCampaignService.activate_campaign(db, campaign_id)


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
def pause_campaign(
    *,
    db: Session = Depends(deps.get_db),
    campaign_id: UUID,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Pause an active or scheduled campaign."""
    return AdminCampaignService.pause_campaign(db, campaign_id)


@router.get("/{campaign_id}/analytics", response_model=CampaignAnalyticsResponse)
def get_campaign_analytics(
    *,
    db: Session = Depends(deps.get_db),
    campaign_id: UUID,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Get sent, opened, and converted counts for a campaign."""
    return AdminCampaignService.get_analytics(db, campaign_id)


@router.post("/{campaign_id}/test")
def test_campaign(
    *,
    db: Session = Depends(deps.get_db),
    campaign_id: UUID,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Send a test version of the campaign to the requesting admin's account."""
    return AdminCampaignService.send_test(db, campaign_id, current_user)
