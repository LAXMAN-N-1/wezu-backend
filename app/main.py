from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings

# import sentry_sdk
# from sentry_sdk.integrations.fastapi import FastApiIntegration

# if settings.SENTRY_DSN:
#     sentry_sdk.init(
#         dsn=settings.SENTRY_DSN,
#         environment=settings.ENVIRONMENT,
#         traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
#         integrations=[FastApiIntegration()]
#     )

# Customer-facing endpoints
from app.api.v1 import (
    auth, users, profile, kyc, stations, batteries, rentals, bookings,
    wallet, payments, notifications, support, favorites, analytics, 
    transactions, promo, faqs, iot, swaps, i18n, fraud, branches, 
    organizations, warehouses, screens, stock, dealers, logistics, 
    settlements, telemetry, vehicles, locations, system, roles, 
    menus, role_rights, admin_kyc, audit, ml, inventory,
    admin_stations, station_monitoring, user_analytics,
    indents, grn, station_camera, maintenance, dealer_support
)
from app.api.v1.admin import (
    support as admin_support, 
    faqs as admin_faqs, 
    analytics as admin_analytics, 
    users as admin_users,
    promo as admin_coupons,
    reviews as admin_reviews,
    roles as admin_roles,
    legal as admin_legal,
    banners as admin_banners,
    media as admin_media,
    blogs as admin_blogs,
    campaigns as admin_campaigns
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

from fastapi.openapi.docs import get_swagger_ui_html

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=None,  # Disable default docs because we're overriding it
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Override Swagger UI CDN to use cdnjs instead of jsdelivr/unpkg (which might be blocked)"""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.11.0/swagger-ui-bundle.min.js",
        swagger_css_url="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.11.0/swagger-ui.min.css",
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

from app.middleware.security import SecureHeadersMiddleware
app.add_middleware(SecureHeadersMiddleware)

# Audit Logging Middleware
app.add_middleware(AuditMiddleware)


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if settings.ENVIRONMENT == "production" else ["*"],
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
app.include_router(user_analytics.router, prefix=f"{customer_api}/users", tags=["Customer: User Analytics"])

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
app.include_router(admin_legal.router, prefix=f"{admin_api}/legal", tags=["Admin: CMS - Legal"], dependencies=admin_deps)
app.include_router(admin_banners.router, prefix=f"{admin_api}/banners", tags=["Admin: CMS - Banners"], dependencies=admin_deps)
app.include_router(admin_media.router, prefix=f"{admin_api}/media", tags=["Admin: CMS - Media"], dependencies=admin_deps)
app.include_router(admin_analytics.router, prefix=f"{admin_api}/analytics", tags=["Admin: Analytics"], dependencies=admin_deps)
app.include_router(admin_coupons.router, prefix=f"{admin_api}/coupons", tags=["Admin: Coupons"], dependencies=admin_deps)
app.include_router(admin_blogs.router, prefix=f"{admin_api}/blogs", tags=["Admin: CMS - Blogs"], dependencies=admin_deps)
app.include_router(admin_reviews.router, prefix=f"{admin_api}/reviews", tags=["Admin: Review Moderation"], dependencies=admin_deps)
app.include_router(admin_stations.router, prefix=f"{admin_api}/stations", tags=["Admin: Stations"], dependencies=admin_deps)
app.include_router(admin_campaigns.router, prefix=f"{admin_api}/campaigns", tags=["Admin: Campaigns"], dependencies=admin_deps)
app.include_router(maintenance.router, prefix=f"{admin_api}/maintenance", tags=["Admin: Maintenance"], dependencies=admin_deps)

# 3. Monitoring Application Endpoints
monitoring_api = f"{settings.API_V1_STR}/monitoring"
app.include_router(station_monitoring.router, prefix=f"{monitoring_api}/stations", tags=["Monitoring: Stations"])
app.include_router(station_camera.router, prefix=f"{monitoring_api}/cameras", tags=["Monitoring: Station Cameras"])

# 3. Dealer Application Endpoints
dealer_api = f"{settings.API_V1_STR}/dealer"
dealer_deps = [Depends(deps.get_current_user)] # Granular checks inside routers for now, or check_permission("dealer_dashboard")
app.include_router(dealers.router, prefix=f"{dealer_api}/profile", tags=["Dealer: Profile"], dependencies=dealer_deps)
app.include_router(stock.router, prefix=f"{dealer_api}/stock", tags=["Dealer: Stock"], dependencies=dealer_deps)
app.include_router(settlements.router, prefix=f"{dealer_api}/settlements", tags=["Dealer: Settlements"], dependencies=dealer_deps)
app.include_router(dealer_support.router, prefix=f"{settings.API_V1_STR}/dealer-portal/tickets", tags=["Dealer Portal: Support"], dependencies=dealer_deps)

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
app.include_router(indents.router, prefix=f"{settings.API_V1_STR}/indents", tags=["Inventory: Indents"])
app.include_router(grn.router, prefix=f"{settings.API_V1_STR}/grn", tags=["Inventory: GRN"])

# RBAC Management Endpoints
app.include_router(roles.router, prefix=f"{settings.API_V1_STR}/roles", tags=["RBAC: Roles"])
app.include_router(menus.router, prefix=f"{settings.API_V1_STR}/menus", tags=["RBAC: Menus"])
app.include_router(role_rights.router, prefix=f"{settings.API_V1_STR}/role-rights", tags=["RBAC: Role Rights"])




# Analytics Module (V2 Architecture)
from app.api.v1.analytics import analytics_router
app.include_router(analytics_router, prefix=f"{settings.API_V1_STR}/analytics")


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

