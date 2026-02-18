from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

class Stock(SQLModel, table=True):
    __tablename__ = "stocks"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    warehouse_id: int = Field(foreign_key="warehouses.id", index=True)
    product_id: int = Field(foreign_key="products.id", index=True)
    
    # Stock Quantities
    quantity_on_hand: int = Field(default=0, ge=0)
    quantity_available: int = Field(default=0, ge=0)
    quantity_reserved: int = Field(default=0, ge=0)
    quantity_damaged: int = Field(default=0, ge=0)
    quantity_in_transit: int = Field(default=0, ge=0)
    
    reorder_level: int = Field(default=10, ge=0)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    warehouse: "Warehouse" = Relationship(back_populates="stocks")
    product: "CatalogProduct" = Relationship(back_populates="stocks")
    movements: List["StockMovement"] = Relationship(back_populates="stock")
