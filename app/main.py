import traceback
import sys
import ssl
import asyncio
from contextlib import asynccontextmanager
from app.core.logging import setup_logging, get_logger

# Initialize structured logging globally
setup_logging()

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.core.config import settings
from app.db.session import engine
from app.api import deps
from app.middleware.rate_limit import limiter
from app.middleware.audit import AuditMiddleware
from app.middleware.security import SecureHeadersMiddleware
from app.middleware.rbac_middleware import RBACMiddleware
from app.api.errors.handlers import add_exception_handlers
from app.workers import start_scheduler, stop_scheduler
from app.services.websocket_service import heartbeat_task
from app.services.mqtt_service import start_mqtt_service, stop_mqtt_service

# Import all routers (Consolidated)
# Import all routers (Consolidated)
from app.api.v1 import (
    auth, customer_auth, sessions, users, profile, kyc, stations, batteries, 
    rentals, wallet, payments, notifications, support, favorites, analytics, 
    transactions, promo, faqs, iot, swaps, i18n, fraud, branches, organizations, 
    warehouses, screens, stock, dealers, logistics, settlements, telemetry, 
    telematics, vehicles, locations, system, roles, menus, role_rights, 
    admin_kyc, audit, ml, inventory, admin_stations, station_monitoring, 
    dealer_portal_auth, dealer_portal_dashboard, dealer_portal_tickets, 
    dealer_portal_customers, dealer_portal_settings, dealer_onboarding, 
    dealer_documents, dealer_portal_roles, dealer_portal_users, 
    dealer_analytics, dealer_campaigns, dealer_stations, drivers, catalog,
    admin_invoices, admin_financial_reports, admin_audit, admin_rbac, admin_users
)
from app.api.v1.admin import (
    support as admin_support, faqs as admin_faqs, analytics as admin_analytics, 
    users as admin_sub_users, promo as admin_coupons, reviews as admin_reviews, 
    roles as admin_roles, legal as admin_legal, banners as admin_banners, 
    media as admin_media, blogs as admin_blogs
)
from app.api.admin import router as global_admin_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.webhooks import razorpay as razorpay_webhook

