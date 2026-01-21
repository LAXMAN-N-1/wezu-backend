"""
ML Fraud Detection Service
Machine learning-based fraud detection and risk scoring
"""
from sqlmodel import Session, select
from typing import Dict, List
from datetime import datetime, timedelta
from app.models.user import User
from app.models.rental import Rental
from app.models.device_fingerprint import DeviceFingerprint
from app.models.kyc_verification import KYCVerification
import logging

logger = logging.getLogger(__name__)

class MLFraudDetectionService:
    """ML-based fraud detection"""
    
    @staticmethod
    def calculate_risk_score(user_id: int, session: Session) -> Dict:
        """
        Calculate fraud risk score for user
        
        Returns:
            Risk score (0-100) and risk factors
        """
        user = session.get(User, user_id)
        if not user:
            return {'risk_score': 100, 'risk_level': 'HIGH', 'factors': ['User not found']}
        
        risk_score = 0
        risk_factors = []
        
        # 1. KYC Verification Status (30 points)
        kyc = session.exec(
            select(KYCVerification)
            .where(KYCVerification.user_id == user_id)
            .where(KYCVerification.status == "VERIFIED")
        ).first()
        
        if not kyc:
            risk_score += 30
            risk_factors.append("KYC not verified")
        elif kyc.verification_score and kyc.verification_score < 70:
            risk_score += 15
            risk_factors.append("Low KYC verification score")
        
        # 2. Account Age (15 points)
        account_age_days = (datetime.utcnow() - user.created_at).days
        if account_age_days < 7:
            risk_score += 15
            risk_factors.append("New account (< 7 days)")
        elif account_age_days < 30:
            risk_score += 8
            risk_factors.append("Recent account (< 30 days)")
        
        # 3. Rental History (20 points)
        rentals = session.exec(
            select(Rental).where(Rental.user_id == user_id)
        ).all()
        
        if len(rentals) == 0:
            risk_score += 20
            risk_factors.append("No rental history")
        else:
            # Check for late returns
            late_returns = sum(1 for r in rentals if r.status == "overdue")
            if late_returns > 0:
                late_rate = late_returns / len(rentals)
                if late_rate > 0.3:
                    risk_score += 15
                    risk_factors.append(f"High late return rate ({late_rate:.0%})")
        
        # 4. Device Fingerprinting (20 points)
        devices = session.exec(
            select(DeviceFingerprint).where(DeviceFingerprint.user_id == user_id)
        ).all()
        
        if len(devices) > 5:
            risk_score += 20
            risk_factors.append(f"Multiple devices ({len(devices)})")
        
        # Check for suspicious device patterns
        for device in devices:
            if device.is_emulator or device.is_rooted:
                risk_score += 15
                risk_factors.append("Emulator or rooted device detected")
                break
        
        # 5. Transaction Patterns (15 points)
        from app.models.financial import Transaction
        
        # Check for failed transactions
        failed_txns = session.exec(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .where(Transaction.status == "FAILED")
        ).all()
        
        if len(failed_txns) > 3:
            risk_score += 15
            risk_factors.append(f"Multiple failed transactions ({len(failed_txns)})")
        
        # Determine risk level
        if risk_score >= 70:
            risk_level = "HIGH"
        elif risk_score >= 40:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        return {
            'risk_score': min(risk_score, 100),
            'risk_level': risk_level,
            'factors': risk_factors,
            'kyc_verified': kyc is not None,
            'account_age_days': account_age_days,
            'total_rentals': len(rentals)
        }
    
    @staticmethod
    def detect_anomalies(user_id: int, session: Session) -> List[Dict]:
        """
        Detect behavioral anomalies
        
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        # Get recent rentals
        recent_rentals = session.exec(
            select(Rental)
            .where(Rental.user_id == user_id)
            .where(Rental.created_at >= datetime.utcnow() - timedelta(days=30))
            .order_by(Rental.created_at.desc())
        ).all()
        
        if not recent_rentals:
            return anomalies
        
        # 1. Unusual rental frequency
        if len(recent_rentals) > 20:  # More than 20 rentals in 30 days
            anomalies.append({
                'type': 'HIGH_FREQUENCY',
                'severity': 'MEDIUM',
                'description': f'Unusually high rental frequency: {len(recent_rentals)} rentals in 30 days'
            })
        
        # 2. Rapid succession rentals (< 1 hour apart)
        for i in range(len(recent_rentals) - 1):
            time_diff = (recent_rentals[i].created_at - recent_rentals[i+1].created_at).total_seconds() / 3600
            if time_diff < 1:
                anomalies.append({
                    'type': 'RAPID_SUCCESSION',
                    'severity': 'HIGH',
                    'description': f'Rentals created {time_diff:.1f} hours apart'
                })
                break
        
        # 3. Unusual locations (different cities in short time)
        from app.models.station import Station
        
        stations_visited = set()
        for rental in recent_rentals[:10]:  # Last 10 rentals
            if rental.pickup_station_id:
                station = session.get(Station, rental.pickup_station_id)
                if station:
                    stations_visited.add(station.city)
        
        if len(stations_visited) > 5:
            anomalies.append({
                'type': 'MULTIPLE_LOCATIONS',
                'severity': 'MEDIUM',
                'description': f'Rentals from {len(stations_visited)} different cities'
            })
        
        # 4. Late night activity pattern
        late_night_count = sum(
            1 for r in recent_rentals
            if r.created_at.hour >= 23 or r.created_at.hour <= 5
        )
        
        if late_night_count > len(recent_rentals) * 0.7:
            anomalies.append({
                'type': 'LATE_NIGHT_PATTERN',
                'severity': 'LOW',
                'description': f'{late_night_count} late night rentals detected'
            })
        
        return anomalies
    
    @staticmethod
    def should_block_transaction(user_id: int, session: Session) -> Dict:
        """
        Determine if transaction should be blocked
        
        Returns:
            Decision and reason
        """
        risk_assessment = MLFraudDetectionService.calculate_risk_score(user_id, session)
        anomalies = MLFraudDetectionService.detect_anomalies(user_id, session)
        
        # Block if high risk
        if risk_assessment['risk_score'] >= 80:
            return {
                'should_block': True,
                'reason': 'High fraud risk score',
                'risk_score': risk_assessment['risk_score']
            }
        
        # Block if critical anomalies
        critical_anomalies = [a for a in anomalies if a['severity'] == 'HIGH']
        if len(critical_anomalies) >= 2:
            return {
                'should_block': True,
                'reason': 'Multiple critical anomalies detected',
                'anomalies': critical_anomalies
            }
        
        # Require manual review if medium-high risk
        if risk_assessment['risk_score'] >= 60:
            return {
                'should_block': False,
                'requires_review': True,
                'reason': 'Medium-high risk, manual review recommended',
                'risk_score': risk_assessment['risk_score']
            }
        
        return {
            'should_block': False,
            'requires_review': False,
            'risk_score': risk_assessment['risk_score']
        }
