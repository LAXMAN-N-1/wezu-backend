from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func, col, update
from sqlalchemy.orm import selectinload
from datetime import datetime, UTC
import logging

from app.api import deps

logger = logging.getLogger(__name__)
from app.models.admin_user import AdminUser
from app.models.rbac import Role, Permission, RolePermission, AdminUserRole, UserRole
from app.models.session import UserSession
from app.services.auth_service import AuthService
from app.schemas import rbac as rbac_schema

router = APIRouter()

def _resolve_assigned_by_admin_id(db: Session, current_user: Any) -> Optional[int]:
    """
    Resolve a valid admin_users.id for RBAC assignment metadata.

    user_roles.assigned_by points to admin_users.id, but current auth dependencies
    return app.models.user.User. If there is no matching AdminUser row, return None
    so role assignment does not fail with a FK error.
    """
    current_user_id = getattr(current_user, "id", None)
    if current_user_id is not None:
        admin_by_id = db.get(AdminUser, current_user_id)
        if admin_by_id:
            return admin_by_id.id

    current_user_email = getattr(current_user, "email", None)
    if isinstance(current_user_email, str) and current_user_email.strip():
        admin_by_email = db.exec(
            select(AdminUser).where(func.lower(AdminUser.email) == current_user_email.strip().lower())
        ).first()
        if admin_by_email:
            return admin_by_email.id

    return None

