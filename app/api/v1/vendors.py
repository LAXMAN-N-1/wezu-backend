from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.db.session import get_session
from app.models.vendor import Vendor
from app.schemas.vendor import VendorCreate, VendorUpdate, VendorResponse, VendorList

router = APIRouter()

@router.get("/", response_model=VendorList)
def read_vendors(
    skip: int = 0,
    limit: int = 100,
    session: Session = Depends(get_session),
) -> Any:
    """
    Retrieve vendors.
    """
    total = session.exec(select(Vendor)).all().__len__()
    vendors = session.exec(select(Vendor).offset(skip).limit(limit)).all()
    return {"total": total, "items": vendors}

@router.post("/", response_model=VendorResponse)
def create_vendor(
    *,
    session: Session = Depends(get_session),
    vendor_in: VendorCreate,
) -> Any:
    """
    Onboard a new vendor.
    """
    vendor = Vendor.from_orm(vendor_in)
    session.add(vendor)
    session.commit()
    session.refresh(vendor)
    return vendor

@router.get("/{vendor_id}", response_model=VendorResponse)
def read_vendor(
    *,
    session: Session = Depends(get_session),
    vendor_id: int,
) -> Any:
    """
    Get vendor by ID.
    """
    vendor = session.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor

@router.put("/{vendor_id}", response_model=VendorResponse)
def update_vendor(
    *,
    session: Session = Depends(get_session),
    vendor_id: int,
    vendor_in: VendorUpdate,
) -> Any:
    """
    Update a vendor.
    """
    vendor = session.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    vendor_data = vendor_in.dict(exclude_unset=True)
    for key, value in vendor_data.items():
        setattr(vendor, key, value)
    
    session.add(vendor)
    session.commit()
    session.refresh(vendor)
    return vendor
