"""
Razorpay Payment Gateway Integration
Handles payment initiation, verification, and refunds
"""
import razorpay
from typing import Dict, Any, Optional
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class RazorpayIntegration:
    """Razorpay payment gateway wrapper"""
    
    def __init__(self):
        self.client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
    
    def create_order(
        self,
        amount: float,
        currency: str = "INR",
        receipt: Optional[str] = None,
        notes: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a Razorpay order
        
        Args:
            amount: Amount in rupees (will be converted to paise)
            currency: Currency code (default: INR)
            receipt: Receipt ID for reference
            notes: Additional notes/metadata
            
        Returns:
            Order details including order_id
        """
        try:
            amount_paise = int(amount * 100)  # Convert to paise
            
            order_data = {
                "amount": amount_paise,
                "currency": currency,
                "payment_capture": 1  # Auto capture
            }
            
            if receipt:
                order_data["receipt"] = receipt
            if notes:
                order_data["notes"] = notes
            
            order = self.client.order.create(data=order_data)
            logger.info(f"Razorpay order created: {order['id']}")
            return order
            
        except Exception as e:
            logger.error(f"Razorpay order creation failed: {str(e)}")
            raise
    
    def verify_payment_signature(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str
    ) -> bool:
        """
        Verify payment signature
        
        Args:
            razorpay_order_id: Order ID
            razorpay_payment_id: Payment ID
            razorpay_signature: Signature to verify
            
        Returns:
            True if signature is valid
        """
        try:
            params_dict = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            }
            
            self.client.utility.verify_payment_signature(params_dict)
            logger.info(f"Payment signature verified: {razorpay_payment_id}")
            return True
            
        except razorpay.errors.SignatureVerificationError as e:
            logger.error(f"Payment signature verification failed: {str(e)}")
            return False
    
    def fetch_payment(self, payment_id: str) -> Dict[str, Any]:
        """
        Fetch payment details
        
        Args:
            payment_id: Razorpay payment ID
            
        Returns:
            Payment details
        """
        try:
            payment = self.client.payment.fetch(payment_id)
            return payment
        except Exception as e:
            logger.error(f"Failed to fetch payment {payment_id}: {str(e)}")
            raise
    
    def capture_payment(
        self,
        payment_id: str,
        amount: float,
        currency: str = "INR"
    ) -> Dict[str, Any]:
        """
        Capture a payment (for manual capture mode)
        
        Args:
            payment_id: Payment ID to capture
            amount: Amount to capture in rupees
            currency: Currency code
            
        Returns:
            Captured payment details
        """
        try:
            amount_paise = int(amount * 100)
            payment = self.client.payment.capture(
                payment_id,
                amount_paise,
                {"currency": currency}
            )
            logger.info(f"Payment captured: {payment_id}")
            return payment
        except Exception as e:
            logger.error(f"Payment capture failed: {str(e)}")
            raise
    
    def create_refund(
        self,
        payment_id: str,
        amount: Optional[float] = None,
        notes: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a refund
        
        Args:
            payment_id: Payment ID to refund
            amount: Amount to refund (None for full refund)
            notes: Additional notes
            
        Returns:
            Refund details
        """
        try:
            refund_data = {}
            
            if amount:
                refund_data["amount"] = int(amount * 100)  # Convert to paise
            if notes:
                refund_data["notes"] = notes
            
            refund = self.client.payment.refund(payment_id, refund_data)
            logger.info(f"Refund created for payment {payment_id}: {refund['id']}")
            return refund
            
        except Exception as e:
            logger.error(f"Refund creation failed: {str(e)}")
            raise
    
    def fetch_refund(self, refund_id: str) -> Dict[str, Any]:
        """Fetch refund details"""
        try:
            refund = self.client.refund.fetch(refund_id)
            return refund
        except Exception as e:
            logger.error(f"Failed to fetch refund {refund_id}: {str(e)}")
            raise
    
    def verify_webhook_signature(
        self,
        webhook_body: str,
        webhook_signature: str
    ) -> bool:
        """
        Verify webhook signature
        
        Args:
            webhook_body: Raw webhook body
            webhook_signature: Signature from X-Razorpay-Signature header
            
        Returns:
            True if signature is valid
        """
        try:
            self.client.utility.verify_webhook_signature(
                webhook_body,
                webhook_signature,
                settings.RAZORPAY_WEBHOOK_SECRET
            )
            return True
        except razorpay.errors.SignatureVerificationError:
            logger.error("Webhook signature verification failed")
            return False


# Singleton instance
razorpay_integration = RazorpayIntegration()
