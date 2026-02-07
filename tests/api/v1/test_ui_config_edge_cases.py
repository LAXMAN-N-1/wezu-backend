
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.api import deps
from app.models.user import User
from app.models.rbac import Role, UserRole
from app.core.config import settings
from unittest.mock import patch, MagicMock
from app.api.v1.screens import MASTER_SCREEN_CONFIG

# Helper to create a user with NO roles
def create_roleless_user(session: Session, email: str) -> User:
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        user = User(email=email, is_active=True)
        session.add(user)
        session.commit()
    # Remove any existing roles
    existing_roles = session.exec(select(UserRole).where(UserRole.user_id == user.id)).all()
    for ur in existing_roles:
        session.delete(ur)
    session.commit()
    session.refresh(user)
    return user

def test_menu_config_no_roles(client: TestClient, session: Session):
    """User with no roles should get empty or default menu, but NO CRASH"""
    user = create_roleless_user(session, "norole_menu@test.com")
    client.app.dependency_overrides[deps.get_current_user] = lambda: user
    
    with patch("app.services.auth_service.AuthService.get_permissions_for_role", return_value=[]):
        resp = client.get(f"{settings.API_V1_STR}/users/me/menu-config")
        assert resp.status_code == 200
        data = resp.json()
        # Should act like a guest/limited user. Items with NO permission requirement should show.
        # Check if dashboard (usually public/base) is there
        ids = [item["id"] for item in data["menu"]]
        assert "dashboard" in ids
        # Restricted items should not be there
        assert "finance" not in ids

def test_screen_config_no_roles(client: TestClient, session: Session):
    """User with no roles should see only public columns/actions"""
    user = create_roleless_user(session, "norole_screen@test.com")
    client.app.dependency_overrides[deps.get_current_user] = lambda: user
    
    with patch("app.services.auth_service.AuthService.get_permissions_for_role", return_value=[]):
        resp = client.get(f"{settings.API_V1_STR}/screens/battery_list/config")
        assert resp.status_code == 200
        data = resp.json()
        
        # Columns
        cols = {c["field"]: c for c in data["columns"]}
        assert cols["battery_id"]["visible"] is True # public
        assert cols["financial_data"]["visible"] is False # restricted
        
        # Actions
        actions = {a["id"]: a for a in data["actions"]}
        assert actions["view_details"]["enabled"] is True # public
        assert actions["delete"]["enabled"] is False # restricted

def test_dashboard_no_roles(client: TestClient, session: Session):
    """User with no roles should get 'default' dashboard layout"""
    user = create_roleless_user(session, "norole_dash@test.com")
    client.app.dependency_overrides[deps.get_current_user] = lambda: user
    
    resp = client.get(f"{settings.API_V1_STR}/users/me/dashboard-widgets")
    assert resp.status_code == 200
    data = resp.json()
    layout = data["layout"]
    
    # Check for default widget
    ids = [w["id"] for w in layout]
    assert "welcome_widget" in ids
    assert "revenue_chart" not in ids
    
def test_feature_flags_no_roles(client: TestClient, session: Session):
    """User with no roles should get base feature flags"""
    user = create_roleless_user(session, "norole_ff@test.com")
    client.app.dependency_overrides[deps.get_current_user] = lambda: user
    
    resp = client.get(f"{settings.API_V1_STR}/users/me/feature-flags")
    assert resp.status_code == 200
    features = resp.json()["features"]
    
    assert features["dynamic_pricing"] is True # Base feature
    assert features["advanced_analytics"] is False # Admin feature

def test_screen_config_empty_definition(client: TestClient, session: Session):
    """Test behavior when screen config is empty/minimal"""
    # Temporarily mock MASTER_SCREEN_CONFIG
    with patch.dict(MASTER_SCREEN_CONFIG, {"empty_screen": {"screen_id": "empty_screen", "columns": []}}):
        user = create_roleless_user(session, "empty_cfg@test.com")
        client.app.dependency_overrides[deps.get_current_user] = lambda: user
        
        with patch("app.services.auth_service.AuthService.get_permissions_for_role", return_value=[]):
            resp = client.get(f"{settings.API_V1_STR}/screens/empty_screen/config")
            assert resp.status_code == 200
            data = resp.json()
            assert data["columns"] == []
            assert data["actions"] == []
