import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.api import deps
from app.models.admin_user import AdminUser
from app.models.rbac import Role, Permission, RolePermission

def create_superuser(session):
    user = session.exec(select(AdminUser).where(AdminUser.email == "admin@roles.com")).first()
    if user:
        return user
    user = AdminUser(phone_number='1824009533', 
        email="admin@roles.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def setup_role_hierarchy(session):
    # Perms
    p_parent = Permission(slug="p:parent", module="test", action="read", scope="all")
    p_child = Permission(slug="p:child", module="test", action="write", scope="all")
    session.add(p_parent)
    session.add(p_child)
    session.commit()
    
    # Roles
    parent = Role(name="Parent Role", is_active=True)
    session.add(parent)
    session.commit()
    
    child = Role(name="Child Role", parent_role_id=parent.id, is_active=True)
    session.add(child)
    session.commit()
    
    # Assign
    session.add(RolePermission(role_id=parent.id, permission_id=p_parent.id))
    session.add(RolePermission(role_id=child.id, permission_id=p_child.id))
    session.commit()
    
    return parent, child

def test_get_role_permissions_inheritance(client: TestClient, session: Session):
    admin = create_superuser(session)
    parent_role, child_role = setup_role_hierarchy(session)
    
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    
    resp = client.get(f"/api/v1/admin/rbac/roles/{child_role.id}/permissions")
    assert resp.status_code == 200
    data = resp.json()
    
    # 1. Direct
    assert len(data["direct_permissions"]) == 1
    assert data["direct_permissions"][0]["id"] == "p:child"
    
    # 2. Inherited
    assert len(data["inherited_permissions"]) == 1
    inh_block = data["inherited_permissions"][0]
    assert inh_block["source_role_id"] == parent_role.id
    assert inh_block["permissions"][0]["id"] == "p:parent"
    
    # 3. Grouped (Union)
    modules = data["all_permissions_grouped"]
    assert len(modules) == 1 # Both in 'test' module
    perms = modules[0]["permissions"]
    slugs = [p["id"] for p in perms]
    assert "p:parent" in slugs
    assert "p:child" in slugs

def test_get_role_permissions_orphan(client: TestClient, session: Session):
    admin = create_superuser(session)
    # Just reusing setup but creating standalone
    role = Role(name="Orphan Perm", is_active=True)
    session.add(role)
    session.commit()
    
    p = Permission(slug="p:orphan", module="test", action="x", scope="all")
    session.add(p)
    session.commit()
    session.add(RolePermission(role_id=role.id, permission_id=p.id))
    session.commit()
    
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    
    resp = client.get(f"/api/v1/admin/rbac/roles/{role.id}/permissions")
    data = resp.json()
    
    assert len(data["direct_permissions"]) == 1
    assert len(data["inherited_permissions"]) == 0
    assert len(data["all_permissions_grouped"]) == 1
