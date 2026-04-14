"""
Dealer Campaigns API — Endpoints for dealers to manage their promotional campaigns,
validate codes at checkout, track analytics, and perform bulk operations.
"""

from typing import Any, List

from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlmodel import Session

from app.db.session import get_session
from app.api import deps
from app.api.deps import get_current_user
from app.models.user import User
from app.services.campaign_service import CampaignService
from pydantic import BaseModel

router = APIRouter()

def _get_dealer_id(db: Session, user_id: int) -> int:
    """Resolve dealer_id from current user, or raise 403."""
    dealer = deps.get_dealer_profile_or_403(db, user_id, detail="Not a dealer")
    return dealer.id


# ─── Pydantic Schemas ───

class CampaignBase(BaseModel):
    name: str
    description: str | None = None
    promo_code: str
    discount_type: str
    discount_value: float
    min_purchase_amount: float | None = None
    max_discount_amount: float | None = None
    budget_limit: float | None = None
    daily_cap: int | None = None
    usage_limit_total: int | None = None
    usage_limit_per_user: int = 1
    applicable_to: str = "ALL"
    applicable_station_ids: list[int] | None = None
    start_date: str
    end_date: str
    is_active: bool = True

class CampaignUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    promo_code: str | None = None
    discount_value: float | None = None
    budget_limit: float | None = None
    daily_cap: int | None = None
    is_active: bool | None = None

class ValidateRequest(BaseModel):
    code: str
    order_amount: float
    station_id: int | None = None

class BulkToggleRequest(BaseModel):
    campaign_ids: list[int]
    is_active: bool

class CloneRequest(BaseModel):
    new_promo_code: str


# ─── CRUD Endpoints ───

@router.post("")
def create_campaign(
    data: CampaignBase,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    dealer_id = _get_dealer_id(db, current_user.id)
    from datetime import datetime
    
    # Parse dates
    payload = data.dict()
    payload["start_date"] = datetime.fromisoformat(payload["start_date"])
    payload["end_date"] = datetime.fromisoformat(payload["end_date"])
    
    return CampaignService.create_campaign(db, dealer_id, payload)


@router.get("")
def list_campaigns(
    active_only: bool = False,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    dealer_id = _get_dealer_id(db, current_user.id)
    return CampaignService.list_campaigns(db, dealer_id, active_only)


@router.get("/{campaign_id}")
def get_campaign(
    campaign_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    dealer_id = _get_dealer_id(db, current_user.id)
    return CampaignService.get_campaign(db, campaign_id, dealer_id)


@router.put("/{campaign_id}")
def update_campaign(
    campaign_id: int,
    data: CampaignUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    dealer_id = _get_dealer_id(db, current_user.id)
    payload = {k: v for k, v in data.dict().items() if v is not None}
    return CampaignService.update_campaign(db, campaign_id, dealer_id, payload)


@router.delete("/{campaign_id}")
def deactivate_campaign(
    campaign_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    dealer_id = _get_dealer_id(db, current_user.id)
    return CampaignService.toggle_active(db, campaign_id, dealer_id, False)

# ─── Validation & Analytics ───

@router.post("/validate")
def validate_promo(
    req: ValidateRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Validate a promo code for checkout."""
    # Note: Using current_user.id to track usage limit
    return CampaignService.validate_promo(
        db, req.code, req.station_id, req.order_amount, current_user.id
    )

@router.get("/{campaign_id}/analytics")
def get_campaign_analytics(
    campaign_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get campaign performance: usages, discount given, ROI."""
    dealer_id = _get_dealer_id(db, current_user.id)
    return CampaignService.get_analytics(db, campaign_id, dealer_id)

# ─── Bulk Operations ───

@router.post("/bulk-create")
async def bulk_create_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Upload a CSV to create multiple campaigns."""
    dealer_id = _get_dealer_id(db, current_user.id)
    content = await file.read()
    try:
        csv_string = content.decode('utf-8-sig') # Handles BOM and strict UTF-8
    except UnicodeDecodeError:
        csv_string = content.decode('latin1') # Fallback for Excel Windows encodings
    return CampaignService.bulk_create_from_csv(db, dealer_id, csv_string)

@router.post("/bulk-toggle")
def bulk_toggle(
    req: BulkToggleRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Activate/deactivate multiple campaigns at once."""
    dealer_id = _get_dealer_id(db, current_user.id)
    count = CampaignService.bulk_toggle(db, dealer_id, req.campaign_ids, req.is_active)
    return {"updated": count}

@router.post("/{campaign_id}/clone")
def clone_campaign(
    campaign_id: int,
    req: CloneRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Clone an existing campaign with a new promo code."""
    dealer_id = _get_dealer_id(db, current_user.id)
    return CampaignService.clone_campaign(db, campaign_id, dealer_id, req.new_promo_code)
