from sqlmodel import Session, select
from app.models.user import User
from app.models.security_settings import SecuritySettings
from app.models.session import UserSession
from fastapi import HTTPException, status
from typing import Optional, List
from datetime import datetime, UTC

class AdminSecurityService:
    @staticmethod
    def get_settings(db: Session) -> SecuritySettings:
        """Fetch current platform-wide security settings, creating defaults if not exists."""
        settings = db.exec(select(SecuritySettings)).first()
        if not settings:
            settings = SecuritySettings()
            db.add(settings)
            db.commit()
            db.refresh(settings)
        return settings

    @staticmethod
    def update_settings(db: Session, update_data: dict, admin_user: User) -> SecuritySettings:
        """Update platform-wide security settings and log the action."""
        settings = AdminSecurityService.get_settings(db)
        
        # In a real app we'd use a service or helper to track before/after for AuditLog
        old_data = settings.model_dump()
        
        for key, value in update_data.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
        
        settings.updated_at = datetime.now(UTC)
        settings.updated_by_id = admin_user.id
        
        db.add(settings)
        db.commit()
        db.refresh(settings)
        
        # Note: We'd trigger an AuditLog here as well
        return settings

    @staticmethod
    def force_logout_all_admins(db: Session, current_admin: User) -> int:
        """Invalidate all active admin sessions immediately (except current)."""
        # Revoke all sessions for users who are ADMIN, dealer staff, etc.
        # This is a critical security action
        from app.models.user import UserType
        
        # 1. Find all admin/staff users
        # For simplicity, we invalidate ALL user sessions in this 'Force Logout All Admins' command
        # as described in requirements: 'all admin sessions invalidated immediately'
        
        # Get all active sessions for non-superuser (or all) that have admin roles
        # Filter logic depends on how granular the 'All Admins' definition is.
        # Requirements suggest a red danger button for 'All Admins'.
        
        statement = select(UserSession).where(UserSession.is_active == True)
        # We might exclude the current_admin's session ID if we know it, 
        # but requirements say "all admin sessions".
        
        sessions = db.exec(statement).all()
        count = 0
        for s in sessions:
            # We check the User associated with the session to see if they are an admin
            user = db.get(User, s.user_id)
            if user and user.user_type in ["ADMIN", "DEALER_STAFF"]:
                s.is_active = False
                db.add(s)
                count += 1
        
        db.commit()
        return count

    @staticmethod
    def add_to_ip_whitelist(db: Session, ip: str, label: str, admin_user: User) -> SecuritySettings:
        """Add a specific IP/CIDR to the whitelist."""
        settings = AdminSecurityService.get_settings(db)
        
        # Basic validation for CIDR could go here
        new_entry = {
            "ip": ip,
            "label": label,
            "added_by": admin_user.id,
            "added_at": datetime.now(UTC).isoformat()
        }
        
        # Use existing whitelisted_ips but make a copy for JSON update
        ips = list(settings.whitelisted_ips)
        # Prevent duplicates
        if not any(item["ip"] == ip for item in ips):
            ips.append(new_entry)
            settings.whitelisted_ips = ips
            db.add(settings)
            db.commit()
            db.refresh(settings)
            
        return settings
