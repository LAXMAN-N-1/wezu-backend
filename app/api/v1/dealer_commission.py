from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session, select
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.db.session import get_session
from app.api.deps import get_current_user, get_current_admin, get_current_dealer
from app.models.commission import CommissionConfig, CommissionTier
from app.models.settlement import Settlement
from app.models.settlement_dispute import SettlementDispute
from app.models.user import User
from app.services.settlement_service import SettlementService
from app.services.dispute_service import DisputeService

router = APIRouter()


# ───────────────── Schemas ──────────────────

class TierCreate(BaseModel):
    min_volume: int = 0
    max_volume: Optional[int] = None
    percentage: float = 0.0
    flat_fee: float = 0.0


class CommissionRateCreate(BaseModel):
    dealer_id: Optional[int] = None
    transaction_type: str
    percentage: float = 0.0
    flat_fee: float = 0.0
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None
    tiers: List[TierCreate] = []

class CommissionRateUpdate(BaseModel):
    percentage: Optional[float] = None
    flat_fee: Optional[float] = None
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None
    is_active: Optional[bool] = None

class CommissionRateResponse(BaseModel):
    id: int
    dealer_id: Optional[int]
    transaction_type: str
    percentage: float
    flat_fee: float
    effective_from: datetime
    effective_until: Optional[datetime]
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class MonthRequest(BaseModel):
    month: str  # "YYYY-MM"


class DisputeCreateRequest(BaseModel):
    reason: str


class DisputeResolveRequest(BaseModel):
    action: str  # "approve" or "reject"
    notes: str
    adjustment_amount: float = 0.0


class SettlementResponse(BaseModel):
    id: int
    dealer_id: Optional[int]
    settlement_month: str
    total_revenue: float
    total_commission: float
    chargeback_amount: float
    net_payable: float
    status: str
    paid_at: Optional[datetime]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DisputeResponse(BaseModel):
    id: int
    settlement_id: int
    dealer_id: int
    reason: str
    status: str
    resolution_notes: Optional[str]
    adjustment_amount: Optional[float]
    created_at: datetime
    resolved_at: Optional[datetime]
    model_config = ConfigDict(from_attributes=True)


# ───────────────── Admin Endpoints ──────────────────

@router.post("/commission/rates", response_model=CommissionRateResponse)
def create_commission_rate(
    *,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_admin),
    request: CommissionRateCreate,
) -> Any:
    """Admin: Create a commission rate config with optional volume tiers."""
    config = CommissionConfig(
        dealer_id=request.dealer_id,
        transaction_type=request.transaction_type,
        percentage=request.percentage,
        flat_fee=request.flat_fee,
        effective_from=request.effective_from or datetime.utcnow(),
        effective_until=request.effective_until,
    )
    db.add(config)
    db.commit()
    db.refresh(config)

    for tier in request.tiers:
        t = CommissionTier(
            config_id=config.id,
            min_volume=tier.min_volume,
            max_volume=tier.max_volume,
            percentage=tier.percentage,
            flat_fee=tier.flat_fee,
        )
        db.add(t)
    db.commit()

    return config


@router.get("/commission/rates", response_model=List[CommissionRateResponse])
def list_commission_rates(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_admin),
) -> Any:
    """Admin: List all commission rate configs."""
    return db.exec(select(CommissionConfig)).all()


@router.patch("/commission/rates/{config_id}", response_model=CommissionRateResponse)
def update_commission_rate(
    *,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_admin),
    config_id: int,
    request: CommissionRateUpdate,
) -> Any:
    """Admin: Update an existing commission rate config."""
    config = db.get(CommissionConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(config, key, value)
    
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@router.post("/admin/settlements/generate")
def admin_generate_settlements(
    *,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_admin),
    request: MonthRequest,
) -> Any:
    """Admin: Manually trigger settlement generation for a given month."""
    from app.models.dealer import DealerProfile

    dealers = db.exec(
        select(DealerProfile).where(DealerProfile.is_active == True)
    ).all()

    results = []
    for dealer in dealers:
        settlement = SettlementService.generate_monthly_settlement(
            db, dealer.user_id, request.month
        )
        results.append(
            {
                "dealer_id": dealer.user_id,
                "settlement_id": settlement.id,
                "net_payable": settlement.net_payable,
                "status": settlement.status,
            }
        )

    return {"month": request.month, "settlements": results}


@router.post("/admin/settlements/batch-pay")
def admin_batch_pay(
    *,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_admin),
    request: MonthRequest,
) -> Any:
    """Admin: Trigger batch payment processing for a month."""
    return SettlementService.process_batch_payments(db, request.month)


@router.post("/admin/settlements/retry/{settlement_id}")
def admin_retry_settlement(
    *,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_admin),
    settlement_id: int,
) -> Any:
    """Admin: Retry a failed settlement payment."""
    try:
        return SettlementService.process_single_payment(db, settlement_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/admin/disputes", response_model=List[DisputeResponse])
def admin_list_disputes(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_admin),
) -> Any:
    """Admin: List all open disputes."""
    return DisputeService.list_open_disputes(db)


@router.post("/admin/disputes/{dispute_id}/resolve", response_model=DisputeResponse)
def admin_resolve_dispute(
    *,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_admin),
    dispute_id: int,
    request: DisputeResolveRequest,
) -> Any:
    """Admin: Resolve a dispute (approve with adjustment or reject)."""
    try:
        return DisputeService.resolve_dispute(
            db, dispute_id, request.action, request.notes, request.adjustment_amount
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ───────────────── Dealer Endpoints ──────────────────

@router.get("/dealer/dashboard")
def dealer_dashboard(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_dealer),
) -> Any:
    """Dealer: View commission dashboard with current earnings & 12-month history."""
    return SettlementService.get_dealer_dashboard(db, current_user.id)


@router.get("/dealer/settlements", response_model=List[SettlementResponse])
def dealer_list_settlements(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_dealer),
) -> Any:
    """Dealer: List own settlements (pending + paid)."""
    return db.exec(
        select(Settlement)
        .where(Settlement.dealer_id == current_user.id)
        .order_by(Settlement.settlement_month.desc())
    ).all()


@router.get("/dealer/settlements/{settlement_id}/details")
def dealer_settlement_details(
    settlement_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_dealer),
) -> Any:
    """Dealer: View transaction-level detail for a settlement."""
    settlement = db.get(Settlement, settlement_id)
    if not settlement or settlement.dealer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Settlement not found")

    detail = SettlementService.get_transaction_detail(db, settlement_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Settlement not found")
    return detail


@router.get("/dealer/settlements/{settlement_id}/pdf")
def dealer_settlement_pdf(
    settlement_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_dealer),
) -> Any:
    """Dealer: Download settlement statement PDF."""
    settlement = db.get(Settlement, settlement_id)
    if not settlement or settlement.dealer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Settlement not found")

    path = SettlementService.generate_settlement_pdf(db, settlement_id)
    if not path:
        raise HTTPException(status_code=404, detail="Could not generate PDF")
    return FileResponse(path, media_type="application/pdf", filename=f"settlement_{settlement_id}.pdf")


@router.post("/dealer/settlements/{settlement_id}/dispute", response_model=DisputeResponse)
def dealer_create_dispute(
    *,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_dealer),
    settlement_id: int,
    request: DisputeCreateRequest,
) -> Any:
    """Dealer: Raise a dispute on a settlement."""
    try:
        return DisputeService.create_dispute(
            db, settlement_id, current_user.id, request.reason
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
