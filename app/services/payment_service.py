import razorpay
from app.core.config import settings
from fastapi import HTTPException, status

# Mock keys if not present (handled gracefully)
KEY_ID = getattr(settings, "RAZORPAY_KEY_ID", "rzp_test_default")
KEY_SECRET = getattr(settings, "RAZORPAY_KEY_SECRET", "secret_default")

client = razorpay.Client(auth=(KEY_ID, KEY_SECRET))

class PaymentService:
    @staticmethod
    def create_order(amount: float, currency: str = "INR") -> dict:
        try:
            data = {
                "amount": int(amount * 100), # Amount in paise
                "currency": currency,
                "payment_capture": 1
            }
            order = client.order.create(data=data)
            return order
        except Exception as e:
            # In dev/mock mode, return a dummy order if keys are invalid
            if "default" in KEY_ID:
                import uuid
                return {
                    "id": f"order_{uuid.uuid4()}",
                    "amount": int(amount * 100),
                    "currency": currency
                }
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    def verify_payment_signature(params_dict: dict):
        try:
            client.utility.verify_payment_signature(params_dict)
            return True
        except Exception as e:
            if "default" in KEY_ID:
                return True # Mock verify
    @staticmethod
    def refund_transaction(transaction_id: str, amount: float = None) -> dict:
        """
        Initiate a refund for a payment. 
        If amount is None, full refund.
        """
        try:
            data = {"payment_id": transaction_id}
            if amount:
                data["amount"] = int(amount * 100) # paise
            
            refund = client.payment.refund(transaction_id, data)
            return refund
        except Exception as e:
            if "default" in KEY_ID:
                 import uuid
                 return {
                     "id": f"rfnd_{uuid.uuid4()}",
                     "payment_id": transaction_id,
                     "amount": int(amount * 100) if amount else 0,
                     "status": "processed"
                 }
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    def verify_webhook_signature(body: bytes, signature: str) -> bool:
        """
        Verify Razorpay webhook signature.
        """
        webhook_secret = getattr(settings, "RAZORPAY_WEBHOOK_SECRET", None)
        if not webhook_secret or not signature:
            # Fallback for dev/mock if secret not provided
            return True
            
        try:
            client.utility.verify_webhook_signature(body.decode(), signature, webhook_secret)
            return True
        except Exception:
            return False

