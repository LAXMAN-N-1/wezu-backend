import traceback
import sys
import ssl
import asyncio
import os
from contextlib import asynccontextmanager
from app.core.logging import setup_logging, get_logger

# Initialize structured logging globally
setup_logging()

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

from app.core.config import settings
from app.db.session import engine
from app.api import deps
import app.models.all  # noqa: F401  Ensure all SQLModel classes are registered before first query.
from app.middleware.rate_limit import limiter
from app.middleware.audit import AuditMiddleware
from app.middleware.security import SecureHeadersMiddleware
from app.middleware.proxy_headers import TrustedProxyHeadersMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.rbac_middleware import RBACMiddleware
from app.api.errors.handlers import add_exception_handlers
from app.workers import start_scheduler, stop_scheduler
from app.services.websocket_service import heartbeat_task
from app.services.mqtt_service import start_mqtt_service, stop_mqtt_service
from app.services.request_audit_queue import request_audit_queue

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
    admin_invoices, admin_financial_reports, admin_audit, admin_rbac, admin_users,
    admin_dealers
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
logger.info(
    "logging.initialized",
    environment=settings.ENVIRONMENT,
    log_level=settings.LOG_LEVEL,
    log_access_logs=settings.LOG_ACCESS_LOGS,
    log_requests=settings.LOG_REQUESTS,
)

from app.utils.cors import cors_headers_for_origin

CORS_ALLOWED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOWED_HEADERS = [
    "Authorization",
    "Content-Type",
    "Accept",
    "Origin",
    "X-Requested-With",
    "X-Request-ID",
    "X-Correlation-ID",
]


class CORSErrorMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        origin = request.headers.get("origin", "")
        for key, value in cors_headers_for_origin(origin).items():
            response.headers[key] = value
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background scheduler and connections on startup"""
    scheduler_started = False
    mqtt_started = False
    request_audit_started = False

    logger.info(
        "Startup settings: env=%s db_pool_size=%s db_max_overflow=%s db_pool_timeout=%s db_pool_recycle=%s "
        "audit_request_logging=%s audit_queue_max=%s audit_batch=%s audit_flush_ms=%s audit_workers=%s "
        "gunicorn_workers=%s gunicorn_timeout=%s gunicorn_graceful_timeout=%s",
        settings.ENVIRONMENT,
        settings.DB_POOL_SIZE,
        settings.DB_MAX_OVERFLOW,
        settings.DB_POOL_TIMEOUT,
        settings.DB_POOL_RECYCLE,
        settings.AUDIT_REQUEST_LOGGING_ENABLED,
        settings.AUDIT_REQUEST_QUEUE_MAXSIZE,
        settings.AUDIT_REQUEST_BATCH_SIZE,
        settings.AUDIT_REQUEST_FLUSH_MS,
        settings.AUDIT_REQUEST_WORKERS,
        os.getenv("GUNICORN_WORKERS", "1"),
        os.getenv("GUNICORN_TIMEOUT", "60"),
        os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"),
    )

    if settings.ENVIRONMENT == "test":
        yield
        return

    if settings.DB_INIT_ON_STARTUP:
        try:
            logger.info("Running Alembic migrations (DB_INIT_ON_STARTUP is True)...")
            from alembic.config import Config as AlembicConfig
            from alembic import command as alembic_command
            alembic_cfg = AlembicConfig("alembic.ini")
            alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
            alembic_command.upgrade(alembic_cfg, "head")
            logger.info("Alembic migrations complete.")
        except Exception:
            logger.exception("Alembic migration on startup failed; falling back to create_all")
            try:
                from app.db.session import init_db
                init_db()
            except Exception:
                logger.exception("Fallback create_all also failed")

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

    if settings.AUDIT_REQUEST_LOGGING_ENABLED:
        await request_audit_queue.start()
        request_audit_started = True
    
    yield
    
    if scheduler_started: stop_scheduler()
    if mqtt_started: stop_mqtt_service()
    if request_audit_started:
        await request_audit_queue.stop()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# ----------------------------
# Middlewares & Global Config
# ----------------------------
app.state.limiter = limiter
add_exception_handlers(app)

app.add_middleware(RBACMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(SecureHeadersMiddleware)
if settings.AUDIT_REQUEST_LOGGING_ENABLED:
    app.add_middleware(AuditMiddleware)
if settings.ENABLE_TRUSTED_HOST_MIDDLEWARE:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
app.add_middleware(RequestLoggingMiddleware)

# Must run before TrustedHostMiddleware to rewrite Host from trusted proxy headers.
# In Starlette, the most recently added middleware runs first.
app.add_middleware(TrustedProxyHeadersMiddleware)

# Keep error-header patching near the edge, then wrap everything with CORSMiddleware.
app.add_middleware(CORSErrorMiddleware)

# CORSMiddleware must be the outermost layer (added last) so OPTIONS preflight never
# reaches auth middleware and CORS headers are consistently returned.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=CORS_ALLOWED_METHODS,
    allow_headers=CORS_ALLOWED_HEADERS,
    expose_headers=["*"],
)


@app.options("/{full_path:path}", include_in_schema=False)
async def global_options_handler(full_path: str, request: Request):
    origin = request.headers.get("origin", "")
    headers = {
        "Access-Control-Allow-Methods": ", ".join(CORS_ALLOWED_METHODS),
        "Access-Control-Allow-Headers": ", ".join(CORS_ALLOWED_HEADERS),
        "Access-Control-Max-Age": "600",
    }
    headers.update(cors_headers_for_origin(origin))
    return Response(status_code=200, headers=headers)

# ----------------------------
# System & Health
# ----------------------------
def _readiness_payload() -> tuple[dict[str, str], bool]:
    """Run bounded dependency checks for readiness only."""
    from sqlalchemy import text

    db_ok = False
    redis_ok = False
    mongo_ok = False
    mongo_configured = bool(
        settings.MONGODB_URL
        and settings.MONGODB_URL != "mongodb://localhost:27017"
    )

    try:
        from app.db.session import SessionLocal

        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            db_ok = True
    except Exception as e:
        logger.error(f"Readiness DB failure: {e}")

    try:
        import redis

        r = redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        r.ping()
        redis_ok = True
    except Exception as e:
        logger.error(f"Readiness Redis failure: {e}")

    if mongo_configured:
        try:
            from pymongo import MongoClient

            client = MongoClient(
                settings.MONGODB_URL,
                serverSelectionTimeoutMS=1000,
                connectTimeoutMS=1000,
                socketTimeoutMS=1000,
            )
            client.admin.command("ping")
            mongo_ok = True
        except Exception as e:
            logger.error(f"Readiness MongoDB failure: {e}")
    else:
        mongo_ok = None

    dependencies = {
        "database": "online" if db_ok else "offline",
        "redis": "online" if redis_ok else "offline",
        "mongodb": (
            "online"
            if mongo_ok
            else ("not_configured" if mongo_ok is None else "offline")
        ),
    }
    ready = db_ok and redis_ok and (mongo_ok is None or mongo_ok)
    return dependencies, ready


@app.get("/live", tags=["System"])
def live_check():
    """Cheap liveness probe for container and reverse-proxy health checks."""
    return {
        "status": "ok",
        "service": "api",
        "environment": settings.ENVIRONMENT,
        "version": settings.APP_VERSION,
    }


@app.get("/health", tags=["System"])
def health_check():
    """Deep readiness-style health diagnostics for dependencies."""
    dependencies, ready = _readiness_payload()
    payload = {
        "status": "ok" if ready else "degraded",
        **dependencies,
        "environment": settings.ENVIRONMENT,
        "version": settings.APP_VERSION,
    }
    if ready:
        return payload
    return JSONResponse(status_code=503, content=payload)


@app.get("/ready", tags=["System"])
def readiness_check():
    return health_check()

@app.get("/", tags=["System"])
async def root():
    return {"message": f"Welcome to {settings.PROJECT_NAME} API", "version": settings.APP_VERSION}

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
admin_deps = [Depends(deps.get_current_active_admin)]

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
app.include_router(admin_dealers.router, prefix=f"{admin_api}/dealers", tags=["Admin: Dealers"], dependencies=admin_deps)

# ----------------------------
# API V1 - Dealer Endpoints
# ----------------------------
dealer_api = f"{v1_str}/dealer"
dealer_deps = [Depends(deps.get_current_user)]

app.include_router(dealer_portal_auth.router, prefix=f"{dealer_api}/auth", tags=["Dealer: Auth"])
app.include_router(dealers.router, prefix=f"{v1_str}/dealers", tags=["Dealer: Profile"], dependencies=dealer_deps)
app.include_router(dealer_stations.router, prefix=f"{v1_str}/dealer-stations", tags=["Dealer: Stations"], dependencies=dealer_deps)
app.include_router(dealer_portal_dashboard.router, prefix=f"{dealer_api}/portal", tags=["Dealer: Dashboard"], dependencies=dealer_deps)
app.include_router(dealer_portal_tickets.router, prefix=f"{dealer_api}/portal/tickets", tags=["Dealer: Tickets"], dependencies=dealer_deps)
app.include_router(dealer_portal_roles.router, prefix=f"{dealer_api}/portal/roles", tags=["Dealer: Roles"], dependencies=dealer_deps)
app.include_router(dealer_portal_users.router, prefix=f"{dealer_api}/portal/users", tags=["Dealer: Users"], dependencies=dealer_deps)
app.include_router(dealer_portal_settings.router, prefix=f"{dealer_api}/portal/settings", tags=["Dealer: Settings"], dependencies=dealer_deps)
app.include_router(dealer_portal_customers.router, prefix=f"{dealer_api}/analytics", tags=["Dealer: Customers"], dependencies=dealer_deps)
app.include_router(dealer_analytics.router, prefix=f"{dealer_api}/analytics", tags=["Dealer: Analytics"], dependencies=dealer_deps)
app.include_router(dealer_campaigns.router, prefix=f"{dealer_api}/campaigns", tags=["Dealer: Campaigns"], dependencies=dealer_deps)
app.include_router(dealer_onboarding.router, prefix=f"{dealer_api}/onboarding", tags=["Dealer: Onboarding"], dependencies=dealer_deps)

# ----------------------------
# API V1 - Logistics & System
# ----------------------------
app.include_router(logistics.router, prefix=f"{v1_str}/logistics", tags=["Logistics"])
app.include_router(telematics.router, prefix=f"{v1_str}/telematics", tags=["Telematics"])
app.include_router(iot.router, prefix=f"{v1_str}/iot", tags=["IoT"])
app.include_router(razorpay_webhook.router, prefix="/api/webhooks", tags=["Webhooks"])
