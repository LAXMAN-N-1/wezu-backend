"""
Enhanced Payment and Invoice API
Invoice generation, refunds, and payment methods
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session
from pydantic import BaseModel
from typing import Optional

from app.api import deps
from app.db.session import get_session
from app.models.user import User
from app.models.catalog import CatalogOrder
from app.models.rental import Rental
from app.services.invoice_service import InvoiceService
from app.schemas.common import DataResponse

router = APIRouter()

# Schemas
class RefundRequest(BaseModel):
    transaction_id: Optional[int] = None
    order_id: Optional[int] = None
    reason: str
    amount: Optional[float] = None  # If None, full refund

class PaymentMethodCreate(BaseModel):
    type: str  # card, upi, netbanking
    details: dict

# Payment Method Endpoints
@router.post("/methods")
async def add_payment_method(
    method: PaymentMethodCreate,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Add a new payment method"""
    return {
        "message": "Payment method added successfully",
        "method_id": "pm_" + str(current_user.id)
    }

@router.delete("/methods/{method_id}")
async def delete_payment_method(
    method_id: str,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Delete a payment method"""
    return {"message": "Payment method deleted successfully"}

# Invoice Endpoints
@router.get("/orders/{order_id}/invoice", response_class=StreamingResponse)
def download_order_invoice(
    order_id: int,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """
    Download PDF invoice for order
    Returns PDF file
    """
    # Verify order belongs to user
    order = session.get(CatalogOrder, order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Generate invoice
    pdf_buffer = InvoiceService.generate_order_invoice(order_id, session)
    
    if not pdf_buffer:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate invoice"
        )
    
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=invoice_{order.order_number}.pdf"
        }
    )

@router.get("/rentals/{rental_id}/invoice", response_class=StreamingResponse)
def download_rental_invoice(
    rental_id: int,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Download PDF invoice for rental"""
    # Verify rental belongs to user
    rental = session.get(Rental, rental_id)
    if not rental or rental.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rental not found"
        )
    
    pdf_buffer = InvoiceService.generate_rental_invoice(rental_id, session)
    
    if not pdf_buffer:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate invoice"
        )
    
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=rental_invoice_{rental_id}.pdf"
        }
    )

# Refund Endpoints
@router.post("/orders/{order_id}/refund", response_model=DataResponse[dict])
def request_refund(
    order_id: int,
    request: RefundRequest,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """
    Request refund for order
    Creates refund request for admin approval
    """
    order = session.get(CatalogOrder, order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    if order.status not in ["CONFIRMED", "SHIPPED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order cannot be refunded"
        )
    
    # Create refund transaction
    from app.models.financial import Transaction
    from datetime import datetime
    
    refund_amount = request.amount or order.total_amount
    
    transaction = Transaction(
        user_id=current_user.id,
        order_id=order_id,
        transaction_type="REFUND",
        amount=refund_amount,
        status="PENDING",
        description=f"Refund request: {request.reason}",
        created_at=datetime.utcnow()
    )
    session.add(transaction)
    session.commit()
    
    return DataResponse(
        success=True,
        data={
            "transaction_id": transaction.id,
            "refund_amount": refund_amount,
            "status": "PENDING",
            "message": "Refund request submitted. Processing time: 3-5 business days"
        }
    )

@router.get("/refunds", response_model=DataResponse[list])
def get_user_refunds(
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Get all refund requests for current user"""
    from app.models.financial import Transaction
    from sqlmodel import select
    
    refunds = session.exec(
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .where(Transaction.transaction_type == "REFUND")
        .order_by(Transaction.created_at.desc())
    ).all()
    
    return DataResponse(
        success=True,
        data=[
            {
                "id": refund.id,
                "order_id": refund.order_id,
                "amount": refund.amount,
                "status": refund.status,
                "description": refund.description,
                "created_at": refund.created_at.isoformat()
            }
            for refund in refunds
        ]
    )

# Payment Methods Info
@router.get("/payment-methods", response_model=DataResponse[dict])
def get_payment_methods(current_user: User = Depends(deps.get_current_user)):
    """Get available payment methods"""
    return DataResponse(
        success=True,
        data={
            "methods": [
                {
                    "id": "UPI",
                    "name": "UPI",
                    "description": "Google Pay, PhonePe, Paytm, etc.",
                    "icon": "upi",
                    "enabled": True
                },
                {
                    "id": "CARD",
                    "name": "Credit/Debit Card",
                    "description": "Visa, Mastercard, RuPay",
                    "icon": "card",
                    "enabled": True
                },
                {
                    "id": "WALLET",
                    "name": "Digital Wallet",
                    "description": "Paytm, Amazon Pay, etc.",
                    "icon": "wallet",
                    "enabled": True
                },
                {
                    "id": "NETBANKING",
                    "name": "Net Banking",
                    "description": "All major banks",
                    "icon": "bank",
                    "enabled": True
                }
            ]
        }
    )
