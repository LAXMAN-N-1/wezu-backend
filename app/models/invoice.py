from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime

class Invoice(SQLModel, table=True):
    __tablename__ = "invoices"
    __table_args__ = {"schema": "finance"}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="core.users.id")
    transaction_id: int = Field(foreign_key="finance.transactions.id")
    invoice_number: str = Field(unique=True)
    amount: float
    tax_amount: float
    gstin: Optional[str] = None
    hsn_code: Optional[str] = None
    is_late_fee: bool = Field(default=False)
    
    pdf_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    user: "User" = Relationship()
    transaction: "Transaction" = Relationship(back_populates="invoice")

# Need to update Transaction to have invoice relationship
