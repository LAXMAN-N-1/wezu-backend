from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional

class NotificationLog(SQLModel, table=True):
    __tablename__ = "notification_log"
    id: Optional[int] = Field(default=None, primary_key=True)
    rental_id: int = Field(foreign_key="rentals.id", index=True)
    milestone_hours: int = Field(index=True)
    sent_at: datetime = Field(default_factory=datetime.utcnow)
