from __future__ import annotations
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
    subtotal: float = 0.0
    total: float = 0.0
    notes: Optional[str] = None

class InvoiceResponse(BaseModel):
    id: int
    transaction_id: int
    invoice_number: Optional[str] = None
    amount: float
    subtotal: float = 0.0
    tax_amount: float = 0.0
    total: float = 0.0
    pdf_url: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class InvoiceListResponse(BaseModel):
    invoices: List[InvoiceResponse]
    total_count: int
    page: int = 1
    limit: int = 20
