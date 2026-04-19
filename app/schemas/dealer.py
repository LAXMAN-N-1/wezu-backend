from __future__ import annotations
"""
Dealer-related Pydantic schemas
Request and response models for dealer operations
"""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum

# Enums
class DealerApplicationStage(str, Enum):
    SUBMITTED = "SUBMITTED"
    DOCUMENTS_PENDING = "DOCUMENTS_PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    FIELD_VISIT_SCHEDULED = "FIELD_VISIT_SCHEDULED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class FieldVisitStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

# Request Models
class DealerProfileCreate(BaseModel):
    """Create dealer profile"""
    business_name: str = Field(..., min_length=2, max_length=200)
    contact_person: str = Field(..., min_length=2, max_length=100)
    contact_email: EmailStr
    contact_phone: str = Field(..., pattern=r'^\+?[1-9]\d{9,14}$')
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    pincode: str = Field(..., pattern=r'^\d{6}$')
    gst_number: Optional[str] = Field(None, pattern=r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$')
    pan_number: Optional[str] = Field(None, pattern=r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$')

class DealerProfileUpdate(BaseModel):
    """Update dealer profile"""
    business_name: Optional[str] = None
    contact_person: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    address_line1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None

class DealerApplicationUpdate(BaseModel):
    """Update dealer application status"""
    stage: DealerApplicationStage
    notes: Optional[str] = None

class DealerRejectionRequest(BaseModel):
    """Reject dealer application with reason"""
    reason: str

class FieldVisitSchedule(BaseModel):
    """Schedule field visit"""
    application_id: int
    officer_id: int
    scheduled_date: datetime
    notes: Optional[str] = None

class DealerInventoryAdjust(BaseModel):
    """Adjust dealer inventory"""
    battery_model: str
    adjustment_quantity: int = Field(..., description="Positive for addition, negative for removal")
    reason: str
    reference_number: Optional[str] = None

class DealerPromotionCreate(BaseModel):
    """Create dealer promotion"""
    promo_code: str = Field(..., min_length=4, max_length=20)
    description: str
    discount_type: str = Field(..., pattern=r'^(Union[PERCENTAGE, FIXED_AMOUNT|FREE_DELIVERY])$')
    discount_value: float = Field(..., gt=0)
    start_date: datetime
    end_date: datetime
    max_usage_total: Optional[int] = None
    max_usage_per_user: Optional[int] = Field(1, ge=1)
    min_order_value: Optional[float] = None
    applicable_battery_models: Optional[List[str]] = None
    applicable_to_rental: bool = True
    applicable_to_purchase: bool = True

# Response Models
class DealerProfileResponse(BaseModel):
    """Dealer profile response"""
    id: int
    user_id: int
    business_name: str
    contact_person: str
    contact_email: str
    contact_phone: str
    address_line1: str
    city: str
    state: str
    pincode: str
    gst_number: Optional[str]
    pan_number: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DealerApplicationResponse(BaseModel):
    """Dealer application response"""
    id: int
    dealer_id: int
    current_stage: str
    risk_score: float = 0.0
    status_history: Optional[List[Dict]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class FieldVisitResponse(BaseModel):
    """Field visit response"""
    id: int
    application_id: int
    officer_id: int
    scheduled_date: datetime
    completed_date: Optional[datetime] = None
    status: str
    report_data: Optional[Dict] = None
    images: Optional[List[str]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DealerInventoryResponse(BaseModel):
    """Dealer inventory response"""
    id: int
    dealer_id: int
    battery_model: str
    quantity_available: int
    quantity_reserved: int
    quantity_damaged: int
    reorder_level: int
    max_capacity: int
    last_restocked_at: Optional[datetime]
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DealerPromotionResponse(BaseModel):
    """Dealer promotion response"""
    id: int
    dealer_id: int
    promo_code: str
    description: str
    discount_type: str
    discount_value: float
    start_date: datetime
    end_date: datetime
    is_active: bool
    max_usage_total: Optional[int]
    current_usage_count: int
    max_usage_per_user: int
    min_order_value: Optional[float]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DealerDashboardResponse(BaseModel):
    """Dealer dashboard statistics"""
    total_sales: float
    total_rentals: int
    active_rentals: int
    total_earnings: float
    pending_commissions: float
    inventory_summary: Dict[str, int]
    recent_orders: List[Dict]
    performance_metrics: Dict[str, Any]

class CommissionStatementResponse(BaseModel):
    """Monthly commission statement"""
    month: str
    total_earnings: float
    total_transactions: int
    status: str
    download_url: Optional[str] = None

class PromotionCampaignRequest(BaseModel):
    """Request to create a promotion"""
    name: str
    promo_code: str
    discount_type: str
    discount_value: float
    start_date: datetime
    end_date: datetime
    applicable_to: str = "ALL"
