from sqlmodel import Session
from app.ml.feature_store import FeatureStore
from app.ml.models.battery_health import BatteryHealthModel, DemandForecastModel
from typing import Dict, Any

from app.ml.registry import ModelRegistry
import numpy as np
from datetime import datetime, timedelta

class MLService:
    @staticmethod
    def get_battery_health_prediction(db: Session, battery_id: int) -> Dict[str, Any]:
        features = FeatureStore.get_battery_features(db, battery_id)
        if not features:
            return {"error": "Features not found"}
        
        # Try to load latest ML model from registry
        model = ModelRegistry.load_latest_model("battery_health")
        if model:
            X = [[
                features["charge_cycle_count"],
                features["avg_temperature_30d"],
                features["voltage_drop_rate"],
                features["battery_age_days"]
            ]]
            pred_soh = model.predict(X)[0]
            return {
                "current_soh": features["current_soh"],
                "predicted_soh_30d": round(float(pred_soh), 2),
                "model_type": "RandomForest-Production",
                "failure_risk": 0.5 if pred_soh < 85 else 0.1
            }
        
        # Fallback to Baseline Heuristics
        return BatteryHealthModel.predict(features)

    @staticmethod
    def get_demand_forecast(db: Session, station_id: int) -> Dict[str, Any]:
        """
        Generate demand forecast based on last 30 days of swap history.
        """
        from app.models.swap import Swap
        from sqlalchemy import func
        
        # 1. Fetch swap counts per day for the last 30 days
        since = datetime.utcnow() - timedelta(days=30)
        history_stmt = select(
            func.date(Swap.created_at).label("date"),
            func.count(Swap.id).label("count")
        ).where(
            Swap.station_id == station_id,
            Swap.created_at >= since
        ).group_by(func.date(Swap.created_at)).order_by(func.date(Swap.created_at).asc())
        
        results = db.exec(history_stmt).all()
        # Convert to list of counts, filling missing days with 0
        history_map = {str(r.date): r.count for r in results}
        history = []
        for i in range(30):
            d = (since + timedelta(days=i)).date()
            history.append(history_map.get(str(d), 0))

        # 2. Predict next 7 days
        predictions = DemandForecastModel.predict(history)
        
        return {
            "station_id": station_id,
            "forecast_7_days": predictions,
            "history_30_days": history[-7:], # Return last week for UI comparison
            "unit": "swaps"
        }
