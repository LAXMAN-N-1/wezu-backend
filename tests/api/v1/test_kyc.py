
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.models.user import User
from app.models.kyc import KYCDocument
from app.main import app

def get_auth_headers(client: TestClient, email: str = "kyc_user@test.com"):
    # 1. Register
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "KYC User",
            "phone_number": "9876543210" if email == "kyc_user@test.com" else "9999999999"
        },
    )
    
    # 2. Login
    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": email,
            "password": "Password123!"
        },
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_submit_kyc_success(client: TestClient, session: Session):
    headers = get_auth_headers(client, email="kyc_success@test.com")
    
    # Create dummy files
    front_content = b"fake_image_content_front"
    back_content = b"fake_image_content_back"
    selfie_content = b"fake_image_content_selfie"
    
    files = [
        ('front_image', ('front.jpg', front_content, 'image/jpeg')),
        ('back_image', ('back.jpg', back_content, 'image/jpeg')),
        ('selfie', ('selfie.jpg', selfie_content, 'image/jpeg'))
    ]
    
    data = {"document_type": "aadhaar", "document_number": "1234-5678-9012"}
    
    response = client.post(
        "/api/v1/users/me/kyc",
        headers=headers,
        data=data,
        files=files
    )
    
    assert response.status_code == 200
    user_data = response.json()
    assert user_data["kyc_status"] == "pending_verification"
    
    # Verify DB records
    user = session.exec(select(User).where(User.email == "kyc_success@test.com")).first()
    assert user.kyc_status == "pending_verification"
    if hasattr(user, "aadhaar_number"):
        assert user.aadhaar_number == "1234-5678-9012"
    
    docs = session.exec(select(KYCDocument).where(KYCDocument.user_id == user.id)).all()
    assert len(docs) == 3 # Front, Back, Selfie
    
    # Verify types
    types = [d.document_type for d in docs]
    assert "aadhaar" in types
    assert "selfie" in types
    
    # Verify metadata
    for doc in docs:
        if doc.document_type == "selfie":
             assert doc.metadata_ is not None and "selfie" in doc.metadata_
        else:
             assert doc.metadata_ is not None and "side" in doc.metadata_

def test_submit_kyc_invalid_type(client: TestClient):
    headers = get_auth_headers(client, email="kyc_fail@test.com")
    
    files = [
        ('front_image', ('front.jpg', b"img", 'image/jpeg')),
        ('selfie', ('selfie.jpg', b"img", 'image/jpeg'))
    ]
    data = {"document_type": "invalid_type", "document_number": "123"}
    
    response = client.post(
        "/api/v1/users/me/kyc",
        headers=headers,
        data=data,
        files=files
    )
    assert response.status_code == 400
    assert "Invalid document type" in response.json()["detail"]
