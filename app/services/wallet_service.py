from sqlmodel import Session, select
from app.models.financial import Wallet, Transaction, WalletWithdrawalRequest
from app.models.user import User
from fastapi import HTTPException
from app.services.security_service import SecurityService
from app.models.refund import Refund
from typing import Optional, List

class WalletService:
    @staticmethod
    def get_wallet(db: Session, user_id: int) -> Wallet:
        wallet = db.exec(select(Wallet).where(Wallet.user_id == user_id)).first()
        if not wallet:
            # Create wallet if not exists (auto-provision)
            wallet = Wallet(user_id=user_id, balance=0.0)
            db.add(wallet)
            db.commit()
            db.refresh(wallet)
        return wallet

    @staticmethod
    def add_balance(db: Session, user_id: int, amount: float, description: str = "Deposit") -> Wallet:
        wallet = WalletService.get_wallet(db, user_id)
        wallet.balance += amount
        db.add(wallet)
        
        # Log Transaction
        txn = Transaction(
            wallet_id=wallet.id,
            amount=amount,
            balance_after=wallet.balance,
            type="credit",
            category="deposit",
            status="success",
            description=description
        )
        db.add(txn)
        
        db.commit()
        db.refresh(wallet)
        return wallet

    @staticmethod
    def deduct_balance(db: Session, user_id: int, amount: float, description: str = "Payment") -> Wallet:
        wallet = WalletService.get_wallet(db, user_id)
        if wallet.balance < amount:
            raise HTTPException(status_code=400, detail="Insufficient balance")
            
        wallet.balance -= amount
        db.add(wallet)
        
        # Log Transaction
        txn = Transaction(
            wallet_id=wallet.id,
            amount=-amount,
            balance_after=wallet.balance,
            type="debit",
            category="withdrawal", # or rental_payment
            status="success",
            description=description
        )
        db.add(txn)
        
        db.commit()
        db.refresh(wallet)
        return wallet

    @staticmethod
    def request_withdrawal(db: Session, user_id: int, amount: float, bank_details: dict) -> WalletWithdrawalRequest:
        wallet = WalletService.get_wallet(db, user_id)
        if wallet.balance < amount:
            raise HTTPException(status_code=400, detail="Insufficient balance")

        # Create Request
        req = WalletWithdrawalRequest(
            wallet_id=wallet.id,
            amount=amount,
            bank_details=str(bank_details),
            status="requested"
        )
        db.add(req)
        
        # Deduct balance temporarily or lock it? 
        # For now, we deduct immediately to prevent double spend.
        wallet.balance -= amount
        db.add(wallet)

        txn = Transaction(
            wallet_id=wallet.id,
            amount=-amount,
            balance_after=wallet.balance,
            type="debit",
            category="withdrawal_request",
            status="pending",
            description=f"Withdrawal Request"
        )
        db.add(txn)
        
        db.commit()
        db.refresh(req)

        # Log Security Event for withdrawal
        SecurityService.log_event(
            db,
            event_type="withdrawal_request",
            severity="medium",
            details=f"User {user_id} requested withdrawal of {amount}",
            user_id=user_id
        )

        return req

    @staticmethod
    def apply_cashback(db: Session, user_id: int, amount: float, reason: str = "Cashback"):
        return WalletService.add_balance(db, user_id, amount, description=reason)

    @staticmethod
    def initiate_refund(db: Session, transaction_id: int, amount: Optional[float] = None, reason: str = "Customer Request") -> Optional[Refund]:
        """
        Record a refund request for a specific transaction.
        """
        orig_txn = db.get(Transaction, transaction_id)
        if not orig_txn or orig_txn.type != "credit":
            return None
        
        refund_amount = amount if amount else orig_txn.amount
        
        refund = Refund(
            transaction_id=transaction_id,
            amount=refund_amount,
            reason=reason,
            status="pending"
        )
        db.add(refund)
        db.commit()
        db.refresh(refund)
        return refund

