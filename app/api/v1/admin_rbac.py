from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from app.api import deps
from app.models.admin_user import AdminUser
from app.models.rbac import Role, Permission, RolePermission, AdminUserRole, UserRole
from app.schemas import rbac as rbac_schema

router = APIRouter()

@router.get("/roles", response_model=List[rbac_schema.RoleRead])
def read_roles(
    skip: int = 0,
    limit: int = 100,
    category: str | None = None,
    active_only: bool = False,
    include_permissions: bool = True,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Retrieve roles.
    """
    query = select(Role)
    
    if category:
        query = query.where(Role.category == category)
        
    if active_only:
        query = query.where(Role.is_active == True)
        
    # TODO: Implement stricter RBAC for non-superusers if needed
    # For now, Super Admin sees all. 
    # Logic for future: if not current_user.is_superuser: query = query.where(Role.level < current_user.role.level)

    roles = db.exec(query.offset(skip).limit(limit)).all()
    
    # Enrichment
    results = []
    for role in roles:
        # Load permissions if needed for count or return
        # Using a separate query or relationship load depending on optimization needs
        # Here accessing role.permissions lazy loads it
        perms = role.permissions
        
        role_data = rbac_schema.RoleRead.model_validate(role)
        role_data.permission_count = len(perms)
        
        if not include_permissions:
            role_data.permissions = None
        
        results.append(role_data)
        
    return results

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
    # 1. Check uniqueness
    existing = db.exec(select(Role).where(Role.name == role_in.name)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Role name already exists")
        
    role_data = role_in.dict(exclude={"permissions", "parent_role_id"})
    
    # 2. Inheritance Logic
    permissions_to_assign = set(role_in.permissions)
    
    if role_in.parent_role_id:
        parent_role = db.get(Role, role_in.parent_role_id)
        if not parent_role:
             raise HTTPException(status_code=404, detail="Parent role not found")
        
        # Load parent permissions
        # Note: SQLModel relationship access might require eager load or session attached
        # We can query link table directly
        parent_perms = db.exec(select(Permission.slug).join(RolePermission).where(RolePermission.role_id == parent_role.id)).all()
        permissions_to_assign.update(parent_perms)
        
        role_data["parent_role_id"] = role_in.parent_role_id

    role = Role(**role_data)
    db.add(role)
    db.commit()
    db.refresh(role)
    
    # 3. Assign Permissions
    for slug in permissions_to_assign:
        permission = db.exec(select(Permission).where(Permission.slug == slug)).first()
        if permission:
            # Check if link exists (unlikely for new role but safe)
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


@router.put("/roles/{role_id}", response_model=rbac_schema.RoleRead)
def update_role(
    *,
    role_id: int,
    role_in: rbac_schema.RoleUpdate,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Update role.
    """
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
        
    # 1. System Role Protection
    if role.is_system_role:
        if role_in.name is not None and role_in.name != role.name:
            raise HTTPException(status_code=400, detail="Cannot rename system roles")
        if role_in.category is not None and role_in.category != role.category:
             raise HTTPException(status_code=400, detail="Cannot change category of system roles")
             
    # 2. Update Basic Fields
    if role_in.name is not None:
        # Check uniqueness
        if role_in.name != role.name:
             existing = db.exec(select(Role).where(Role.name == role_in.name)).first()
             if existing:
                 raise HTTPException(status_code=400, detail="Role name already exists")
        role.name = role_in.name
        
    if role_in.description is not None:
        role.description = role_in.description
    if role_in.category is not None:
        role.category = role_in.category
    if role_in.level is not None:
        role.level = role_in.level
    if role_in.parent_role_id is not None:
        # Prevent circular logic usually, but keep simple for now
        role.parent_role_id = role_in.parent_role_id
        
    db.add(role)
    db.commit()
    
    # 3. Update Permissions
    if role_in.permissions is not None:
        # Clear existing
        existing_links = db.exec(select(RolePermission).where(RolePermission.role_id == role.id)).all()
        for link in existing_links:
            db.delete(link)
            
        # Add new
        for slug in role_in.permissions:
            permission = db.exec(select(Permission).where(Permission.slug == slug)).first()
            if permission:
                 db.add(RolePermission(role_id=role.id, permission_id=permission.id))
        
        # 4. Session Invalidation (Security)
        # Invalidate sessions for users having this role
        # Find users
        user_ids = db.exec(select(UserRole.user_id).where(UserRole.role_id == role.id)).all()
        if user_ids:
             # This requires UserSession import, avoiding circular dep if possible or import inside
             from app.models.session import UserSession
             # Bulk update approach
             statement = select(UserSession).where(UserSession.user_id.in_(user_ids)).where(UserSession.is_active == True)
             sessions = db.exec(statement).all()
             for session in sessions:
                 session.is_active = False
                 db.add(session)
        
        db.commit()
        
    db.refresh(role)
    return role


@router.get("/roles/{role_id}", response_model=rbac_schema.RoleDetail)
def get_role_detail(
    role_id: int,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Get detailed role information including hierarchy and stats.
    """
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
        
    # 1. User Count
    # Combining counts from UserRole and AdminUserRole if applicable
    # Querying relationship table for counting is more efficient than loading relationships
    user_count = db.exec(select(func.count()).select_from(UserRole).where(UserRole.role_id == role_id)).one()
    
    # 2. Permission Tree
    permissions = role.permissions
    permission_tree = {}
    for perm in permissions:
        if perm.module not in permission_tree:
            permission_tree[perm.module] = []
        permission_tree[perm.module].append(perm.action)
        
    # 3. Hierarchy
    parent_role = None
    if role.parent_role_id:
        parent_role_obj = db.get(Role, role.parent_role_id)
        if parent_role_obj:
            parent_role = rbac_schema.RoleRead.model_validate(parent_role_obj)
            
    child_roles_objs = db.exec(select(Role).where(Role.parent_role_id == role_id)).all()
    child_roles = [rbac_schema.RoleRead.model_validate(c) for c in child_roles_objs]
    
    # Construct Response
    result = rbac_schema.RoleDetail.model_validate(role)
    result.user_count = user_count
    result.permission_tree = permission_tree
    result.parent_role = parent_role
    result.child_roles = child_roles
    
    return result

@router.delete("/roles/{role_id}", response_model=Any)
def delete_role(
    role_id: int,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Soft delete a role.
    """
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
        
    # 1. System Role Protection
    if role.is_system_role:
        raise HTTPException(status_code=400, detail="Cannot delete system roles")
        
    # 2. Check for active users
    # Check UserRole table
    user_count = db.exec(select(func.count()).select_from(UserRole).where(UserRole.role_id == role_id)).one()
    if user_count > 0:
        raise HTTPException(status_code=400, detail="Cannot delete role with assigned active users")
        
    # Check AdminUserRole table
    admin_user_count = db.exec(select(func.count()).select_from(AdminUserRole).where(AdminUserRole.role_id == role_id)).one()
    if admin_user_count > 0:
        raise HTTPException(status_code=400, detail="Cannot delete role with assigned admin users")

    # 3. Soft Delete
    role.is_active = False
    db.add(role)
    db.commit()
    
    return {"status": "success", "message": "Role deleted successfully"}
