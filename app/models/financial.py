from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.rental import Rental
    from app.models.invoice import Invoice

class TransactionType(str, Enum):
    RENTAL_PAYMENT = "rental_payment"
    SECURITY_DEPOSIT = "security_deposit"
    WALLET_TOPUP = "wallet_topup"
    REFUND = "refund"
    FINE = "fine"
    SUBSCRIPTION = "subscription"
    WITHDRAWAL = "withdrawal"

class TransactionStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"

class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"
    __table_args__ = {"schema": "finance"}
    id: Optional[int] = Field(default=None, primary_key=True)
    
    user_id: int = Field(foreign_key="core.users.id", index=True)
    rental_id: Optional[int] = Field(default=None, foreign_key="rentals.rentals.id")
    wallet_id: Optional[int] = Field(default=None, foreign_key="finance.wallets.id")
    
    amount: float
    currency: str = Field(default="INR")
    
    transaction_type: TransactionType = Field(index=True)
    status: TransactionStatus = Field(default=TransactionStatus.PENDING, index=True)
    
    payment_method: str = Field(default="upi") # upi, card, netbanking, wallet
    payment_gateway_ref: Optional[str] = Field(default=None, index=True) # Razorpay/Stripe ID
    
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    user: "User" = Relationship(back_populates="transactions")
    rental: Optional["Rental"] = Relationship(back_populates="transactions")
    wallet: Optional["Wallet"] = Relationship(back_populates="transactions")
    invoice: Optional["Invoice"] = Relationship(back_populates="transaction")

class Wallet(SQLModel, table=True):
    __tablename__ = "wallets"
    __table_args__ = {"schema": "finance"}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="core.users.id", unique=True, index=True)
    
    balance: float = Field(default=0.0)
    currency: str = Field(default="INR")
    
    is_frozen: bool = Field(default=False)
    
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    user: "User" = Relationship(back_populates="wallet")
    transactions: List["Transaction"] = Relationship(back_populates="wallet")
    withdrawal_requests: List["WalletWithdrawalRequest"] = Relationship(back_populates="wallet")

class WalletWithdrawalRequest(SQLModel, table=True):
    __tablename__ = "wallet_withdrawal_requests"
    __table_args__ = {"schema": "finance"}
    id: Optional[int] = Field(default=None, primary_key=True)
    wallet_id: int = Field(foreign_key="finance.wallets.id")
    amount: float
    status: str = Field(default="requested") # requested, approved, rejected, processed
    bank_details: str 
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    
    wallet: "Wallet" = Relationship(back_populates="withdrawal_requests")
