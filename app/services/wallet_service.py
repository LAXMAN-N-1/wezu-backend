from sqlmodel import Session, select
from app.models.user import User
from app.models.financial import Transaction, TransactionType, TransactionStatus, Wallet
from app.services.payment_service import PaymentService
from app.services.financial_service import FinancialService
from app.repositories.wallet_repository import wallet_repository
from typing import Optional, List
from datetime import datetime, UTC
import logging

logger = logging.getLogger(__name__)

class WalletService:
    @staticmethod
    def get_wallet(db: Session, user_id: int) -> Wallet:
        """Get or create user wallet"""
        return wallet_repository.get_or_create(db, user_id)

    @staticmethod
    def initiate_topup(db: Session, user_id: int, amount: float) -> Transaction:
        """Create a Razorpay order and a pending transaction record"""
        # Ensure wallet exists
        wallet = wallet_repository.get_or_create(db, user_id)
        # 1. Create Razorpay order
        order = PaymentService.create_order(amount)
        
        # 2. Save Transaction
        tx = Transaction(
            user_id=user_id,
            wallet_id=wallet.id,
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
        wallet = wallet_repository.get_or_create(db, user_id)
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
        tx.updated_at = datetime.now(UTC)
        
        # Calculate Taxes for Audit (18% GST inclusive)
        tx.subtotal = round(tx.amount / 1.18, 2)
        tx.tax_amount = round(tx.amount - tx.subtotal, 2)
        
        wallet.balance += tx.amount
        tx.wallet_id = wallet.id

        db.add(tx)
        db.add(wallet)
        db.commit()
        db.refresh(tx)
        
        # Auto-generate Invoice
        try:
            FinancialService.create_invoice(tx.id, user_id)
        except Exception as e:
            logger.error(f"Failed to auto-generate invoice for topup {tx.id}: {e}")
            
        return tx

    @staticmethod
    def deduct_for_swap(db: Session, user_id: int, amount: float, swap_id: int) -> Transaction:
        """Deduct funds from wallet for a swap"""
        wallet = wallet_repository.get_or_create(db, user_id)
        if wallet.balance < amount:
            raise ValueError("Insufficient wallet balance")
            
        wallet.balance -= amount
        
        subtotal = round(amount / 1.18, 2)
        tax = round(amount - subtotal, 2)
        
        tx = Transaction(
            user_id=user_id,
            wallet_id=wallet.id,
            amount=amount,
            subtotal=subtotal,
            tax_amount=tax,
            transaction_type=TransactionType.SWAP_FEE,
            status=TransactionStatus.SUCCESS,
            description=f"Swap fee for swap #{swap_id}",
            metadata={"swap_id": swap_id}
        )
        
        db.add(tx)
        db.add(wallet)
        db.commit()
        db.refresh(tx)
        
        # Auto-generate Invoice
        try:
            FinancialService.create_invoice(tx.id, user_id)
        except Exception as e:
            logger.error(f"Failed to auto-generate invoice for swap {tx.id}: {e}")
            
        return tx
        
    @staticmethod
    def refund_to_wallet(db: Session, user_id: int, amount: float, reason: str) -> Transaction:
        """Refund funds back to user wallet"""
        wallet = wallet_repository.get_or_create(db, user_id)
        wallet.balance += amount
        
        subtotal = round(amount / 1.18, 2)
        tax = round(amount - subtotal, 2)
        
        tx = Transaction(
            user_id=user_id,
            wallet_id=wallet.id,
            amount=amount,
            subtotal=subtotal,
            tax_amount=tax,
            transaction_type=TransactionType.REFUND,
            status=TransactionStatus.SUCCESS,
            description=f"Refund: {reason}"
        )
        
        db.add(tx)
        db.add(wallet)
        db.commit()
        db.refresh(tx)
        
        # Auto-generate Invoice (Refund Receipt)
        try:
            FinancialService.create_invoice(tx.id, user_id)
        except Exception as e:
            logger.error(f"Failed to auto-generate invoice for refund {tx.id}: {e}")
            
        return tx

    @staticmethod
    def add_balance(db: Session, user_id: int, amount: float, description: str) -> Transaction:
        """Add balance to wallet (e.g. from webhook or manual admin action)"""
        wallet = WalletService.get_wallet(db, user_id)
        wallet.balance += amount
        
        subtotal = round(amount / 1.18, 2)
        tax = round(amount - subtotal, 2)
        
        tx = Transaction(
            user_id=user_id,
            wallet_id=wallet.id,
            amount=amount,
            subtotal=subtotal,
            tax_amount=tax,
            transaction_type=TransactionType.WALLET_TOPUP,
            status=TransactionStatus.SUCCESS,
            description=description
        )
        
        db.add(tx)
        db.add(wallet)
        db.commit()
        db.refresh(tx)
        
        # Auto-generate Invoice
        try:
            FinancialService.create_invoice(tx.id, user_id)
        except Exception as e:
            logger.error(f"Failed to auto-generate invoice for manual credit {tx.id}: {e}")
            
        return tx

    @staticmethod
    def get_cashback_history(db: Session, user_id: int) -> List[Transaction]:
        """Get cashback transaction history"""
        from sqlalchemy import or_
        statement = select(Transaction).where(
            Transaction.user_id == user_id,
            or_(
                Transaction.transaction_type == TransactionType.CASHBACK,
                Transaction.description.ilike("%cashback%")
            )
        )
        return db.exec(statement).all()

    @staticmethod
    def transfer_balance(db: Session, sender_id: int, recipient_phone: str, amount: float, note: Optional[str] = None) -> Transaction:
        """Transfer money to another user by phone number"""
        sender_wallet = WalletService.get_wallet(db, sender_id)
        if sender_wallet.balance < amount:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Insufficient balance")
            
        recipient = db.exec(select(User).where(User.phone_number == recipient_phone)).first()
        if not recipient:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Recipient not found")
            
        recipient_wallet = WalletService.get_wallet(db, recipient.id)
        
        # Deduct from sender
        sender_wallet.balance -= amount
        subtotal = round(abs(amount) / 1.18, 2)
        tax = round(abs(amount) - subtotal, 2)
        
        sender_tx = Transaction(
            user_id=sender_id,
            wallet_id=sender_wallet.id,
            amount=-amount,
            subtotal=subtotal,
            tax_amount=tax,
            transaction_type=TransactionType.TRANSFER,
            status=TransactionStatus.SUCCESS,
            description=f"Transfer to {recipient_phone}: {note or ''}"
        )
        
        # Add to recipient
        recipient_wallet.balance += amount
        recipient_tx = Transaction(
            user_id=recipient.id,
            wallet_id=recipient_wallet.id,
            amount=amount,
            subtotal=subtotal,
            tax_amount=tax,
            transaction_type=TransactionType.TRANSFER,
            status=TransactionStatus.SUCCESS,
            description=f"Received from {sender_id}: {note or ''}"
        )
        
        db.add(sender_wallet)
        db.add(recipient_wallet)
        db.add(sender_tx)
        db.add(recipient_tx)
        db.commit()
        db.refresh(sender_tx)
        
        # Auto-generate Invoices for both parties
        try:
            FinancialService.create_invoice(sender_tx.id, sender_id)
            FinancialService.create_invoice(recipient_tx.id, recipient.id)
        except Exception as e:
            logger.error(f"Failed to auto-generate invoices for transfer {sender_tx.id}: {e}")
            
        return sender_tx

    @staticmethod
    def request_withdrawal(db: Session, user_id: int, amount: float, bank_details: dict) -> "WalletWithdrawalRequest":
        """Request withdrawal to bank account"""
        wallet = WalletService.get_wallet(db, user_id)
        if wallet.balance < amount:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Insufficient balance for withdrawal")
            
        wallet.balance -= amount
        
        from app.models.financial import WalletWithdrawalRequest
        import json
        wr = WalletWithdrawalRequest(
            wallet_id=wallet.id,
            amount=amount,
            status="requested",
            bank_details=json.dumps(bank_details)
        )
        
        subtotal = round(abs(amount) / 1.18, 2)
        tax = round(abs(amount) - subtotal, 2)
        
        tx = Transaction(
            user_id=user_id,
            wallet_id=wallet.id,
            amount=-amount,
            subtotal=subtotal,
            tax_amount=tax,
            transaction_type=TransactionType.WITHDRAWAL,
            status=TransactionStatus.SUCCESS,
            description=f"Withdrawal request: {amount}"
        )
        
        db.add(wallet)
        db.add(wr)
        db.add(tx)
        db.commit()
        db.refresh(wr)
        return wr
