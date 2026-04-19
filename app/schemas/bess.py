from __future__ import annotations
"""BESS Pydantic schemas."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


# --- BessUnit ---
class BessUnitBase(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    name: str
    location: str
    capacity_kwh: float
    max_power_kw: float
    manufacturer: Optional[str] = None
    model_number: Optional[str] = None

class BessUnitCreate(BessUnitBase):
    status: str = "online"

class BessUnitRead(BessUnitBase):
    id: int
    current_charge_kwh: float
    status: str
    soc: float
    soh: float
    temperature_c: float
    cycle_count: int
    firmware_version: Optional[str] = None
    installed_at: Optional[datetime] = None
    last_maintenance_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- BessEnergyLog ---
class BessEnergyLogRead(BaseModel):
    id: int
    bess_unit_id: int
    timestamp: datetime
    power_kw: float
    energy_kwh: float
    soc_start: float
    soc_end: float
    source: str
    voltage: Optional[float] = None
    current_a: Optional[float] = None
    temperature_c: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)


# --- BessGridEvent ---
class BessGridEventBase(BaseModel):
    bess_unit_id: int
    event_type: str
    start_time: datetime
    end_time: Optional[datetime] = None
    target_power_kw: float
    grid_operator: Optional[str] = None
    notes: Optional[str] = None

class BessGridEventCreate(BessGridEventBase):
    pass

class BessGridEventRead(BessGridEventBase):
    id: int
    status: str
    actual_power_kw: Optional[float] = None
    energy_kwh: Optional[float] = None
    revenue_earned: Optional[float] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- BessReport ---
class BessReportRead(BaseModel):
    id: int
    bess_unit_id: Optional[int] = None
    report_type: str
    period_start: datetime
    period_end: datetime
    total_charged_kwh: float
    total_discharged_kwh: float
    avg_efficiency: float
    peak_power_kw: float
    avg_soc: float
    min_soc: float
    max_soc: float
    revenue: float
    cost: float
    grid_events_count: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Dashboard Aggregates ---
class BessOverviewStats(BaseModel):
    total_units: int
    online_units: int
    total_capacity_kwh: float
    current_stored_kwh: float
    avg_soc: float
    avg_soh: float
    total_energy_today_kwh: float
    total_revenue_today: float
