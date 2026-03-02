from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
from typing import List, Optional, Dict, Any
from app.api import deps
from app.db.session import get_session
from app.models.user import User
from app.models.audit_log import AuditLog
from app.models.address import Address
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime

router = APIRouter()

from app.services.audit_service import audit_service

class AuditLogEntry(BaseModel):
    id: int
    user_id: Optional[int]
    action: str
    resource_type: str
    resource_id: Optional[str]
    timestamp: datetime
    details: Optional[str]
    ip_address: Optional[str]

    model_config = ConfigDict(from_attributes=True)

class AuditLogResponse(BaseModel):
    logs: List[AuditLogEntry]
    total_count: int
    page: int
    limit: int

class MongoAuditEntry(BaseModel):
    id: str = Field(alias="_id")
    user_id: Optional[int] = None
    event_type: str
    action: Optional[str] = None
    resource: Optional[str] = None
    status: str
    timestamp: datetime
    metadata: Dict[str, Any] = {}
    ip_address: Optional[str] = None

class MongoAuditResponse(BaseModel):
    logs: List[MongoAuditEntry]
    total_count: int
    page: int
    limit: int

@router.get("/users/{user_id}", response_model=MongoAuditResponse)
async def get_user_audit_log(
    user_id: int,
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(deps.get_current_user),
):
    """
    Get audit activity history for a user from MongoDB.
    """
    # 1. Authorization (Simplified for now, keep existing logic if critical)
    if current_user.id != user_id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    # 2. Query MongoDB
    result = await audit_service.get_logs(
        user_id=user_id,
        page=page,
        limit=limit
    )
    
    return result


@router.get("/roles/{role_id}/changes", response_model=AuditLogResponse)
async def get_role_audit_log(
    role_id: int,
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Get audit history for a specific role.
    Tracks:
    - Creation
    - Updates (Name, Description, etc.)
    - Permission changes
    - Deletion
    
    Authorization:
    - Super Admin / Admin only
    """
    # 1. Authorization
    current_user_roles = [r.name for r in current_user.roles] if current_user.roles else []
    is_super_admin = "super_admin" in current_user_roles or current_user.is_superuser
    is_admin = "admin" in current_user_roles
    
    if not any([is_super_admin, is_admin]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins can view role audit logs"
        )
        
    # 2. Query Audit Logs
    # We look for resource_type="role" and resource_id=str(role_id)
    query = select(AuditLog).where(AuditLog.resource_type == "role").where(AuditLog.resource_id == str(role_id))
    
    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total_count = db.exec(count_query).one()
    
    # Pagination & Sort
    offset = (page - 1) * limit
    logs = db.exec(query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit)).all()
    
    return AuditLogResponse(
        logs=logs,
        total_count=total_count,
        page=page,
        limit=limit
    )

@router.get("/permissions/usage")
async def get_permission_usage_analytics(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Get permission usage analytics.
    Returns:
    - Usage count per permission (Granted vs Denied)
    - List of unused permissions
    - Most frequent users per permission
    
    Authorization:
    - Super Admin / Admin only
    """
    # 1. Authorization
    current_user_roles = [r.name for r in current_user.roles] if current_user.roles else []
    is_super_admin = "super_admin" in current_user_roles or current_user.is_superuser
    is_admin = "admin" in current_user_roles
    
    if not any([is_super_admin, is_admin]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins can view permission analytics"
        )
        
    # 2. Fetch all permissions (to find unused ones)
    from app.models.rbac import Permission
    all_perms = db.exec(select(Permission)).all()
    all_slugs = {p.slug: p.description for p in all_perms}
    
    # 3. Query Audit Logs for permission checks
    query = select(AuditLog).where(AuditLog.action == "permission_check")
    logs = db.exec(query).all()
    
    usage_map = {}
    
    for log in logs:
        perm_slug = log.resource_id
        if perm_slug not in usage_map:
            usage_map[perm_slug] = {
                "slug": perm_slug,
                "total_checks": 0,
                "granted": 0,
                "denied": 0,
                "users": set()
            }
            
        usage_map[perm_slug]["total_checks"] += 1
        usage_map[perm_slug]["users"].add(log.user_id)
        
        if "Granted: True" in (log.details or ""):
            usage_map[perm_slug]["granted"] += 1
        else:
            usage_map[perm_slug]["denied"] += 1
            
    # 4. Construct Response
    used_permissions = []
    for slug, data in usage_map.items():
        used_permissions.append({
            "slug": slug,
            "description": all_slugs.get(slug, "Unknown"),
            "total_checks": data["total_checks"],
            "granted": data["granted"],
            "denied": data["denied"],
            "unique_user_count": len(data["users"])
        })
        
    # Find unused
    used_slugs = set(usage_map.keys())
    unused_permissions = []
    for slug, desc in all_slugs.items():
        if slug not in used_slugs:
            unused_permissions.append({
                "slug": slug,
                "description": desc
            })
            
    return {
        "used_permissions": sorted(used_permissions, key=lambda x: x["total_checks"], reverse=True),
        "unused_permissions": sorted(unused_permissions, key=lambda x: x["slug"]),
        "total_checks_recorded": len(logs)
    }

@router.get("/auth/failures", response_model=AuditLogResponse)
async def get_auth_failures(
    user_id: Optional[int] = None,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
    page: int = 1,
    limit: int = 20,
):
    """
    Get failed authentication attempts.
    
    Filters:
    - User ID (optional)
    
    Authorization:
    - Super Admin / Admin only
    """
    # 1. Authorization
    current_user_roles = [r.name for r in current_user.roles] if current_user.roles else []
    is_super_admin = "super_admin" in current_user_roles or current_user.is_superuser
    is_admin = "admin" in current_user_roles
    
    if not any([is_super_admin, is_admin]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins can view auth failures"
        )
        
    # 2. Query Audit Logs
    query = select(AuditLog).where(AuditLog.action == "login_failed")
    
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
        
    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total_count = db.exec(count_query).one()
    
    # Pagination & Sort
    offset = (page - 1) * limit
    logs = db.exec(query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit)).all()
    
    return AuditLogResponse(
        logs=logs,
        total_count=total_count,
        page=page,
        limit=limit
    )

@router.get("/data-access", response_model=AuditLogResponse)
async def get_data_access_log(
    user_id: Optional[int] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
    page: int = 1,
    limit: int = 20,
):
    """
    Get data access log (Who accessed what).
    
    Filters:
    - User ID
    - Resource Type (user, battery, transaction, etc.)
    - Resource ID
    - Date Range
    
    Authorization:
    - Super Admin / Admin only
    """
    # 1. Authorization
    current_user_roles = [r.name for r in current_user.roles] if current_user.roles else []
    is_super_admin = "super_admin" in current_user_roles or current_user.is_superuser
    is_admin = "admin" in current_user_roles
    
    if not any([is_super_admin, is_admin]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins can view data access logs"
        )
        
    # 2. Query Audit Logs
    query = select(AuditLog)
    
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if resource_id:
        query = query.where(AuditLog.resource_id == resource_id)
    if start_date:
        query = query.where(AuditLog.timestamp >= start_date)
    if end_date:
        query = query.where(AuditLog.timestamp <= end_date)
        
    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total_count = db.exec(count_query).one()
    
    # Pagination & Sort
    offset = (page - 1) * limit
    logs = db.exec(query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit)).all()
    
    return AuditLogResponse(
        logs=logs,
        total_count=total_count,
        page=page,
        limit=limit
    )
