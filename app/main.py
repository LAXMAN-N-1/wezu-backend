from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings


# Customer-facing endpoints only
from app.api.v1 import (
    auth, users, kyc, stations, batteries, rentals, wallet, payments, 
    notifications, support, favorites, analytics, transactions, promo, 
    faqs, iot, swaps, i18n, fraud, branches, organizations, warehouses, screens, stock, dealers
)
# Enhanced customer endpoints
from app.api.v1 import (
    system, payments_enhanced, wallet_enhanced, notifications_enhanced,
    support_enhanced, rentals_enhanced, purchases_enhanced, analytics_enhanced,
    roles, menus, role_rights
)
from app.api.admin import router as admin_router
from app.api.webhooks import razorpay as razorpay_webhook
from app.middleware.rate_limit import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Background Workers
from app.workers import start_scheduler, stop_scheduler
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background scheduler on app startup and init DB"""
    from app.db.session import init_db
    init_db()
    start_scheduler()
    yield
    """Stop background scheduler on app shutdown"""
    stop_scheduler()

app = FastAPI(
    title=settings.PROJECT_NAME, 
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Rate Limit
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# GZip Compression
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Customer API Routes
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])
app.include_router(users.router, prefix=f"{settings.API_V1_STR}/users", tags=["Users"])
app.include_router(kyc.router, prefix=f"{settings.API_V1_STR}/kyc", tags=["KYC"])
app.include_router(stations.router, prefix=f"{settings.API_V1_STR}/stations", tags=["Stations"])
app.include_router(batteries.router, prefix=f"{settings.API_V1_STR}/batteries", tags=["Batteries"])
app.include_router(rentals.router, prefix=f"{settings.API_V1_STR}/rentals", tags=["Rentals"])
app.include_router(wallet.router, prefix=f"{settings.API_V1_STR}/wallet", tags=["Wallet"])
app.include_router(payments.router, prefix=f"{settings.API_V1_STR}/payments", tags=["Payments"])
app.include_router(notifications.router, prefix=f"{settings.API_V1_STR}/notifications", tags=["Notifications"])
app.include_router(support.router, prefix=f"{settings.API_V1_STR}/support", tags=["Support"])
app.include_router(favorites.router, prefix=f"{settings.API_V1_STR}/favorites", tags=["Favorites"])
app.include_router(analytics.router, prefix=f"{settings.API_V1_STR}/analytics", tags=["Analytics"])
app.include_router(transactions.router, prefix=f"{settings.API_V1_STR}/transactions", tags=["Transactions"])
app.include_router(promo.router, prefix=f"{settings.API_V1_STR}/promo", tags=["Promo"])
app.include_router(faqs.router, prefix=f"{settings.API_V1_STR}/faqs", tags=["FAQs"])
app.include_router(iot.router, prefix=f"{settings.API_V1_STR}/iot", tags=["IoT"])
app.include_router(swaps.router, prefix=f"{settings.API_V1_STR}/swaps", tags=["Swaps"])
app.include_router(i18n.router, prefix=f"{settings.API_V1_STR}/i18n", tags=["i18n"])
app.include_router(fraud.router, prefix=f"{settings.API_V1_STR}/fraud", tags=["Fraud Detection"])
app.include_router(branches.router, prefix=f"{settings.API_V1_STR}/branches", tags=["Branches"])
app.include_router(organizations.router, prefix=f"{settings.API_V1_STR}/organizations", tags=["Organizations"])
app.include_router(warehouses.router, prefix=f"{settings.API_V1_STR}/warehouses", tags=["Warehouses"])
app.include_router(screens.router, prefix=f"{settings.API_V1_STR}/screens", tags=["UI Configuration"])
app.include_router(system.router, prefix=f"{settings.API_V1_STR}/system", tags=["System"])
app.include_router(stock.router, prefix=f"{settings.API_V1_STR}/stock", tags=["Stock"])
app.include_router(dealers.router, prefix=f"{settings.API_V1_STR}/dealers", tags=["Dealers"])

# Admin & Role Based Routes
app.include_router(roles.router, prefix=f"{settings.API_V1_STR}/roles", tags=["Roles"])
app.include_router(menus.router, prefix=f"{settings.API_V1_STR}/menus", tags=["Menus"])
app.include_router(role_rights.router, prefix=f"{settings.API_V1_STR}/role-rights", tags=["Role Rights"])

# Locations Hierarchy
from app.api.v1 import locations
app.include_router(locations.router, prefix=f"{settings.API_V1_STR}/locations", tags=["Locations"])

# Vendor Management
from app.api.v1 import vendors
app.include_router(vendors.router, prefix=f"{settings.API_V1_STR}/vendors", tags=["Vendors"])

# Customer Vehicles
from app.api.v1 import vehicles
app.include_router(vehicles.router, prefix=f"{settings.API_V1_STR}/vehicles", tags=["Vehicles"])

# Financial Settlements
from app.api.v1 import settlements
app.include_router(settlements.router, prefix=f"{settings.API_V1_STR}/settlements", tags=["Settlements"])

# Telematics & Telemetry
from app.api.v1 import telematics, telemetry
app.include_router(telematics.router, prefix=f"{settings.API_V1_STR}/telematics", tags=["IoT & Telematics"])
app.include_router(telemetry.router, prefix=f"{settings.API_V1_STR}/telemetry", tags=["Real-time Tracking"])

# Extra Operations
from app.api.v1 import ml, admin_roles, admin_kyc, admin_users, audit, battery_catalog, logistics
app.include_router(ml.router, prefix=f"{settings.API_V1_STR}/ml", tags=["Machine Learning"])
app.include_router(admin_roles.router, prefix=f"{settings.API_V1_STR}/admin/roles", tags=["Admin Roles"])
app.include_router(admin_kyc.router, prefix=f"{settings.API_V1_STR}/admin/kyc", tags=["Admin KYC"])
app.include_router(admin_users.router, prefix=f"{settings.API_V1_STR}/admin/users", tags=["Admin Users"])
app.include_router(audit.router, prefix=f"{settings.API_V1_STR}/audit", tags=["Audit"])
app.include_router(battery_catalog.router, prefix=f"{settings.API_V1_STR}/catalog", tags=["Inventory Catalog"])
app.include_router(logistics.router, prefix=f"{settings.API_V1_STR}/logistics", tags=["Logistics"])

app.include_router(admin_router, prefix=f"{settings.API_V1_STR}/admin/main", tags=["Admin Comprehensive"])


# Webhooks
# Webhooks
app.include_router(razorpay_webhook.router, prefix="/api/webhooks", tags=["Webhooks"])

# Battery Catalog (Specs)
from app.api.v1 import battery_catalog
app.include_router(battery_catalog.router, prefix=f"{settings.API_V1_STR}/batteries", tags=["Battery Catalog"])

# Logistics (Warehouses & Transfers)
from app.api.v1 import logistics
app.include_router(logistics.router, prefix=f"{settings.API_V1_STR}/logistics", tags=["Logistics & Supply Chain"])


@app.get("/")
async def root():
    return {
        "message": "Welcome to WEZU Energy API",
        "status": "Running",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
