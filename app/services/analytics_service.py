from sqlmodel import Session, select, func
from app.models.swap import SwapSession
from app.models.rental import Rental
from app.models.financial import Transaction
from app.models.commission import CommissionLog
from datetime import datetime, timedelta
from typing import Dict, Any

class AnalyticsService:
    @staticmethod
    def get_dashboard_summary(db: Session) -> Dict[str, Any]:
        """
        Aggregate high-level business metrics for the last 24 hours.
        """
        since = datetime.utcnow() - timedelta(hours=24)
        
        # 1. Swap Volume
        swap_count = db.exec(select(func.count(SwapSession.id)).where(SwapSession.created_at >= since)).one()
        
        # 2. Revenue (Wallet Top-ups)
        revenue = db.exec(select(func.sum(Transaction.amount)).where(
            Transaction.type == "credit",
            Transaction.category == "deposit",
            Transaction.created_at >= since
        )).one() or 0.0
        
        # 3. Active Rentals
        active_rentals = db.exec(select(func.count(Rental.id)).where(Rental.status == "active")).one()
        
        return {
            "swaps_24h": swap_count,
            "revenue_24h": revenue,
            "active_rentals": active_rentals,
            "timestamp": datetime.utcnow()
        }

    @staticmethod
    def get_partner_revenue_report(db: Session, partner_id: int, is_vendor: bool = False) -> Dict[str, Any]:
        """
        Generate earnings report for a specific dealer or vendor.
        """
        if is_vendor:
            stmt = select(func.sum(CommissionLog.amount)).where(CommissionLog.vendor_id == partner_id)
        else:
            stmt = select(func.sum(CommissionLog.amount)).where(CommissionLog.dealer_id == partner_id)
            
        total_earnings = db.exec(stmt).one() or 0.0
        
        # Get last 5 logs
        if is_vendor:
            logs_stmt = select(CommissionLog).where(CommissionLog.vendor_id == partner_id).order_by(CommissionLog.created_at.desc()).limit(5)
        else:
            logs_stmt = select(CommissionLog).where(CommissionLog.dealer_id == partner_id).order_by(CommissionLog.created_at.desc()).limit(5)
            
        recent_logs = db.exec(logs_stmt).all()
        
        return {
            "partner_id": partner_id,
            "total_earnings": total_earnings,
            "recent_commissions": recent_logs
        }
