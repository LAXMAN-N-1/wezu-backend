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


# ===== ENGAGEMENT METRICS =====

class LoginFrequency(BaseModel):
    daily_avg: float
    weekly_avg: float
    monthly_avg: float


class FeatureUsage(BaseModel):
    feature_name: str
    usage_count: int
    unique_users: int
    percentage_of_users: float


class UserEngagementResponse(BaseModel):
    # Active users
    daily_active_users: int
    weekly_active_users: int
    monthly_active_users: int
    
    # DAU/MAU ratio (stickiness)
    stickiness_ratio: float
    
    # Login frequency
    login_frequency: LoginFrequency
    
    # Feature usage (top features)
    feature_usage: List[FeatureUsage]
    
    # Churn metrics
    churn_rate_30d: float  # percentage of users who became inactive in last 30 days
    churned_users_count: int
    
    # Retention
    retention_rate_7d: float
    retention_rate_30d: float
    
    # Timestamps
    generated_at: datetime


@router.get("/engagement", response_model=UserEngagementResponse)
async def get_user_engagement(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """
    Get user engagement metrics (Admin only).
    
    Returns:
    - Daily/Weekly/Monthly Active Users
    - Login frequency statistics
    - Feature usage breakdown
    - Churn and retention rates
    """
    # 1. Authorization
    current_user_roles = [r.name for r in current_user.roles] if current_user.roles else []
    is_super_admin = "super_admin" in current_user_roles or current_user.is_superuser
    is_admin = "admin" in current_user_roles
    
    if not any([is_super_admin, is_admin]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins can access engagement metrics"
        )
    
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    # 2. Active Users (based on last_login)
    daily_active = db.exec(
        select(func.count(User.id)).where(
            User.last_login >= day_ago,
            User.is_active == True
        )
    ).one()
    
    weekly_active = db.exec(
        select(func.count(User.id)).where(
            User.last_login >= week_ago,
            User.is_active == True
        )
    ).one()
    
    monthly_active = db.exec(
        select(func.count(User.id)).where(
            User.last_login >= month_ago,
            User.is_active == True
        )
    ).one()
    
    # Stickiness = DAU / MAU
    stickiness = (daily_active / monthly_active) if monthly_active > 0 else 0.0
    
    # 3. Login Frequency
    # Get total logins from audit logs if available, otherwise estimate from last_login
    total_active = db.exec(select(func.count(User.id)).where(User.is_active == True)).one()
    
    # Using heuristics based on last_login distribution
    login_frequency = LoginFrequency(
        daily_avg=round(daily_active / max(total_active, 1), 2),
        weekly_avg=round(weekly_active / max(total_active, 1), 2),
        monthly_avg=round(monthly_active / max(total_active, 1), 2)
    )
    
    # 4. Feature Usage (from audit logs or predefined features)
    # For now, using common features based on endpoint patterns
    from app.models.audit_log import AuditLog
    
    feature_usage = []
    
    # Define key features to track
    features = [
        ("Wallet Top-up", "wallet_topup"),
        ("Battery Rental", "rental_create"),
        ("Battery Swap", "swap_initiate"),
        ("KYC Submission", "kyc_submit"),
        ("Profile Update", "profile_update"),
    ]
    
    for feature_name, action_pattern in features:
        try:
            usage_count = db.exec(
                select(func.count(AuditLog.id)).where(
                    AuditLog.action.contains(action_pattern),
                    AuditLog.timestamp >= month_ago
                )
            ).one()
            
            unique_users_count = db.exec(
                select(func.count(AuditLog.user_id.distinct())).where(
                    AuditLog.action.contains(action_pattern),
                    AuditLog.timestamp >= month_ago
                )
            ).one()
            
            pct = (unique_users_count / total_active * 100) if total_active > 0 else 0
            
            feature_usage.append(FeatureUsage(
                feature_name=feature_name,
                usage_count=usage_count,
                unique_users=unique_users_count,
                percentage_of_users=round(pct, 2)
            ))
        except Exception:
            # If audit logs don't have this action, add zero
            feature_usage.append(FeatureUsage(
                feature_name=feature_name,
                usage_count=0,
                unique_users=0,
                percentage_of_users=0.0
            ))
    
    # Sort by usage
    feature_usage.sort(key=lambda x: x.usage_count, reverse=True)
    
    # 5. Churn Rate
    # Users who were active before 30 days but haven't logged in since
    two_months_ago = now - timedelta(days=60)
    
    # Users who logged in between 60-30 days ago
    previously_active = db.exec(
        select(func.count(User.id)).where(
            User.last_login >= two_months_ago,
            User.last_login < month_ago,
            User.is_active == True
        )
    ).one()
    
    # Users who haven't logged in for 30+ days
    churned = db.exec(
        select(func.count(User.id)).where(
            User.last_login < month_ago,
            User.is_active == True
        )
    ).one()
    
    churn_rate = (churned / previously_active * 100) if previously_active > 0 else 0.0
    
    # 6. Retention Rates
    # 7-day retention: users who signed up 7+ days ago and logged in within last 7 days
    seven_days_ago_signups = db.exec(
        select(func.count(User.id)).where(
            User.created_at <= week_ago,
            User.created_at >= (week_ago - timedelta(days=7))
        )
    ).one()
    
    retained_7d = db.exec(
        select(func.count(User.id)).where(
            User.created_at <= week_ago,
            User.created_at >= (week_ago - timedelta(days=7)),
            User.last_login >= week_ago
        )
    ).one()
    
    retention_7d = (retained_7d / seven_days_ago_signups * 100) if seven_days_ago_signups > 0 else 0.0
    
    # 30-day retention
    thirty_days_ago_signups = db.exec(
        select(func.count(User.id)).where(
            User.created_at <= month_ago,
            User.created_at >= (month_ago - timedelta(days=30))
        )
    ).one()
    
    retained_30d = db.exec(
        select(func.count(User.id)).where(
            User.created_at <= month_ago,
            User.created_at >= (month_ago - timedelta(days=30)),
            User.last_login >= month_ago
        )
    ).one()
    
    retention_30d = (retained_30d / thirty_days_ago_signups * 100) if thirty_days_ago_signups > 0 else 0.0
    
    return UserEngagementResponse(
        daily_active_users=daily_active,
        weekly_active_users=weekly_active,
        monthly_active_users=monthly_active,
        stickiness_ratio=round(stickiness, 4),
        login_frequency=login_frequency,
        feature_usage=feature_usage,
        churn_rate_30d=round(churn_rate, 2),
        churned_users_count=churned,
        retention_rate_7d=round(retention_7d, 2),
        retention_rate_30d=round(retention_30d, 2),
        generated_at=datetime.utcnow()
    )
