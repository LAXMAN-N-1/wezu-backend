from app.core.database import engine
from app.models.user_alert_config import UserAlertConfig
from app.models.battery_health import BatteryHealthAlert
from app.services.alert_service import AlertService
from sqlmodel import Session, select
import uuid
import logging

logging.basicConfig(level=logging.INFO)

print("Ensuring UserAlertConfig table exists...")
UserAlertConfig.metadata.create_all(engine)
print("Table assured.")

print("Running mock telemetry processor test...")
with Session(engine) as db:
    # Get any active rental just to have a valid user and battery
    from app.models.rental import Rental
    rental = db.exec(select(Rental).where(Rental.status == "active")).first()
    
    if rental:
        print(f"Testing against Rental {rental.id} with Battery {rental.battery_id}")
        
        # Ensure config exists
        config = db.exec(select(UserAlertConfig).where(UserAlertConfig.user_id == rental.user_id)).first()
        if not config:
            config = UserAlertConfig(user_id=rental.user_id, high_temp_celsius=60)
            db.add(config)
            db.commit()
            print("Created mock UserAlertConfig.")
            
        print("Feeding high temperature telemetry mapping...")
        AlertService.process_battery_telemetry(
            db=db,
            battery_id=str(rental.battery_id),
            temp_celsius=65.0
        )
        
        alerts = db.exec(
            select(BatteryHealthAlert).where(
                BatteryHealthAlert.battery_id == rental.battery_id,
                BatteryHealthAlert.is_resolved == False
            )
        ).all()
        print(f"Generated {len(alerts)} alerts.")
        for a in alerts:
            print(f" -> {a.alert_type}: {a.message}")
            
    else:
        print("No active rentals found to test against. Skipping deep test.")
        
print("Test completed.")
