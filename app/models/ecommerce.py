from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, UTC

class EcommerceProduct(SQLModel, table=True):
    __tablename__ = "ecommerce_products"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    sku: str = Field(unique=True, index=True)
    description: Optional[str] = None
    price: float
    stock_quantity: int = Field(default=0)
    category: str = Field(default="battery") # battery, charger, accessory
    image_url: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Relationships
    order_items: List["EcommerceOrderItem"] = Relationship(back_populates="product")

class EcommerceOrder(SQLModel, table=True):
    __tablename__ = "ecommerce_orders"
    # __table_args__ = {"schema": "public"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    total_amount: float
    status: str = Field(default="pending") # pending, paid, shipped, delivered, cancelled
    shipping_address_id: Optional[int] = Field(default=None, foreign_key="addresses.id")
    payment_transaction_id: Optional[int] = Field(default=None, foreign_key="payment_transactions.id") # Link to payment_transactions if needed
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Relationships
    user: "User" = Relationship()
    items: List["EcommerceOrderItem"] = Relationship(back_populates="order")
    delivery: Optional["DeliveryAssignment"] = Relationship(back_populates="order")

class EcommerceOrderItem(SQLModel, table=True):
    __tablename__ = "ecommerce_order_items"
    # __table_args__ = {"schema": "public"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="ecommerce_orders.id")
    product_id: int = Field(foreign_key="ecommerce_products.id")
    quantity: int = Field(default=1)
    unit_price: float
    total_price: float
    
    # Relationships
    order: EcommerceOrder = Relationship(back_populates="items")
    product: EcommerceProduct = Relationship(back_populates="order_items")
