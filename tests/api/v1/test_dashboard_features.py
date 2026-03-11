import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.api import deps
from app.models.user import User
from app.models.rbac import Role, UserRole
from app.core.config import settings
from unittest.mock import patch

def create_test_user(session: Session, email: str, role_name: str) -> User:
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        user = User(phone_number='2516995984', email=email, is_active=True)
        session.add(user)
        session.commit()
    
    role = session.exec(select(Role).where(Role.name == role_name)).first()
    if not role:
        role = Role(name=role_name, category="system")
        session.add(role)
        session.commit()
    
    # Check assignment
    existing = session.exec(select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)).first()
    if not existing:
        user_role = UserRole(user_id=user.id, role_id=role.id)
        session.add(user_role)
        session.commit()
    
    session.refresh(user)
    return user

def test_feature_flags_admin(client: TestClient, session: Session):
    user = create_test_user(session, "ff_admin@test.com", "admin")
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: user
    
    resp = client.get(f"{settings.API_V1_STR}/users/me/feature-flags")
    assert resp.status_code == 200
    features = resp.json()["features"]
    
    assert features["dynamic_pricing"] is True
    assert features["advanced_analytics"] is True
    assert features["bulk_transfers"] is True

def test_feature_flags_customer(client: TestClient, session: Session):
    user = create_test_user(session, "ff_cust@test.com", "customer")
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: user
    
    resp = client.get(f"{settings.API_V1_STR}/users/me/feature-flags")
    assert resp.status_code == 200
    features = resp.json()["features"]
    
    assert features["dynamic_pricing"] is True
    assert features["advanced_analytics"] is False
    assert features["bulk_transfers"] is False

def test_dashboard_widgets_admin(client: TestClient, session: Session):
    user = create_test_user(session, "dash_admin@test.com", "admin")
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: user
    
    # Assuming MASTER_DASHBOARD_CONFIG is imported correctly in endpoint
    resp = client.get(f"{settings.API_V1_STR}/users/me/dashboard-widgets")
    assert resp.status_code == 200
    data = resp.json()
    layout = data["layout"]
    
    ids = [w["id"] for w in layout]
    assert "revenue_chart" in ids
    assert "battery_health_map" in ids

def test_dashboard_widgets_customer(client: TestClient, session: Session):
    user = create_test_user(session, "dash_cust@test.com", "customer")
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: user
    
    resp = client.get(f"{settings.API_V1_STR}/users/me/dashboard-widgets")
    assert resp.status_code == 200
    data = resp.json()
    layout = data["layout"]
    
    ids = [w["id"] for w in layout]
    assert "vehicle_soc" in ids
    assert "nearby_stations" in ids
    assert "revenue_chart" not in ids
