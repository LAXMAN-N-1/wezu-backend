from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime

class SwapSuggestion(SQLModel, table=True):
    __tablename__ = "swap_suggestions"
    """ML-based swap station recommendations"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    rental_id: int = Field(foreign_key="rentals.id")
    
    # Current battery state
    current_battery_soc: float  # State of charge (0-100)
    current_location_lat: float
    current_location_lng: float
    
    # Suggested stations (ordered by priority)
    suggested_station_id: int = Field(foreign_key="stations.id")
    priority_rank: int = Field(default=1)  # 1 = highest priority
    
    # Scoring factors
    distance_km: float
    estimated_travel_time_minutes: int
    
    station_availability_score: float = Field(default=0.0)  # 0-100
    station_rating: float = Field(default=0.0)
    
    # Predictive factors
    predicted_wait_time_minutes: Optional[int] = None
    predicted_battery_availability: Optional[int] = None
    
    # User preference alignment
    preference_match_score: float = Field(default=0.0)  # 0-100
    
    # Overall recommendation score
    total_score: float = Field(default=0.0)  # Weighted combination
    
    # User interaction
    was_accepted: Optional[bool] = None
    accepted_at: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: "User" = Relationship()
    rental: "Rental" = Relationship()
    station: "Station" = Relationship()

class SwapPreference(SQLModel, table=True):
    __tablename__ = "swap_preferences"
    """User preferences for swap stations"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True)
    
    # Preference weights (0-10, higher = more important)
    prefer_nearby: int = Field(default=8)  # Prioritize closest stations
    prefer_fast_charging: int = Field(default=5)  # Stations with fast chargers
    prefer_high_rated: int = Field(default=6)  # Highly rated stations
    prefer_low_wait: int = Field(default=7)  # Stations with low wait times
    
    # Favorite stations
    favorite_station_ids: Optional[str] = None  # JSON array of station IDs
    
    # Blacklisted stations (bad experience)
    blacklisted_station_ids: Optional[str] = None  # JSON array of station IDs
    
    # Time preferences
    preferred_swap_time: Optional[str] = None  # e.g., "morning", "evening", "night"
    
    # Maximum acceptable distance
    max_acceptable_distance_km: float = Field(default=10.0)
    
    # Notification preferences
    notify_when_battery_below: int = Field(default=20)  # SOC percentage
    notify_suggestion_radius_km: float = Field(default=5.0)
    
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: "User" = Relationship()
