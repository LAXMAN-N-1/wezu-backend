from __future__ import annotations
"""
GST Verification Integration
Handles GSTIN verification
"""
import httpx
from typing import Dict, Any, Optional
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class GSTVerificationIntegration:
    """GST verification wrapper"""
    
    def __init__(self):
        self.api_key = settings.GST_API_KEY
        self.base_url = "https://api.gstverify.io/v1"  # Example URL
    
    async def verify_gstin(
        self,
        gstin: str
    ) -> Optional[Dict[str, Any]]:
        """
        Verify GSTIN details
        
        Args:
            gstin: GSTIN number
            
        Returns:
            GST details if valid
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/verify/{gstin.upper()}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=30
                )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('valid'):
                    logger.info(f"GSTIN verified: {gstin}")
                    return {
                        "gstin": data.get('gstin'),
                        "legal_name": data.get('legal_name'),
                        "trade_name": data.get('trade_name'),
                        "status": data.get('status'),  # Active, Inactive
                        "address": data.get('address'),
                        "verified": True
                    }
                else:
                    logger.warning(f"GSTIN invalid: {gstin}")
                    return {"verified": False, "message": data.get('message')}
            else:
                logger.error(f"GSTIN verification failed: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"GSTIN verification request failed: {str(e)}")
            return None
    
    def get_gst_returns(
        self,
        gstin: str,
        financial_year: Optional[str] = None
    ) -> Optional[list]:
        """
        Get GST return filing status
        
        Args:
            gstin: GSTIN
            financial_year: FY (e.g., "2023-24")
            
        Returns:
            List of return filing details
        """
        try:
            params = {}
            if financial_year:
                params['fy'] = financial_year
            
            response = requests.get(
                f"{self.base_url}/returns/{gstin.upper()}",
                params=params,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"GST returns retrieved for: {gstin}")
                return data.get('returns', [])
            else:
                logger.error(f"Failed to get GST returns: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"GST returns request failed: {str(e)}")
            return None


# Singleton instance
gst_verification_integration = GSTVerificationIntegration()
