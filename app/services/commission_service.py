from sqlmodel import Session, select
from app.models.commission import CommissionConfig, CommissionLog, CommissionTier
from app.models.financial import Transaction
from typing import Optional
from datetime import datetime, UTC
import logging

logger = logging.getLogger("wezu_commissions")


class CommissionService:
    @staticmethod
    def get_applicable_rate(
        db: Session,
        transaction_type: str,
        dealer_id: Optional[int] = None,
        monthly_volume: int = 0,
        as_of_date: Optional[datetime] = None,
    ) -> dict:
        """
        Resolve the correct commission rate considering:
        1. Active configs matching transaction_type and dealer_id
        2. Effective date window
        3. Volume-based tiers
        Returns {"percentage": float, "flat_fee": float}
        """
        now = as_of_date or datetime.now(UTC)

        statement = select(CommissionConfig).where(
            CommissionConfig.transaction_type == transaction_type,
            CommissionConfig.is_active == True,
            CommissionConfig.effective_from <= now,
        )
        # Filter by effective_until (None means no expiry)
        configs = db.exec(statement).all()
        configs = [
            c for c in configs
            if c.effective_until is None or c.effective_until >= now
        ]

        # Prefer dealer-specific config, then global
        dealer_configs = [c for c in configs if c.dealer_id == dealer_id] if dealer_id else []
        chosen = dealer_configs[0] if dealer_configs else (configs[0] if configs else None)

        if not chosen:
            return {"percentage": 0.0, "flat_fee": 0.0}

        # Check for volume-based tier
        tiers = db.exec(
            select(CommissionTier)
            .where(CommissionTier.config_id == chosen.id)
            .order_by(CommissionTier.min_volume)
        ).all()

        if tiers:
            for tier in tiers:
                if tier.min_volume <= monthly_volume and (
                    tier.max_volume is None or monthly_volume <= tier.max_volume
                ):
                    return {"percentage": tier.percentage, "flat_fee": tier.flat_fee}

        # Fallback to config default
        return {"percentage": chosen.percentage, "flat_fee": chosen.flat_fee}

    @staticmethod
    def calculate_and_log(db: Session, transaction: Transaction):
        """
        Calculate commissions for a given transaction based on transaction_type.
        Uses tiered rate resolution.

        Idempotency: webhooks / retry loops may call this more than once for
        the same Transaction. We serialize concurrent callers by locking the
        parent Transaction row, then guard against duplicate CommissionLog
        rows with an explicit existence check. A follow-up migration should
        add a partial unique index on
        ``commission_logs(transaction_id) WHERE status IN ('pending','paid')``
        to make this race-free at the DB layer as well.
        """
        rate = CommissionService.get_applicable_rate(
            db,
            transaction_type=transaction.transaction_type.value if transaction.transaction_type else "unknown",
        )

        amount = 0.0
        if rate["percentage"] > 0:
            amount += abs(transaction.amount) * (rate["percentage"] / 100.0)
        if rate["flat_fee"] > 0:
            amount += rate["flat_fee"]

        amount = round(amount, 2)

        if amount <= 0:
            db.commit()
            return None

        # Serialize concurrent calculators on the same parent transaction.
        locked_txn = db.exec(
            select(Transaction).where(Transaction.id == transaction.id).with_for_update()
        ).first()
        if not locked_txn:
            logger.warning(
                "commission.parent_transaction_missing",
                extra={"transaction_id": transaction.id},
            )
            db.commit()
            return None

        # Duplicate guard — return the existing non-reversed log if any.
        existing = db.exec(
            select(CommissionLog).where(
                CommissionLog.transaction_id == transaction.id,
                CommissionLog.status.in_(["pending", "paid"]),
            )
        ).first()
        if existing:
            logger.info(
                "commission.duplicate_skipped",
                extra={
                    "transaction_id": transaction.id,
                    "existing_log_id": existing.id,
                    "existing_status": existing.status,
                },
            )
            db.commit()
            return existing

        log = CommissionLog(
            transaction_id=transaction.id,
            dealer_id=None,  # Determined by config context
            vendor_id=None,
            amount=amount,
            status="pending",
        )
        db.add(log)
        logger.info(f"Commission logged: {amount} for Transaction {transaction.id}")

        db.commit()
        db.refresh(log)
        return log

    @staticmethod
    def process_payout(db: Session, log_id: int):
        """
        Mark a commission as paid.
        """
        log = db.get(CommissionLog, log_id)
        if log:
            log.status = "paid"
            db.add(log)
            db.commit()
            return log
        return None
