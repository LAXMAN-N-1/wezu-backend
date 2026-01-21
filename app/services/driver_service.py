from sqlmodel import Session, select
from app.core.database import engine
from app.models.logistics import DriverProfile
from datetime import datetime
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
                driver.last_location_update = datetime.utcnow()
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
    def find_nearby_drivers(lat: float, lng: float, radius_km: float = 10.0) -> List[DriverProfile]:
        # Simple bounding box or just return all online drivers for now
        with Session(engine) as session:
            # In production, use PostGIS or Haversine filter
            drivers = session.exec(select(DriverProfile).where(DriverProfile.is_online == True)).all()
            return drivers
