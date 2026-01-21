from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime

class Commission(SQLModel, table=True):
    __tablename__ = "commissions"
    id: Optional[int] = Field(default=None, primary_key=True)
    dealer_id: int = Field(foreign_key="dealer_profiles.id")
    transaction_id: int = Field(foreign_key="transactions.id")
    settlement_id: Optional[int] = Field(default=None, foreign_key="settlements.id")
    amount: float
    percentage: float
    status: str = Field(default="pending") # pending, paid
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    paid_at: Optional[datetime] = None
    
    # Relationships
    # Relationships
    transaction: "Transaction" = Relationship()
    dealer: Optional["DealerProfile"] = Relationship(back_populates="commissions")
    settlement: Optional["Settlement"] = Relationship(back_populates="commissions")

class Settlement(SQLModel, table=True):
    __tablename__ = "settlements"
    id: Optional[int] = Field(default=None, primary_key=True)
    dealer_id: int = Field(foreign_key="dealer_profiles.id")
    
    start_date: datetime
    end_date: datetime
    
    total_commission: float
    total_deductions: float = Field(default=0.0)
    net_amount: float
    
    status: str = Field(default="pending") # pending, processed, paid, disputing
    
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    paid_at: Optional[datetime] = None
    
    pdf_statement_url: Optional[str] = None
    
    commissions: list[Commission] = Relationship(back_populates="settlement")
