from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, Response, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select, func
from typing import Any, Dict, List, Optional
import csv
import io
import secrets
import string
import logging
from app.api import deps
from app.services.user_service import UserService
from app.services.email_service import EmailService
from app.core.security import get_password_hash
from app.models.rbac import Role
from app.schemas.admin_user import (
    UserSuspensionRequest, 
    UserRoleUpdateRequest, 
    BulkUserActionRequest,
    UserHistoryResponse,
    AdminUserCreateRequest,
    AdminInviteRequest,
    BulkInviteRowResult,
    BulkInviteResponse,
)
from app.schemas.user import UserSearchResponse, UserSearchItem
from app.models.user import User, UserStatus, UserType
from datetime import datetime, UTC, timedelta

logger = logging.getLogger("wezu_admin")

router = APIRouter()


# =====================================================================
#  LIST / SEARCH USERS
# =====================================================================

@router.get("/", response_model=dict)
async def list_users(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    status: Optional[str] = None,
    user_type: Optional[str] = None,
    kyc_status: Optional[str] = None,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
):
    """Admin: List all users with filtering and pagination."""
    query = select(User)
    
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (User.email.ilike(search_term)) |
            (User.full_name.ilike(search_term)) |
            (User.phone_number.ilike(search_term))
        )
    
    if status is not None:
        if status.lower() == "active":
            query = query.where(User.status == "active")
        elif status.lower() == "suspended":
            query = query.where(User.status == "suspended")
        elif status.lower() == "pending_verification":
            query = query.where(User.status == "pending_verification")
            
    if user_type:
        query = query.where(User.user_type == user_type)
        
    if kyc_status:
        query = query.where(User.kyc_status == kyc_status)
        
    query = query.order_by(User.created_at.desc())
    
    total_count = db.exec(select(func.count()).select_from(query.subquery())).one()
    users = db.exec(query.offset(skip).limit(limit)).all()
    
    return {
        "users": users,
        "total_count": total_count,
    }


@router.get("/suspended", response_model=dict)
async def list_suspended_users(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
):
    """Admin: List all suspended users."""
    query = select(User).where(User.status == "suspended")
    
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (User.email.ilike(search_term)) |
            (User.full_name.ilike(search_term)) |
            (User.phone_number.ilike(search_term))
        )
        
    query = query.order_by(User.created_at.desc())
    
    total_count = db.exec(select(func.count()).select_from(query.subquery())).one()
    users = db.exec(query.offset(skip).limit(limit)).all()
    
    return {
        "users": users,
        "total_count": total_count,
    }


# =====================================================================
#  CREATE / INVITE / BULK-INVITE  (new admin user-management endpoints)
# =====================================================================

