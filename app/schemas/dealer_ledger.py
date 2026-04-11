from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

class LedgerEntry(BaseModel):
    id: str  # e.g., "RENTAL-123" or "COMM-456"
    transaction_id: str
    date: datetime
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    station_name: Optional[str] = None
    battery_id: Optional[str] = None
    type: str  # "Rental Income", "Commission", "Refund", "Penalty"
    duration: Optional[str] = None
    amount: float
    status: str  # "Completed", "Pending", "Failed", "Refunded"

class LedgerResponse(BaseModel):
    data: List[LedgerEntry]
    total: int
    total_amount: float
    
class LedgerDetailResponse(BaseModel):
    id: str
    transaction_id: str
    date: datetime
    customer_name: Optional[str]
    customer_phone: Optional[str]
    battery_id: Optional[str]
    station_name: Optional[str]
    terminal_number: Optional[str]
    rental_start_time: Optional[datetime]
    rental_end_time: Optional[datetime]
    duration: Optional[str]
    gross_amount: float
    platform_fee: float
    commission_rate: float
    commission_amount: float
    net_amount: float
    payment_method: Optional[str]
    payment_gateway_ref: Optional[str]
    settlement_status: str
    expected_settlement_date: Optional[datetime]
    type: str
    status: str
    events: List[dict]  # {"name": "Rental Started", "status": "completed", "date": ...}
