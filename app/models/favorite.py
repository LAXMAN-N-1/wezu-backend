from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime

class Favorite(SQLModel, table=True):
    __tablename__ = "favorites"
    # __table_args__ = {"schema": "public", "extend_existing": True}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    station_id: int = Field(foreign_key="stations.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    user: Optional["User"] = Relationship()
    station: Optional["Station"] = Relationship()