def _generate_temp_password(length: int = 12) -> str:
    """Generate a secure temporary password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _generate_invite_token() -> str:
    return secrets.token_urlsafe(24)


def _resolve_role(db: Session, role_name: str) -> Role:
    role = db.exec(select(Role).where(func.lower(Role.name) == role_name.lower())).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role '{role_name}' not found.",
        )
    return role


def _derive_user_type(role_name: str) -> UserType:
    role_value = role_name.strip().lower()
    if role_value in {"admin", "super_admin", "superadmin", "manager", "support_agent", "support"}:
        return UserType.ADMIN
    if role_value == "dealer":
        return UserType.DEALER
    if role_value in {"logistics", "driver"}:
        return UserType.LOGISTICS
    return UserType.CUSTOMER


def _issue_invite(
    *,
    db: Session,
    user: User,
    role: Role,
    raw_password: str,
    current_user: User,
) -> bool:
    user.role_id = role.id
    user.user_type = _derive_user_type(role.name)
    user.status = UserStatus.ACTIVE
    user.force_password_change = True
    user.invite_token = _generate_invite_token()
    user.invite_token_expires = datetime.now(UTC) + timedelta(hours=72)
    user.invite_sent_at = datetime.now(UTC)
    user.created_by_user_id = current_user.id
    db.add(user)
    db.commit()
    db.refresh(user)

    subject = "You've Been Invited to Wezu!"
    content = f"""
    <h3>Welcome to Wezu, {user.full_name}!</h3>
    <p>You have been invited as a <strong>{role.name}</strong>.</p>
    <p>Your temporary password is: <strong>{raw_password}</strong></p>
    <p>Please log in and change your password immediately.</p>
    """
    email_sent = EmailService.send_email(user.email, subject, content)
    if not email_sent:
        logger.error("Failed to send invite email to %s", user.email)
    return email_sent


def _invite_status(user: User) -> str:
    if user.last_login or user.password_changed_at:
        return "accepted"
    if user.status == UserStatus.INACTIVE and user.invite_sent_at:
        return "revoked"
    if user.invite_token_expires and user.invite_token_expires < datetime.now(UTC):
        return "expired"
    return "pending"


def _serialize_invite(db: Session, user: User) -> Dict[str, Any]:
    role_name = None
    if user.role_id:
        role = db.get(Role, user.role_id)
        role_name = role.name if role else None

    invited_by_name = None
    if user.created_by_user_id:
        invited_by = db.get(User, user.created_by_user_id)
        invited_by_name = invited_by.full_name if invited_by and invited_by.full_name else invited_by.email if invited_by else None

    accepted_at = user.password_changed_at or user.last_login

    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": role_name or (user.user_type.value if user.user_type else "customer"),
        "status": _invite_status(user),
        "token": user.invite_token,
        "created_at": user.invite_sent_at.isoformat() if user.invite_sent_at else None,
        "sent_at": user.invite_sent_at.isoformat() if user.invite_sent_at else None,
        "expires_at": user.invite_token_expires.isoformat() if user.invite_token_expires else None,
        "created_by": invited_by_name or "System",
        "invited_by": invited_by_name,
        "used_at": accepted_at.isoformat() if accepted_at else None,
        "is_used": accepted_at is not None,
    }


def _load_bulk_invite_rows(raw_rows: List[dict]) -> List[dict]:
    rows: List[dict] = []
    for row in raw_rows:
        rows.append(
            {
                "email": (row.get("email") or "").strip(),
                "full_name": (row.get("full_name") or row.get("name") or "").strip(),
                "phone_number": (row.get("phone_number") or "").strip(),
                "role": (row.get("role") or row.get("role_name") or "customer").strip(),
            }
        )
    return rows


@router.post("/create", response_model=dict)
async def admin_create_user(
    payload: AdminUserCreateRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
):
    """
    Admin: Create a new user directly.

    - If `password` is omitted a secure random password is generated.
    - If `role_name` is provided the user is assigned that role.
    - A welcome email with credentials is sent automatically.
    """
    # 1. Duplicate check
    existing = db.exec(select(User).where(User.email == payload.email)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists.",
        )

    phone_exists = db.exec(select(User).where(User.phone_number == payload.phone_number)).first()
    if phone_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this phone number already exists.",
        )

    # 2. Resolve role (optional)
    role = None
    if payload.role_name:
        role = _resolve_role(db, payload.role_name)

    # 3. Password
    raw_password = payload.password or _generate_temp_password()

    # 4. Create user
    new_user = User(
        email=payload.email,
        full_name=payload.full_name,
        phone_number=payload.phone_number,
        hashed_password=get_password_hash(raw_password),
        is_active=True,
        is_deleted=False,
        created_at=datetime.now(UTC),
    )
    if role:
        new_user.role_id = role.id
        new_user.user_type = _derive_user_type(role.name)

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # 5. Send welcome email
    subject = "Your Wezu Account Has Been Created"
    content = f"""
    <h3>Welcome to Wezu, {new_user.full_name}!</h3>
    <p>An administrator has created an account for you.</p>
    <p>Your login credentials:</p>
    <ul>
        <li><strong>Email:</strong> {new_user.email}</li>
        <li><strong>Password:</strong> {raw_password}</li>
    </ul>
    <p>Please log in and change your password immediately.</p>
    """
    email_sent = EmailService.send_email(new_user.email, subject, content)

    return {
        "status": "success",
        "message": f"User created successfully. Email sent: {email_sent}",
        "user_id": new_user.id,
        "email": new_user.email,
    }


@router.post("/invite", response_model=dict)
async def admin_invite_user(
    payload: AdminInviteRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
):
    """
    Admin: Invite a new user by email.

    Generates a temporary password, creates the user record, assigns the
    requested role, and sends an invitation email with credentials.
    """
    # 1. Duplicate check
    existing = db.exec(select(User).where(User.email == payload.email)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists.",
        )

    # 2. Resolve role
    role = _resolve_role(db, payload.role_name)

    # 3. Generate temp password
    temp_password = _generate_temp_password()

    # 4. Create user
    new_user = User(
        email=payload.email,
        full_name=payload.full_name or "Invited User",
        phone_number=f"invited_{secrets.token_hex(4)}",  # placeholder until user updates
        hashed_password=get_password_hash(temp_password),
        is_deleted=False,
        created_at=datetime.now(UTC),
    )
    email_sent = _issue_invite(
        db=db,
        user=new_user,
        role=role,
        raw_password=temp_password,
        current_user=current_user,
    )

    return {
        "status": "success",
        "message": f"User invited successfully. Email sent: {email_sent}",
        "user_id": new_user.id,
        "email": new_user.email,
        "role": role.name,
        "invite": _serialize_invite(db, new_user),
    }


@router.post("/bulk-invite", response_model=BulkInviteResponse)
async def admin_bulk_invite(
    request: Request,
    file: Optional[UploadFile] = File(default=None),
    send_emails: bool = True,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
):
    """
    Admin: Bulk-invite users via CSV upload.

    **CSV columns** (header row required):
    `email, full_name, phone_number, role`

    - `email` — required, must be unique
    - `full_name` — required
    - `phone_number` — optional (placeholder generated if blank)
    - `role` — optional, defaults to "customer"

    A temporary password is generated per user and emailed if `send_emails=true`.
    """
    rows: List[dict]
    if file is not None:
        if not file.filename.endswith(".csv"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a .csv file.",
            )
        try:
            raw = await file.read()
            reader = csv.DictReader(io.StringIO(raw.decode("utf-8")))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse CSV: {e}",
            )
        required_cols = {"email", "full_name"}
        if not required_cols.issubset(set(reader.fieldnames or [])):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CSV must contain at least these columns: {', '.join(required_cols)}",
            )
        rows = list(reader)
    else:
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Expected CSV upload or JSON body with 'invites': {exc}",
            )
        raw_invites = payload.get("invites") if isinstance(payload, dict) else None
        if not isinstance(raw_invites, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="JSON bulk invite payload must include an 'invites' list.",
            )
        rows = _load_bulk_invite_rows(raw_invites)

    # 3. Preload existing emails & roles
    existing_emails = {
        e.lower() for e in db.exec(select(User.email)).all() if e
    }
    available_roles = {
        r.name.lower(): r for r in db.exec(select(Role)).all()
    }

    results: List[BulkInviteRowResult] = []
    success_count = 0
    failure_count = 0
    emails_sent = 0

    for idx, row in enumerate(rows, start=2):  # row 1 = header
        email = (row.get("email") or "").strip()
        full_name = (row.get("full_name") or "").strip()
        phone_number = (row.get("phone_number") or "").strip()
        role_name = (row.get("role") or "customer").strip().lower()

        # --- validate ---
        if not email or "@" not in email:
            results.append(BulkInviteRowResult(row_number=idx, email=email, success=False, error="Invalid or missing email"))
            failure_count += 1
            continue

        if email.lower() in existing_emails:
            results.append(BulkInviteRowResult(row_number=idx, email=email, success=False, error="Email already exists"))
            failure_count += 1
            continue

        if not full_name:
            results.append(BulkInviteRowResult(row_number=idx, email=email, success=False, error="Full name is required"))
            failure_count += 1
            continue

        if role_name not in available_roles:
            results.append(BulkInviteRowResult(row_number=idx, email=email, success=False, error=f"Role '{role_name}' not found"))
            failure_count += 1
            continue

        # --- create ---
        try:
            temp_password = _generate_temp_password()
            role = available_roles[role_name]

            new_user = User(
                email=email,
                full_name=full_name,
                phone_number=phone_number or f"invited_{secrets.token_hex(4)}",
                hashed_password=get_password_hash(temp_password),
                is_deleted=False,
                created_at=datetime.now(UTC),
            )
            email_sent = False
            if send_emails:
                if _issue_invite(
                    db=db,
                    user=new_user,
                    role=role,
                    raw_password=temp_password,
                    current_user=current_user,
                ):
                    emails_sent += 1
            else:
                new_user.role_id = role.id
                new_user.user_type = _derive_user_type(role.name)
                new_user.status = UserStatus.ACTIVE
                new_user.force_password_change = True
                new_user.invite_token = _generate_invite_token()
                new_user.invite_token_expires = datetime.now(UTC) + timedelta(hours=72)
                new_user.invite_sent_at = datetime.now(UTC)
                new_user.created_by_user_id = current_user.id
                db.add(new_user)
                db.commit()
                db.refresh(new_user)

            existing_emails.add(email.lower())
            results.append(BulkInviteRowResult(row_number=idx, email=email, success=True))
            success_count += 1
        except Exception as exc:
            db.rollback()
            results.append(BulkInviteRowResult(row_number=idx, email=email, success=False, error=str(exc)))
            failure_count += 1

    return BulkInviteResponse(
        success_count=success_count,
        failure_count=failure_count,
        total_rows=len(rows),
        results=results,
        emails_sent=emails_sent,
        generated_at=datetime.now(UTC),
    )


@router.get("/invites", response_model=dict)
async def list_admin_invites(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
):
    statement = select(User).where(User.invite_sent_at != None).order_by(User.invite_sent_at.desc())
    users = db.exec(statement).all()

    invites = [_serialize_invite(db, user) for user in users]
    if status_filter:
        invites = [
            invite for invite in invites
            if invite["status"] == status_filter.lower()
        ]

    return {"items": invites, "total_count": len(invites)}


@router.post("/{id}/invite/resend", response_model=dict)
async def resend_admin_invite(
    id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
):
    user = db.get(User, id)
    if not user or not user.invite_sent_at:
        raise HTTPException(status_code=404, detail="Invite not found")
    if _invite_status(user) == "accepted":
        raise HTTPException(status_code=400, detail="Invite already accepted")
    if not user.email:
        raise HTTPException(status_code=400, detail="Invited user has no email address")
    if not user.role_id:
        raise HTTPException(status_code=400, detail="Invited user has no role assigned")

    role = db.get(Role, user.role_id)
    if not role:
        raise HTTPException(status_code=400, detail="Invited user role no longer exists")

    temp_password = _generate_temp_password()
    user.hashed_password = get_password_hash(temp_password)
    user.status = UserStatus.PENDING
    user.force_password_change = True
    email_sent = _issue_invite(
        db=db,
        user=user,
        role=role,
        raw_password=temp_password,
        current_user=current_user,
    )
    return {
        "status": "success",
        "message": f"Invite resent. Email sent: {email_sent}",
        "invite": _serialize_invite(db, user),
    }


@router.post("/{id}/invite/revoke", response_model=dict)
async def revoke_admin_invite(
    id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
):
    user = db.get(User, id)
    if not user or not user.invite_sent_at:
        raise HTTPException(status_code=404, detail="Invite not found")
    if _invite_status(user) == "accepted":
        raise HTTPException(status_code=400, detail="Accepted invites cannot be revoked")

    user.invite_token = None
    user.invite_token_expires = None
    user.force_password_change = False
    user.status = UserStatus.INACTIVE
    user.updated_at = datetime.now(UTC)
    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "status": "success",
        "message": "Invite revoked",
        "invite": _serialize_invite(db, user),
    }


# =====================================================================
#  EXISTING ENDPOINTS (unchanged)
# =====================================================================

@router.put("/{id}/role", response_model=dict)
async def change_user_role(
    id: int,
    role_in: UserRoleUpdateRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
):
    """Change a user's role with reason logging"""
    user = UserService.update_role(db, id, current_user.id, role_in.role_id, role_in.reason)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "success", "message": f"Role updated to {role_in.role_id}"}

