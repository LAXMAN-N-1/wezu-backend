from fastapi import APIRouter

from app.api.admin import main, fraud, jobs, monitoring

router = APIRouter()
router.include_router(main.router)
router.include_router(fraud.router, prefix="/fraud", tags=["Admin Fraud"])
router.include_router(jobs.router, prefix="/jobs", tags=["Admin Jobs"])
router.include_router(monitoring.router, prefix="/monitoring", tags=["Admin Monitoring"])
