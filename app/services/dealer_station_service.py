"""
Dealer Station Service — Handles dealer operations for stations, inventory, alerts and maintenance.
"""

from sqlmodel import Session, select, func
from fastapi import HTTPException
from datetime import datetime, UTC
from typing import List, Dict, Any

from app.models.station import Station, StationSlot
from app.models.dealer_inventory import DealerInventory
from app.models.maintenance import StationDowntime

import logging

logger = logging.getLogger(__name__)


class DealerStationService:

    # ─── Station Submission ───

    @staticmethod
    def submit_station(db: Session, dealer_id: int, schema_data: dict) -> Station:
        """Create a new station for a dealer with pending status."""
        station = Station(
            **schema_data,
            dealer_id=dealer_id,
            approval_status="pending",
            status="inactive",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        db.add(station)
        db.commit()
        db.refresh(station)
        return station

    @staticmethod
    def get_dealer_station(db: Session, station_id: int, dealer_id: int) -> Station:
        """Fetch a specific station, ensuring it belongs to the dealer."""
        station = db.exec(
            select(Station).where(
                Station.id == station_id,
                Station.dealer_id == dealer_id
            )
        ).first()
        if not station:
            raise HTTPException(status_code=404, detail="Station not found")
        return station

    # ─── Inventory Rules & Hours ───

    @staticmethod
    def update_inventory_rules(db: Session, station_id: int, dealer_id: int, threshold_pct: float) -> Station:
        """Update low stock alert threshold for a station."""
        station = DealerStationService.get_dealer_station(db, station_id, dealer_id)
        station.low_stock_threshold_pct = threshold_pct
        db.add(station)
        db.commit()
        db.refresh(station)
        return station

    @staticmethod
    def update_opening_hours(db: Session, station_id: int, dealer_id: int, hours: str) -> Station:
        """Update opening hours for a station."""
        station = DealerStationService.get_dealer_station(db, station_id, dealer_id)
        station.opening_hours = hours # Format expected: "09:00-18:00" etc
        db.add(station)
        db.commit()
        db.refresh(station)
        return station

    # ─── Battery Monitoring ───

    @staticmethod
    def get_station_batteries(db: Session, station_id: int, dealer_id: int, health_status: str = None) -> List[dict]:
        """View all batteries currently slotted at a specific station."""
        # Ensure station belongs to dealer
        DealerStationService.get_dealer_station(db, station_id, dealer_id)
        
        from app.models.battery import Battery
        
        query = (
            select(Battery, StationSlot.slot_number)
            .join(StationSlot, StationSlot.battery_id == Battery.id)
            .where(StationSlot.station_id == station_id)
        )
             
        results = db.exec(query).all()
        
        batteries = []
        for battery, slot_num in results:
             health_stat = "good" if battery.health_percentage > 80 else "degraded" if battery.health_percentage > 50 else "damaged"
             
             if health_status and health_stat != health_status.lower():
                 continue # Manual filter if requested
                 
             batteries.append({
                 "id": battery.id,
                 "serial_number": battery.serial_number,
                 "current_charge": battery.current_charge,
                 "health_percentage": battery.health_percentage,
                 "health_status": health_stat,
                 "cycle_count": battery.cycle_count,
                 "slot_number": slot_num,
                 "status": battery.status
             })
        return batteries

    @staticmethod
    def get_low_inventory_alerts(db: Session, dealer_id: int) -> List[dict]:
        """Generate alerts for stations where total available batteries drop below threshold."""
        stations = db.exec(
            select(Station).where(Station.dealer_id == dealer_id)
        ).all()
        
        alerts = []
        
        from app.models.battery import Battery
        
        for station in stations:
             # Calculate total slotted batteries with sufficient SOC and health
             ready_batteries_count = db.exec(
                 select(func.count(StationSlot.id))
                 .join(Battery, StationSlot.battery_id == Battery.id)
                 .where(
                     StationSlot.station_id == station.id,
                     Battery.current_charge > 20, # arbitrary definition of "available"
                     Battery.health_percentage > 80 # "good" health
                 )
             ).one()
             
             total_slots = getattr(station, "total_slots", 0)
             if total_slots == 0:
                  continue
                  
             current_pct = (ready_batteries_count / total_slots) * 100
             threshold = getattr(station, "low_stock_threshold_pct", 20.0)
             
             if current_pct < threshold:
                  alerts.append({
                      "station_id": station.id,
                      "station_name": station.name,
                      "current_available_pct": round(current_pct, 1),
                      "threshold_pct": threshold,
                      "available_count": ready_batteries_count,
                      "total_slots": total_slots,
                      "message": f"Inventory critically low. {ready_batteries_count} left ({round(current_pct, 1)}%)"
                  })
                  
        return alerts

    # ─── Maintenance ───

    @staticmethod
    def schedule_maintenance(db: Session, station_id: int, dealer_id: int, data: dict) -> StationDowntime:
        """Schedule future downtime for a station."""
        # Ensure dealership
        DealerStationService.get_dealer_station(db, station_id, dealer_id)
        
        start_time = data["start_time"] # expected datetime object
        end_time = data.get("end_time") # expected datetime object
        
        # Prevent overlapping downtimes
        overlap_query = select(StationDowntime).where(
             StationDowntime.station_id == station_id,
             StationDowntime.start_time < (end_time if end_time else datetime.max),
             (StationDowntime.end_time > start_time) if end_time else True
        )
        if db.exec(overlap_query).first():
             raise HTTPException(status_code=400, detail="Maintenance schedule overlaps with existing downtime")

        downtime = StationDowntime(
            station_id=station_id,
            start_time=start_time,
            end_time=end_time,
            reason=data["reason"]
        )
        db.add(downtime)
        db.commit()
        db.refresh(downtime)
        return downtime

    @staticmethod
    def is_station_operational(db: Session, station_id: int) -> tuple[bool, str]:
        """Check if station is within hours and not down for maintenance. Used by swap checkout."""
        station = db.get(Station, station_id)
        if not station:
            return False, "Station not found"
            
        now = datetime.now(UTC)
        
        # 1. Check Maintenance
        downtime = db.exec(
            select(StationDowntime).where(
                StationDowntime.station_id == station_id,
                StationDowntime.start_time <= now,
                (StationDowntime.end_time >= now) | (StationDowntime.end_time == None)
            )
        ).first()
        
        if downtime:
             return False, f"Station under maintenance: {downtime.reason}"
             
        # 2. Check Opening Hours
        if station.opening_hours:
             try:
                 # Format: "09:00-18:00"
                 start_str, end_str = station.opening_hours.split("-")
                 start_hour, start_min = map(int, start_str.split(":"))
                 end_hour, end_min = map(int, end_str.split(":"))
                 
                 # Note: this is a simple UTC comparison. Real world would use station timezone.
                 current_time = now.time()
                 start_time = now.replace(hour=start_hour, minute=start_min, second=0).time()
                 end_time = now.replace(hour=end_hour, minute=end_min, second=0).time()
                 
                 if current_time < start_time or current_time > end_time:
                      return False, "Station is currently closed outside of operating hours"
             except Exception:
                 logger.warning("dealer_station.operating_hours_parse_failed", exc_info=True)
                 
        return True, "Operational"

