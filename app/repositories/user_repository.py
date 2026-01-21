"""
User Repository
Data access layer for User model
"""
from typing import Optional, List
from sqlmodel import Session, select
from app.models.user import User
from app.repositories.base_repository import BaseRepository
from app.schemas.user import UserCreate, UserUpdate


class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    """User-specific data access methods"""
    
    def __init__(self):
        super().__init__(User)
    
    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        """Get user by email"""
        return self.get_by_field(db, "email", email)
    
    def get_by_phone(self, db: Session, phone_number: str) -> Optional[User]:
        """Get user by phone number"""
        return self.get_by_field(db, "phone_number", phone_number)
    
    def get_by_google_id(self, db: Session, google_id: str) -> Optional[User]:
        """Get user by Google ID"""
        return self.get_by_field(db, "google_id", google_id)
    
    def get_by_apple_id(self, db: Session, apple_id: str) -> Optional[User]:
        """Get user by Apple ID"""
        return self.get_by_field(db, "apple_id", apple_id)
    
    def get_active_users(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """Get all active users"""
        query = select(User).where(User.is_active == True).offset(skip).limit(limit)
        return list(db.exec(query).all())
    
    def get_by_kyc_status(
        self,
        db: Session,
        kyc_status: str,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """Get users by KYC status"""
        return self.get_multi_by_field(db, "kyc_status", kyc_status, skip=skip, limit=limit)
    
    def search_users(
        self,
        db: Session,
        search_term: str,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """Search users by name, email, or phone"""
        query = select(User).where(
            (User.full_name.contains(search_term)) |
            (User.email.contains(search_term)) |
            (User.phone_number.contains(search_term))
        ).offset(skip).limit(limit)
        return list(db.exec(query).all())


# Singleton instance
user_repository = UserRepository()
