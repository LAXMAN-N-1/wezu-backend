from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict
from datetime import datetime
from app.models.financial import TransactionType, TransactionStatus

class WalletBalanceResponse(BaseModel):
    user_id: int
    balance: float
    cashback_balance: float
    currency: str = "INR"

class TransactionFilterRequest(BaseModel):
    transaction_type: Optional[TransactionType] = None
    status: Optional[TransactionStatus] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    page: int = 1
    page_size: int = 20

class RefundStatusResponse(BaseModel):
    transaction_id: int
    status: str
    refund_id: Optional[str] = None
    amount: float
    processed_at: Optional[datetime] = None

class RevenueSummary(BaseModel):
    period: str
    total_revenue: float
    rental_revenue: float
    purchase_revenue: float
    transaction_count: int
    comparison_percentage: float = 0.0

class StationRevenueResponse(BaseModel):
    station_id: int
    station_name: str
    revenue: float
    rental_count: int

class RevenueForecastResponse(BaseModel):
    date: datetime
    projected_revenue: float

class ProfitMarginResponse(BaseModel):
    category: str  # Station ID or Battery Type
    revenue: float
    estimated_cost: float
    margin_percentage: float
