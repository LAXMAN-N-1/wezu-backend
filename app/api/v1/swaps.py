from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from datetime import datetime
from sqlmodel import Session, select
from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.models.swap import SwapSession
from app.models.station import Station
from app.models.financial import Transaction, Wallet
from app.models.battery import Battery, BatteryLifecycleEvent
from app.schemas.swap import SwapInitRequest, SwapResponse, SwapCompleteRequest

router = APIRouter()

@router.post("/initiate", response_model=SwapResponse)
def initiate_swap(
    *,
    session: Session = Depends(get_session),
    swap_in: SwapInitRequest,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    User initiates a swap at a station.
    """
    # 1. Validate Station
    station = session.get(Station, swap_in.station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
        
    # 2. Check Wallet Balance (Minimum amount required e.g. 100)
    wallet = session.exec(select(Wallet).where(Wallet.user_id == current_user.id)).first()
    if not wallet or wallet.balance < 50: # Example threshold
        raise HTTPException(status_code=400, detail="Insufficient wallet balance. Please recharge.")
        
    # 3. Create Session
    swap_session = SwapSession(
        user_id=current_user.id,
        station_id=station.id,
        status="initiated"
    )
    session.add(swap_session)
    session.commit()
    session.refresh(swap_session)
    
    return {
        "id": swap_session.id, 
        "status": swap_session.status, 
        "station_id": station.id,
        "station_name": station.name,
        "amount": 0.0,
        "created_at": swap_session.created_at
    }

@router.post("/{swap_id}/complete", response_model=SwapResponse)
def complete_swap(
    *,
    session: Session = Depends(get_session),
    swap_id: int,
    complete_in: SwapCompleteRequest,
    # In production, this endpoint might be protected for IoT Station Callbacks only
    current_user: User = Depends(get_current_user), 
) -> Any:
    """
    Finalize swap: hardware confirmed dispense. Deduct money.
    """
    swap_session = session.get(SwapSession, swap_id)
    if not swap_session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    if swap_session.status == "completed":
        raise HTTPException(status_code=400, detail="Swap already completed")
        
    # Calculate Cost (Mock logic)
    cost = 50.0 # Fixed price for MVP
    
    # 1. Update Session
    swap_session.new_battery_id = complete_in.new_battery_id
    swap_session.old_battery_soc = complete_in.old_battery_soc
    swap_session.new_battery_soc = complete_in.new_battery_soc
    swap_session.amount = cost
    swap_session.status = "completed"
    swap_session.payment_status = "paid"
    swap_session.completed_at = datetime.utcnow()
    
    # 2. Deduct Wallet
    wallet = session.exec(select(Wallet).where(Wallet.user_id == swap_session.user_id)).first()
    if wallet:
        wallet.balance -= cost
        session.add(wallet)
        
        # Log Transaction
        txn = Transaction(
            wallet_id=wallet.id,
            amount=-cost,
            balance_after=wallet.balance,
            type="debit",
            category="swap_fee",
            reference_type="swap_session",
            reference_id=str(swap_session.id),
            description=f"Swap at {swap_session.station_id}"
        )
        session.add(txn)
    
    # 3. Update Batteries (Mock)
    # old_bat = ... set location to station
    # new_bat = ... set location to user
    
    session.add(swap_session)
    session.commit()
    session.refresh(swap_session)
    
    return {
        "id": swap_session.id, 
        "status": swap_session.status, 
        "station_id": swap_session.station_id,
        "amount": swap_session.amount,
        "created_at": swap_session.created_at
    }
