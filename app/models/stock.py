from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.warehouse import Warehouse
    from app.models.battery_catalog import BatteryCatalog
    from app.models.stock_movement import StockMovement

class Stock(SQLModel, table=True):
    __tablename__ = "stocks"
    # __table_args__ = {"schema": "public"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    warehouse_id: int = Field(foreign_key="warehouses.id", index=True)
    product_id: int = Field(foreign_key="battery_catalog.id", index=True)
    
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
    catalog: "BatteryCatalog" = Relationship()
    movements: List["StockMovement"] = Relationship(back_populates="stock")
