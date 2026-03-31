from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class HeartbeatMetrics(BaseModel):
    temperature: float
    power_consumption: float
    network_latency: float

class HeartbeatRequestV2(BaseModel):
    station_id: str
    status: str # ONLINE | WARNING | ERROR
    metrics: HeartbeatMetrics
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

class StationHealthStatus(BaseModel):
    station_id: str
    status: str # ONLINE | OFFLINE
    last_heartbeat: Optional[datetime] = None
    uptime_percentage: float = 0.0
    avg_response_time: float = 0.0
    total_downtime_minutes: int = 0

class StationHealthListResponse(BaseModel):
    stations: List[StationHealthStatus]

class BatteryHealthStatus(BaseModel):
    battery_id: str
    charge_cycles: int
    state_of_health: float
    health_status: str # EXCELLENT | GOOD | FAIR | POOR | DAMAGED
    last_maintenance_date: Optional[datetime] = None

class BatteryListResponse(BaseModel):
    batteries: List[BatteryHealthStatus]

class BatteryHealthLog(BaseModel):
    timestamp: datetime
    soh: float
    status: str

class BatteryHealthReport(BaseModel):
    battery_id: str
    state_of_health: float
    charge_cycles: int
    temperature_history: List[float] = []
    health_logs: List[BatteryHealthLog] = []
    maintenance_recommendation: str

class OptimizationBattery(BaseModel):
    battery_id: str
    current_charge: float
    state_of_health: float

class ChargingOptimizationRequest(BaseModel):
    station_id: str
    batteries: List[OptimizationBattery]

class OptimizedQueueItem(BaseModel):
    battery_id: str
    priority_score: float
    queue_position: int
    estimated_completion_time: Optional[datetime] = None

class OptimizedQueueResponse(BaseModel):
    optimized_queue: List[OptimizedQueueItem]

class ChargingQueueResponse(BaseModel):
    station_id: str
    capacity: int
    current_queue: List[OptimizedQueueItem]
