from __future__ import annotations
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import Response, StreamingResponse
from sqlmodel import Session, select, func
from datetime import datetime

from app.api.deps import get_current_active_superuser
from app.core.database import get_db
from app.models.invoice import Invoice
from app.models.user import User
from app.services.invoice_service import InvoiceService
from pydantic import BaseModel

router = APIRouter()

class InvoiceResponse(BaseModel):
    id: int
    user_id: int
    transaction_id: int
    invoice_number: str
    amount: float
    subtotal: float
    tax_amount: float
    total: float
    pdf_url: Optional[str]
    created_at: datetime

@router.get("/", response_model=dict)
def list_admin_invoices(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    user_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> Any:
    """Admin: List all invoices across the platform with filters."""
    query = select(Invoice)
    
    if user_id:
        query = query.where(Invoice.user_id == user_id)
    if date_from:
        query = query.where(Invoice.created_at >= date_from)
    if date_to:
        query = query.where(Invoice.created_at <= date_to)
        
    total = db.exec(select(func.count()).select_from(query.subquery())).one()
    invoices = db.exec(query.order_by(Invoice.created_at.desc()).offset(skip).limit(limit)).all()
    
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": invoices
    }

@router.get("/{invoice_id}/pdf")
def download_invoice_pdf(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    invoice_id: int,
) -> Any:
    """Admin: Download the PDF for a specific invoice."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
        
    # Proxy to InvoiceService based on transaction type (Order vs Rental)
    # For now, we use a generic generation if not already stored
    from app.models.financial import Transaction, TransactionType
    txn = db.get(Transaction, invoice.transaction_id)
    
    buffer = None
    filename = f"invoice_{invoice.invoice_number}.pdf"
    
    if txn and txn.rental_id:
        buffer = InvoiceService.generate_rental_invoice(txn.rental_id, db)
    else:
        # Fallback to order invoice if possible, or generic
        # (Assuming most transactions are swaps/rentals in this context)
        buffer = InvoiceService.generate_rental_invoice(invoice.transaction_id, db) # Simplified fallback
        
    if not buffer:
        raise HTTPException(status_code=500, detail="Failed to generate PDF")
        
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
