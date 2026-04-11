"""
System Health and Version Endpoints
Provides health checks and system information
"""
from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.core.config import settings
from app.api import deps
from datetime import datetime, UTC
import psutil
import platform

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat()
    }


@router.get("/health/detailed")
async def detailed_health_check(db: Session = Depends(deps.get_db)):
    """Detailed health check with system metrics"""
    try:
        # Test database connection
        db.exec("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "timestamp": datetime.now(UTC).isoformat(),
        "components": {
            "database": db_status,
            "api": "healthy"
        },
        "system": {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent
        }
    }


@router.get("/version")
async def get_version():
    """Get API version information"""
    return {
        "version": settings.APP_VERSION,
        "api_version": "v1",
        "environment": settings.ENVIRONMENT,
        "python_version": platform.python_version(),
    }


@router.get("/config")
async def get_public_config():
    """Get public configuration"""
    return {
        "features": {
            "apple_signin": True,
            "google_signin": True,
            "biometric_auth": True,
            "two_factor_auth": True,
            "video_kyc": True,
            "battery_swap": True,
            "e_commerce": True
        },
        "limits": {
            "max_file_size_mb": 10,
            "max_rentals_per_user": 5,
            "max_addresses_per_user": 5
        },
        "support": {
            "email": settings.SUPPORT_EMAIL,
            "phone": settings.SUPPORT_PHONE,
            "hours": "24/7"
        }
    }