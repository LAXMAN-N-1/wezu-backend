from sqlmodel import Session, select, col
from app.models.commission import CommissionConfig, CommissionLog, CommissionTier
from app.models.financial import Transaction
from typing import Optional
from datetime import datetime
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
        now = as_of_date or datetime.utcnow()

        statement = select(CommissionConfig).where(
            col(CommissionConfig.transaction_type) == transaction_type,
            col(CommissionConfig.is_active) == True,
            col(CommissionConfig.effective_from) <= now,
        )
        # Filter by effective_until (None means no expiry)
        configs = list(db.exec(statement).all())
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
        tiers = list(db.exec(
            select(CommissionTier)
            .where(col(CommissionTier.config_id) == (chosen.id or 0))
            .order_by(col(CommissionTier.min_volume))
        ).all())

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
        """
        rate = CommissionService.get_applicable_rate(
            db,
            transaction_type=transaction.transaction_type,
        )

        amount = 0.0
        if rate["percentage"] > 0:
            amount += abs(transaction.amount) * (rate["percentage"] / 100.0)
        if rate["flat_fee"] > 0:
            amount += rate["flat_fee"]

        amount = round(amount, 2)

        if amount > 0:
            assert transaction.id is not None
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
