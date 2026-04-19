from __future__ import annotations
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
        statement = select(User).where(User.phone_number == phone_number)
        return db.exec(statement).first()

user_repository = UserRepository()
