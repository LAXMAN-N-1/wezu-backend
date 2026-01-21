"""
Battery Repository
Data access layer for Battery model
"""
from typing import Optional, List
from sqlmodel import Session, select
from app.models.battery import Battery
from app.repositories.base_repository import BaseRepository
from pydantic import BaseModel


class BatteryCreate(BaseModel):
    serial_number: str
    model: str
    capacity_ah: float
    status: str = "available"


class BatteryUpdate(BaseModel):
    status: Optional[str] = None
    current_charge: Optional[float] = None
    health_percentage: Optional[float] = None


class BatteryRepository(BaseRepository[Battery, BatteryCreate, BatteryUpdate]):
    """Battery-specific data access methods"""
    
    def __init__(self):
        super().__init__(Battery)
    
    def get_by_serial(self, db: Session, serial_number: str) -> Optional[Battery]:
        """Get battery by serial number"""
        return self.get_by_field(db, "serial_number", serial_number)
    
    def get_available_batteries(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Battery]:
        """Get all available batteries"""
        query = select(Battery).where(
            Battery.status == "available"
        ).offset(skip).limit(limit)
        return list(db.exec(query).all())
    
    def get_by_status(
        self,
        db: Session,
        status: str,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Battery]:
        """Get batteries by status"""
        return self.get_multi_by_field(db, "status", status, skip=skip, limit=limit)
    
    def get_low_health_batteries(
        self,
        db: Session,
        threshold: float = 70.0,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Battery]:
        """Get batteries with health below threshold"""
        query = select(Battery).where(
            Battery.health_percentage < threshold
        ).offset(skip).limit(limit)
        return list(db.exec(query).all())
    
    def get_by_model(
        self,
        db: Session,
        model: str,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Battery]:
        """Get batteries by model"""
        return self.get_multi_by_field(db, "model", model, skip=skip, limit=limit)


# Singleton instance
battery_repository = BatteryRepository()
