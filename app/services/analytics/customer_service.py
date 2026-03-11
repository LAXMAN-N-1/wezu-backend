from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc, extract
from datetime import datetime, timedelta
from typing import Dict, List, Any

from app.schemas.analytics.customer import CustomerOverviewResponse
from app.schemas.analytics.base import KpiCard, TrendPoint, DistributionPoint
from .base import BaseAnalyticsService
from app.models.rental import Rental, RentalStatus
from app.models.user import User
from app.models.battery import Battery
from app.models.membership import UserMembership, MembershipTier
from app.models.financial import Wallet, Transaction, TransactionType

class AnalyticsCustomerService(BaseAnalyticsService):
    @staticmethod
    async def get_overview(db: Session, period: str = "30d", customer_id: int = None) -> CustomerOverviewResponse:
        days = BaseAnalyticsService.parse_period(period)
        target_date = datetime.utcnow() - timedelta(days=days)
        
        c_id = customer_id or 1 # Fallback for now

        # 1. Personal Overview
        user = db.query(User).filter(User.id == c_id).first()
        membership = db.query(UserMembership).filter(UserMembership.user_id == c_id).first()
        wallet = db.query(Wallet).filter(Wallet.user_id == c_id).first()
        total_rentals = db.query(func.count(Rental.id)).filter(Rental.user_id == c_id).scalar() or 0
        active_rental = db.query(Rental).filter(Rental.user_id == c_id, Rental.status == RentalStatus.ACTIVE).first()
        
        personal_overview = {
            "active_rentals": 1 if active_rental else 0,
            "total_rentals": total_rentals,
            "membership_level": membership.tier.value if membership else MembershipTier.BRONZE.value,
            "wallet_balance": float(wallet.balance) if wallet else 0.0
        }

        # 2. Spending Analytics
        total_spent = db.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == c_id, 
            Transaction.status == "success"
        ).scalar() or 0.0
        
        monthly_spent = db.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == c_id,
            Transaction.status == "success",
            Transaction.created_at >= datetime.utcnow().replace(day=1)
        ).scalar() or 0.0

        rental_spending = db.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == c_id,
            Transaction.transaction_type == TransactionType.RENTAL_PAYMENT,
            Transaction.status == "success"
        ).scalar() or 0.0
        
        purchase_spending = db.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == c_id,
            Transaction.transaction_type == TransactionType.PURCHASE,
            Transaction.status == "success"
        ).scalar() or 0.0

        spending_analytics = {
            "total_amount_spent": float(total_spent),
            "monthly_spending": float(monthly_spent),
            "rental_vs_purchase": {
                "rental": float(rental_spending),
                "purchase": float(purchase_spending)
            }
        }

        # 3. Usage Analytics
        batteries_used = db.query(func.count(func.distinct(Rental.battery_id))).filter(Rental.user_id == c_id).scalar() or 0
        avg_dur = db.query(func.avg(extract('epoch', Rental.end_time - Rental.start_time) / 3600)).filter(
            Rental.user_id == c_id, 
            Rental.status == RentalStatus.COMPLETED
        ).scalar() or 0
        
        usage_analytics = {
            "total_batteries_used": batteries_used,
            "avg_rental_duration": round(float(avg_dur), 2),
            "most_used_station": "Station Alpha" # Mocked
        }

        # 4. Battery & Energy
        current_battery = None
        if active_rental:
            current_battery = db.query(Battery).filter(Battery.id == active_rental.battery_id).first()
            
        battery_analytics = {
            "health": current_battery.health_status.value if current_battery else "N/A",
            "usage_time_hours": 4.5, # Mocked
            "energy_consumed_kwh": 12.3 # Mocked
        }

        # 5. Environmental Impact
        total_dist = db.query(func.sum(Rental.distance_traveled_km)).filter(Rental.user_id == c_id).scalar() or 0.0
        carbon_saved = total_dist * 0.12 # Assuming 120g/km for ICE
        
        environmental_impact = {
            "carbon_saved_kg": round(float(carbon_saved), 2),
            "energy_consumption_estimate_kwh": round(float(total_dist * 0.05), 2) # proxy 0.05kWh per km
        }

        # 6. Rental History
        history = db.query(Rental).filter(Rental.user_id == c_id).order_by(desc(Rental.created_at)).limit(10).all()
        rental_history = [{
            "id": r.id,
            "cost": float(r.total_amount),
            "duration": "2h 30m", # Mocked formatting
            "timestamp": r.created_at.isoformat()
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
