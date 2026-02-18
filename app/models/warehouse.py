from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.user import User

class Warehouse(SQLModel, table=True):
    __tablename__ = "warehouses"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    code: str = Field(unique=True, index=True)
    
    address: str
    city: str
    state: str
    pincode: str
    
    branch_id: Optional[int] = Field(default=None, foreign_key="branches.id")
    manager_id: Optional[int] = Field(default=None, foreign_key="users.id")
    
    is_active: bool = Field(default=True)
    
    # Merged from logistics.py
    manager_id: Optional[int] = Field(default=None, foreign_key="users.id")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    branch: Optional["Branch"] = Relationship(back_populates="warehouses")
    manager: Optional["User"] = Relationship()
    stocks: List["Stock"] = Relationship(back_populates="warehouse")
