"""
Rental Repository
Data access layer for Rental model
"""
from typing import Optional, List
from datetime import datetime, UTC
from sqlmodel import Session, select
from app.models.rental import Rental
from app.repositories.base_repository import BaseRepository
from pydantic import BaseModel


class RentalCreate(BaseModel):
    user_id: int
    battery_id: int
    start_station_id: int
    start_time: datetime
    expected_end_time: datetime
    total_amount: float


class RentalUpdate(BaseModel):
    status: Optional[str] = None
    end_time: Optional[datetime] = None
    total_amount: Optional[float] = None


class RentalRepository(BaseRepository[Rental, RentalCreate, RentalUpdate]):
    """Rental-specific data access methods"""
    
    def __init__(self):
        super().__init__(Rental)
    
    def get_user_rentals(
        self,
        db: Session,
        user_id: int,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Rental]:
        """Get all rentals for a user"""
        return self.get_multi_by_field(db, "user_id", user_id, skip=skip, limit=limit)
    
    def get_active_rental(self, db: Session, user_id: int) -> Optional[Rental]:
        """Get user's active rental"""
        query = select(Rental).where(
            (Rental.user_id == user_id) &
            (Rental.status == "active")
        )
        return db.exec(query).first()
    
    def get_battery_rentals(
        self,
        db: Session,
        battery_id: int,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Rental]:
        """Get all rentals for a battery"""
        return self.get_multi_by_field(db, "battery_id", battery_id, skip=skip, limit=limit)
    
    def get_overdue_rentals(self, db: Session) -> List[Rental]:
        """Get all overdue rentals (active rentals past their expected end time)"""
        now = datetime.now(UTC)
        query = select(Rental).where(
            (Rental.status == "active") &
            (Rental.expected_end_time < now)
        )
        return list(db.exec(query).all())
    
    def get_by_status(
        self,
        db: Session,
        status: str,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Rental]:
        """Get rentals by status"""
        return self.get_multi_by_field(db, "status", status, skip=skip, limit=limit)


# Singleton instance
rental_repository = RentalRepository()
