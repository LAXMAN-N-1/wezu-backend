"""
Dealer Portal — User Management API
Full CRUD for dealer staff users, invite flow, sessions, password management.
"""
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session, select, func, or_
from datetime import datetime, UTC, timedelta
import secrets
import logging

from app.db.session import get_session
from app.api import deps
from app.models.user import User, UserStatus, UserType
from app.models.dealer import DealerProfile
from app.models.rbac import Role
from app.models.session import UserSession
from app.models.audit_log import AuditLog, AuditActionType
from app.core.security import get_password_hash, verify_password
from app.schemas.dealer_user import (
    DealerUserCreate, DealerUserUpdate, DealerUserRead,
    DealerUserDetail, DealerUserStatusUpdate, DealerUserPasswordReset,
    EmailCheckRequest, EmailCheckResponse, UserStats, SessionRead,
    LoginHistoryEntry, BulkActionRequest, BulkActionType, CredentialMode,
)
from app.services.email_service import EmailService
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger("dealer_portal_users")

INVITE_TOKEN_EXPIRY_HOURS = 72


# ── Helpers ──────────────────────────────────────────────

def _get_dealer(db: Session, user_id: int) -> DealerProfile:
    dealer = db.exec(select(DealerProfile).where(DealerProfile.user_id == user_id)).first()
    if not dealer:
        raise HTTPException(status_code=403, detail="Not a dealer account")
    return dealer


def _user_to_read(user: User, db: Session) -> DealerUserRead:
    """Convert User model to DealerUserRead schema."""
    role_name = role_icon = role_color = None
    if user.role_id:
        role = db.get(Role, user.role_id)
        if role:
            role_name = role.name
            role_icon = role.icon
            role_color = role.color

    creator_name = None
    if user.created_by_user_id:
        creator = db.get(User, user.created_by_user_id)
        if creator:
            creator_name = creator.full_name

    return DealerUserRead(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone_number=user.phone_number,
        department=user.department,
        profile_picture=user.profile_picture,
        status=user.status.value if hasattr(user.status, 'value') else str(user.status),
        role_id=user.role_id,
        role_name=role_name,
        role_icon=role_icon,
        role_color=role_color,
        last_login=user.last_login,
        created_at=user.created_at,
        created_by=creator_name,
    )


def _generate_invite_token() -> str:
    return secrets.token_urlsafe(48)


def _audit(db: Session, user_id: int, dealer_id: int, action: str,
           target_id: int = None, details: str = "", old_value=None, new_value=None):
    db.add(AuditLog(
        user_id=user_id,
        action=action,
        resource_type="DEALER_USER",
        target_id=target_id,
        details=details,
        old_value=old_value,
        new_value=new_value,
    ))


# ── Stats ────────────────────────────────────────────────

