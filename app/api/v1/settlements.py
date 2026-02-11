from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, col
from datetime import datetime
from app.db.session import get_session
from app.models.settlement import Settlement
from app.models.vendor import Vendor
from app.models.swap import SwapSession
from app.models.station import Station
from app.schemas.settlement import SettlementGenerateRequest, SettlementResponse, SettlementUpdateRequest

router = APIRouter()

@router.post("/generate", response_model=SettlementResponse)
def generate_settlement(
    *,
    session: Session = Depends(get_session),
    request: SettlementGenerateRequest,
) -> Any:
    """
    Generate a settlement report for a vendor for a specific period.
    Calculates total revenue from completed swaps and determines the payable amount.
    """
    # 1. Fetch Vendor
    vendor = session.get(Vendor, request.vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
        
    # 2. Find all stations owned by this vendor
    stations = session.exec(select(Station.id).where(Station.vendor_id == vendor.id)).all()
    if not stations:
        raise HTTPException(status_code=400, detail="No stations found for this vendor")
        
    # 3. Aggregate Swap Revenue
    # Select swaps at these stations, completed within range, that are paid
    swaps = session.exec(
        select(SwapSession)
        .where(col(SwapSession.station_id).in_(stations))
        .where(SwapSession.status == "completed")
        .where(SwapSession.payment_status == "paid")
        .where(SwapSession.completed_at >= request.start_date)
        .where(SwapSession.completed_at <= request.end_date)
    ).all()
    
    total_revenue = sum(swap.amount for swap in swaps)
    
    # 4. Calculate Commission
    # Commission is what Platform keeps. 
    # Example: 15% commission -> Platform keeps 15%, Vendor gets 85%.
    commission_rate = vendor.commission_rate / 100.0
    platform_fee = total_revenue * commission_rate
    payable_amount = total_revenue - platform_fee
    
    # 5. Create Settlement Record
    settlement = Settlement(
        vendor_id=vendor.id,
        start_date=request.start_date,
        end_date=request.end_date,
        total_revenue=total_revenue,
        platform_fee=platform_fee,
        payable_amount=payable_amount,
        status="generated"
    )
    
    session.add(settlement)
    session.commit()
    session.refresh(settlement)
    
    return settlement

@router.get("/", response_model=List[SettlementResponse])
def read_settlements(
    skip: int = 0,
    limit: int = 100,
    session: Session = Depends(get_session),
) -> Any:
    return session.exec(select(Settlement).offset(skip).limit(limit)).all()

@router.put("/{settlement_id}", response_model=SettlementResponse)
def update_settlement_status(
    *,
    session: Session = Depends(get_session),
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
