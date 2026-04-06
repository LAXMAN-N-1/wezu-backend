"""
Main Scheduler Configuration
APScheduler setup with job registration
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Create scheduler instance
scheduler = BackgroundScheduler(
    timezone='Asia/Kolkata',
    job_defaults={
        'coalesce': True,  # Combine missed runs
        'max_instances': 1,  # Prevent concurrent runs
        'misfire_grace_time': 300  # 5 minutes grace period
    }
)

def register_jobs():
    """Register all scheduled jobs"""
    from app.workers import daily_jobs, hourly_jobs, monthly_jobs, rental_worker
    
    logger.info("Registering scheduled jobs...")
    
    # Daily Jobs (00:00 IST)
    scheduler.add_job(
        daily_jobs.revenue_aggregation,
        CronTrigger(hour=0, minute=0),
        id='daily_revenue_aggregation',
        name='Daily Revenue Aggregation',
        replace_existing=True
    )
    
    scheduler.add_job(
        daily_jobs.inventory_sync,
        CronTrigger(hour=0, minute=15),
        id='daily_inventory_sync',
        name='Daily Inventory Synchronization',
        replace_existing=True
    )
    
    scheduler.add_job(
        daily_jobs.late_fee_calculation,
        CronTrigger(hour=0, minute=30),
        id='daily_late_fee_calculation',
        name='Daily Late Fee Calculation',
        replace_existing=True
    )
    
    scheduler.add_job(
        daily_jobs.commission_accrual,
        CronTrigger(hour=0, minute=45),
        id='daily_commission_accrual',
        name='Daily Commission Accrual',
        replace_existing=True
    )
    
    scheduler.add_job(
        daily_jobs.fraud_score_recalculation,
        CronTrigger(hour=1, minute=0),
        id='daily_fraud_score_recalc',
        name='Daily Fraud Score Recalculation',
        replace_existing=True
    )
    
    # Hourly Jobs
    scheduler.add_job(
        hourly_jobs.battery_health_checks,
        IntervalTrigger(hours=1),
        id='hourly_battery_health',
        name='Hourly Battery Health Checks',
        replace_existing=True
    )
    
    scheduler.add_job(
        hourly_jobs.geofence_violation_detection,
        IntervalTrigger(hours=1),
        id='hourly_geofence_check',
        name='Hourly Geofence Violation Detection',
        replace_existing=True
    )
    
    scheduler.add_job(
        hourly_jobs.low_stock_alerts,
        IntervalTrigger(hours=1),
        id='hourly_stock_alerts',
        name='Hourly Low Stock Alerts',
        replace_existing=True
    )
    
    scheduler.add_job(
        rental_worker.process_overdue_rentals,
        IntervalTrigger(hours=1),
        id='hourly_rental_overdue_check',
        name='Hourly Rental Overdue Check',
        replace_existing=True
    )
    
    scheduler.add_job(
        hourly_jobs.smart_battery_swap_notifications,
        IntervalTrigger(minutes=30), # Every 30 minutes to ensure timely swapping
        id='smart_battery_swap_notifications',
        name='Smart Battery Swap Notifications',
        replace_existing=True
    )
    
    # Monthly Jobs (1st of month, 02:00 IST)
    scheduler.add_job(
        monthly_jobs.commission_settlement,
        CronTrigger(day=1, hour=2, minute=0),
        id='monthly_commission_settlement',
        name='Monthly Commission Settlement',
        replace_existing=True
    )
    
    scheduler.add_job(
        monthly_jobs.financial_reconciliation,
        CronTrigger(day=1, hour=3, minute=0),
        id='monthly_financial_reconciliation',
        name='Monthly Financial Reconciliation',
        replace_existing=True
    )
    
    scheduler.add_job(
        monthly_jobs.data_archival,
        CronTrigger(day=1, hour=4, minute=0),
        id='monthly_data_archival',
        name='Monthly Data Archival',
        replace_existing=True
    )

    # Real-time Health Monitoring
    from app.tasks import station_monitor, battery_health_monitor, charging_optimizer
    
    scheduler.add_job(
        station_monitor.monitor_stations,
        IntervalTrigger(minutes=2),
        id='periodic_station_health_check',
        name='Periodic Station Health Check',
        replace_existing=True
    )

    scheduler.add_job(
        battery_health_monitor.monitor_battery_health,
        IntervalTrigger(hours=1),
        id='periodic_battery_health_monitor',
        name='Periodic Battery Health Monitor',
        replace_existing=True
    )

    scheduler.add_job(
        charging_optimizer.optimize_charging_queues,
        IntervalTrigger(minutes=30),
        id='periodic_charging_optimization',
        name='Periodic Charging Optimization',
        replace_existing=True
    )
    
    scheduler.add_job(
        monthly_jobs.batch_payment_processing,
        CronTrigger(day=5, hour=2, minute=0),
        id='monthly_batch_payment',
        name='Monthly Batch Payment Processing',
        replace_existing=True
    )
    
    logger.info(f"Registered {len(scheduler.get_jobs())} scheduled jobs")

def start_scheduler():
    """Start the scheduler"""
    if not scheduler.running:
        register_jobs()
        scheduler.start()
        logger.info("Background scheduler started successfully")
        
        # Log all registered jobs
        for job in scheduler.get_jobs():
            logger.info(f"Scheduled job: {job.name} (ID: {job.id})")
    else:
        logger.warning("Scheduler is already running")

def stop_scheduler():
    """Stop the scheduler"""
    if scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("Background scheduler stopped")
    else:
        logger.warning("Scheduler is not running")

def get_job_status():
    """Get status of all jobs"""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            'id': job.id,
            'name': job.name,
            'next_run': job.next_run_time,
            'trigger': str(job.trigger)
        })
    return jobs


def get_scheduler_runtime_state() -> dict:
    """Return scheduler runtime state for diagnostics."""
    from datetime import datetime, UTC
    return {
        "running": scheduler.running if scheduler else False,
        "job_count": len(scheduler.get_jobs()) if scheduler and scheduler.running else 0,
        "jobs": get_job_status() if scheduler and scheduler.running else [],
        "checked_at": datetime.now(UTC).isoformat(),
    }
