from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime, timedelta
from enum import Enum
import secrets

if TYPE_CHECKING:
    from app.models.user import User


class InviteStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


class UserInvite(SQLModel, table=True):
    """Tracks the lifecycle of admin-initiated user invitations."""

    __tablename__ = "user_invites"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Invite details
    email: str = Field(index=True)
    full_name: Optional[str] = None
    role_name: str  # Role assigned to the invited user

    # Tracking
    invited_by: int = Field(foreign_key="users.id", index=True)
    invited_user_id: Optional[int] = Field(default=None, foreign_key="users.id")

    # Status
    status: InviteStatus = Field(default=InviteStatus.PENDING, index=True)
    token: str = Field(default_factory=lambda: secrets.token_urlsafe(32), unique=True, index=True)

    # Expiry
    expires_at: datetime = Field(
        default_factory=lambda: datetime.utcnow() + timedelta(days=7)
    )

    # Lifecycle timestamps
    accepted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[int] = Field(default=None, foreign_key="users.id")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    inviter: Optional["User"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[UserInvite.invited_by]",
            "lazy": "selectin",
        }
    )
