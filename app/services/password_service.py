"""
Password management service — history check (last 5), expiry (90-day), and recording.
"""

import logging
from datetime import datetime, UTC, timedelta
from typing import Optional

from sqlmodel import Session, select
from app.models.password_history import PasswordHistory
from app.models.user import User

logger = logging.getLogger(__name__)

PASSWORD_EXPIRY_DAYS = 90
MAX_HISTORY_ENTRIES = 5


class PasswordService:

    @staticmethod
    def check_password_history(
        db: Session, user_id: int, new_plain_password: str
    ) -> bool:
        """
        Check if new_plain_password matches any of the last 5 stored hashes.
        Returns True if the password is SAFE to use (no reuse), False if reused.
        """
        from app.core.security import verify_password

        entries = db.exec(
            select(PasswordHistory)
            .where(PasswordHistory.user_id == user_id)
            .order_by(PasswordHistory.created_at.desc())
            .limit(MAX_HISTORY_ENTRIES)
        ).all()

        for entry in entries:
            if verify_password(new_plain_password, entry.hashed_password):
                return False  # Reuse detected
        return True  # Safe

    @staticmethod
    def is_password_expired(user: User) -> bool:
        """Check if the user's password is older than PASSWORD_EXPIRY_DAYS."""
        if user.password_changed_at is None:
            # Never changed — treat as expired if account is old enough
            if user.created_at:
                return (datetime.now(UTC) - user.created_at).days > PASSWORD_EXPIRY_DAYS
            return False
        return (datetime.now(UTC) - user.password_changed_at).days > PASSWORD_EXPIRY_DAYS

    @staticmethod
    def record_password_change(
        db: Session, user_id: int, hashed_password: str
    ) -> None:
        """
        Record a password change in history and update user's password_changed_at.
        Keeps only the last MAX_HISTORY_ENTRIES entries.
        """
        # Add new entry
        entry = PasswordHistory(
            user_id=user_id,
            hashed_password=hashed_password,
        )
        db.add(entry)

        # Update user timestamp
        user = db.get(User, user_id)
        if user:
            user.password_changed_at = datetime.now(UTC)
            user.force_password_change = False
            db.add(user)

        # Prune old entries beyond MAX_HISTORY_ENTRIES
        all_entries = db.exec(
            select(PasswordHistory)
            .where(PasswordHistory.user_id == user_id)
            .order_by(PasswordHistory.created_at.desc())
        ).all()

        if len(all_entries) > MAX_HISTORY_ENTRIES:
            for old_entry in all_entries[MAX_HISTORY_ENTRIES:]:
                db.delete(old_entry)

        db.commit()
