from fastapi import APIRouter, Depends, HTTPException, Body
from sqlmodel import Session
from app.api import deps
from app.core.database import get_db
from app.models.user import User
from app.models.security_settings import SecuritySettings
from app.services.admin_security_service import AdminSecurityService
from typing import Any, Dict

router = APIRouter()

@router.get("/settings", response_model=SecuritySettings)
async def get_security_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """Fetch current platform-wide security configuration."""
    return AdminSecurityService.get_settings(db)

@router.patch("/settings", response_model=SecuritySettings)
async def update_security_settings(
    update_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """
    Update security settings (Password policy, 2FA, Sessions, etc.).
    Triggers immediate effect across the platform.
    """
    return AdminSecurityService.update_settings(db, update_data, current_user)

@router.post("/force-logout-all")
async def force_logout_all_admins(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """
    🔴 DANGER: Immediately invalidates all active admin and dealer staff sessions.
    Requires Super Admin privileges.
    """
    count = AdminSecurityService.force_logout_all_admins(db, current_user)
    return {"message": f"Successfully terminated {count} admin sessions.", "count": count}

@router.post("/whitelist-ip")
async def add_ip_to_whitelist(
    ip: str = Body(..., embed=True),
    label: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """Add a specific IP/CIDR to the platform-wide whitelist."""
    return AdminSecurityService.add_to_ip_whitelist(db, ip, label, current_user)
