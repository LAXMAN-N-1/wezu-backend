from fastapi import APIRouter

from app.api.admin import main, fraud, jobs, monitoring, users, rentals, finance, iot, batteries, stock, health, stations

router = APIRouter()
router.include_router(main.router)
router.include_router(stations.router, prefix="/stations", tags=["Admin Stations"])
router.include_router(users.router, prefix="/users", tags=["Admin Users"])
router.include_router(batteries.router, prefix="/batteries", tags=["Admin Batteries"]) # New
router.include_router(stock.router, prefix="/stock", tags=["Admin Stock Levels"])
router.include_router(health.router, prefix="/health", tags=["Admin Battery Health"])
router.include_router(rentals.router, prefix="/rentals", tags=["Admin Rentals"])
router.include_router(finance.router, prefix="/finance", tags=["Admin Finance"])
router.include_router(iot.router, prefix="/iot", tags=["Admin IoT"])
router.include_router(fraud.router, prefix="/fraud", tags=["Admin Fraud"])
router.include_router(jobs.router, prefix="/jobs", tags=["Admin Jobs"])
router.include_router(monitoring.router, prefix="/monitoring", tags=["Admin Monitoring"])

