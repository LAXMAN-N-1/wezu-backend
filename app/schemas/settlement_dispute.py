"""
Settlement dispute schemas
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


class SettlementDisputeCreate(BaseModel):
    settlement_id: int
    reason: str
    description: Optional[str] = None
    evidence_urls: Optional[List[str]] = None

class SettlementDisputeResponse(BaseModel):
    id: int
    settlement_id: int
    raised_by: Optional[int] = None
    reason: str
    description: Optional[str] = None
    status: str = "open"
    resolution: Optional[str] = None
    resolved_by: Optional[int] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
