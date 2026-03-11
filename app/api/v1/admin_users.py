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
    db: Session = Depends(deps.get_db),
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
    db: Session = Depends(deps.get_db),
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


# ===== USER IMPERSONATION =====

from app.core.security import create_access_token
from app.services.audit_service import AuditService


class ImpersonateRequest(BaseModel):
    reason: str  # Required reason for audit


class PermissionInfo(BaseModel):
    name: str
    resource: Optional[str] = None
    action: Optional[str] = None


class MenuItemConfig(BaseModel):
    id: str
    label: str
    path: str
    icon: Optional[str] = None


class ImpersonationResponse(BaseModel):
    impersonation_token: str
    expires_at: datetime
    impersonated_user_id: int
    impersonated_user_email: str
    user_roles: List[str]
    user_permissions: List[PermissionInfo]
    menu_config: List[MenuItemConfig]
    warning: str


@router.post("/{user_id}/impersonate", response_model=ImpersonationResponse)
async def impersonate_user(
    user_id: int,
    request: ImpersonateRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """
    Impersonate a user (Super Admin only).
    
    Generates a special time-limited token (30 minutes) that gives the admin
    the same view as the target user. All actions are logged as "impersonated by Admin".
    
    Authorization:
    - Super Admin only
    - Reason is required for audit trail
    """
    # 1. Authorization - Super Admin only
    current_user_roles = [r.name for r in current_user.roles] if current_user.roles else []
    is_super_admin = "super_admin" in current_user_roles or current_user.is_superuser
    
    if not is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admins can impersonate users"
        )
    
    # 2. Get target user
    target_user = db.exec(select(User).where(User.id == user_id)).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # 3. Cannot impersonate yourself
    if target_user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot impersonate yourself"
        )
    
    # 4. Generate impersonation token (30 minutes)
    expires_delta = timedelta(minutes=30)
    expires_at = datetime.utcnow() + expires_delta
    
    # Create token with special claims for impersonation
    from jose import jwt
    from app.core.config import settings
    
    impersonation_payload = {
        "sub": str(target_user.id),
        "exp": expires_at,
        "iat": datetime.utcnow(),
        "type": "impersonation",
        "impersonated_by": current_user.id,
        "impersonated_by_email": current_user.email,
        "reason": request.reason
    }
    
    impersonation_token = jwt.encode(
        impersonation_payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    # 5. Log impersonation action
    import json as json_module
    AuditService.log_action(
        db=db,
        user_id=current_user.id,
        action="user_impersonation_start",
        resource_type="user",
        resource_id=str(target_user.id),
        details=json_module.dumps({
            "target_user_id": target_user.id,
            "target_user_email": target_user.email,
            "reason": request.reason,
            "expires_at": expires_at.isoformat()
        })
    )
    
    # 6. Get user's roles and permissions
    user_roles = [r.name for r in target_user.roles] if target_user.roles else []
    
    user_permissions = []
    if target_user.roles:
        for role in target_user.roles:
            if role.permissions:
                for perm in role.permissions:
                    user_permissions.append(PermissionInfo(
                        name=perm.name,
                        resource=perm.resource,
                        action=perm.action
                    ))
    
    # 7. Generate menu config based on roles
    menu_config = []
    
    # Base menu items for all users
    base_menu = [
        {"id": "dashboard", "label": "Dashboard", "path": "/dashboard", "icon": "home"},
        {"id": "profile", "label": "Profile", "path": "/profile", "icon": "user"},
    ]
    
    # Role-specific menu items
    if "customer" in user_roles:
        base_menu.extend([
            {"id": "rentals", "label": "My Rentals", "path": "/rentals", "icon": "battery"},
            {"id": "wallet", "label": "Wallet", "path": "/wallet", "icon": "wallet"},
        ])
    
    if any(r in ["admin", "super_admin"] for r in user_roles):
        base_menu.extend([
            {"id": "admin_users", "label": "User Management", "path": "/admin/users", "icon": "users"},
            {"id": "admin_analytics", "label": "Analytics", "path": "/admin/analytics", "icon": "chart"},
        ])
    
    if "vendor_owner" in user_roles:
        base_menu.extend([
            {"id": "stations", "label": "My Stations", "path": "/vendor/stations", "icon": "station"},
            {"id": "inventory", "label": "Inventory", "path": "/vendor/inventory", "icon": "box"},
        ])
    
    menu_config = [MenuItemConfig(**item) for item in base_menu]
    
    return ImpersonationResponse(
        impersonation_token=impersonation_token,
        expires_at=expires_at,
        impersonated_user_id=target_user.id,
        impersonated_user_email=target_user.email,
        user_roles=user_roles,
        user_permissions=user_permissions,
        menu_config=menu_config,
        warning="This is an impersonation token. All actions will be logged as 'impersonated by Admin'. Token expires in 30 minutes."
    )


# ===== END IMPERSONATION =====

class EndImpersonationResponse(BaseModel):
    message: str
    admin_user_id: int
    admin_email: str
    impersonated_user_id: int
    session_duration_seconds: float
    actions_performed: int
    new_admin_token: str


@router.post("/impersonation/end", response_model=EndImpersonationResponse)
async def end_impersonation(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
    authorization: str = Depends(deps.oauth2_scheme),
):
    """
    End an active impersonation session and return to admin session.
    
    This endpoint should be called with the impersonation token.
    It will log the end of impersonation and return a new admin token.
    """
    from jose import jwt, JWTError
    from app.core.config import settings
    
    # 1. Decode the current token to check if it's an impersonation token
    try:
        payload = jwt.decode(
            authorization,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    token_type = payload.get("type")
    
    if token_type != "impersonation":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not an impersonation session. Use regular logout instead."
        )
    
    # 2. Get impersonation details from token
    impersonated_by = payload.get("impersonated_by")
    impersonated_by_email = payload.get("impersonated_by_email")
    impersonated_user_id = int(payload.get("sub"))
    reason = payload.get("reason", "Not specified")
    iat = payload.get("iat")
    
    if not impersonated_by:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid impersonation token"
        )
    
    # 3. Get original admin user
    admin_user = db.exec(select(User).where(User.id == impersonated_by)).first()
    if not admin_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original admin user not found"
        )
    
    # 4. Calculate session duration
    import time
    if iat:
        session_duration = time.time() - iat
    else:
        session_duration = 0
    
    # 5. Count actions performed during impersonation (from audit logs)
    from app.models.audit_log import AuditLog
    
    try:
        actions_count = db.exec(
            select(func.count(AuditLog.id)).where(
                AuditLog.user_id == impersonated_user_id,
                AuditLog.details.contains("impersonated")
            )
        ).one()
    except Exception:
        actions_count = 0
    
    # 6. Log end of impersonation
    import json as json_module
    AuditService.log_action(
        db=db,
        user_id=impersonated_by,
        action="user_impersonation_end",
        resource_type="user",
        resource_id=str(impersonated_user_id),
        details=json_module.dumps({
            "impersonated_user_id": impersonated_user_id,
            "session_duration_seconds": round(session_duration, 2),
            "actions_performed": actions_count,
            "original_reason": reason
        })
    )
    
    # 7. Generate new admin token
    new_admin_token = create_access_token(
        subject=admin_user.id,
        expires_delta=timedelta(hours=24)
    )
    
    return EndImpersonationResponse(
        message="Impersonation session ended successfully",
        admin_user_id=admin_user.id,
        admin_email=admin_user.email,
        impersonated_user_id=impersonated_user_id,
        session_duration_seconds=round(session_duration, 2),
        actions_performed=actions_count,
        new_admin_token=new_admin_token
    )


