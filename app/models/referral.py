from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime, UTC

class Referral(SQLModel, table=True):
    __tablename__ = "referrals"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    referrer_id: int = Field(foreign_key="users.id")
    referred_user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    referral_code: str = Field(unique=True, index=True)
    
    status: str = Field(default="pending") # pending, completed, expired
    reward_amount: float = Field(default=0.0) # Reward for referrer
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: Optional[datetime] = None
    
    # Relationships
    referrer: "User" = Relationship(sa_relationship_kwargs={"foreign_keys": "[Referral.referrer_id]"})
    referred_user: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Referral.referred_user_id]"})
