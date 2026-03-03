from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from app.schemas.analytics.customer import CustomerOverviewResponse
from .base import BaseAnalyticsService
from app.models.rental import Rental, RentalStatus
from app.models.user import User
from app.models.battery import Battery

class AnalyticsCustomerService(BaseAnalyticsService):
    @staticmethod
    async def get_overview(db: Session, period: str = "30d", customer_id: int = None) -> CustomerOverviewResponse:
        days = BaseAnalyticsService.parse_period(period)
        target_date_ago = datetime.utcnow() - timedelta(days=days)
        
        # Mock customer ID if not provided by fastAPI router
        c_id = customer_id or 1
        
        # 1. Ride Status (Fetching the active rental for the user)
        active_rental = db.query(Rental).filter(Rental.user_id == c_id, Rental.status == RentalStatus.ACTIVE).first()
        current_range = 0
        battery_health = "unknown"
        
        if active_rental:
            battery = db.query(Battery).filter(Battery.id == active_rental.battery_id).first()
            if battery:
                current_range = battery.current_charge * 0.8 # Rough proxy 1% = 0.8km
                battery_health = battery.health_status
                
        # 2. Savings (Distance traveled * Petrol cost proxy within period)
        total_distance = db.query(func.sum(Rental.distance_traveled_km)).filter(Rental.user_id == c_id, Rental.created_at >= target_date_ago).scalar() or 0.0
        petrol_savings = total_distance * 2.5 # Assuming EV saves 2.5 INR per KM vs petrol
        
        return CustomerOverviewResponse(
            ride_status={"current_range": round(current_range, 1), "battery_health": battery_health},
            gamification={"eco_score": 100}, # Setup for ML scoring later
            savings={"money_saved": BaseAnalyticsService.format_kpi_card(round(petrol_savings, 0), petrol_savings, petrol_savings * 0.9)}
        )

analytics_customer_service = AnalyticsCustomerService()
