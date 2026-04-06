from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, UTC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.user import User

from app.models.stock import Stock

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
    
    capacity: int = Field(default=100)
    is_active: bool = Field(default=True)
    
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Relationships
    branch: Optional["Branch"] = Relationship(back_populates="warehouses")
    manager: Optional["User"] = Relationship()
    stocks: List["Stock"] = Relationship(back_populates="warehouse")
    racks: List["Rack"] = Relationship(back_populates="warehouse")


class Rack(SQLModel, table=True):
    __tablename__ = "warehouse_racks"

    id: Optional[int] = Field(default=None, primary_key=True)
    warehouse_id: int = Field(foreign_key="warehouses.id")
    name: str

    # Relationships
    warehouse: Optional[Warehouse] = Relationship(back_populates="racks")
    shelves: List["Shelf"] = Relationship(back_populates="rack")


class Shelf(SQLModel, table=True):
    __tablename__ = "warehouse_shelves"

    id: Optional[int] = Field(default=None, primary_key=True)
    rack_id: int = Field(foreign_key="warehouse_racks.id")
    name: str
    capacity: int = Field(default=50)

    # Relationships
    rack: Optional[Rack] = Relationship(back_populates="shelves")
    shelf_batteries: List["ShelfBattery"] = Relationship(back_populates="shelf")

    @property
    def battery_ids(self) -> List[str]:
        return [sb.battery_id for sb in self.shelf_batteries]


class ShelfBattery(SQLModel, table=True):
    __tablename__ = "shelf_batteries"

    id: Optional[int] = Field(default=None, primary_key=True)
    shelf_id: int = Field(foreign_key="warehouse_shelves.id", index=True)
    battery_id: str = Field(index=True, unique=True)

    # Relationships
    shelf: Optional[Shelf] = Relationship(back_populates="shelf_batteries")
