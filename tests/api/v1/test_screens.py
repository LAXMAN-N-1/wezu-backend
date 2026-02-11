
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.api import deps
from app.models.user import User
from app.models.rbac import Role, UserRole
from app.core.config import settings
from unittest.mock import patch

def create_test_user(session: Session, email: str, role_name: str) -> User:
    # Check if user exists
    user = session.exec(select(User).where(User.email == email)).first()
    if user:
        return user
        
    user = User(email=email, is_active=True)
    session.add(user)
    session.commit()
    
    # Create role if not exists (minimal)
    role = session.exec(select(Role).where(Role.name == role_name)).first()
    if not role:
        role = Role(name=role_name, category="system")
        session.add(role)
        session.commit()
    
    # Assign role
    user_role = UserRole(user_id=user.id, role_id=role.id)
    session.add(user_role)
    session.commit()
    session.refresh(user)
    return user

def test_get_screen_config_full_access(client: TestClient, session: Session):
    user = create_test_user(session, "admin_screen@test.com", "admin")
    
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: user
    
    # Mock permissions to be "all"
    with patch("app.services.auth_service.AuthService.get_permissions_for_role", return_value=["all"]):
        resp = client.get(f"{settings.API_V1_STR}/screens/battery_list/config")
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify columns
        columns = {col["field"]: col for col in data["columns"]}
        assert columns["financial_data"]["visible"] is True
        
        # Verify actions
        actions = {act["id"]: act for act in data["actions"]}
        assert actions["delete"]["enabled"] is True

def test_get_screen_config_limited_access(client: TestClient, session: Session):
    user = create_test_user(session, "limited_screen@test.com", "viewer")
    
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: user
    
    # Mock permissions: view only, no finance, no update/delete
    with patch("app.services.auth_service.AuthService.get_permissions_for_role", return_value=["battery:view"]):
        resp = client.get(f"{settings.API_V1_STR}/screens/battery_list/config")
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify columns: cost should be hidden
        columns = {col["field"]: col for col in data["columns"]}
        assert columns["financial_data"]["visible"] is False
        
        # Verify actions: edit/delete should be disabled
        actions = {act["id"]: act for act in data["actions"]}
        assert actions["edit"]["enabled"] is False
        assert actions["delete"]["enabled"] is False
        assert actions["view_details"]["enabled"] is True

def test_get_screen_config_not_found(client: TestClient, session: Session):
    user = create_test_user(session, "fail_screen@test.com", "admin")
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: user
    
    resp = client.get(f"{settings.API_V1_STR}/screens/non_existent_screen/config")
    assert resp.status_code == 404
