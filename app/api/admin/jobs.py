from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from app.api import deps
from app.models.user import User
from app.models.batch_job import BatchJob, JobExecution

router = APIRouter()

# Batch job management

@router.get("/", response_model=List[BatchJob])
def list_jobs(
    is_active: Optional[bool] = None,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(deps.get_db)
):
    """List all scheduled batch jobs"""
    query = select(BatchJob)
    if is_active is not None:
        query = query.where(BatchJob.is_active == is_active)
    
    query = query.order_by(BatchJob.job_name)
    return session.exec(query).all()

@router.get("/{job_id}", response_model=BatchJob)
def get_job(
    job_id: int,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(deps.get_db)
):
    """Get job details"""
    job = session.get(BatchJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

class JobTrigger(BaseModel):
    parameters: Optional[dict] = None

@router.post("/{job_id}/run", response_model=JobExecution)
def trigger_job(
    job_id: int,
    req: JobTrigger,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(deps.get_db)
):
    """Manually trigger a job"""
    import uuid
    
    job = session.get(BatchJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if not job.is_active:
        raise HTTPException(status_code=400, detail="Job is not active")
    
    # Create execution record
    execution = JobExecution(
        job_id=job_id,
        execution_id=str(uuid.uuid4()),
        status="PENDING",
        trigger_type="MANUAL",
        triggered_by=current_user.id,
        started_at=datetime.utcnow()
    )
    session.add(execution)
    session.commit()
    session.refresh(execution)
    
    # In production, this would trigger actual job via Celery/RQ
    # For now, just mark as completed
    execution.status = "RUNNING"
    session.add(execution)
    session.commit()
    
    return execution

@router.get("/{job_id}/history", response_model=List[JobExecution])
def get_job_history(
    job_id: int,
    limit: int = 50,
    status: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(deps.get_db)
):
    """Get job execution history"""
    query = select(JobExecution).where(JobExecution.job_id == job_id)
    
    if status:
        query = query.where(JobExecution.status == status)
    
    query = query.order_by(JobExecution.created_at.desc()).limit(limit)
    return session.exec(query).all()

@router.get("/{job_id}/logs/{execution_id}")
def get_execution_logs(
    job_id: int,
    execution_id: str,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(deps.get_db)
):
    """Get execution logs"""
    execution = session.exec(
        select(JobExecution)
        .where(JobExecution.job_id == job_id)
        .where(JobExecution.execution_id == execution_id)
    ).first()
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return {
        "execution_id": execution.execution_id,
        "status": execution.status,
        "started_at": execution.started_at,
        "completed_at": execution.completed_at,
        "duration_seconds": execution.duration_seconds,
        "result_summary": execution.result_summary,
        "error_message": execution.error_message,
        "error_stack_trace": execution.error_stack_trace,
        "execution_log": execution.execution_log,
        "processed_items": execution.processed_items,
        "failed_items": execution.failed_items
    }

class JobUpdate(BaseModel):
    is_active: Optional[bool] = None
    schedule_cron: Optional[str] = None
    max_retries: Optional[int] = None
    timeout_seconds: Optional[int] = None

@router.put("/{job_id}", response_model=BatchJob)
def update_job(
    job_id: int,
    req: JobUpdate,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(deps.get_db)
):
    """Update job configuration"""
    job = session.get(BatchJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if req.is_active is not None:
        job.is_active = req.is_active
    if req.schedule_cron:
        job.schedule_cron = req.schedule_cron
    if req.max_retries is not None:
        job.max_retries = req.max_retries
    if req.timeout_seconds is not None:
        job.timeout_seconds = req.timeout_seconds
    
    job.updated_at = datetime.utcnow()
    session.add(job)
    session.commit()
    session.refresh(job)
    return job

@router.get("/executions/recent", response_model=List[dict])
def get_recent_executions(
    limit: int = 100,
    status: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(deps.get_db)
):
    """Get recent job executions across all jobs"""
    query = select(JobExecution)
    
    if status:
        query = query.where(JobExecution.status == status)
    
    query = query.order_by(JobExecution.created_at.desc()).limit(limit)
    executions = session.exec(query).all()
    
    result = []
    for exec in executions:
        job = session.get(BatchJob, exec.job_id)
        result.append({
            "execution_id": exec.execution_id,
            "job_id": exec.job_id,
            "job_name": job.job_name if job else "Unknown",
            "status": exec.status,
            "trigger_type": exec.trigger_type,
            "started_at": exec.started_at,
            "completed_at": exec.completed_at,
            "duration_seconds": exec.duration_seconds,
            "processed_items": exec.processed_items,
            "failed_items": exec.failed_items
        })
    
    return result
