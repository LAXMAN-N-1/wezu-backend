from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings


# Customer-facing endpoints only
from app.api.v1 import (
    auth, users, kyc, stations, batteries, rentals, wallet, payments, 
    notifications, support, favorites, analytics, transactions, promo, 
    faqs, iot, swaps, i18n, fraud, branches, organizations, warehouses, screens, stock, dealers
)
from app.api.v1.admin import support as admin_support
from app.api.v1.admin import faqs as admin_faqs
from app.api.v1.admin import analytics as admin_analytics
from app.api.v1 import inventory
from app.api.v1.admin import promo as admin_coupons
from app.api.v1.admin import reviews as admin_reviews
from app.api.v1.admin import roles as admin_roles
from app.api.v1.admin import users as admin_user_mgmt
# Enhanced customer endpoints
from app.api.v1 import (
    system, payments_enhanced, wallet_enhanced, notifications_enhanced,
    support_enhanced, rentals_enhanced, purchases_enhanced, analytics_enhanced,
    roles, menus, role_rights
)
from app.api.admin import router as admin_router
from app.api.webhooks import razorpay as razorpay_webhook
from app.middleware.rate_limit import limiter
from app.middleware.audit import AuditMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Background Workers
from app.workers import start_scheduler, stop_scheduler
from app.services.websocket_service import heartbeat_task
from app.services.mqtt_service import start_mqtt_service, stop_mqtt_service
import asyncio
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background scheduler on app startup and init DB"""
    from app.db.session import init_db
    init_db()
    start_scheduler()
    
    # Start MQTT and WebSocket background tasks
    start_mqtt_service()
    asyncio.create_task(heartbeat_task())
    
    yield
    """Stop background scheduler on app shutdown"""
    stop_scheduler()
    stop_mqtt_service()

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

# Audit Logging Middleware
app.add_middleware(AuditMiddleware)

# Customer API Routes
# 1. Customer Application Endpoints
customer_api = f"{settings.API_V1_STR}/customer"
app.include_router(auth.router, prefix=f"{customer_api}/auth", tags=["Customer: Auth"])
app.include_router(users.router, prefix=f"{customer_api}/users", tags=["Customer: Users"])
app.include_router(kyc.router, prefix=f"{customer_api}/kyc", tags=["Customer: KYC"])
app.include_router(stations.router, prefix=f"{customer_api}/stations", tags=["Customer: Stations"])
app.include_router(batteries.router, prefix=f"{customer_api}/batteries", tags=["Customer: Batteries"])
app.include_router(rentals.router, prefix=f"{customer_api}/rentals", tags=["Customer: Rentals"])
app.include_router(wallet.router, prefix=f"{customer_api}/wallet", tags=["Customer: Wallet"])
app.include_router(payments.router, prefix=f"{customer_api}/payments", tags=["Customer: Payments"])
app.include_router(notifications.router, prefix=f"{customer_api}/notifications", tags=["Customer: Notifications"])
app.include_router(support.router, prefix=f"{customer_api}/support", tags=["Customer: Support"])
app.include_router(favorites.router, prefix=f"{settings.API_V1_STR}/users/me/favorites", tags=["Customer: Favorites"])
app.include_router(analytics.router, prefix=f"{customer_api}/analytics", tags=["Customer: Analytics"])
app.include_router(promo.router, prefix=f"{settings.API_V1_STR}/coupons", tags=["Customer: Coupons"])
app.include_router(swaps.router, prefix=f"{customer_api}/swaps", tags=["Customer: Swaps"])
app.include_router(vehicles.router, prefix=f"{customer_api}/vehicles", tags=["Customer: Vehicles"])

# 2. Admin Application Endpoints
admin_api = f"{settings.API_V1_STR}/admin"
from app.api import deps
admin_deps = [Depends(deps.get_current_active_superuser)]
app.include_router(admin_router, prefix=f"{admin_api}", tags=["Admin: Main"], dependencies=admin_deps)
app.include_router(admin_users.router, prefix=f"{admin_api}/users", tags=["Admin: Users"], dependencies=admin_deps)
app.include_router(admin_roles.router, prefix=f"{admin_api}/roles", tags=["Admin: Roles"], dependencies=admin_deps)
app.include_router(admin_kyc.router, prefix=f"{admin_api}/kyc", tags=["Admin: KYC"], dependencies=admin_deps)
app.include_router(audit.router, prefix=f"{admin_api}/audit", tags=["Admin: Audit"], dependencies=admin_deps)
app.include_router(fraud.router, prefix=f"{admin_api}/fraud", tags=["Admin: Fraud"], dependencies=admin_deps)
app.include_router(ml.router, prefix=f"{admin_api}/ml", tags=["Admin: ML & Analytics"], dependencies=admin_deps)
app.include_router(admin_support.router, prefix=f"{admin_api}/support", tags=["Admin: Support"], dependencies=admin_deps)
app.include_router(admin_faqs.router, prefix=f"{admin_api}/faq", tags=["Admin: FAQ"], dependencies=admin_deps)
app.include_router(admin_analytics.router, prefix=f"{admin_api}/analytics", tags=["Admin: Analytics"], dependencies=admin_deps)
app.include_router(admin_coupons.router, prefix=f"{admin_api}/coupons", tags=["Admin: Coupons"], dependencies=admin_deps)
app.include_router(admin_reviews.router, prefix=f"{admin_api}/reviews", tags=["Admin: Review Moderation"], dependencies=admin_deps)
app.include_router(admin_roles.router, prefix=f"{admin_api}/roles", tags=["Admin: RBAC"], dependencies=admin_deps)
app.include_router(admin_user_mgmt.router, prefix=f"{admin_api}/users", tags=["Admin: User Management"], dependencies=admin_deps)

# 3. Dealer Application Endpoints
dealer_api = f"{settings.API_V1_STR}/dealer"
dealer_deps = [Depends(deps.get_current_user)] # Granular checks inside routers for now, or check_permission("dealer_dashboard")
app.include_router(dealers.router, prefix=f"{dealer_api}/profile", tags=["Dealer: Profile"], dependencies=dealer_deps)
app.include_router(stock.router, prefix=f"{dealer_api}/stock", tags=["Dealer: Stock"], dependencies=dealer_deps)
app.include_router(settlements.router, prefix=f"{dealer_api}/settlements", tags=["Dealer: Settlements"], dependencies=dealer_deps)

# 4. Logistics Application Endpoints
logistics_api = f"{settings.API_V1_STR}/logistics"
logistics_deps = [Depends(deps.get_current_user)]
app.include_router(logistics.router, prefix=f"{logistics_api}", tags=["Logistics: Main"], dependencies=logistics_deps)
app.include_router(warehouses.router, prefix=f"{logistics_api}/warehouses", tags=["Logistics: Warehouses"], dependencies=logistics_deps)

# 5. Shared / Infrastructure Endpoints
infra_api = f"{settings.API_V1_STR}/infra"
app.include_router(system.router, prefix=f"{infra_api}/system", tags=["Infra: System"])
app.include_router(iot.router, prefix=f"{infra_api}/iot", tags=["Infra: IoT"])
app.include_router(telemetry.router, prefix=f"{infra_api}/telemetry", tags=["Infra: Telemetry"])
app.include_router(i18n.router, prefix=f"{infra_api}/i18n", tags=["Infra: i18n"])
app.include_router(locations.router, prefix=f"{infra_api}/locations", tags=["Infra: Locations"])
app.include_router(inventory.router, prefix=f"{settings.API_V1_STR}/inventory", tags=["Logistics: Inventory"])


# Webhooks
# Webhooks
app.include_router(razorpay_webhook.router, prefix="/api/webhooks", tags=["Webhooks"])

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
