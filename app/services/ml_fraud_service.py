"""
ML Fraud Detection Service
Machine learning-based fraud detection and risk scoring
"""
from sqlmodel import Session, select
from typing import Dict, List
from datetime import datetime, UTC, timedelta
from app.models.user import User
from app.models.rental import Rental
from app.models.device_fingerprint import DeviceFingerprint
from app.models.kyc import KYCRecord
import logging

logger = logging.getLogger(__name__)

class MLFraudDetectionService:
    """ML-based fraud detection"""
    
    @staticmethod
    def calculate_risk_score(user_id: int, session: Session) -> Dict:
        """
        Calculate fraud risk score for user using real features.
        """
        from app.ml.feature_store import FeatureStore
        features = FeatureStore.get_user_features(session, user_id)
        if not features:
            return {'risk_score': 100, 'risk_level': 'HIGH', 'factors': ['User metrics not found']}
        
        risk_score = 0
        risk_factors = []
        
        # 1. Payment History (25 points)
        if features["failed_payment_count"] > 3:
            risk_score += 25
            risk_factors.append(f"High payment failure count ({features['failed_payment_count']})")
        elif features["failed_payment_count"] > 0:
            risk_score += 10
            risk_factors.append("Payment history has failures")

        # 2. Overdue Rental Rate (25 points)
        if features["overdue_rate"] > 0.5:
            risk_score += 25
            risk_factors.append(f"Critical overdue rate ({features['overdue_rate']:.0%})")
        elif features["overdue_rate"] > 0.2:
            risk_score += 15
            risk_factors.append(f"Suspicious overdue rate ({features['overdue_rate']:.0%})")

        # 3. Swap Anomalies (20 points)
        if features["avg_swap_interval_days"] > 0 and features["avg_swap_interval_days"] < 1:
            risk_score += 20
            risk_factors.append("Extremely high swap frequency (< 1 day average)")

        # 4. KYC Status (30 points)
        from app.models.kyc import KYCRecord
        kyc = session.exec(select(KYCRecord).where(KYCRecord.user_id == user_id)).first()
        if not kyc or kyc.status.lower() != "verified":
            risk_score += 30
            risk_factors.append("KYC not verified")

        # Determine level
        risk_level = "LOW"
        if risk_score >= 80: risk_level = "HIGH"
        elif risk_score >= 40: risk_level = "MEDIUM"
        
        return {
            'risk_score': min(risk_score, 100),
            'risk_level': risk_level,
            'factors': risk_factors,
            'metrics': features
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
            .where(Rental.created_at >= datetime.now(UTC) - timedelta(days=30))
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
            if rental.start_station_id:
                station = session.get(Station, rental.start_station_id)
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
