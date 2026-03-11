from fastapi import APIRouter
from . import admin, dealer, logistics, customer

analytics_router = APIRouter()
analytics_router.include_router(admin.router, prefix="/admin", tags=["analytics-admin"])
analytics_router.include_router(dealer.router, prefix="/dealer", tags=["analytics-dealer"])
analytics_router.include_router(logistics.router, prefix="/logistics", tags=["analytics-logistics"])
analytics_router.include_router(customer.router, prefix="/customer", tags=["analytics-customer"])
