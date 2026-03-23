from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime
import uuid

class StationStockConfig(SQLModel, table=True):
    __tablename__ = "station_stock_configs" # type: ignore
    # __table_args__ = {"schema": "public"}

    id: Optional[int] = Field(default=None, primary_key=True)
    station_id: int = Field(foreign_key="stations.id", unique=True, index=True)
    max_capacity: int = Field(default=50)
    reorder_point: int = Field(default=10)
    reorder_quantity: int = Field(default=20)
    manager_email: Optional[str] = None
    manager_phone: Optional[str] = None

    updated_by: Optional[int] = Field(foreign_key="users.id", nullable=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ReorderRequest(SQLModel, table=True):
    __tablename__ = "reorder_requests" # type: ignore
    # __table_args__ = {"schema": "public"}

    id: int = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    station_id: int = Field(foreign_key="stations.id", index=True)
    requested_quantity: int
    reason: Optional[str] = None
    status: str = Field(default="pending") # pending, approved, fulfilled, cancelled
    
    created_by: Optional[int] = Field(foreign_key="users.id", nullable=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    fulfilled_at: Optional[datetime] = None

class StockAlertDismissal(SQLModel, table=True):
    __tablename__ = "stock_alert_dismissals" # type: ignore
    # __table_args__ = {"schema": "public"}

    id: Optional[int] = Field(default=None, primary_key=True)
    station_id: int = Field(foreign_key="stations.id", index=True)
    reason: str
    dismissed_by: int = Field(foreign_key="users.id")
    dismissed_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True) # Automatically clears when stock goes back to normal