@router.put("/{id}/suspend", response_model=dict)
async def suspend_user(
    id: int,
    req: UserSuspensionRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
):
    """Suspend account with reason and optional duration"""
    expires_at = None
    if req.duration_days:
        expires_at = datetime.now(UTC) + timedelta(days=req.duration_days)
        
    user = UserService.suspend_user(db, id, current_user.id, req.reason, expires_at)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "suspended", "until": expires_at}

@router.put("/{id}/reactivate", response_model=dict)
async def reactivate_user(
    id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
):
    """Manually reactivate a suspended account"""
    user = UserService.reactivate_user(db, id, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "active"}

@router.get("/{id}/suspension-history", response_model=List[UserHistoryResponse])
async def get_suspension_history(
    id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
):
    """View all suspension/reactivation events for a user"""
    logs = UserService.get_status_history(db, id)
    
    results = []
    for log in logs:
        # Resolve actor name
        actor = db.get(User, log.actor_id)
        results.append(UserHistoryResponse(
            id=log.id,
            action_type=log.action_type,
            old_value=log.old_value,
            new_value=log.new_value,
            reason=log.reason,
            actor_name=actor.full_name if actor else "Unknown",
            created_at=log.created_at
        ))
    return results

@router.post("/bulk-action", response_model=dict)
async def bulk_user_action(
    req: BulkUserActionRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
):
    """Bulk activate, deactivate, or message users"""
    if req.action not in ["activate", "deactivate", "message"]:
        raise HTTPException(status_code=400, detail="Invalid action")
        
    updated_count = 0
    for uid in req.user_ids:
        user = db.get(User, uid)
        if not user: continue
        
        if req.action == "activate":
            user.is_active = True
        elif req.action == "deactivate":
            user.is_active = False
            
        db.add(user)
        updated_count += 1
        
    db.commit()
    return {"status": "success", "processed": updated_count}

@router.post("/export")
async def export_users(
    role: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db),
):
    """Export user list to CSV with applied filters"""
    from app.api.v1.users import read_users
    
    # Simulate the query (reusing logic conceptually)
    query = select(User)
    if status == "active":
        query = query.where(User.is_active == True)
    elif status == "inactive":
        query = query.where(User.is_active == False)
        
    users = db.exec(query).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Email", "Phone", "Status", "Joined At"])
    
    for u in users:
        writer.writerow([u.id, u.full_name, u.email, u.phone_number, u.status, u.created_at])
        
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=users_export_{datetime.now().strftime('%Y%m%d')}.csv"}
    )

@router.delete("/{id}/sessions", status_code=status.HTTP_204_NO_CONTENT)
async def terminate_user_sessions(
    id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_admin),
):
    """Admin: forcibly log out a user from all devices"""
    from app.models.security import UserSession
    statement = select(UserSession).where(UserSession.user_id == id)
    sessions = db.exec(statement).all()
    for s in sessions:
        db.delete(s)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
