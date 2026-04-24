import logging
import time
from app.workers.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)
print("Starting scheduler...")
try:
    start_scheduler()
    print("Scheduler started. Waiting 5 seconds...")
    time.sleep(5)
    print("Stopping scheduler...")
    stop_scheduler()
    print("Success!")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
