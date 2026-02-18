from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field

class BlacklistedToken(SQLModel, table=True):
    __tablename__ = "blacklisted_tokens"
    __table_args__ = {"schema": "core"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    token: str = Field(index=True, unique=True)
    expires_at: datetime
    blacklisted_at: datetime = Field(default_factory=datetime.utcnow)
