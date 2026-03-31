from typing import Dict, Any, Optional
from datetime import datetime, UTC, timedelta
from sqlmodel import Session, select, func
from app.models.battery import Battery
from app.models.telemetry import Telemetry
from app.models.rental import Rental
from app.models.swap import SwapSession
from app.models.financial import Transaction

class FeatureStore:
    @staticmethod
    def get_battery_features(db: Session, battery_id: int) -> Dict[str, Any]:
        """
        Extract features for battery health prediction using Telemetry.
        """
        battery = db.get(Battery, battery_id)
        if not battery:
            return {}
            
        # Recent logs from Telemetry (TimescaleDB)
        since = datetime.now(UTC) - timedelta(days=30)
        logs = db.exec(select(Telemetry).where(
            Telemetry.battery_id == battery_id,
            Telemetry.timestamp >= since
        ).order_by(Telemetry.timestamp.asc())).all()
        
        avg_temp = sum(l.temperature for l in logs if l.temperature) / len(logs) if logs else 30.0
        voltage_drop = (logs[0].voltage - logs[-1].voltage) if len(logs) > 1 and logs[0].voltage and logs[-1].voltage else 0.0
        
        return {
            "battery_id": battery_id,
            "charge_cycle_count": battery.cycle_count,
            "avg_temperature_30d": avg_temp,
            "voltage_drop_rate": voltage_drop,
            "battery_age_days": (datetime.now(UTC) - battery.created_at).days,
            "current_soh": battery.health_percentage
        }

    @staticmethod
    def get_user_features(db: Session, user_id: int) -> Dict[str, Any]:
        """
        Extract features for fraud and churn prediction from real activity.
        """
        # 1. Rental activity
        rentals = db.exec(select(Rental).where(Rental.user_id == user_id)).all()
        total_rentals = len(rentals)
        overdue_count = sum(1 for r in rentals if r.status == "overdue")
        
        # 2. Payment failures
        failed_payments = db.exec(select(func.count(Transaction.id)).where(
            Transaction.user_id == user_id,
            Transaction.status == "failed"
        )).one() or 0

        # 3. Swap frequency (average days between swaps)
        swaps = db.exec(select(SwapSession).where(SwapSession.user_id == user_id).order_by(SwapSession.created_at.desc())).all()
        avg_swap_interval = 0
        if len(swaps) > 1:
            intervals = [(swaps[i].created_at - swaps[i+1].created_at).days for i in range(len(swaps)-1)]
            avg_swap_interval = sum(intervals) / len(intervals)

        return {
            "user_id": user_id,
            "total_rentals": total_rentals,
            "overdue_rate": overdue_count / total_rentals if total_rentals > 0 else 0,
            "failed_payment_count": failed_payments,
            "avg_swap_interval_days": avg_swap_interval,
            "account_age_days": (datetime.now(UTC) - rentals[0].created_at).days if rentals else 0
        }