# Fix for macOS local dev SSL certificate verification errors with urlopen
if settings.ENVIRONMENT != "production":
    try:
        _create_unverified_https_context = ssl._create_unverified_context
    except AttributeError:
        pass
    else:
        ssl._create_default_https_context = _create_unverified_https_context

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        integrations=[FastApiIntegration()]
    )

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background scheduler and connections on startup"""
    scheduler_started = False
    mqtt_started = False

    if settings.ENVIRONMENT == "test":
        yield
        return

    if settings.DB_INIT_ON_STARTUP:
        try:
            logger.info("Initializing database schema (DB_INIT_ON_STARTUP is True)...")
            from app.db.session import init_db
            init_db()
            logger.info("Database schema initialization complete.")
        except Exception:
            logger.exception("DB init on startup failed; continuing")

    if settings.RUN_BACKGROUND_TASKS:
        logger.info("Starting background tasks...")
        if settings.SCHEDULER_ENABLED:
            try:
                logger.info("Starting background scheduler...")
                start_scheduler()
                scheduler_started = True
                logger.info("Background scheduler started.")
            except Exception:
                logger.exception("Scheduler startup failed")

        if settings.MQTT_ENABLED:
            try:
                logger.info("Starting MQTT service...")
                start_mqtt_service()
                mqtt_started = True
                logger.info("MQTT service startup sequence initiated.")
            except Exception:
                logger.exception("MQTT startup failed")

        logger.info("Creating heartbeat task...")
        asyncio.create_task(heartbeat_task())
    
    yield
    
    if scheduler_started: stop_scheduler()
    if mqtt_started: stop_mqtt_service()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# ----------------------------
# Middlewares & Global Config
# ----------------------------
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
add_exception_handlers(app)

app.add_middleware(RBACMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(SecureHeadersMiddleware)
app.add_middleware(AuditMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if settings.ENVIRONMENT == "production" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# System & Health
# ----------------------------
@app.get("/health", tags=["System"])
async def health_check():
    """Deep health check for database and basic connectivity"""
    from sqlalchemy import text
    db_ok = False
    try:
        from app.db.session import SessionLocal
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            db_ok = True
    except Exception as e:
        logger.error(f"Health check DB failure: {e}")

    return {
        "status": "ok" if db_ok else "degraded",
        "database": "online" if db_ok else "offline",
        "environment": settings.ENVIRONMENT,
        "version": "1.0.0"
    }

@app.get("/", tags=["System"])
async def root():
    return {"message": f"Welcome to {settings.PROJECT_NAME} API", "version": "1.0.0"}

# ----------------------------
# API V1 - Customer Endpoints
# ----------------------------
v1_str = settings.API_V1_STR

# Authentication
app.include_router(auth.router, prefix=f"{v1_str}/auth", tags=["Auth"])
app.include_router(customer_auth.router, prefix=f"{v1_str}/customer/auth", tags=["Customer Auth"])
app.include_router(sessions.router, prefix=f"{v1_str}/sessions", tags=["Sessions"])

# Core Entities
app.include_router(users.router, prefix=f"{v1_str}/users", tags=["Users"])
app.include_router(profile.router, prefix=f"{v1_str}/profile", tags=["Profile"])
app.include_router(kyc.router, prefix=v1_str, tags=["KYC"])
app.include_router(stations.router, prefix=f"{v1_str}/stations", tags=["Stations"])
app.include_router(batteries.router, prefix=f"{v1_str}/batteries", tags=["Batteries"])
app.include_router(rentals.router, prefix=f"{v1_str}/rentals", tags=["Rentals"])
app.include_router(vehicles.router, prefix=f"{v1_str}/vehicles", tags=["Vehicles"])
app.include_router(swaps.router, prefix=f"{v1_str}/swaps", tags=["Swaps"])

# Finance & Notifications
app.include_router(wallet.router, prefix=f"{v1_str}/wallet", tags=["Wallet"])
app.include_router(payments.router, prefix=f"{v1_str}/payments", tags=["Payments"])
app.include_router(notifications.router, prefix=f"{v1_str}/notifications", tags=["Notifications"])
app.include_router(support.router, prefix=f"{v1_str}/support", tags=["Support"])
app.include_router(favorites.router, prefix=f"{v1_str}/favorites", tags=["Favorites"])

# Utility & Information
app.include_router(promo.router, prefix=f"{v1_str}/promo", tags=["Promo"])
app.include_router(faqs.router, prefix=f"{v1_str}/faqs", tags=["FAQs"])
app.include_router(catalog.router, prefix=f"{v1_str}/catalog", tags=["Catalog"])
app.include_router(i18n.router, prefix=f"{v1_str}/i18n", tags=["i18n"])
app.include_router(screens.router, prefix=f"{v1_str}/screens", tags=["UI Config"])

# ----------------------------
# API V1 - Admin Endpoints
# ----------------------------
admin_api = f"{v1_str}/admin"
admin_deps = [Depends(deps.get_current_active_superuser)]

# Global Admin Router
app.include_router(global_admin_router, prefix=admin_api, tags=["Admin: Core"], dependencies=admin_deps)
app.include_router(dashboard_router, prefix=f"{v1_str}/dashboard", tags=["Admin: Dashboard"], dependencies=admin_deps)

# Admin Domain Specific
app.include_router(admin_users.router, prefix=f"{admin_api}/users", tags=["Admin: Users"], dependencies=admin_deps)
app.include_router(admin_kyc.router, prefix=f"{admin_api}/kyc", tags=["Admin: KYC"], dependencies=admin_deps)
app.include_router(admin_stations.router, prefix=f"{admin_api}/stations", tags=["Admin: Stations"], dependencies=admin_deps)
app.include_router(admin_invoices.router, prefix=f"{admin_api}/invoices", tags=["Admin: Invoices"], dependencies=admin_deps)
app.include_router(admin_analytics.router, prefix=f"{admin_api}/analytics", tags=["Admin: Analytics"], dependencies=admin_deps)
app.include_router(admin_audit.router, prefix=f"{admin_api}/audit-logs", tags=["Admin: Audit"], dependencies=admin_deps)
app.include_router(admin_rbac.router, prefix=f"{admin_api}/rbac", tags=["Admin: RBAC"], dependencies=admin_deps)
app.include_router(admin_legal.router, prefix=f"{admin_api}/legal", tags=["Admin: Legal"], dependencies=admin_deps)
app.include_router(admin_banners.router, prefix=f"{admin_api}/banners", tags=["Admin: Banners"], dependencies=admin_deps)
app.include_router(admin_blogs.router, prefix=f"{admin_api}/blogs", tags=["Admin: Blogs"], dependencies=admin_deps)

# ----------------------------
# API V1 - Dealer Endpoints
# ----------------------------
dealer_api = f"{v1_str}/dealer"
dealer_deps = [Depends(deps.get_current_user)]

app.include_router(dealer_portal_auth.router, prefix=f"{dealer_api}/auth", tags=["Dealer: Auth"])
app.include_router(dealer_portal_dashboard.router, prefix=f"{dealer_api}/portal", tags=["Dealer: Dashboard"], dependencies=dealer_deps)
app.include_router(dealer_portal_tickets.router, prefix=f"{dealer_api}/portal/tickets", tags=["Dealer: Tickets"], dependencies=dealer_deps)
app.include_router(dealer_onboarding.router, prefix=f"{dealer_api}/onboarding", tags=["Dealer: Onboarding"], dependencies=dealer_deps)

# ----------------------------
# API V1 - Logistics & System
# ----------------------------
app.include_router(logistics.router, prefix=f"{v1_str}/logistics", tags=["Logistics"])
app.include_router(telematics.router, prefix=f"{v1_str}/telematics", tags=["Telematics"])
app.include_router(iot.router, prefix=f"{v1_str}/iot", tags=["IoT"])
app.include_router(razorpay_webhook.router, prefix="/api/webhooks", tags=["Webhooks"])