@router.get("/roles", response_model=List[rbac_schema.RoleRead])
def read_roles(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    active_only: bool = False,
    include_permissions: bool = True,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Retrieve roles.
    """
    # Pre-fetch permissions efficiently
    query = select(Role).options(selectinload(Role.permissions))
    
    if category:
        query = query.where(Role.category == category)
        
    if active_only:
        query = query.where(Role.is_active == True)
        
    roles = db.exec(query.offset(skip).limit(limit)).all()
    
    # Enrichment
    results = []
    
    # Batch count users for these roles to avoid N+1 and slow relationship loading
    role_ids = [r.id for r in roles]
    user_counts = {}
    active_user_counts = {}
    if role_ids:
        from app.models.rbac import UserRole
        # Efficient count query grouping by role_id
        count_data = db.exec(
            select(UserRole.role_id, func.count(UserRole.user_id))
            .where(col(UserRole.role_id).in_(role_ids))
            .group_by(UserRole.role_id)
        ).all()
        user_counts = {rid: count for rid, count in count_data}
        now = datetime.now(UTC)
        active_count_data = db.exec(
            select(UserRole.role_id, func.count(UserRole.user_id))
            .where(
                col(UserRole.role_id).in_(role_ids),
                UserRole.effective_from <= now,
                ((UserRole.expires_at == None) | (UserRole.expires_at >= now)),
            )
            .group_by(UserRole.role_id)
        ).all()
        active_user_counts = {rid: count for rid, count in active_count_data}

    for role in roles:
        # Use pre-fetched permissions
        perms = role.permissions
        
        role_data = rbac_schema.RoleRead.model_validate(role)
        role_data.permission_count = len(perms)
        
        # Use batch-fetched user count
        role_data.user_count = user_counts.get(role.id, 0)
        role_data.active_user_count = active_user_counts.get(role.id, 0)
            
        if not include_permissions:
            role_data.permissions = None
        
        results.append(role_data)
        
    return results

@router.post("/roles", response_model=rbac_schema.RoleRead)
def create_role(
    *,
    db: Session = Depends(deps.get_db),
    role_in: rbac_schema.RoleCreate,
    current_user: AdminUser = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Create new role.
    """
    # 1. Check uniqueness
    existing = db.exec(select(Role).where(Role.name == role_in.name)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Role name already exists")
        
    role_data = role_in.model_dump(exclude={"permissions", "permission_ids", "parent_role_id", "parent_id"})
    
    # 2. Inheritance Logic
    permissions_to_assign = set(role_in.permissions or [])
    
    parent_id = role_in.parent_role_id or getattr(role_in, "parent_id", None)
    if parent_id:
        parent_role = db.get(Role, parent_id)
        if not parent_role:
             raise HTTPException(status_code=404, detail="Parent role not found")
        allowed_dealer_templates = {
            "dealer_owner",
            "dealer_manager",
            "dealer_inventory_staff",
            "dealer_finance_staff",
            "dealer_support_staff",
        }
        if (parent_role.name or "").strip().lower() not in allowed_dealer_templates:
            raise HTTPException(
                status_code=400,
                detail="Custom role parent must be a dealer template role",
            )
        if not role_in.dealer_id:
            raise HTTPException(
                status_code=400,
                detail="dealer_id is required for custom role creation",
            )
        role_data["is_custom_role"] = True
        role_data["scope_owner"] = "dealer"
        
        # Load parent permissions
        # Note: SQLModel relationship access might require eager load or session attached
        # We can query link table directly
        parent_perms = db.exec(select(Permission.slug).join(RolePermission).where(RolePermission.role_id == parent_role.id)).all()
        permissions_to_assign.update(parent_perms)
        
        role_data["parent_id"] = parent_id
    else:
        # Preset global roles are managed by migration/seed only.
        raise HTTPException(
            status_code=400,
            detail="Global custom role creation is disabled; create dealer child roles only",
        )

    role = Role(**role_data)
    db.add(role)
    db.commit()
    db.refresh(role)
    
    # 3. Assign Permissions (batch lookup instead of per-slug query)
    if permissions_to_assign:
        found_perms = db.exec(
            select(Permission).where(col(Permission.slug).in_(list(permissions_to_assign)))
        ).all()
        for permission in found_perms:
            link = RolePermission(role_id=role.id, permission_id=permission.id)
            db.add(link)
    
    db.commit()
    db.refresh(role)
    
    # Audit Log
    from app.services.audit_service import AuditService
    AuditService.log_action(
        db=db,
        user_id=current_user.id,
        action="create_role",
        resource_type="role",
        resource_id=str(role.id),
        details=f"Created role '{role.name}'"
    )
    
    return role

@router.post("/permissions", response_model=rbac_schema.PermissionRead)
def create_permission(
    *,
    permission_in: rbac_schema.PermissionCreate,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Create a new custom permission.
    """
    # 1. Check Uniqueness
    existing = db.exec(select(Permission).where(Permission.slug == permission_in.slug)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Permission slug already exists")
        
    # 2. Create Permission
    permission = Permission.model_validate(permission_in)
    db.add(permission)
    db.commit()
    db.refresh(permission)
    
    return permission


@router.get("/permissions", response_model=rbac_schema.PermissionListResponse)
def read_permissions(
    skip: int = 0,
    limit: int = 1000, # Increased limit for grouping view
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Retrieve permissions grouped by module.
    """
    permissions = db.exec(select(Permission).order_by(Permission.module, Permission.slug)).all()
    
    grouped = {}
    
    for perm in permissions:
        if perm.module not in grouped:
            grouped[perm.module] = []
            
        # Transform to Item
        parts = perm.slug.split(":")
        if len(parts) >= 3:
            label = f"{parts[1].replace('_', ' ').title()} ({parts[2]})"
        else:
            label = perm.slug
        if perm.description:
             desc = perm.description
        else:
             desc = f"Access to {perm.action} {perm.module}"
             
        item = rbac_schema.PermissionItem(
            id=perm.slug,
            label=label,
            description=desc,
            resource=perm.module,
            action=perm.action,
            scope=perm.scope or "global"
        )
        grouped[perm.module].append(item)
        
    modules = []
    for module_name, items in grouped.items():
        # Clean module label
        mod_label = module_name.replace("_", " ").title()
        modules.append(rbac_schema.PermissionModule(
            module=module_name,
            label=mod_label,
            permissions=items
        ))
        
    return rbac_schema.PermissionListResponse(modules=modules)




@router.get("/roles/{role_id}/permissions", response_model=rbac_schema.RolePermissionsResponse)
def get_role_permissions(
    role_id: int,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Get all permissions for a role, including inherited ones.
    """
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    def perm_to_item(perm):
        label = perm.slug.split(":")[-1].replace("_", " ").title() if ":" in perm.slug else perm.slug
        desc = perm.description or f"Access to {perm.action} {perm.module}"
        return rbac_schema.PermissionItem(
            id=perm.slug,
            label=label,
            description=desc,
            resource=perm.module,
            action=perm.action,
            scope=perm.scope
        )

    # 1. Direct Permissions
    direct_perms = [perm_to_item(p) for p in role.permissions]
    
    # 2. Inherited Permissions
    inherited_list = []
    
    # Traverse Parents
    current = role
    while current.parent_id:
        parent = db.get(Role, current.parent_id)
        if not parent:
            break
            
        p_items = [perm_to_item(p) for p in parent.permissions]
        if p_items:
             inherited_list.append(rbac_schema.InheritedPermissions(
                 source_role_id=parent.id,
                 source_role_name=parent.name,
                 permissions=p_items
             ))
        current = parent

    # 3. Aggregated View (Grouped)
    all_perms_map = {}
    
    # Add direct
    for p in direct_perms:
        all_perms_map[p.id] = p
        
    # Add inherited (overwriting if same slug? usually union. Inherited permissions shouldn't conflict, if they do, direct might override or just exist)
    # We just want unique set.
    for group in inherited_list:
        for p in group.permissions:
            if p.id not in all_perms_map:
                all_perms_map[p.id] = p
                
    # Group by module
    grouped_map = {}
    for p in all_perms_map.values():
        if p.resource not in grouped_map:
            grouped_map[p.resource] = []
        grouped_map[p.resource].append(p)
        
    modules = []
    for mod_name, items in grouped_map.items():
        modules.append(rbac_schema.PermissionModule(
            module=mod_name,
            label=mod_name.replace("_", " ").title(),
            permissions=items
        ))
        
    return rbac_schema.RolePermissionsResponse(
        direct_permissions=direct_perms,
        inherited_permissions=inherited_list,
        all_permissions_grouped=modules
    )


    return rbac_schema.RolePermissionsResponse(
        direct_permissions=direct_perms,
        inherited_permissions=inherited_list,
        all_permissions_grouped=modules
    )


@router.post("/roles/{role_id}/permissions", response_model=rbac_schema.RolePermissionUpdateResponse)
def assign_permissions_to_role(
    role_id: int,
    assignment: rbac_schema.RolePermissionAssign,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Assign permissions to a role.
    Mode: "overwrite" (replace all) or "append" (add to existing).
    """
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # 1. Validate permissions exist
    req_slugs = set(assignment.permissions)
    if not req_slugs:
        found_perms = []
    else:
        found_perms = db.exec(select(Permission).where(col(Permission.slug).in_(req_slugs))).all()
    
    found_slugs = {p.slug for p in found_perms}
    missing = req_slugs - found_slugs
    if missing:
        raise HTTPException(status_code=400, detail=f"Invalid permission slugs: {', '.join(missing)}")
        
    # 2. Update Logic
    if assignment.mode == "overwrite":
         role.permissions = found_perms
    elif assignment.mode == "append":
         # Add ones that don't exist
         current_ids = {p.id for p in role.permissions}
         for p in found_perms:
             if p.id not in current_ids:
                 role.permissions.append(p)
    else:
        raise HTTPException(status_code=400, detail="Invalid mode. Use 'overwrite' or 'append'.")
        
    db.commit()
    db.refresh(role)
    
    # Audit Log
    from app.services.audit_service import AuditService
    
    details = f"Updated permissions for role '{role.name}'. Mode: {assignment.mode}."
    if assignment.mode == "overwrite":
         details += f" Set to: {', '.join([p.slug for p in role.permissions])}"
    elif assignment.mode == "append":
         details += f" Added: {', '.join([p.slug for p in found_perms])}"
         
    AuditService.log_action(
        db=db,
        user_id=current_user.id,
        action="update_role_permissions",
        resource_type="role",
        resource_id=str(role.id),
        details=details
    )
    
    # 3. Session Invalidation
    users_affected = 0
    
    # Invalidate sessions for regular users with this role
    if role.users:
        user_ids = [u.id for u in role.users]
        if user_ids:
            # Bulk update session status
            # Bulk revoke sessions for users with this role
            # Note: revoke_all_user_sessions is per user. We need bulk!
            # Or loop.
            for uid in user_ids:
                 AuthService.revoke_all_user_sessions(db, uid)
            users_affected = len(user_ids)
    
    return {
        "role_id": role.id,
        "users_affected": users_affected,
        "active_permissions": [p.slug for p in role.permissions]
    }


@router.get("/users/{user_id}/roles", response_model=List[rbac_schema.UserRoleDetail])
def get_user_roles(
    user_id: int,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_admin),
) -> Any:
    """
    List all roles assigned to a user with details.
    """
    from app.models.user import User
    
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Query UserRole with Role and AdminUser (assigned_by)
    # We can fetch UserRoles and then join or just iterate since likely small number
    user_roles = db.exec(select(UserRole).where(UserRole.user_id == user_id)).all()
    
    # Batch-load roles + admin users (eliminates 2 N+1 per user-role)
    role_ids = list({ur.role_id for ur in user_roles if ur.role_id})
    admin_ids = list({ur.assigned_by for ur in user_roles if ur.assigned_by})
    roles_map = {r.id: r for r in db.exec(select(Role).where(Role.id.in_(role_ids))).all()} if role_ids else {}
    admins_map = {a.id: a for a in db.exec(select(AdminUser).where(AdminUser.id.in_(admin_ids))).all()} if admin_ids else {}

    results = []
    now = datetime.now(UTC)
    
    for ur in user_roles:
        role = roles_map.get(ur.role_id)
        if not role:
            # Should not happen with FK constraint but safe check
            continue
            
        assigned_by_name = None
        if ur.assigned_by:
            admin = admins_map.get(ur.assigned_by)
            if admin:
                assigned_by_name = admin.full_name or admin.email
        
        # Calculate Active Status
        is_active = True
        if not role.is_active:
             is_active = False # Role itself disabled
        elif ur.expires_at and ur.expires_at < now:
             is_active = False
        elif ur.effective_from and ur.effective_from > now:
             is_active = False
             
        results.append(rbac_schema.UserRoleDetail(
            role_id=role.id,
            role_name=role.name,
            role_description=role.description,
            assigned_at=ur.created_at,
            assigned_by=ur.assigned_by,
            assigned_by_name=assigned_by_name,
            effective_from=ur.effective_from,
            expires_at=ur.expires_at,
            notes=ur.notes,
            is_active=is_active
        ))
        
    return results

    return results


@router.post("/roles/bulk-assign", response_model=rbac_schema.BulkRoleAssignResponse)
def bulk_assign_roles(
    *,
    assignment: rbac_schema.BulkRoleAssignRequest,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Assign a role to multiple users.
    """
    from app.models.user import User
    
    # 1. Validate Role
    role = db.get(Role, assignment.role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
        
    results = []
    success_count = 0
    fail_count = 0
    
    assigned_by_admin_id = _resolve_assigned_by_admin_id(db, current_user)

    # Batch-load users + existing links (eliminates 2 N+1 per user)
    batch_users = db.exec(select(User).where(User.id.in_(assignment.user_ids))).all()
    batch_users_map = {u.id: u for u in batch_users}
    existing_links_list = db.exec(
        select(UserRole).where(
            UserRole.user_id.in_(assignment.user_ids),
            UserRole.role_id == role.id,
        )
    ).all()
    existing_link_set = {el.user_id for el in existing_links_list}

    for uid in assignment.user_ids:
        try:
            user = batch_users_map.get(uid)
            if not user:
                results.append(rbac_schema.BulkAssignmentResult(user_id=uid, success=False, message="User not found"))
                fail_count += 1
                continue

            # Single-role compatibility: keep primary role on users.role_id in sync.
            if user.role_id != role.id:
                user.role_id = role.id
                db.add(user)
                
            # Check existing
            if uid in existing_link_set:
                 # Already assigned, consider success or updated
                 results.append(rbac_schema.BulkAssignmentResult(user_id=uid, success=True, message="Already assigned"))
                 success_count += 1
            else:
                new_link = UserRole(
                    user_id=uid,
                    role_id=role.id,
                    assigned_by=assigned_by_admin_id,
                    effective_from=datetime.now(UTC)
                )
                db.add(new_link)
                results.append(rbac_schema.BulkAssignmentResult(user_id=uid, success=True, message="Assigned successfully"))
                success_count += 1

            # Commit per user so one failure does not fail the entire batch.
            db.commit()
            AuthService.revoke_all_user_sessions(db, uid)
                
        except Exception as e:
            db.rollback()
            results.append(rbac_schema.BulkAssignmentResult(user_id=uid, success=False, message=str(e)))
            fail_count += 1
    
    return rbac_schema.BulkRoleAssignResponse(
        total_requested=len(assignment.user_ids),
        total_success=success_count,
        total_failed=fail_count,
        results=results
    )

    
    return rbac_schema.BulkRoleAssignResponse(
        total_requested=len(assignment.user_ids),
        total_success=success_count,
        total_failed=fail_count,
        results=results
    )


@router.get("/roles/{role_id}/users")
def get_users_by_role(
    role_id: int,
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    region: Optional[str] = None,
    export_csv: bool = False,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Get all users with a specific role.
    Supports filtering by active status and region (state/city).
    Supports CSV export.
    """
    from app.models.user import User
    from app.models.address import Address
    
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
        
    
    # Start Query - Select both User and UserRole to get assignment details
    query = select(User, UserRole).join(UserRole).where(UserRole.role_id == role_id)
    
    if active_only:
        query = query.where(User.is_active == True)
        
    if region:
        query = query.join(Address).where(
            (col(Address.state).ilike(f"%{region}%")) | 
            (col(Address.city).ilike(f"%{region}%"))
        ).distinct()
        
    # Count total
    # Use subquery for count to handle joins correctly
    count_query = select(func.count()).select_from(query.subquery())
    total = db.exec(count_query).one()
    
    if export_csv:
        # Fetch all
        results = db.exec(query).all()
        
        import csv
        import io
        from fastapi.responses import StreamingResponse
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Headers
        headers = ["User ID", "Full Name", "Email", "Phone", "Status", "Joined At", "Assigned At", "Assigned By (ID)"]
        writer.writerow(headers)
        
        for user, ur in results:
            writer.writerow([
                user.id,
                user.full_name or "",
                user.email or "",
                user.phone_number or "",
                "Active" if user.is_active else "Inactive",
                user.created_at,
                ur.created_at,
                ur.assigned_by or ""
            ])
            
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=role_{role.name}_users.csv"}
        )
        
    # Standard JSON Response
    results = db.exec(query.offset(skip).limit(limit)).all()
    
    items = []
    for user, ur in results:
        # Enrich with assignment info
        item = {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "phone_number": user.phone_number,
            "is_active": user.is_active,
            "assigned_at": ur.created_at,
            "assigned_by": ur.assigned_by,
            "expires_at": ur.expires_at
        }
        items.append(item)
        
    return {
        "total": total,
        "items": items,
        "role_name": role.name,
        "skip": skip,
        "limit": limit
    }


@router.post("/users/{source_user_id}/roles/transfer", response_model=rbac_schema.RoleTransferResponse)
def transfer_role_assignment(
    source_user_id: int,
    transfer_req: rbac_schema.RoleTransferRequest,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Transfer a role from one user to another.
    Removes role from source user and assigns to target user.
    """
    from app.models.user import User
    from app.models.audit_log import AuditLog
    from app.services.notification_service import NotificationService
    
    # 1. Validate Source User
    source_user = db.get(User, source_user_id)
    if not source_user:
        raise HTTPException(status_code=404, detail="Source user not found")
        
    # 2. Validate Target User
    target_user = db.get(User, transfer_req.new_user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")
        
    # 3. Validate Role
    role = db.get(Role, transfer_req.role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
        
    # 4. Check Source has Role
    source_link = db.exec(
        select(UserRole)
        .where(UserRole.user_id == source_user_id)
        .where(UserRole.role_id == role.id)
    ).first()
    
    if not source_link:
        raise HTTPException(status_code=400, detail="Source user does not have this role")
        
    # 5. Check Target doesn't have Role
    target_link = db.exec(
        select(UserRole)
        .where(UserRole.user_id == target_user.id)
        .where(UserRole.role_id == role.id)
    ).first()
    
    if target_link:
        raise HTTPException(status_code=400, detail="Target user already has this role")

    assigned_by_admin_id = _resolve_assigned_by_admin_id(db, current_user)

    try:
        # --- Transaction Start ---
        
        # A. Remove from source
        db.delete(source_link)
        
        # B. Add to target
        new_link = UserRole(
            user_id=target_user.id,
            role_id=role.id,
            assigned_by=assigned_by_admin_id,
            notes=f"Transferred from User {source_user_id}. Reason: {transfer_req.reason or 'No reason provided'}"
        )
        db.add(new_link)
        db.flush()

        # Single-role compatibility for login/auth checks.
        target_user.role_id = role.id
        db.add(target_user)
        if source_user.role_id == role.id:
            replacement_link = db.exec(
                select(UserRole)
                .where(UserRole.user_id == source_user_id)
                .where(UserRole.role_id != role.id)
            ).first()
            source_user.role_id = replacement_link.role_id if replacement_link else None
            db.add(source_user)
        
        # C. Audit Logs
        db.add(AuditLog(
            action="ROLE_TRANSFER_REMOVE",
            resource_type="user_role",
            resource_id=str(source_user_id),
            details=f"Role {role.name} transferred TO user {target_user.id}",
            user_id=current_user.id
        ))
        
        db.add(AuditLog(
            action="ROLE_TRANSFER_ADD",
            resource_type="user_role",
            resource_id=str(target_user.id),
            details=f"Role {role.name} transferred FROM user {source_user_id}",
            user_id=current_user.id
        ))
        
        # D. Invalidate Sessions
        # D. Invalidate Sessions
        AuthService.revoke_all_user_sessions(db, source_user_id)
        AuthService.revoke_all_user_sessions(db, target_user.id)
                
        db.commit()
        # No ID to refresh for new_link
            
        return rbac_schema.RoleTransferResponse(
            success=True,
            message="Role transferred successfully",
            old_assignment_id=None,
            new_assignment_id=0 # No specific ID for link table
        )
        
    except Exception as e:
        db.rollback()
        logger.exception("role_transfer_failed")
        raise HTTPException(status_code=500, detail="Role transfer failed")


@router.post("/users/{user_id}/roles", response_model=rbac_schema.UserRoleAssignmentResponse)
def assign_roles_to_user(
    *,
    user_id: int,
    assignment: rbac_schema.UserRoleAssign,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Assign a role to a user.
    Supports effective dates and expiration.
    Auth: Super Admin only (for now).
    """
    from app.models.user import User
    from app.services.auth_service import AuthService
    
    # 1. Validate User & Role
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    role = db.get(Role, assignment.role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
        
    assigned_by_admin_id = _resolve_assigned_by_admin_id(db, current_user)

    # Single-role compatibility: keep primary role on users.role_id in sync.
    if user.role_id != role.id:
        user.role_id = role.id
        db.add(user)

    # 2. Check/Create Assignment
    # Check if assignment already exists
    existing_link = db.exec(
        select(UserRole)
        .where(UserRole.user_id == user_id)
        .where(UserRole.role_id == assignment.role_id)
    ).first()
    
    if existing_link:
        # Update existing
        if assigned_by_admin_id is not None:
            existing_link.assigned_by = assigned_by_admin_id
        existing_link.notes = assignment.notes
        if assignment.expires_at:
            existing_link.expires_at = assignment.expires_at
        if assignment.effective_from:
            existing_link.effective_from = assignment.effective_from
        
        db.add(existing_link)
    else:
        # Create new
        new_link = UserRole(
            user_id=user_id,
            role_id=assignment.role_id,
            assigned_by=assigned_by_admin_id,
            notes=assignment.notes,
            effective_from=assignment.effective_from or datetime.now(UTC),
            expires_at=assignment.expires_at
        )
        db.add(new_link)
        
    db.commit()
    
    # 3. Side Effects: Invalidate User Session
    AuthService.revoke_all_user_sessions(db, user_id)
    
    # 4. Prepare Response (Refresh perms)
    db.refresh(user)
    
    active_perms = set()
    for r in user.roles:
        for p in r.permissions:
            active_perms.add(p.slug)
            
    menu = AuthService.get_menu_for_role(db, role.name)
    
    return rbac_schema.UserRoleAssignmentResponse(
        success=True,
        active_permissions=list(active_perms),
        menu_config=menu
    )


@router.delete("/users/{user_id}/roles/{role_id}", response_model=rbac_schema.UserRoleAssignmentResponse)
def remove_role_from_user(
    *,
    user_id: int,
    role_id: int,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Remove a role from a user.
    Prevents removing the last role.
    """
    from app.models.user import User
    from app.models.audit_log import AuditLog
    from app.services.auth_service import AuthService
    
    # 1. Validate User & Role
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
        
    # 2. Check if assignment exists
    link = db.exec(
        select(UserRole)
        .where(UserRole.user_id == user_id)
        .where(UserRole.role_id == role_id)
    ).first()
    
    if not link:
        raise HTTPException(status_code=404, detail="Role not assigned to user")
        
    # 3. Prevent removing last role
    role_count = db.exec(select(func.count()).select_from(UserRole).where(UserRole.user_id == user_id)).one()
    if role_count <= 1:
        raise HTTPException(status_code=400, detail="Cannot remove the last role from a user")
        
    # 4. Remove Assignment
    db.delete(link)
    db.flush()

    # Single-role compatibility: if removing primary role, move to remaining role (if any).
    if user.role_id == role_id:
        replacement_link = db.exec(
            select(UserRole)
            .where(UserRole.user_id == user_id)
            .where(UserRole.role_id != role_id)
        ).first()
        user.role_id = replacement_link.role_id if replacement_link else None
        db.add(user)

    db.commit()
    db.refresh(user)
    
    # 5. Invalidate Session
    user_sessions = db.exec(select(UserSession).where(UserSession.user_id == user_id).where(UserSession.is_active == True)).all()
    if user_sessions:
        for sess in user_sessions:
            sess.is_active = False
            db.add(sess)
        db.commit()
        
    # 6. Log Activity
    audit_log = AuditLog(
        user_id=current_user.id,
        action="remove_role_from_user",
        resource_type="user",
        resource_id=str(user_id),
        details=f"Removed role {role.name} ({role.id}) from user {user.email}",
        ip_address=None # Not readily available in this context without Request
    )
    db.add(audit_log)
    db.commit()

    # 7. Prepare Response (Refresh perms)
    # Re-calculate permissions
    active_perms = set()
    first_role_name = None
    
    # Reload user.roles
    user_roles = db.exec(select(UserRole).where(UserRole.user_id == user_id)).all()
    # Batch-load Role objects (eliminates N+1 per role)
    ur_role_ids = list({ur.role_id for ur in user_roles})
    ur_roles_map = {r.id: r for r in db.exec(select(Role).where(Role.id.in_(ur_role_ids))).all()} if ur_role_ids else {}
    for ur in user_roles:
        r = ur_roles_map.get(ur.role_id)
        if r and r.is_active:
            if not first_role_name:
                first_role_name = r.name
            for p in r.permissions:
                active_perms.add(p.slug)
    
    # Fallback for menu if roles exist (which they should)
    menu = []
    if first_role_name:
         menu = AuthService.get_menu_for_role(db, first_role_name)
    
    return rbac_schema.UserRoleAssignmentResponse(
        success=True,
        active_permissions=list(active_perms),
        menu_config=menu
    )


@router.put("/roles/{role_id}", response_model=rbac_schema.RoleRead)
def update_role(
    *,
    role_id: int,
    role_in: rbac_schema.RoleUpdate,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_admin),
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
    changes = []
    if role_in.name is not None and role_in.name != role.name:
        # Check uniqueness
        existing = db.exec(select(Role).where(Role.name == role_in.name)).first()
        if existing:
             raise HTTPException(status_code=400, detail="Role name already exists")
        changes.append(f"Name: '{role.name}' -> '{role_in.name}'")
        role.name = role_in.name
        
    if role_in.description is not None and role_in.description != role.description:
        changes.append(f"Description changed")
        role.description = role_in.description
    if role_in.category is not None and role_in.category != role.category:
        changes.append(f"Category: '{role.category}' -> '{role_in.category}'")
        role.category = role_in.category
    if role_in.level is not None and role_in.level != role.level:
        changes.append(f"Level: {role.level} -> {role_in.level}")
        role.level = role_in.level
    if role_in.parent_role_id is not None and role_in.parent_role_id != role.parent_id:
        # Prevent circular logic usually, but keep simple for now
        changes.append(f"Parent Role ID: {getattr(role, 'parent_id', None)} -> {role_in.parent_role_id}")
        role.parent_id = role_in.parent_role_id
        
    db.add(role)
    db.commit()
    
    # 3. Update Permissions
    if role_in.permissions is not None:
        # Clear existing
        existing_links = db.exec(select(RolePermission).where(RolePermission.role_id == role.id)).all()
        for link in existing_links:
            db.delete(link)
            
        # Add new (batch lookup instead of per-slug query)
        added_perms = []
        if role_in.permissions:
            found_perms = db.exec(
                select(Permission).where(col(Permission.slug).in_(list(role_in.permissions)))
            ).all()
            for permission in found_perms:
                db.add(RolePermission(role_id=role.id, permission_id=permission.id))
                added_perms.append(permission.slug)
        changes.append(f"Permissions set to: {', '.join(added_perms)}")
        
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
    
    # Audit Log
    from app.services.audit_service import AuditService
    AuditService.log_action(
        db=db,
        user_id=current_user.id,
        action="update_role",
        resource_type="role",
        resource_id=str(role.id),
        details=f"Updated role '{role.name}'. Changes: {'; '.join(changes)}" if changes else f"Updated role '{role.name}' (No field changes, possibly permissions)"
    )
    
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "category": role.category,
        "level": role.level,
        "is_active": role.is_active,
        "parent_role_id": getattr(role, "parent_id", None),
        "permissions": [p.slug for p in role.permissions]
    }


@router.get("/roles/{role_id}", response_model=rbac_schema.RoleDetail)
def get_role_detail(
    role_id: int,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_admin),
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
    if role.parent_id:
        parent_role_obj = db.get(Role, role.parent_id)
        if parent_role_obj:
            parent_role = rbac_schema.RoleRead.model_validate(parent_role_obj)
            
    child_roles_objs = db.exec(select(Role).where(Role.parent_id == role_id)).all()
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
    current_user: AdminUser = Depends(deps.get_current_active_admin),
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
    
    # 3. Soft Delete
    role.is_active = False
    db.add(role)
    db.commit()
    
    # Audit Log
    from app.services.audit_service import AuditService
    AuditService.log_action(
        db=db,
        user_id=current_user.id,
        action="delete_role",
        resource_type="role",
        resource_id=str(role.id),
        details=f"Deleted role '{role.name}' (Soft Delete)"
    )
    
    return {"status": "success", "message": "Role deleted successfully"}


    db.commit()
    
    return Any


@router.get("/users/{user_id}/permissions/check", response_model=rbac_schema.PermissionCheckResponse)
def check_user_permission(
    user_id: int,
    permission: str,
    resource_id: Optional[int] = None,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Verify if a user has a specific permission.
    Traverses all assigned roles and their hierarchy.
    """
    # 1. Get User explicitly (Assuming User model, not AdminUser for this check as per req)
    # The requirement says "users/{user_id}", implying the app Users.
    # However, AdminUser might also implement RBAC.
    # Since existing RBAC models link to "User" via UserRole and "AdminUser" via AdminUserRole,
    # and the prompt context heavily implied "User" (frontend UI), checks.
    
    # We need to import User model inside function or at top to avoid loops if any
    from app.models.user import User
    
    target_user = db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # 2. Collect all roles (direct)
    user_roles = target_user.roles
    
    # 3. Check permissions
    # We need to traverse up for each role
    
    for role in user_roles:
        # Check current role hierarchy
        current = role
        while current:
            # Check permissions in current role
            for p in current.permissions:
                if p.slug == permission:
                    # Log Grant
                    from app.services.audit_service import AuditService
                    AuditService.log_action(
                        db=db,
                        user_id=current_user.id,
                        action="permission_check",
                        resource_type="permission",
                        resource_id=permission,
                        details=f"Check for user {user_id}. Granted: True. Role: {role.name}"
                    )
                    
                    return rbac_schema.PermissionCheckResponse(
                        has_permission=True,
                        granted_by_role=role.name, # The direct role assigned to user
                        scope=p.scope
                    )
            
            # Move to parent
            if current.parent_role_id:
                current = db.get(Role, current.parent_role_id)
            else:
                break
                
    # Log Denial
    from app.services.audit_service import AuditService
    AuditService.log_action(
        db=db,
        user_id=current_user.id,
        action="permission_check",
        resource_type="permission",
        resource_id=permission,
        details=f"Check for user {user_id}. Granted: False"
    )

    return rbac_schema.PermissionCheckResponse(has_permission=False)


@router.get("/users/{user_id}/permissions", response_model=rbac_schema.PermissionListResponse)
def get_user_permissions(
    user_id: int,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Get complete set of permissions for a user (direct + inherited).
    Grouped by module.
    """
    from app.models.user import User
    
    target_user = db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    unique_perms = {}
    
    # Traverse all roles
    for role in target_user.roles:
        current = role
        while current:
            for p in current.permissions:
                if p.slug not in unique_perms:
                    unique_perms[p.slug] = p
            
            if current.parent_role_id:
                current = db.get(Role, current.parent_role_id)
            else:
                break
                
    # Group by module
    grouped = {}
    for p in unique_perms.values():
        if p.module not in grouped:
            grouped[p.module] = []
            
        # Re-use logic to create item or helper function
        label = p.slug.split(":")[-1].replace("_", " ").title() if ":" in p.slug else p.slug
        desc = p.description or f"Access to {p.action} {p.module}"
        
        item = rbac_schema.PermissionItem(
            id=p.slug,
            label=label,
            description=desc,
            resource=p.module,
            action=p.action,
            scope=p.scope
        )
        grouped[p.module].append(item)
        
    modules = []
    for mod_name, items in grouped.items():
        modules.append(rbac_schema.PermissionModule(
            module=mod_name,
            label=mod_name.title(),
            permissions=items
        ))
        
    return rbac_schema.PermissionListResponse(modules=modules)


@router.post("/roles/{role_id}/duplicate", response_model=rbac_schema.RoleRead)
def duplicate_role(
    *,
    role_id: int,
    duplicate_in: rbac_schema.RoleDuplicate,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Duplicate an existing role.
    """
    # 1. Fetch Source Role
    source_role = db.get(Role, role_id)
    if not source_role:
        raise HTTPException(status_code=404, detail="Source role not found")
        
    # 2. Check Uniqueness of New Name
    existing = db.exec(select(Role).where(Role.name == duplicate_in.new_name)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Role name already exists")
        
    # 3. Create New Role
    # Copy attributes
    new_role = Role(
        name=duplicate_in.new_name,
        description=duplicate_in.description or source_role.description,
        category=source_role.category,
        level=source_role.level,
        parent_role_id=source_role.parent_role_id,
        is_system_role=False, # Cloned roles are always custom
        is_active=True
    )
    db.add(new_role)
    db.commit()
    db.refresh(new_role)
    
    # 4. Copy Permissions
    source_perms = db.exec(select(Permission).join(RolePermission).where(RolePermission.role_id == source_role.id)).all()
    
    for perm in source_perms:
        link = RolePermission(role_id=new_role.id, permission_id=perm.id)
        db.add(link)
        
    db.commit()
    db.refresh(new_role)
    
    db.refresh(new_role)
    
    return new_role


@router.get("/hierarchy", response_model=List[rbac_schema.RoleHierarchy])
def get_role_hierarchy(
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Get role hierarchy/tree.
    """
    # 1. Fetch all active roles
    roles = db.exec(select(Role).where(Role.is_active == True)).all()
    
    # 2. Build Tree
    role_map = {}
    roots = []
    
    # Initialize all nodes
    for role in roles:
        # Convert to hierarchy schema (without children first)
        r_schema = rbac_schema.RoleHierarchy.model_validate(role)
        # Manually enrich permission count if RoleRead (base) requires it or relies on it
        # Since RoleRead has permission_count=0 default, likely fine. 
        # But if we want accurate perm counts in tree:
        r_schema.permission_count = len(role.permissions) 
        r_schema.children = []
        role_map[role.id] = r_schema
        
    # Link nodes
    for role in roles:
        node = role_map[role.id]
        if role.parent_role_id and role.parent_role_id in role_map:
            parent = role_map[role.parent_role_id]
            parent.children.append(node)
        else:
            roots.append(node)
            
    return roots


@router.post("/users/{user_id}/access-paths", response_model=rbac_schema.AccessPathRead)
def assign_access_path(
    *,
    user_id: int,
    path_in: rbac_schema.AccessPathCreate,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Assign a geographic or hierarchical access path to a user.
    """
    from app.models.user import User
    from app.models.rbac import UserAccessPath
    
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Validate Access Level
    if path_in.access_level not in ["view", "manage", "admin"]:
        raise HTTPException(status_code=422, detail="Invalid access level. Must be view, manage, or admin.")

    access_path = UserAccessPath(
        user_id=user_id,
        path_pattern=path_in.path_pattern,
        access_level=path_in.access_level,
        created_by=current_user.id
    )
    
    db.add(access_path)
    db.commit()
    db.refresh(access_path)
    
    return access_path


@router.get("/users/{user_id}/access-paths", response_model=List[rbac_schema.AccessPathRead])
def get_user_access_paths(
    user_id: int,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Get all access paths assigned to a user.
    """
    from app.models.user import User
    from app.models.rbac import UserAccessPath
    
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    paths = db.exec(select(UserAccessPath).where(UserAccessPath.user_id == user_id)).all()
    
    # Enrich with Creator Name
    results = []
    for p in paths:
        item = rbac_schema.AccessPathRead.model_validate(p)
        if p.created_by:
            admin = db.get(AdminUser, p.created_by)
            if admin:
                item.created_by_name = admin.email # Or full_name if available
        results.append(item)
        
    return results


@router.delete("/users/{user_id}/access-paths/{path_id}", response_model=Any)
def remove_access_path(
    user_id: int,
    path_id: int,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Revoke a specific access path.
    """
    from app.models.rbac import UserAccessPath
    
    path = db.get(UserAccessPath, path_id)
    if not path:
        raise HTTPException(status_code=404, detail="Access path not found")
        
    if path.user_id != user_id:
        raise HTTPException(status_code=400, detail="Access path does not belong to this user")
        
    db.delete(path)
    db.commit()
    
    return {"status": "success", "message": "Access path revoked"}


@router.put("/users/{user_id}/access-paths/{path_id}", response_model=rbac_schema.AccessPathRead)
def update_access_path(
    user_id: int,
    path_id: int,
    path_in: rbac_schema.AccessPathUpdate,
    db: Session = Depends(deps.get_db),
    current_user: AdminUser = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Update access level for a specific path.
    """
    from app.models.rbac import UserAccessPath
    
    path = db.get(UserAccessPath, path_id)
    if not path:
        raise HTTPException(status_code=404, detail="Access path not found")
        
    if path.user_id != user_id:
        raise HTTPException(status_code=400, detail="Access path does not belong to this user")
        
    # Validate Access Level
    if path_in.access_level not in ["view", "manage", "admin"]:
        raise HTTPException(status_code=422, detail="Invalid access level. Must be view, manage, or admin.")
        
    path.access_level = path_in.access_level
    db.add(path)
    db.commit()
    db.refresh(path)
    
    return path
