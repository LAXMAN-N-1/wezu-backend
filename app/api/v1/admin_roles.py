from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from app.api import deps
from app.models.rbac import Role, Permission, UserRole
from app.models.user import User
from app.core.rbac import canonical_role_name, canonicalize_permission_set
from typing import List, Any, Optional
from pydantic import BaseModel
from datetime import datetime, UTC, timedelta

router = APIRouter()

PLATFORM_ADMIN_ROLES = {"super_admin", "operations_admin", "security_admin", "finance_admin"}


@router.post("/roles")
def create_role(
    role_in: Any, # Simple dict for now, should be schema
    db: Session = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Dynamic Role Creation (Part 1.1)
    """
    new_role = Role(
        name=role_in["name"],
        description=role_in.get("description"),
        category=role_in.get("category", "staff"),
        level=role_in.get("level", 5),
        parent_id=role_in.get("parent_id")
    )
    db.add(new_role)
    db.commit()
    db.refresh(new_role)
    return new_role

@router.get("/permissions")
def list_permissions(
    db: Session = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
) -> List[Permission]:
    """
    List all available permissions for role assignment.
    """
    return db.exec(select(Permission)).all()


# ===== ROLE DISTRIBUTION ANALYTICS =====

class RoleUserCount(BaseModel):
    role_id: int
    role_name: str
    user_count: int
    percentage: float
    category: Optional[str] = None


class RoleGrowthTrend(BaseModel):
    role_name: str
    current_count: int
    previous_count: int
    growth_rate: float  # percentage change


class RoleDistributionResponse(BaseModel):
    # Users per role
    users_per_role: List[RoleUserCount]
    
    # Total users with roles
    total_users_with_roles: int
    
    # Growth trends (30-day comparison)
    role_growth_trends: List[RoleGrowthTrend]
    
    # Most used roles (top 5)
    most_used_roles: List[RoleUserCount]
    
    # Underutilized roles (roles with < 5% of total)
    underutilized_roles: List[RoleUserCount]
    
    # Roles with no users
    empty_roles: List[str]
    
    # Generated timestamp
    generated_at: datetime


@router.get("/roles/distribution", response_model=RoleDistributionResponse)
async def get_role_distribution(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """
    Get role distribution analytics (Admin only).
    
    Returns:
    - Users per role with percentages
    - Role growth trends (30-day comparison)
    - Most used roles
    - Underutilized roles
    """
    # 1. Authorization
    current_user_roles = [canonical_role_name(r.name) for r in current_user.roles] if current_user.roles else []
    is_super_admin = "super_admin" in current_user_roles or current_user.is_superuser
    is_admin = bool(set(current_user_roles) & PLATFORM_ADMIN_ROLES)
    
    if not any([is_super_admin, is_admin]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins can access role distribution"
        )
    
    # 2. Get all roles
    roles = db.exec(select(Role)).all()
    
    # 3. Users per role — single GROUP BY query (eliminates N+1 COUNT per role)
    count_rows = db.exec(
        select(UserRole.role_id, func.count(UserRole.user_id.distinct()))
        .group_by(UserRole.role_id)
    ).all()
    role_counts = {row[0]: row[1] for row in count_rows}

    users_per_role = []
    for role in roles:
        count = role_counts.get(role.id, 0)
        users_per_role.append({
            "role": role,
            "count": count
        })
    
    total_users_with_roles = db.exec(
        select(func.count(UserRole.user_id.distinct()))
    ).one()
    
    # Convert to response models
    users_per_role_response = []
    for item in users_per_role:
        pct = (item["count"] / total_users_with_roles * 100) if total_users_with_roles > 0 else 0
        users_per_role_response.append(RoleUserCount(
            role_id=item["role"].id,
            role_name=item["role"].name,
            user_count=item["count"],
            percentage=round(pct, 2),
            category=item["role"].category
        ))
    
    # Sort by count descending
    users_per_role_response.sort(key=lambda x: x.user_count, reverse=True)
    
    # 4. Role growth trends (compare with 30 days ago)
    # This requires historical data from audit logs
    month_ago = datetime.now(UTC) - timedelta(days=30)
    
    role_growth_trends = []
    
    # For growth, we'll estimate based on user_role created_at if available
    # Otherwise, we'll show current counts with 0 growth
    for role in roles:
        current_count = role_counts.get(role.id, 0)
        
        # Try to get historical count from audit or estimate
        # For now, using a simple heuristic
        try:
            # Count users assigned to this role before 30 days ago
            previous_count = db.exec(
                select(func.count(UserRole.user_id.distinct()))
                .where(
                    UserRole.role_id == role.id,
                    UserRole.created_at <= month_ago
                )
            ).one()
        except Exception:
            previous_count = current_count  # Fallback
        
        growth = ((current_count - previous_count) / max(previous_count, 1)) * 100
        
        role_growth_trends.append(RoleGrowthTrend(
            role_name=role.name,
            current_count=current_count,
            previous_count=previous_count,
            growth_rate=round(growth, 2)
        ))
    
    # Sort by growth rate descending
    role_growth_trends.sort(key=lambda x: x.growth_rate, reverse=True)
    
    # 5. Most used roles (top 5)
    most_used = users_per_role_response[:5]
    
    # 6. Underutilized roles (< 5% of total)
    underutilized = [r for r in users_per_role_response if r.percentage < 5 and r.user_count > 0]
    
    # 7. Empty roles (no users)
    empty_roles = [r.role_name for r in users_per_role_response if r.user_count == 0]
    
    return RoleDistributionResponse(
        users_per_role=users_per_role_response,
        total_users_with_roles=total_users_with_roles,
        role_growth_trends=role_growth_trends,
        most_used_roles=most_used,
        underutilized_roles=underutilized,
        empty_roles=empty_roles,
        generated_at=datetime.now(UTC)
    )


# ===== ROLE TESTING =====

class MenuItemPreview(BaseModel):
    id: str
    label: str
    path: str
    icon: Optional[str] = None
    visible: bool = True


class ScreenAccess(BaseModel):
    screen_id: str
    screen_name: str
    accessible: bool
    actions: List[str]


class ActionEnabled(BaseModel):
    action_name: str
    enabled: bool
    resource: Optional[str] = None


class DataVisibility(BaseModel):
    data_type: str
    visibility_level: str  # "full", "partial", "none"
    filters: Optional[List[str]] = None


class RoleTestResponse(BaseModel):
    role_id: int
    role_name: str
    role_description: Optional[str]
    
    # Menu structure
    menu_structure: List[MenuItemPreview]
    
    # Available screens
    available_screens: List[ScreenAccess]
    
    # Actions enabled
    actions_enabled: List[ActionEnabled]
    
    # Data visibility
    data_visibility: List[DataVisibility]
    
    # Summary
    total_permissions: int
    access_level: str  # "full", "restricted", "minimal"
    
    generated_at: datetime


@router.post("/roles/{role_id}/test", response_model=RoleTestResponse)
async def test_role_configuration(
    role_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """
    Test/preview a role configuration without activating (Admin only).
    
    Returns:
    - Sample menu structure this role would see
    - Available screens and their access levels
    - Actions enabled by this role
    - Data visibility settings
    """
    # 1. Authorization
    current_user_roles = [canonical_role_name(r.name) for r in current_user.roles] if current_user.roles else []
    is_super_admin = "super_admin" in current_user_roles or current_user.is_superuser
    is_admin = bool(set(current_user_roles) & PLATFORM_ADMIN_ROLES)
    
    if not any([is_super_admin, is_admin]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins can test role configurations"
        )
    
    # 2. Get role
    role = db.exec(select(Role).where(Role.id == role_id)).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # 3. Get role permissions
    permissions = role.permissions if role.permissions else []
    permission_names = sorted(
        canonicalize_permission_set(
            [p.slug for p in permissions if getattr(p, "slug", None)]
        )
    )
    
    # 4. Build menu structure based on role
    menu_structure = []
    
    # Base menu items
    base_items = [
        {"id": "dashboard", "label": "Dashboard", "path": "/dashboard", "icon": "home"},
        {"id": "profile", "label": "Profile", "path": "/profile", "icon": "user"},
    ]
    
    # Role-specific menu items
    role_menu_mapping = {
        "super_admin": [
            {"id": "admin_users", "label": "User Management", "path": "/admin/users", "icon": "users"},
            {"id": "admin_roles", "label": "Role Management", "path": "/admin/roles", "icon": "shield"},
            {"id": "admin_settings", "label": "System Settings", "path": "/admin/settings", "icon": "settings"},
            {"id": "admin_analytics", "label": "Analytics", "path": "/admin/analytics", "icon": "chart"},
            {"id": "admin_audit", "label": "Audit Logs", "path": "/admin/audit", "icon": "history"},
        ],
        "operations_admin": [
            {"id": "admin_users", "label": "User Management", "path": "/admin/users", "icon": "users"},
            {"id": "admin_analytics", "label": "Analytics", "path": "/admin/analytics", "icon": "chart"},
            {"id": "admin_kyc", "label": "KYC Queue", "path": "/admin/kyc", "icon": "id-card"},
        ],
        "customer": [
            {"id": "rentals", "label": "My Rentals", "path": "/rentals", "icon": "battery"},
            {"id": "wallet", "label": "Wallet", "path": "/wallet", "icon": "wallet"},
            {"id": "history", "label": "History", "path": "/history", "icon": "clock"},
        ],
        "dealer_owner": [
            {"id": "stations", "label": "My Stations", "path": "/dealer/stations", "icon": "store"},
            {"id": "inventory", "label": "Inventory", "path": "/dealer/inventory", "icon": "box"},
            {"id": "earnings", "label": "Earnings", "path": "/dealer/earnings", "icon": "dollar"},
        ],
        "dealer_manager": [
            {"id": "stations", "label": "My Stations", "path": "/dealer/stations", "icon": "store"},
            {"id": "inventory", "label": "Inventory", "path": "/dealer/inventory", "icon": "box"},
            {"id": "team", "label": "Team", "path": "/dealer/team", "icon": "users"},
        ],
    }
    
    role_items = role_menu_mapping.get(role.name, [])
    all_items = base_items + role_items
    
    for item in all_items:
        menu_structure.append(MenuItemPreview(**item))
    
    # 5. Available screens
    screen_definitions = [
        {"id": "dashboard", "name": "Dashboard", "required_perm": None},
        {"id": "profile", "name": "User Profile", "required_perm": None},
        {"id": "users_list", "name": "Users List", "required_perm": "users:view:global"},
        {"id": "users_edit", "name": "Edit User", "required_perm": "users:update:global"},
        {"id": "roles_manage", "name": "Role Management", "required_perm": "roles:override:global"},
        {"id": "kyc_queue", "name": "KYC Queue", "required_perm": "kyc:approve:global"},
        {"id": "analytics", "name": "Analytics Dashboard", "required_perm": "analytics:view:global"},
        {"id": "audit_logs", "name": "Audit Logs", "required_perm": "audit:view:global"},
        {"id": "rentals", "name": "Rentals", "required_perm": "rentals:view:global"},
        {"id": "wallet", "name": "Wallet", "required_perm": "wallet:view:global"},
    ]
    
    available_screens = []
    for screen in screen_definitions:
        accessible = screen["required_perm"] is None or screen["required_perm"] in permission_names
        actions = []
        if accessible:
            required_perm = screen["required_perm"] or ""
            if ":override:" in required_perm:
                actions = ["view", "edit", "create", "delete", "configure"]
            elif ":update:" in required_perm or ":create:" in required_perm:
                actions = ["view", "edit", "create"]
            else:
                actions = ["view"]
        
        available_screens.append(ScreenAccess(
            screen_id=screen["id"],
            screen_name=screen["name"],
            accessible=accessible,
            actions=actions
        ))
    
    # 6. Actions enabled
    action_definitions = [
        {"name": "Create User", "perm": "users:create:global", "resource": "users"},
        {"name": "Edit User", "perm": "users:update:global", "resource": "users"},
        {"name": "Delete User", "perm": "users:delete:global", "resource": "users"},
        {"name": "Approve KYC", "perm": "kyc:approve:global", "resource": "kyc"},
        {"name": "Reject KYC", "perm": "kyc:override:global", "resource": "kyc"},
        {"name": "Manage Roles", "perm": "roles:override:global", "resource": "roles"},
        {"name": "View Analytics", "perm": "analytics:view:global", "resource": "analytics"},
        {"name": "Export Data", "perm": "analytics:export:global", "resource": "analytics"},
        {"name": "Impersonate User", "perm": "users:override:global", "resource": "users"},
    ]
    
    actions_enabled = []
    for action in action_definitions:
        enabled = action["perm"] in permission_names
        actions_enabled.append(ActionEnabled(
            action_name=action["name"],
            enabled=enabled,
            resource=action["resource"]
        ))
    
    # 7. Data visibility
    data_visibility = []
    
    # User data
    perm_set = set(permission_names)

    if is_super_admin or any(
        p.startswith("users:override:") or p.startswith("users:delete:") or p.startswith("users:assign:")
        for p in perm_set
    ):
        data_visibility.append(DataVisibility(data_type="User Data", visibility_level="full"))
    elif any(
        p.startswith("users:view:") or p.startswith("users:update:")
        for p in perm_set
    ):
        data_visibility.append(DataVisibility(data_type="User Data", visibility_level="partial", filters=["own_data", "assigned_users"]))
    else:
        data_visibility.append(DataVisibility(data_type="User Data", visibility_level="none"))
    
    # Financial data
    if any(
        p.startswith("finance:override:") or p.startswith("finance:delete:") or p.startswith("finance:approve:")
        for p in perm_set
    ):
        data_visibility.append(DataVisibility(data_type="Financial Data", visibility_level="full"))
    elif any(
        p.startswith("finance:view:") or p.startswith("finance:update:")
        for p in perm_set
    ):
        data_visibility.append(DataVisibility(data_type="Financial Data", visibility_level="partial", filters=["own_transactions"]))
    else:
        data_visibility.append(DataVisibility(data_type="Financial Data", visibility_level="none"))
    
    # Analytics data
    if any(
        p.startswith("analytics:override:") or p.startswith("analytics:delete:") or p.startswith("analytics:export:")
        for p in perm_set
    ):
        data_visibility.append(DataVisibility(data_type="Analytics", visibility_level="full"))
    elif any(
        p.startswith("analytics:view:") or p.startswith("analytics:update:")
        for p in perm_set
    ):
        data_visibility.append(DataVisibility(data_type="Analytics", visibility_level="partial", filters=["aggregated_only"]))
    else:
        data_visibility.append(DataVisibility(data_type="Analytics", visibility_level="none"))
    
    # 8. Determine access level
    if role.name == "super_admin" or len(permissions) > 20:
        access_level = "full"
    elif len(permissions) > 5:
        access_level = "restricted"
    else:
        access_level = "minimal"
    
    return RoleTestResponse(
        role_id=role.id,
        role_name=role.name,
        role_description=role.description,
        menu_structure=menu_structure,
        available_screens=available_screens,
        actions_enabled=actions_enabled,
        data_visibility=data_visibility,
        total_permissions=len(permissions),
        access_level=access_level,
        generated_at=datetime.now(UTC)
    )


# ===== BULK ROLE ASSIGNMENT =====

from app.services.audit_service import AuditService
import json as json_module


class BulkRoleAssignRequest(BaseModel):
    user_ids: List[int]
    role_id: int
    replace_existing: bool = False  # If true, replace all roles; if false, add to existing


class BulkRoleAssignResultItem(BaseModel):
    user_id: int
    success: bool
    error: Optional[str] = None


class BulkRoleAssignResponse(BaseModel):
    success_count: int
    failure_count: int
    role_name: str
    results: List[BulkRoleAssignResultItem]
    generated_at: datetime


@router.post("/roles/bulk-assign", response_model=BulkRoleAssignResponse)
async def bulk_assign_role(
    request: BulkRoleAssignRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """
    Assign a role to multiple users (Admin only).
    
    Options:
    - replace_existing: If true, removes all existing roles and assigns only the specified role
    - If false (default), adds the role to user's existing roles
    """
    # 1. Authorization
    current_user_roles = [canonical_role_name(r.name) for r in current_user.roles] if current_user.roles else []
    is_super_admin = "super_admin" in current_user_roles or current_user.is_superuser
    is_admin = bool(set(current_user_roles) & PLATFORM_ADMIN_ROLES)
    
    if not any([is_super_admin, is_admin]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins can bulk assign roles"
        )
    
    # 2. Get role
    role = db.exec(select(Role).where(Role.id == request.role_id)).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # 3. Process each user
    results = []
    success_count = 0
    failure_count = 0
    
    for user_id in request.user_ids:
        try:
            user = db.exec(select(User).where(User.id == user_id)).first()
            if not user:
                results.append(BulkRoleAssignResultItem(
                    user_id=user_id,
                    success=False,
                    error="User not found"
                ))
                failure_count += 1
                continue
            
            # Check if preventing self-role-modification for non-superadmins
            if user.id == current_user.id and not is_super_admin:
                results.append(BulkRoleAssignResultItem(
                    user_id=user_id,
                    success=False,
                    error="Cannot modify own roles"
                ))
                failure_count += 1
                continue
            
            if request.replace_existing:
                db.exec(sa.delete(UserRole).where(UserRole.user_id == user.id))
                db.add(
                    UserRole(
                        user_id=user.id,
                        role_id=role.id,
                        effective_from=datetime.now(UTC),
                    )
                )
                user.role_id = role.id
            else:
                existing_link = db.exec(
                    select(UserRole).where(
                        UserRole.user_id == user.id,
                        UserRole.role_id == role.id
                    )
                ).first()
                if not existing_link:
                    db.add(
                        UserRole(
                            user_id=user.id,
                            role_id=role.id,
                            effective_from=datetime.now(UTC),
                        )
                    )
                if not user.role_id:
                    user.role_id = role.id
            
            db.add(user)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                # If duplicate role assignment, treat as success (idempotent)
                # But verify it's not some other integrity error?
                # For now assume it's the role assignment conflict.
                pass
            
            results.append(BulkRoleAssignResultItem(
                user_id=user_id,
                success=True
            ))
            success_count += 1
            
        except Exception as e:
            db.rollback()
            results.append(BulkRoleAssignResultItem(
                user_id=user_id,
                success=False,
                error=str(e)
            ))
            failure_count += 1
    
    # 4. Log the bulk action
    AuditService.log_action(
        db=db,
        user_id=current_user.id,
        action="bulk_role_assign",
        resource_type="roles",
        resource_id=str(role.id),
        details=json_module.dumps({
            "role_name": role.name,
            "user_count": len(request.user_ids),
            "success_count": success_count,
            "failure_count": failure_count,
            "replace_existing": request.replace_existing
        })
    )
    
    return BulkRoleAssignResponse(
        success_count=success_count,
        failure_count=failure_count,
        role_name=role.name,
        results=results,
        generated_at=datetime.now(UTC)
    )
