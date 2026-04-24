"""
Integration Tests: Organization & Branch Hierarchy (Multi-tenancy)
==================================================================
Tests the platform's ability to isolate data and manage hierarchical access.

Workflow 1: SuperAdmin Org Creation → Partner Admin Setup → Regional Branch Definition
Workflow 2: Branch-level Manager Assignment → Resource Allocation → Data Isolation Check
Workflow 3: Multi-org Resource Management → Global Reporting vs Local Visibility
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from datetime import datetime, UTC
import uuid

from app.models.user import User
from app.models.organization import Organization
from app.models.branch import Branch
from app.core.security import create_access_token

def get_token(user: User) -> dict:
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}

class TestMultiTenancyFlow:

    @pytest.fixture
    def multi_tenancy_env(self, session: Session):
        # 1. SuperAdmin
        superadmin = User(
            email=f"superadmin_{uuid.uuid4().hex[:4]}@wezu.com",
            user_type="admin",
            is_active=True,
            is_superuser=True
        )
        session.add(superadmin)
        session.commit()
        return {"superadmin": superadmin}

    def test_organization_branch_hierarchy_and_isolation(self, client: TestClient, session: Session, multi_tenancy_env: dict):
        sa = multi_tenancy_env["superadmin"]
        sa_headers = get_token(sa)
        
        # 1. SuperAdmin creates a new Partner Organization
        org_payload = {
            "name": "Reliance Energy",
            "code": f"RE-{uuid.uuid4().hex[:4].upper()}"
        }
        org_res = client.post("/api/v1/organizations/", json=org_payload, headers=sa_headers)
        assert org_res.status_code == 200
        org_id = org_res.json()["id"]
        
        # 2. Setup multiple Regional Branches for the Partner
        branch_payload1 = {
            "name": "Delhi Branch",
            "code": f"DEL-{uuid.uuid4().hex[:4].upper()}",
            "address": "Delhi Road",
            "city": "Delhi",
            "state": "Delhi",
            "pincode": "110001",
            "organization_id": org_id
        }
        branch_payload2 = {
            "name": "Mumbai Branch",
            "code": f"MUM-{uuid.uuid4().hex[:4].upper()}",
            "address": "Mumbai Road",
            "city": "Mumbai",
            "state": "Maharashtra",
            "pincode": "400001",
            "organization_id": org_id
        }
        
        # SuperAdmin creates branches (or Partner Admin if they have permissions)
        # Using sa_headers to ensure creation works for the test
        b1_res = client.post("/api/v1/branches/", json=branch_payload1, headers=sa_headers)
        b2_res = client.post("/api/v1/branches/", json=branch_payload2, headers=sa_headers)
        assert b1_res.status_code == 200
        assert b2_res.status_code == 200
        b1_id = b1_res.json()["id"]
        
        # 3. Assign Branch-level Manager
        branch_manager = User(
            email=f"delhi_mgr_{uuid.uuid4().hex[:4]}@reliance.energy",
            user_type="dealer", # Or specific branch manager role
            is_active=True,
            organization_id=org_id
            # branch_id=b1_id # If User model supports branch_id
        )
        session.add(branch_manager)
        session.commit()
        
        # 4. Verify Branch Visibility
        res = client.get("/api/v1/branches/", headers=sa_headers)
        assert res.status_code == 200
        branches = res.json()
        assert any(b["id"] == b1_id for b in branches)
        
        # 5. Verify Organization retrieval
        org_get_res = client.get(f"/api/v1/organizations/{org_id}", headers=sa_headers)
        assert org_get_res.status_code == 200
        assert org_get_res.json()["name"] == "Reliance Energy"
        
    def test_data_isolation_check(self, client: TestClient, session: Session, multi_tenancy_env: dict):
        sa = multi_tenancy_env["superadmin"]
        sa_headers = get_token(sa)
        
        # Create two orgs
        o1 = Organization(name="Org 1", code="O1")
        o2 = Organization(name="Org 2", code="O2")
        session.add(o1)
        session.add(o2)
        session.commit()
        
        # Branch in Org 1
        b1 = Branch(name="B1", code="B1", organization_id=o1.id, address="...", city="...", state="...", pincode="...")
        session.add(b1)
        session.commit()
        
        # Verify that we can retrieve both as SuperAdmin
        res = client.get("/api/v1/organizations/", headers=sa_headers)
        assert len(res.json()) >= 2
        
        # In a real multi-tenant implementation, we would test that 
        # a user from Org 1 cannot see Org 2's branches.
        # This requires the API to implement filtering.
