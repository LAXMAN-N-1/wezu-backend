from __future__ import annotations
"""
Enhanced Payment Endpoints
Secondary payment operations for receipts, invoices, and webhook compatibility.
"""
from datetime import datetime, timezone; UTC = timezone.utc
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlmodel import Session, select

from app.api import deps
from app.core.config import settings
from app.db.session import get_session
from app.models.financial import (
    Transaction,
    TransactionStatus,
    TransactionType,
    Wallet,
)
from app.models.payment_method import PaymentMethod
from app.models.refund import Refund
from app.models.user import User
from app.services.payment_service import PaymentService
from app.services.razorpay_webhook_service import RazorpayWebhookService
from app.services.wallet_service import WalletService

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


class PaymentInitiateRequest(BaseModel):
    amount: float = Field(gt=0)
    payment_method: str = Field(default="upi", min_length=1, max_length=32)
    product_sku: Optional[str] = None
    description: Optional[str] = None
    currency: str = Field(default="INR", min_length=3, max_length=3)


class PaymentVerifyRequest(BaseModel):
    transaction_id: Optional[int] = None
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    razorpay_signature: Optional[str] = None


class CompatibilityInvoiceRequest(BaseModel):
    order_id: Optional[str] = None
    product_name: Optional[str] = None
    amount: Optional[float] = None


class RefundCompatibilityRequest(BaseModel):
    transaction_id: str
    amount: Optional[float] = None
    reason: str = "customer_requested"


def _get_owned_transaction(db: Session, user_id: int, transaction_id: int) -> Optional[Transaction]:
    transaction = db.exec(
        select(Transaction)
        .join(Wallet, Wallet.id == Transaction.wallet_id)
        .where(Transaction.id == transaction_id, Wallet.user_id == user_id)
    ).first()
    if transaction:
        return transaction
    return db.exec(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
        )
    ).first()


