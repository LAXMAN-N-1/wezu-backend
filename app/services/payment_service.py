import razorpay
from app.core.config import settings
from fastapi import HTTPException, status
import logging
import uuid

logger = logging.getLogger("wezu_payments")

# Determine if we're in mock mode (explicit opt-in only)
PAYMENT_MOCK_MODE = getattr(settings, "PAYMENT_MOCK_MODE", False)

# Initialize Razorpay client only if real keys are available
_client = None
if settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
    _client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
elif not PAYMENT_MOCK_MODE:
    logger.warning("PAYMENT_SERVICE: Razorpay keys not configured. Set PAYMENT_MOCK_MODE=true for dev.")


def _get_client() -> razorpay.Client:
    """Get Razorpay client or raise if not configured."""
    if _client:
        return _client
    if PAYMENT_MOCK_MODE:
        return None
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Payment gateway not configured. Contact administrator."
    )


class PaymentService:
    @staticmethod
    def create_order(amount: float, currency: str = "INR") -> dict:
        client = _get_client()
        if client is None and PAYMENT_MOCK_MODE:
            logger.info(f"MOCK_PAYMENT: Creating mock order for {amount} {currency}")
            return {
                "id": f"order_mock_{uuid.uuid4().hex[:12]}",
                "amount": int(amount * 100),
                "currency": currency,
                "status": "created",
                "_mock": True
            }

        try:
            data = {
                "amount": int(amount * 100),
                "currency": currency,
                "payment_capture": 1
            }
            order = client.order.create(data=data)
            return order
        except Exception as e:
            logger.error(f"PAYMENT_ERROR: Failed to create order: {e}")
            raise HTTPException(status_code=400, detail=f"Payment order creation failed: {str(e)}")

    @staticmethod
    def verify_payment_signature(params_dict: dict) -> bool:
        client = _get_client()
        if client is None and PAYMENT_MOCK_MODE:
            logger.info("MOCK_PAYMENT: Skipping signature verification in mock mode")
            return True

        try:
            client.utility.verify_payment_signature(params_dict)
            return True
        except Exception as e:
            logger.error(f"PAYMENT_ERROR: Signature verification failed: {e}")
            return False

    @staticmethod
    def refund_transaction(transaction_id: str, amount: float = None) -> dict:
        """Initiate a refund for a payment."""
        client = _get_client()
        if client is None and PAYMENT_MOCK_MODE:
            logger.info(f"MOCK_PAYMENT: Mock refund for {transaction_id}")
            return {
                "id": f"rfnd_mock_{uuid.uuid4().hex[:12]}",
                "payment_id": transaction_id,
                "amount": int(amount * 100) if amount else 0,
                "status": "processed",
                "_mock": True
            }

        try:
            data = {"payment_id": transaction_id}
            if amount:
                data["amount"] = int(amount * 100)
            refund = client.payment.refund(transaction_id, data)
            return refund
        except Exception as e:
            logger.error(f"PAYMENT_ERROR: Refund failed for {transaction_id}: {e}")
            raise HTTPException(status_code=400, detail=f"Refund failed: {str(e)}")

    @staticmethod
    def verify_webhook_signature(body: bytes, signature: str) -> bool:
        """Verify Razorpay webhook signature."""
        webhook_secret = getattr(settings, "RAZORPAY_WEBHOOK_SECRET", None)
        if not webhook_secret or not signature:
            if PAYMENT_MOCK_MODE:
                return True
            logger.warning("PAYMENT_WARNING: Webhook secret not configured")
            return False

        try:
            _get_client().utility.verify_webhook_signature(body.decode(), signature, webhook_secret)
            return True
        except Exception:
            return False

