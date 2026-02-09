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
