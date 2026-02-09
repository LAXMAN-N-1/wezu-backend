from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
from app.api import deps
from app.models.rbac import Role, Permission, UserRole
from app.models.user import User
from app.db.session import get_session
from typing import List, Any, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta

router = APIRouter()


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
    db: Session = Depends(get_session),
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
    current_user_roles = [r.name for r in current_user.roles] if current_user.roles else []
    is_super_admin = "super_admin" in current_user_roles or current_user.is_superuser
    is_admin = "admin" in current_user_roles
    
    if not any([is_super_admin, is_admin]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins can access role distribution"
        )
    
    # 2. Get all roles
    roles = db.exec(select(Role)).all()
    
    # 3. Users per role
    users_per_role = []
    role_counts = {}
    
    for role in roles:
        count = db.exec(
            select(func.count(UserRole.user_id.distinct()))
            .where(UserRole.role_id == role.id)
        ).one()
        role_counts[role.id] = count
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
    month_ago = datetime.utcnow() - timedelta(days=30)
    
    role_growth_trends = []
    
    # For growth, we'll estimate based on user_role created_at if available
    # Otherwise, we'll show current counts with 0 growth
    for role in roles:
        current_count = role_counts[role.id]
        
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
        generated_at=datetime.utcnow()
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
    db: Session = Depends(get_session),
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
    current_user_roles = [r.name for r in current_user.roles] if current_user.roles else []
    is_super_admin = "super_admin" in current_user_roles or current_user.is_superuser
    is_admin = "admin" in current_user_roles
    
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
    permission_names = [p.name for p in permissions]
    
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
        "admin": [
            {"id": "admin_users", "label": "User Management", "path": "/admin/users", "icon": "users"},
            {"id": "admin_analytics", "label": "Analytics", "path": "/admin/analytics", "icon": "chart"},
            {"id": "admin_kyc", "label": "KYC Queue", "path": "/admin/kyc", "icon": "id-card"},
        ],
        "customer": [
            {"id": "rentals", "label": "My Rentals", "path": "/rentals", "icon": "battery"},
            {"id": "wallet", "label": "Wallet", "path": "/wallet", "icon": "wallet"},
            {"id": "history", "label": "History", "path": "/history", "icon": "clock"},
        ],
        "vendor_owner": [
            {"id": "stations", "label": "My Stations", "path": "/vendor/stations", "icon": "store"},
            {"id": "inventory", "label": "Inventory", "path": "/vendor/inventory", "icon": "box"},
            {"id": "earnings", "label": "Earnings", "path": "/vendor/earnings", "icon": "dollar"},
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
        {"id": "users_list", "name": "Users List", "required_perm": "users:read"},
        {"id": "users_edit", "name": "Edit User", "required_perm": "users:write"},
        {"id": "roles_manage", "name": "Role Management", "required_perm": "roles:admin"},
        {"id": "kyc_queue", "name": "KYC Queue", "required_perm": "kyc:review"},
        {"id": "analytics", "name": "Analytics Dashboard", "required_perm": "analytics:read"},
        {"id": "audit_logs", "name": "Audit Logs", "required_perm": "audit:read"},
        {"id": "rentals", "name": "Rentals", "required_perm": "rentals:read"},
        {"id": "wallet", "name": "Wallet", "required_perm": "wallet:read"},
    ]
    
    available_screens = []
    for screen in screen_definitions:
        accessible = screen["required_perm"] is None or screen["required_perm"] in permission_names
        actions = []
        if accessible:
            if "write" in (screen["required_perm"] or ""):
                actions = ["view", "edit", "create"]
            elif "admin" in (screen["required_perm"] or ""):
                actions = ["view", "edit", "create", "delete", "configure"]
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
        {"name": "Create User", "perm": "users:create", "resource": "users"},
        {"name": "Edit User", "perm": "users:write", "resource": "users"},
        {"name": "Delete User", "perm": "users:delete", "resource": "users"},
        {"name": "Approve KYC", "perm": "kyc:approve", "resource": "kyc"},
        {"name": "Reject KYC", "perm": "kyc:reject", "resource": "kyc"},
        {"name": "Manage Roles", "perm": "roles:admin", "resource": "roles"},
        {"name": "View Analytics", "perm": "analytics:read", "resource": "analytics"},
        {"name": "Export Data", "perm": "data:export", "resource": "data"},
        {"name": "Impersonate User", "perm": "users:impersonate", "resource": "users"},
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
    if "users:admin" in permission_names or is_super_admin:
        data_visibility.append(DataVisibility(data_type="User Data", visibility_level="full"))
    elif "users:read" in permission_names:
        data_visibility.append(DataVisibility(data_type="User Data", visibility_level="partial", filters=["own_data", "assigned_users"]))
    else:
        data_visibility.append(DataVisibility(data_type="User Data", visibility_level="none"))
    
    # Financial data
    if "finance:admin" in permission_names:
        data_visibility.append(DataVisibility(data_type="Financial Data", visibility_level="full"))
    elif "finance:read" in permission_names:
        data_visibility.append(DataVisibility(data_type="Financial Data", visibility_level="partial", filters=["own_transactions"]))
    else:
        data_visibility.append(DataVisibility(data_type="Financial Data", visibility_level="none"))
    
    # Analytics data
    if "analytics:admin" in permission_names:
        data_visibility.append(DataVisibility(data_type="Analytics", visibility_level="full"))
    elif "analytics:read" in permission_names:
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
        generated_at=datetime.utcnow()
    )
