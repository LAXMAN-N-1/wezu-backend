from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
import sqlalchemy as sa

if TYPE_CHECKING:
    from app.models.indent import Indent, IndentItem
    from app.models.battery_catalog import BatteryCatalog

class GRNStatus(str, Enum):
    DRAFT = "DRAFT"
    RECEIVED = "RECEIVED"
    DISCREPANCY = "DISCREPANCY"

class GRN(SQLModel, table=True):
    __tablename__ = "grns"
    __table_args__ = {"schema": "inventory"}

    id: Optional[int] = Field(default=None, primary_key=True)
    indent_id: int = Field(foreign_key="inventory.indents.id", index=True)
    
    dealer_id: int = Field(foreign_key="dealers.dealer_profiles.id")
    warehouse_id: int = Field(foreign_key="logistics.warehouses.id")
    
    status: GRNStatus = Field(default=GRNStatus.DRAFT, sa_column=sa.Column(sa.String))
    
    received_by: int = Field(foreign_key="core.users.id")
    notes: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    indent: Optional["Indent"] = Relationship(back_populates="grns")
    items: List["GRNItem"] = Relationship(back_populates="grn")


class GRNItem(SQLModel, table=True):
    __tablename__ = "grn_items"
    __table_args__ = {"schema": "inventory"}

    id: Optional[int] = Field(default=None, primary_key=True)
    grn_id: int = Field(foreign_key="inventory.grns.id", index=True)
    indent_item_id: int = Field(foreign_key="inventory.indent_items.id", index=True)
    product_id: int = Field(foreign_key="inventory.battery_catalog.id", index=True)
    
    expected_quantity: int = Field(default=0, ge=0)
    received_quantity: int = Field(default=0, ge=0)
    damaged_quantity: int = Field(default=0, ge=0)
    
    # Relationships
    grn: GRN = Relationship(back_populates="items")
    # Using string annotation for circular imports or defer loading
    indent_item: Optional["IndentItem"] = Relationship()
    catalog: Optional["BatteryCatalog"] = Relationship()
