from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

# Customer-facing endpoints only
from app.api.v1 import (
    auth, users, kyc, stations, batteries, rentals, wallet, payments, 
    notifications, support, favorites, analytics, transactions, promo, 
    faqs, iot, swaps, i18n, fraud
)
# Enhanced customer endpoints
from app.api.v1 import (
    system, payments_enhanced, wallet_enhanced, notifications_enhanced,
    support_enhanced, rentals_enhanced, purchases_enhanced, analytics_enhanced
)
from app.api.webhooks import razorpay as razorpay_webhook
from app.middleware.rate_limit import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

app = FastAPI(title=settings.PROJECT_NAME, openapi_url=f"{settings.API_V1_STR}/openapi.json")

# Rate Limit
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Customer API Routes
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])
app.include_router(users.router, prefix=f"{settings.API_V1_STR}/users", tags=["Users"])
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

# Enhanced Customer Endpoints
app.include_router(system.router, prefix=f"{settings.API_V1_STR}", tags=["System"])
app.include_router(payments_enhanced.router, prefix=f"{settings.API_V1_STR}/payments", tags=["Payments Enhanced"])
app.include_router(wallet_enhanced.router, prefix=f"{settings.API_V1_STR}/wallet", tags=["Wallet Enhanced"])
app.include_router(notifications_enhanced.router, prefix=f"{settings.API_V1_STR}/notifications", tags=["Notifications Enhanced"])
app.include_router(support_enhanced.router, prefix=f"{settings.API_V1_STR}/support", tags=["Support Enhanced"])
app.include_router(rentals_enhanced.router, prefix=f"{settings.API_V1_STR}/rentals", tags=["Rentals Enhanced"])
app.include_router(purchases_enhanced.router, prefix=f"{settings.API_V1_STR}/purchases", tags=["Purchases Enhanced"])
app.include_router(analytics_enhanced.router, prefix=f"{settings.API_V1_STR}/analytics", tags=["Analytics Enhanced"])

# Webhooks
app.include_router(razorpay_webhook.router, prefix="/api/webhooks", tags=["Webhooks"])


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

# Background Workers
from app.workers import start_scheduler, stop_scheduler

@app.on_event("startup")
async def startup_event():
    """Start background scheduler on app startup"""
    start_scheduler()

@app.on_event("shutdown")
async def shutdown_event():
    """Stop background scheduler on app shutdown"""
    stop_scheduler()
