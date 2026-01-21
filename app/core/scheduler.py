from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.services.maintenance_service import MaintenanceService
# from app.services.financial_service import FinancialService

scheduler = BackgroundScheduler()

def daily_jobs():
    print("Running Daily Jobs...")
    MaintenanceService.check_batteries_due()
    # FinancialService.calculate_late_fees()

def start_scheduler():
    scheduler.add_job(daily_jobs, CronTrigger(hour=0, minute=0)) # Midnight
    scheduler.start()
    print("Scheduler Started.")

def stop_scheduler():
    scheduler.shutdown()
