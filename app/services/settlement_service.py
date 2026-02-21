from sqlmodel import Session, select, func
from app.models.settlement import Settlement, SettlementStatus
from app.models.commission import CommissionLog
from app.models.dealer import DealerProfile
from datetime import datetime, timedelta
from typing import List, Optional

class SettlementService:
    @staticmethod
    def trigger_settlement(db: Session, dealer_id: int) -> Optional[Settlement]:
        """Trigger a new settlement for pending commissions"""
        # Find all pending commissions for this dealer
        commissions = db.exec(
            select(CommissionLog)
            .where(CommissionLog.dealer_id == dealer_id)
            .where(CommissionLog.status == "pending")
        ).all()
        
        if not commissions:
            return None
            
        total_amount = sum(c.amount for c in commissions)
        
        # Create Settlement record
        settlement = Settlement(
            dealer_id=dealer_id,
            amount=total_amount,
            status=SettlementStatus.PENDING,
            period_start=min(c.created_at for c in commissions),
            period_end=max(c.created_at for c in commissions)
        )
        db.add(settlement)
        db.flush() # Get ID
        
        # Link commissions to settlement
        for c in commissions:
            c.status = "paid"
            c.settlement_id = settlement.id
            db.add(c)
            
        db.commit()
        db.refresh(settlement)
        return settlement

    @staticmethod
    def get_settlements(db: Session, dealer_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> List[Settlement]:
        statement = select(Settlement)
        if dealer_id:
            statement = statement.where(Settlement.dealer_id == dealer_id)
        return db.exec(statement.offset(skip).limit(limit).order_by(Settlement.created_at.desc())).all()
