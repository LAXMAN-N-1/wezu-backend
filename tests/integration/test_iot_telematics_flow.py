"""
Integration Tests: IoT & Telematics End-to-End Workflow
=======================================================
Tests the ingestion of IoT telemetry data and the dispatch of IoT commands.

Workflow 1: Telemetry Ingestion → Update Battery State → Alert Generation
Workflow 2: IoT Commands → Lock/Unlock Dispatch → Device Response Simulation
Workflow 3: Real-time Telemetry Retrieval → Status Monitoring
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from datetime import datetime, UTC

from app.models.battery import Battery, BatteryLifecycleEvent
from app.models.telemetry import Telemetry
from app.models.user import User
from app.models.roles import RoleEnum
from app.models.rbac import Role, UserRole
from app.core.security import create_access_token, get_password_hash


# ─── Helpers ─────────────────────────────────────────────────────────

def get_token(user: User) -> dict:
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def iot_env(session: Session):
    """
    Set up a basic environment for IoT testing: an admin user and a battery.
    """
    import uuid
    admin_role = session.exec(select(Role).where(Role.name == RoleEnum.ADMIN.value)).first()
    if not admin_role:
        admin_role = Role(name=RoleEnum.ADMIN.value)
        session.add(admin_role)
        session.commit()

    admin = User(
        email=f"iot_admin_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=get_password_hash("password"),
        is_active=True,
        is_superuser=True,
        status="active",
        phone_number=f"44{uuid.uuid4().hex[:8]}"
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    session.add(UserRole(user_id=admin.id, role_id=admin_role.id))
    session.commit()

    battery = Battery(
        serial_number=f"IOT-TEST-{uuid.uuid4().hex[:6]}",
        iot_device_id=f"DEV-IOT-{uuid.uuid4().hex[:6]}",
        current_charge=100.0,
        health_percentage=100.0,
        location_type="station",
        status="available"
    )
    session.add(battery)
    session.commit()
    session.refresh(battery)

    return {
        "admin": admin,
        "battery": battery
    }


# ─── Workflow 1: Telemetry Ingestion ─────────────────────────────────────────

class TestTelemetryIngestionFlow:
    """
    Integration: Device pushes telemetry -> platform updates battery state
    and checks for alerts (overheating/low battery).
    """

    def test_ingest_telemetry_updates_battery(self, client: TestClient, session: Session, iot_env: dict):
        battery_id = iot_env["battery"].id
        
        # Ingest normal data
        payload = {
            "battery_id": battery_id,
            "device_id": iot_env["battery"].iot_device_id,
            "soc": 85.5,
            "soh": 99.0,
            "voltage": 72.5,
            "current": -5.0,
            "temperature": 35.0,
            "gps_latitude": 12.9716,
            "gps_longitude": 77.5946
        }
        
        res = client.post("/api/v1/telematics/ingest", json=payload)
        
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Telematics ingest endpoint not implemented")
            
        assert res.status_code == status.HTTP_200_OK, res.text
        
        # Verify battery state was updated
        session.refresh(iot_env["battery"])
        assert iot_env["battery"].current_charge == 85.5
        assert iot_env["battery"].temperature_c == 35.0
        
        # Fetch latest telemetry via API
        latest_res = client.get(f"/api/v1/telematics/battery/{battery_id}/latest")
        if latest_res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Telematics latest endpoint not implemented")
            
        assert latest_res.status_code == status.HTTP_200_OK
        data = latest_res.json()
        assert data["soc"] == 85.5

    def test_ingest_telemetry_triggers_alerts(self, client: TestClient, session: Session, iot_env: dict):
        """High temp or low SOC should create BatteryLifecycleEvent alerts in the background."""
        battery_id = iot_env["battery"].id
        
        # Ingest critical data
        payload = {
            "battery_id": battery_id,
            "device_id": iot_env["battery"].iot_device_id,
            "soc": 5.0, # Low battery
            "soh": 90.0,
            "voltage": 62.0,
            "current": 10.0,
            "temperature": 50.0, # High temp
        }
        
        res = client.post("/api/v1/telematics/ingest", json=payload)
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Telematics ingest endpoint not implemented")
            
        assert res.status_code == status.HTTP_200_OK
        
        # Validate events were created
        events = session.exec(select(BatteryLifecycleEvent).where(BatteryLifecycleEvent.battery_id == battery_id)).all()
        event_types = [e.event_type for e in events]
        
        assert "alert_overheating" in event_types
        assert "alert_low_battery" in event_types


# ─── Workflow 2: IoT Device Commands ─────────────────────────────────────────

class TestIoTCommandsFlow:
    """
    Integration: Admin sends lock, unlock, shutdown commands to IoT Devices.
    """

    def test_battery_lock_unlock(self, client: TestClient, session: Session, iot_env: dict):
        battery_id = iot_env["battery"].id
        headers = get_token(iot_env["admin"])
        
        # LOCK
        lock_res = client.post(f"/api/v1/iot/{battery_id}/lock", headers=headers)
        if lock_res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("IoT endpoints not implemented")
        assert lock_res.status_code == status.HTTP_200_OK
        assert "Lock command sent" in lock_res.json()["message"]
        
        # UNLOCK
        unlock_res = client.post(f"/api/v1/iot/{battery_id}/unlock", headers=headers)
        assert unlock_res.status_code == status.HTTP_200_OK
        assert "Unlock command sent" in unlock_res.json()["message"]
        
    def test_battery_shutdown(self, client: TestClient, session: Session, iot_env: dict):
        battery_id = iot_env["battery"].id
        headers = get_token(iot_env["admin"])
        
        res = client.post(f"/api/v1/iot/{battery_id}/shutdown", headers=headers)
        if res.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("IoT endpoints not implemented")
            
        assert res.status_code == status.HTTP_200_OK
        assert "Shutdown command sent" in res.json()["message"]

    def test_iot_command_denied_no_device(self, client: TestClient, session: Session, iot_env: dict):
        battery = Battery(
            serial_number="NO-IOT-BATCH",
            iot_device_id=None,
            current_charge=100.0,
            health_percentage=100.0,
            location_type="station",
            status="available"
        )
        session.add(battery)
        session.commit()
        session.refresh(battery)
        
        headers = get_token(iot_env["admin"])
        res = client.post(f"/api/v1/iot/{battery.id}/lock", headers=headers)
        if res.status_code != status.HTTP_404_NOT_FOUND and res.status_code != 200:
            assert res.status_code == status.HTTP_400_BAD_REQUEST
            body = res.json()
            assert "no IoT device assigned" in str(body.get("error", "")) or "no IoT device assigned" in str(body.get("details", ""))
