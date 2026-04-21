from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid
from app.models.warranty_claim import ClaimType, ClaimStatus

class WarrantyClaimCreate(BaseModel):
    order_id: int
    product_id: uuid.UUID
    claim_type: ClaimType
    description: str = Field(..., min_length=50, description="Detailed description of the issue (min 50 chars).")
    photos: List[str] = Field(default_factory=list, description="List of photo URLs")

class WarrantyClaimResponse(WarrantyClaimCreate):
    id: uuid.UUID
    user_id: int
    status: ClaimStatus
    admin_notes: Optional[str] = None
    resolution: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class WarrantyClaimUpdate(BaseModel):
    status: ClaimStatus
    admin_notes: Optional[str] = None
    resolution: Optional[str] = None

class WarrantyCheckResponse(BaseModel):
    order_id: int
    is_eligible: bool
    reason: str
    days_remaining: Optional[int] = None
