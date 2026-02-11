"""
Aadhaar KYC Verification Integration
Handles Aadhaar e-KYC verification
"""
import httpx
from typing import Dict, Any, Optional
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class AadhaarKYCIntegration:
    """Aadhaar e-KYC verification wrapper"""
    
    def __init__(self):
        self.api_key = settings.AADHAAR_API_KEY
        self.base_url = "https://api.aadhaarkyc.io/v1"  # Example URL
    
    async def send_otp(self, aadhaar_number: str) -> Optional[Dict[str, Any]]:
        """
        Send OTP to Aadhaar-linked mobile
        
        Args:
            aadhaar_number: 12-digit Aadhaar number
            
        Returns:
            Transaction details with request_id
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/otp/send",
                    json={"aadhaar_number": aadhaar_number},
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=30
                )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Aadhaar OTP sent: {data.get('request_id')}")
                return data
            else:
                logger.error(f"Aadhaar OTP failed: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Aadhaar OTP request failed: {str(e)}")
            return None
    
    async def verify_otp(
        self,
        request_id: str,
        otp: str
    ) -> Optional[Dict[str, Any]]:
        """
        Verify OTP and get KYC details
        
        Args:
            request_id: Request ID from send_otp
            otp: OTP received
            
        Returns:
            KYC details if successful
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/otp/verify",
                    json={
                        "request_id": request_id,
                        "otp": otp
                    },
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=30
                )
            
            if response.status_code == 200:
                data = response.json()
                logger.info("Aadhaar OTP verified successfully")
                
                # Extract KYC details
                kyc_data = data.get('kyc_data', {})
                return {
                    "name": kyc_data.get('name'),
                    "dob": kyc_data.get('dob'),
                    "gender": kyc_data.get('gender'),
                    "address": {
                        "house": kyc_data.get('house'),
                        "street": kyc_data.get('street'),
                        "landmark": kyc_data.get('landmark'),
                        "locality": kyc_data.get('locality'),
                        "city": kyc_data.get('city'),
                        "state": kyc_data.get('state'),
                        "pincode": kyc_data.get('pincode')
                    },
                    "photo": kyc_data.get('photo'),  # Base64 encoded
                    "verified": True
                }
            else:
                logger.error(f"Aadhaar verification failed: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Aadhaar verification request failed: {str(e)}")
            return None
    
    async def verify_aadhaar(
        self,
        aadhaar_number: str,
        name: str,
        dob: str
    ) -> bool:
        """
        Verify Aadhaar details without OTP (offline verification)
        
        Args:
            aadhaar_number: Aadhaar number
            name: Name to verify
            dob: Date of birth (YYYY-MM-DD)
            
        Returns:
            True if details match
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/verify/offline",
                    json={
                        "aadhaar_number": aadhaar_number,
                        "name": name,
                        "dob": dob
                    },
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=30
                )
            
            if response.status_code == 200:
                data = response.json()
                is_valid = data.get('verified', False)
                logger.info(f"Aadhaar offline verification: {is_valid}")
                return is_valid
            else:
                logger.error(f"Aadhaar offline verification failed: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Aadhaar offline verification failed: {str(e)}")
            return False


# Singleton instance
aadhaar_kyc_integration = AadhaarKYCIntegration()
