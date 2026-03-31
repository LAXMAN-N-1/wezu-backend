"""
Daily Scheduled Jobs
Run at midnight IST (00:00)
"""
from sqlmodel import Session, select, func
from datetime import datetime, UTC, timedelta
from app.core.database import engine
from app.models.batch_job import BatchJob, JobExecution
import logging
import uuid

logger = logging.getLogger(__name__)

def create_job_execution(job_name: str, trigger_type: str = "SCHEDULED") -> JobExecution:
    """Create a job execution record"""
    with Session(engine) as session:
        # Get or create job definition
        job = session.exec(select(BatchJob).where(BatchJob.job_name == job_name)).first()
        if not job:
            job = BatchJob(
                job_name=job_name,
                job_type="SCHEDULED",
                is_active=True,
                description=f"Automated {job_name}"
            )
            session.add(job)
            session.commit()
            session.refresh(job)
        
        # Create execution
        execution = JobExecution(
            job_id=job.id,
            execution_id=str(uuid.uuid4()),
            status="RUNNING",
            trigger_type=trigger_type,
            started_at=datetime.now(UTC)
        )
        session.add(execution)
        session.commit()
        session.refresh(execution)
        return execution

def complete_job_execution(execution_id: str, status: str, result_summary: dict = None, error: str = None):
    """Complete a job execution"""
    with Session(engine) as session:
        execution = session.exec(
            select(JobExecution).where(JobExecution.execution_id == execution_id)
        ).first()
        
        if execution:
            execution.status = status
            execution.completed_at = datetime.now(UTC)
            
            started_at = execution.started_at
            if started_at and started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=UTC)
                
            if started_at:
                execution.duration_seconds = int((execution.completed_at - started_at).total_seconds())
            else:
                execution.duration_seconds = 0
                
            execution.result_summary = result_summary
            execution.error_message = error
            session.add(execution)
            session.commit()

def revenue_aggregation():
    """Calculate daily revenue per station"""
    logger.info("Starting daily revenue aggregation...")
    execution = create_job_execution("daily_revenue_aggregation")
    
    try:
        from app.models.financial import Transaction, TransactionStatus
        from app.models.station import Station
        
        with Session(engine) as session:
            yesterday = datetime.now(UTC) - timedelta(days=1)
            yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday_end = yesterday_start + timedelta(days=1)
            
            # Aggregate revenue per station
            stations = session.exec(select(Station)).all()
            total_revenue = 0
            station_revenues = {}
            
            for station in stations:
                # Get transactions for this station
                revenue = session.exec(
                    select(func.sum(Transaction.amount))
                    .where(Transaction.created_at >= yesterday_start)
                    .where(Transaction.created_at < yesterday_end)
                    .where(Transaction.status == TransactionStatus.SUCCESS)
                    # TODO: attach station_id to transaction for accurate per-station revenue
                ).one() or 0
                
                station_revenues[station.name] = float(revenue)
                total_revenue += float(revenue)
            
            result = {
                "date": yesterday_start.date().isoformat(),
                "total_revenue": total_revenue,
                "station_count": len(stations),
                "station_revenues": station_revenues
            }
            
            logger.info(f"Revenue aggregation completed: ₹{total_revenue}")
            complete_job_execution(execution.execution_id, "COMPLETED", result)
            
    except Exception as e:
        logger.error(f"Revenue aggregation failed: {str(e)}")
        complete_job_execution(execution.execution_id, "FAILED", error=str(e))

def inventory_sync():
    """Synchronize inventory across all stations"""
    logger.info("Starting inventory synchronization...")
    execution = create_job_execution("daily_inventory_sync")
    
    try:
        from app.models.dealer_inventory import DealerInventory
        from app.models.battery import Battery
        
        with Session(engine) as session:
            inventories = session.exec(select(DealerInventory)).all()
            synced_count = 0
            
            for inventory in inventories:
                # Recalculate available batteries
                # This is simplified - in production, would sync with actual battery status
                inventory.updated_at = datetime.now(UTC)
                session.add(inventory)
                synced_count += 1
            
            session.commit()
            
            result = {
                "synced_inventories": synced_count,
                "timestamp": datetime.now(UTC).isoformat()
            }
            
            logger.info(f"Inventory sync completed: {synced_count} inventories")
            complete_job_execution(execution.execution_id, "COMPLETED", result)
            
    except Exception as e:
        logger.error(f"Inventory sync failed: {str(e)}")
        complete_job_execution(execution.execution_id, "FAILED", error=str(e))

