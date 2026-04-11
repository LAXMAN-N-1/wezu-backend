from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, UTC


class PasswordHistory(SQLModel, table=True):
    """Stores hashed password entries for reuse prevention (last 5)."""
    __tablename__ = "password_history"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
