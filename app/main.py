from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
import ssl

# Fix for macOS local dev SSL certificate verification errors with urlopen
if settings.ENVIRONMENT != "production":
    try:
        _create_unverified_https_context = ssl._create_unverified_context
    except AttributeError:
        pass
    else:
        ssl._create_default_https_context = _create_unverified_https_context

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        integrations=[FastApiIntegration()]
    )

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
    roles as admin_roles,
    legal as admin_legal,
    banners as admin_banners,
    media as admin_media,
    blogs as admin_blogs
)
from app.api.admin import router as admin_router
from app.api.v1.dashboard import router as dashboard_router
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
    # During tests we skip heavy startup work (DB schema seeds, schedulers, MQTT).
    if settings.ENVIRONMENT == "test":
        yield
        return

    # 1. DB Init
    from app.db.session import init_db
    init_db()
    
    # 2. Scheduler
    start_scheduler()
    
    # 3. MQTT and WebSocket
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

@app.get("/debug-routes")
def debug_routes():
    return {"status": "ok", "routes": [r.path for r in app.routes]}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# ----------------------------
# Rate Limiting
# ----------------------------
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# RBAC Middleware
from app.middleware.rbac_middleware import RBACMiddleware
app.add_middleware(RBACMiddleware)

# GZip Compression
from fastapi.middleware.gzip import GZipMiddleware
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
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])

# Customer App Auth (JSON-based login/register for Flutter app)
from app.api.v1 import customer_auth
app.include_router(customer_auth.router, prefix=f"{settings.API_V1_STR}/customer/auth", tags=["Customer Auth"])
from app.api.v1 import sessions
app.include_router(sessions.router, prefix=f"{settings.API_V1_STR}/sessions", tags=["Session Management"])
app.include_router(users.router, prefix=f"{settings.API_V1_STR}/users", tags=["Users"])
from app.api.v1 import admin_users, admin_user_bulk
app.include_router(admin_users.router, prefix=f"{settings.API_V1_STR}/admin/users", tags=["Admin User Management"])
app.include_router(admin_user_bulk.router, prefix=f"{settings.API_V1_STR}/admin/users", tags=["Admin User Bulk Operations"])
app.include_router(kyc.router, prefix=f"{settings.API_V1_STR}", tags=["KYC"])
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

# 2. Admin Application Endpoints
admin_api = f"{settings.API_V1_STR}/admin"
from app.api import deps
admin_deps = [Depends(deps.get_current_active_superuser)]

# Use the consolidated admin router which includes stations, users, rentals, etc.
app.include_router(admin_router, prefix=f"{admin_api}", tags=["Admin: Main"], dependencies=admin_deps)

# Dashboard specific
app.include_router(dashboard_router, prefix=f"{settings.API_V1_STR}/dashboard", tags=["Admin: Dashboard"], dependencies=admin_deps)

# 3. Monitoring Application Endpoints
monitoring_api = f"{settings.API_V1_STR}/monitoring"
from app.api.v1 import station_monitoring
app.include_router(station_monitoring.router, prefix=f"{monitoring_api}/stations", tags=["Monitoring: Stations"])

# 3. Dealer Application Endpoints
dealer_api = f"{settings.API_V1_STR}/dealer"
dealer_deps = [Depends(deps.get_current_user)] # Granular checks inside routers for now, or check_permission("dealer_dashboard")
app.include_router(dealers.router, prefix=f"{dealer_api}/profile", tags=["Dealer: Profile"], dependencies=dealer_deps)
app.include_router(stock.router, prefix=f"{dealer_api}/stock", tags=["Dealer: Stock"], dependencies=dealer_deps)
app.include_router(settlements.router, prefix=f"{dealer_api}/settlements", tags=["Dealer: Settlements"], dependencies=dealer_deps)

