from fastapi import APIRouter

from . import main, fraud, jobs, monitoring, users, rentals, finance, iot, batteries, stock, health, stations, kyc_admin, rbac_admin, cms, admin_groups, audit_trails, logistics, support, bess, notifications, settings, security

router = APIRouter()
router.include_router(main.router)
router.include_router(audit_trails.router, prefix="/audit-trails", tags=["Admin Audit Trails"])
router.include_router(stations.router, prefix="/stations", tags=["Admin Stations"])
router.include_router(cms.router, prefix="/cms", tags=["Admin CMS"])
router.include_router(users.router, prefix="/users", tags=["Admin Users"])
router.include_router(batteries.router, prefix="/batteries", tags=["Admin Batteries"])
router.include_router(stock.router, prefix="/stock", tags=["Admin Stock Levels"])
router.include_router(health.router, prefix="/health", tags=["Admin Battery Health"])
router.include_router(rentals.router, prefix="/rentals", tags=["Admin Rentals"])
router.include_router(finance.router, prefix="/finance", tags=["Admin Finance"])
router.include_router(iot.router, prefix="/iot", tags=["Admin IoT"])
router.include_router(fraud.router, prefix="/fraud", tags=["Admin Fraud"])
router.include_router(jobs.router, prefix="/jobs", tags=["Admin Jobs"])
router.include_router(monitoring.router, prefix="/monitoring", tags=["Admin Monitoring"])
router.include_router(kyc_admin.router, prefix="/kyc-docs", tags=["Admin KYC Documents"])
router.include_router(rbac_admin.router, prefix="/rbac", tags=["Admin RBAC"])
# Dealers are served by app.api.v1.admin_dealers and mounted directly in
# app.main to avoid duplicate route registrations at /api/v1/admin/dealers.
router.include_router(admin_groups.router, prefix="/groups", tags=["Admin Groups"])
# Analytics is served by app.api.v1.admin.analytics to avoid duplicate route
# registrations at /api/v1/admin/analytics.
router.include_router(logistics.router, prefix="/logistics", tags=["Admin Logistics"])
router.include_router(support.router, prefix="/support", tags=["Admin Support"])

# New module routers
router.include_router(bess.router, prefix="/bess", tags=["Admin BESS"])
router.include_router(notifications.router, prefix="/notifications", tags=["Admin Notifications"])
router.include_router(settings.router, prefix="/settings", tags=["Admin Settings"])
router.include_router(security.router, prefix="/security", tags=["Admin Security"])
