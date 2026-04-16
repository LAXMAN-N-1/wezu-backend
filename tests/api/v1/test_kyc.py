import pytest
from fastapi import status

# --- POSITIVE CASES ---

def test_submit_kyc_success(client, normal_user_token_headers):
    """Test successful KYC submission by a normal user"""
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
        headers=normal_user_token_headers,
        data=data,
        files=files
    )
    
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["kyc_status"] == "pending_verification"

def test_get_kyc_status(client, normal_user_token_headers):
    """Test retrieving KYC status"""
    response = client.get("/api/v1/users/me/kyc/status", headers=normal_user_token_headers)
    assert response.status_code == status.HTTP_200_OK
    assert "overall_status" in response.json()

# --- NEGATIVE CASES ---

def test_submit_kyc_invalid_type(client, normal_user_token_headers):
    """Test KYC submission with unsupported document type"""
    files = [('front_image', ('front.jpg', b"img", 'image/jpeg')), ('selfie', ('selfie.jpg', b"img", 'image/jpeg'))]
    data = {"document_type": "invalid_type", "document_number": "123"}
    
    response = client.post(
        "/api/v1/users/me/kyc",
        headers=normal_user_token_headers,
        data=data,
        files=files
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

def test_submit_kyc_missing_files(client, normal_user_token_headers):
    """Test KYC submission without mandatory files"""
    data = {"document_type": "pan", "document_number": "ABCDE1234F"}
    response = client.post(
        "/api/v1/users/me/kyc",
        headers=normal_user_token_headers,
        data=data
    )
    # Depending on implementation, might be 422 or 400
    assert response.status_code in [status.HTTP_422_UNPROCESSABLE_ENTITY, status.HTTP_400_BAD_REQUEST]

# --- EDGE CASES ---

def test_submit_kyc_empty_document_number(client, normal_user_token_headers):
    """Test KYC submission with empty document number"""
    files = [('front_image', ('front.jpg', b"img", 'image/jpeg')), ('selfie', ('selfie.jpg', b"img", 'image/jpeg'))]
    data = {"document_type": "pan", "document_number": ""}
    
    response = client.post(
        "/api/v1/users/me/kyc",
        headers=normal_user_token_headers,
        data=data,
        files=files
    )
    assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY]
