"""
Dealer KYC schemas
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict
from datetime import datetime


class DealerKYCApplicationCreate(BaseModel):
    dealer_id: int
    document_type: str
    document_number: Optional[str] = None
    file_url: str
    notes: Optional[str] = None

class DealerKYCApplicationResponse(BaseModel):
    id: int
    dealer_id: int
    document_type: str
    document_number: Optional[str] = None
    file_url: Optional[str] = None
    status: str = "pending"
    rejection_reason: Optional[str] = None
    verified_by: Optional[int] = None
    verified_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class KYCStateTransitionResponse(BaseModel):
    id: int
    application_id: int
    from_state: str
    to_state: str
    reason: Optional[str] = None
    transitioned_by: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DealerKYCListResponse(BaseModel):
    applications: List[DealerKYCApplicationResponse]
    total_count: int
