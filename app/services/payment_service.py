import razorpay
from app.core.config import settings
from app.core.logging import get_logger
from fastapi import HTTPException, status
import uuid

logger = get_logger("wezu_payments")

# ── Mock-mode guard ───────────────────────────────────────────────────────
# Mock mode is for local dev / CI ONLY.  It MUST NEVER be active in prod.
PAYMENT_MOCK_MODE = getattr(settings, "PAYMENT_MOCK_MODE", False)

if PAYMENT_MOCK_MODE and getattr(settings, "ENVIRONMENT", "development") == "production":
    raise RuntimeError(
        "FATAL: PAYMENT_MOCK_MODE is True while ENVIRONMENT=production. "
        "This is a configuration error — disable PAYMENT_MOCK_MODE before "
        "deploying to production."
    )

# Initialize Razorpay client only if real keys are available
_client = None
if settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
    _client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
elif not PAYMENT_MOCK_MODE:
    if settings.REQUIRE_PAYMENT_AT_STARTUP:
        logger.warning("payment.razorpay_keys_missing")
    else:
        logger.info("payment.razorpay_keys_missing_optional")

if PAYMENT_MOCK_MODE:
    logger.info(
        "payment.mock_mode_active",
        environment=getattr(settings, "ENVIRONMENT", "unknown"),
    )


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
            mock_id = f"order_mock_{uuid.uuid4().hex[:12]}"
            logger.warning(
                "payment.mock_create_order",
                amount=amount,
                currency=currency,
                mock_id=mock_id,
            )
            return {
                "id": mock_id,
                "amount": int(amount * 100),
                "currency": currency,
                "status": "created",
                "_mock": True,
            }

        try:
            data = {
                "amount": int(amount * 100),
                "currency": currency,
                "payment_capture": 1,
            }
            order = client.order.create(data=data)
            logger.info("payment.order_created", order_id=order.get("id"), amount=data["amount"])
            return order
        except Exception as e:
            logger.error("payment.order_create_failed", error=str(e))
            raise HTTPException(status_code=400, detail=f"Payment order creation failed: {str(e)}")

    @staticmethod
    def verify_payment_signature(params_dict: dict) -> bool:
        client = _get_client()
        if client is None and PAYMENT_MOCK_MODE:
            logger.warning("payment.mock_skip_signature_verify")
            return True

        try:
            client.utility.verify_payment_signature(params_dict)
            logger.info("payment.signature_verified", order_id=params_dict.get("razorpay_order_id"))
            return True
        except Exception as e:
            logger.error("payment.signature_verification_failed", error=str(e))
            return False

    @staticmethod
    def refund_transaction(transaction_id: str, amount: float = None) -> dict:
        """Initiate a refund for a payment via the payment gateway."""
        client = _get_client()
        if client is None and PAYMENT_MOCK_MODE:
            mock_id = f"rfnd_mock_{uuid.uuid4().hex[:12]}"
            logger.warning(
                "payment.mock_refund",
                transaction_id=transaction_id,
                amount=amount,
                mock_refund_id=mock_id,
            )
            return {
                "id": mock_id,
                "payment_id": transaction_id,
                "amount": int(amount * 100) if amount else 0,
                "status": "processed",
                "_mock": True,
            }

        try:
            data = {"payment_id": transaction_id}
            if amount:
                data["amount"] = int(amount * 100)
            refund = client.payment.refund(transaction_id, data)
            logger.info("payment.refund_initiated", refund_id=refund.get("id"), payment_id=transaction_id)
            return refund
        except Exception as e:
            logger.error("payment.refund_failed", transaction_id=transaction_id, error=str(e))
            raise HTTPException(status_code=400, detail=f"Refund failed: {str(e)}")

    @staticmethod
    def verify_webhook_signature(body: bytes, signature: str) -> bool:
        """Verify Razorpay webhook signature."""
        webhook_secret = getattr(settings, "RAZORPAY_WEBHOOK_SECRET", None)
        if not webhook_secret or not signature:
            if PAYMENT_MOCK_MODE:
                return True
            logger.warning("payment.webhook_secret_missing")
            return False

        try:
            _get_client().utility.verify_webhook_signature(body.decode(), signature, webhook_secret)
            return True
        except Exception:
            return False
