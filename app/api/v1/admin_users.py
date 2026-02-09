"""
Admin User Analytics Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
from sqlalchemy import and_
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, ConfigDict

from app.api import deps
from app.db.session import get_session
from app.models.user import User
from app.models.rbac import Role, UserRole
from app.models.address import Address

router = APIRouter()


# Response Schemas
class RoleCount(BaseModel):
    role_name: str
    count: int


class KYCStats(BaseModel):
    pending: int
    verified: int
    rejected: int
    verification_rate: float  # percentage


class GrowthDataPoint(BaseModel):
    period: str  # e.g., "2024-01", "2024-02"
    new_users: int
    cumulative_total: int


class RegionDistribution(BaseModel):
    region: str
    count: int
    percentage: float


class UserStatisticsResponse(BaseModel):
    # Totals
    total_users: int
    active_users: int
    inactive_users: int
    deleted_users: int
    
    # By Role
    users_by_role: List[RoleCount]
    
    # KYC Metrics
    kyc_stats: KYCStats
    
    # Growth (last 12 months)
    growth_over_time: List[GrowthDataPoint]
    
    # Regional
    regional_distribution: List[RegionDistribution]
    
    # Timestamps
    generated_at: datetime


@router.get("/statistics", response_model=UserStatisticsResponse)
async def get_user_statistics(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Get overall user statistics (Admin only).
    
    Returns:
    - Total users (active, inactive, deleted)
    - Users by role
    - KYC verification rates
    - User growth over time (last 12 months)
    - Regional distribution
    """
    # 1. Authorization
    current_user_roles = [r.name for r in current_user.roles] if current_user.roles else []
    is_super_admin = "super_admin" in current_user_roles or current_user.is_superuser
    is_admin = "admin" in current_user_roles
    
    if not any([is_super_admin, is_admin]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins can access user statistics"
        )
    
    # 2. Total Users
    total_users = db.exec(select(func.count(User.id))).one()
    active_users = db.exec(select(func.count(User.id)).where(User.is_active == True, User.is_deleted == False)).one()
    inactive_users = db.exec(select(func.count(User.id)).where(User.is_active == False, User.is_deleted == False)).one()
    deleted_users = db.exec(select(func.count(User.id)).where(User.is_deleted == True)).one()
    
    # 3. Users by Role
    roles = db.exec(select(Role)).all()
    users_by_role = []
    for role in roles:
        count_query = (
            select(func.count(UserRole.user_id.distinct()))
            .where(UserRole.role_id == role.id)
        )
        count = db.exec(count_query).one()
        users_by_role.append(RoleCount(role_name=role.name, count=count))
    
    # Sort by count descending
    users_by_role.sort(key=lambda x: x.count, reverse=True)
    
    # 4. KYC Stats
    pending = db.exec(select(func.count(User.id)).where(User.kyc_status == "pending")).one()
    verified = db.exec(select(func.count(User.id)).where(User.kyc_status == "verified")).one()
    rejected = db.exec(select(func.count(User.id)).where(User.kyc_status == "rejected")).one()
    
    total_kyc_submitted = pending + verified + rejected
    verification_rate = (verified / total_kyc_submitted * 100) if total_kyc_submitted > 0 else 0.0
    
    kyc_stats = KYCStats(
        pending=pending,
        verified=verified,
        rejected=rejected,
        verification_rate=round(verification_rate, 2)
    )
    
    # 5. Growth Over Time (Last 12 months)
    growth_over_time = []
    now = datetime.utcnow()
    cumulative = 0
    
    for i in range(11, -1, -1):
        # Calculate month start/end
        month_date = now - timedelta(days=i * 30)
        month_start = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_date.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1)
        
        new_users = db.exec(
            select(func.count(User.id)).where(
                User.created_at >= month_start,
                User.created_at < month_end
            )
        ).one()
        
        cumulative += new_users
        
        growth_over_time.append(GrowthDataPoint(
            period=month_start.strftime("%Y-%m"),
            new_users=new_users,
            cumulative_total=cumulative
        ))
    
    # 6. Regional Distribution
    # Get states from Address table
    regional_distribution = []
    state_counts = db.exec(
        select(Address.state, func.count(Address.user_id.distinct()))
        .where(Address.state.isnot(None))
        .group_by(Address.state)
        .order_by(func.count(Address.user_id.distinct()).desc())
        .limit(10)
    ).all()
    
    total_with_address = sum(count for _, count in state_counts)
    
    for state, count in state_counts:
        pct = (count / total_with_address * 100) if total_with_address > 0 else 0
        regional_distribution.append(RegionDistribution(
            region=state or "Unknown",
            count=count,
            percentage=round(pct, 2)
        ))
    
    return UserStatisticsResponse(
        total_users=total_users,
        active_users=active_users,
        inactive_users=inactive_users,
        deleted_users=deleted_users,
        users_by_role=users_by_role,
        kyc_stats=kyc_stats,
        growth_over_time=growth_over_time,
        regional_distribution=regional_distribution,
        generated_at=datetime.utcnow()
    )
