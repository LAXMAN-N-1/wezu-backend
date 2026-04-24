from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime, timezone; UTC = timezone.utc

class Invoice(SQLModel, table=True):
    __tablename__ = "invoices"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    transaction_id: int = Field(foreign_key="transactions.id")
    invoice_number: str = Field(unique=True)
    amount: float
    subtotal: float = Field(default=0.0)
    tax_amount: float = Field(default=0.0)
    total: float = Field(default=0.0)
    gstin: Optional[str] = None
    hsn_code: Optional[str] = None
    is_late_fee: bool = Field(default=False)
    
    pdf_url: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Relationships
    user: "User" = Relationship()
    transaction: "Transaction" = Relationship(back_populates="invoice")

# Need to update Transaction to have invoice relationship
