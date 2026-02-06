from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

class WalletResponse(BaseModel):
    id: int
    user_id: int
    balance: float
    deposit_amount: float
    
    model_config = ConfigDict(from_attributes=True)

class TransactionResponse(BaseModel):
    id: int
    wallet_id: int
    amount: float
    type: str
    status: str
    description: Optional[str]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class RechargeRequest(BaseModel):
    amount: float
