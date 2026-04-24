from __future__ import annotations
from sqlmodel import Session, select
from app.models.driver_profile import DriverProfile
from datetime import datetime, timezone; UTC = timezone.utc
from typing import List

import logging

logger = logging.getLogger(__name__)


class DriverService:
    
    @staticmethod
    def get_profile(db: Session, user_id: int) -> DriverProfile:
        return db.exec(select(DriverProfile).where(DriverProfile.user_id == user_id)).first()

    @staticmethod
    def create_profile(db: Session, user_id: int, data: dict) -> DriverProfile:
        profile = DriverProfile(user_id=user_id, **data)
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile

    @staticmethod
    def update_location(db: Session, driver_id: int, lat: float, lng: float):
        driver = db.get(DriverProfile, driver_id)
        if driver:
            driver.current_latitude = lat
            driver.current_longitude = lng
            driver.last_location_update = datetime.now(UTC)
            db.add(driver)
            db.commit()

    @staticmethod
    def toggle_status(db: Session, driver_id: int, is_online: bool):
        driver = db.get(DriverProfile, driver_id)
        if driver:
            driver.is_online = is_online
            db.add(driver)
            db.commit()

    @staticmethod
    def get_driver_performance(db: Session, driver_id: int) -> dict:
        """Calculate real-time KPIs for a driver"""
        driver = db.get(DriverProfile, driver_id)
        if not driver:
            return {}
            
        on_time_rate = (driver.on_time_deliveries / driver.total_deliveries * 100) if driver.total_deliveries > 0 else 100.0
        avg_time = (driver.total_delivery_time_seconds / driver.total_deliveries / 60) if driver.total_deliveries > 0 else 0.0
        satisfaction = (driver.satisfaction_sum / driver.total_deliveries) if driver.total_deliveries > 0 else 5.0
        
        return {
            "driver_id": driver_id,
            "on_time_rate": round(on_time_rate, 2),
            "avg_delivery_time_minutes": round(avg_time, 2),
            "satisfaction_score": round(satisfaction, 2)
        }

    @staticmethod
    def get_driver_dashboard_stats(db: Session, driver_id: int) -> dict:
        """
        Driver dashboard aggregate for today's load and overall execution stats.
        """
        from app.models.logistics import DeliveryOrder

        driver = db.get(DriverProfile, driver_id)
        if not driver:
            return {
                "driver_id": driver_id,
                "total_jobs": 0,
                "today_jobs": 0,
                "active_jobs": 0,
                "completed_jobs": 0,
                "rating": 0.0,
                "total_earnings": 0.0,
                "on_time_rate": 0.0,
                "avg_delivery_time_minutes": 0.0,
                "satisfaction_score": 0.0,
            }

        orders = db.exec(
            select(DeliveryOrder).where(DeliveryOrder.assigned_driver_id == driver.user_id)
        ).all()
        today = datetime.now(UTC).date()

        def _status_value(order_status) -> str:
            if hasattr(order_status, "value"):
                return str(order_status.value).lower()
            return str(order_status).lower()

        total_jobs = len(orders)
        completed_jobs = sum(1 for o in orders if _status_value(o.status) == "delivered")
        active_jobs = sum(1 for o in orders if _status_value(o.status) in {"assigned", "in_transit"})
        today_jobs = 0
        for order in orders:
            anchor = order.scheduled_at or order.created_at
            if anchor and anchor.date() == today:
                today_jobs += 1

        perf = DriverService.get_driver_performance(db, driver_id)

        # Earnings are deployment-specific; default to zero unless payout data is available.
        earnings_per_delivery = float(getattr(driver, "payout_per_delivery", 0.0) or 0.0)
        total_earnings = round(completed_jobs * earnings_per_delivery, 2)

        return {
            "driver_id": driver.id,
            "user_id": driver.user_id,
            "is_online": bool(driver.is_online),
            "rating": round(float(driver.rating or 0.0), 2),
            "total_jobs": total_jobs,
            "today_jobs": today_jobs,
            "active_jobs": active_jobs,
            "completed_jobs": completed_jobs,
            "total_earnings": total_earnings,
            "on_time_rate": perf.get("on_time_rate", 0.0),
            "avg_delivery_time_minutes": perf.get("avg_delivery_time_minutes", 0.0),
            "satisfaction_score": perf.get("satisfaction_score", 0.0),
        }
