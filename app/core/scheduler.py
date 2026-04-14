import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.services.maintenance_service import MaintenanceService

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def daily_jobs():
    logger.info("Running daily scheduled jobs")
    MaintenanceService.check_batteries_due()


def start_scheduler():
    scheduler.add_job(daily_jobs, CronTrigger(hour=0, minute=0))
    scheduler.start()
    logger.info("Background scheduler started")


def stop_scheduler():
    scheduler.shutdown()
    logger.info("Background scheduler stopped")
