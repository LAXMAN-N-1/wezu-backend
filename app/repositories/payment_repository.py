"""
Payment Repository  
Data access layer for Transaction model
"""
from typing import Optional, List
from datetime import datetime, timedelta
from sqlmodel import Session, select, func
from app.models.financial import Transaction
from app.repositories.base_repository import BaseRepository
from pydantic import BaseModel


class PaymentCreate(BaseModel):
    user_id: int
    amount: float
    payment_method: str
    transaction_type: str


class PaymentUpdate(BaseModel):
    status: Optional[str] = None
    razorpay_payment_id: Optional[str] = None


class PaymentRepository(BaseRepository[Transaction, PaymentCreate, PaymentUpdate]):
    """Payment-specific data access methods"""
    
    def __init__(self):
        super().__init__(Transaction)
    
    def get_user_transactions(
        self,
        db: Session,
        user_id: int,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Transaction]:
        """Get all transactions for a user"""
        return self.get_multi_by_field(db, "user_id", user_id, skip=skip, limit=limit)
    
    def get_by_status(
        self,
        db: Session,
        status: str,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Transaction]:
        """Get transactions by status"""
        return self.get_multi_by_field(db, "status", status, skip=skip, limit=limit)
    
    def get_successful_transactions(
        self,
        db: Session,
        user_id: int,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Transaction]:
        """Get successful transactions for a user"""
        query = select(Transaction).where(
            (Transaction.user_id == user_id) &
            (Transaction.status == "completed")
        ).offset(skip).limit(limit)
        return list(db.exec(query).all())
    
    def get_total_spent(self, db: Session, user_id: int) -> float:
        """Get total amount spent by user"""
        result = db.exec(
            select(func.sum(Transaction.amount)).where(
                (Transaction.user_id == user_id) &
                (Transaction.status == "completed") &
                (Transaction.transaction_type == "debit")
            )
        ).one()
        return result or 0.0
    
    def get_recent_transactions(
        self,
        db: Session,
        user_id: int,
        days: int = 30,
        *,
        limit: int = 10
    ) -> List[Transaction]:
        """Get recent transactions"""
        since = datetime.utcnow() - timedelta(days=days)
        query = select(Transaction).where(
            (Transaction.user_id == user_id) &
            (Transaction.created_at >= since)
        ).order_by(Transaction.created_at.desc()).limit(limit)
        return list(db.exec(query).all())


# Singleton instance
payment_repository = PaymentRepository()
