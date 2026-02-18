from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

class BatchJob(SQLModel, table=True):
    __tablename__ = "batch_jobs"
    __table_args__ = {"schema": "core"}
    """Background job definitions and tracking"""
    id: Optional[int] = Field(default=None, primary_key=True)
    
    job_name: str = Field(index=True)  # e.g., "daily_revenue_rollup", "late_fee_calculation"
    job_type: str  # SCHEDULED, MANUAL, TRIGGERED
    
    schedule_cron: Optional[str] = None  # Cron expression for scheduled jobs
    
    is_active: bool = Field(default=True)
    is_critical: bool = Field(default=False)  # Alert if critical job fails
    
    # Retry configuration
    max_retries: int = Field(default=3)
    retry_delay_seconds: int = Field(default=300)  # 5 minutes
    
    # Timeout configuration
    timeout_seconds: int = Field(default=3600)  # 1 hour default
    
    # Alert configuration
    alert_on_failure: bool = Field(default=True)
    alert_emails: Optional[str] = None  # JSON array of email addresses
    
    description: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    executions: list["JobExecution"] = Relationship(back_populates="job")

class JobExecution(SQLModel, table=True):
    __tablename__ = "job_executions"
    __table_args__ = {"schema": "core"}
    """Individual job run history"""
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="core.batch_jobs.id", index=True)
    
    execution_id: str = Field(unique=True, index=True)  # UUID for tracking
    
    status: str = Field(default="PENDING")  
    # PENDING, RUNNING, COMPLETED, FAILED, TIMEOUT, CANCELLED, RETRYING
    
    trigger_type: str  # SCHEDULED, MANUAL, API, EVENT
    triggered_by: Optional[int] = Field(default=None, foreign_key="core.users.id")
    
    # Execution details
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    
    # Progress tracking
    total_items: Optional[int] = None
    processed_items: int = Field(default=0)
    failed_items: int = Field(default=0)
    
    # Results and logs
    result_summary: Optional[dict] = Field(default=None, sa_column=sa.Column(JSON().with_variant(JSONB, "postgresql")))
    error_message: Optional[str] = None
    error_stack_trace: Optional[str] = None
    
    # Logs (truncated, full logs in external system)
    execution_log: Optional[str] = None
    
    # Retry tracking
    retry_count: int = Field(default=0)
    parent_execution_id: Optional[int] = Field(default=None, foreign_key="core.job_executions.id")
    
    # Resource usage
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    job: BatchJob = Relationship(back_populates="executions")
