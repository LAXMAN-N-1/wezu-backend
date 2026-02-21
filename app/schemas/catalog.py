from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime
from app.models.catalog import ProductCategory, ProductStatus

class ProductImageBase(BaseModel):
    image_url: str
    alt_text: Optional[str] = None
    is_primary: bool = False
    display_order: int = 0

class ProductImageResponse(ProductImageBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class ProductVariantBase(BaseModel):
    variant_name: str
    sku: str
    price: Optional[float] = None
    stock_quantity: int = 0
    color: Optional[str] = None
    capacity_mah: Optional[int] = None

class ProductVariantResponse(ProductVariantBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class ProductBase(BaseModel):
    name: str
    description: str
    category: str
    brand: str
    model: str
    sku: str
    price: float
    original_price: Optional[float] = None
    discount_percentage: Optional[float] = None
    capacity_mah: Optional[int] = None
    voltage: Optional[float] = None
    battery_type: Optional[str] = None
    warranty_months: int = 12
    warranty_terms: Optional[str] = None
    stock_quantity: int = 0
    status: str = "ACTIVE"
    is_featured: bool = False

class ProductCreate(ProductBase):
    images: List[ProductImageBase] = []
    variants: List[ProductVariantBase] = []

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    stock_quantity: Optional[int] = None
    status: Optional[str] = None
    is_featured: Optional[bool] = None

class ProductResponse(ProductBase):
    id: int
    images: List[ProductImageResponse] = []
    variants: List[ProductVariantResponse] = []
    average_rating: float = 0.0
    review_count: int = 0
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class OrderReturnRequest(BaseModel):
    reason: str
    description: Optional[str] = None

class CategoryListResponse(BaseModel):
    categories: List[str]
