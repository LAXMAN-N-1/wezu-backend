from sqlmodel import Session, select, func
from app.models.financial import Transaction, Wallet
from app.models.rental import Rental
from datetime import datetime, timedelta
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)

class AnalyticsService:
    @staticmethod
    def get_user_dashboard_stats(db: Session, user_id: int) -> Dict[str, Any]:
        """
        Get aggregated stats for the user dashboard.
        """
        # 1. Total Spent this month
        first_day_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        wallet = db.exec(select(Wallet).where(Wallet.user_id == user_id)).first()
        if not wallet:
            return {"error": "Wallet not found"}

        spent_stmt = select(func.sum(Transaction.amount)).where(
            Transaction.wallet_id == wallet.id,
            Transaction.type == "debit",
            Transaction.created_at >= first_day_of_month
        )
        total_spent_month = db.exec(spent_stmt).one() or 0.0

        # 2. Active Rentals Count
        active_rentals_stmt = select(func.count(Rental.id)).where(
            Rental.user_id == user_id,
            Rental.status == "active"
        )
        active_rentals_count = db.exec(active_rentals_stmt).one() or 0

        # 3. Total Rentals Lifetime
        total_rentals_stmt = select(func.count(Rental.id)).where(Rental.user_id == user_id)
        total_rentals_count = db.exec(total_rentals_stmt).one() or 0

        # 4. Carbon Saved Calculation (Estimated)
        # Assuming 1 hour of EV battery usage saves 0.5kg of CO2 vs traditional fuel alternatives
        total_hours_stmt = select(func.sum(Rental.rental_duration_days * 24)).where(Rental.user_id == user_id)
        total_hours = db.exec(total_hours_stmt).one() or 0
        carbon_saved_kg = total_hours * 0.5

        return {
            "total_spent_this_month": abs(total_spent_month),
            "active_rentals": active_rentals_count,
            "total_rentals_lifetime": total_rentals_count,
            "carbon_saved_kg": carbon_saved_kg,
            "wallet_balance": wallet.balance
        }

    @staticmethod
    def get_spending_trend(db: Session, user_id: int, months: int = 6) -> List[Dict[str, Any]]:
        """
        Get monthly spending trend for the last N months.
        """
        wallet = db.exec(select(Wallet).where(Wallet.user_id == user_id)).first()
        if not wallet:
            return []

        trend = []
        for i in range(months - 1, -1, -1):
            date_ptr = datetime.utcnow() - timedelta(days=i*30)
            start_of_month = date_ptr.replace(day=1, hour=0, minute=0, second=0)
            if i == 0:
                end_of_month = datetime.utcnow()
            else:
                end_of_month = (start_of_month + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)

            spent_stmt = select(func.sum(Transaction.amount)).where(
                Transaction.wallet_id == wallet.id,
                Transaction.type == "debit",
                Transaction.created_at >= start_of_month,
                Transaction.created_at <= end_of_month
            )
            monthly_total = db.exec(spent_stmt).one() or 0.0
            
    @staticmethod
    def get_customer_dashboard(user_id: int, db: Session) -> Dict[str, Any]:
        """Get consolidated dashboard data"""
        stats = AnalyticsService.get_user_dashboard_stats(db, user_id)
        # Add a few more quick links/stats
        stats["recent_transactions"] = [] # Placeholder or fetch last 3
        return stats

    @staticmethod
    def get_rental_history_stats(user_id: int, db: Session) -> Dict[str, Any]:
        """Get stats for rental history screen"""
        total_rentals = db.exec(select(func.count(Rental.id)).where(Rental.user_id == user_id)).one() or 0
        avg_duration = db.exec(select(func.avg(Rental.rental_duration_days)).where(Rental.user_id == user_id)).one() or 0.0
        
        return {
            "total_rentals": total_rentals,
            "average_duration_days": round(float(avg_duration), 1),
            "completed_rentals": db.exec(select(func.count(Rental.id)).where(Rental.user_id == user_id, Rental.status == "completed")).one() or 0
        }

    @staticmethod
    def get_cost_analytics(user_id: int, months: int, db: Session) -> Dict[str, Any]:
        """Get cost analytics for charts"""
        trend = AnalyticsService.get_spending_trend(db, user_id, months)
        
        # Calculate breakdown (Rental vs Purchase)
        wallet = db.exec(select(Wallet).where(Wallet.user_id == user_id)).first()
        breakdown = {"rentals": 0.0, "purchases": 0.0, "others": 0.0}
        
        if wallet:
            txns = db.exec(select(Transaction).where(Transaction.wallet_id == wallet.id, Transaction.type == "debit")).all()
            for t in txns:
                if t.category == "rental_payment" or "swap" in (t.description or "").lower():
                    breakdown["rentals"] += abs(t.amount)
                elif "purchase" in (t.description or "").lower():
                    breakdown["purchases"] += abs(t.amount)
                else:
                    breakdown["others"] += abs(t.amount)

        return {
            "monthly_trend": trend,
            "category_breakdown": breakdown
        }

    @staticmethod
    def get_usage_patterns(user_id: int, db: Session) -> Dict[str, Any]:
        """Analyze usage patterns"""
        # Simple analysis of rentals
        rentals = db.exec(select(Rental).where(Rental.user_id == user_id)).all()
        
        day_freq = {}
        for r in rentals:
            day = r.start_time.strftime("%A")
            day_freq[day] = day_freq.get(day, 0) + 1
            
        most_active_day = max(day_freq, key=day_freq.get) if day_freq else "N/A"
        
        return {
            "most_active_day": most_active_day,
            "rental_frequency": day_freq,
            "avg_rental_duration_hours": round(float(len(rentals)) * 24 / max(len(rentals), 1), 1) # Mock logic
        }
