from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime, UTC
from enum import Enum

if TYPE_CHECKING:
    from app.models.user import User

class MembershipTier(str, Enum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"

class UserMembership(SQLModel, table=True):
    __tablename__ = "user_memberships"
    # __table_args__ = {"schema": "public"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True, index=True)
    tier: MembershipTier = Field(default=MembershipTier.BRONZE)
    points_balance: float = Field(default=0.0)
    status: str = Field(default="active") # active, expired, suspended
    
    tier_expiry: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Relationships
    user: "User" = Relationship(back_populates="membership")
