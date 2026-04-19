from __future__ import annotations
from sqlmodel import Session, select
from datetime import datetime, timezone; UTC = timezone.utc
from app.core.database import engine
from app.models.rental import Rental
from app.services.late_fee_service import LateFeeService
from app.workers.daily_jobs import create_job_execution, complete_job_execution
import logging

logger = logging.getLogger(__name__)

def process_overdue_rentals():
    """Scan and apply late fees for all overdue active rentals"""
    logger.info("Starting automated overdue rental scan...")
    execution = create_job_execution("automated_late_fee_trigger")
    
    try:
        with Session(engine) as session:
            # get_overdue_rentals identifies rentals past their expected end_time
            overdue_list = LateFeeService.get_overdue_rentals(session)
            
            applied_count = 0
            for item in overdue_list:
                rental_id = item['rental_id']
                # apply_late_fee creates/updates the LateFee record and Transaction
                LateFeeService.apply_late_fee(rental_id, session)
                applied_count += 1
            
            result = {
                "overdue_detected": len(overdue_list),
                "fees_applied": applied_count,
                "timestamp": datetime.now(UTC).isoformat()
            }
            
            logger.info(f"Overdue scan completed: {applied_count} fees applied/updated")
            complete_job_execution(execution.execution_id, "COMPLETED", result)
            
    except Exception as e:
        logger.error(f"Overdue rental scan failed: {str(e)}")
        complete_job_execution(execution.execution_id, "FAILED", error=str(e))
