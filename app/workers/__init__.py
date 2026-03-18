"""
Background Workers Package
Handles all scheduled and background tasks
"""
from app.workers.scheduler import scheduler, start_scheduler, stop_scheduler
from app.workers.rental_expiry_worker import run_rental_expiry_job

if scheduler:
    scheduler.add_job(
        run_rental_expiry_job,
        'interval',
        minutes=15,
        id='rental_expiry_job',
        replace_existing=True,
        max_instances=1,
        coalesce=True
    )

__all__ = ['scheduler', 'start_scheduler', 'stop_scheduler', 'run_rental_expiry_job']
