import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.api import deps
from app.models.admin_user import AdminUser
from app.models.user import User
from app.models.rbac import UserAccessPath

def create_superuser_path(session):
    user = session.exec(select(AdminUser).where(AdminUser.email == "admin@path.com")).first()
    if user:
        return user
    user = AdminUser(
        email="admin@path.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def test_assign_access_path(client: TestClient, session: Session):
    admin = create_superuser_path(session)
    
    # Target User
    user = User(email="path_user@test.com", is_active=True)
    session.add(user)
    session.commit()
    
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    # Action
    payload = {
        "path_pattern": "Asia/India/Telangana/%",
        "access_level": "manage"
    }
    
    resp = client.post(f"/api/v1/admin/rbac/users/{user.id}/access-paths", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["path_pattern"] == "Asia/India/Telangana/%"
    assert data["access_level"] == "manage"
    assert data["user_id"] == user.id
    
    # Verify DB
    path = session.exec(select(UserAccessPath).where(UserAccessPath.user_id == user.id)).first()
    assert path is not None
    assert path.path_pattern == "Asia/India/Telangana/%"
    assert path.created_by == admin.id

def test_assign_access_path_invalid_level(client: TestClient, session: Session):
    admin = create_superuser_path(session)
    user = User(email="path_invalid@test.com", is_active=True)
    session.add(user)
    session.commit()
    
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    payload = {
        "path_pattern": "Global/%",
        "access_level": "super_god_mode"
    }
    
    resp = client.post(f"/api/v1/admin/rbac/users/{user.id}/access-paths", json=payload)
    assert resp.status_code == 422 # Validator should catch enum or logic check if manually implemented

def test_get_user_access_paths(client: TestClient, session: Session):
    admin = create_superuser_path(session)
    user = User(email="path_get@test.com", is_active=True)
    session.add(user)
    session.commit()
    
    # Create Path
    path = UserAccessPath(
        user_id=user.id,
        path_pattern="Region/A/%",
        access_level="view",
        created_by=admin.id
    )
    session.add(path)
    session.commit()
    
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    resp = client.get(f"/api/v1/admin/rbac/users/{user.id}/access-paths")
    assert resp.status_code == 200
    data = resp.json()
    
    assert len(data) == 1
    assert data[0]["path_pattern"] == "Region/A/%"
    assert data[0]["created_by"] == admin.id
    assert data[0]["created_by_name"] == admin.email

def test_update_access_path(client: TestClient, session: Session):
    admin = create_superuser_path(session)
    user = User(email="path_update@test.com", is_active=True)
    session.add(user)
    session.commit()
    
    path = UserAccessPath(
        user_id=user.id,
        path_pattern="Region/B/%",
        access_level="view",
        created_by=admin.id
    )
    session.add(path)
    session.commit()
    
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    payload = {"access_level": "admin"}
    resp = client.put(f"/api/v1/admin/rbac/users/{user.id}/access-paths/{path.id}", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_level"] == "admin"
    
    # Verify DB
    session.refresh(path)
    assert path.access_level == "admin"

def test_remove_access_path(client: TestClient, session: Session):
    admin = create_superuser_path(session)
    user = User(email="path_del@test.com", is_active=True)
    session.add(user)
    session.commit()
    
    path = UserAccessPath(
        user_id=user.id,
        path_pattern="Region/C/%",
        access_level="view",
        created_by=admin.id
    )
    session.add(path)
    session.commit()
    
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    resp = client.delete(f"/api/v1/admin/rbac/users/{user.id}/access-paths/{path.id}")
    assert resp.status_code == 200
    
    # Verify DB
    path_check = session.get(UserAccessPath, path.id)
    assert path_check is None
