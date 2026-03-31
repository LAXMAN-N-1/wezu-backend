"""
Campaign Worker — Scheduled background jobs for campaign processing.
1. process_birthday_campaigns: Daily at 08:00 IST
2. process_scheduled_campaigns: Every 15 minutes
"""
from sqlmodel import Session
from datetime import datetime
from app.core.database import engine
from app.workers.daily_jobs import create_job_execution, complete_job_execution
import logging

logger = logging.getLogger(__name__)


def process_birthday_campaigns():
    """
    Daily job: find active birthday campaigns, send to users whose DOB = today.
    """
    logger.info("Starting birthday campaign processing...")
    execution = create_job_execution("birthday_campaign_trigger")

    try:
        from app.services.campaign_service import CampaignService

        with Session(engine) as session:
            result = CampaignService.process_birthday_campaigns(session)

        logger.info(
            f"Birthday campaigns completed: {result['campaigns_processed']} campaigns, "
            f"{result['total_sent']} notifications sent"
        )
        complete_job_execution(execution.execution_id, "COMPLETED", result)

    except Exception as e:
        logger.error(f"Birthday campaign processing failed: {str(e)}")
        complete_job_execution(execution.execution_id, "FAILED", error=str(e))


def process_scheduled_campaigns():
    """
    Periodic job (every 15 min): find scheduled campaigns whose
    scheduled_at has passed, execute send, and mark as completed.
    """
    logger.info("Checking for scheduled campaigns to process...")
    execution = create_job_execution("scheduled_campaign_sender")

    try:
        from app.services.campaign_service import CampaignService

        with Session(engine) as session:
            result = CampaignService.process_scheduled_campaigns(session)

        if result["campaigns_processed"] > 0:
            logger.info(
                f"Scheduled campaigns completed: {result['campaigns_processed']} campaigns, "
                f"{result['total_sent']} notifications sent"
            )
        complete_job_execution(execution.execution_id, "COMPLETED", result)

    except Exception as e:
        logger.error(f"Scheduled campaign processing failed: {str(e)}")
        complete_job_execution(execution.execution_id, "FAILED", error=str(e))
