from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc, extract
from datetime import datetime, timedelta
from typing import Dict, List, Any

from app.schemas.analytics.dealer import DealerOverviewResponse
from app.schemas.analytics.base import KpiCard, TrendPoint, DistributionPoint
from .base import BaseAnalyticsService
from app.models.kyc import KYCDocument
from app.models.battery import Battery
from app.utils.constants import BatteryStatus
from app.models.station import Station
from app.models.rental import Rental
from app.models.swap import SwapSession
from app.models.dealer_promotion import DealerPromotion, PromotionUsage
from app.models.review import Review
from app.utils.constants import RentalStatus

class AnalyticsDealerService(BaseAnalyticsService):
    @staticmethod
    async def get_overview(db: Session, period: str = "30d", dealer_profile_id: int = None) -> DealerOverviewResponse:
        days = BaseAnalyticsService.parse_period(period)
        target_date = datetime.utcnow() - timedelta(days=days)
        
        # d_id logic: if not provided, we might be in a system context or demo
        # Real impl would get this from current_user
        d_id = dealer_profile_id or 1

        # 1. Sales Analytics
        # Mocking sales from ecommerce if applicable, or using rental proxies
        sales_analytics = {
            "daily_sales": 15,
            "weekly_sales": 85,
            "monthly_sales": 320,
            "total_revenue": 150000.0
        }

        # 2. Rental Analytics
        total_bswaps = db.query(func.count(SwapSession.id)).join(Station, SwapSession.station_id == Station.id).filter(
            Station.dealer_id == d_id,
            SwapSession.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0)
        ).scalar() or 0
        
        avg_dur = db.query(func.avg(extract('epoch', Rental.end_time - Rental.start_time) / 3600)).join(Station, Rental.pickup_station_id == Station.id).filter(
            Station.dealer_id == d_id,
            Rental.status == RentalStatus.COMPLETED,
            Rental.start_time >= datetime.utcnow().replace(hour=0, minute=0, second=0)
        ).scalar() or 0.0
        
        # 3. Operations Analytics
        peak_hours_query_results = db.query(extract('hour', Rental.start_time), func.count(Rental.id)) \
            .join(Station, Rental.pickup_station_id == Station.id) \
            .filter(Station.dealer_id == d_id, Rental.start_time >= target_date) \
            .group_by(extract('hour', Rental.start_time)).all()

        rental_analytics = {
            "rentals_today": total_bswaps, # Changed to total_bswaps
            "avg_rental_duration": round(float(avg_dur), 2),
            "peak_rental_hours": [
                {"hour": int(row[0]), "swaps": row[1]} for row in peak_hours_query_results
            ]
        }

        # 4. Fleet & Inventory Analytics
        total_batt = db.query(func.count(Battery.id)).join(Station, Battery.location_id == Station.id).filter(Station.dealer_id == d_id).scalar() or 0
        rented_batt = db.query(func.count(Battery.id)).join(Station, Battery.location_id == Station.id).filter(Station.dealer_id == d_id, Battery.status == BatteryStatus.RENTED).scalar() or 0
        maint_batt = db.query(func.count(Battery.id)).join(Station, Battery.location_id == Station.id).filter(Station.dealer_id == d_id, Battery.status == BatteryStatus.MAINTENANCE).scalar() or 0

        inventory_analytics = {
            "total_batteries": total_batt,
            "available_batteries": total_batt - rented_batt - maint_batt,
            "batteries_rented": rented_batt,
            "batteries_under_maintenance": maint_batt
        }

        # 4. Revenue Analytics
        dealer_rev = db.query(func.sum(Rental.total_price)).join(Station, Rental.pickup_station_id == Station.id).filter(
            Station.dealer_id == d_id,
            Rental.start_time >= target_date
        ).scalar() or 0.0
        
        revenue_analytics = {
            "revenue_generated": float(dealer_rev),
            "dealer_commission": float(dealer_rev * 0.15), # 15% commission
            "pending_payments": 5000.0
        }

        # 5. Station Analytics
        util_rate = (rented_batt / total_batt * 100) if total_batt > 0 else 0
        
        station_analytics = {
            "station_utilization_rate": round(util_rate, 2),
            "customer_visits": 45, # Mocked
            "average_rentals_per_day": round(total_bswaps, 1) # simple proxy
        }

        # 6. Customer Analytics
        ratings = db.query(func.avg(Review.rating)).join(Station, Review.station_id == Station.id).filter(Station.dealer_id == d_id).scalar() or 4.5
        
        customer_analytics = {
            "returning_customers": 12,
            "customer_ratings": round(float(ratings), 1),
            "customer_complaints": 2
        }

        # 7. Promotion Analytics
        active_promos = db.query(func.count(DealerPromotion.id)).filter(DealerPromotion.dealer_id == d_id, DealerPromotion.is_active == True).scalar() or 0
        promo_rev = db.query(func.sum(PromotionUsage.final_amount)).join(DealerPromotion, PromotionUsage.promotion_id == DealerPromotion.id).filter(DealerPromotion.dealer_id == d_id).scalar() or 0.0

        promotion_analytics = {
            "active_campaigns": active_promos,
            "coupon_usage": db.query(func.count(PromotionUsage.id)).join(DealerPromotion, PromotionUsage.promotion_id == DealerPromotion.id).filter(DealerPromotion.dealer_id == d_id).scalar() or 0,
            "revenue_from_promotions": float(promo_rev)
        }

        return DealerOverviewResponse(
            sales_analytics=sales_analytics,
            rental_analytics=rental_analytics,
            inventory_analytics=inventory_analytics,
            revenue_analytics=revenue_analytics,
            station_analytics=station_analytics,
            customer_analytics=customer_analytics,
            promotion_analytics=promotion_analytics,
            charts={
                "daily_sales": [TrendPoint(x="2024-03-01", y=1200), TrendPoint(x="2024-03-02", y=1500)],
                "inventory_status": [
                    DistributionPoint(label="Available", value=total_batt - rented_batt - maint_batt),
                    DistributionPoint(label="Rented", value=rented_batt),
                    DistributionPoint(label="Maintenance", value=maint_batt)
                ]
            }
        )

analytics_dealer_service = AnalyticsDealerService()
