import traceback
import sys

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from app.core.config import settings
except Exception:
    traceback.print_exc()
    sys.exit(1)

print("DEBUG: main.py - Imports started")


# Customer-facing endpoints
from app.api.v1 import (
    auth, users, profile, kyc, stations, batteries, rentals, bookings,
    wallet, payments, notifications, support, favorites, analytics, 
    transactions, promo, faqs, iot, swaps, i18n, fraud, branches, 
    organizations, warehouses, screens, stock, dealers, logistics, 
    settlements, telemetry, vehicles, locations, system, roles, 
    menus, role_rights, admin_kyc, audit, ml, inventory,
    admin_stations, station_monitoring
)
from app.api.v1.admin import (
    support as admin_support, 
    faqs as admin_faqs, 
    analytics as admin_analytics, 
    users as admin_users,
    promo as admin_coupons,
    reviews as admin_reviews,
    roles as admin_roles
)
from app.api.admin import router as admin_router
from app.api.webhooks import razorpay as razorpay_webhook
from app.middleware.rate_limit import limiter
from app.middleware.audit import AuditMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.workers import start_scheduler, stop_scheduler
from app.services.websocket_service import heartbeat_task
from app.services.mqtt_service import start_mqtt_service, stop_mqtt_service
import asyncio

# ----------------------------
# Lifespan
# ----------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background scheduler on app startup and init DB"""
    from app.db.session import init_db
    init_db()
    start_scheduler()
    
    # Start MQTT and WebSocket background tasks - making MQTT non-fatal for dev
    try:
        start_mqtt_service()
    except Exception as e:
        print(f"MQTT Service Startup Error: {e}")
        
    asyncio.create_task(heartbeat_task())
    
    yield
    
    # 4. Cleanup
    try:
        stop_scheduler()
    except:
        pass
    try:
        stop_mqtt_service()
    except:
        pass

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# ----------------------------
# Rate Limiting
# ----------------------------
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ----------------------------
# Middleware
# ----------------------------
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Audit Logging Middleware
app.add_middleware(AuditMiddleware)

# Configure CORS - Outermost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In development "*" is often safest for dynamic ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared Auth Routes (needed for admin login at /api/v1/auth/admin/login)
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Auth"])

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
app.include_router(promo.router, prefix=f"{settings.API_V1_STR}/coupons", tags=["Customer: Coupons"])
app.include_router(swaps.router, prefix=f"{customer_api}/swaps", tags=["Customer: Swaps"])
app.include_router(vehicles.router, prefix=f"{customer_api}/vehicles", tags=["Customer: Vehicles"])

# 2. Admin Application Endpoints
admin_api = f"{settings.API_V1_STR}/admin"
from app.api import deps
admin_deps = [Depends(deps.get_current_active_superuser)]
app.include_router(admin_router, prefix=f"{admin_api}", tags=["Admin: Main"], dependencies=admin_deps)
app.include_router(admin_user_mgmt.router, prefix=f"{admin_api}/users", tags=["Admin: Users"], dependencies=admin_deps)
app.include_router(admin_roles.router, prefix=f"{admin_api}/roles", tags=["Admin: Roles"], dependencies=admin_deps)
app.include_router(admin_kyc.router, prefix=f"{admin_api}/kyc", tags=["Admin: KYC"], dependencies=admin_deps)
app.include_router(audit.router, prefix=f"{admin_api}/audit", tags=["Admin: Audit"], dependencies=admin_deps)
app.include_router(fraud.router, prefix=f"{admin_api}/fraud", tags=["Admin: Fraud"], dependencies=admin_deps)
app.include_router(ml.router, prefix=f"{admin_api}/ml", tags=["Admin: ML & Analytics"], dependencies=admin_deps)
app.include_router(admin_support.router, prefix=f"{admin_api}/support", tags=["Admin: Support"], dependencies=admin_deps)
app.include_router(admin_faqs.router, prefix=f"{admin_api}/faq", tags=["Admin: FAQ"], dependencies=admin_deps)
app.include_router(admin_legal.router, prefix=f"{admin_api}/legal", tags=["Admin: CMS - Legal"], dependencies=admin_deps)
app.include_router(admin_banners.router, prefix=f"{admin_api}/banners", tags=["Admin: CMS - Banners"], dependencies=admin_deps)
app.include_router(admin_media.router, prefix=f"{admin_api}/media", tags=["Admin: CMS - Media"], dependencies=admin_deps)
app.include_router(admin_analytics.router, prefix=f"{admin_api}/analytics", tags=["Admin: Analytics"], dependencies=admin_deps)
app.include_router(admin_coupons.router, prefix=f"{admin_api}/coupons", tags=["Admin: Coupons"], dependencies=admin_deps)
app.include_router(admin_blogs.router, prefix=f"{admin_api}/blogs", tags=["Admin: CMS - Blogs"], dependencies=admin_deps)
app.include_router(admin_reviews.router, prefix=f"{admin_api}/reviews", tags=["Admin: Review Moderation"], dependencies=admin_deps)
app.include_router(admin_stations.router, prefix=f"{admin_api}/stations", tags=["Admin: Stations"], dependencies=admin_deps)

