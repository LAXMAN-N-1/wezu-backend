from fastapi import APIRouter, Request, Header, HTTPException, Depends
from sqlmodel import Session
from app.api import deps
from app.core.config import settings
from app.services.payment_service import PaymentService
# from app.services.wallet_service import WalletService
import hashlib
import hmac
import json

router = APIRouter()

@router.post("/razorpay")
async def razorpay_webhook_event(
    request: Request,
    x_razorpay_signature: str = Header(None),
    db: Session = Depends(deps.get_db),
):
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    body = await request.body()
    
    # Verify Signature
    # hmac verification
    generated_signature = hmac.new(
        key=bytes(settings.RAZORPAY_WEBHOOK_SECRET, 'utf-8'),
        msg=body,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    if generated_signature != x_razorpay_signature:
         raise HTTPException(status_code=400, detail="Invalid signature")

    event = json.loads(body)
    
    # Process Event
    if event['event'] == 'payment.captured':
        payment_id = event['payload']['payment']['entity']['id']
        order_id = event['payload']['payment']['entity']['order_id']
        amount = event['payload']['payment']['entity']['amount'] # in paise
        
        # Logic to find pending transaction by order_id and update status
        # wallet_txn = db.exec(...)
        # if wallet_txn:
        #     wallet_txn.status = "success"
        #     WalletService.credit(...)
        
    return {"status": "ok"}
