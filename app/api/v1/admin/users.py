from fastapi import APIRouter, Depends, HTTPException, Query, status, Response, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select, func
from typing import List, Optional
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
from app.models.user import User
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
    current_user: User = Depends(deps.get_current_active_superuser),
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
    current_user: User = Depends(deps.get_current_active_superuser),
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


@router.post("/create", response_model=dict)
async def admin_create_user(
    payload: AdminUserCreateRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
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
        role = db.exec(select(Role).where(Role.name == payload.role_name)).first()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role '{payload.role_name}' not found.",
            )

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
    current_user: User = Depends(deps.get_current_active_superuser),
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
    role = db.exec(select(Role).where(Role.name == payload.role_name)).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role '{payload.role_name}' not found.",
        )

    # 3. Generate temp password
    temp_password = _generate_temp_password()

    # 4. Create user
    new_user = User(
        email=payload.email,
        full_name=payload.full_name or "Invited User",
        phone_number=f"invited_{secrets.token_hex(4)}",  # placeholder until user updates
        hashed_password=get_password_hash(temp_password),
        is_active=True,
        is_deleted=False,
        created_at=datetime.now(UTC),
    )
    new_user.role_id = role.id

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # 5. Send invite email
    subject = "You've Been Invited to Wezu!"
    content = f"""
    <h3>Welcome to Wezu, {new_user.full_name}!</h3>
    <p>An administrator has invited you to join the Wezu platform as a <strong>{role.name}</strong>.</p>
    <p>Your temporary password is: <strong>{temp_password}</strong></p>
    <p>Please log in and change your password immediately.</p>
    """
    email_sent = EmailService.send_email(new_user.email, subject, content)

    if not email_sent:
        logger.error(f"Failed to send invite email to {new_user.email}")

    return {
        "status": "success",
        "message": f"User invited successfully. Email sent: {email_sent}",
        "user_id": new_user.id,
        "email": new_user.email,
        "role": role.name,
    }


@router.post("/bulk-invite", response_model=BulkInviteResponse)
async def admin_bulk_invite(
    file: UploadFile = File(...),
    send_emails: bool = True,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
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
    # 1. Validate file type
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a .csv file.",
        )

    # 2. Parse CSV
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

    # 3. Preload existing emails & roles
    existing_emails = {
        e.lower() for e in db.exec(select(User.email)).all() if e
    }
    available_roles = {
        r.name.lower(): r for r in db.exec(select(Role)).all()
    }

    rows = list(reader)
    results: List[BulkInviteRowResult] = []
    success_count = 0
    failure_count = 0
    emails_to_send: list = []

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
                is_active=True,
                is_deleted=False,
                created_at=datetime.now(UTC),
            )
            new_user.role_id = role.id

            db.add(new_user)
            db.commit()
            db.refresh(new_user)

            existing_emails.add(email.lower())
            results.append(BulkInviteRowResult(row_number=idx, email=email, success=True))
            success_count += 1

            if send_emails:
                emails_to_send.append({
                    "to": email,
                    "name": full_name,
                    "role": role.name,
                    "password": temp_password,
                })
        except Exception as exc:
            db.rollback()
            results.append(BulkInviteRowResult(row_number=idx, email=email, success=False, error=str(exc)))
            failure_count += 1

    # 4. Send invite emails
    emails_sent = 0
    for item in emails_to_send:
        subject = "You've Been Invited to Wezu!"
        content = f"""
        <h3>Welcome to Wezu, {item['name']}!</h3>
        <p>You have been invited as a <strong>{item['role']}</strong>.</p>
        <p>Your temporary password: <strong>{item['password']}</strong></p>
        <p>Please log in and change your password immediately.</p>
        """
        if EmailService.send_email(item["to"], subject, content):
            emails_sent += 1

    return BulkInviteResponse(
        success_count=success_count,
        failure_count=failure_count,
        total_rows=len(rows),
        results=results,
        emails_sent=emails_sent,
        generated_at=datetime.now(UTC),
    )


# =====================================================================
#  EXISTING ENDPOINTS (unchanged)
# =====================================================================

@router.put("/{id}/role", response_model=dict)
async def change_user_role(
    id: int,
    role_in: UserRoleUpdateRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
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
    current_user: User = Depends(deps.get_current_active_superuser),
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
    current_user: User = Depends(deps.get_current_active_superuser),
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
    current_user: User = Depends(deps.get_current_active_superuser),
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
    current_user: User = Depends(deps.get_current_active_superuser),
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
    current_user: User = Depends(deps.get_current_active_superuser),
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
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """Admin: forcibly log out a user from all devices"""
    from app.models.security import UserSession
    statement = select(UserSession).where(UserSession.user_id == id)
    sessions = db.exec(statement).all()
    for s in sessions:
        db.delete(s)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
