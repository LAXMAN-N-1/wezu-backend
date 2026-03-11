from fastapi import APIRouter
from . import admin, dealer, logistics, customer

router = APIRouter()
router.include_router(admin.router, prefix="/admin", tags=["analytics-admin"])
router.include_router(dealer.router, prefix="/dealer", tags=["analytics-dealer"])
router.include_router(logistics.router, prefix="/logistics", tags=["analytics-logistics"])
router.include_router(customer.router, prefix="/customer", tags=["analytics-customer"])
