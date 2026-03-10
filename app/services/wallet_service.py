from sqlmodel import Session, select
from app.models.user import User
from app.models.financial import Transaction, TransactionType, TransactionStatus
from app.services.payment_service import PaymentService
from typing import Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class WalletService:
    @staticmethod
    def initiate_topup(db: Session, user_id: int, amount: float) -> Transaction:
        """Create a Razorpay order and a pending transaction record"""
        # 1. Create Razorpay order
        order = PaymentService.create_order(amount)
        
        # 2. Save Transaction
        tx = Transaction(
            user_id=user_id,
            amount=amount,
            transaction_type=TransactionType.WALLET_TOPUP,
            status=TransactionStatus.PENDING,
            payment_gateway_ref=order["id"],
            description=f"Wallet topup of {amount}"
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        return tx

    @staticmethod
    def confirm_topup(
        db: Session, 
        user_id: int, 
        order_id: str, 
        payment_id: str, 
        signature: str
    ) -> Transaction:
        """Verify payment and update user wallet balance"""
        # 1. Verify Signature
        params = {
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature
        }
        if not PaymentService.verify_payment_signature(params):
            raise ValueError("Invalid payment signature")
            
        # 2. Find Transaction
        statement = select(Transaction).where(
            Transaction.payment_gateway_ref == order_id,
            Transaction.user_id == user_id
        )
        tx = db.exec(statement).first()
        if not tx:
            raise ValueError("Transaction not found")
            
        if tx.status == TransactionStatus.SUCCESS:
            return tx
            
        # 3. Update Transaction and Wallet
        tx.status = TransactionStatus.SUCCESS
        tx.payment_gateway_ref = payment_id # Update with final payment ID
        tx.updated_at = datetime.utcnow()
        
        user = db.get(User, user_id)
        user.wallet_balance += tx.amount
        
        db.add(tx)
        db.add(user)
        db.commit()
        db.refresh(tx)
        return tx

    @staticmethod
    def deduct_for_swap(db: Session, user_id: int, amount: float, swap_id: int) -> Transaction:
        """Deduct funds from wallet for a swap"""
        user = db.get(User, user_id)
        if user.wallet_balance < amount:
            raise ValueError("Insufficient wallet balance")
            
        user.wallet_balance -= amount
        
        tx = Transaction(
            user_id=user_id,
            amount=amount,
            transaction_type=TransactionType.SWAP_FEE,
            status=TransactionStatus.SUCCESS,
            description=f"Swap fee for swap #{swap_id}",
            metadata={"swap_id": swap_id}
        )
        
        db.add(tx)
        db.add(user)
        db.commit()
        db.refresh(tx)
        return tx
        
    @staticmethod
    def refund_to_wallet(db: Session, user_id: int, amount: float, reason: str) -> Transaction:
        """Refund funds back to user wallet"""
        user = db.get(User, user_id)
        user.wallet_balance += amount
        
        tx = Transaction(
            user_id=user_id,
            amount=amount,
            transaction_type=TransactionType.REFUND,
            status=TransactionStatus.SUCCESS,
            description=f"Refund: {reason}"
        )
        
        db.add(tx)
        db.add(user)
        db.commit()
        db.refresh(tx)
        return tx
