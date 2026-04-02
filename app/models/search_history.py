from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime, UTC

class SearchHistory(SQLModel, table=True):
    __tablename__ = "search_histories"
    """User search patterns for analytics and personalization"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    session_id: Optional[str] = None  # For anonymous users
    
    # Search details
    search_query: str = Field(index=True)
    search_type: str  # STATION, BATTERY, DEALER, PRODUCT, GENERAL
    
    # Location context
    search_latitude: Optional[float] = None
    search_longitude: Optional[float] = None
    search_location_name: Optional[str] = None
    
    # Filters applied
    filters_applied: Optional[str] = None  # JSON object of filters
    
    # Results
    results_count: int = Field(default=0)
    results_shown: int = Field(default=0)
    
    # User interaction
    clicked_result_id: Optional[int] = None
    clicked_result_type: Optional[str] = None  # STATION, BATTERY, etc.
    clicked_result_position: Optional[int] = None  # Position in results (1-based)
    
    time_to_click_seconds: Optional[int] = None
    
    # Conversion tracking
    led_to_rental: bool = Field(default=False)
    led_to_purchase: bool = Field(default=False)
    led_to_swap: bool = Field(default=False)
    
    conversion_id: Optional[int] = None  # ID of rental/purchase/swap
    conversion_type: Optional[str] = None
    
    # Device and context
    device_type: Optional[str] = None  # MOBILE, WEB, TABLET
    platform: Optional[str] = None  # iOS, Android, Web
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Relationships
    user: Optional["User"] = Relationship()
