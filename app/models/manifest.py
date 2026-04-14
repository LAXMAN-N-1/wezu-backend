from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import UniqueConstraint
from app.models.battery import Battery

class Manifest(SQLModel, table=True):
    __tablename__ = "manifests"
    
    id: str = Field(primary_key=True) # MAN-001
    source: str # Factory A
    date: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="In Transit") # In Transit, Received, Processed
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    items: List["ManifestItem"] = Relationship(back_populates="manifest")

class ManifestItem(SQLModel, table=True):
    __tablename__ = "manifest_items"
    __table_args__ = (
        UniqueConstraint("manifest_id", "battery_id", name="uq_manifest_items_manifest_battery"),
    )
    
    id: Optional[int] = Field(default=None, primary_key=True)
    manifest_id: str = Field(foreign_key="manifests.id")
    
    battery_id: str # BAT-1001 (This serves as reference, actual FK ID is below)
    battery_table_id: Optional[int] = Field(default=None, foreign_key="batteries.id")
    
    serial_number: Optional[str] = None
    type: str # Li-ion 48V
    status: str = Field(default="pending") # pending, scanned, missing, damaged, extra
    
    # Relationships
    manifest: Optional[Manifest] = Relationship(back_populates="items")
    battery: Optional["Battery"] = Relationship()
