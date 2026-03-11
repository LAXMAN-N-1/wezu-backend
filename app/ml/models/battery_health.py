from typing import Dict, Any, List
from datetime import datetime, timedelta

class BatteryHealthModel:
    """
    Baseline ML Model for Battery Health Prediction (RUL & SoH).
    """
    @staticmethod
    def predict(features: Dict[str, Any]) -> Dict[str, Any]:
        # Heuristic Logic (Representing a real ML model's inference)
        cycles = features.get("charge_cycle_count", 0)
        current_soh = features.get("current_soh", 100.0)
        temp_impact = max(0, features.get("avg_temperature_30d", 30.0) - 35.0) * 0.1
        
        # Predicted SoH degradation
        decay_per_100_cycles = 0.5 + temp_impact
        predicted_soh_30d = current_soh - (decay_per_100_cycles * (30/365)) # Very rough 
        
        risk_score = 0.0
        if current_soh < 80 or cycles > 1000:
            risk_score = 0.8
        
        return {
            "current_soh": current_soh,
            "predicted_soh_30d": round(predicted_soh_30d, 2),
            "failure_risk_30d": risk_score,
            "explanation": {
                "top_factors": [
                    "Cycle count" if cycles > 500 else None,
                    "High temperature" if temp_impact > 0 else None
                ]
            }
        }

class DemandForecastModel:
    """
    Weighted Moving Average Demand Forecasting.
    """
    @staticmethod
    def predict(history: List[int]) -> List[int]:
        if not history:
            return [0] * 7
        
        # Weighted average of last 14 days if available, otherwise all history
        window_size = min(len(history), 14)
        recent_history = history[-window_size:]
        
        # Weights: more weight to more recent days [1, 2, 3, ... window_size]
        weights = list(range(1, window_size + 1))
        total_weight = sum(weights)
        
        weighted_avg = sum(h * w for h, w in zip(recent_history, weights)) / total_weight
        
        # Generate 7-day forecast with slight day-of-week seasonality simulation
        # In a real model, we'd use Prophet or an LSTM
        forecast = []
        for i in range(1, 8):
            seasonality = 1.1 if i in [5, 6] else 0.9 # Weekends usually have higher demand
            val = int(round(weighted_avg * seasonality))
            forecast.append(max(0, val))
            
        return forecast
