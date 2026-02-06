from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlmodel import Session, select
from app.models.battery import Battery
from app.models.battery_health_log import BatteryHealthLog

class FeatureStore:
    @staticmethod
    def get_battery_features(db: Session, battery_id: int) -> Dict[str, Any]:
        """
        Extract features for battery health prediction.
        """
        battery = db.get(Battery, battery_id)
        if not battery:
            return {}
            
        # Recent logs
        since = datetime.utcnow() - timedelta(days=30)
        logs = db.exec(select(BatteryHealthLog).where(
            BatteryHealthLog.battery_id == battery_id,
            BatteryHealthLog.timestamp >= since
        )).all()
        
        avg_temp = sum(l.temperature for l in logs) / len(logs) if logs else 30.0
        voltage_drop = (logs[0].voltage - logs[-1].voltage) if len(logs) > 1 else 0.0
        
        return {
            "battery_id": battery_id,
            "charge_cycle_count": battery.cycle_count,
            "avg_temperature_30d": avg_temp,
            "voltage_drop_rate": voltage_drop,
            "battery_age_days": (datetime.utcnow() - battery.created_at).days,
            "current_soh": battery.health_percentage
        }

    @staticmethod
    def get_user_features(db: Session, user_id: int) -> Dict[str, Any]:
        """
        Extract features for fraud and churn prediction.
        """
        # Placeholder for complex user activity aggregation
        return {
            "user_id": user_id,
            "total_rentals": 10, # Mock
            "days_since_last_activity": 2, # Mock
            "failed_payment_count": 0
        }
