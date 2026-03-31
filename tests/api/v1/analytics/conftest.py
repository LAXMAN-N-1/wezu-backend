import pytest
from httpx import AsyncClient
from sqlmodel import Session
from app.models.user import User

# The root conftest.py implicitly provides `client`, `session`, and `normal_user` fixtures
# We can add any analytics-specific fixtures here.

@pytest.fixture(name="analytics_admin_user")
def analytics_admin_user_fixture(session: Session) -> User:
    """Fixture providing a user with 'admin' access (superuser)."""
    from app.core.security import get_password_hash
    user = User(
        email="analytics_admin@example.com",
        phone_number="555-ADMIN",
        hashed_password=get_password_hash("password"),
        full_name="Analytics Admin User",
        is_active=True,
        is_superuser=True  # Ensure superuser access to bypass RBAC
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

@pytest.fixture(name="mock_admin_token_headers")
def mock_admin_token_headers_fixture(client, analytics_admin_user: User) -> dict[str, str]:
    """Fixture providing JWT token headers for the analytics admin."""
    from app.core.security import create_access_token
    access_token = create_access_token(
        subject=str(analytics_admin_user.id)
    )
    return {"Authorization": f"Bearer {access_token}"}

@pytest.fixture(name="mock_customer_token_headers")
def mock_customer_token_headers_fixture(client, normal_user: User, session: Session) -> dict[str, str]:
    """Fixture providing JWT token headers for a standard customer with the 'customer' role."""
    from app.core.security import create_access_token
    from app.models.rbac import Role, UserRole

    # Create the 'customer' role if it doesn't exist
    customer_role = session.query(Role).filter(Role.name == "customer").first()
    if not customer_role:
        customer_role = Role(name="customer", description="Customer role", category="customer")
        session.add(customer_role)
        session.commit()
        session.refresh(customer_role)

    # Assign the role to the normal_user
    if normal_user.role_id != customer_role.id:
        normal_user.role_id = customer_role.id
        session.add(normal_user)
        session.commit()

    # Refresh user to load roles relationship
    session.refresh(normal_user)

    access_token = create_access_token(
        subject=str(normal_user.id)
    )
    return {"Authorization": f"Bearer {access_token}"}

