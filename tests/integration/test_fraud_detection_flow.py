"""
Integration Tests: Fraud Detection & Security Flow
==================================================
Tests multi-step fraud detection workflows for user and system security.

Workflow 1: Simulate Suspicious Activity → Generate Alert → Admin Investigation → Resolution
Workflow 2: Device Fingerprinting → Duplicate Account Detection → Risk Score Update
Workflow 3: Blacklist Verification (Phone/PAN/GST)
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from datetime import datetime, UTC
import uuid

from app.models.user import User
from app.models.fraud_alert import FraudAlert, FraudAlertStatus
from app.core.security import create_access_token

def get_token(user: User) -> dict:
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}

class TestFraudDetectionFlow:

    @pytest.fixture
    def fraud_env(self, session: Session):
        admin = User(
            email=f"fraud_admin_{uuid.uuid4().hex[:4]}@wezu.com",
            user_type="admin",
            is_active=True,
            is_superuser=True,
            full_name="Fraud Investigator"
        )
        session.add(admin)
        
        customer = User(
            email=f"sus_customer_{uuid.uuid4().hex[:4]}@example.com",
            user_type="customer",
            is_active=True,
            full_name="Suspicious Customer"
        )
        session.add(customer)
        session.commit()
        return {"admin": admin, "customer": customer}

    def test_fraud_alert_lifecycle(self, client: TestClient, session: Session, fraud_env: dict):
        admin = fraud_env["admin"]
        customer = fraud_env["customer"]
        a_headers = get_token(admin)
        
        # 1. Simulate suspicious activity (Manual alert creation as if by backend)
        a_id = f"FD-{uuid.uuid4().hex[:8].upper()}"
        alert = FraudAlert(
            alert_id=a_id,
            user_id=customer.id,
            alert_type="IMPOSSIBLE_TRAVEL",
            risk_score=85.0,
            status=FraudAlertStatus.OPEN,
            meta_data={"locations": ["Bangalore", "Delhi"], "time_diff_mins": 10}
        )
        session.add(alert)
        session.commit()
        session.refresh(alert)
        
        # 2. Admin retrieves alerts
        res = client.get("/api/v1/admin/fraud/alerts", headers=a_headers)
        assert res.status_code == 200
        body = res.json()
        alerts = body if isinstance(body, list) else body.get("data", [])
        assert len(alerts) >= 1
        
        target = next((a for a in alerts if a["alert_id"] == a_id), None)
        assert target is not None
        assert target["status"] == "OPEN"
        inv_res = client.post(f"/api/v1/admin/fraud/alerts/{a_id}/investigate", headers=a_headers)
        assert inv_res.status_code == 200
        
        # 4. Admin adds a note
        note_payload = {"note": "User confirmed they were testing a VPN."}
        note_res = client.post(f"/api/v1/admin/fraud/alerts/{a_id}/note", json=note_payload, headers=a_headers)
        assert note_res.status_code == 200
        
        # 5. Admin resolves alert as false positive
        resolve_payload = {"status": FraudAlertStatus.FALSE_POSITIVE}
        res_res = client.post(f"/api/v1/admin/fraud/alerts/{a_id}/resolve", json=resolve_payload, headers=a_headers)
        assert res_res.status_code == 200
        
        # 6. Verify final status
        session.refresh(alert)
        assert alert.status == FraudAlertStatus.FALSE_POSITIVE

    def test_device_fingerprint_and_risk_score(self, client: TestClient, session: Session, fraud_env: dict):
        customer = fraud_env["customer"]
        c_headers = get_token(customer)
        
        # 1. Submit device fingerprint
        fp_payload = {
            "device_id": "device_123",
            "fingerprint_hash": "hash_abc",
            "device_type": "mobile",
            "os_name": "android",
            "ip_address": "1.2.3.4"
        }
        fp_res = client.post("/api/v1/fraud/device/fingerprint", json=fp_payload, headers=c_headers)
        assert fp_res.status_code == 200
        
        # 2. Check risk score
        score_res = client.get(f"/api/v1/fraud/users/{customer.id}/risk-score", headers=c_headers)
        assert score_res.status_code == 200
        assert "total_score" in score_res.json()
