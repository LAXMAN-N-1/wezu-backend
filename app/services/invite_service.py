"""Service layer for invite lifecycle management and user creation history."""

import secrets
import string
import logging
from typing import List, Optional, Tuple
from datetime import datetime, timedelta

from sqlmodel import Session, select, func, col, desc
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.user_invite import UserInvite, InviteStatus
from app.models.rbac import Role
from app.models.audit_log import AuditLog
from app.core.security import get_password_hash
from app.services.email_service import EmailService

logger = logging.getLogger("wezu_invite")


class InviteService:
    """Manages invite creation, resend, revoke, and history queries."""

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _generate_temp_password(length: int = 12) -> str:
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def _send_invite_email(email: str, full_name: str, role_name: str, temp_password: str) -> bool:
        subject = "You've Been Invited to Wezu!"
        content = f"""
        <h3>Welcome to Wezu, {full_name}!</h3>
        <p>An administrator has invited you to join the Wezu platform as a <strong>{role_name}</strong>.</p>
        <p>Your temporary password is: <strong>{temp_password}</strong></p>
        <p>Please log in and change your password immediately.</p>
        """
        return EmailService.send_email(email, subject, content)

    # ── Create Invite ────────────────────────────────────────────────

    @staticmethod
    def create_invite(
        db: Session,
        email: str,
        role_name: str,
        invited_by: int,
        full_name: Optional[str] = None,
    ) -> Tuple[UserInvite, User, str]:
        """
        Create a new invite: creates UserInvite record + User record + sends email.
        Returns (invite, user, temp_password).
        """
        # 1. Check duplicate email
        existing = db.exec(select(User).where(User.email == email)).first()
        if existing:
            raise ValueError("A user with this email already exists.")

        # 2. Check duplicate pending invite
        existing_invite = db.exec(
            select(UserInvite).where(
                UserInvite.email == email,
                UserInvite.status == InviteStatus.PENDING,
            )
        ).first()
        if existing_invite:
            raise ValueError("A pending invite already exists for this email.")

        # 3. Resolve role
        role = db.exec(select(Role).where(Role.name == role_name)).first()
        if not role:
            raise ValueError(f"Role '{role_name}' not found.")

        # 4. Generate temp password
        temp_password = InviteService._generate_temp_password()

        # 5. Create user record
        new_user = User(
            email=email,
            full_name=full_name or "Invited User",
            phone_number=f"invited_{secrets.token_hex(4)}",
            hashed_password=get_password_hash(temp_password),
            is_active=True,
            is_deleted=False,
            created_at=datetime.utcnow(),
        )
        new_user.role_id = role.id
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        # 6. Create invite record
        invite = UserInvite(
            email=email,
            full_name=full_name,
            role_name=role_name,
            invited_by=invited_by,
            invited_user_id=new_user.id,
            status=InviteStatus.PENDING,
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
        db.add(invite)
        db.commit()
        db.refresh(invite)

        # 7. Send email
        email_sent = InviteService._send_invite_email(email, new_user.full_name, role_name, temp_password)
        if not email_sent:
            logger.error(f"Failed to send invite email to {email}")

        return invite, new_user, temp_password

    # ── Resend Invite ────────────────────────────────────────────────

    @staticmethod
    def resend_invite(db: Session, invite_id: int, admin_user_id: int) -> UserInvite:
        """Resend an existing invite: resets expiry, generates new password, re-sends email."""
        invite = db.get(UserInvite, invite_id)
        if not invite:
            raise ValueError("Invite not found.")

        if invite.status != InviteStatus.PENDING:
            raise ValueError(f"Cannot resend invite with status '{invite.status.value}'. Only PENDING invites can be resent.")

        # 1. Reset expiry
        invite.expires_at = datetime.utcnow() + timedelta(days=7)
        invite.updated_at = datetime.utcnow()
        invite.token = secrets.token_urlsafe(32)

        # 2. Reset password for the associated user
        temp_password = InviteService._generate_temp_password()
        if invite.invited_user_id:
            user = db.get(User, invite.invited_user_id)
            if user:
                user.hashed_password = get_password_hash(temp_password)
                user.force_password_change = True
                db.add(user)

        db.add(invite)
        db.commit()
        db.refresh(invite)

        # 3. Resend email
        email_sent = InviteService._send_invite_email(
            invite.email,
            invite.full_name or "Invited User",
            invite.role_name,
            temp_password,
        )
        if not email_sent:
            logger.error(f"Failed to resend invite email to {invite.email}")

        return invite

    # ── Revoke Invite ────────────────────────────────────────────────

    @staticmethod
    def revoke_invite(db: Session, invite_id: int, admin_user_id: int) -> UserInvite:
        """Revoke a pending invite and deactivate the associated user."""
        invite = db.get(UserInvite, invite_id)
        if not invite:
            raise ValueError("Invite not found.")

        if invite.status != InviteStatus.PENDING:
            raise ValueError(f"Cannot revoke invite with status '{invite.status.value}'. Only PENDING invites can be revoked.")

        # 1. Update invite status
        invite.status = InviteStatus.REVOKED
        invite.revoked_at = datetime.utcnow()
        invite.revoked_by = admin_user_id
        invite.updated_at = datetime.utcnow()

        # 2. Deactivate the associated user
        if invite.invited_user_id:
            user = db.get(User, invite.invited_user_id)
            if user:
                user.is_active = False
                db.add(user)

        db.add(invite)
        db.commit()
        db.refresh(invite)

        return invite

    # ── List Invites ─────────────────────────────────────────────────

    @staticmethod
    def list_invites(
        db: Session,
        status_filter: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[UserInvite], int]:
        """List invites with optional status filter and pagination."""
        query = select(UserInvite).order_by(desc(UserInvite.created_at))

        if status_filter:
            query = query.where(UserInvite.status == status_filter)

        # Count
        count_query = select(func.count()).select_from(UserInvite)
        if status_filter:
            count_query = count_query.where(UserInvite.status == status_filter)
        total = db.exec(count_query).one()

        # Paginate
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        invites = db.exec(query).all()
        return invites, total

    # ── User Creation History ────────────────────────────────────────

    @staticmethod
    def get_creation_history(
        db: Session,
        page: int = 1,
        limit: int = 20,
        method: Optional[str] = None,
    ) -> Tuple[List[dict], int]:
        """
        Get user creation history by querying AuditLog for creation events.
        Supplements with invite data where available.
        """
        # Query audit log for user creation events
        action_types = ["USER_CREATION", "REGISTER", "INVITE"]
        query = (
            select(AuditLog)
            .where(col(AuditLog.action).in_(action_types))
            .order_by(desc(AuditLog.timestamp))
        )

        if method:
            method_map = {
                "direct": "USER_CREATION",
                "invite": "INVITE",
                "self_registered": "REGISTER",
            }
            mapped = method_map.get(method)
            if mapped:
                query = query.where(AuditLog.action == mapped)

        # Count
        count_query = select(func.count()).select_from(AuditLog).where(
            col(AuditLog.action).in_(action_types)
        )
        if method:
            mapped = {"direct": "USER_CREATION", "invite": "INVITE", "self_registered": "REGISTER"}.get(method)
            if mapped:
                count_query = count_query.where(AuditLog.action == mapped)
        total = db.exec(count_query).one()

        # Paginate
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)
        logs = db.exec(query).all()

        # Build response items
        items = []
        for log in logs:
            # Resolve user details
            target_user = None
            if log.resource_id:
                try:
                    target_user = db.get(User, int(log.resource_id))
                except (ValueError, TypeError):
                    pass

            actor = db.get(User, log.user_id) if log.user_id else None

            creation_method = "self_registered"
            if log.action == "USER_CREATION":
                creation_method = "direct"
            elif log.action == "INVITE":
                creation_method = "invite"

            items.append({
                "id": log.id,
                "email": target_user.email if target_user else None,
                "full_name": target_user.full_name if target_user else None,
                "phone_number": target_user.phone_number if target_user else None,
                "role_name": target_user.role.name if target_user and target_user.role else None,
                "created_by_name": actor.full_name if actor else "System",
                "created_at": log.timestamp,
                "creation_method": creation_method,
            })

        return items, total

    # ── Background: Expire Stale Invites ─────────────────────────────

    @staticmethod
    def expire_stale_invites(db: Session) -> int:
        """Mark expired invites. Called by background jobs."""
        now = datetime.utcnow()
        stale = db.exec(
            select(UserInvite).where(
                UserInvite.status == InviteStatus.PENDING,
                UserInvite.expires_at < now,
            )
        ).all()

        count = 0
        for invite in stale:
            invite.status = InviteStatus.EXPIRED
            invite.updated_at = now
            db.add(invite)
            count += 1

        if count > 0:
            db.commit()

        return count
