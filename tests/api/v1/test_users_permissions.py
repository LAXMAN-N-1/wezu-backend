
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool
from app.main import app
from app.api import deps
from app.models.user import User
from app.models.address import Address
from app.models.rbac import Role, UserRole
import datetime
from app.api import deps

# Fixtures 'session' and 'client' are provided by conftest.py

def create_role(session, name):
    # ... (same)
    role = session.exec(select(Role).where(Role.name == name)).first()
    if not role:
        role = Role(name=name, module="system", action="all") # Minimal fields
        session.add(role)
        session.commit()
        session.refresh(role)
    return role

def create_user_with_role(session, email, role_name, address_state=None):
    # ... (same)
    user = User(email=email, full_name=f"User {email}", is_active=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    
    role = create_role(session, role_name)
    user_role = UserRole(user_id=user.id, role_id=role.id)
    session.add(user_role)
    
    if address_state:
        address = Address(
            user_id=user.id,
            street_address="123 St",
            city="City",
            state=address_state,
            postal_code="110001",
            country="India",
            is_default=True
        )
        session.add(address)
    
    session.commit()
    session.refresh(user)
    return user

def create_role(session, name):
    role = session.exec(select(Role).where(Role.name == name)).first()
    if not role:
        role = Role(name=name, module="system", action="all") # Minimal fields
        session.add(role)
        session.commit()
        session.refresh(role)
    return role

def create_user_with_role(session, email, role_name, address_state=None):
    user = User(email=email, full_name=f"User {email}", is_active=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    
    role = create_role(session, role_name)
    user_role = UserRole(user_id=user.id, role_id=role.id)
    session.add(user_role)
    
    if address_state:
        address = Address(
            user_id=user.id,
            street_address="123 St",
            city="City",
            state=address_state,
            postal_code="110001",
            country="India",
            is_default=True
        )
        session.add(address)
    
    session.commit()
    session.refresh(user)
    return user

def test_regional_manager_access(session, client):
    # Setup
    super_admin = create_user_with_role(session, "admin@example.com", "super_admin")
    manager_delhi = create_user_with_role(session, "manager@delhi.com", "regional_manager", "Delhi")
    user_delhi = create_user_with_role(session, "user@delhi.com", "user", "Delhi")
    user_mumbai = create_user_with_role(session, "user@mumbai.com", "user", "Mumbai")
    user_no_addr = create_user_with_role(session, "noaddr@example.com", "user")

    # Override current_user to simulate login
    
    # 1. Super Admin should see everyone
    app.dependency_overrides[deps.get_current_user] = lambda: super_admin
    resp = client.get(f"/api/v1/users/{user_delhi.id}")
    assert resp.status_code == 200, f"Super Admin failed: {resp.text}"
    
    # 2. Regional Manager (Delhi) -> User (Delhi) : Should Pass
    # Verify setup
    manager_addr_count = session.exec(select(Address).where(Address.user_id == manager_delhi.id)).all()
    with open("debug.log", "w") as f:
        f.write(f"Manager ID: {manager_delhi.id}\n")
        f.write(f"Manager Addresses in DB: {[a.state for a in manager_addr_count]}\n")
        
    app.dependency_overrides[deps.get_current_user] = lambda: manager_delhi
    resp = client.get(f"/api/v1/users/{user_delhi.id}")
    
    with open("debug.log", "a") as f:
        f.write(f"Response Status: {resp.status_code}\n")
        f.write(f"Response Body: {resp.text}\n")
    
    assert resp.status_code == 200, "Manager should access user in same region"
    
    # 3. Regional Manager (Delhi) -> User (Mumbai) : Should Fail
    resp = client.get(f"/api/v1/users/{user_mumbai.id}")
    print(f"Manager (Delhi) -> User (Mumbai): {resp.status_code}")
    assert resp.status_code == 403, "Manager should NOT access user in different region"
    
    # 4. Regional Manager (Delhi) -> User (No Addr) : Should Fail
    resp = client.get(f"/api/v1/users/{user_no_addr.id}")
    print(f"Manager (Delhi) -> User (No Addr): {resp.status_code}")
    assert resp.status_code == 403, "Manager should NOT access user with no address"

if __name__ == "__main__":
    # Manually run the test function to see output
    import sys
    sys.exit(pytest.main(["-v", __file__]))
