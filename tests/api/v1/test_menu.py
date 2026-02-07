
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.api import deps
from app.models.user import User
from app.models.rbac import Role, UserRole
from app.core.config import settings
from unittest.mock import patch

def create_test_user(session: Session, email: str, role_name: str) -> User:
    user = User(email=email, is_active=True)
    session.add(user)
    session.commit()
    
    # Create role if not exists (minimal)
    role = session.exec(select(Role).where(Role.name == role_name)).first()
    if not role:
        role = Role(name=role_name, category="system")
        session.add(role)
        session.commit()
    
    user_role = UserRole(user_id=user.id, role_id=role.id)
    session.add(user_role)
    session.commit()
    session.refresh(user)
    return user

def test_get_menu_config_admin_permissions(client: TestClient, session: Session):
    user = create_test_user(session, "admin_menu_test@test.com", "admin")
    
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: user
    
    # Mock permissions to be "all"
    with patch("app.services.auth_service.AuthService.get_permissions_for_role", return_value=["all"]):
        resp = client.get(f"{settings.API_V1_STR}/users/me/menu-config")
        assert resp.status_code == 200
        data = resp.json()
        menu = data["menu"]
        ids = [item["id"] for item in menu]
        
        # Should see everything
        assert "dashboard" in ids
        assert "users" in ids
        assert "finance" in ids

def test_get_menu_config_limited_permissions(client: TestClient, session: Session):
    user = create_test_user(session, "limited_menu_test@test.com", "limited_user")
    
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: user
    
    # Mock permissions to only have "finance:view"
    with patch("app.services.auth_service.AuthService.get_permissions_for_role", return_value=["finance:view"]):
        resp = client.get(f"{settings.API_V1_STR}/users/me/menu-config")
        assert resp.status_code == 200
        data = resp.json()
        menu = data["menu"]
        ids = [item["id"] for item in menu]
        
        # Should see Dashboard (no perm required) and Finance
        assert "dashboard" in ids
        assert "finance" in ids
        
        # Should NOT see Users or Batteries
        assert "users" not in ids
        assert "batteries" not in ids

def test_menu_structure_integrity(client: TestClient, session: Session):
    user = create_test_user(session, "struct_test@test.com", "struct_user")
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: user
    
    with patch("app.services.auth_service.AuthService.get_permissions_for_role", return_value=["all"]):
        resp = client.get(f"{settings.API_V1_STR}/users/me/menu-config")
        data = resp.json()
        menu = data["menu"]
        
        for item in menu:
            assert "id" in item
            assert "label" in item
            assert "route" in item
            assert "enabled" in item
            
            if item.get("submenu"):
                for sub in item["submenu"]:
                    assert "id" in sub
                    assert "label" in sub
                    assert "route" in sub