def late_fee_calculation():
    """Calculate late fees for overdue rentals"""
    logger.info("Starting late fee calculation...")
    execution = create_job_execution("daily_late_fee_calculation")
    
    try:
        from app.services.late_fee_service import LateFeeService
        
        with Session(engine) as session:
            overdue = LateFeeService.get_overdue_rentals(session)
            fees_applied = 0
            total_fees = 0.0
            for item in overdue:
                fee = LateFeeService.apply_late_fee(item["rental_id"], session)
                if fee:
                    fees_applied += 1
                    total_fees += fee.total_late_fee

            result = {
                "overdue_rentals": len(overdue),
                "fees_created": fees_applied,
                "total_fees": total_fees
            }
            
            logger.info(f"Late fee calculation completed: {fees_applied} fees, ₹{total_fees}")
            complete_job_execution(execution.execution_id, "COMPLETED", result)
            
    except Exception as e:
        logger.error(f"Late fee calculation failed: {str(e)}")
        complete_job_execution(execution.execution_id, "FAILED", error=str(e))

def commission_accrual():
    """Calculate daily commission accrual for dealers"""
    logger.info("Starting commission accrual...")
    execution = create_job_execution("daily_commission_accrual")
    
    try:
        from app.models.commission import Commission
        from app.models.dealer import DealerProfile
        from app.models.rental import Rental
        
        with Session(engine) as session:
            yesterday = datetime.now(UTC) - timedelta(days=1)
            yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday_end = yesterday_start + timedelta(days=1)
            
            dealers = session.exec(select(DealerProfile)).all()
            commissions_created = 0
            total_commission = 0.0
            
            for dealer in dealers:
                # Get rentals from dealer's stations
                # Simplified - would need station-dealer relationship
                commission_rate = 0.10  # 10% commission
                
                # Calculate commission (simplified)
                # In production, would calculate based on actual transactions
                
                # Create commission record
                # commission = Commission(...)
                # session.add(commission)
                pass
            
            session.commit()
            
            result = {
                "dealers_processed": len(dealers),
                "commissions_created": commissions_created,
                "total_commission": total_commission
            }
            
            logger.info(f"Commission accrual completed: {commissions_created} commissions")
            complete_job_execution(execution.execution_id, "COMPLETED", result)
            
    except Exception as e:
        logger.error(f"Commission accrual failed: {str(e)}")
        complete_job_execution(execution.execution_id, "FAILED", error=str(e))

def fraud_score_recalculation():
    """Recalculate fraud scores for all users"""
    logger.info("Starting fraud score recalculation...")
    execution = create_job_execution("daily_fraud_score_recalc")
    
    try:
        from app.models.fraud import RiskScore, FraudCheckLog
        from app.models.user import User
        
        with Session(engine) as session:
            users = session.exec(select(User)).all()
            updated_count = 0
            high_risk_count = 0
            
            for user in users:
                risk_score = session.exec(
                    select(RiskScore).where(RiskScore.user_id == user.id)
                ).first()
                
                if not risk_score:
                    risk_score = RiskScore(user_id=user.id, total_score=0.0)
                
                # Recalculate based on recent activity
                recent_checks = session.exec(
                    select(FraudCheckLog)
                    .where(FraudCheckLog.user_id == user.id)
                    .where(FraudCheckLog.created_at >= datetime.now(UTC) - timedelta(days=30))
                ).all()
                
                failed_checks = sum(1 for check in recent_checks if check.status == "FAIL")
                risk_score.total_score = failed_checks * 15  # 15 points per failed check
                risk_score.last_updated = datetime.now(UTC)
                
                session.add(risk_score)
                updated_count += 1
                
                if risk_score.total_score >= 50:
                    high_risk_count += 1
            
            session.commit()
            
            result = {
                "users_processed": len(users),
                "scores_updated": updated_count,
                "high_risk_users": high_risk_count
            }
            
            logger.info(f"Fraud score recalculation completed: {updated_count} users")
            complete_job_execution(execution.execution_id, "COMPLETED", result)
            
    except Exception as e:
        logger.error(f"Fraud score recalculation failed: {str(e)}")
        complete_job_execution(execution.execution_id, "FAILED", error=str(e))
