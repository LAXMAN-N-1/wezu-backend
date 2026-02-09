from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
from typing import List, Optional
from app.api import deps
from app.db.session import get_session
from app.models.user import User
from app.models.audit_log import AuditLog
from app.models.address import Address
from pydantic import BaseModel, ConfigDict
from datetime import datetime

router = APIRouter()

class AuditLogEntry(BaseModel):
    id: int
    user_id: Optional[int]
    action: str
    resource_type: str
    resource_id: Optional[str]
    details: Optional[str]
    ip_address: Optional[str]
    timestamp: datetime
    
    model_config = ConfigDict(from_attributes=True)

class AuditLogResponse(BaseModel):
    logs: List[AuditLogEntry]
    total_count: int
    page: int
    limit: int

@router.get("/users/{user_id}", response_model=AuditLogResponse)
async def get_user_audit_log(
    user_id: int,
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Get complete audit activity history for a user.
    
    Response:
    - All actions by user
    - Login history
    - Permission checks
    - Data modifications
    - Role changes
    - Timestamps
    - IP addresses
    
    Authorization:
    - User: Own activity
    - Super Admin / Admin: Any user
    - Regional Manager: Users in their region
    """
    # 1. Authorization
    is_self = current_user.id == user_id
    
    current_user_roles = [r.name for r in current_user.roles] if current_user.roles else []
    is_super_admin = "super_admin" in current_user_roles or current_user.is_superuser
    is_admin = "admin" in current_user_roles
    is_regional_manager = "regional_manager" in current_user_roles
    
    if not is_self and not any([is_super_admin, is_admin, is_regional_manager]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own audit log"
        )
        
    # 2. Regional Manager Check (if not self/admin)
    if not is_self and is_regional_manager and not is_super_admin and not is_admin:
        # Check if target user is in region
        user = db.get(User, user_id)
        if not user:
             raise HTTPException(status_code=404, detail="User not found")
             
        manager_addresses = db.exec(select(Address).where(Address.user_id == current_user.id)).all()
        manager_states = {addr.state.lower().strip() for addr in manager_addresses if addr.state}
        
        target_addresses = db.exec(select(Address).where(Address.user_id == user.id)).all()
        target_states = {addr.state.lower().strip() for addr in target_addresses if addr.state}
        
        # If no addresses, potentially deny or allow if generic rules apply. 
        # Safest is to deny if no overlap and manager is restricted.
        # If manager has no state, they see nothing? Or everything? Usually nothing.
        if not manager_states:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Regional Manager has no assigned region"
            )
            
        if not manager_states.intersection(target_states):
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view audit logs of users in your region"
            )

    # 3. Query Audit Logs
    query = select(AuditLog).where(AuditLog.user_id == user_id)
    
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
