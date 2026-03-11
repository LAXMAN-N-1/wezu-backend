from sqlmodel import Session, select
from app.models.commission import CommissionConfig, CommissionLog
from app.models.financial import Transaction
from typing import Optional
import logging

logger = logging.getLogger("wezu_commissions")

class CommissionService:
    @staticmethod
    def calculate_and_log(db: Session, transaction: Transaction):
        """
        Calculate commissions for a given transaction based on transaction_type.
        """
        # Find active configs for this transaction type
        statement = select(CommissionConfig).where(
            CommissionConfig.transaction_type == transaction.transaction_type,
            CommissionConfig.is_active == True
        )
        configs = db.exec(statement).all()
        
        for config in configs:
            amount = 0.0
            if config.percentage > 0:
                amount += abs(transaction.amount) * (config.percentage / 100.0)
            if config.flat_fee > 0:
                amount += config.flat_fee
            
            if amount > 0:
                log = CommissionLog(
                    transaction_id=transaction.id,
                    dealer_id=config.dealer_id,
                    vendor_id=config.vendor_id,
                    amount=amount,
                    status="pending"
                )
                db.add(log)
                logger.info(f"Commission logged: ₹{amount} for Transaction {transaction.id} ({transaction.transaction_type})")
        
        db.commit()

    @staticmethod
    def process_payout(db: Session, log_id: int):
        """
        Mark a commission as paid. In production, this would bridge to internal ledgers.
        """
        log = db.get(CommissionLog, log_id)
        if log:
            log.status = "paid"
            db.add(log)
            db.commit()
            return log
        return None
