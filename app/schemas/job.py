"""
Background job-related Pydantic schemas
Job status, execution history, and monitoring
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime

# Request Models
class JobTriggerRequest(BaseModel):
    """Manually trigger a job"""
    parameters: Optional[Dict] = None
    priority: str = Field("NORMAL", pattern=r'^(LOW|NORMAL|HIGH|URGENT)$')

class JobUpdateRequest(BaseModel):
    """Update job configuration"""
    is_active: Optional[bool] = None
    schedule_cron: Optional[str] = None
    max_retries: Optional[int] = Field(None, ge=0, le=10)
    timeout_seconds: Optional[int] = Field(None, gt=0)
    retry_delay_seconds: Optional[int] = Field(None, gt=0)
    alert_on_failure: Optional[bool] = None
    alert_recipients: Optional[List[str]] = None

class JobExecutionFilter(BaseModel):
    """Filter job executions"""
    job_id: Optional[int] = None
    status: Optional[str] = Field(None, pattern=r'^(PENDING|RUNNING|COMPLETED|FAILED|CANCELLED|TIMEOUT|RETRYING)$')
    trigger_type: Optional[str] = Field(None, pattern=r'^(SCHEDULED|MANUAL|API|WEBHOOK)$')
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = Field(50, ge=1, le=500)

# Response Models
class BatchJobResponse(BaseModel):
    """Batch job response"""
    id: int
    job_name: str
    job_type: str
    description: Optional[str]
    schedule_cron: Optional[str]
    is_active: bool
    max_retries: int
    timeout_seconds: int
    retry_delay_seconds: int
    alert_on_failure: bool
    alert_recipients: Optional[List[str]]
    last_execution_at: Optional[datetime]
    last_execution_status: Optional[str]
    next_scheduled_run: Optional[datetime]
    total_executions: int
    successful_executions: int
    failed_executions: int
    average_duration_seconds: Optional[float]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class JobExecutionResponse(BaseModel):
    """Job execution response"""
    id: int
    job_id: int
    job_name: Optional[str]
    execution_id: str
    status: str
    trigger_type: str
    triggered_by: Optional[int]
    started_at: datetime
    completed_at: Optional[datetime]
    duration_seconds: Optional[int]
    processed_items: Optional[int]
    failed_items: Optional[int]
    result_summary: Optional[Dict]
    error_message: Optional[str]
    error_stack_trace: Optional[str]
    retry_count: int
    parent_execution_id: Optional[str]
    resource_usage: Optional[Dict]

    class Config:
        from_attributes = True

class JobExecutionLogResponse(BaseModel):
    """Detailed job execution log"""
    execution: JobExecutionResponse
    execution_log: Optional[str]
    performance_metrics: Dict
    resource_usage: Dict
    warnings: List[str]
    errors: List[str]

class JobStatusSummaryResponse(BaseModel):
    """Job status summary"""
    job_id: int
    job_name: str
    is_active: bool
    current_status: str
    last_run: Optional[datetime]
    next_run: Optional[datetime]
    success_rate: float
    average_duration: Optional[float]
    recent_failures: int
    health_status: str  # HEALTHY, DEGRADED, FAILING

class JobScheduleResponse(BaseModel):
    """Job schedule information"""
    job_id: int
    job_name: str
    schedule_type: str  # CRON, INTERVAL, ONE_TIME
    schedule_expression: str
    timezone: str
    next_run_time: Optional[datetime]
    previous_run_time: Optional[datetime]
    is_paused: bool

class JobMetricsResponse(BaseModel):
    """Job performance metrics"""
    job_id: int
    job_name: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    success_rate: float
    average_duration_seconds: float
    min_duration_seconds: float
    max_duration_seconds: float
    p50_duration_seconds: float
    p95_duration_seconds: float
    p99_duration_seconds: float
    total_items_processed: int
    total_items_failed: int
    average_items_per_execution: float
    last_7_days_executions: List[Dict]
    failure_reasons: Dict[str, int]

class JobHealthCheckResponse(BaseModel):
    """Job health check"""
    job_id: int
    job_name: str
    health_status: str
    issues: List[str]
    recommendations: List[str]
    last_successful_run: Optional[datetime]
    consecutive_failures: int
    is_overdue: bool
    estimated_next_run: Optional[datetime]

class JobDashboardResponse(BaseModel):
    """Job monitoring dashboard"""
    total_jobs: int
    active_jobs: int
    paused_jobs: int
    currently_running: int
    jobs_with_issues: int
    total_executions_today: int
    successful_executions_today: int
    failed_executions_today: int
    average_success_rate: float
    jobs_by_status: Dict[str, int]
    recent_executions: List[JobExecutionResponse]
    failing_jobs: List[JobStatusSummaryResponse]
    slow_jobs: List[Dict]
    upcoming_jobs: List[Dict]

class JobAlertResponse(BaseModel):
    """Job alert/notification"""
    alert_id: str
    job_id: int
    job_name: str
    alert_type: str  # FAILURE, TIMEOUT, SLOW_EXECUTION, CONSECUTIVE_FAILURES
    severity: str  # INFO, WARNING, ERROR, CRITICAL
    message: str
    details: Dict
    triggered_at: datetime
    acknowledged: bool
    acknowledged_by: Optional[int]
    acknowledged_at: Optional[datetime]
