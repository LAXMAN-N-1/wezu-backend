from typing import List, Optional, Tuple, Dict
from datetime import datetime, UTC
from sqlmodel import Session, select, func, and_
from app.models.user import User, UserStatus
from app.models.user_history import UserStatusLog
from app.models.address import Address
from app.schemas.user import UserCreate, UserUpdate, AddressCreate, AddressUpdate
from fastapi import HTTPException
from app.core.security import get_password_hash

class UserService:
    @staticmethod
    def get_by_id(db: Session, user_id: int) -> Optional[User]:
        return db.get(User, user_id)

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[User]:
        statement = select(User).where(User.email == email)
        return db.exec(statement).first()

    @staticmethod
    def update_user(db: Session, user: User, user_in: UserUpdate) -> User:
        user_data = user_in.model_dump(exclude_unset=True)
        for key, value in user_data.items():
            setattr(user, key, value)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def delete_account(db: Session, user: User, reason: str):
        """Soft delete the user account and revoke sessions"""
        from datetime import datetime, UTC
        from app.services.auth_service import AuthService
        
        user.is_deleted = True
        user.deletion_reason = reason
        user.deleted_at = datetime.now(UTC)
        user.is_active = False
        db.add(user)
        
        # Revoke all sessions for security
        AuthService.revoke_all_user_sessions(db, user.id)
        
        db.commit()
        return True

    @staticmethod
    def get_login_history(db: Session, user_id: int, page: int = 1, limit: int = 20):
        """Fetch user login sessions from UserSession table"""
        from app.models.session import UserSession
        
        statement = select(UserSession).where(UserSession.user_id == user_id).order_by(UserSession.created_at.desc())
        
        # Paginate
        total_count = db.exec(select(func.count()).select_from(statement.subquery())).one()
        offset = (page - 1) * limit
        sessions = db.exec(statement.offset(offset).limit(limit)).all()
        
        return sessions, total_count

    @staticmethod
    def suspend_user(db: Session, user_id: int, actor_id: int, reason: str, expires_at: Optional[datetime] = None) -> User:
        user = db.get(User, user_id)
        if not user:
            return None
        
        user.status = "suspended"
        user.is_active = False
        db.add(user)
        
        log = UserStatusLog(
            user_id=user_id,
            actor_id=actor_id,
            action_type="suspension",
            reason=reason,
            new_value="suspended",
            expires_at=expires_at
        )
        db.add(log)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def reactivate_user(db: Session, user_id: int, actor_id: int) -> User:
        user = db.get(User, user_id)
        if not user:
            return None
            
        user.status = "active"
        user.is_active = True
        db.add(user)
        
        log = UserStatusLog(
            user_id=user_id,
            actor_id=actor_id,
            action_type="reactivation",
            new_value="active"
        )
        db.add(log)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update_role(db: Session, user_id: int, actor_id: int, role_id: int, reason: str) -> User:
        user = db.get(User, user_id)
        if not user:
            return None
            
        old_role = str(user.role_id) if user.role_id else "None"
        user.role_id = role_id
        db.add(user)
        
        log = UserStatusLog(
            user_id=user_id,
            actor_id=actor_id,
            action_type="role_change",
            old_value=old_role,
            new_value=str(role_id),
            reason=reason
        )
        db.add(log)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_status_history(db: Session, user_id: int) -> List[UserStatusLog]:
        return db.exec(
            select(UserStatusLog)
            .where(UserStatusLog.user_id == user_id)
            .order_by(UserStatusLog.created_at.desc())
        ).all()

    @staticmethod
    def create_address(db: Session, user_id: int, address_in: AddressCreate) -> Address:
        # If this is default, unsettle other defaults
        if address_in.is_default:
            statement = select(Address).where(Address.user_id == user_id, Address.is_default == True)
            existing_defaults = db.exec(statement).all()
            for addr in existing_defaults:
                addr.is_default = False
                db.add(addr)
        
        address = Address(**address_in.dict(), user_id=user_id)
        db.add(address)
        db.commit()
        db.refresh(address)
        return address

    @staticmethod
    def create_user(db: Session, user_in: UserCreate) -> User:
        user_data = user_in.model_dump(exclude={"password"})
        user = User(**user_data)
        user.hashed_password = get_password_hash(user_in.password)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_addresses(db: Session, user_id: int) -> List[Address]:
        statement = select(Address).where(Address.user_id == user_id)
        return db.exec(statement).all()
