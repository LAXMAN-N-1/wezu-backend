from typing import Optional
from datetime import datetime
from pydantic import BaseModel

class SettlementGenerateRequest(BaseModel):
    vendor_id: int
    start_date: datetime
    end_date: datetime

class SettlementUpdateRequest(BaseModel):
    status: str
    transaction_reference: Optional[str] = None

class SettlementResponse(BaseModel):
    id: int
    vendor_id: int
    start_date: datetime
    end_date: datetime
    total_revenue: float
    platform_fee: float
    payable_amount: float
    status: str
    created_at: datetime
    
    class Config:
        orm_mode = True