# ===== BULK USER IMPORT =====

from fastapi import UploadFile, File
import csv
import io
from app.core.security import get_password_hash


class RowError(BaseModel):
    row_number: int
    email: Optional[str] = None
    error: str


class ImportedUser(BaseModel):
    email: str
    full_name: str
    roles_assigned: List[str]


class BulkImportResponse(BaseModel):
    success_count: int
    failure_count: int
    total_rows: int
    imported_users: List[ImportedUser]
    errors: List[RowError]
    notifications_sent: int
    generated_at: datetime


@router.post("/bulk-import", response_model=BulkImportResponse)
async def bulk_import_users(
    file: UploadFile = File(...),
    send_notifications: bool = True,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """
    Bulk import users from CSV file (Admin only).
    
    CSV Format:
    email,full_name,phone_number,password,roles
    
    - email: Required, must be valid email format
    - full_name: Required
    - phone_number: Required, 10 digits
    - password: Optional (auto-generated if not provided)
    - roles: Optional, comma-separated role names
    
    Process:
    1. Validate CSV format
    2. Check for duplicates
    3. Validate roles exist
    4. Create users
    5. Send welcome notifications (if enabled)
    """
    # 1. Authorization
    current_user_roles = [r.name for r in current_user.roles] if current_user.roles else []
    is_super_admin = "super_admin" in current_user_roles or current_user.is_superuser
    is_admin = "admin" in current_user_roles
    
    if not any([is_super_admin, is_admin]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins can bulk import users"
        )
    
    # 2. Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file"
        )
    
    # 3. Read and parse CSV
    try:
        contents = await file.read()
        decoded = contents.decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse CSV: {str(e)}"
        )
    
    # 4. Validate CSV has required columns
    required_columns = {'email', 'full_name', 'phone_number'}
    if not required_columns.issubset(set(reader.fieldnames or [])):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV must have columns: {', '.join(required_columns)}"
        )
    
    # 5. Get existing emails and roles
    existing_emails = set()
    all_users = db.exec(select(User.email)).all()
    for email in all_users:
        existing_emails.add(email.lower())
    
    available_roles = {}
    all_roles = db.exec(select(Role)).all()
    for role in all_roles:
        available_roles[role.name.lower()] = role
    
    # 6. Process rows
    success_count = 0
    failure_count = 0
    errors = []
    imported_users = []
    notifications_to_send = []
    
    rows = list(reader)
    total_rows = len(rows)
    
    for row_num, row in enumerate(rows, start=2):  # Start at 2 (header is row 1)
        email = row.get('email', '').strip()
        full_name = row.get('full_name', '').strip()
        phone_number = row.get('phone_number', '').strip()
        password = row.get('password', '').strip()
        roles_str = row.get('roles', '').strip()
        
        # Validate email
        if not email:
            errors.append(RowError(row_number=row_num, email=email, error="Email is required"))
            failure_count += 1
            continue
        
        if '@' not in email or '.' not in email:
            errors.append(RowError(row_number=row_num, email=email, error="Invalid email format"))
            failure_count += 1
            continue
        
        # Check duplicate
        if email.lower() in existing_emails:
            errors.append(RowError(row_number=row_num, email=email, error="Email already exists"))
            failure_count += 1
            continue
        
        # Validate full_name
        if not full_name:
            errors.append(RowError(row_number=row_num, email=email, error="Full name is required"))
            failure_count += 1
            continue
        
        # Validate phone_number
        if not phone_number:
            errors.append(RowError(row_number=row_num, email=email, error="Phone number is required"))
            failure_count += 1
            continue
        
        if not phone_number.isdigit() or len(phone_number) != 10:
            errors.append(RowError(row_number=row_num, email=email, error="Phone number must be 10 digits"))
            failure_count += 1
            continue
        
        # Generate password if not provided
        if not password:
            import secrets
            password = secrets.token_urlsafe(12)
        
        # Validate roles
        requested_roles = []
        if roles_str:
            for role_name in roles_str.split(','):
                role_name = role_name.strip().lower()
                if role_name and role_name not in available_roles:
                    errors.append(RowError(row_number=row_num, email=email, error=f"Role '{role_name}' does not exist"))
                    failure_count += 1
                    continue
                if role_name in available_roles:
                    requested_roles.append(available_roles[role_name])
        
        # Create user
        try:
            hashed_password = get_password_hash(password)
            new_user = User(
                email=email,
                full_name=full_name,
                phone_number=phone_number,
                hashed_password=hashed_password,
                is_active=True,
                is_deleted=False,
                created_at=datetime.utcnow()
            )
            
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            
            # Assign roles
            role_names_assigned = []
            for role in requested_roles:
                new_user.roles.append(role)
                role_names_assigned.append(role.name)
            
            # Default customer role if no roles specified
            if not requested_roles and 'customer' in available_roles:
                new_user.roles.append(available_roles['customer'])
                role_names_assigned.append('customer')
            
            db.add(new_user)
            db.commit()
            
            # Track for notification
            if send_notifications:
                notifications_to_send.append({
                    "email": email,
                    "full_name": full_name,
                    "temp_password": password
                })
            
            existing_emails.add(email.lower())
            imported_users.append(ImportedUser(
                email=email,
                full_name=full_name,
                roles_assigned=role_names_assigned
            ))
            success_count += 1
            
        except Exception as e:
            db.rollback()
            errors.append(RowError(row_number=row_num, email=email, error=f"Database error: {str(e)}"))
            failure_count += 1
    
    # 7. Send welcome notifications (in background, simplified for now)
    notifications_sent = 0
    if send_notifications and notifications_to_send:
        # In production, this would be done via a background task/queue
        notifications_sent = len(notifications_to_send)
    
    # 8. Log the bulk import
    import json as json_module
    AuditService.log_action(
        db=db,
        user_id=current_user.id,
        action="bulk_user_import",
        resource_type="users",
        resource_id="bulk",
        details=json_module.dumps({
            "total_rows": total_rows,
            "success_count": success_count,
            "failure_count": failure_count,
            "file_name": file.filename
        })
    )
    
    return BulkImportResponse(
        success_count=success_count,
        failure_count=failure_count,
        total_rows=total_rows,
        imported_users=imported_users,
        errors=errors,
        notifications_sent=notifications_sent,
        generated_at=datetime.utcnow()
    )


