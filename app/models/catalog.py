"""
Product Catalog Models
E-commerce product catalog for battery purchase
"""
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from enum import Enum

class ProductCategory(str, Enum):
    BATTERY = "BATTERY"
    CHARGER = "CHARGER"
    ACCESSORY = "ACCESSORY"
    BUNDLE = "BUNDLE"

class ProductStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    DISCONTINUED = "DISCONTINUED"

class CatalogProduct(SQLModel, table=True):
    """Product catalog"""
    __tablename__ = "products"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Basic Info
    name: str = Field(index=True)
    description: str
    category: str = Field(index=True)  # BATTERY, CHARGER, ACCESSORY
    brand: str = Field(index=True)
    model: str
    sku: str = Field(unique=True, index=True)
    
    # Pricing
    price: float = Field(gt=0)
    original_price: Optional[float] = None  # For discounts
    discount_percentage: Optional[float] = Field(None, ge=0, le=100)
    
    # Battery Specifications (if category=BATTERY)
    capacity_mah: Optional[int] = None
    voltage: Optional[float] = None
    battery_type: Optional[str] = None  # Li-ion, LiFePO4, etc.
    
    # Warranty
    warranty_months: int = Field(default=12)
    warranty_terms: Optional[str] = None
    
    # Inventory
    stock_quantity: int = Field(default=0, ge=0)
    low_stock_threshold: int = Field(default=10)
    
    # Status
    status: str = Field(default="ACTIVE")
    is_featured: bool = Field(default=False)
    is_bestseller: bool = Field(default=False)
    
    # SEO & Marketing
    tags: Optional[str] = None  # Comma-separated
    meta_description: Optional[str] = None
    
    # Ratings
    average_rating: float = Field(default=0.0, ge=0, le=5)
    review_count: int = Field(default=0, ge=0)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    images: List["CatalogProductImage"] = Relationship(back_populates="product")
    variants: List["CatalogProductVariant"] = Relationship(back_populates="product")
    stocks: List["Stock"] = Relationship(back_populates="product")

class CatalogProductImage(SQLModel, table=True):
    """Product images"""
    __tablename__ = "product_images"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="products.id", index=True)
    image_url: str
    alt_text: Optional[str] = None
    display_order: int = Field(default=0)
    is_primary: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationship
    product: Optional[CatalogProduct] = Relationship(back_populates="images")

class CatalogProductVariant(SQLModel, table=True):
    """Product variants (color, size, etc.)"""
    __tablename__ = "product_variants"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="products.id", index=True)
    
    # Variant details
    variant_name: str  # e.g., "Red - 5000mAh"
    sku: str = Field(unique=True, index=True)
    
    # Variant-specific pricing
    price: Optional[float] = None  # If different from base product
    
    # Variant-specific inventory
    stock_quantity: int = Field(default=0, ge=0)
    
    # Variant attributes
    color: Optional[str] = None
    size: Optional[str] = None
    capacity_mah: Optional[int] = None
    
    # Status
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationship
    product: Optional[CatalogProduct] = Relationship(back_populates="variants")

class CatalogOrder(SQLModel, table=True):
    """Customer orders"""
    __tablename__ = "orders"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    order_number: str = Field(unique=True, index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    
    # Order details
    subtotal: float
    tax_amount: float = Field(default=0)
    shipping_fee: float = Field(default=0)
    discount_amount: float = Field(default=0)
    total_amount: float
    
    # Shipping
    shipping_address: str
    shipping_city: str
    shipping_state: str
    shipping_pincode: str
    shipping_phone: str
    
    # Payment
    payment_method: str  # UPI, CARD, WALLET, etc.
    payment_status: str = Field(default="PENDING")  # PENDING, PAID, FAILED, REFUNDED
    payment_id: Optional[str] = None  # Razorpay payment ID
    
    # Order status
    status: str = Field(default="PENDING", index=True)  # PENDING, CONFIRMED, SHIPPED, DELIVERED, CANCELLED
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    confirmed_at: Optional[datetime] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    
    # Notes
    customer_notes: Optional[str] = None
    admin_notes: Optional[str] = None
    
    # Relationships
    items: List["CatalogOrderItem"] = Relationship(back_populates="order")

class CatalogOrderItem(SQLModel, table=True):
    """Order line items"""
    __tablename__ = "order_items"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id", index=True)
    product_id: int = Field(foreign_key="products.id")
    variant_id: Optional[int] = Field(None, foreign_key="product_variants.id")
    
    # Item details
    product_name: str  # Snapshot at time of order
    sku: str
    quantity: int = Field(gt=0)
    unit_price: float
    total_price: float
    
    # Warranty
    warranty_months: int
    warranty_start_date: Optional[datetime] = None
    
    # Relationship
    order: Optional[CatalogOrder] = Relationship(back_populates="items")

class DeliveryTracking(SQLModel, table=True):
    """Delivery tracking for orders"""
    __tablename__ = "delivery_tracking"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id", index=True, unique=True)
    
    # Tracking details
    tracking_number: str = Field(unique=True, index=True)
    courier_name: str
    courier_contact: Optional[str] = None
    
    # Estimated delivery
    estimated_delivery_date: Optional[datetime] = None
    actual_delivery_date: Optional[datetime] = None
    
    # Current status
    current_status: str = Field(default="PENDING")  # PENDING, PICKED_UP, IN_TRANSIT, OUT_FOR_DELIVERY, DELIVERED
    current_location: Optional[str] = None
    
    # Delivery proof
    delivery_image_url: Optional[str] = None
    recipient_name: Optional[str] = None
    recipient_signature: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class DeliveryEvent(SQLModel, table=True):
    """Delivery status history"""
    __tablename__ = "delivery_events"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    tracking_id: int = Field(foreign_key="delivery_tracking.id", index=True)
    
    # Event details
    status: str
    location: Optional[str] = None
    description: str
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    
    # Additional info
    event_metadata: Optional[str] = None  # JSON string
