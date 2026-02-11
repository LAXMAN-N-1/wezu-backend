import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.api import deps
from app.models.user import User
from app.models.address import Address
from app.models.rbac import Role, UserRole

def create_role(session, role_name):
    role = session.exec(select(Role).where(Role.name == role_name)).first()
    if not role:
        role = Role(name=role_name, description=f"{role_name} role")
        session.add(role)
        session.commit()
        session.refresh(role)
    return role

def create_user_with_role(session, email, role_name, address_state=None, name="Test User"):
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        user = User(
            email=email,
            full_name=name,
            phone_number=f"999{hash(email) % 10000000}", # Unique dummy phone
            hashed_password="hashed_password",
            is_active=True,
            kyc_status="verified"
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        
        role = create_role(session, role_name)
        user_role = UserRole(user_id=user.id, role_id=role.id)
        session.add(user_role)
    
    if address_state:
        # Create address
        addr = Address(
            user_id=user.id,
            street_address="123 Test St",
            city="Test City",
            state=address_state,
            postal_code="123456",
            country="India",
            is_default=True
        )
        session.add(addr)
    
    session.commit()
    session.refresh(user)
    return user

def test_search_users_super_admin(client: TestClient, session: Session):
    # Setup
    admin = create_user_with_role(session, "superadmin@search.com", "super_admin", "Delhi")
    user1 = create_user_with_role(session, "user1@search.com", "user", "Mumbai", "User One")
    user2 = create_user_with_role(session, "user2@search.com", "user", "Delhi", "User Two")
    
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    
    # Search by name
    resp = client.get("/api/v1/users/search?name=One")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["users"]) == 1
    assert data["users"][0]["email"] == "user1@search.com"
    
    # Search by region (Delhi)
    resp = client.get("/api/v1/users/search?region=Delhi")
    assert resp.status_code == 200
    data = resp.json()
    # Expect admin (Delhi) and user2 (Delhi)
    assert len(data["users"]) >= 2
    emails = [u["email"] for u in data["users"]]
    assert "user2@search.com" in emails
    assert "user1@search.com" not in emails # user1 is Mumbai
    
    # Test Pagination (Admin sees all)
    auth_resp = client.get("/api/v1/users/search")
    assert auth_resp.status_code == 200
    assert auth_resp.json()["total_count"] >= 3 # admin + user1 + user2

def test_regional_manager_search_restriction(client: TestClient, session: Session):
    # Setup
    manager = create_user_with_role(session, "manager@search.com", "regional_manager", "Karnataka")
    user_karnataka = create_user_with_role(session, "u_ka@search.com", "user", "Karnataka", "Karnataka User")
    user_mumbai = create_user_with_role(session, "u_mh@search.com", "user", "Mumbai", "Mumbai User")
    
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: manager
    
    # CAUTION: The current implementation relies on `User.address` string field in database matching.
    # Our helper creates `Address` objects in `addresses` table.
    # We expect the implementation effectively to use Address table joining.
    # If not, this test helps drive that change.
    
    resp = client.get("/api/v1/users/search")
    assert resp.status_code == 200
    data = resp.json()
    
    emails = [u["email"] for u in data["users"]]
    
    # Manager should see Karnataka user
    assert "u_ka@search.com" in emails
    
    # Manager should NOT see Mumbai user
    assert "u_mh@search.com" not in emails
