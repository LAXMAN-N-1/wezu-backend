import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.api import deps
from app.models.admin_user import AdminUser
from app.models.rbac import Role

def create_superuser(session):
    user = session.exec(select(AdminUser).where(AdminUser.email == "admin@roles.com")).first()
    if user:
        return user
    user = AdminUser(
        email="admin@roles.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def test_role_hierarchy_structure(client: TestClient, session: Session):
    admin = create_superuser(session)
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    # Create Hierarchy: Root -> Mid -> Leaf
    root = Role(name="Root", is_active=True)
    session.add(root)
    session.commit()
    
    mid = Role(name="Mid", parent_role_id=root.id, is_active=True)
    session.add(mid)
    session.commit()
    
    leaf = Role(name="Leaf", parent_role_id=mid.id, is_active=True)
    session.add(leaf)
    session.commit()
    
    # Valid orphan (no parent)
    orphan = Role(name="Orphan", is_active=True)
    session.add(orphan)
    session.commit()
    
    # Inactive should be ignored
    inactive = Role(name="Inactive", is_active=False)
    session.add(inactive)
    session.commit()
    
    resp = client.get("/api/v1/admin/rbac/hierarchy")
    assert resp.status_code == 200
    data = resp.json()
    
    # Find Root
    root_node = next((r for r in data if r["name"] == "Root"), None)
    assert root_node is not None
    assert len(root_node["children"]) == 1
    assert root_node["children"][0]["name"] == "Mid"
    
    mid_node = root_node["children"][0]
    assert len(mid_node["children"]) == 1
    assert mid_node["children"][0]["name"] == "Leaf"
    
    # Find Orphan
    orphan_node = next((r for r in data if r["name"] == "Orphan"), None)
    assert orphan_node is not None
    assert len(orphan_node["children"]) == 0
    
    # Ensure Inactive not present (recursively check or check roots)
    # Since it has no parent, it would be a root if present
    inactive_node = next((r for r in data if r["name"] == "Inactive"), None)
    assert inactive_node is None
