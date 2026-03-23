import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.models.dealer_kyc import DealerKYCApplication, KYCStateConfig, KYCStateTransition
from app.models.roles import RoleEnum
from app.models.user import User
from app.models.rbac import Role, UserRole

@pytest.fixture
def mock_users_and_roles(session: Session):
    roles = {}
    for r_name in [RoleEnum.ADMIN.value, RoleEnum.DEALER.value, RoleEnum.DRIVER.value, RoleEnum.CUSTOMER.value]:
        role = session.exec(select(Role).where(Role.name == r_name)).first()
        if not role:
            role = Role(name=r_name)
            session.add(role)
        roles[r_name] = role
    session.commit()
    
    users_data = {
        RoleEnum.ADMIN.value: User(email="admin@test.com", hashed_password="pw", is_active=True),
        RoleEnum.DEALER.value: User(email="dealer@test.com", hashed_password="pw", is_active=True),
        RoleEnum.DRIVER.value: User(email="driver@test.com", hashed_password="pw", is_active=True),
        RoleEnum.CUSTOMER.value: User(email="customer@test.com", hashed_password="pw", is_active=True),
    }
    
    for r_name, user in users_data.items():
        session.add(user)
        session.commit()
        session.refresh(user)
        link = UserRole(user_id=user.id, role_id=roles[r_name].id)
        session.add(link)
    session.commit()
    
    return users_data


def get_override_token(user: User):
    from app.core.security import create_access_token
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}

