from sqlmodel import Session
from app.ml.feature_store import FeatureStore
from app.ml.models.battery_health import BatteryHealthModel, DemandForecastModel
from typing import Dict, Any

class MLService:
    @staticmethod
    def get_battery_health_prediction(db: Session, battery_id: int) -> Dict[str, Any]:
        features = FeatureStore.get_battery_features(db, battery_id)
        if not features:
            return {"error": "Features not found"}
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
