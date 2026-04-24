from __future__ import annotations
"""
Financial schemas: Transaction, Wallet, WalletWithdrawalRequest
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


# ── Transaction ──────────────────────────────────────────

class TransactionBase(BaseModel):
    amount: float
    currency: str = "INR"
    transaction_type: str
    payment_method: str = "upi"
    description: Optional[str] = None

class TransactionCreate(TransactionBase):
    user_id: int
    rental_id: Optional[int] = None
    wallet_id: Optional[int] = None
    tax_amount: float = 0.0
    subtotal: float = 0.0
    payment_gateway_ref: Optional[str] = None

class TransactionUpdate(BaseModel):
    status: Optional[str] = None
    payment_gateway_ref: Optional[str] = None
    description: Optional[str] = None

class TransactionResponse(TransactionBase):
    id: int
    user_id: int
    rental_id: Optional[int] = None
    wallet_id: Optional[int] = None
    tax_amount: float = 0.0
    subtotal: float = 0.0
    status: str
    payment_gateway_ref: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TransactionListResponse(BaseModel):
    transactions: List[TransactionResponse]
    total_count: int
    page: int = 1
    limit: int = 20


# ── Wallet ───────────────────────────────────────────────

class WalletResponse(BaseModel):
    id: int
    user_id: int
    balance: float
    cashback_balance: float = 0.0
    currency: str = "INR"
    is_frozen: bool = False
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class WalletTopupRequest(BaseModel):
    amount: float
    payment_method: str = "upi"
    payment_gateway_ref: Optional[str] = None


# ── Withdrawal ───────────────────────────────────────────

class WithdrawalRequestCreate(BaseModel):
    amount: float
    bank_details: str

class WithdrawalRequestResponse(BaseModel):
    id: int
    wallet_id: int
    amount: float
    status: str
    bank_details: str
    created_at: datetime
    processed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
