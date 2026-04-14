from __future__ import annotations

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.user import User


class PasskeyCredential(SQLModel, table=True):
    """WebAuthn passkey credentials registered by users."""

    __tablename__ = "passkey_credentials"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    credential_id: str = Field(index=True, unique=True)
    public_key: str
    sign_count: int = Field(default=0)
    aaguid: Optional[str] = Field(default=None, index=True)
    transports_json: Optional[str] = None
    credential_device_type: Optional[str] = None
    credential_backed_up: bool = Field(default=False)
    passkey_name: Optional[str] = None
    last_used_at: Optional[datetime] = Field(default=None, index=True)
    is_active: bool = Field(default=True, index=True)
    revoked_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Keep relationship target concrete under postponed annotations to avoid
    # SQLAlchemy interpreting it as "Optional['User']" during mapper setup.
    user: User = Relationship()


class PasskeyChallenge(SQLModel, table=True):
    """One-time challenge records for registration/authentication ceremonies."""

    __tablename__ = "passkey_challenges"

    id: Optional[int] = Field(default=None, primary_key=True)
    challenge_id: str = Field(index=True, unique=True)
    challenge: str = Field(index=True)
    ceremony: str = Field(index=True)  # registration | authentication
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    expires_at: datetime = Field(index=True)
    used_at: Optional[datetime] = Field(default=None, index=True)
