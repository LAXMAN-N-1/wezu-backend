from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.user import User
    from app.models.organization import Organization
    from app.models.warehouse import Warehouse
from datetime import datetime

class Branch(SQLModel, table=True):
    __tablename__ = "branches"
    # __table_args__ = {"schema": "public"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    code: str = Field(unique=True, index=True) # e.g., "DEL-01"
    
    address: str
    city: str
    state: str
    pincode: str
    
    contact_number: Optional[str] = None
    manager_id: Optional[int] = Field(default=None, foreign_key="users.id")
    organization_id: Optional[int] = Field(default=None, foreign_key="organizations.id")
    
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    manager: Optional["User"] = Relationship()
    organization: Optional["Organization"] = Relationship(back_populates="branches")
    warehouses: List["Warehouse"] = Relationship(back_populates="branch")
