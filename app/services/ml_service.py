from sqlmodel import Session
from app.ml.feature_store import FeatureStore
from app.ml.models.battery_health import BatteryHealthModel, DemandForecastModel
from typing import Dict, Any

from app.ml.registry import ModelRegistry
import numpy as np

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
        # In a real system, we'd fetch actual historical swaps for the station
        # Mocking history here for demonstration
        mock_history = [45, 52, 48, 60, 55, 50, 47]
        predictions = DemandForecastModel.predict(mock_history)
        return {
            "station_id": station_id,
            "forecast_7_days": predictions,
            "unit": "swaps"
        }