# 3b. Dealer Portal Endpoints (Auth, Dashboard, Tickets, Customers, Settings, Onboarding, Documents, Roles)
from app.api.v1 import dealer_portal_auth, dealer_portal_dashboard, dealer_portal_tickets, dealer_portal_customers, dealer_portal_settings, dealer_onboarding, dealer_documents, dealer_portal_roles
app.include_router(dealer_portal_auth.router, prefix=f"{dealer_api}/auth", tags=["Dealer Portal: Auth"])
app.include_router(dealer_onboarding.router, prefix=f"{dealer_api}/onboarding", tags=["Dealer Portal: Onboarding"], dependencies=dealer_deps)
app.include_router(dealer_documents.router, prefix=f"{dealer_api}/documents", tags=["Dealer Portal: Documents"], dependencies=dealer_deps)
app.include_router(dealer_portal_dashboard.router, prefix=f"{dealer_api}/portal", tags=["Dealer Portal: Dashboard"], dependencies=dealer_deps)
app.include_router(dealer_portal_tickets.router, prefix=f"{dealer_api}/portal/tickets", tags=["Dealer Portal: Tickets"], dependencies=dealer_deps)
app.include_router(dealer_portal_customers.router, prefix=f"{dealer_api}/portal/customers", tags=["Dealer Portal: Customers"], dependencies=dealer_deps)
app.include_router(dealer_portal_settings.router, prefix=f"{dealer_api}/portal/settings", tags=["Dealer Portal: Settings"], dependencies=dealer_deps)
app.include_router(dealer_portal_roles.router, prefix=f"{dealer_api}/portal/roles", tags=["Dealer Portal: Roles"], dependencies=dealer_deps)


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
from app.api.v1 import admin_rbac, security, admin_audit
app.include_router(admin_rbac.router, prefix=f"{settings.API_V1_STR}/admin/rbac", tags=["Admin RBAC"])
app.include_router(security.router, prefix=f"{settings.API_V1_STR}/admin/security", tags=["Admin Security"])
app.include_router(admin_audit.router, prefix=f"{settings.API_V1_STR}/admin/audit-logs", tags=["Admin Audit Logs"])
# app.include_router(support_enhanced.router, prefix=f"{settings.API_V1_STR}/support", tags=["Support Enhanced"])
# app.include_router(rentals_enhanced.router, prefix=f"{settings.API_V1_STR}/rentals", tags=["Rentals Enhanced"])
# app.include_router(purchases_enhanced.router, prefix=f"{settings.API_V1_STR}/purchases", tags=["Purchases Enhanced"])
# app.include_router(analytics_enhanced.router, prefix=f"{settings.API_V1_STR}/analytics", tags=["Analytics Enhanced"])

# Dealer Analytics
from app.api.v1 import dealer_analytics
app.include_router(dealer_analytics.router, prefix=f"{settings.API_V1_STR}/dealer-analytics", tags=["Dealer Analytics"])

# Dealer Campaigns
from app.api.v1 import dealer_campaigns
app.include_router(dealer_campaigns.router, prefix=f"{settings.API_V1_STR}/dealer-campaigns", tags=["Dealer Campaigns"])

# Dealer Stations (Inventory & Management)
from app.api.v1 import dealer_stations
app.include_router(dealer_stations.router, prefix=f"{settings.API_V1_STR}/dealer-stations", tags=["Dealer Stations"])

# RBAC API Routes
app.include_router(roles.router, prefix=f"{settings.API_V1_STR}/roles", tags=["Roles"])
app.include_router(menus.router, prefix=f"{settings.API_V1_STR}/menus", tags=["Menus"])
app.include_router(role_rights.router, prefix=f"{settings.API_V1_STR}/role-rights", tags=["Role Rights"])

# ML & Dynamics (Phase 5)
from app.api.v1 import ml, admin_roles, admin_kyc, admin_financial_reports
app.include_router(ml.router, prefix=f"{settings.API_V1_STR}/ml", tags=["Machine Learning"])
app.include_router(admin_roles.router, prefix=f"{settings.API_V1_STR}/admin", tags=["Admin Role Management"])
app.include_router(admin_kyc.router, prefix=f"{settings.API_V1_STR}/admin/kyc", tags=["Admin KYC Management"])
app.include_router(admin_financial_reports.router, prefix=f"{settings.API_V1_STR}/admin/reports", tags=["Admin Financial Reports"])


# Webhooks
app.include_router(razorpay_webhook.router, prefix="/api/webhooks", tags=["Webhooks"])

# Battery Catalog (Specs)
from app.api.v1 import catalog
app.include_router(catalog.router, prefix=f"{settings.API_V1_STR}/catalog", tags=["Battery Catalog"])

# Logistics already included above

# Dealer Onboarding
from app.api.v1 import dealers, dealer_kyc, dealer_commission
app.include_router(dealers.router, prefix=f"{settings.API_V1_STR}/dealers", tags=["Dealers"])
app.include_router(dealer_kyc.router, prefix=f"{settings.API_V1_STR}/dealer-kyc", tags=["Dealer KYC"])
app.include_router(dealer_commission.router, prefix=f"{settings.API_V1_STR}/dealer-commission", tags=["Dealer Commission & Settlement"])

# Driver Onboarding
from app.api.v1 import drivers
app.include_router(drivers.router, prefix=f"{settings.API_V1_STR}/drivers", tags=["Driver Onboarding"])


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
