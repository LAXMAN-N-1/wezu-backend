"""
Pydantic schemas for the Promotional Campaign Engine
"""
from pydantic import BaseModel, ConfigDict, Field as PydField
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


# ── Enums (mirror model enums for schema validation) ──

class CampaignTypeEnum(str, Enum):
    birthday = "birthday"
    seasonal = "seasonal"
    history_based = "history_based"
    manual = "manual"


class CampaignStatusEnum(str, Enum):
    draft = "draft"
    scheduled = "scheduled"
    active = "active"
    completed = "completed"
    paused = "paused"


class CampaignTargetRuleTypeEnum(str, Enum):
    rental_history = "rental_history"
    birthday = "birthday"
    location = "location"
    last_activity = "last_activity"
    spending_tier = "spending_tier"


# ── Sub-models ──

class CampaignTargetRuleCreate(BaseModel):
    """A single targeting rule attached to a campaign."""
    rule_type: CampaignTargetRuleTypeEnum
    rule_config: Dict[str, Any] = {}
    # Examples:
    #   rental_history  → {"min_rentals": 5}
    #   birthday        → {}  (auto-resolved by DOB match)
    #   location        → {"city": "Mumbai"}
    #   last_activity   → {"inactive_days": 30}
    #   spending_tier   → {"min_spend": 1000, "max_spend": 5000}


class CampaignTargetRuleResponse(CampaignTargetRuleCreate):
    id: UUID
    campaign_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Campaign Create / Update ──

class CampaignCreate(BaseModel):
    name: str = PydField(..., min_length=1, max_length=200)
    type: CampaignTypeEnum
    message_title: str = PydField(..., min_length=1, max_length=60)
    message_body: str = PydField(..., min_length=1, max_length=200)
    promo_code_id: Optional[int] = None
    scheduled_at: Optional[datetime] = None
    frequency_cap: int = PydField(default=3, ge=1, le=3)
    target_criteria: Dict[str, Any] = {}
    targets: List[CampaignTargetRuleCreate] = []


class CampaignUpdate(BaseModel):
    name: Optional[str] = PydField(default=None, max_length=200)
    message_title: Optional[str] = PydField(default=None, max_length=60)
    message_body: Optional[str] = PydField(default=None, max_length=200)
    promo_code_id: Optional[int] = None
    scheduled_at: Optional[datetime] = None
    frequency_cap: Optional[int] = PydField(default=None, ge=1, le=3)
    target_criteria: Optional[Dict[str, Any]] = None
    targets: Optional[List[CampaignTargetRuleCreate]] = None


# ── Campaign Response ──

class CampaignResponse(BaseModel):
    id: UUID
    name: str
    type: CampaignTypeEnum
    target_criteria: Dict[str, Any]
    message_title: str
    message_body: str
    promo_code_id: Optional[int] = None
    scheduled_at: Optional[datetime] = None
    frequency_cap: int
    status: CampaignStatusEnum
    sent_count: int
    opened_count: int
    converted_count: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    targets: List[CampaignTargetRuleResponse] = []

    model_config = ConfigDict(from_attributes=True)


class CampaignListResponse(BaseModel):
    id: UUID
    name: str
    type: CampaignTypeEnum
    status: CampaignStatusEnum
    scheduled_at: Optional[datetime] = None
    sent_count: int
    opened_count: int
    converted_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CampaignAnalyticsResponse(BaseModel):
    campaign_id: UUID
    campaign_name: str
    sent_count: int
    opened_count: int
    converted_count: int
    open_rate: float = 0.0       # opened / sent * 100
    conversion_rate: float = 0.0  # converted / sent * 100
