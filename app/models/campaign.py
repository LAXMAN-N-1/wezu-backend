import uuid
"""
Promotional Campaign Engine Models
Campaign, CampaignTarget, CampaignSend
"""
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, JSON

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.promo_code import PromoCode
    from app.models.notification import Notification


class CampaignType(str, Enum):
    BIRTHDAY = "birthday"
    SEASONAL = "seasonal"
    HISTORY_BASED = "history_based"
    MANUAL = "manual"


class CampaignStatus(str, Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"


class CampaignTargetRuleType(str, Enum):
    RENTAL_HISTORY = "rental_history"
    BIRTHDAY = "birthday"
    LOCATION = "location"
    LAST_ACTIVITY = "last_activity"
    SPENDING_TIER = "spending_tier"


class Campaign(SQLModel, table=True):
    __tablename__ = "campaigns"
    __table_args__ = {"schema": "core"}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    name: str = Field(index=True)
    type: CampaignType = Field(index=True)

    # Targeting (denormalized JSON for quick reference; canonical rules in CampaignTarget)
    target_criteria: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))

    # Notification content
    message_title: str = Field(max_length=60)
    message_body: str = Field(max_length=200)

    # Optional linked promo code
    promo_code_id: Optional[int] = Field(default=None, foreign_key="promo_codes.id")

    # Scheduling
    scheduled_at: Optional[datetime] = None

    # Frequency capping (max promotional notifications per user per week)
    frequency_cap: int = Field(default=3, ge=1, le=3)

    # Status lifecycle: draft → scheduled → active → completed | paused
    status: CampaignStatus = Field(default=CampaignStatus.DRAFT, index=True)

    # Analytics counters (denormalized for fast reads)
    sent_count: int = Field(default=0)
    opened_count: int = Field(default=0)
    converted_count: int = Field(default=0)

    # Audit
    created_by: Optional[int] = Field(default=None, foreign_key="core.users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    targets: List["CampaignTarget"] = Relationship(back_populates="campaign")
    sends: List["CampaignSend"] = Relationship(back_populates="campaign")


class CampaignTarget(SQLModel, table=True):
    __tablename__ = "campaign_targets"
    __table_args__ = {"schema": "core"}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    campaign_id: uuid.UUID = Field(foreign_key="core.campaigns.id", index=True)

    rule_type: CampaignTargetRuleType
    rule_config: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    campaign: Campaign = Relationship(back_populates="targets")


class CampaignSend(SQLModel, table=True):
    __tablename__ = "campaign_sends"
    __table_args__ = {"schema": "core"}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    campaign_id: uuid.UUID = Field(foreign_key="core.campaigns.id", index=True)
    user_id: int = Field(foreign_key="core.users.id", index=True)

    sent_at: datetime = Field(default_factory=datetime.utcnow)
    opened_at: Optional[datetime] = None
    converted_at: Optional[datetime] = None

    notification_id: Optional[int] = Field(
        default=None, foreign_key="core.notifications.id"
    )

    # Relationships
    campaign: Campaign = Relationship(back_populates="sends")