@router.get("/stats", response_model=UserStats)
def get_user_stats(
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    """Summary metrics: total, active, pending, inactive users under this dealer."""
    dealer = _get_dealer(db, current_user.id)

    base = select(func.count(User.id)).where(
        User.created_by_dealer_id == dealer.id,
        User.is_deleted == False,
    )

    total = db.exec(base).one() or 0
    active = db.exec(base.where(User.status == UserStatus.ACTIVE)).one() or 0
    pending = db.exec(base.where(User.status == UserStatus.PENDING)).one() or 0
    inactive = db.exec(base.where(User.status == UserStatus.INACTIVE)).one() or 0

    return UserStats(total=total, active=active, pending=pending, inactive=inactive)


# ── List Users ───────────────────────────────────────────

@router.get("", response_model=List[DealerUserRead])
def list_dealer_users(
    search: Optional[str] = None,
    role_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    """List all users under the current dealer, with optional filters."""
    dealer = _get_dealer(db, current_user.id)

    stmt = select(User).where(
        User.created_by_dealer_id == dealer.id,
        User.is_deleted == False,
    )

    if search:
        stmt = stmt.where(
            or_(
                User.full_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
            )
        )

    if role_id:
        stmt = stmt.where(User.role_id == role_id)

    if status_filter and status_filter != "all":
        stmt = stmt.where(User.status == status_filter)

    stmt = stmt.order_by(User.created_at.desc())
    users = db.exec(stmt).all()

    # Also include the dealer owner themselves
    owner_list = [_user_to_read(u, db) for u in users]

    return owner_list


# ── Create User ──────────────────────────────────────────

@router.post("", response_model=DealerUserRead, status_code=status.HTTP_201_CREATED)
def create_dealer_user(
    data: DealerUserCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    """Create a new user under this dealer with credentials (invite or manual)."""
    dealer = _get_dealer(db, current_user.id)

    # Check email uniqueness within this dealer
    existing = db.exec(
        select(User).where(
            User.email == data.email,
            User.created_by_dealer_id == dealer.id,
            User.is_deleted == False,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists for this dealer")

    # Validate role belongs to this dealer
    role = db.get(Role, data.role_id)
    if not role or (role.dealer_id and role.dealer_id != dealer.id):
        raise HTTPException(status_code=400, detail="Invalid role")

    # Build user record
    user = User(
        email=data.email,
        full_name=data.full_name,
        phone_number=data.phone_number,
        user_type=UserType.DEALER_STAFF,
        role_id=data.role_id,
        created_by_dealer_id=dealer.id,
        created_by_user_id=current_user.id,
        department=data.department,
        notes_internal=data.notes,
    )

    if data.credential_mode == CredentialMode.INVITE:
        # Generate invite token
        token = _generate_invite_token()
        user.invite_token = token
        user.invite_token_expires = datetime.now(UTC) + timedelta(hours=INVITE_TOKEN_EXPIRY_HOURS)
        user.invite_sent_at = datetime.now(UTC)
        user.status = UserStatus.PENDING

        # Send actual email with invite link containing token
        base_url = settings.ADMIN_FRONTEND_ORIGIN or "https://admin.powerfrill.com"
        invite_link = f"{base_url}/activate/{token}"
        
        email_content = f"""
            <h3>Welcome to Wezu Dealer Portal</h3>
            <p>You have been invited to join the dealer team. Click the link below to activate your account and set your password:</p>
            <p><a href="{invite_link}">{invite_link}</a></p>
            <p>This link expires in {INVITE_TOKEN_EXPIRY_HOURS} hours.</p>
        """
        EmailService.send_email(
            to_email=data.email,
            subject="Invitation to join Wezu Dealer Portal",
            content=email_content
        )
        
        logger.info(f"[INVITE] Sent activation email to {data.email}")

    elif data.credential_mode == CredentialMode.MANUAL:
        if not data.password:
            raise HTTPException(status_code=400, detail="Password required for manual mode")
        user.hashed_password = get_password_hash(data.password)
        user.force_password_change = data.force_password_change
        user.status = UserStatus.ACTIVE if data.initial_status == "active" else UserStatus.INACTIVE

    db.add(user)
    db.commit()
    db.refresh(user)

    # Audit log
    _audit(db, current_user.id, dealer.id, AuditActionType.USER_CREATION,
           target_id=user.id, details=f"Created user {data.email} with mode={data.credential_mode.value}",
           new_value={"email": data.email, "role_id": data.role_id, "mode": data.credential_mode.value})
    db.commit()

    return _user_to_read(user, db)


# ── Check Email ──────────────────────────────────────────

@router.post("/check-email", response_model=EmailCheckResponse)
def check_email_availability(
    data: EmailCheckRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    dealer = _get_dealer(db, current_user.id)
    existing = db.exec(
        select(User).where(
            User.email == data.email,
            User.created_by_dealer_id == dealer.id,
            User.is_deleted == False,
        )
    ).first()

    if existing:
        return EmailCheckResponse(available=False, message="Email already in use by another team member")
    return EmailCheckResponse(available=True, message="Email is available")


# ── Get User Detail ──────────────────────────────────────

@router.get("/{user_id}", response_model=DealerUserDetail)
def get_dealer_user_detail(
    user_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    dealer = _get_dealer(db, current_user.id)
    user = db.get(User, user_id)
    if not user or user.created_by_dealer_id != dealer.id or user.is_deleted:
        raise HTTPException(status_code=404, detail="User not found")

    base = _user_to_read(user, db)

    # Sessions
    sessions = db.exec(
        select(UserSession).where(
            UserSession.user_id == user.id,
            UserSession.is_active == True,
            UserSession.is_revoked == False,
        ).order_by(UserSession.created_at.desc())
    ).all()

    session_list = [
        SessionRead(
            id=s.id,
            device_type=s.device_type or "unknown",
            user_agent=s.user_agent,
            ip_address=s.ip_address,
            location=s.location,
            is_active=s.is_active,
            created_at=s.created_at,
            last_active_at=s.last_active_at,
        ) for s in sessions
    ]

    # Login history from audit logs
    login_logs = db.exec(
        select(AuditLog).where(
            AuditLog.target_id == user.id,
            AuditLog.resource_type == "AUTH",
        ).order_by(AuditLog.timestamp.desc()).limit(10)
    ).all()

    login_history = [
        LoginHistoryEntry(
            timestamp=log.timestamp,
            ip_address=log.ip_address,
            device=log.user_agent,
            location=None,
            success="LOGIN" in (log.action or ""),
        ) for log in login_logs
    ]

    # Permissions from role
    permissions = {}
    if user.role_id:
        role = db.get(Role, user.role_id)
        if role:
            for p in role.permissions:
                mod = p.module.title()
                if mod not in permissions:
                    permissions[mod] = []
                permissions[mod].append(p.action.capitalize())

    return DealerUserDetail(
        **base.dict(),
        notes=user.notes_internal,
        force_password_change=user.force_password_change or False,
        invite_sent_at=user.invite_sent_at,
        sessions=session_list,
        login_history=login_history,
        permissions=permissions,
    )


# ── Update User ──────────────────────────────────────────

@router.put("/{user_id}", response_model=DealerUserRead)
def update_dealer_user(
    user_id: int,
    data: DealerUserUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    dealer = _get_dealer(db, current_user.id)
    user = db.get(User, user_id)
    if not user or user.created_by_dealer_id != dealer.id or user.is_deleted:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = data.dict(exclude_unset=True)
    old_values = {}

    for key, value in update_data.items():
        if key == "notes":
            old_values["notes_internal"] = user.notes_internal
            user.notes_internal = value
        elif key == "role_id" and value is not None:
            # Validate role
            role = db.get(Role, value)
            if not role or (role.dealer_id and role.dealer_id != dealer.id):
                raise HTTPException(status_code=400, detail="Invalid role")
            old_values["role_id"] = user.role_id
            user.role_id = value
        else:
            if hasattr(user, key):
                old_values[key] = getattr(user, key)
                setattr(user, key, value)

    user.updated_at = datetime.now(UTC)
    db.add(user)

    _audit(db, current_user.id, dealer.id, AuditActionType.DATA_MODIFICATION,
           target_id=user.id, details=f"Updated user {user.email}",
           old_value=old_values, new_value=update_data)
    db.commit()
    db.refresh(user)

    return _user_to_read(user, db)


# ── Delete User ──────────────────────────────────────────

@router.delete("/{user_id}")
def delete_dealer_user(
    user_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    dealer = _get_dealer(db, current_user.id)
    user = db.get(User, user_id)
    if not user or user.created_by_dealer_id != dealer.id:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    user.is_deleted = True
    user.deleted_at = datetime.now(UTC)
    user.deletion_reason = "Deleted by admin"
    user.status = UserStatus.DELETED
    db.add(user)

    # Revoke all sessions
    sessions = db.exec(
        select(UserSession).where(UserSession.user_id == user.id, UserSession.is_active == True)
    ).all()
    for s in sessions:
        s.is_active = False
        s.is_revoked = True
        s.revoked_at = datetime.now(UTC)
        db.add(s)

    _audit(db, current_user.id, dealer.id, AuditActionType.DATA_MODIFICATION,
           target_id=user.id, details=f"Deleted user {user.email}")
    db.commit()

    return {"success": True}


# ── Change Status ────────────────────────────────────────

@router.patch("/{user_id}/status", response_model=DealerUserRead)
def change_user_status(
    user_id: int,
    data: DealerUserStatusUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    dealer = _get_dealer(db, current_user.id)
    user = db.get(User, user_id)
    if not user or user.created_by_dealer_id != dealer.id or user.is_deleted:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own status")

    old_status = user.status
    user.status = data.status
    user.updated_at = datetime.now(UTC)

    # If deactivating, revoke all sessions
    if data.status in ["inactive", "suspended"]:
        sessions = db.exec(
            select(UserSession).where(UserSession.user_id == user.id, UserSession.is_active == True)
        ).all()
        for s in sessions:
            s.is_active = False
            s.is_revoked = True
            s.revoked_at = datetime.now(UTC)
            db.add(s)

    db.add(user)
    _audit(db, current_user.id, dealer.id, AuditActionType.ACCOUNT_STATUS_CHANGE,
           target_id=user.id, details=f"Status changed: {old_status} -> {data.status}",
           old_value={"status": str(old_status)}, new_value={"status": data.status})
    db.commit()
    db.refresh(user)

    return _user_to_read(user, db)


# ── Reset Password ───────────────────────────────────────

@router.post("/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    data: DealerUserPasswordReset,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    dealer = _get_dealer(db, current_user.id)
    user = db.get(User, user_id)
    if not user or user.created_by_dealer_id != dealer.id or user.is_deleted:
        raise HTTPException(status_code=404, detail="User not found")

    if data.mode == "manual":
        if not data.password:
            raise HTTPException(status_code=400, detail="Password required")
        user.hashed_password = get_password_hash(data.password)
        user.force_password_change = data.force_password_change
        user.password_changed_at = datetime.now(UTC)
        user.updated_at = datetime.now(UTC)
        db.add(user)

        # Revoke all sessions to force re-login
        sessions = db.exec(
            select(UserSession).where(UserSession.user_id == user.id, UserSession.is_active == True)
        ).all()
        for s in sessions:
            s.is_active = False
            s.is_revoked = True
            s.revoked_at = datetime.now(UTC)
            db.add(s)

    elif data.mode == "email":
        # Generate password reset token (reuse invite_token field)
        token = _generate_invite_token()
        user.invite_token = token
        user.invite_token_expires = datetime.now(UTC) + timedelta(hours=1)
        db.add(user)
        # Send reset email
        base_url = settings.ADMIN_FRONTEND_ORIGIN or "https://admin.powerfrill.com"
        reset_link = f"{base_url}/reset-password/{token}"
        
        email_content = f"""
            <h3>Password Reset Request</h3>
            <p>You requested a password reset. Click the link below to set a new password:</p>
            <p><a href="{reset_link}">{reset_link}</a></p>
            <p>This link expires in 1 hour.</p>
        """
        EmailService.send_email(
            to_email=user.email,
            subject="Wezu Dealer Portal - Password Reset",
            content=email_content
        )
        logger.info(f"[RESET] Sent password reset email to {user.email}")

    _audit(db, current_user.id, dealer.id, AuditActionType.PASSWORD_RESET,
           target_id=user.id, details=f"Password reset ({data.mode}) for {user.email}")
    db.commit()

    return {"success": True, "message": f"Password reset via {data.mode}"}


# ── Resend Invite ────────────────────────────────────────

@router.post("/{user_id}/resend-invite")
def resend_invite(
    user_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    dealer = _get_dealer(db, current_user.id)
    user = db.get(User, user_id)
    if not user or user.created_by_dealer_id != dealer.id or user.is_deleted:
        raise HTTPException(status_code=404, detail="User not found")

    if user.status != UserStatus.PENDING:
        raise HTTPException(status_code=400, detail="User is not in pending state")

    # Generate new token
    token = _generate_invite_token()
    user.invite_token = token
    user.invite_token_expires = datetime.now(UTC) + timedelta(hours=INVITE_TOKEN_EXPIRY_HOURS)
    user.invite_sent_at = datetime.now(UTC)
    db.add(user)

    # Send actual email
    base_url = settings.ADMIN_FRONTEND_ORIGIN or "https://admin.powerfrill.com"
    invite_link = f"{base_url}/activate/{token}"
    
    email_content = f"""
        <h3>Welcome to Wezu Dealer Portal (Reminder)</h3>
        <p>You have been invited to join the dealer team. Click the link below to activate your account and set your password:</p>
        <p><a href="{invite_link}">{invite_link}</a></p>
        <p>This link expires in {INVITE_TOKEN_EXPIRY_HOURS} hours.</p>
    """
    EmailService.send_email(
        to_email=user.email,
        subject="Invitation to join Wezu Dealer Portal (Reminder)",
        content=email_content
    )
    
    logger.info(f"[INVITE-RESEND] Resent activation email to {user.email}")

    _audit(db, current_user.id, dealer.id, AuditActionType.USER_INVITE,
           target_id=user.id, details=f"Resent invitation to {user.email}")
    db.commit()

    return {"success": True, "message": f"Invitation resent to {user.email}"}


# ── Sessions ─────────────────────────────────────────────

@router.get("/{user_id}/sessions", response_model=List[SessionRead])
def get_user_sessions(
    user_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    dealer = _get_dealer(db, current_user.id)
    user = db.get(User, user_id)
    if not user or user.created_by_dealer_id != dealer.id or user.is_deleted:
        raise HTTPException(status_code=404, detail="User not found")

    sessions = db.exec(
        select(UserSession).where(
            UserSession.user_id == user.id,
            UserSession.is_active == True,
        ).order_by(UserSession.created_at.desc())
    ).all()

    return [
        SessionRead(
            id=s.id, device_type=s.device_type or "unknown",
            user_agent=s.user_agent, ip_address=s.ip_address,
            location=s.location, is_active=s.is_active,
            created_at=s.created_at, last_active_at=s.last_active_at,
        ) for s in sessions
    ]


@router.delete("/{user_id}/sessions")
def terminate_all_sessions(
    user_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    dealer = _get_dealer(db, current_user.id)
    user = db.get(User, user_id)
    if not user or user.created_by_dealer_id != dealer.id or user.is_deleted:
        raise HTTPException(status_code=404, detail="User not found")

    sessions = db.exec(
        select(UserSession).where(UserSession.user_id == user.id, UserSession.is_active == True)
    ).all()

    count = 0
    for s in sessions:
        s.is_active = False
        s.is_revoked = True
        s.revoked_at = datetime.now(UTC)
        db.add(s)
        count += 1

    _audit(db, current_user.id, dealer.id, AuditActionType.SESSION_TERMINATED,
           target_id=user.id, details=f"Terminated all {count} sessions for {user.email}")
    db.commit()

    return {"success": True, "terminated": count}


@router.delete("/{user_id}/sessions/{session_id}")
def terminate_session(
    user_id: int,
    session_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    dealer = _get_dealer(db, current_user.id)
    user = db.get(User, user_id)
    if not user or user.created_by_dealer_id != dealer.id:
        raise HTTPException(status_code=404, detail="User not found")

    session = db.get(UserSession, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    session.is_active = False
    session.is_revoked = True
    session.revoked_at = datetime.now(UTC)
    db.add(session)

    _audit(db, current_user.id, dealer.id, AuditActionType.SESSION_TERMINATED,
           target_id=user.id, details=f"Terminated session {session_id} for {user.email}")
    db.commit()

    return {"success": True}


# ── Bulk Actions ─────────────────────────────────────────

@router.post("/bulk")
def bulk_action(
    data: BulkActionRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
):
    dealer = _get_dealer(db, current_user.id)
    results = {"success": 0, "failed": 0, "errors": []}

    for uid in data.user_ids:
        user = db.get(User, uid)
        if not user or user.created_by_dealer_id != dealer.id or user.id == current_user.id:
            results["failed"] += 1
            results["errors"].append(f"User {uid}: not found or cannot modify")
            continue

        try:
            if data.action == BulkActionType.CHANGE_ROLE:
                if not data.role_id:
                    results["failed"] += 1
                    continue
                role = db.get(Role, data.role_id)
                if not role or (role.dealer_id and role.dealer_id != dealer.id):
                    results["failed"] += 1
                    continue
                user.role_id = data.role_id

            elif data.action == BulkActionType.DEACTIVATE:
                user.status = UserStatus.INACTIVE
                # Revoke sessions
                for s in db.exec(select(UserSession).where(
                    UserSession.user_id == user.id, UserSession.is_active == True
                )).all():
                    s.is_active = False
                    s.is_revoked = True
                    db.add(s)

            elif data.action == BulkActionType.DELETE:
                user.is_deleted = True
                user.deleted_at = datetime.now(UTC)
                user.status = UserStatus.DELETED

            user.updated_at = datetime.now(UTC)
            db.add(user)
            results["success"] += 1

        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"User {uid}: {str(e)}")

    _audit(db, current_user.id, dealer.id, AuditActionType.DATA_MODIFICATION,
           details=f"Bulk {data.action.value} on {len(data.user_ids)} users")
    db.commit()

    return results
