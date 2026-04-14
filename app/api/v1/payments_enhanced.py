"""
Enhanced Payment Endpoints
Secondary payment operations for receipts, invoices, and webhook compatibility.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api import deps
from app.core.config import settings
from app.db.session import get_session
from app.models.financial import Transaction, Wallet
from app.models.payment_method import PaymentMethod
from app.models.refund import Refund
from app.models.user import User
from app.services.razorpay_webhook_service import RazorpayWebhookService

router = APIRouter()


class PaymentMethodCreate(BaseModel):
    type: str
    provider_token: str
    provider: str = "razorpay"
    is_default: bool = False
    details: dict = Field(default_factory=dict)


class RefundRequest(BaseModel):
    transaction_id: int
    amount: Optional[float] = None
    reason: str


def _get_owned_transaction(db: Session, user_id: int, transaction_id: int) -> Optional[Transaction]:
    return db.exec(
        select(Transaction)
        .join(Wallet, Wallet.id == Transaction.wallet_id)
        .where(Transaction.id == transaction_id, Wallet.user_id == user_id)
    ).first()


# DECONFLICTED P0-B: POST /methods and DELETE /methods/{method_id} removed.
# Canonical handlers live in app/api/v1/payments.py (uses PaymentMethodService).
# Removed 2026-04-06.


@router.get("/methods")
def list_payment_methods(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    methods = db.exec(
        select(PaymentMethod)
        .where(PaymentMethod.user_id == current_user.id)
        .where(PaymentMethod.status == "active")
        .order_by(PaymentMethod.is_default.desc(), PaymentMethod.created_at.desc())
    ).all()
    return [
        {
            "id": row.id,
            "provider": row.provider,
            "type": row.method_type,
            "last4": row.last4,
            "brand": row.brand,
            "is_default": row.is_default,
            "created_at": row.created_at,
        }
        for row in methods
    ]


@router.post("/methods/{method_id}/default")
def set_default_payment_method(
    method_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    selected = db.exec(
        select(PaymentMethod)
        .where(PaymentMethod.id == method_id)
        .where(PaymentMethod.user_id == current_user.id)
        .where(PaymentMethod.status == "active")
    ).first()
    if not selected:
        raise HTTPException(status_code=404, detail="Payment method not found")

    active_methods = db.exec(
        select(PaymentMethod)
        .where(PaymentMethod.user_id == current_user.id)
        .where(PaymentMethod.status == "active")
    ).all()
    now = datetime.utcnow()
    for row in active_methods:
        row.is_default = row.id == selected.id
        row.updated_at = now
        db.add(row)
    db.commit()
    return {"message": "Default payment method updated", "method_id": selected.id}


@router.get("/refunds/history")
def list_refunds(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """Enhanced refund history endpoint without shadowing /refunds."""
    rows = db.exec(
        select(Refund, Transaction)
        .join(Transaction, Refund.transaction_id == Transaction.id)
        .join(Wallet, Transaction.wallet_id == Wallet.id)
        .where(Wallet.user_id == current_user.id)
        .order_by(Refund.created_at.desc())
    ).all()
    return [
        {
            "id": refund.id,
            "transaction_id": transaction.id,
            "amount": float(refund.amount),
            "status": refund.status,
            "reason": refund.reason,
            "created_at": refund.created_at,
            "processed_at": refund.processed_at,
            "gateway_refund_id": refund.gateway_refund_id,
        }
        for refund, transaction in rows
    ]


@router.get("/{transaction_id}/receipt")
def get_receipt(
    transaction_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """Get receipt metadata for a wallet transaction."""
    transaction = _get_owned_transaction(db, current_user.id, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return {
        "transaction_id": transaction.id,
        "amount": transaction.amount,
        "status": transaction.status,
        "type": transaction.type,
        "category": transaction.category,
        "created_at": transaction.created_at,
        "description": transaction.description,
        "receipt_url": f"/receipts/{transaction.id}.pdf",
    }


@router.post("/razorpay/webhook")
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_session),
):
    """Compatibility webhook endpoint under /api/v1/payments (canonical handler)."""
    body_bytes = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")
    event_id = request.headers.get("X-Razorpay-Event-Id")

    if not RazorpayWebhookService.verify_signature(body_bytes, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = RazorpayWebhookService.parse_payload(body_bytes)
    if settings.WEBHOOK_QUEUE_ENABLED:
        queued_id = RazorpayWebhookService.enqueue_event(
            body=body_bytes,
            signature=signature,
            payload=payload,
            source="/api/v1/payments/razorpay/webhook",
            event_id=event_id,
        )
        if queued_id:
            return {
                "status": "accepted",
                "mode": "queued",
                "queue_id": queued_id,
                "event_id": RazorpayWebhookService.compute_event_id(body_bytes, event_id),
            }
        if settings.WEBHOOK_QUEUE_REQUIRED:
            raise HTTPException(status_code=503, detail="Webhook queue is unavailable. Please retry.")

    return RazorpayWebhookService.process_event(db, payload)


@router.get("/invoice/{transaction_id}")
def get_invoice(
    transaction_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """Get invoice metadata for a wallet transaction."""
    transaction = _get_owned_transaction(db, current_user.id, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    amount = Decimal(str(transaction.amount)).quantize(Decimal("0.01"))
    gst = (amount * Decimal("0.18")).quantize(Decimal("0.01"))

    return {
        "invoice_id": f"INV-{transaction.id}",
        "transaction_id": transaction.id,
        "amount": float(amount),
        "gst": float(gst),
        "total": float(amount + gst),
        "status": transaction.status,
        "description": transaction.description,
        "invoice_url": f"/invoices/{transaction.id}.pdf",
    }
