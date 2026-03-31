from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from enum import Enum

class StockTransactionType(str, Enum):
    GRN = "GRN"
    SALE = "SALE"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    ADJUSTMENT_ADD = "ADJUSTMENT_ADD"
    ADJUSTMENT_SUB = "ADJUSTMENT_SUB"
    DAMAGED = "DAMAGED"
    RETURN = "RETURN"
    INDENT_DISPATCH = "INDENT_DISPATCH"

class StockMovementDirection(str, Enum):
    IN = "IN"
    OUT = "OUT"

class StockMovement(SQLModel, table=True):
    __tablename__ = "stock_movements"
    __table_args__ = {"schema": "inventory"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    stock_id: int = Field(foreign_key="inventory.stocks.id", index=True)
    
    transaction_type: StockTransactionType
    quantity: int = Field(gt=0)
    direction: StockMovementDirection
    
    reference_type: str # ORDER, MANUAL, GRN
    reference_id: Optional[str] = None # ID of source doc
    
    battery_ids: Optional[str] = None # JSON list of battery IDs involved
    notes: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[int] = Field(default=None, foreign_key="core.users.id")
    
    # Relationships
    stock: "Stock" = Relationship(back_populates="movements")
    # user: "User" = Relationship()
