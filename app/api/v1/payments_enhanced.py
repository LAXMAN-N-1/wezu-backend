"""
Enhanced Payment Endpoints
Additional payment operations including methods, refunds, and webhooks
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session
from typing import List, Optional
from app.api import deps
from app.models.user import User
from app.models.financial import Transaction
from app.db.session import get_session
from app.integrations.razorpay import razorpay_integration
from pydantic import BaseModel
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class PaymentMethodCreate(BaseModel):
    type: str  # card, upi, netbanking
    details: dict


class RefundRequest(BaseModel):
    transaction_id: int
    amount: Optional[float] = None
    reason: str


@router.post("/methods")
async def add_payment_method(
    method: PaymentMethodCreate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Add a new payment method"""
    # In production, you would save tokenized payment details
    return {
        "message": "Payment method added successfully",
        "method_id": "pm_" + str(current_user.id)
    }


@router.delete("/methods/{method_id}")
async def delete_payment_method(
    method_id: str,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Delete a payment method"""
    # In production, you would delete from payment gateway
    return {"message": "Payment method deleted successfully"}


@router.get("/refunds")
async def list_refunds(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """List all refunds for user"""
    from sqlmodel import select
    statement = select(Transaction).where(
        (Transaction.user_id == current_user.id) &
        (Transaction.transaction_type == "refund")
    )
    refunds = db.exec(statement).all()
    return refunds


@router.get("/{transaction_id}/receipt")
async def get_receipt(
    transaction_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Get payment receipt"""
    transaction = db.get(Transaction, transaction_id)
    if not transaction or transaction.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    return {
        "transaction_id": transaction.id,
        "amount": transaction.amount,
        "status": transaction.status,
        "created_at": transaction.created_at,
        "receipt_url": f"/receipts/{transaction.id}.pdf"
    }


@router.post("/razorpay/webhook")
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_session)
):
    """Handle Razorpay webhooks"""
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")
    
    # Verify webhook signature
    if not razorpay_integration.verify_webhook_signature(body.decode(), signature):
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    import json
    payload = json.loads(body)
    event = payload.get("event")
    
    logger.info(f"Razorpay webhook received: {event}")
    
    # Handle different events
    if event == "payment.captured":
        # Update transaction status
        payment_data = payload.get("payload", {}).get("payment", {}).get("entity", {})
        # Process payment
        pass
    elif event == "refund.created":
        # Process refund
        pass
    
    return {"status": "ok"}


@router.get("/invoice/{transaction_id}")
async def get_invoice(
    transaction_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Get invoice for transaction"""
    transaction = db.get(Transaction, transaction_id)
    if not transaction or transaction.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    return {
        "invoice_id": f"INV-{transaction.id}",
        "transaction_id": transaction.id,
        "amount": transaction.amount,
        "gst": transaction.amount * 0.18,
        "total": transaction.amount * 1.18,
        "invoice_url": f"/invoices/{transaction.id}.pdf"
    }
