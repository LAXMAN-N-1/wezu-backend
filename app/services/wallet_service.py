from sqlmodel import Session, select
from app.models.financial import Wallet, Transaction, WalletWithdrawalRequest, TransactionType, TransactionStatus
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
            user_id=user_id,
            wallet_id=wallet.id,
            amount=amount,
            transaction_type=TransactionType.WALLET_TOPUP,
            status=TransactionStatus.SUCCESS,
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
            user_id=user_id,
            wallet_id=wallet.id,
            amount=amount,
            transaction_type=TransactionType.RENTAL_PAYMENT,
            status=TransactionStatus.SUCCESS,
            description=description
        )
        db.add(txn)
        
        db.commit()
        db.refresh(wallet)
        return wallet

    @staticmethod
    def transfer_balance(db: Session, sender_id: int, recipient_phone: str, amount: float, note: Optional[str] = None) -> Transaction:
        # Check sender balance
        sender_wallet = WalletService.get_wallet(db, sender_id)
        if sender_wallet.balance < amount:
            raise HTTPException(status_code=400, detail="Insufficient balance")
        
        # Find recipient
        recipient = db.exec(select(User).where(User.phone_number == recipient_phone)).first()
        if not recipient:
            raise HTTPException(status_code=404, detail="Recipient not found")
        
        if recipient.id == sender_id:
            raise HTTPException(status_code=400, detail="Cannot transfer to yourself")
        
        # Deduct from sender
        sender_wallet.balance -= amount
        db.add(sender_wallet)
        
        # Add to recipient
        recipient_wallet = WalletService.get_wallet(db, recipient.id)
        recipient_wallet.balance += amount
        db.add(recipient_wallet)
        
        # Create transaction records
        sender_txn = Transaction(
            user_id=sender_id,
            wallet_id=sender_wallet.id,
            amount=amount,
            transaction_type="transfer_out", # Should probably add to TransactionType Enum
            status=TransactionStatus.SUCCESS,
            description=f"Transfer to {recipient.phone_number}. {note or ''}"
        )
        recipient_txn = Transaction(
            user_id=recipient.id,
            wallet_id=recipient_wallet.id,
            amount=amount,
            transaction_type="transfer_in",
            status=TransactionStatus.SUCCESS,
            description=f"Transfer from {User.phone_number}. {note or ''}" # Wait, need sender phone
        )
        # Get sender phone
        sender = db.get(User, sender_id)
        recipient_txn.description = f"Transfer from {sender.phone_number}. {note or ''}"
        
        db.add(sender_txn)
        db.add(recipient_txn)
        db.commit()
        db.refresh(sender_txn)
        return sender_txn

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
        
        # Deduct balance immediately
        wallet.balance -= amount
        db.add(wallet)

        txn = Transaction(
            user_id=user_id,
            wallet_id=wallet.id,
            amount=amount,
            transaction_type=TransactionType.WITHDRAWAL,
            status=TransactionStatus.PENDING,
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
        wallet = WalletService.get_wallet(db, user_id)
        wallet.balance += amount
        db.add(wallet)
        
        txn = Transaction(
            user_id=user_id,
            wallet_id=wallet.id,
            amount=amount,
            transaction_type="cashback",
            status=TransactionStatus.SUCCESS,
            description=reason
        )
        db.add(txn)
        db.commit()
        return wallet

    @staticmethod
    def get_cashback_history(db: Session, user_id: int) -> List[Transaction]:
        return db.exec(
            select(Transaction).where(
                Transaction.user_id == user_id,
                Transaction.transaction_type == "cashback"
            )
        ).all()

    @staticmethod
    def initiate_refund(db: Session, transaction_id: int, amount: Optional[float] = None, reason: str = "Customer Request") -> Optional[Refund]:
        """
        Record a refund request for a specific transaction.
        """
        orig_txn = db.get(Transaction, transaction_id)
        if not orig_txn or orig_txn.transaction_type not in ["rental_payment", "wallet_topup"]:
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

