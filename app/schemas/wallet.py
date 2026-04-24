from __future__ import annotations
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
    
    # P1-C canonical fields
    type: Optional[str] = None
    category: Optional[str] = None
    balance_after: Optional[float] = None
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    
    description: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class RechargeRequest(BaseModel):
    amount: float
    payment_method: str = "upi"
