from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from app.core.logging import get_logger
from app.core.observability import SLOTimer
from app.models.financial import Transaction, Wallet, WalletWithdrawalRequest
from app.models.notification import Notification, NotificationStatus
from app.models.refund import Refund
from app.services.notification_outbox_service import NotificationOutboxService
from app.services.security_service import SecurityService
from app.services.workflow_automation_service import WorkflowAutomationService

logger = get_logger("wezu_wallet")


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
        auto_commit_if_created: bool = False,
    ) -> Wallet:
        """Fetch (or lazily create) a user's wallet.

        Atomicity: default is ``auto_commit_if_created=False`` so the caller
        owns the transaction boundary. Committing here mid-request would
        publish a zero-balance wallet even if the caller's follow-up work
        (balance mutation + transaction row) later failed, leaving orphaned
        state. Callers that only need to read and do not intend to commit
        can still safely call this — the just-created wallet lives inside
        the session and will be persisted on the caller's commit.
        """
        query = select(Wallet).where(Wallet.user_id == user_id)
        if for_update:
            query = query.with_for_update()

        wallet = db.exec(query).first()
        if wallet:
            return wallet

        wallet = Wallet(user_id=user_id, balance=Decimal("0.00"))
        db.add(wallet)
        db.flush()  # populate wallet.id within the open transaction
        if auto_commit_if_created:
            db.commit()
            db.refresh(wallet)
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
        with SLOTimer("wallet.add_balance", budget_ms=500, extra={"user_id": user_id}):
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
                user_id=wallet.user_id,
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
        with SLOTimer("wallet.deduct_balance", budget_ms=500, extra={"user_id": user_id}):
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
                user_id=wallet.user_id,
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
            user_id=wallet.user_id,
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
        with SLOTimer("wallet.apply_recharge_capture", budget_ms=1000, extra={"order_id": order_id}):
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

            # ── Idempotency guard ────────────────────────────────────────────
            # Razorpay webhooks may fire multiple times for the same capture.
            # If the intent is already "success", return it as-is without
            # crediting the wallet again.  This guarantees exactly-once balance
            # updates even under concurrent webhook deliveries.
            if intent.status == "success":
                logger.info(
                    "wallet.recharge_capture_idempotent",
                    order_id=order_id,
                )
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

            # ── Transactional outbox for the success notification ──────────
            # Previously we called WorkflowAutomationService *after* commit,
            # which meant a crash between commit and the notification call
            # would silently drop the user notification. We now stage a
            # Notification + NotificationOutbox row per channel inside the
            # same transaction, so the outbox dispatcher is guaranteed to
            # see them iff the wallet credit is committed.
            WalletService._stage_recharge_success_notifications(
                db,
                user_id=wallet.user_id,
                amount=amount_value,
                payment_id=payment_id,
            )

            db.commit()
            db.refresh(intent)
            return intent

    @staticmethod
    def _stage_recharge_success_notifications(
        db: Session,
        *,
        user_id: int,
        amount: Decimal,
        payment_id: str,
    ) -> None:
        """Stage (do not commit) recharge-success notifications + outbox rows.

        Must be called inside an open transaction that the caller will
        commit. Each channel gets its own idempotency key derived from the
        payment_id so webhook retries converge on the same outbox entries.
        """
        title = "Wallet Recharge Successful"
        message = (
            f"We have credited INR {amount} to your wallet. "
            f"Payment reference: {payment_id}."
        )
        now = datetime.utcnow()
        for channel in ("push", "email", "sms"):
            notif = Notification(
                user_id=user_id,
                title=title,
                message=message,
                type="wallet_recharge_success",
                channel=channel,
                status=NotificationStatus.QUEUED,
                scheduled_at=now,
            )
            db.add(notif)
            db.flush()  # populate notif.id for the outbox row
            NotificationOutboxService.enqueue(
                db,
                notification=notif,
                scheduled_at=now,
                idempotency_key=f"wallet_recharge_captured:{payment_id}:{channel}",
            )

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
            user_id=wallet.user_id,
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
            user_id=wallet.user_id,
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

    # ── P1-A-1: Wallet-to-wallet transfer ─────────────────────────────────
    @staticmethod
    def transfer_balance(
        db: Session,
        sender_id: int,
        recipient_phone: str,
        amount: float | Decimal,
        note: str | None = None,
    ) -> Transaction:
        """Transfer balance between two user wallets, identified by phone number."""
        from app.models.user import User

        with SLOTimer("wallet.transfer_balance", budget_ms=800, extra={"sender_id": sender_id}):
            amount_value = WalletService._to_money(amount)
            if amount_value <= 0:
                raise HTTPException(status_code=400, detail="Transfer amount must be greater than zero")

            recipient = db.exec(
                select(User).where(User.phone_number == recipient_phone)
            ).first()
            if not recipient:
                raise HTTPException(status_code=404, detail="Recipient not found")
            if recipient.id == sender_id:
                raise HTTPException(status_code=400, detail="Cannot transfer to yourself")

            # Lock both wallets (always lock lower id first to avoid deadlocks)
            ids = sorted([sender_id, recipient.id])
            wallet_a = WalletService.get_wallet(db, ids[0], for_update=True, auto_commit_if_created=False)
            wallet_b = WalletService.get_wallet(db, ids[1], for_update=True, auto_commit_if_created=False)
            sender_wallet = wallet_a if wallet_a.user_id == sender_id else wallet_b
            recipient_wallet = wallet_b if wallet_b.user_id == recipient.id else wallet_a

            sender_balance = WalletService._to_money(sender_wallet.balance)
            if sender_balance < amount_value:
                raise HTTPException(status_code=400, detail="Insufficient balance")

            # Debit sender
            sender_wallet.balance = sender_balance - amount_value
            sender_wallet.updated_at = datetime.utcnow()
            db.add(sender_wallet)

            debit_txn = Transaction(
                user_id=sender_wallet.user_id,
                wallet_id=sender_wallet.id,
                amount=-amount_value,
                balance_after=WalletService._to_money(sender_wallet.balance),
                type="debit",
                category="transfer",
                status="success",
                description=note or f"Transfer to {recipient_phone}",
                reference_type="transfer",
                reference_id=str(recipient.id),
            )
            db.add(debit_txn)

            # Credit recipient
            recipient_wallet.balance = WalletService._to_money(recipient_wallet.balance) + amount_value
            recipient_wallet.updated_at = datetime.utcnow()
            db.add(recipient_wallet)

            credit_txn = Transaction(
                user_id=recipient_wallet.user_id,
                wallet_id=recipient_wallet.id,
                amount=amount_value,
                balance_after=WalletService._to_money(recipient_wallet.balance),
                type="credit",
                category="transfer",
                status="success",
                description=note or f"Transfer from user #{sender_id}",
                reference_type="transfer",
                reference_id=str(sender_id),
            )
            db.add(credit_txn)

            db.commit()
            db.refresh(debit_txn)
            return debit_txn

    # ── P1-A-2: Cashback transaction history ──────────────────────────────
    @staticmethod
    def get_cashback_history(db: Session, user_id: int) -> list[Transaction]:
        """Return up to 100 cashback transactions for a user, newest first."""
        wallet = WalletService.get_wallet(db, user_id)
        return list(
            db.exec(
                select(Transaction)
                .where(Transaction.wallet_id == wallet.id, Transaction.category == "cashback")
                .order_by(Transaction.created_at.desc())
                .limit(100)
            ).all()
        )

    @staticmethod
    def initiate_refund(
        db: Session,
        transaction_id: int,
        amount: Optional[float] = None,
        reason: str = "Customer Request",
    ) -> Optional[Refund]:
        """Create a refund request with exactly-once semantics.

        Guards:
        1. Original transaction must exist and be a credit.
        2. No pending/processed refund may already exist for this transaction
           (prevents duplicate refunds from UI double-clicks or webhook retries).
        3. Refund amount must be > 0 and <= original transaction amount.
        """
        orig_txn = db.get(Transaction, transaction_id)
        if not orig_txn or orig_txn.type != "credit":
            return None

        # ── Duplicate-refund guard (exactly-once) ────────────────────────
        existing_refund = db.exec(
            select(Refund).where(
                Refund.transaction_id == transaction_id,
                Refund.status.in_(["pending", "processed"]),
            )
        ).first()
        if existing_refund:
            logger.info(
                "wallet.refund_duplicate_blocked",
                refund_id=existing_refund.id,
                status=existing_refund.status,
            )
            return existing_refund  # idempotent: return the in-flight refund

        refund_amount = WalletService._to_money(amount if amount is not None else orig_txn.amount)
        if refund_amount <= 0:
            raise HTTPException(status_code=400, detail="Refund amount must be greater than zero")
        if refund_amount > WalletService._to_money(orig_txn.amount):
            raise HTTPException(status_code=400, detail="Refund amount exceeds original transaction")

        refund = Refund(
            transaction_id=transaction_id,
            amount=refund_amount,
            reason=reason,
            status="pending",
        )
        db.add(refund)
        db.commit()
        db.refresh(refund)
        logger.info(
            "wallet.refund_initiated",
            refund_id=refund.id,
            transaction_id=transaction_id,
            amount=refund_amount,
        )
        return refund

    @staticmethod
    def process_refund(db: Session, refund_id: int) -> Refund:
        """Transition a refund from pending → processed | failed.

        State machine:
          pending → processed  (wallet credited back)
          pending → failed     (gateway failure)
          processed → (no-op)  idempotent return
          failed → pending     (allowed for retry via initiate_refund)
        """
        with SLOTimer("wallet.process_refund", budget_ms=600, extra={"refund_id": refund_id}):
            refund = db.exec(
                select(Refund).where(Refund.id == refund_id).with_for_update()
            ).first()
            if not refund:
                raise HTTPException(status_code=404, detail="Refund not found")

            if refund.status == "processed":
                return refund  # idempotent

            if refund.status != "pending":
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot process refund with status '{refund.status}'",
                )

            orig_txn = db.get(Transaction, refund.transaction_id)
            if not orig_txn:
                refund.status = "failed"
                db.add(refund)
                db.commit()
                raise HTTPException(status_code=404, detail="Original transaction not found")

            wallet = db.exec(
                select(Wallet).where(Wallet.id == orig_txn.wallet_id).with_for_update()
            ).first()
            if not wallet:
                refund.status = "failed"
                db.add(refund)
                db.commit()
                raise HTTPException(status_code=404, detail="Wallet not found")

            # Credit wallet back
            wallet.balance = WalletService._to_money(wallet.balance) + WalletService._to_money(refund.amount)
            wallet.updated_at = datetime.utcnow()
            db.add(wallet)

            # Record refund transaction
            refund_txn = Transaction(
                user_id=wallet.user_id,
                wallet_id=wallet.id,
                amount=WalletService._to_money(refund.amount),
                type="credit",
                category="refund",
                description=f"Refund for transaction #{refund.transaction_id}: {refund.reason}",
                status="success",
                balance_after=WalletService._to_money(wallet.balance),
                reference_type="refund",
                reference_id=str(refund.id),
            )
            db.add(refund_txn)

            refund.status = "processed"
            refund.processed_at = datetime.utcnow()
            db.add(refund)

            db.commit()
            db.refresh(refund)
            logger.info(
                "wallet.refund_processed",
                refund_id=refund.id,
                amount=refund.amount,
                wallet_id=wallet.id,
            )
            return refund
