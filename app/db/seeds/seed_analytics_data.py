from __future__ import annotations
import logging
import random
import sys
import os
from datetime import datetime, timedelta, date, timezone; UTC = timezone.utc

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlmodel import Session, select
from app.db.session import engine
from app.models import (
    User, Station, Battery,
)
from app.models.telemetry import Telemetry
from app.models.analytics import DemandForecast, ChurnPrediction, PricingRecommendation
from app.models.swap import SwapSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_analytics():
    with Session(engine) as session:
        logger.info("📊 Seeding Analytics Data...")
        
        users = session.exec(select(User)).all()
        stations = session.exec(select(Station)).all()
        batteries = session.exec(select(Battery)).all()
        
        if not users or not stations or not batteries:
            logger.error("❌ Missing base data (users, stations, batteries). Run seed_full_db.py first.")
            return

        # 1. Seed Telemetry (Time-series data)
        logger.info("📡 Seeding Telemetry...")
        for battery in batteries[:10]: # Seed for first 10 batteries
            now = datetime.now(UTC)
            for i in range(50): # 50 data points per battery
                timestamp = now - timedelta(minutes=i * 15)
                telemetry = Telemetry(
                    device_id=f"D-00{battery.id}",
                    battery_id=battery.id,
                    latitude=17.4474 + (random.random() - 0.5) * 0.01,
                    longitude=78.3762 + (random.random() - 0.5) * 0.01,
                    speed_kmph=random.uniform(0, 45),
                    voltage=random.uniform(68.0, 74.0),
                    current=random.uniform(0, 10.0),
                    temperature=random.uniform(20.0, 45.0),
                    soc=random.uniform(10.0, 100.0),
                    soh=random.uniform(90.0, 100.0),
                    timestamp=timestamp
                )
                session.add(telemetry)
        
        # 2. Seed Demand Forecasts
        logger.info("📈 Seeding Demand Forecasts...")
        for station in stations:
            for d in range(7): # Next 7 days
                forecast_date = date.today() + timedelta(days=d)
                for h in [8, 12, 18, 22]: # Peak hours
                    forecast = DemandForecast(
                        forecast_type="STATION",
                        entity_id=station.id,
                        entity_name=station.name,
                        forecast_date=forecast_date,
                        forecast_hour=h,
                        predicted_rentals=random.randint(5, 20),
                        predicted_swaps=random.randint(2, 15),
                        confidence_level=0.9,
                        lower_bound=random.randint(1, 5),
                        upper_bound=random.randint(20, 30)
                    )
                    session.add(forecast)

        # 3. Seed Churn Predictions
        logger.info("🎯 Seeding Churn Predictions...")
        for user in users[:20]: # First 20 users
            prob = random.random()
            prediction = ChurnPrediction(
                user_id=user.id,
                churn_probability=prob,
                churn_risk_level="HIGH" if prob > 0.7 else "MEDIUM" if prob > 0.3 else "LOW",
                days_since_last_activity=random.randint(0, 30),
                total_rentals=random.randint(0, 15),
                total_spend=random.uniform(0, 5000),
                prediction_date=date.today()
            )
            session.add(prediction)

        # 4. Seed Pricing Recommendations
        logger.info("💰 Seeding Pricing Recommendations...")
        recommendation_types = ["RENTAL", "SWAP"]
        for station in stations[:3]:
            for r_type in recommendation_types:
                current_p = 100.0 if r_type == "RENTAL" else 50.0
                rec_p = current_p * (1 + (random.random() - 0.3) * 0.2)
                rec = PricingRecommendation(
                    recommendation_type=r_type,
                    entity_type="STATION",
                    entity_id=station.id,
                    current_price=current_p,
                    recommended_price=round(rec_p, 2),
                    price_change_percentage=round(((rec_p - current_p) / current_p) * 100, 2),
                    valid_from=datetime.now(UTC),
                    valid_until=datetime.now(UTC) + timedelta(days=7),
                    status="PENDING"
                )
                session.add(rec)
        
        # 5. Seed Swaps (Historical Transactions)
        logger.info("🔄 Seeding Swaps...")
        for _ in range(30):
            user = random.choice(users)
            station = random.choice(stations)
            batt_out = random.choice(batteries)
            batt_in = random.choice(batteries)
            if batt_out.id == batt_in.id: continue
            
            swap = SwapSession(
                user_id=user.id,
                station_id=station.id,
                old_battery_id=batt_out.id,
                new_battery_id=batt_in.id,
                status="completed",
                old_battery_soc=random.uniform(5, 30),
                new_battery_soc=random.uniform(80, 100),
                created_at=datetime.now(UTC) - timedelta(days=random.randint(0, 30))
            )
            session.add(swap)

        session.commit()
        logger.info("✅ Analytics Data Seeding Complete!")

if __name__ == "__main__":
    seed_analytics()
