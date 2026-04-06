from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.api import deps
from app.db.session import get_session
from app.models.battery_catalog import BatterySpec, BatteryBatch
from app.models.user import User
from app.schemas.battery_catalog import (
    BatterySpecCreate, BatterySpecResponse,
    BatteryBatchCreate, BatteryBatchResponse,
    BatteryCatalogResponse
)

router = APIRouter()

# --- Battery Specs ---
@router.post("/specs", response_model=BatterySpecResponse)
def create_battery_spec(
    *,
    session: Session = Depends(get_session),
    spec_in: BatterySpecCreate,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Create a new battery specification type.
    """
    spec = BatterySpec.from_orm(spec_in)
    session.add(spec)
    session.commit()
    session.refresh(spec)
    return spec

@router.get("/specs", response_model=List[BatterySpecResponse])
def read_battery_specs(
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    List all battery specifications.
    """
    return session.exec(select(BatterySpec)).all()

# --- Battery Batches ---
@router.post("/batches", response_model=BatteryBatchResponse)
def create_battery_batch(
    *,
    session: Session = Depends(get_session),
    batch_in: BatteryBatchCreate,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Register a new procurement batch.
    """
    batch = BatteryBatch.from_orm(batch_in)
    session.add(batch)
    session.commit()
    session.refresh(batch)
    # Note: Actual individual Battery creation from batch is handled separately
    # typically via a bulk create endpoint referring to this batch_id
    return batch
