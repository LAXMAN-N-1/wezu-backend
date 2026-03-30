from fastapi import APIRouter, Request, Header, HTTPException, Depends
from sqlmodel import Session, select
from app.api import deps
from app.core.config import settings
from app.services.wallet_service import WalletService
import hashlib
import hmac
import json
import logging

router = APIRouter()
logger = logging.getLogger("wezu_payments")

@router.post("/razorpay")
async def razorpay_webhook_event(
    request: Request,
    x_razorpay_signature: str = Header(None),
    db: Session = Depends(deps.get_db),
):
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        logger.error("RAZORPAY_WEBHOOK_SECRET is not configured")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    body = await request.body()
    
    # Verify Signature
    generated_signature = hmac.new(
        key=bytes(settings.RAZORPAY_WEBHOOK_SECRET, 'utf-8'),
        msg=body,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    if not x_razorpay_signature or generated_signature != x_razorpay_signature:
         logger.warning("Invalid Razorpay webhook signature")
         raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    event_type = event.get('event')
    payload = event.get('payload', {})
    
    logger.info(f"Processing Razorpay webhook event: {event_type}")

    if event_type == 'payment.captured':
        payment_entity = payload.get('payment', {}).get('entity', {})
        payment_id = payment_entity.get('id')
        amount = payment_entity.get('amount', 0) / 100.0 # convert paise to INR
        user_id = payment_entity.get('notes', {}).get('user_id')
        
        if user_id:
            WalletService.add_balance(
                db, 
                user_id=int(user_id), 
                amount=amount, 
                description=f"Razorpay Deposit: {payment_id}"
            )
            # Find and update any associated transaction record
            from app.models.financial import Transaction
            txn = db.exec(select(Transaction).where(Transaction.razorpay_payment_id == payment_id)).first()
            if txn:
                txn.status = "success"
                db.add(txn)
                db.commit()
            logger.info(f"Successfully processed payment for user {user_id}: {payment_id}")

    elif event_type == 'payment.failed':
        payment_entity = payload.get('payment', {}).get('entity', {})
        payment_id = payment_entity.get('id')
        logger.warning(f"Payment failed for users: {payment_id}")

    elif event_type == 'refund.processed':
        refund_entity = payload.get('refund', {}).get('entity', {})
        payment_id = refund_entity.get('payment_id')
        gateway_refund_id = refund_entity.get('id')
        
        from app.models.refund import Refund
        from datetime import datetime, UTC
        
        # Find pending refund by gateway payment ID or similar logic
        # Usually we link by payment_id and amount
        refund = db.exec(select(Refund).where(Refund.gateway_refund_id == gateway_refund_id)).first()
        if not refund:
            # Fallback: find by payment_id
            from app.models.financial import Transaction
            txn = db.exec(select(Transaction).where(Transaction.razorpay_payment_id == payment_id)).first()
            if txn:
                refund = db.exec(select(Refund).where(Refund.transaction_id == txn.id, Refund.status == "pending")).first()

        if refund:
            refund.status = "processed"
            refund.processed_at = datetime.now(UTC)
            refund.gateway_refund_id = gateway_refund_id
            db.add(refund)
            db.commit()
            logger.info(f"Refund {gateway_refund_id} processed for payment {payment_id}")
        
    return {"status": "ok"}
