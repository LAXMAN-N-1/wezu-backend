from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.financial import Transaction, Wallet, WalletWithdrawalRequest
from app.models.refund import Refund
from app.services.security_service import SecurityService
from app.services.workflow_automation_service import WorkflowAutomationService


class WalletService:
    @staticmethod
    def _to_money(value: float | int | str | Decimal) -> Decimal:
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid amount") from exc
        return amount.quantize(Decimal("0.01"))

    @staticmethod
    def get_wallet(
        db: Session,
        user_id: int,
        for_update: bool = False,
        auto_commit_if_created: bool = True,
    ) -> Wallet:
        query = select(Wallet).where(Wallet.user_id == user_id)
        if for_update:
            query = query.with_for_update()

        wallet = db.exec(query).first()
        if wallet:
            return wallet

        wallet = Wallet(user_id=user_id, balance=Decimal("0.00"))
        db.add(wallet)
        db.flush()
        if auto_commit_if_created:
            db.commit()
        db.refresh(wallet)
        if for_update and auto_commit_if_created:
            wallet = db.exec(select(Wallet).where(Wallet.user_id == user_id).with_for_update()).first()
        return wallet

    @staticmethod
    def add_balance(
        db: Session,
        user_id: int,
        amount: float | Decimal,
        description: str = "Deposit",
        gateway_payment_id: Optional[str] = None,
        *,
        category: str = "deposit",
        reference_type: Optional[str] = None,
        reference_id: Optional[str] = None,
    ) -> Wallet:
        amount_value = WalletService._to_money(amount)
        if amount_value <= 0:
            raise HTTPException(status_code=400, detail="Amount must be greater than zero")

        wallet = WalletService.get_wallet(
            db,
            user_id,
            for_update=True,
            auto_commit_if_created=False,
        )
        wallet.balance = WalletService._to_money(wallet.balance) + amount_value
        wallet.updated_at = datetime.utcnow()
        db.add(wallet)

        txn = Transaction(
            wallet_id=wallet.id,
            amount=amount_value,
            balance_after=WalletService._to_money(wallet.balance),
            type="credit",
            category=category,
            status="success",
            description=description,
            razorpay_payment_id=gateway_payment_id,
            reference_type=reference_type,
            reference_id=reference_id,
        )
        db.add(txn)

        db.commit()
        db.refresh(wallet)
        return wallet

    @staticmethod
    def deduct_balance(db: Session, user_id: int, amount: float | Decimal, description: str = "Payment") -> Wallet:
        amount_value = WalletService._to_money(amount)
        if amount_value <= 0:
            raise HTTPException(status_code=400, detail="Amount must be greater than zero")

        wallet = WalletService.get_wallet(
            db,
            user_id,
            for_update=True,
            auto_commit_if_created=False,
        )
        current_balance = WalletService._to_money(wallet.balance)
        if current_balance < amount_value:
            raise HTTPException(status_code=400, detail="Insufficient balance")

        wallet.balance = current_balance - amount_value
        wallet.updated_at = datetime.utcnow()
        db.add(wallet)

        txn = Transaction(
            wallet_id=wallet.id,
            amount=-amount_value,
            balance_after=WalletService._to_money(wallet.balance),
            type="debit",
            category="withdrawal",
            status="success",
            description=description,
        )
        db.add(txn)

        db.commit()
        db.refresh(wallet)
        return wallet

    @staticmethod
    def create_recharge_intent(
        db: Session,
        *,
        user_id: int,
        amount: float | Decimal,
        order_id: str,
        description: str = "Wallet recharge intent",
    ) -> Transaction:
        if not order_id:
            raise HTTPException(status_code=400, detail="order_id is required")
        amount_value = WalletService._to_money(amount)
        if amount_value <= 0:
            raise HTTPException(status_code=400, detail="Amount must be greater than zero")

        wallet = WalletService.get_wallet(
            db,
            user_id,
            for_update=True,
            auto_commit_if_created=False,
        )

        existing = db.exec(
            select(Transaction)
            .where(Transaction.wallet_id == wallet.id)
            .where(Transaction.reference_type == "wallet_recharge")
            .where(Transaction.reference_id == order_id)
            .with_for_update()
        ).first()
        if existing:
            return existing

        intent = Transaction(
            wallet_id=wallet.id,
            amount=amount_value,
            balance_after=WalletService._to_money(wallet.balance),
            type="credit",
            category="deposit",
            status="pending",
            description=description,
            reference_type="wallet_recharge",
            reference_id=order_id,
        )
        db.add(intent)
        db.commit()
        db.refresh(intent)
        return intent

    @staticmethod
    def apply_recharge_capture(
        db: Session,
        *,
        order_id: str,
        payment_id: str,
        amount: float | Decimal,
        noted_user_id: Optional[int] = None,
    ) -> Transaction:
        amount_value = WalletService._to_money(amount)
        if amount_value <= 0:
            raise HTTPException(status_code=400, detail="Recharge amount must be greater than zero")

        intent = db.exec(
            select(Transaction)
            .where(Transaction.reference_type == "wallet_recharge")
            .where(Transaction.reference_id == order_id)
            .with_for_update()
        ).first()
        if not intent:
            raise HTTPException(status_code=404, detail="Recharge intent not found")

        wallet = db.exec(select(Wallet).where(Wallet.id == intent.wallet_id).with_for_update()).first()
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")

        if noted_user_id is not None and wallet.user_id != noted_user_id:
            raise HTTPException(status_code=400, detail="Webhook user mismatch for recharge intent")

        if intent.status == "success":
            return intent

        wallet.balance = WalletService._to_money(wallet.balance) + amount_value
        wallet.updated_at = datetime.utcnow()
        db.add(wallet)

        intent.status = "success"
        intent.amount = amount_value
        intent.balance_after = WalletService._to_money(wallet.balance)
        intent.razorpay_payment_id = payment_id
        intent.description = f"Wallet recharge captured ({payment_id})"
        db.add(intent)

        db.commit()
        db.refresh(intent)
        WorkflowAutomationService.notify_wallet_recharge_captured(
            db,
            user_id=wallet.user_id,
            amount=amount_value,
            payment_id=payment_id,
        )
        return intent

    @staticmethod
    def mark_recharge_intent_failed(db: Session, *, order_id: str, payment_id: Optional[str] = None) -> Optional[Transaction]:
        intent = db.exec(
            select(Transaction)
            .where(Transaction.reference_type == "wallet_recharge")
            .where(Transaction.reference_id == order_id)
            .with_for_update()
        ).first()
        if not intent:
            return None
        if intent.status == "success":
            return intent

        wallet = db.exec(select(Wallet).where(Wallet.id == intent.wallet_id)).first()
        user_id = wallet.user_id if wallet else None
        intent.status = "failed"
        if payment_id:
            intent.razorpay_payment_id = payment_id
        db.add(intent)
        db.commit()
        db.refresh(intent)
        if user_id is not None:
            WorkflowAutomationService.notify_wallet_recharge_failed(
                db,
                user_id=user_id,
                order_id=order_id,
                payment_id=payment_id,
            )
        return intent

    @staticmethod
    def request_withdrawal(db: Session, user_id: int, amount: float, bank_details: dict) -> WalletWithdrawalRequest:
        amount_value = WalletService._to_money(amount)
        if amount_value <= 0:
            raise HTTPException(status_code=400, detail="Amount must be greater than zero")

        wallet = WalletService.get_wallet(
            db,
            user_id,
            for_update=True,
            auto_commit_if_created=False,
        )
        current_balance = WalletService._to_money(wallet.balance)
        if current_balance < amount_value:
            raise HTTPException(status_code=400, detail="Insufficient balance")

        req = WalletWithdrawalRequest(
            wallet_id=wallet.id,
            amount=amount_value,
            bank_details=str(bank_details),
            status="requested",
        )
        db.add(req)
        db.flush()

        wallet.balance = current_balance - amount_value
        wallet.updated_at = datetime.utcnow()
        db.add(wallet)

        txn = Transaction(
            wallet_id=wallet.id,
            amount=-amount_value,
            balance_after=WalletService._to_money(wallet.balance),
            type="debit",
            category="withdrawal_request",
            status="pending",
            description=f"Withdrawal request #{req.id}",
            reference_type="withdrawal_request",
            reference_id=str(req.id),
        )
        db.add(txn)

        db.commit()
        db.refresh(req)

        SecurityService.log_event(
            db,
            event_type="withdrawal_request",
            severity="medium",
            details=f"User {user_id} requested withdrawal of {amount_value}",
            user_id=user_id,
        )
        WorkflowAutomationService.notify_withdrawal_requested(
            db,
            user_id=user_id,
            request_id=req.id,
            amount=amount_value,
        )
        return req

    @staticmethod
    def approve_withdrawal_request(
        db: Session,
        *,
        request_id: int,
        approver_user_id: int,
        payout_reference: Optional[str] = None,
    ) -> WalletWithdrawalRequest:
        req = db.exec(
            select(WalletWithdrawalRequest).where(WalletWithdrawalRequest.id == request_id).with_for_update()
        ).first()
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
        if req.status != "requested":
            raise HTTPException(status_code=400, detail="Request already processed")

        txn = db.exec(
            select(Transaction)
            .where(Transaction.reference_type == "withdrawal_request")
            .where(Transaction.reference_id == str(req.id))
            .with_for_update()
        ).first()

        req.status = "processed"
        req.processed_at = datetime.utcnow()
        db.add(req)

        if txn:
            txn.status = "success"
            if payout_reference:
                txn.description = f"Withdrawal payout processed ({payout_reference})"
            db.add(txn)

        db.commit()
        db.refresh(req)

        wallet = db.exec(select(Wallet).where(Wallet.id == req.wallet_id)).first()
        if wallet:
            WorkflowAutomationService.notify_withdrawal_processed(
                db,
                user_id=wallet.user_id,
                request_id=req.id,
                amount=req.amount,
                payout_reference=payout_reference,
            )

        SecurityService.log_event(
            db,
            event_type="withdrawal_processed",
            severity="medium",
            details=f"Withdrawal request {req.id} approved by user {approver_user_id}",
            user_id=approver_user_id,
        )
        return req

    @staticmethod
    def reject_withdrawal_request(
        db: Session,
        *,
        request_id: int,
        approver_user_id: int,
        reason: Optional[str] = None,
    ) -> WalletWithdrawalRequest:
        req = db.exec(
            select(WalletWithdrawalRequest).where(WalletWithdrawalRequest.id == request_id).with_for_update()
        ).first()
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
        if req.status != "requested":
            raise HTTPException(status_code=400, detail="Request already processed")

        wallet = db.exec(select(Wallet).where(Wallet.id == req.wallet_id).with_for_update()).first()
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")

        pending_txn = db.exec(
            select(Transaction)
            .where(Transaction.reference_type == "withdrawal_request")
            .where(Transaction.reference_id == str(req.id))
            .with_for_update()
        ).first()
        if pending_txn and pending_txn.status == "success":
            raise HTTPException(status_code=400, detail="Cannot reject an already processed withdrawal")

        amount = WalletService._to_money(req.amount)
        wallet.balance = WalletService._to_money(wallet.balance) + amount
        wallet.updated_at = datetime.utcnow()
        db.add(wallet)

        reversal = Transaction(
            wallet_id=wallet.id,
            amount=amount,
            balance_after=WalletService._to_money(wallet.balance),
            type="credit",
            category="withdrawal_reversal",
            status="success",
            description=f"Withdrawal request #{req.id} rejected" + (f": {reason}" if reason else ""),
            reference_type="withdrawal_request",
            reference_id=str(req.id),
        )
        db.add(reversal)

        if pending_txn:
            pending_txn.status = "failed"
            if reason:
                pending_txn.description = f"Withdrawal request #{req.id} rejected: {reason}"
            db.add(pending_txn)

        req.status = "rejected"
        req.processed_at = datetime.utcnow()
        db.add(req)
        db.commit()
        db.refresh(req)

        WorkflowAutomationService.notify_withdrawal_rejected(
            db,
            user_id=wallet.user_id,
            request_id=req.id,
            amount=req.amount,
            reason=reason,
        )

        SecurityService.log_event(
            db,
            event_type="withdrawal_rejected",
            severity="medium",
            details=f"Withdrawal request {req.id} rejected by user {approver_user_id}",
            user_id=approver_user_id,
        )
        return req

    @staticmethod
    def apply_cashback(db: Session, user_id: int, amount: float, reason: str = "Cashback"):
        return WalletService.add_balance(db, user_id, amount, description=reason, category="cashback")

    @staticmethod
    def initiate_refund(
        db: Session,
        transaction_id: int,
        amount: Optional[float] = None,
        reason: str = "Customer Request",
    ) -> Optional[Refund]:
        orig_txn = db.get(Transaction, transaction_id)
        if not orig_txn or orig_txn.type != "credit":
            return None

        refund_amount = WalletService._to_money(amount if amount is not None else orig_txn.amount)
        if refund_amount <= 0:
            raise HTTPException(status_code=400, detail="Refund amount must be greater than zero")

        refund = Refund(
            transaction_id=transaction_id,
            amount=refund_amount,
            reason=reason,
            status="pending",
        )
        db.add(refund)
        db.commit()
        db.refresh(refund)
        return refund
