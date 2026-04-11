from typing import Optional, List
from datetime import datetime
import uuid
from sqlmodel import SQLModel, Field, Column, JSON
from enum import Enum

class ClaimType(str, Enum):
    DEFECT = "defect"
    DAMAGE = "damage"
    PERFORMANCE = "performance"

class ClaimStatus(str, Enum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    RESOLVED = "resolved"

class WarrantyClaim(SQLModel, table=True):
    __tablename__ = "warranty_claims"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    order_id: int = Field(foreign_key="orders.id", index=True)
    product_id: uuid.UUID = Field(foreign_key="batteries.id", index=True)

    claim_type: ClaimType = Field(index=True)
    description: str
    
    photos: List[str] = Field(default=[], sa_column=Column(JSON))
    
    status: ClaimStatus = Field(default=ClaimStatus.SUBMITTED, index=True)
    admin_notes: Optional[str] = None
    resolution: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
