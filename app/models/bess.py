from __future__ import annotations
"""BESS (Battery Energy Storage System) models."""
from datetime import datetime, timezone; UTC = timezone.utc
from typing import Optional
from sqlmodel import SQLModel, Field
from enum import Enum


class BessUnitStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    STANDBY = "standby"


class BessUnit(SQLModel, table=True):
    __tablename__ = "bess_units"
    model_config = {"protected_namespaces": ()}

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    location: str
    capacity_kwh: float  # Total energy storage capacity
    current_charge_kwh: float = 0.0  # Current stored energy
    max_power_kw: float  # Maximum charge/discharge rate
    status: str = Field(default="online", index=True)
    soc: float = Field(default=50.0)  # State of Charge (0-100%)
    soh: float = Field(default=100.0)  # State of Health (0-100%)
    temperature_c: float = Field(default=25.0)
    cycle_count: int = Field(default=0)
    manufacturer: Optional[str] = None
    model_number: Optional[str] = None
    firmware_version: Optional[str] = None
    installed_at: Optional[datetime] = None
    last_maintenance_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BessEnergyLog(SQLModel, table=True):
    __tablename__ = "bess_energy_logs"
    id: Optional[int] = Field(default=None, primary_key=True)
    bess_unit_id: int = Field(foreign_key="bess_units.id", index=True)
    timestamp: datetime = Field(index=True)
    power_kw: float  # Positive = charging, Negative = discharging
    energy_kwh: float  # Energy transferred in this interval
    soc_start: float
    soc_end: float
    source: str = Field(default="grid")  # grid, solar, wind, station
    voltage: Optional[float] = None
    current_a: Optional[float] = None
    temperature_c: Optional[float] = None


class BessGridEvent(SQLModel, table=True):
    __tablename__ = "bess_grid_events"
    id: Optional[int] = Field(default=None, primary_key=True)
    bess_unit_id: int = Field(foreign_key="bess_units.id", index=True)
    event_type: str = Field(index=True)  # peak_shaving, load_shifting, frequency_regulation, backup
    status: str = Field(default="scheduled")  # scheduled, active, completed, cancelled
    start_time: datetime
    end_time: Optional[datetime] = None
    target_power_kw: float
    actual_power_kw: Optional[float] = None
    energy_kwh: Optional[float] = None
    revenue_earned: Optional[float] = None
    grid_operator: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BessReport(SQLModel, table=True):
    __tablename__ = "bess_reports"
    id: Optional[int] = Field(default=None, primary_key=True)
    bess_unit_id: Optional[int] = Field(default=None, foreign_key="bess_units.id")
    report_type: str = Field(index=True)  # daily, weekly, monthly
    period_start: datetime
    period_end: datetime
    total_charged_kwh: float = 0.0
    total_discharged_kwh: float = 0.0
    avg_efficiency: float = 0.0  # percentage
    peak_power_kw: float = 0.0
    avg_soc: float = 0.0
    min_soc: float = 0.0
    max_soc: float = 0.0
    revenue: float = 0.0
    cost: float = 0.0
    grid_events_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
