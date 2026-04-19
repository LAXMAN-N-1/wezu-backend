from __future__ import annotations
"""
User state machine service — validates and enforces transitions.

Valid transitions:
    PENDING → VERIFIED
    VERIFIED → ACTIVE
    ACTIVE → SUSPENDED
    ACTIVE → DELETED
    SUSPENDED → ACTIVE
    SUSPENDED → DELETED
"""

import logging
from datetime import datetime
from typing import Optional

from sqlmodel import Session
from app.models.user import User
from app.core.audit import AuditLogger

logger = logging.getLogger(__name__)

from app.models.user import User, UserStatus

VALID_TRANSITIONS = {
    UserStatus.PENDING: [UserStatus.VERIFIED],
    UserStatus.VERIFIED: [UserStatus.ACTIVE],
    UserStatus.ACTIVE: [UserStatus.SUSPENDED, UserStatus.DELETED],
    UserStatus.SUSPENDED: [UserStatus.ACTIVE, UserStatus.DELETED],
}


class UserStateService:

    @staticmethod
    def transition(
        db: Session,
        user_id: int,
        new_status: str,
        admin_user_id: Optional[int] = None,
    ) -> User:
        """
        Validate and apply a status transition for a user.

        Raises:
            ValueError: If the user is not found or the transition is invalid.
        """
        user = db.get(User, user_id)
        if not user:
            raise ValueError("User not found")

        current_status = user.status
        try:
            new_status_enum = UserStatus(new_status.lower())
        except ValueError:
            raise ValueError(f"Invalid status: {new_status}")

        allowed = VALID_TRANSITIONS.get(current_status, [])
        if new_status_enum not in allowed:
            raise ValueError(
                f"Invalid transition: {current_status} → {new_status_enum}. "
                f"Allowed: {allowed}"
            )

        old_status = user.status
        user.status = new_status_enum

        # Sync is_active flag
        if new_status_enum in (UserStatus.ACTIVE, UserStatus.VERIFIED):
            user.is_active = True
        elif new_status_enum in (UserStatus.SUSPENDED, UserStatus.DELETED):
            user.is_active = False

        # If deleted, anonymize
        if new_status == "deleted":
            user.email = f"deleted_{user.id}@removed.local"
            user.phone_number = None
            user.full_name = "Deleted User"

        # Revoke sessions if suspended/deleted
        if new_status in ("suspended", "deleted"):
            try:
                from app.services.auth_service import AuthService
                AuthService.revoke_all_user_sessions(db, user_id)
            except Exception as e:
                logger.warning(f"Could not revoke sessions for user {user_id}: {e}")

        db.add(user)
        db.commit()
        db.refresh(user)

        # Audit
        AuditLogger.log_event(
            db=db,
            user_id=admin_user_id,
            action="USER_STATE_TRANSITION",
            resource_type="USER",
            resource_id=str(user_id),
            target_id=user_id,
            old_value={"status": old_status},
            new_value={"status": new_status},
        )

        logger.info(f"User {user_id} transitioned: {old_status} → {new_status}")
        return user

    @staticmethod
    def get_allowed_transitions(current_status: str) -> list:
        """Return list of valid next statuses for the given current status."""
        return VALID_TRANSITIONS.get(current_status.lower(), [])
