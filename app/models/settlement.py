from typing import Optional, TYPE_CHECKING, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from app.models.dealer import DealerProfile
    from app.models.commission import CommissionLog
    from app.models.vendor import Vendor


class Settlement(SQLModel, table=True):
    __tablename__ = "settlements"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    
    dealer_id: Optional[int] = Field(default=None, foreign_key="dealer_profiles.id", index=True)
    vendor_id: Optional[int] = Field(default=None, foreign_key="vendors.id")
    # user_id: Optional[int] = Field(default=None, foreign_key="users.id") # If needed for something else

    # Period
    settlement_month: str = Field(index=True)  # "YYYY-MM" for fast lookup
    start_date: datetime
    end_date: datetime
    due_date: Optional[datetime] = None

    # Financials (all rounded to 2 decimal places)
    total_revenue: float = Field(default=0.0)       # Total collected from swaps
    total_commission: float = Field(default=0.0)     # Calculated commission earnings
    chargeback_amount: float = Field(default=0.0)    # Total chargebacks deducted
    platform_fee: float = Field(default=0.0)         # Platform's cut
    tax_amount: float = Field(default=0.0)           # GST/VAT if applicable
    net_payable: float = Field(default=0.0)          # Final amount to dealer/vendor

    currency: str = Field(default="INR")
    status: str = Field(default="pending")  # pending, generated, approved, processing, paid, failed
    failure_reason: Optional[str] = None

    # Payment details
    transaction_reference: Optional[str] = None  # Bank transfer ref
    payment_proof_url: Optional[str] = None      # Receipt/proof URL

    created_at: datetime = Field(default_factory=datetime.utcnow)
    paid_at: Optional[datetime] = None

    # Relationship
    dealer: Optional["DealerProfile"] = Relationship(back_populates="settlements")
    vendor: Optional["Vendor"] = Relationship(back_populates="settlements")
    commission_logs: List["CommissionLog"] = Relationship(back_populates="settlement")
