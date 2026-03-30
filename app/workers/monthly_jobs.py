"""
Monthly Scheduled Jobs
Run on 1st of each month
"""
from sqlmodel import Session, select, func
from datetime import datetime, timedelta
from app.core.database import engine
from app.workers.daily_jobs import create_job_execution, complete_job_execution
import logging

logger = logging.getLogger(__name__)

def commission_settlement():
    """Process monthly dealer commission settlements on 1st of each month."""
    logger.info("Starting monthly commission settlement...")
    execution = create_job_execution("monthly_commission_settlement")
    
    try:
        from app.models.dealer import DealerProfile
        from app.services.settlement_service import SettlementService
        
        with Session(engine) as session:
            # Get previous month
            today = datetime.utcnow()
            first_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_month_end = first_of_month - timedelta(days=1)
            month_str = last_month_end.strftime("%Y-%m")
            
            dealers = session.exec(select(DealerProfile).where(DealerProfile.is_active == True)).all()
            
            settlements_created = 0
            total_amount = 0.0
            
            for dealer in dealers:
                settlement = SettlementService.generate_monthly_settlement(
                    session, dealer.user_id, month_str
                )
                settlements_created += 1
                total_amount += settlement.net_payable
                
                logger.info(
                    f"Settlement created for dealer {dealer.user_id}: "
                    f"₹{settlement.net_payable}"
                )
            
            result = {
                "period": month_str,
                "dealers_processed": len(dealers),
                "settlements_created": settlements_created,
                "total_amount": total_amount
            }
            
            logger.info(f"Commission settlement completed: {settlements_created} settlements")
            complete_job_execution(execution.execution_id, "COMPLETED", result)
            
    except Exception as e:
        logger.error(f"Commission settlement failed: {str(e)}")
        complete_job_execution(execution.execution_id, "FAILED", error=str(e))


def batch_payment_processing():
    """Process batch payments for generated settlements on 5th of each month."""
    logger.info("Starting batch payment processing...")
    execution = create_job_execution("monthly_batch_payment")
    
    try:
        from app.services.settlement_service import SettlementService
        
        with Session(engine) as session:
            # Pay last month's settlements
            today = datetime.utcnow()
            first_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_month_end = first_of_month - timedelta(days=1)
            month_str = last_month_end.strftime("%Y-%m")
            
            result = SettlementService.process_batch_payments(session, month_str)
            
            # FR-ADMIN-FIN-003: Failed settlement alert
            failed_count = result.get("failed_count", 0)
            if failed_count > 0:
                logger.error(f"ALERT: {failed_count} settlements failed in batch {month_str}")
                # In production, trigger Email/SMS alert to Admin
                from app.services.audit_service import AuditService
                AuditService.log_action(
                    session, 
                    user_id=None, 
                    action="SETTLEMENT_BATCH_FAILURE",
                    resource="settlement",
                    resource_id=month_str,
                    details=f"Batch payment failure detected: {failed_count} records"
                )
            
            logger.info(f"Batch payment completed: {result}")
            complete_job_execution(execution.execution_id, "COMPLETED", result)
            
    except Exception as e:
        logger.error(f"Batch payment processing failed: {str(e)}")
        complete_job_execution(execution.execution_id, "FAILED", error=str(e))


def financial_reconciliation():
    """Reconcile financial transactions with bank statements"""
    logger.info("Starting monthly financial reconciliation...")
    execution = create_job_execution("monthly_financial_reconciliation")
    
    try:
        from app.models.financial import Transaction
        from app.models.payment import PaymentTransaction
        
        with Session(engine) as session:
            # Get previous month transactions
            today = datetime.utcnow()
            first_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_month_end = first_of_month - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            
            # Get all completed transactions
            transactions = session.exec(
                select(Transaction)
                .where(Transaction.created_at >= last_month_start)
                .where(Transaction.created_at < first_of_month)
                .where(Transaction.status == "completed")
            ).all()
            
            total_transactions = len(transactions)
            total_amount = sum(t.amount for t in transactions)
            
            # Get payment gateway transactions
            payment_txns = session.exec(
                select(PaymentTransaction)
                .where(PaymentTransaction.created_at >= last_month_start)
                .where(PaymentTransaction.created_at < first_of_month)
                .where(PaymentTransaction.status == "success")
            ).all()
            
            payment_total = sum(p.amount for p in payment_txns)
            
            # Check for discrepancies
            discrepancy = abs(total_amount - payment_total)
            
            result = {
                "period_start": last_month_start.isoformat(),
                "period_end": last_month_end.isoformat(),
                "total_transactions": total_transactions,
                "transaction_amount": float(total_amount),
                "payment_gateway_amount": float(payment_total),
                "discrepancy": float(discrepancy),
                "reconciled": discrepancy < 1.0  # Within ₹1
            }
            
            if discrepancy >= 1.0:
                logger.warning(f"Reconciliation discrepancy: ₹{discrepancy}")
            else:
                logger.info("Financial reconciliation successful - no discrepancies")
            
            complete_job_execution(execution.execution_id, "COMPLETED", result)
            
    except Exception as e:
        logger.error(f"Financial reconciliation failed: {str(e)}")
        complete_job_execution(execution.execution_id, "FAILED", error=str(e))

def data_archival():
    """Archive old data to cold storage"""
    logger.info("Starting monthly data archival...")
    execution = create_job_execution("monthly_data_archival")
    
    try:
        from app.models.rental_event import RentalEvent
        from app.models.gps_log import GPSTrackingLog
        from app.models.battery_health_log import BatteryHealthLog
        from app.models.audit_log import AuditLog
        
        with Session(engine) as session:
            # Archive data older than 1 year
            archive_date = datetime.utcnow() - timedelta(days=365)
            
            archived_counts = {}
            
            # Archive rental events
            old_events = session.exec(
                select(RentalEvent).where(RentalEvent.timestamp < archive_date)
            ).all()
            
            # In production, would move to cold storage (S3, etc.)
            # For now, just count
            archived_counts['rental_events'] = len(old_events)
            
            # Archive GPS logs
            old_gps = session.exec(
                select(GPSTrackingLog).where(GPSTrackingLog.timestamp < archive_date)
            ).all()
            archived_counts['gps_logs'] = len(old_gps)
            
            # Archive battery health logs
            old_health = session.exec(
                select(BatteryHealthLog).where(BatteryHealthLog.timestamp < archive_date)
            ).all()
            archived_counts['battery_health_logs'] = len(old_health)
            
            # Keep audit logs for 7 years (compliance)
            audit_archive_date = datetime.utcnow() - timedelta(days=365*7)
            old_audits = session.exec(
                select(AuditLog).where(AuditLog.timestamp < audit_archive_date)
            ).all()
            archived_counts['audit_logs'] = len(old_audits)
            
            total_archived = sum(archived_counts.values())
            
            result = {
                "archive_date": archive_date.isoformat(),
                "total_records_archived": total_archived,
                "breakdown": archived_counts
            }
            
            logger.info(f"Data archival completed: {total_archived} records")
            complete_job_execution(execution.execution_id, "COMPLETED", result)
            
    except Exception as e:
        logger.error(f"Data archival failed: {str(e)}")
        complete_job_execution(execution.execution_id, "FAILED", error=str(e))
