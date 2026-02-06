from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict

# Shared properties
class VendorBase(BaseModel):
    name: str
    email: EmailStr
    phone: str
    license_number: Optional[str] = None
    commission_rate: Optional[float] = 15.0
    zone_id: Optional[int] = None
    address: Optional[str] = None
    gps_coordinates: Optional[str] = None

# Properties to receive on item creation
class VendorCreate(VendorBase):
    pass

# Properties to receive on item update
class VendorUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    license_number: Optional[str] = None
    commission_rate: Optional[float] = None
    status: Optional[str] = None
    contract_start_date: Optional[datetime] = None
    contract_end_date: Optional[datetime] = None
    zone_id: Optional[int] = None
    address: Optional[str] = None
    gps_coordinates: Optional[str] = None

# Properties shared by models stored in DB
class VendorInDBBase(VendorBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Properties to return to client
class VendorResponse(VendorInDBBase):
    pass

class VendorList(BaseModel):
    total: int
    items: List[VendorResponse]
