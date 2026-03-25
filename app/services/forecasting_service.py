from sqlmodel import Session, select, func, col
from app.models.analytics import DemandForecast
from app.models.swap import SwapSession
from app.models.station import Station
from datetime import datetime, date, timedelta
import logging

logger = logging.getLogger("wezu_forecasting")

class ForecastingService:
    @staticmethod
    def generate_demand_forecast(db: Session):
        """
        Generate a 7-day demand forecast for all stations based on historical averages.
        """
        stations = list(db.exec(select(Station)).all())
        today = date.today()
        
        for station in stations:
            # Look at last 7 days of actual swaps
            history_start = datetime.utcnow() - timedelta(days=7)
            stmt = select(func.count(col(SwapSession.id))).where(
                col(SwapSession.station_id) == station.id,
                col(SwapSession.created_at) >= history_start
            )
            total_past_swaps = db.exec(stmt).one() or 0
            daily_avg = total_past_swaps / 7.0
            
            # Predict for the next 7 days
            for i in range(1, 8):
                forecast_date = today + timedelta(days=i)
                
                # Check if forecast already exists
                existing = db.exec(select(DemandForecast).where(
                    col(DemandForecast.entity_id) == station.id,
                    col(DemandForecast.forecast_type) == "STATION",
                    col(DemandForecast.forecast_date) == forecast_date
                )).first()
                
                if not existing:
                    forecast = DemandForecast(
                        forecast_type="STATION",
                        entity_id=station.id,
                        entity_name=station.name,
                        forecast_date=forecast_date,
                        predicted_swaps=int(round(daily_avg)),
                        confidence_level=0.7, # Low confidence for baseline model
                        model_version="v1.0-baseline"
                    )
                    db.add(forecast)
        
        db.commit()
        logger.info(f"Demand forecast generated for {len(stations)} stations")
