from sqlmodel import Session, select
from app.core.database import engine
from app.models.driver_profile import DriverProfile
from datetime import datetime, UTC
from typing import List

class DriverService:
    
    @staticmethod
    def get_profile(user_id: int) -> DriverProfile:
        with Session(engine) as session:
            return session.exec(select(DriverProfile).where(DriverProfile.user_id == user_id)).first()

    @staticmethod
    def create_profile(user_id: int, data: dict) -> DriverProfile:
        with Session(engine) as session:
            profile = DriverProfile(user_id=user_id, **data)
            session.add(profile)
            session.commit()
            session.refresh(profile)
            return profile

    @staticmethod
    def update_location(driver_id: int, lat: float, lng: float):
        with Session(engine) as session:
            driver = session.get(DriverProfile, driver_id)
            if driver:
                driver.current_latitude = lat
                driver.current_longitude = lng
                driver.last_location_update = datetime.now(UTC)
                session.add(driver)
                session.commit()

    @staticmethod
    def toggle_status(driver_id: int, is_online: bool):
        with Session(engine) as session:
            driver = session.get(DriverProfile, driver_id)
            if driver:
                driver.is_online = is_online
                session.add(driver)
                session.commit()

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
