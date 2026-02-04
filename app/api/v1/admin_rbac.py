from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.api import deps
from app.models.admin_user import AdminUser
from app.models.rbac import Role, Permission, RolePermission, AdminUserRole
from app.schemas import rbac as rbac_schema

router = APIRouter()

@router.get("/roles", response_model=List[rbac_schema.RoleRead])
def read_roles(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Retrieve roles.
    """
    roles = db.exec(select(Role).offset(skip).limit(limit)).all()
    return roles

@router.post("/roles", response_model=rbac_schema.RoleRead)
def create_role(
    *,
    db: Session = Depends(deps.get_db),
    role_in: rbac_schema.RoleCreate,
    current_user: AdminUser = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Create new role.
    """
    role = Role.from_orm(role_in)
    db.add(role)
    db.commit()
    db.refresh(role)
    
    # Assign permissions
    for slug in role_in.permissions:
        permission = db.exec(select(Permission).where(Permission.slug == slug)).first()
        if permission:
            link = RolePermission(role_id=role.id, permission_id=permission.id)
            db.add(link)
    
    db.commit()
    db.refresh(role)
    return role

@router.get("/permissions", response_model=List[rbac_schema.PermissionRead])
def read_permissions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Retrieve permissions.
    """
    permissions = db.exec(select(Permission).offset(skip).limit(limit)).all()
    return permissions

@router.post("/users/{user_id}/roles", response_model=Any)
def assign_roles_to_user(
    *,
    db: Session = Depends(deps.get_db),
    user_id: int,
    assignment: rbac_schema.UserRoleAssign,
    current_user: AdminUser = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Assign roles to a user.
    """
    user = db.get(AdminUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Clear existing roles (simple replacement specific logic)
    # Ideally we might want to Add or Remove specific roles, but replacement is easier for now
    existing_links = db.exec(select(AdminUserRole).where(AdminUserRole.admin_id == user_id)).all()
    for link in existing_links:
        db.delete(link)
        
    for role_id in assignment.role_ids:
        role = db.get(Role, role_id)
        if not role:
            continue
        link = AdminUserRole(admin_id=user_id, role_id=role_id, assigned_by=current_user.id)
        db.add(link)
        
    db.commit()
    return {"status": "success", "message": "Roles updated"}
