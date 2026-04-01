"""
E-commerce and cart schemas
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


# ── Cart ─────────────────────────────────────────────────

class CartItemCreate(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    quantity: int = 1

class CartItemUpdate(BaseModel):
    quantity: int

class CartItemResponse(BaseModel):
    id: int
    user_id: int
    product_id: int
    variant_id: Optional[int] = None
    quantity: int
    unit_price: float = 0.0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CartResponse(BaseModel):
    items: List[CartItemResponse]
    total_items: int = 0
    subtotal: float = 0.0


# ── Ecommerce ────────────────────────────────────────────

class EcommerceProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: float
    category: Optional[str] = None
    image_url: Optional[str] = None
    is_available: bool = True
    stock_quantity: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class EcommerceOrderCreate(BaseModel):
    items: List[CartItemCreate]
    delivery_address_id: Optional[int] = None
    payment_method: str = "upi"

class EcommerceOrderResponse(BaseModel):
    id: int
    user_id: int
    order_number: Optional[str] = None
    total_amount: float
    status: str = "pending"
    payment_status: str = "pending"
    delivery_address_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class EcommerceOrderItemResponse(BaseModel):
    id: int
    order_id: int
    product_id: int
    variant_id: Optional[int] = None
    quantity: int
    unit_price: float
    total_price: float

    model_config = ConfigDict(from_attributes=True)
