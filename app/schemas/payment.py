from pydantic import BaseModel
from typing import Optional

class PaymentOrderRequest(BaseModel):
    amount: float # in INR
    currency: str = "INR"

class PaymentOrderResponse(BaseModel):
    order_id: str
    amount: float
    currency: str
    key_id: str

class PaymentVerifyRequest(BaseModel):
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str
