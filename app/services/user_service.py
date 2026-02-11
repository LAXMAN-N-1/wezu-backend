from sqlmodel import Session, select
from app.models.user import User
from app.models.address import Address
from app.schemas.user import UserCreate, UserUpdate, AddressCreate, AddressUpdate
from typing import Optional, List
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
