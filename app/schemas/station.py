from pydantic import BaseModel, ConfigDict, computed_field
from typing import Optional, List, Any
from datetime import datetime
import json


# ── Image Schema ───────────────────────────────────────────────────

class StationImageResponse(BaseModel):
    url: str
    is_primary: bool


# ── Structured Sub-Schemas ─────────────────────────────────────────

class DayHours(BaseModel):
    """Operating window for a single day."""
    open: Optional[str] = None   # "09:00" or null (closed)
    close: Optional[str] = None  # "18:00" or null (closed)

class OperatingHoursSchema(BaseModel):
    """Day-by-day operating hours including holidays."""
    mon: Optional[DayHours] = None
    tue: Optional[DayHours] = None
    wed: Optional[DayHours] = None
    thu: Optional[DayHours] = None
    fri: Optional[DayHours] = None
    sat: Optional[DayHours] = None
    sun: Optional[DayHours] = None
    holidays: Optional[DayHours] = None

class ChargerConfig(BaseModel):
    """Individual charger specification."""
    type: str               # CCS2, CHAdeMO, Type2, GB/T
    count: int = 1
    power_kw: float = 0.0
    efficiency: float = 0.95
    speed: str = "standard"  # slow, standard, fast, ultra_fast

class AutoCloseConfig(BaseModel):
    """Auto-close rental settings."""
    enabled: bool = False
    grace_period_minutes: int = 30

class OperatingTempRange(BaseModel):
    """Safe operating temperature window (°C)."""
    min_temp: Optional[float] = None
    max_temp: Optional[float] = None

class TroubleshootingStep(BaseModel):
    """A single troubleshooting step for alerts."""
    step_number: int
    title: str
    description: str
    action: str = "inspect"   # inspect, restart, replace, escalate


# ── Station Base Schemas ───────────────────────────────────────────

class StationBase(BaseModel):
    name: str
    address: str
    latitude: float
    longitude: float
    status: str = "active"
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    opening_hours: Optional[str] = None
    is_24x7: bool = False
    amenities: Optional[str] = None

    # Operational
    station_type: str = "automated"
    total_slots: int = 0
    power_rating_kw: Optional[float] = None

    # Ownership/Location
    zone_id: Optional[int] = None
    dealer_id: Optional[int] = None

    # NEW — structured fields
    structured_hours: Optional[str] = None
    charger_configs: Optional[str] = None
    auto_close_enabled: bool = False
    auto_close_grace_minutes: int = 30
    operating_temp_min: Optional[float] = None
    operating_temp_max: Optional[float] = None
    geofence_id: Optional[int] = None


class StationCreate(StationBase):
    pass

class StationUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: Optional[str] = None
    contact_phone: Optional[str] = None
    operating_hours: Optional[str] = None
    is_24x7: Optional[bool] = None
    amenities: Optional[str] = None
    total_slots: Optional[int] = None
    power_rating_kw: Optional[float] = None

    # NEW
    structured_hours: Optional[str] = None
    charger_configs: Optional[str] = None
    auto_close_enabled: Optional[bool] = None
    auto_close_grace_minutes: Optional[int] = None
    operating_temp_min: Optional[float] = None
    operating_temp_max: Optional[float] = None
    geofence_id: Optional[int] = None


class StationResponse(StationBase):
    id: int
    rating: float
    total_reviews: int
    available_batteries: int = 0
    available_slots: int = 0
    images: List[StationImageResponse] = []

    model_config = ConfigDict(from_attributes=True)

    # ── Derived convenience helpers ────────────────────────────────

    @computed_field
    @property
    def parsed_operating_hours(self) -> Optional[OperatingHoursSchema]:
        """Parse structured_hours JSON into a typed object."""
        if not self.structured_hours:
            return None
        try:
            return OperatingHoursSchema(**json.loads(self.structured_hours))
        except Exception:
            return None

    @computed_field
    @property
    def parsed_charger_configs(self) -> Optional[List[ChargerConfig]]:
        """Parse charger_configs JSON into typed objects."""
        if not self.charger_configs:
            return None
        try:
            return [ChargerConfig(**c) for c in json.loads(self.charger_configs)]
        except Exception:
            return None

    @computed_field
    @property
    def auto_close(self) -> AutoCloseConfig:
        return AutoCloseConfig(
            enabled=self.auto_close_enabled,
            grace_period_minutes=self.auto_close_grace_minutes,
        )

    @computed_field
    @property
    def temp_range(self) -> OperatingTempRange:
        return OperatingTempRange(
            min_temp=self.operating_temp_min,
            max_temp=self.operating_temp_max,
        )

    @computed_field
    @property
    def is_open_now(self) -> bool:
        """
        Real-time availability indicator derived from status + operating hours.
        If 24x7 and active → always open.
        Otherwise checks structured_hours against current UTC time & weekday.
        """
        if self.status not in ("active", "OPERATIONAL"):
            return False
        if self.is_24x7:
            return True
        if not self.structured_hours:
            return True  # assume open if no schedule configured
        try:
            hours = json.loads(self.structured_hours)
            day_key = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][datetime.utcnow().weekday()]
            day = hours.get(day_key)
            if not day or not day.get("open") or not day.get("close"):
                return False
            now_str = datetime.utcnow().strftime("%H:%M")
            return day["open"] <= now_str <= day["close"]
        except Exception:
            return True


class NearbyStationResponse(StationResponse):
    distance: float  # km


# ── Performance & Map Schemas ──────────────────────────────────────

class StationPerformanceResponse(BaseModel):
    daily_rentals: int
    daily_revenue: float
    avg_duration_minutes: float
    satisfaction_score: float
    utilization_percentage: float

class StationMapResponse(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    status: str
    available_batteries: int

class HeatmapPoint(BaseModel):
    latitude: float
    longitude: float
    intensity: float  # 0.0 to 1.0

class StationAvailabilityResponse(BaseModel):
    station_id: int
    available_count: int
    batteries: List[dict]


# ── Station Specs Schemas ──────────────────────────────────────────

class StationSpecsBase(BaseModel):
    total_slots: int
    station_type: str
    power_rating_kw: Optional[float] = None
    max_capacity: Optional[int] = None
    charger_type: Optional[str] = None
    temperature_control: bool = False
    safety_features: Optional[str] = None

    # NEW
    charger_configs: Optional[str] = None
    operating_temp_min: Optional[float] = None
    operating_temp_max: Optional[float] = None

class StationSpecsResponse(StationSpecsBase):
    station_id: int

    @computed_field
    @property
    def parsed_charger_configs(self) -> Optional[List[ChargerConfig]]:
        if not self.charger_configs:
            return None
        try:
            return [ChargerConfig(**c) for c in json.loads(self.charger_configs)]
        except Exception:
            return None

    @computed_field
    @property
    def temp_range(self) -> OperatingTempRange:
        return OperatingTempRange(
            min_temp=self.operating_temp_min,
            max_temp=self.operating_temp_max,
        )

class StationSpecsUpdate(BaseModel):
    total_slots: Optional[int] = None
    station_type: Optional[str] = None
    power_rating_kw: Optional[float] = None
    max_capacity: Optional[int] = None
    charger_type: Optional[str] = None
    temperature_control: Optional[bool] = None
    safety_features: Optional[str] = None

    # NEW
    charger_configs: Optional[str] = None
    operating_temp_min: Optional[float] = None
    operating_temp_max: Optional[float] = None


# ── Lean Location Schema (for map markers) ─────────────────────────

class StationLocationLean(BaseModel):
    id: int
    latitude: float
    longitude: float

    model_config = ConfigDict(from_attributes=True)