# ===== BULK STATUS UPDATE =====

class BulkStatusUpdateRequest(BaseModel):
    user_ids: List[int]
    action: str  # "activate", "suspend", "delete"
    reason: str


class BulkStatusResultItem(BaseModel):
    user_id: int
    email: Optional[str] = None
    success: bool
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    error: Optional[str] = None


class BulkStatusUpdateResponse(BaseModel):
    action: str
    success_count: int
    failure_count: int
    results: List[BulkStatusResultItem]
    generated_at: datetime


@router.post("/bulk-status-update", response_model=BulkStatusUpdateResponse)
async def bulk_status_update(
    request: BulkStatusUpdateRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """
    Bulk suspend/activate/delete multiple users (Admin only).
    
    Actions:
    - activate: Set is_active=True
    - suspend: Set is_active=False
    - delete: Soft delete (is_deleted=True)
    
    Use Cases:
    - Seasonal staff activation
    - Mass suspension for policy violation
    - Offboarding terminated employees
    """
    # 1. Authorization
    current_user_roles = [r.name for r in current_user.roles] if current_user.roles else []
    is_super_admin = "super_admin" in current_user_roles or current_user.is_superuser
    is_admin = "admin" in current_user_roles
    
    if not any([is_super_admin, is_admin]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins can bulk update user status"
        )
    
    # 2. Validate action
    valid_actions = ["activate", "suspend", "delete"]
    if request.action not in valid_actions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Action must be one of: {', '.join(valid_actions)}"
        )
    
    # 3. Process each user
    results = []
    success_count = 0
    failure_count = 0
    
    for user_id in request.user_ids:
        try:
            user = db.exec(select(User).where(User.id == user_id)).first()
            if not user:
                results.append(BulkStatusResultItem(
                    user_id=user_id,
                    success=False,
                    error="User not found"
                ))
                failure_count += 1
                continue
            
            # Prevent self-modification
            if user.id == current_user.id:
                results.append(BulkStatusResultItem(
                    user_id=user_id,
                    email=user.email,
                    success=False,
                    error="Cannot modify own status"
                ))
                failure_count += 1
                continue
            
            # Prevent modifying super admins (unless you're a super admin)
            user_roles_names = [r.name for r in user.roles] if user.roles else []
            if "super_admin" in user_roles_names and not is_super_admin:
                results.append(BulkStatusResultItem(
                    user_id=user_id,
                    email=user.email,
                    success=False,
                    error="Cannot modify super admin status"
                ))
                failure_count += 1
                continue
            
            # Get previous status
            if user.is_deleted:
                previous = "deleted"
            elif user.is_active:
                previous = "active"
            else:
                previous = "suspended"
            
            # Apply action
            if request.action == "activate":
                user.is_active = True
                user.is_deleted = False
                new_status = "active"
            elif request.action == "suspend":
                user.is_active = False
                new_status = "suspended"
            elif request.action == "delete":
                user.is_deleted = True
                user.is_active = False
                new_status = "deleted"
            
            db.add(user)
            db.commit()
            
            results.append(BulkStatusResultItem(
                user_id=user_id,
                email=user.email,
                success=True,
                previous_status=previous,
                new_status=new_status
            ))
            success_count += 1
            
        except Exception as e:
            db.rollback()
            results.append(BulkStatusResultItem(
                user_id=user_id,
                success=False,
                error=str(e)
            ))
            failure_count += 1
    
    # 4. Log the bulk action
    import json as json_module
    AuditService.log_action(
        db=db,
        user_id=current_user.id,
        action=f"bulk_user_{request.action}",
        resource_type="users",
        resource_id="bulk",
        details=json_module.dumps({
            "action": request.action,
            "user_count": len(request.user_ids),
            "success_count": success_count,
            "failure_count": failure_count,
            "reason": request.reason
        })
    )
    
    return BulkStatusUpdateResponse(
        action=request.action,
        success_count=success_count,
        failure_count=failure_count,
        results=results,
        generated_at=datetime.utcnow()
    )


