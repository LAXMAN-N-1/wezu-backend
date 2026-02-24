from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Dict
from sqlmodel import Session, select
from app.models.battery_reservation import BatteryReservation

class DemandPredictor(ABC):
    @abstractmethod
    def predict_demand(self, db: Session, station_id: int, start_time: datetime, end_time: datetime) -> float:
        """
        Predict demand (number of batteries needed) for a station in a given time window.
        Returns a probability or a predicted count.
        """
        pass

class MockDemandPredictor(DemandPredictor):
    def predict_demand(self, db: Session, station_id: int, start_time: datetime, end_time: datetime) -> float:
        """
        Mock implementation:
        1. Count actual reservations in the window.
        2. Add a base demand score based on time of day (Heuristic).
        """
        # 1. Actual Reservations
        stmt = select(BatteryReservation).where(
            BatteryReservation.station_id == station_id,
            BatteryReservation.status == "PENDING",
            BatteryReservation.start_time <= end_time,
            BatteryReservation.end_time >= start_time
        )
        reservations = db.exec(stmt).all()
        reservation_count = len(reservations)
        
        # 2. Heuristic: Peak hours (8-10 AM, 5-7 PM) have higher base demand
        hour = start_time.hour
        base_demand = 0.5 # Default low demand
        if 8 <= hour <= 10 or 17 <= hour <= 19:
            base_demand = 2.0 # High demand
            
        return float(reservation_count) + base_demand
