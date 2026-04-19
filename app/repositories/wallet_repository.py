from __future__ import annotations
"""
Wallet Repository
Data access layer for Wallet model
"""
from typing import Optional
from sqlmodel import Session, select
from app.models.financial import Wallet
from app.repositories.base_repository import BaseRepository
from pydantic import BaseModel


class WalletCreate(BaseModel):
    user_id: int
    balance: float = 0.0


class WalletUpdate(BaseModel):
    balance: Optional[float] = None


class WalletRepository(BaseRepository[Wallet, WalletCreate, WalletUpdate]):
    """Wallet-specific data access methods"""
    
    def __init__(self):
        super().__init__(Wallet)
    
    def get_by_user(self, db: Session, user_id: int) -> Optional[Wallet]:
        """Get wallet by user ID"""
        return self.get_by_field(db, "user_id", user_id)
    
    def get_or_create(self, db: Session, user_id: int) -> Wallet:
        """Get wallet or create if doesn't exist"""
        wallet = self.get_by_user(db, user_id)
        if not wallet:
            wallet_data = WalletCreate(user_id=user_id)
            wallet = self.create(db, obj_in=wallet_data)
        return wallet
    
    def add_balance(self, db: Session, user_id: int, amount: float) -> Wallet:
        """Add balance to wallet"""
        wallet = self.get_or_create(db, user_id)
        wallet.balance += amount
        db.add(wallet)
        db.commit()
        db.refresh(wallet)
        return wallet
    
    def deduct_balance(self, db: Session, user_id: int, amount: float) -> Wallet:
        """Deduct balance from wallet"""
        wallet = self.get_or_create(db, user_id)
        if wallet.balance < amount:
            raise ValueError("Insufficient balance")
        wallet.balance -= amount
        db.add(wallet)
        db.commit()
        db.refresh(wallet)
        return wallet


# Singleton instance
wallet_repository = WalletRepository()
