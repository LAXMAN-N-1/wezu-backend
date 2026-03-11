from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, col
from datetime import datetime
from app.api.deps import get_db
from app.models.settlement import Settlement
from app.models.vendor import Vendor
from app.models.swap import SwapSession
from app.models.station import Station
from app.schemas.settlement import SettlementGenerateRequest, SettlementResponse, SettlementUpdateRequest

router = APIRouter()

@router.post("/generate", response_model=SettlementResponse)
def generate_settlement(
    *,
    session: Session = Depends(get_db),
    request: SettlementGenerateRequest,
) -> Any:
    """
    Generate a settlement report for a vendor for a specific period.
    Calculates total revenue from completed swaps and determines the payable amount.
    """
    # 1. Fetch Target (Vendor or Dealer)
    from app.models.commission import CommissionLog
    
    total_revenue = 0.0
    platform_fee = 0.0
    payable_amount = 0.0
    
    # query filters
    filters = [
        CommissionLog.status == "pending",
        CommissionLog.created_at >= request.start_date,
        CommissionLog.created_at <= request.end_date
    ]
    
    if request.vendor_id:
        filters.append(CommissionLog.vendor_id == request.vendor_id)
    elif hasattr(request, 'dealer_id') and request.dealer_id:
        filters.append(CommissionLog.dealer_id == request.dealer_id)
    else:
        raise HTTPException(status_code=400, detail="Either vendor_id or dealer_id must be provided")

    # 2. Aggregate Commissions
    logs = session.exec(select(CommissionLog).where(*filters)).all()
    
    if not logs:
        raise HTTPException(status_code=400, detail="No pending commissions found for this period")
        
    payable_amount = sum(log.amount for log in logs)
    
    # 3. Create Settlement Record
    settlement = Settlement(
        vendor_id=request.vendor_id,
        dealer_id=getattr(request, 'dealer_id', None),
        start_date=request.start_date,
        end_date=request.end_date,
        total_revenue=0, # This can be aggregated from source transactions if needed
        platform_fee=0, # Already deducted in CommissionLog.amount logic (net payable)
        payable_amount=payable_amount,
        status="generated"
    )
    
    session.add(settlement)
    session.commit()
    session.refresh(settlement)
    
    # 4. Link logs to settlement
    for log in logs:
        log.settlement_id = settlement.id
        log.status = "paid" # Or 'settled'
        session.add(log)
    session.commit()
    
    return settlement

@router.get("/", response_model=List[SettlementResponse])
def read_settlements(
    skip: int = 0,
    limit: int = 100,
    session: Session = Depends(get_db),
) -> Any:
    return session.exec(select(Settlement).offset(skip).limit(limit)).all()

@router.put("/{settlement_id}", response_model=SettlementResponse)
def update_settlement_status(
    *,
    session: Session = Depends(get_db),
    settlement_id: int,
    request: SettlementUpdateRequest,
) -> Any:
    settlement = session.get(Settlement, settlement_id)
    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")
        
    settlement.status = request.status
    if request.transaction_reference:
        settlement.transaction_reference = request.transaction_reference
    if request.status == "paid" and not settlement.paid_at:
        settlement.paid_at = datetime.utcnow()
        
    session.add(settlement)
    session.commit()
    session.refresh(settlement)
    return settlement
