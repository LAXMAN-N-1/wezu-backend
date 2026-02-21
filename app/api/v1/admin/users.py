from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select, func
from typing import List, Optional
import csv
import io
from app.api import deps
from app.services.user_service import UserService
from app.schemas.admin_user import (
    UserSuspensionRequest, 
    UserRoleUpdateRequest, 
    BulkUserActionRequest,
    UserHistoryResponse
)
from app.schemas.user import UserSearchResponse, UserSearchItem
from app.models.user import User
from datetime import datetime, timedelta

router = APIRouter()

@router.put("/{id}/role", response_model=dict)
async def change_user_role(
    id: int,
    role_in: UserRoleUpdateRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """Change a user's role with reason logging"""
    user = UserService.update_role(db, id, current_user.id, role_in.role_id, role_in.reason)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "success", "message": f"Role updated to {role_in.role_id}"}

@router.put("/{id}/suspend", response_model=dict)
async def suspend_user(
    id: int,
    req: UserSuspensionRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """Suspend account with reason and optional duration"""
    expires_at = None
    if req.duration_days:
        expires_at = datetime.utcnow() + timedelta(days=req.duration_days)
        
    user = UserService.suspend_user(db, id, current_user.id, req.reason, expires_at)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "suspended", "until": expires_at}

@router.put("/{id}/reactivate", response_model=dict)
async def reactivate_user(
    id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """Manually reactivate a suspended account"""
    user = UserService.reactivate_user(db, id, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "active"}

@router.get("/{id}/suspension-history", response_model=List[UserHistoryResponse])
async def get_suspension_history(
    id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """View all suspension/reactivation events for a user"""
    logs = UserService.get_status_history(db, id)
    
    results = []
    for log in logs:
        # Resolve actor name
        actor = db.get(User, log.actor_id)
        results.append(UserHistoryResponse(
            id=log.id,
            action_type=log.action_type,
            old_value=log.old_value,
            new_value=log.new_value,
            reason=log.reason,
            actor_name=actor.full_name if actor else "Unknown",
            created_at=log.created_at
        ))
    return results

@router.post("/bulk-action", response_model=dict)
async def bulk_user_action(
    req: BulkUserActionRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """Bulk activate, deactivate, or message users"""
    if req.action not in ["activate", "deactivate", "message"]:
        raise HTTPException(status_code=400, detail="Invalid action")
        
    updated_count = 0
    for uid in req.user_ids:
        user = db.get(User, uid)
        if not user: continue
        
        if req.action == "activate":
            user.is_active = True
        elif req.action == "deactivate":
            user.is_active = False
            
        db.add(user)
        updated_count += 1
        
    db.commit()
    return {"status": "success", "processed": updated_count}

@router.post("/export")
async def export_users(
    role: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    """Export user list to CSV with applied filters"""
    from app.api.v1.users import read_users
    
    # Simulate the query (reusing logic conceptually)
    query = select(User)
    if status == "active":
        query = query.where(User.is_active == True)
    elif status == "inactive":
        query = query.where(User.is_active == False)
        
    users = db.exec(query).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Email", "Phone", "Status", "Joined At"])
    
    for u in users:
        writer.writerow([u.id, u.full_name, u.email, u.phone_number, u.status, u.created_at])
        
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=users_export_{datetime.now().strftime('%Y%m%d')}.csv"}
    )

@router.delete("/{id}/sessions", status_code=status.HTTP_204_NO_CONTENT)
async def terminate_user_sessions(
    id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """Admin: forcibly log out a user from all devices"""
    from app.models.security import UserSession
    statement = select(UserSession).where(UserSession.user_id == id)
    sessions = db.exec(statement).all()
    for s in sessions:
        db.delete(s)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