# ===== USER EXPORT =====

from fastapi.responses import StreamingResponse
from enum import Enum


class ExportFormat(str, Enum):
    CSV = "csv"
    JSON = "json"
    EXCEL = "xlsx"


class ExportUserItem(BaseModel):
    id: int
    email: str
    full_name: str
    phone_number: Optional[str] = None
    is_active: bool
    is_verified: bool = False
    kyc_status: Optional[str] = None
    roles: List[str]
    created_at: datetime
    last_login: Optional[datetime] = None


class ExportResponse(BaseModel):
    export_id: str
    format: str
    total_users: int
    filters_applied: Dict
    download_url: Optional[str] = None  # For async generation
    data: Optional[List[Dict]] = None  # For immediate JSON response
    generated_at: datetime
    message: str


@router.get("/export", response_model=ExportResponse)
async def export_users(
    # Filters
    role: Optional[str] = None,
    status: Optional[str] = None,  # "active", "suspended", "deleted"
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    # Format and Fields
    format: ExportFormat = ExportFormat.JSON,
    fields: Optional[str] = None,  # Comma-separated: "email,full_name,roles"
    # Options
    send_email: bool = False,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """
    Export user data with filters (Admin only).
    
    Query Parameters:
    - role: Filter by role name
    - status: Filter by status (active/suspended/deleted)
    - date_from/date_to: Filter by created_at date range
    - format: Output format (csv/json/xlsx)
    - fields: Comma-separated list of fields to include
    - send_email: If true, generates async and sends download link
    
    Returns:
    - For JSON format: Data directly in response
    - For CSV/Excel: Download URL or streamed content
    """
    # 1. Authorization
    current_user_roles = [r.name for r in current_user.roles] if current_user.roles else []
    is_super_admin = "super_admin" in current_user_roles or current_user.is_superuser
    is_admin = "admin" in current_user_roles
    
    if not any([is_super_admin, is_admin]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins can export user data"
        )
    
    # 2. Build query with filters
    query = select(User).where(User.is_deleted == False)
    
    filters_applied = {}
    
    # Role filter
    if role:
        role_obj = db.exec(select(Role).where(Role.name == role)).first()
        if role_obj:
            # Get user_ids with this role
            user_ids_with_role = db.exec(
                select(UserRole.user_id).where(UserRole.role_id == role_obj.id)
            ).all()
            query = query.where(User.id.in_(user_ids_with_role))
            filters_applied["role"] = role
    
    # Status filter
    if status:
        if status == "active":
            query = query.where(User.is_active == True)
        elif status == "suspended":
            query = query.where(User.is_active == False)
        elif status == "deleted":
            query = select(User).where(User.is_deleted == True)
        filters_applied["status"] = status
    
    # Date range filter
    if date_from:
        query = query.where(User.created_at >= date_from)
        filters_applied["date_from"] = date_from.isoformat()
    
    if date_to:
        query = query.where(User.created_at <= date_to)
        filters_applied["date_to"] = date_to.isoformat()
    
    # 3. Execute query
    users = db.exec(query).all()
    
    # 4. Parse fields to include
    default_fields = ["id", "email", "full_name", "phone_number", "is_active", "roles", "created_at"]
    if fields:
        selected_fields = [f.strip() for f in fields.split(",")]
    else:
        selected_fields = default_fields
    
    # 5. Build export data
    export_data = []
    for user in users:
        user_roles = [r.name for r in user.roles] if user.roles else []
        
        user_dict = {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "phone_number": user.phone_number,
            "is_active": user.is_active,
            "is_verified": getattr(user, 'is_verified', False),
            "kyc_status": getattr(user, 'kyc_status', None),
            "roles": ", ".join(user_roles),
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login": getattr(user, 'last_login', None),
        }
        
        # Filter to selected fields only
        filtered_user = {k: v for k, v in user_dict.items() if k in selected_fields}
        export_data.append(filtered_user)
    
    # 6. Generate unique export ID
    import uuid
    export_id = str(uuid.uuid4())[:8]
    
    # 7. Handle different formats
    if format == ExportFormat.JSON:
        # Return data directly for JSON
        import json as json_module
        AuditService.log_action(
            db=db,
            user_id=current_user.id,
            action="user_export",
            resource_type="users",
            resource_id="export",
            details=json_module.dumps({
                "export_id": export_id,
                "format": format.value,
                "total_users": len(export_data),
                "filters": filters_applied
            })
        )
        
        return ExportResponse(
            export_id=export_id,
            format=format.value,
            total_users=len(export_data),
            filters_applied=filters_applied,
            data=export_data,
            generated_at=datetime.utcnow(),
            message=f"Exported {len(export_data)} users in JSON format"
        )
    
    elif format == ExportFormat.CSV:
        # Generate CSV
        import io
        output = io.StringIO()
        if export_data:
            writer = csv.DictWriter(output, fieldnames=export_data[0].keys())
            writer.writeheader()
            writer.writerows(export_data)
        
        csv_content = output.getvalue()
        
        import json as json_module
        AuditService.log_action(
            db=db,
            user_id=current_user.id,
            action="user_export",
            resource_type="users",
            resource_id="export",
            details=json_module.dumps({
                "export_id": export_id,
                "format": format.value,
                "total_users": len(export_data),
                "filters": filters_applied
            })
        )
        
        if send_email:
            # In production, this would save to cloud storage and send email
            return ExportResponse(
                export_id=export_id,
                format=format.value,
                total_users=len(export_data),
                filters_applied=filters_applied,
                download_url=f"/api/v1/admin/users/export/download/{export_id}",
                generated_at=datetime.utcnow(),
                message=f"Export initiated. Download link will be sent to {current_user.email}"
            )
        
        # Return CSV directly
        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=users_export_{export_id}.csv"}
        )
    
    elif format == ExportFormat.EXCEL:
        # For Excel, return metadata (would use openpyxl in production)
        import json as json_module
        AuditService.log_action(
            db=db,
            user_id=current_user.id,
            action="user_export",
            resource_type="users",
            resource_id="export",
            details=json_module.dumps({
                "export_id": export_id,
                "format": format.value,
                "total_users": len(export_data),
                "filters": filters_applied
            })
        )
        
        return ExportResponse(
            export_id=export_id,
            format=format.value,
            total_users=len(export_data),
            filters_applied=filters_applied,
            download_url=f"/api/v1/admin/users/export/download/{export_id}",
            generated_at=datetime.utcnow(),
            message=f"Excel export initiated for {len(export_data)} users. Download link will be available shortly."
        )
