"""
P3-A: Wallet flow-level invariant tests.

Validates core financial invariants that must hold across all code paths:
  1. Wallet balance is never negative after any operation.
  2. Recharge capture is idempotent (credited exactly once).
  3. Transfer conserves total money (sender debit + recipient credit = 0).
  4. Refund state machine follows defined transitions.
  5. Withdrawal rejection restores balance to pre-request value.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from hypothesis import given, settings as h_settings, HealthCheck
from hypothesis import strategies as st

from app.models.financial import Transaction, TransactionType, Wallet
from app.models.refund import Refund
from app.models.user import User
from app.services.wallet_service import WalletService


# ── Helpers ──────────────────────────────────────────────────────────────

_counter = 0


def _create_user(db, phone: str | None = None, email: str | None = None) -> User:
    """Create a minimal User row for testing with auto-unique phone/email."""
    global _counter
    _counter += 1
    tag = f"{_counter}_{uuid.uuid4().hex[:8]}"
    from app.core.security import get_password_hash

    user = User(
        phone_number=phone or f"10{tag}",
        email=email or f"u{tag}@test.com",
        full_name="Test User",
        hashed_password=get_password_hash("test123"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _wallet_balance(db, user_id: int) -> Decimal:
    wallet = WalletService.get_wallet(db, user_id)
    return WalletService._to_money(wallet.balance)


# ── 1. Balance never negative ───────────────────────────────────────────

class TestWalletBalanceNonNegative:
    """After any add/deduct sequence the balance must be >= 0."""

    @given(deposit=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("9999.99"), places=2))
    @h_settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_deposit_always_positive(self, session, deposit: Decimal):
        user = _create_user(session)
        WalletService.add_balance(session, user.id, float(deposit))
        assert _wallet_balance(session, user.id) >= 0

    def test_deduct_rejects_overdraft(self, session):
        user = _create_user(session, "1000000002", "ovr@test.com")
        WalletService.add_balance(session, user.id, 50.00)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            WalletService.deduct_balance(session, user.id, 100.00)
        assert exc_info.value.status_code == 400
        assert "Insufficient" in exc_info.value.detail

        # Balance must remain at 50 after rejected deduction
        assert _wallet_balance(session, user.id) == Decimal("50.00")

    def test_deduct_exact_balance_reaches_zero(self, session):
        user = _create_user(session, "1000000003", "zero@test.com")
        WalletService.add_balance(session, user.id, 25.50)
        WalletService.deduct_balance(session, user.id, 25.50)
        assert _wallet_balance(session, user.id) == Decimal("0.00")

    @given(
        amounts=st.lists(
            st.decimals(min_value=Decimal("0.01"), max_value=Decimal("100.00"), places=2),
            min_size=2,
            max_size=6,
        )
    )
    @h_settings(max_examples=15, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_series_of_deposits_balance_equals_sum(self, session, amounts):
        user = _create_user(session)
        expected = Decimal("0.00")
        for amt in amounts:
            WalletService.add_balance(session, user.id, float(amt))
            expected += WalletService._to_money(amt)
        assert _wallet_balance(session, user.id) == expected


# ── 2. Recharge capture idempotency ─────────────────────────────────────

class TestRechargeCaptureIdempotent:
    """Calling apply_recharge_capture twice with the same order must credit only once."""

    def test_double_capture_credits_once(self, session):
        user = _create_user(session, "2000000001", "idem@test.com")
        intent = WalletService.create_recharge_intent(
            session, user_id=user.id, amount=200.00, order_id="order_idem_001"
        )
        assert intent.status == "pending"

        # First capture
        captured_1 = WalletService.apply_recharge_capture(
            session,
            order_id="order_idem_001",
            payment_id="pay_idem_001",
            amount=200.00,
            noted_user_id=user.id,
        )
        assert captured_1.status == "success"
        balance_after_first = _wallet_balance(session, user.id)
        assert balance_after_first == Decimal("200.00")

        # Second capture — must be idempotent (no double-credit)
        captured_2 = WalletService.apply_recharge_capture(
            session,
            order_id="order_idem_001",
            payment_id="pay_idem_001",
            amount=200.00,
            noted_user_id=user.id,
        )
        assert captured_2.status == "success"
        assert captured_2.id == captured_1.id
        assert _wallet_balance(session, user.id) == balance_after_first

    def test_failed_intent_not_recapturable_after_success(self, session):
        """Once a recharge succeeds, mark_failed must not undo it."""
        user = _create_user(session, "2000000002", "fail@test.com")
        WalletService.create_recharge_intent(
            session, user_id=user.id, amount=150.00, order_id="order_fail_001"
        )
        WalletService.apply_recharge_capture(
            session,
            order_id="order_fail_001",
            payment_id="pay_fail_001",
            amount=150.00,
        )
        balance_before = _wallet_balance(session, user.id)

        # mark_failed should be a no-op when intent is already "success"
        result = WalletService.mark_recharge_intent_failed(
            session, order_id="order_fail_001"
        )
        assert result is not None
        assert result.status == "success"
        assert _wallet_balance(session, user.id) == balance_before


# ── 3. Transfer conservation ────────────────────────────────────────────

class TestTransferConservation:
    """sender_debit + recipient_credit == 0 (zero-sum transfer)."""

    def test_transfer_conserves_total_money(self, session):
        sender = _create_user(session, "3000000001", "sender@test.com")
        recipient = _create_user(session, "3000000002", "recip@test.com")

        WalletService.add_balance(session, sender.id, 500.00)
        WalletService.add_balance(session, recipient.id, 100.00)

        total_before = _wallet_balance(session, sender.id) + _wallet_balance(session, recipient.id)

        WalletService.transfer_balance(
            session, sender.id, recipient.phone_number, Decimal("200.00"), "test xfer"
        )

        total_after = _wallet_balance(session, sender.id) + _wallet_balance(session, recipient.id)
        assert total_after == total_before

    def test_transfer_rejects_overdraft(self, session):
        sender = _create_user(session, "3000000003", "broke@test.com")
        recipient = _create_user(session, "3000000004", "rich@test.com")

        WalletService.add_balance(session, sender.id, 50.00)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            WalletService.transfer_balance(
                session, sender.id, recipient.phone_number, Decimal("100.00")
            )
        assert "Insufficient" in exc_info.value.detail
        # Sender balance unchanged
        assert _wallet_balance(session, sender.id) == Decimal("50.00")

    def test_transfer_to_self_rejected(self, session):
        user = _create_user(session, "3000000005", "self@test.com")
        WalletService.add_balance(session, user.id, 100.00)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            WalletService.transfer_balance(
                session, user.id, user.phone_number, Decimal("10.00")
            )
        assert "yourself" in exc_info.value.detail.lower()


# ── 4. Refund state machine ─────────────────────────────────────────────

class TestRefundStateMachine:
    """Refund must follow pending → processed | failed transitions."""

    def _make_credit_txn(self, db, user_id: int, wallet_id: int, amount: float) -> Transaction:
        txn = Transaction(
            user_id=user_id,
            wallet_id=wallet_id,
            amount=amount,
            balance_after=amount,
            type="credit",
            category="deposit",
            status="success",
            transaction_type=TransactionType.WALLET_TOPUP,
        )
        db.add(txn)
        db.commit()
        db.refresh(txn)
        return txn

    def test_initiate_then_process(self, session):
        user = _create_user(session, "4000000001", "refund@test.com")
        WalletService.add_balance(session, user.id, 300.00)
        wallet = WalletService.get_wallet(session, user.id)

        txn = self._make_credit_txn(session, user.id, wallet.id, 300.00)
        refund = WalletService.initiate_refund(session, txn.id, amount=100.00)
        assert refund is not None
        assert refund.status == "pending"

        processed = WalletService.process_refund(session, refund.id)
        assert processed.status == "processed"
        assert processed.processed_at is not None

    def test_process_is_idempotent(self, session):
        user = _create_user(session, "4000000002", "idem_ref@test.com")
        WalletService.add_balance(session, user.id, 200.00)
        wallet = WalletService.get_wallet(session, user.id)

        txn = self._make_credit_txn(session, user.id, wallet.id, 200.00)
        refund = WalletService.initiate_refund(session, txn.id, amount=50.00)
        WalletService.process_refund(session, refund.id)
        balance_after_refund = _wallet_balance(session, user.id)

        # Second call is idempotent
        same_refund = WalletService.process_refund(session, refund.id)
        assert same_refund.status == "processed"
        assert _wallet_balance(session, user.id) == balance_after_refund

    def test_duplicate_initiate_returns_existing(self, session):
        user = _create_user(session, "4000000003", "dup_ref@test.com")
        WalletService.add_balance(session, user.id, 500.00)
        wallet = WalletService.get_wallet(session, user.id)

        txn = self._make_credit_txn(session, user.id, wallet.id, 500.00)
        refund_1 = WalletService.initiate_refund(session, txn.id, amount=100.00)
        refund_2 = WalletService.initiate_refund(session, txn.id, amount=100.00)
        assert refund_1.id == refund_2.id  # exactly-once

    def test_refund_amount_cannot_exceed_original(self, session):
        user = _create_user(session, "4000000004", "excess@test.com")
        WalletService.add_balance(session, user.id, 100.00)
        wallet = WalletService.get_wallet(session, user.id)

        txn = self._make_credit_txn(session, user.id, wallet.id, 100.00)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            WalletService.initiate_refund(session, txn.id, amount=200.00)
        assert "exceeds" in exc_info.value.detail.lower()


# ── 5. Withdrawal rejection restores balance ────────────────────────────

class TestWithdrawalRejectionRestoresBalance:
    """When a withdrawal is rejected, the held amount must be credited back."""

    def test_reject_restores_full_balance(self, session):
        user = _create_user(session, "5000000001", "wd_rej@test.com")
        WalletService.add_balance(session, user.id, 1000.00)
        balance_before = _wallet_balance(session, user.id)

        req = WalletService.request_withdrawal(
            session, user.id, 400.00, {"bank": "test", "account": "123"}
        )
        # Balance reduced by withdrawal hold
        assert _wallet_balance(session, user.id) == balance_before - Decimal("400.00")

        WalletService.reject_withdrawal_request(
            session, request_id=req.id, approver_user_id=1, reason="Test rejection"
        )
        # Balance restored
        assert _wallet_balance(session, user.id) == balance_before
        assert req.status == "rejected"

    def test_approve_does_not_restore_balance(self, session):
        user = _create_user(session, "5000000002", "wd_app@test.com")
        WalletService.add_balance(session, user.id, 800.00)

        req = WalletService.request_withdrawal(
            session, user.id, 300.00, {"bank": "test", "account": "456"}
        )
        balance_after_hold = _wallet_balance(session, user.id)

        WalletService.approve_withdrawal_request(
            session, request_id=req.id, approver_user_id=1
        )
        # Balance stays at held level (money left the system)
        assert _wallet_balance(session, user.id) == balance_after_hold