def _resolve_owned_transaction_reference(
    db: Session,
    *,
    user_id: int,
    transaction_reference: str,
) -> Optional[Transaction]:
    token = (transaction_reference or "").strip()
    if not token:
        return None

    if token.isdigit():
        transaction = _get_owned_transaction(db, user_id, int(token))
        if transaction:
            return transaction

    return db.exec(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .where(
            or_(
                Transaction.payment_gateway_ref == token,
                Transaction.razorpay_payment_id == token,
                Transaction.reference_id == token,
            )
        )
        .order_by(Transaction.created_at.desc())
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


@router.post("/initiate")
def initiate_payment(
    request: PaymentInitiateRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Mobile compatibility endpoint.
    Creates a gateway order + pending transaction row and returns both IDs.
    """
    wallet = WalletService.get_wallet(db, current_user.id)
    gateway_order = PaymentService.create_order(request.amount, currency=request.currency.upper())
    gateway_order_id = str(gateway_order.get("id") or "")
    if not gateway_order_id:
        raise HTTPException(status_code=502, detail="Payment gateway order creation failed")

    payment_method = (request.payment_method or "upi").strip().lower()
    transaction = Transaction(
        user_id=current_user.id,
        wallet_id=wallet.id,
        amount=float(request.amount),
        transaction_type=TransactionType.PURCHASE,
        status=TransactionStatus.PENDING,
        payment_method=payment_method or "upi",
        payment_gateway_ref=gateway_order_id,
        description=request.description
        or f"Payment initiated for {request.product_sku or 'purchase'}",
        reference_type="purchase",
        reference_id=request.product_sku,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    return {
        "status": "initiated",
        "order_id": gateway_order_id,
        "transaction_id": transaction.id,
        "amount": float(request.amount),
        "currency": request.currency.upper(),
    }


@router.post("/verify")
def verify_payment(
    request: PaymentVerifyRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Mobile compatibility endpoint to mark initiated payments as successful.
    """
    order_id = (request.razorpay_order_id or "").strip()
    payment_id = (request.razorpay_payment_id or "").strip()
    signature = (request.razorpay_signature or "").strip()

    transaction: Optional[Transaction] = None
    if request.transaction_id is not None:
        transaction = _get_owned_transaction(db, current_user.id, request.transaction_id)
    if transaction is None and order_id:
        transaction = db.exec(
            select(Transaction)
            .where(Transaction.user_id == current_user.id)
            .where(Transaction.payment_gateway_ref == order_id)
            .order_by(Transaction.created_at.desc())
        ).first()
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if order_id and payment_id and signature:
        if not PaymentService.verify_payment_signature(
            {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature,
            }
        ):
            raise HTTPException(status_code=400, detail="Payment signature verification failed")

    transaction.status = TransactionStatus.SUCCESS
    if payment_id:
        transaction.razorpay_payment_id = payment_id
    transaction.updated_at = datetime.now(UTC)
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    return {
        "status": "success",
        "transaction_id": transaction.id,
        "order_id": transaction.payment_gateway_ref,
        "payment_id": transaction.razorpay_payment_id,
    }


@router.post("/refund")
def request_refund_compatibility(
    request: RefundCompatibilityRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Compatibility endpoint for clients posting to /payments/refund.
    Accepts transaction id/gateway reference and creates a refund request.
    """
    transaction = _resolve_owned_transaction_reference(
        db,
        user_id=current_user.id,
        transaction_reference=request.transaction_id,
    )
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if transaction.status == TransactionStatus.REFUNDED:
        return {
            "status": "already_refunded",
            "transaction_id": transaction.id,
        }

    refund_amount = float(request.amount) if request.amount is not None else float(transaction.amount)
    if refund_amount <= 0:
        raise HTTPException(status_code=400, detail="Refund amount must be greater than zero")

    existing_refund = db.exec(
        select(Refund)
        .where(Refund.transaction_id == transaction.id)
        .where(Refund.status.in_(["pending", "processed"]))
        .order_by(Refund.created_at.desc())
    ).first()
    if existing_refund:
        return {
            "status": existing_refund.status,
            "refund_id": existing_refund.id,
            "transaction_id": transaction.id,
        }

    gateway_payment_id = (transaction.razorpay_payment_id or transaction.payment_gateway_ref or "").strip()
    gateway_refund_id: Optional[str] = None
    refund_status = "pending"
    processed_at = None
    if gateway_payment_id:
        try:
            gateway_refund = PaymentService.refund_transaction(gateway_payment_id, refund_amount)
            gateway_refund_id = str(gateway_refund.get("id") or "") or None
            raw_status = str(gateway_refund.get("status") or "pending").lower()
            if raw_status in {"processed", "success", "completed"}:
                refund_status = "processed"
                processed_at = datetime.now(UTC)
            else:
                refund_status = "pending"
        except HTTPException:
            # Keep a pending refund request for manual processing if gateway reject occurs.
            refund_status = "pending"

    refund_record = Refund(
        transaction_id=transaction.id,
        amount=refund_amount,
        reason=request.reason,
        status=refund_status,
        gateway_refund_id=gateway_refund_id,
        processed_at=processed_at,
    )
    db.add(refund_record)
    if refund_status == "processed":
        transaction.status = TransactionStatus.REFUNDED
        transaction.updated_at = datetime.now(UTC)
        db.add(transaction)
    db.commit()
    db.refresh(refund_record)

    return {
        "status": "initiated" if refund_record.status == "pending" else "processed",
        "refund_id": refund_record.id,
        "transaction_id": transaction.id,
    }


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


@router.post("/{transaction_id}/invoice")
def create_invoice_compatibility(
    transaction_id: int,
    request: CompatibilityInvoiceRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Compatibility endpoint for clients expecting POST /payments/{id}/invoice.
    Returns invoice metadata payload consumed by mobile UI.
    """
    transaction = _get_owned_transaction(db, current_user.id, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    amount = Decimal(str(request.amount if request.amount is not None else transaction.amount)).quantize(
        Decimal("0.01")
    )
    product_name = (request.product_name or "").strip() or "Battery Rental"

    return {
        "invoice_id": f"INV-{transaction.id}",
        "order_id": request.order_id or transaction.reference_id or transaction.payment_gateway_ref or str(transaction.id),
        "transaction_id": str(transaction.id),
        "product_name": product_name,
        "amount": float(amount),
        "payment_method": transaction.payment_method or "upi",
        "customer_name": current_user.full_name or "Customer",
        "customer_address": "",
        "generated_at": datetime.now(UTC).isoformat(),
        "invoice_url": f"/invoices/{transaction.id}.pdf",
    }


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