# 3. Monitoring Application Endpoints
monitoring_api = f"{v1_prefix}/monitoring"
app.include_router(station_monitoring.router, prefix=f"{monitoring_api}/stations", tags=["Monitoring: Stations"])

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

# Customer Vehicles
from app.api.v1 import vehicles
app.include_router(vehicles.router, prefix=f"{settings.API_V1_STR}/vehicles", tags=["Customer Vehicles"])

# Swap Operations
from app.api.v1 import swaps
app.include_router(swaps.router, prefix=f"{settings.API_V1_STR}/swaps", tags=["Swap Operations"])

# Financial Settlements
from app.api.v1 import settlements
app.include_router(settlements.router, prefix=f"{settings.API_V1_STR}/settlements", tags=["Financial Settlements"])

# Telematics Ingestion
from app.api.v1 import telematics
app.include_router(telematics.router, prefix=f"{settings.API_V1_STR}/telematics", tags=["Telematics & IoT"])

# Support Tickets
from app.api.v1 import support
app.include_router(support.router, prefix=f"{settings.API_V1_STR}/support", tags=["Support & Ticketing"])

# Admin / RBAC
from app.api.v1 import admin_rbac, security
app.include_router(admin_rbac.router, prefix=f"{settings.API_V1_STR}/admin/rbac", tags=["Admin RBAC"])
app.include_router(security.router, prefix=f"{settings.API_V1_STR}/admin/security", tags=["Admin Security"])
app.include_router(support_enhanced.router, prefix=f"{settings.API_V1_STR}/support", tags=["Support Enhanced"])
app.include_router(rentals_enhanced.router, prefix=f"{settings.API_V1_STR}/rentals", tags=["Rentals Enhanced"])
app.include_router(purchases_enhanced.router, prefix=f"{settings.API_V1_STR}/purchases", tags=["Purchases Enhanced"])
app.include_router(analytics_enhanced.router, prefix=f"{settings.API_V1_STR}/analytics", tags=["Analytics Enhanced"])

    # Admin Analytics - Updated 
from app.api.v1 import admin_analytics
app.include_router(admin_analytics.router, prefix=f"{settings.API_V1_STR}/admin/analytics", tags=["Admin Analytics"])


# RBAC API Routes
app.include_router(roles.router, prefix=f"{settings.API_V1_STR}/roles", tags=["Roles"])
app.include_router(menus.router, prefix=f"{settings.API_V1_STR}/menus", tags=["Menus"])
app.include_router(role_rights.router, prefix=f"{settings.API_V1_STR}/role-rights", tags=["Role Rights"])

# ML & Dynamics (Phase 5)
from app.api.v1 import ml, admin_roles, admin_kyc, admin_users
app.include_router(ml.router, prefix=f"{settings.API_V1_STR}/ml", tags=["Machine Learning"])
app.include_router(admin_roles.router, prefix=f"{settings.API_V1_STR}/admin", tags=["Admin Role Management"])
app.include_router(admin_kyc.router, prefix=f"{settings.API_V1_STR}/admin/kyc", tags=["Admin KYC Management"])
app.include_router(admin_users.router, prefix=f"{settings.API_V1_STR}/admin/users", tags=["Admin User Analytics"])

# Audit Logs
from app.api.v1 import audit
app.include_router(audit.router, prefix=f"{settings.API_V1_STR}/audit", tags=["Audit Logs"])

app.include_router(admin_router, prefix=f"{settings.API_V1_STR}/admin/main", tags=["Admin Comprehensive"])


# Webhooks
app.include_router(razorpay_webhook.router, prefix="/api/webhooks", tags=["Webhooks"])


@app.get("/")
async def root():
    return {
        "message": "Welcome to WEZU Energy API",
        "status": "Running",
        "version": "1.0.0",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}

