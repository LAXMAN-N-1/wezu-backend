from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

class Wallet(SQLModel, table=True):
    __tablename__ = "wallets"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(unique=True, foreign_key="users.id")
    balance: float = Field(default=0.0)
    deposit_amount: float = Field(default=0.0) # Security deposit held
    currency: str = Field(default="INR")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationship
    user: "User" = Relationship(back_populates="wallet")
    transactions: List["Transaction"] = Relationship(back_populates="wallet")

class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"
    id: Optional[int] = Field(default=None, primary_key=True)
    wallet_id: int = Field(foreign_key="wallets.id")
    
    amount: float # Positive for credit, negative for debit
    balance_after: float # Wallet balance after transaction
    
    type: str = Field(index=True) # credit, debit
    category: str = Field(index=True) # deposit, swap_fee, penalty, refund, withdrawal
    
    status: str = Field(default="success") # success, pending, failed
    
    # References (Generic Foreign Key Concept)
    reference_type: Optional[str] = None # swap_session, payment_gateway, admin_adjustment
    reference_id: Optional[str] = None # ID of the related entity
    
    razorpay_payment_id: Optional[str] = None
    description: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    wallet: Wallet = Relationship(back_populates="transactions")
    # invoice: Optional["Invoice"] = Relationship(back_populates="transaction")
    # refund: Optional["Refund"] = Relationship(back_populates="transaction")

class WalletWithdrawalRequest(SQLModel, table=True):
    __tablename__ = "wallet_withdrawal_requests"
    id: Optional[int] = Field(default=None, primary_key=True)
    wallet_id: int = Field(foreign_key="wallets.id")
    amount: float
    status: str = Field(default="requested") # requested, approved, processed, rejected
    bank_details: str # JSON of bank info
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
