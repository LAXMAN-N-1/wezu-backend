
import pytest
from unittest.mock import patch, MagicMock
from app.api.v1.auth import login
from app.schemas.auth import LoginRequest
from app.models.user import User
from app.core.security import get_password_hash, generate_totp_secret
import pyotp
from datetime import datetime
from fastapi import HTTPException

@pytest.mark.asyncio
async def test_login_success_no_2fa(session):
    # Setup user
    password = "password123"
    hashed = get_password_hash(password)
    user = User(
        email="test_no_2fa@example.com", 
        hashed_password=hashed,
        is_active=True,
        two_factor_enabled=False
    )
    # Mock role
    from app.models.rbac import Role
    role = Role(name="user", description="User role", is_system_role=True)
    user.roles = [role]
    
    session.add(role)
    session.add(user)
    session.commit()
    
    # Login
    req = LoginRequest(username=user.email, password=password)
    
    with patch("app.services.auth_service.AuthService.get_permissions_for_role", return_value=[]), \
         patch("app.services.auth_service.AuthService.get_menu_for_role", return_value=[]):
        response = await login(req, db=session)
    
    assert response.success is True
    assert response.access_token is not None

@pytest.mark.asyncio
async def test_login_requires_2fa_fail(session):
    # Setup user with 2FA
    password = "password123"
    hashed = get_password_hash(password)
    user = User(
        email="test_2fa_fail@example.com", 
        hashed_password=hashed,
        is_active=True,
        two_factor_enabled=True,
        two_factor_secret=generate_totp_secret()
    )
    from app.models.rbac import Role
    role = Role(name="user_2fa", description="User role", is_system_role=True)
    user.roles = [role]
    
    session.add(role)
    session.add(user)
    session.commit()
    
    # Login without code
    req = LoginRequest(username=user.email, password=password)
    
    with pytest.raises(HTTPException) as excinfo:
        await login(req, db=session)
    
    assert excinfo.value.status_code == 400
    assert "Two-factor authentication required" in excinfo.value.detail

@pytest.mark.asyncio
async def test_login_2fa_success(session):
    # Setup user with 2FA
    password = "password123"
    hashed = get_password_hash(password)
    secret = generate_totp_secret()
    user = User(
        email="test_2fa_success@example.com", 
        hashed_password=hashed,
        is_active=True,
        two_factor_enabled=True,
        two_factor_secret=secret
    )
    from app.models.rbac import Role
    role = Role(name="user_2fa_ok", description="User role", is_system_role=True)
    user.roles = [role]
    
    session.add(role)
    session.add(user)
    session.commit()
    
    # Generate valid code
    totp = pyotp.TOTP(secret)
    code = totp.now()
    
    # Login with code
    req = LoginRequest(username=user.email, password=password, totp_code=code)
    
    with patch("app.services.auth_service.AuthService.get_permissions_for_role", return_value=[]), \
         patch("app.services.auth_service.AuthService.get_menu_for_role", return_value=[]):
        response = await login(req, db=session)
    
    assert response.success is True
    assert response.access_token is not None

@pytest.mark.asyncio
async def test_login_inactive_user(session):
    # Setup inactive user
    password = "password123"
    hashed = get_password_hash(password)
    user = User(
        email="test_inactive@example.com", 
        hashed_password=hashed,
        is_active=False
        # security_lock_reason defaults to None or we can set it
    )
    # Mock role (needed for session load usually, but fail happens before role check)
    
    session.add(user)
    session.commit()
    
    # Login
    req = LoginRequest(username=user.email, password=password)
    
    with pytest.raises(HTTPException) as excinfo:
        await login(req, db=session)
    
    assert excinfo.value.status_code == 403
    assert "Account is inactive" in excinfo.value.detail
