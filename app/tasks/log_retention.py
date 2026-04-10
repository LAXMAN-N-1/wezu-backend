import logging
from datetime import datetime, UTC, timedelta
from sqlmodel import Session, delete
from app.core.database import engine
from app.models.audit_log import AuditLog
from app.workers.daily_jobs import create_job_execution, complete_job_execution

logger = logging.getLogger(__name__)

def purge_old_audit_logs(days: int = 30):
    """
    Hard delete audit logs older than the specified retention period (days).
    """
    logger.info(f"Starting audit log retention policy (Purging older than {days} days)...")
    execution = create_job_execution("daily_audit_log_retention")
    
    try:
        with Session(engine) as session:
            cutoff_date = datetime.now(UTC) - timedelta(days=days)
            
            stmt = delete(AuditLog).where(AuditLog.timestamp < cutoff_date)
            result = session.exec(stmt)
            deleted_count = result.rowcount
            
            session.commit()
            
            summary = {
                "deleted_rows": deleted_count,
                "cutoff_date": cutoff_date.isoformat(),
            }
            
            logger.info(f"Audit log retention completed: Purged {deleted_count} logs.")
            complete_job_execution(execution.execution_id, "COMPLETED", summary)
            
    except Exception as e:
        logger.error(f"Audit log retention failed: {str(e)}", exc_info=True)
        complete_job_execution(execution.execution_id, "FAILED", error=str(e))