class TestDealerKYC:
    def test_submit_documents_success(self, client: TestClient, session: Session, mock_users_and_roles):
        dealer = mock_users_and_roles[RoleEnum.DEALER.value]
        headers = get_override_token(dealer)
        
        # We need mock files
        files = {
            "pan_doc_file": ("pan.pdf", b"dummy pdf content", "application/pdf"),
            "gst_doc_file": ("gst.jpg", b"dummy jpg content", "image/jpeg"),
            "reg_cert_file": ("reg.pdf", b"dummy pdf content", "application/pdf")
        }
        data = {
            "company_name": "Test Company",
            "pan_number": "ABCDE1234F",
            "gst_number": "22AAAAA0000A1Z5",
            "bank_details_json": '{"acc": "123"}'
        }
        
        response = client.post("/api/v1/dealer-kyc/kyc/documents", headers=headers, data=data, files=files)
        assert response.status_code == 200
        
        # Verify DB
        app = session.exec(select(DealerKYCApplication).where(DealerKYCApplication.user_id == dealer.id)).first()
        assert app is not None
        assert app.application_state == KYCStateConfig.DOC_SUBMITTED
        assert app.company_name == "Test Company"
        
        # Verify Audit Log
        transitions = session.exec(select(KYCStateTransition).where(KYCStateTransition.application_id == app.id)).all()
        assert len(transitions) == 1
        assert transitions[0].to_state == KYCStateConfig.DOC_SUBMITTED.value

    def test_submit_documents_invalid_file_type(self, client: TestClient, session: Session, mock_users_and_roles):
        dealer = mock_users_and_roles[RoleEnum.DEALER.value]
        # Delete existing application if it exists from previous test depending on test isolation
        app = session.exec(select(DealerKYCApplication).where(DealerKYCApplication.user_id == dealer.id)).first()
        if app:
            session.delete(app)
            session.commit()

        headers = get_override_token(dealer)
        
        files = {
            "pan_doc_file": ("pan.exe", b"dummy exe content", "application/x-msdownload"),
            "gst_doc_file": ("gst.jpg", b"dummy jpg content", "image/jpeg"),
            "reg_cert_file": ("reg.pdf", b"dummy pdf content", "application/pdf")
        }
        data = {
            "company_name": "Test Company",
            "pan_number": "ABCDE1234F",
            "gst_number": "22AAAAA0000A1Z5",
            "bank_details_json": '{"acc": "123"}'
        }
        
        response = client.post("/api/v1/dealer-kyc/kyc/documents", headers=headers, data=data, files=files)
        assert response.status_code == 400
        assert "Invalid file type" in response.text

    def test_run_auto_checks_success(self, client: TestClient, session: Session, mock_users_and_roles):
        dealer = mock_users_and_roles[RoleEnum.DEALER.value]
        
        # Ensure we are in DOC_SUBMITTED state
        app = session.exec(select(DealerKYCApplication).where(DealerKYCApplication.user_id == dealer.id)).first()
        if not app:
            app = DealerKYCApplication(
                user_id=dealer.id,
                company_name="Test Company",
                pan_number="ABCDE1234F",
                gst_number="22AAAAA0000A1Z5",
                bank_details_json='{"acc": "123"}',
                application_state=KYCStateConfig.DOC_SUBMITTED
            )
            session.add(app)
            session.commit()
        else:
            app.application_state = KYCStateConfig.DOC_SUBMITTED
            app.pan_number = "ABCDE1234F" # Ensure it passes
            session.commit()

        headers = get_override_token(dealer)
        response = client.post("/api/v1/dealer-kyc/kyc/trigger-auto-checks", headers=headers)
        assert response.status_code == 200
        
        # Verify DB changed to MANUAL_REVIEW
        session.refresh(app)
        assert app.application_state == KYCStateConfig.MANUAL_REVIEW
        
    def test_run_auto_checks_failure(self, client: TestClient, session: Session, mock_users_and_roles):
        dealer = mock_users_and_roles[RoleEnum.DEALER.value]
        headers = get_override_token(dealer)
        
        # Set explicitly to fail by using FAILED_PAN
        app = session.exec(select(DealerKYCApplication).where(DealerKYCApplication.user_id == dealer.id)).first()
        if not app:
            app = DealerKYCApplication(
                user_id=dealer.id,
                company_name="Test Company",
                pan_number="FAILED_PAN",
                gst_number="22AAAAA0000A1Z5",
                bank_details_json='{"acc": "123"}',
                application_state=KYCStateConfig.DOC_SUBMITTED
            )
            session.add(app)
        else:
            app.application_state = KYCStateConfig.DOC_SUBMITTED
            app.pan_number = "FAILED_PAN"
        
        session.commit()
        
        response = client.post("/api/v1/dealer-kyc/kyc/trigger-auto-checks", headers=headers)
        assert response.status_code == 200 # The endpoint returns 200 with the app state
        
        session.refresh(app)
        assert app.application_state == KYCStateConfig.REJECTED

    def test_admin_pending_dealers_and_review(self, client: TestClient, session: Session, mock_users_and_roles):
        dealer = mock_users_and_roles[RoleEnum.DEALER.value]
        admin = mock_users_and_roles[RoleEnum.ADMIN.value]
        admin_headers = get_override_token(admin)
        
        # Setup dealer in MANUAL_REVIEW
        app = session.exec(select(DealerKYCApplication).where(DealerKYCApplication.user_id == dealer.id)).first()
        if not app:
            app = DealerKYCApplication(
                user_id=dealer.id,
                company_name="Test Company",
                pan_number="ABCDE1234F",
                gst_number="22AAAAA0000A1Z5",
                bank_details_json='{"acc": "123"}',
                application_state=KYCStateConfig.MANUAL_REVIEW
            )
            session.add(app)
        else:
            app.application_state = KYCStateConfig.MANUAL_REVIEW
        session.commit()
        
        # 1. Get Pending
        response = client.get("/api/v1/dealer-kyc/admin/dealers/pending", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) >= 1
        assert str(app.id) in [str(d["id"]) for d in data]
        
        # 2. Approve
        review_data = {
            "action": "approve",
            "comments": "Looks good"
        }
        response = client.post(f"/api/v1/dealer-kyc/admin/dealers/{app.id}/review", headers=admin_headers, json=review_data)
        assert response.status_code == 200
        
        session.refresh(app)
        # Assuming activate_dealer is chained
        assert app.application_state == KYCStateConfig.ACTIVE
        assert app.admin_comments == "Looks good"
        
        # Verify transitions recorded
        transitions = session.exec(select(KYCStateTransition).where(KYCStateTransition.application_id == app.id).order_by(KYCStateTransition.id.desc())).all()
        assert transitions[0].to_state == KYCStateConfig.ACTIVE.value
        assert transitions[1].to_state == KYCStateConfig.APPROVED.value
