from sqlmodel import Session, select
from app.models.battery import Battery
from app.models.battery_reservation import BatteryReservation
from app.schemas.station_monitoring import OptimizedQueueItem, OptimizationBattery
from app.services.demand_predictor import MockDemandPredictor
from datetime import datetime, UTC, timedelta
from typing import List, Optional

class ChargingService:
    @staticmethod
    def get_energy_cost_multiplier() -> float:
        """
        Simple energy cost multiplier based on time of day.
        Off-peak (11 PM - 6 AM): 0.5
        Peak (6 PM - 10 PM): 1.5
        Standard: 1.0
        """
        now = datetime.now(UTC)
        hour = now.hour
        if 23 <= hour or hour <= 6:
            return 0.5
        if 18 <= hour <= 22:
            return 1.5
        return 1.0

    @staticmethod
    def prioritize_charging(db: Session, station_id: int, batteries: List[OptimizationBattery]) -> List[OptimizedQueueItem]:
        """
        Comprehensive Prioritization Logic:
        Factor in Demand, Health, Cycles, and Energy Costs.
        """
        predictor = MockDemandPredictor()
        demand_score = predictor.predict_demand(db, station_id, datetime.now(UTC), datetime.now(UTC) + timedelta(hours=2))
        energy_multiplier = ChargingService.get_energy_cost_multiplier()
        
        items = []
        for b in batteries:
            # 1. Base Score (Need for charge)
            base_score = (100 - b.current_charge) * 0.5
            
            # 2. Health & Cycles Factor (Higher SOH preferred for fast turnover)
            health_score = (b.state_of_health * 0.2)
            
            # 3. Reservation Factor (Urgency)
            # Check if this specific battery is reserved in the next 2 hours
            stmt = select(BatteryReservation).where(
                BatteryReservation.battery_id == b.battery_id,
                BatteryReservation.status == "PENDING",
                BatteryReservation.start_time <= datetime.now(UTC) + timedelta(hours=2)
            )
            reservation = db.exec(stmt).first()
            reservation_boost = 1000 if reservation else 0
            
            # 4. Energy Cost Factor
            # If energy is expensive, lower the priority for non-urgent batteries
            if energy_multiplier > 1.0 and reservation_boost == 0:
                base_score *= 0.5 
            
            final_score = base_score + health_score + reservation_boost + (demand_score * 10)
            
            items.append({
                "battery_id": b.battery_id,
                "score": final_score
            })
        
        # Build battery mapping for SOC lookups
        battery_map = {b.battery_id: b for b in batteries}
        
        # Sort by score descending
        sorted_items = sorted(items, key=lambda x: x['score'], reverse=True)
        
        result = []
        for i, item in enumerate(sorted_items):
            battery = battery_map[item['battery_id']]
            needed_charge = max(0, 100 - battery.current_charge)
            
            # Dynamic calculation: 1.5 minutes per 1% charge needed
            # Plus 5 minutes base wait time per slot queuing
            est_minutes = (needed_charge * 1.5) + (5 * i)
            
            est_time = datetime.now(UTC) + timedelta(minutes=est_minutes)
            
            result.append(OptimizedQueueItem(
                battery_id=item['battery_id'],
                priority_score=item['score'],
                queue_position=i + 1,
                estimated_completion_time=est_time
            ))
        
        return result

    @staticmethod
    def get_charging_queue(db: Session, station_id: int) -> List[OptimizedQueueItem]:
        # In a real scenario, this would look up current assignments in the database
        # For now, we'll list batteries currently at the station and rank them
        from app.models.station import StationSlot
        slots = db.exec(select(StationSlot).where(StationSlot.station_id == station_id, StationSlot.status == "charging")).all()
        
        opt_batteries = []
        for slot in slots:
            if slot.battery:
                opt_batteries.append(OptimizationBattery(
                    battery_id=str(slot.battery.id),
                    current_charge=slot.battery.current_charge,
                    state_of_health=slot.battery.health_percentage
                ))
        
        if not opt_batteries:
            return []
            
        return ChargingService.prioritize_charging(db, station_id, opt_batteries)

    @staticmethod
    def reprioritize_queue(db: Session, station_id: int, urgent_ids: List[str]) -> List[OptimizedQueueItem]:
        # Urgent batteries get a massive score boost
        queue = ChargingService.get_charging_queue(db, station_id)
        for item in queue:
            if item.battery_id in urgent_ids:
                item.priority_score += 1000
        
        # Re-sort
        sorted_queue = sorted(queue, key=lambda x: x.priority_score, reverse=True)
        for i, item in enumerate(sorted_queue):
            item.queue_position = i + 1
            
        return sorted_queue
