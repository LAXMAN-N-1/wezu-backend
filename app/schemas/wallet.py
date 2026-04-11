from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

class WalletResponse(BaseModel):
    id: int
    user_id: int
    balance: float
    currency: str = "INR"
    is_frozen: bool = False
    
    model_config = ConfigDict(from_attributes=True)

class TransactionResponse(BaseModel):
    id: int
    wallet_id: Optional[int] = None
    user_id: int
    rental_id: Optional[int] = None
    
    amount: float
    currency: str
    
    transaction_type: str
    status: str
    
    payment_method: Optional[str] = None
    payment_gateway_ref: Optional[str] = None
    
    description: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class RechargeRequest(BaseModel):
    amount: float
    payment_method: str = "upi"

class DealerTransactionResponse(TransactionResponse):
    customer_name: str
    customer_phone: Optional[str] = None
    station_name: str
    terminal_id: Optional[int] = None
    battery_serial: Optional[str] = None
    duration_minutes: Optional[int] = None
    net_amount: float
    commission_amount: float
    settlement_status: str

class TransactionLifecycleEvent(BaseModel):
    event_type: str
    timestamp: datetime
    is_completed: bool

class TransactionLifecycleResponse(BaseModel):
    transaction_id: int
    events: List[TransactionLifecycleEvent]
