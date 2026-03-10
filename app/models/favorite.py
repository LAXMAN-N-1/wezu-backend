from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime

class Favorite(SQLModel, table=True):
    __table_args__ = {"schema": "core"}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="core.users.id")
    station_id: int = Field(foreign_key="stations.stations.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    user: "User" = Relationship()
    station: "Station" = Relationship()
