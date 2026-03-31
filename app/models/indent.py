from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
import sqlalchemy as sa

if TYPE_CHECKING:
    from app.models.dealer import DealerProfile
    from app.models.warehouse import Warehouse
    from app.models.battery_catalog import BatteryCatalog
    from app.models.grn import GRN

class IndentStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DISPATCHED = "DISPATCHED"
    PARTIAL_FULFILLED = "PARTIAL_FULFILLED"
    FULFILLED = "FULFILLED"

class Indent(SQLModel, table=True):
    __tablename__ = "indents"
    __table_args__ = {"schema": "inventory"}

    id: Optional[int] = Field(default=None, primary_key=True)
    dealer_id: int = Field(foreign_key="dealers.dealer_profiles.id", index=True)
    warehouse_id: int = Field(foreign_key="logistics.warehouses.id", index=True)
    
    status: IndentStatus = Field(default=IndentStatus.PENDING, sa_column=sa.Column(sa.String))
    
    notes: Optional[str] = None
    manager_notes: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    dealer: Optional["DealerProfile"] = Relationship()
    warehouse: Optional["Warehouse"] = Relationship()
    items: List["IndentItem"] = Relationship(back_populates="indent")
    grns: List["GRN"] = Relationship(back_populates="indent")


class IndentItem(SQLModel, table=True):
    __tablename__ = "indent_items"
    __table_args__ = {"schema": "inventory"}

    id: Optional[int] = Field(default=None, primary_key=True)
    indent_id: int = Field(foreign_key="inventory.indents.id", index=True)
    product_id: int = Field(foreign_key="inventory.battery_catalog.id", index=True)
    
    requested_quantity: int = Field(default=0, ge=1)
    approved_quantity: int = Field(default=0, ge=0)
    dispatched_quantity: int = Field(default=0, ge=0)
    received_quantity: int = Field(default=0, ge=0)
    
    # Relationships
    indent: Indent = Relationship(back_populates="items")
    catalog: Optional["BatteryCatalog"] = Relationship()
