from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session

from app.api import deps
from app.core.config import settings
from app.core.proxy import extract_forwarded_client_ip
from app.core.security import create_access_token, create_refresh_token
from app.db.session import get_session
from app.models.user import User
from app.schemas.auth import (
    LoginResponse,
    PasskeyCredentialInfo,
    PasskeyListResponse,
    PasskeyOperationResponse,
    PasskeyOptionsRequest,
    PasskeyOptionsResponse,
    PasskeyRegistrationOptionsRequest,
    PasskeyRegistrationVerifyRequest,
    PasskeyRegistrationVerifyResponse,
    PasskeyVerifyRequest,
)
from app.services.auth_service import AuthService
from app.services.passkey_service import PasskeyService

router = APIRouter(prefix="/passkeys")


def _extract_client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    source_ip = request.client.host if request.client else None
    return extract_forwarded_client_ip(
        source_ip,
        request.headers.get("x-forwarded-for"),
        request.headers.get("forwarded"),
        request.headers.get("x-real-ip"),
    )


def _to_credential_info(item) -> PasskeyCredentialInfo:
    return PasskeyCredentialInfo(
        credential_id=item.credential_id,
        passkey_name=item.passkey_name,
        created_at=item.created_at,
        last_used_at=item.last_used_at,
        device_type=item.credential_device_type,
        backed_up=bool(item.credential_backed_up),
    )


def _resolve_selected_role(user: User, requested_role: Optional[str]) -> tuple[Optional[str], list[str], bool]:
    user_roles = [role.name for role in (user.roles or []) if getattr(role, "name", None)]
    if not user_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No roles assigned to user")

    if requested_role:
        if requested_role not in user_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User does not have role: {requested_role}",
            )
        return requested_role, user_roles, False

    if len(user_roles) == 1:
        return user_roles[0], user_roles, False

    return None, user_roles, True


@router.post("/register/options", response_model=PasskeyOptionsResponse)
def create_registration_options(
    payload: PasskeyRegistrationOptionsRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    if not settings.PASSKEY_ENABLED:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Passkey login is disabled")

    data = PasskeyService.generate_registration_options(db, user=current_user)
    return PasskeyOptionsResponse(**data)


@router.post("/register/verify", response_model=PasskeyRegistrationVerifyResponse)
def verify_registration(
    payload: PasskeyRegistrationVerifyRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    if not settings.PASSKEY_ENABLED:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Passkey login is disabled")

    credential = PasskeyService.verify_registration(
        db,
        user=current_user,
        challenge_id=payload.challenge_id,
        credential=payload.credential,
        passkey_name=payload.passkey_name,
    )

    return PasskeyRegistrationVerifyResponse(
        success=True,
        message="Passkey registered successfully",
        credential=_to_credential_info(credential),
    )


@router.post("/auth/options", response_model=PasskeyOptionsResponse)
def create_authentication_options(
    payload: PasskeyOptionsRequest,
    db: Session = Depends(get_session),
):
    if not settings.PASSKEY_ENABLED:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Passkey login is disabled")

    data = PasskeyService.generate_authentication_options(db, username=payload.username)
    return PasskeyOptionsResponse(**data)


@router.post("/auth/verify", response_model=LoginResponse)
def verify_authentication(
    payload: PasskeyVerifyRequest,
    request: Request,
    db: Session = Depends(get_session),
):
    if not settings.PASSKEY_ENABLED:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Passkey login is disabled")

    user, _ = PasskeyService.verify_authentication(
        db,
        challenge_id=payload.challenge_id,
        credential=payload.credential,
    )

    selected_role, user_roles, needs_selection = _resolve_selected_role(user, payload.role)
    if needs_selection:
        return LoginResponse(
            success=False,
            message="Please select a role to continue",
            requires_role_selection=True,
            available_roles=user_roles,
            user=user.model_dump(exclude={"hashed_password"}),
        )

    assert selected_role is not None

    user.last_login = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    AuthService.create_session(
        db,
        user.id,
        access_token,
        refresh_token,
        device_info="Passkey",
        ip_address=_extract_client_ip(request),
    )

    permissions = AuthService.get_permissions_for_role(db, selected_role)
    menu_data = AuthService.get_menu_for_role(db, selected_role)

    return LoginResponse(
        success=True,
        access_token=access_token,
        refresh_token=refresh_token,
        user=user.model_dump(exclude={"hashed_password"}),
        role=selected_role,
        available_roles=user_roles,
        permissions=permissions,
        menu=menu_data,
    )


@router.get("", response_model=PasskeyListResponse)
def list_passkeys(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    items = PasskeyService.list_passkeys(db, user_id=current_user.id)
    return PasskeyListResponse(items=[_to_credential_info(item) for item in items])


@router.delete("/{credential_id}", response_model=PasskeyOperationResponse)
def delete_passkey(
    credential_id: str,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    PasskeyService.deactivate_passkey(db, user_id=current_user.id, credential_id=credential_id)
    return PasskeyOperationResponse(success=True, message="Passkey removed")
