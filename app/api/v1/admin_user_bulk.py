"""
Admin Bulk User Operations API — CSV import, bulk deactivate, bulk role change.
"""

import csv
import io
import logging
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.deps import get_current_active_superuser
from app.core.database import get_db
from app.core.audit import AuditLogger
from app.core.security import get_password_hash
from app.models.user import User
from app.models.rbac import Role, UserRole

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Schemas ───

class BulkDeactivateRequest(BaseModel):
    user_ids: List[int]


class BulkRoleChangeRequest(BaseModel):
    user_ids: List[int]
    role: str  # Target role name


class BulkImportResult(BaseModel):
    created: int = 0
    skipped: int = 0
    errors: List[str] = []


# ─── Endpoints ───

@router.post("/bulk-import", response_model=BulkImportResult)
async def bulk_import_users(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Import users from CSV file.

    CSV format: email,full_name,phone_number,role,password
    First row should be a header. Duplicate emails are skipped.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    content = await file.read()
    text = content.decode("utf-8-sig")  # Handle BOM
    reader = csv.DictReader(io.StringIO(text))

    required_fields = {"email", "full_name"}
    if not required_fields.issubset(set(reader.fieldnames or [])):
        raise HTTPException(
            status_code=400,
            detail=f"CSV must contain columns: {required_fields}. Found: {reader.fieldnames}",
        )

    result = BulkImportResult()

    for row_num, row in enumerate(reader, start=2):
        email = (row.get("email") or "").strip()
        full_name = (row.get("full_name") or "").strip()
        phone = (row.get("phone_number") or "").strip() or None
        role_name = (row.get("role") or "customer").strip().lower()
        password = (row.get("password") or "Welcome@123").strip()

        if not email:
            result.errors.append(f"Row {row_num}: missing email")
            continue

        # Check duplicate
        existing = db.exec(select(User).where(User.email == email)).first()
        if existing:
            result.skipped += 1
            continue

        try:
            user = User(
                email=email,
                full_name=full_name,
                phone_number=phone,
                hashed_password=get_password_hash(password),
                is_active=True,
                status="active",
                force_password_change=True,  # Force change on first login
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            # Assign role
            role = db.exec(select(Role).where(Role.name == role_name)).first()
            if role:
                link = UserRole(user_id=user.id, role_id=role.id)
                db.add(link)
                db.commit()

            result.created += 1
        except Exception as e:
            result.errors.append(f"Row {row_num} ({email}): {str(e)}")
            db.rollback()

    AuditLogger.log_event(
        db, current_user.id, "BULK_IMPORT", "USER",
        metadata={"created": result.created, "skipped": result.skipped, "errors": len(result.errors)},
    )

    return result


@router.post("/bulk-deactivate")
def bulk_deactivate_users(
    request: BulkDeactivateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """Deactivate multiple users and revoke their sessions."""
    from app.services.auth_service import AuthService

    deactivated = 0
    errors = []

    for user_id in request.user_ids:
        user = db.get(User, user_id)
        if not user:
            errors.append(f"User {user_id} not found")
            continue
        if user.is_superuser:
            errors.append(f"User {user_id} is superuser — cannot deactivate")
            continue

        user.is_active = False
        user.status = "suspended"
        db.add(user)

        try:
            AuthService.revoke_all_user_sessions(db, user_id)
        except Exception:
            pass

        deactivated += 1

    db.commit()

    AuditLogger.log_event(
        db, current_user.id, "BULK_DEACTIVATE", "USER",
        metadata={"user_ids": request.user_ids, "deactivated": deactivated},
    )

    return {"deactivated": deactivated, "errors": errors}


@router.post("/bulk-role-change")
def bulk_role_change(
    request: BulkRoleChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """Change the role for multiple users."""
    role = db.exec(select(Role).where(Role.name == request.role)).first()
    if not role:
        raise HTTPException(status_code=404, detail=f"Role '{request.role}' not found")

    changed = 0
    errors = []

    for user_id in request.user_ids:
        user = db.get(User, user_id)
        if not user:
            errors.append(f"User {user_id} not found")
            continue

        # Remove existing roles
        existing_links = db.exec(
            select(UserRole).where(UserRole.user_id == user_id)
        ).all()
        for link in existing_links:
            db.delete(link)

        # Assign new role
        db.add(UserRole(user_id=user_id, role_id=role.id))
        changed += 1

    db.commit()

    AuditLogger.log_event(
        db, current_user.id, "BULK_ROLE_CHANGE", "USER",
        metadata={"user_ids": request.user_ids, "new_role": request.role, "changed": changed},
    )

    return {"changed": changed, "new_role": request.role, "errors": errors}
