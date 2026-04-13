import traceback
from fastapi.testclient import TestClient
from app.main import app
from app.api import deps
from app.models.user import User, UserStatus, UserType

def override_superuser():
    return User(id=1, email="admin@example.com", is_superuser=True, status=UserStatus.ACTIVE, user_type=UserType.ADMIN)

app.dependency_overrides[deps.get_current_active_superuser] = override_superuser
client = TestClient(app, raise_server_exceptions=True)

endpoints = [
    "/api/v1/admin/analytics/fraud-risks",
    "/api/v1/admin/analytics/suspensions",
    "/api/v1/admin/analytics/invite-links"
]

for ep in endpoints:
    print(f"\n--- Testing {ep} ---")
    try:
        response = client.get(ep)
        print(f"Status: {response.status_code}")
    except Exception as e:
        print(f"Exception on {ep}:")
        traceback.print_exc()
