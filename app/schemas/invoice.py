"""
Invoice schemas
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


class InvoiceCreate(BaseModel):
    transaction_id: int
    invoice_number: Optional[str] = None
    amount: float
    tax_amount: float = 0.0
    total_amount: float = 0.0
    currency: str = "INR"
    notes: Optional[str] = None

class InvoiceResponse(BaseModel):
    id: int
    transaction_id: int
    invoice_number: Optional[str] = None
    amount: float
    tax_amount: float = 0.0
    total_amount: float = 0.0
    currency: str = "INR"
    status: str = "generated"
    pdf_url: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class InvoiceListResponse(BaseModel):
    invoices: List[InvoiceResponse]
    total_count: int
    page: int = 1
    limit: int = 20
