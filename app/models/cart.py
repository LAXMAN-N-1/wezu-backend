from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

class CartItem(SQLModel, table=True):
    """Items in a user's shopping cart"""
    __tablename__ = "cart_items"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    product_id: int = Field(foreign_key="products.id")
    variant_id: Optional[int] = Field(default=None, foreign_key="product_variants.id")
    
    quantity: int = Field(default=1, gt=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships (Optional, but good for joins)
    # product: "CatalogProduct" = Relationship()
