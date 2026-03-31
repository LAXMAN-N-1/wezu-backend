from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime, UTC

class TwoFactorAuth(SQLModel, table=True):
    __tablename__ = "two_factor_auth"
    # __table_args__ = {"schema": "public"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    secret_key: str
    is_enabled: bool = Field(default=False)
    backup_codes: Optional[str] = None # JSON list of codes (encrypted ideally)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Relationship
    user: "User" = Relationship(back_populates="two_factor_auth")
