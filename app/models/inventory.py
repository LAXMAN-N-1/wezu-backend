from datetime import datetime
from typing import Optional
from sqlalchemy import UniqueConstraint
from sqlmodel import SQLModel, Field

class InventoryTransfer(SQLModel, table=True):
    __tablename__ = "inventory_transfers"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Source
    from_location_type: str = Field(default="warehouse") # warehouse, station
    from_location_id: int = Field(index=True)
    
    # Destination
    to_location_type: str = Field(default="station") # warehouse, station
    to_location_id: int = Field(index=True)
    
    # Mechanism
    driver_id: Optional[int] = Field(default=None, foreign_key="driver_profiles.id")
    
    # Denormalized JSON mirror for API compatibility. Source of truth is inventory_transfer_items.
    items: str = Field(default="[]") 
    
    # Status
    status: str = Field(default="pending") # pending, in_transit, completed, cancelled
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class InventoryTransferItem(SQLModel, table=True):
    __tablename__ = "inventory_transfer_items"
    __table_args__ = (
        UniqueConstraint("transfer_id", "battery_id", name="uq_inventory_transfer_item"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    transfer_id: int = Field(foreign_key="inventory_transfers.id", index=True)
    battery_id: str = Field(index=True)
    battery_pk: Optional[int] = Field(default=None, foreign_key="batteries.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StockDiscrepancy(SQLModel, table=True):
    __tablename__ = "stock_discrepancies"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    location_type: str # warehouse, station
    location_id: int
    
    # Discrepancy details
    system_count: int
    physical_count: int
    
    # JSON list of battery IDs that were expected vs found
    missing_items: Optional[str] = None
    extra_items: Optional[str] = None
    
    notes: Optional[str] = None
    status: str = Field(default="open") # open, resolved
    
    reported_by_id: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
