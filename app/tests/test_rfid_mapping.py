import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool
import uuid

from app.main import app
from app.core.database import get_db
from app.api.deps import get_current_active_admin
from app.models.battery import Battery, RFIDMapping
from app.models.user import User

# Setup in-memory SQLite for testing
# Note: Since the real app uses schemas (inventory.batteries), 
# SQLite might need adjustments or we mock the session differently.
# For simplicity in this environment, we'll focus on the logic.
engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)

@pytest.fixture(name="session")
def session_fixture():
    # We strip schemas for SQLite testing if necessary, but SQLModel usually handles it 
    # if we don't fixate on exact naming in tests.
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)

@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    def get_admin_override():
        return User(id=1, email="admin@wezu.com", is_superuser=True, user_type="admin")

    app.dependency_overrides[get_db] = get_session_override
    app.dependency_overrides[get_current_active_admin] = get_admin_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

def test_rfid_mapping_success(client: TestClient, session: Session):
    # 1. Create a battery
    battery_serial = "WEZU-BAT-TEST-001"
    battery = Battery(serial_number=battery_serial, status="available")
    session.add(battery)
    session.commit()

    # 2. Map RFID tag
    rfid_tag = "RFID-TAG-001"
    response = client.post(
        "/api/admin/batteries/rfid-map",
        json={"rfid_tag": rfid_tag, "battery_serial": battery_serial}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["serial_number"] == battery_serial

    # 3. Verify in DB
    mapping = session.exec(select(RFIDMapping).where(RFIDMapping.rfid_tag == rfid_tag)).first()
    assert mapping is not None
    assert mapping.battery_serial == battery_serial

def test_rfid_mapping_duplicate_tag(client: TestClient, session: Session):
    # 1. Create a battery and an existing mapping
    battery_serial = "WEZU-BAT-TEST-002"
    battery = Battery(serial_number=battery_serial, status="available")
    rfid_tag = "RFID-TAG-EXISTING"
    mapping = RFIDMapping(rfid_tag=rfid_tag, battery_serial=battery_serial)
    session.add(battery)
    session.add(mapping)
    session.commit()

    # 2. Attempt to map the same tag to another serial (even if battery exists)
    other_battery = Battery(serial_number="WEZU-BAT-TEST-003", status="available")
    session.add(other_battery)
    session.commit()
    
    response = client.post(
        "/api/admin/batteries/rfid-map",
        json={"rfid_tag": rfid_tag, "battery_serial": "WEZU-BAT-TEST-003"}
    )

    assert response.status_code == 409
    assert "already mapped" in response.json()["detail"]

def test_rfid_mapping_missing_battery(client: TestClient):
    # Map tag to non-existent battery
    response = client.post(
        "/api/admin/batteries/rfid-map",
        json={"rfid_tag": "NEW-TAG", "battery_serial": "NON-EXISTENT"}
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]
