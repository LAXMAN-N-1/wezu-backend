from typing import Any, List, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
import sqlalchemy as sa
from datetime import datetime, UTC

from app.db.session import get_session
from app.api import deps
from app.models.user import User
from app.models.dealer import DealerProfile
from app.models.rbac import Role, Permission, RolePermission, UserRole
from app.models.audit_log import AuditLog, AuditActionType
from app.schemas.role import (
    RoleRead, RoleCreate, RoleUpdate, RoleDetail, 
    RolePermissionRead, PermissionMatrix, ModulePermission, RoleAuditLog
)

router = APIRouter()

def _get_dealer(db: Session, user_id: int) -> DealerProfile:
    return deps.get_dealer_profile_or_403(db, user_id, detail="Not a dealer account")

@router.get("", response_model=List[RoleRead])
def get_roles(
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    """List all available roles for the dealer (system roles + custom dealer roles)."""
    dealer = _get_dealer(db, current_user.id)
    
    # Fetch roles: global (dealer_id is null) OR dealer-specific
    # For Dealer Portal, we mainly want to show their own roles.
    # We might want to hide internal system roles like 'Super Admin'
    statement = select(Role).where(
        (Role.dealer_id == dealer.id) | 
        ((Role.dealer_id == None) & (Role.is_system_role == True) & (Role.name.ilike("%dealer%") | Role.name.ilike("%customer%")))
    )
    roles = db.exec(statement).all()
    
    results = []
    for role in roles:
        # Count users in this role (User.role_id == role.id)
        user_count = db.exec(select(func.count(User.id)).where(User.role_id == role.id)).one() or 0
        
        # Structured permissions for Matrix (Title Case for frontend)
        perms_matrix = {}
        for p in role.permissions:
            mod_name = p.module.title()
            if mod_name not in perms_matrix:
                perms_matrix[mod_name] = []
            perms_matrix[mod_name].append(p.action.capitalize())
        
        # Summary of permissions (e.g., "Dashboard, Stock, Analytics")
        all_modules: List[str] = sorted(list(set([p.module.title() for p in role.permissions])))
        permission_summary = ", ".join(all_modules[:3]) + ("..." if len(all_modules) > 3 else "")
        
        results.append(RoleRead(
            id=role.id,
            name=role.name,
            description=role.description,
            icon=role.icon,
            color=role.color,
            is_active=role.is_active,
            user_count=user_count,
            permission_summary=permission_summary,
            is_system=role.is_system_role,
            permissions_matrix=perms_matrix,
            created_at=role.created_at,
            updated_at=role.updated_at
        ))
    return results

@router.get("/{role_id}", response_model=RoleDetail)
def get_role_detail(
    role_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    dealer = _get_dealer(db, current_user.id)
    role = db.get(Role, role_id)
    if not role or (role.dealer_id and role.dealer_id != dealer.id):
        raise HTTPException(status_code=404, detail="Role not found")
        
    permissions = [
        RolePermissionRead(slug=p.slug, module=p.module, action=p.action, description=p.description)
        for p in role.permissions
    ]
    
    # Get user count
    user_count = db.exec(select(func.count(User.id)).where(User.role_id == role.id)).one() or 0
    # Summary of permissions
    all_modules: List[str] = sorted(list(set([p.module.title() for p in role.permissions])))
    permission_summary = ", ".join(all_modules[:3]) + ("..." if len(all_modules) > 3 else "")

    # Structured permissions for Matrix
    perms_matrix = {}
    for p in role.permissions:
        mod_name = p.module.title()
        if mod_name not in perms_matrix:
            perms_matrix[mod_name] = []
        perms_matrix[mod_name].append(p.action.capitalize())

    return RoleDetail(
        id=role.id,
        name=role.name,
        description=role.description,
        icon=role.icon,
        color=role.color,
        is_active=role.is_active,
        user_count=user_count,
        permission_summary=permission_summary,
        is_system=role.is_system_role,
        permissions_matrix=perms_matrix,
        created_at=role.created_at,
        updated_at=role.updated_at,
        permissions=permissions
    )

@router.post("", response_model=RoleRead)
def create_role(
    role_in: RoleCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    dealer = _get_dealer(db, current_user.id)
    
    # Create Role object
    role = Role(
        name=role_in.name,
        description=role_in.description,
        icon=role_in.icon,
        color=role_in.color,
        dealer_id=dealer.id,
        category="dealer_staff"
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    
    # Assign permissions if provided (batch lookup)
    if role_in.permissions:
        found_perms = db.exec(
            select(Permission).where(Permission.slug.in_(list(role_in.permissions)))
        ).all()
        for perm in found_perms:
            db.add(RolePermission(role_id=role.id, permission_id=perm.id))
        db.commit()
        db.refresh(role)
    
    # Audit Log
    db.add(AuditLog(
        user_id=current_user.id,
        action=AuditActionType.DATA_MODIFICATION,
        resource_type="ROLE",
        target_id=role.id,
        details=f"Created role: {role.name}",
        new_value=role_in.dict()
    ))
    db.commit()
        
    return RoleRead(
        id=role.id,
        name=role.name,
        description=role.description,
        icon=role.icon,
        color=role.color,
        is_active=role.is_active,
        user_count=0,
        permission_summary="",
        created_at=role.created_at
    )

@router.put("/{role_id}", response_model=RoleRead)
def update_role(
    role_id: int,
    role_in: RoleUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    dealer = _get_dealer(db, current_user.id)
    role = db.get(Role, role_id)
    if not role or role.dealer_id != dealer.id:
        raise HTTPException(status_code=404, detail="Custom role not found")
        
    role_data = role_in.dict(exclude_unset=True)
    permissions = role_data.pop("permissions", None)
    
    for key, value in role_data.items():
        setattr(role, key, value)
    
    role.updated_at = datetime.now(UTC)
    db.add(role)
    
    if permissions is not None:
        # Clear existing and add new (batch lookup)
        db.exec(sa.delete(RolePermission).where(RolePermission.role_id == role.id))
        if permissions:
            found_perms = db.exec(
                select(Permission).where(Permission.slug.in_(list(permissions)))
            ).all()
            for perm in found_perms:
                db.add(RolePermission(role_id=role.id, permission_id=perm.id))
                
    db.commit()
    db.refresh(role)
    
    # Audit Log
    db.add(AuditLog(
        user_id=current_user.id,
        action=AuditActionType.DATA_MODIFICATION,
        resource_type="ROLE",
        target_id=role.id,
        details=f"Updated role: {role.name}",
        new_value=role_in.dict(exclude_unset=True)
    ))
    db.commit()
    
    return get_roles(db, current_user)[0] # Simplified refresh

@router.delete("/{role_id}")
def delete_role(
    role_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    dealer = _get_dealer(db, current_user.id)
    role = db.get(Role, role_id)
    if not role or role.dealer_id != dealer.id:
        raise HTTPException(status_code=404, detail="Custom role not found")
    
    if role.is_system_role:
        raise HTTPException(status_code=400, detail="Cannot delete system roles")
        
    # Audit Log
    db.add(AuditLog(
        user_id=current_user.id,
        action=AuditActionType.DATA_MODIFICATION,
        resource_type="ROLE",
        target_id=role.id,
        details=f"Deleted role: {role.name}",
        old_value={"name": role.name}
    ))
    
    db.delete(role)
    db.commit()
    return {"success": True}

@router.get("/{role_id}/users")
def get_role_users(
    role_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    dealer = _get_dealer(db, current_user.id)
    role = db.get(Role, role_id)
    if not role or (role.dealer_id and role.dealer_id != dealer.id):
        raise HTTPException(status_code=404, detail="Role not found")
        
    users = db.exec(select(User).where(User.role_id == role_id)).all()
    return [
        {"id": u.id, "name": u.full_name, "email": u.email, "status": u.status}
        for u in users
    ]

@router.post("/{role_id}/users")
def assign_user_to_role(
    role_id: int,
    payload: Dict[str, int],
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    user_id = payload.get("user_id")
    dealer = _get_dealer(db, current_user.id)
    role = db.get(Role, role_id)
    if not role or (role.dealer_id and role.dealer_id != dealer.id):
        raise HTTPException(status_code=404, detail="Role not found")
        
    target_user = db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    target_user.role_id = role_id
    db.add(target_user)
    db.commit()
    return {"success": True}

@router.delete("/{role_id}/users/{user_id}")
def remove_user_from_role(
    role_id: int,
    user_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    dealer = _get_dealer(db, current_user.id)
    target_user = db.get(User, user_id)
    if not target_user or target_user.role_id != role_id:
        raise HTTPException(status_code=404, detail="User not assigned to this role")
        
    target_user.role_id = None
    db.add(target_user)
    db.commit()
    return {"success": True}

@router.get("/permissions/modules", response_model=List[ModulePermission])
def get_permission_modules(
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    # Fetch all permissions and group by module
    perms = db.exec(select(Permission)).all()
    grouped = {}
    for p in perms:
        if p.module not in grouped:
            grouped[p.module] = set()
        grouped[p.module].add(p.action)
        
    return [ModulePermission(module=m, permissions=list(a)) for m, a in grouped.items()]

@router.get("/matrix", response_model=PermissionMatrix)
def get_roles_matrix(
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    dealer = _get_dealer(db, current_user.id)
    roles = db.exec(select(Role).where(
        (Role.dealer_id == dealer.id) | 
        ((Role.dealer_id == None) & (Role.is_system_role == True) & (Role.name.ilike("%dealer%") | Role.name.ilike("%customer%")))
    )).all()
    
    perms = db.exec(select(Permission)).all()
    modules = {}
    for p in perms:
        if p.module not in modules:
            modules[p.module] = set()
        modules[p.module].add(p.action)
    
    # Build matrix: role_name -> module_name -> list of actions
    matrix: Dict[str, Dict[str, List[str]]] = {}
    for r in roles:
        role_name = r.name
        matrix[role_name] = {}
        for p in r.permissions:
            mod_title = p.module.title()
            if mod_title not in matrix[role_name]:
                matrix[role_name][mod_title] = []
            matrix[role_name][mod_title].append(p.action.capitalize())
            
    return PermissionMatrix(
        roles=[r.name for r in roles],
        modules=[ModulePermission(module=m.title(), permissions=list(a)) for m, a in modules.items()],
        matrix=matrix
    )

@router.post("/users/invite")
def invite_user(
    payload: Dict[str, str],
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    """Mock invitation logic."""
    email = payload.get("email")
    role_id = payload.get("role_id")
    return {"success": True, "message": f"Invitation sent to {email}"}

@router.get("/{role_id}/audit-log", response_model=List[RoleAuditLog])
def get_role_audit_log(
    role_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    logs = db.exec(
        select(AuditLog).where(
            AuditLog.resource_type == "ROLE",
            AuditLog.target_id == role_id
        ).order_by(AuditLog.timestamp.desc())
    ).all()
    
    # Batch-load users (eliminates N+1 per log entry)
    log_user_ids = list({log.user_id for log in logs if log.user_id})
    users_map = {u.id: u for u in db.exec(select(User).where(User.id.in_(log_user_ids))).all()} if log_user_ids else {}

    results = []
    for log in logs:
        user = users_map.get(log.user_id) if log.user_id else None
        results.append(RoleAuditLog(
            action=log.action,
            user_name=user.full_name if user else "System",
            timestamp=log.timestamp,
            details=log.details
        ))
    return results
