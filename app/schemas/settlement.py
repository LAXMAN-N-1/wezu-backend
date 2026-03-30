from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class SettlementGenerateRequest(BaseModel):
    vendor_id: int
    start_date: datetime
    end_date: datetime

class SettlementUpdateRequest(BaseModel):
    status: str
    transaction_reference: Optional[str] = None

class SettlementResponse(BaseModel):
    id: int
    vendor_id: Optional[int] = None
    dealer_id: Optional[int] = None
    start_date: datetime
    end_date: datetime
    total_revenue: float
    platform_fee: float
    net_payable: float
    status: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
