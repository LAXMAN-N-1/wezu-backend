from __future__ import annotations
import re
from typing import Optional
from sqlmodel import Session, select
from app.models.user import User
from app.repositories.base import BaseRepository

class UserRepository(BaseRepository[User]):
    def __init__(self):
        super().__init__(User)

    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        statement = select(User).where(User.email == email)
        return db.exec(statement).first()

    def get_by_phone(self, db: Session, phone_number: str) -> Optional[User]:
        raw_value = (phone_number or "").strip()
        if not raw_value:
            return None

        digits = re.sub(r"\D", "", raw_value)
        variants: set[str] = {raw_value}
        local_10: str | None = None

        if digits:
            variants.add(digits)
            if len(digits) == 12 and digits.startswith("91"):
                local_10 = digits[2:]
                variants.add(local_10)
                variants.add(f"+91{local_10}")
            elif len(digits) == 10:
                local_10 = digits
                variants.add(f"91{local_10}")
                variants.add(f"+91{local_10}")
            elif len(digits) > 10:
                local_10 = digits[-10:]
                variants.add(local_10)
                variants.add(f"91{local_10}")
                variants.add(f"+91{local_10}")

        # Fast-path exact lookups for common stored formats.
        statement = select(User).where(User.phone_number.in_(list(variants)))
        match = db.exec(statement).first()
        if match:
            return match

        if not local_10:
            return None

        # Fallback for formatted numbers (spaces/dashes).
        candidates = db.exec(
            select(User).where(
                User.phone_number.is_not(None),
                User.phone_number.like(f"%{local_10}"),
            )
        ).all()
        for candidate in candidates:
            candidate_digits = re.sub(r"\D", "", candidate.phone_number or "")
            if candidate_digits == local_10 or candidate_digits == f"91{local_10}":
                return candidate
        return None

user_repository = UserRepository()
