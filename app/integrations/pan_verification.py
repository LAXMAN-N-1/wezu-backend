from __future__ import annotations
"""
PAN Verification Integration
Handles PAN card verification
"""
import httpx
from typing import Dict, Any, Optional
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class PANVerificationIntegration:
    """PAN verification wrapper"""
    
    def __init__(self):
        self.api_key = settings.PAN_API_KEY
        self.base_url = "https://api.panverification.io/v1"  # Example URL
    
    async def verify_pan(
        self,
        pan_number: str,
        name: Optional[str] = None,
        dob: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Verify PAN card details
        
        Args:
            pan_number: 10-character PAN number
            name: Name to verify (optional)
            dob: Date of birth (optional, YYYY-MM-DD)
            
        Returns:
            PAN details if valid
        """
        try:
            payload = {"pan_number": pan_number.upper()}
            if name:
                payload["name"] = name
            if dob:
                payload["dob"] = dob
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/verify",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=30
                )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('valid'):
                    logger.info(f"PAN verified: {pan_number}")
                    return {
                        "pan_number": data.get('pan_number'),
                        "name": data.get('name'),
                        "category": data.get('category'),  # Individual, Company, etc.
                        "status": data.get('status'),  # Active, Inactive
                        "verified": True
                    }
                else:
                    logger.warning(f"PAN invalid: {pan_number}")
                    return {"verified": False, "message": data.get('message')}
            else:
                logger.error(f"PAN verification failed: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"PAN verification request failed: {str(e)}")
            return None
    
    async def get_pan_details(self, pan_number: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed PAN information
        
        Args:
            pan_number: PAN number
            
        Returns:
            Detailed PAN information
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/details/{pan_number.upper()}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=30
                )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"PAN details retrieved: {pan_number}")
                return data
            else:
                logger.error(f"Failed to get PAN details: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"PAN details request failed: {str(e)}")
            return None


# Singleton instance
pan_verification_integration = PANVerificationIntegration()
