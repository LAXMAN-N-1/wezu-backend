from sqlmodel import Session, select, func, and_, desc, extract
from datetime import datetime, UTC, timedelta
from typing import Dict, List, Any

from app.schemas.analytics.customer import CustomerOverviewResponse
from app.schemas.analytics.base import KpiCard, TrendPoint, DistributionPoint
from .base import BaseAnalyticsService
from app.models.rental import Rental
from app.utils.constants import RentalStatus
from app.models.user import User
from app.models.battery import Battery
from app.models.financial import Wallet, Transaction
from app.utils.constants import PaymentStatus # Maybe replace TransactionType logic

class AnalyticsCustomerService(BaseAnalyticsService):
    @staticmethod
    async def get_overview(db: Session, period: str = "30d", customer_id: int = None) -> CustomerOverviewResponse:
        days = BaseAnalyticsService.parse_period(period)
        target_date = datetime.now(UTC) - timedelta(days=days)
        
        c_id = customer_id or 1 # Fallback for now

        # 1. Personal Overview
        user = db.exec(select(User).where(User.id == c_id)).first()
        wallet = db.exec(select(Wallet).where(Wallet.user_id == c_id)).first()
        total_rentals = db.exec(select(func.count(Rental.id)).where(Rental.user_id == c_id)).one() or 0
        active_rental = db.exec(select(Rental).where(Rental.user_id == c_id, Rental.status == RentalStatus.ACTIVE)).first()
        
        personal_overview = {
            "active_rentals": 1 if active_rental else 0,
            "total_rentals": total_rentals,
            "membership_level": "Bronze", # Fallback since membership module is missing
            "wallet_balance": float(wallet.balance) if wallet else 0.0
        }

        # 2. Spending Analytics
        transactions = db.exec(select(Transaction).join(Wallet).where(
            Wallet.user_id == c_id,
            Transaction.created_at >= target_date
        )).all() or 0.0
        
        total_spent = db.exec(select(func.sum(Transaction.amount)).join(Wallet).where(
            Wallet.user_id == c_id,
            Transaction.transaction_type == "RENTAL_PAYMENT",
            Transaction.created_at >= target_date
        )).one() or 0.0
        
        monthly_spent = db.exec(select(func.sum(Transaction.amount)).join(Wallet).where(
            Wallet.user_id == c_id,
            Transaction.status == "success",
            Transaction.created_at >= datetime.now(UTC).replace(day=1)
        )).one() or 0.0

        rental_spending = db.exec(select(func.sum(Transaction.amount)).join(Wallet).where(
            Wallet.user_id == c_id,
            Transaction.transaction_type == "RENTAL_PAYMENT",
            Transaction.status == "success"
        )).one() or 0.0
        
        purchase_spending = db.exec(select(func.sum(Transaction.amount)).join(Wallet).where(
            Wallet.user_id == c_id,
            Transaction.transaction_type == "SUBSCRIPTION",
            Transaction.status == "success"
        )).one() or 0.0

        spending_analytics = {
            "total_amount_spent": float(total_spent),
            "monthly_spending": float(monthly_spent),
            "rental_vs_purchase": {
                "rental": float(rental_spending),
                "purchase": float(purchase_spending)
            }
        }

        # 3. Usage Analytics
        batteries_used = db.exec(select(func.count(func.distinct(Rental.battery_id))).where(Rental.user_id == c_id)).one() or 0
        avg_dur = db.exec(select(func.avg(extract('epoch', Rental.end_time - Rental.start_time) / 3600)).where(
            Rental.user_id == c_id, 
            Rental.status == RentalStatus.COMPLETED
        )).one() or 0
        
        usage_analytics = {
            "total_batteries_used": batteries_used,
            "avg_rental_duration": round(float(avg_dur), 2),
            "most_used_station": "Station Alpha" # Mocked
        }

        # 4. Battery & Energy
        current_battery = None
        if active_rental:
            current_battery = db.exec(select(Battery).where(Battery.id == active_rental.battery_id)).first()
            
        battery_analytics = {
            "health": current_battery.health_status.value if current_battery else "N/A",
            "usage_time_hours": 4.5, # Mocked
            "energy_consumed_kwh": 12.3 # Mocked
        }

        # 5. Environmental Impact
        total_dist = 0.0 # Distance tracking not currently supported by Rental schema
        carbon_saved = total_dist * 0.12 # Assuming 120g/km for ICE
        
        environmental_impact = {
            "carbon_saved_kg": round(float(carbon_saved), 2),
            "energy_consumption_estimate_kwh": round(float(total_dist * 0.05), 2) # proxy 0.05kWh per km
        }

        # 6. Rental History
        history = db.exec(select(Rental).where(Rental.user_id == c_id).order_by(desc(Rental.start_time)).limit(10)).all()
        rental_history = [{
            "id": r.id,
            "cost": float(r.total_amount),
            "duration": "2h 30m", # Mocked formatting
            "timestamp": r.start_time.isoformat()
        } for r in history]

        return CustomerOverviewResponse(
            personal_overview=personal_overview,
            spending_analytics=spending_analytics,
            usage_analytics=usage_analytics,
            battery_analytics=battery_analytics,
            environmental_impact=environmental_impact,
            rental_history=rental_history,
            charts={
                "spending_history": [TrendPoint(x="2024-01", y=500), TrendPoint(x="2024-02", y=750)],
                "rental_usage": [TrendPoint(x="Mon", y=2), TrendPoint(x="Tue", y=1)]
            }
        )

analytics_customer_service = AnalyticsCustomerService()
