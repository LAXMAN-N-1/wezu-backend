from app.workers.rental_expiry_worker import run_rental_expiry_job
from app.models.notification_log import NotificationLog
from app.core.database import engine
import logging

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    print("Creating NotificationLog table if not exists...")
    try:
        NotificationLog.metadata.create_all(engine)
    except Exception as e:
        print(f"Table creation error: {e}")
        
    print("Starting manual run of rental_expiry_worker...")
    print("Starting manual run of rental_expiry_worker...")
    try:
        run_rental_expiry_job()
        print("Worker job executed successfully.")
    except Exception as e:
        print(f"Error: {e}")
