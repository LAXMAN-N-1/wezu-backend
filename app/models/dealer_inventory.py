from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from app.models.dealer import DealerProfile
    from app.models.battery_catalog import BatteryCatalog
class DealerInventory(SQLModel, table=True):
    __tablename__ = "dealer_inventories"
    __table_args__ = {"schema": "dealers"}
    """Track dealer-specific battery inventory"""
    id: Optional[int] = Field(default=None, primary_key=True)
    dealer_id: int = Field(foreign_key="dealers.dealer_profiles.id")
    product_id: int = Field(foreign_key="inventory.battery_catalog.id", index=True)
    battery_model: Optional[str] = None  # Legacy, or cached model name
    
    quantity_available: int = Field(default=0)
    quantity_reserved: int = Field(default=0)  # Reserved for pending orders
    quantity_damaged: int = Field(default=0)
    
    reorder_level: int = Field(default=10)  # Alert when stock falls below this
    max_capacity: int = Field(default=100)
    
    last_restocked_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    dealer: "DealerProfile" = Relationship()
    catalog: Optional["BatteryCatalog"] = Relationship()
    transactions: list["InventoryTransaction"] = Relationship(back_populates="inventory")

class InventoryTransaction(SQLModel, table=True):
    __tablename__ = "inventory_transactions"
    __table_args__ = {"schema": "dealers"}
    """Log all inventory movements"""
    id: Optional[int] = Field(default=None, primary_key=True)
    inventory_id: int = Field(foreign_key="dealers.dealer_inventories.id")
    
    transaction_type: str  # RECEIVED, SOLD, RETURNED, DAMAGED, ADJUSTED
    quantity: int
    reference_type: Optional[str] = None  # ORDER, RENTAL, PURCHASE, MANUAL
    reference_id: Optional[int] = None  # ID of the related order/rental
    
    notes: Optional[str] = None
    performed_by: Optional[int] = Field(default=None, foreign_key="core.users.id")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    inventory: DealerInventory = Relationship(back_populates="transactions")
