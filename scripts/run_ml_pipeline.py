import sys
import os

# Add app directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal
from app.ml.pipeline import MLPipeline

def main():
    print("🚀 Triggering MLOps Retraining Pipeline...")
    db = SessionLocal()
    try:
        MLPipeline.retrain_battery_health_model(db)
        MLPipeline.retrain_demand_forecast(db)
        print("✅ Retraining complete. New models registered.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
