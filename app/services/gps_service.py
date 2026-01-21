"""
GPS Tracking Service
Continuous location tracking and history management
"""
from sqlmodel import Session, select
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from app.models.gps_log import GPSTrackingLog
from app.models.rental import Rental
from app.services.geofence_service import GeofenceService
import logging

logger = logging.getLogger(__name__)

class GPSTrackingService:
    """GPS tracking and location management"""
    
    @staticmethod
    def log_location(
        rental_id: int,
        latitude: float,
        longitude: float,
        accuracy: Optional[float],
        session: Session
    ) -> GPSTrackingLog:
        """
        Log GPS location for rental
        
        Args:
            rental_id: Rental ID
            latitude: Latitude
            longitude: Longitude
            accuracy: GPS accuracy in meters
            session: Database session
            
        Returns:
            GPS log entry
        """
        # Verify rental exists and is active
        rental = session.get(Rental, rental_id)
        if not rental:
            raise ValueError(f"Rental {rental_id} not found")
        
        if rental.status != "active":
            raise ValueError(f"Rental {rental_id} is not active")
        
        # Create GPS log
        gps_log = GPSTrackingLog(
            rental_id=rental_id,
            battery_id=rental.battery_id,
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy,
            timestamp=datetime.utcnow()
        )
        session.add(gps_log)
        session.commit()
        session.refresh(gps_log)
        
        # Check geofence violations
        GPSTrackingService._check_geofence(rental_id, latitude, longitude, session)
        
        return gps_log
    
    @staticmethod
    def get_location_history(
        rental_id: int,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        limit: int,
        session: Session
    ) -> List[GPSTrackingLog]:
        """
        Get location history for rental
        
        Args:
            rental_id: Rental ID
            start_time: Start time filter
            end_time: End time filter
            limit: Maximum number of records
            session: Database session
            
        Returns:
            List of GPS logs
        """
        query = select(GPSTrackingLog).where(GPSTrackingLog.rental_id == rental_id)
        
        if start_time:
            query = query.where(GPSTrackingLog.timestamp >= start_time)
        
        if end_time:
            query = query.where(GPSTrackingLog.timestamp <= end_time)
        
        query = query.order_by(GPSTrackingLog.timestamp.desc()).limit(limit)
        
        return session.exec(query).all()
    
    @staticmethod
    def get_current_location(rental_id: int, session: Session) -> Optional[GPSTrackingLog]:
        """
        Get most recent location for rental
        
        Args:
            rental_id: Rental ID
            session: Database session
            
        Returns:
            Latest GPS log or None
        """
        return session.exec(
            select(GPSTrackingLog)
            .where(GPSTrackingLog.rental_id == rental_id)
            .order_by(GPSTrackingLog.timestamp.desc())
        ).first()
    
    @staticmethod
    def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two coordinates using Haversine formula
        
        Args:
            lat1, lon1: First coordinate
            lat2, lon2: Second coordinate
            
        Returns:
            Distance in kilometers
        """
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371  # Earth's radius in kilometers
        
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
    
    @staticmethod
    def get_travel_path(rental_id: int, session: Session) -> List[Dict]:
        """
        Get complete travel path for rental
        
        Args:
            rental_id: Rental ID
            session: Database session
            
        Returns:
            List of coordinates with timestamps
        """
        logs = session.exec(
            select(GPSTrackingLog)
            .where(GPSTrackingLog.rental_id == rental_id)
            .order_by(GPSTrackingLog.timestamp)
        ).all()
        
        path = []
        total_distance = 0.0
        
        for i, log in enumerate(logs):
            point = {
                "latitude": log.latitude,
                "longitude": log.longitude,
                "timestamp": log.timestamp.isoformat(),
                "accuracy": log.accuracy
            }
            
            if i > 0:
                # Calculate distance from previous point
                distance = GPSTrackingService.calculate_distance(
                    logs[i-1].latitude,
                    logs[i-1].longitude,
                    log.latitude,
                    log.longitude
                )
                total_distance += distance
                point["distance_from_previous"] = distance
            
            path.append(point)
        
        return {
            "path": path,
            "total_distance_km": total_distance,
            "total_points": len(path),
            "start_time": logs[0].timestamp.isoformat() if logs else None,
            "end_time": logs[-1].timestamp.isoformat() if logs else None
        }
    
    @staticmethod
    def _check_geofence(rental_id: int, latitude: float, longitude: float, session: Session):
        """
        Check if location violates any geofences
        
        Args:
            rental_id: Rental ID
            latitude: Current latitude
            longitude: Current longitude
            session: Database session
        """
        from app.models.geofence import Geofence
        
        # Get all active geofences
        geofences = session.exec(
            select(Geofence).where(Geofence.is_active == True)
        ).all()
        
        for geofence in geofences:
            violation = GeofenceService.check_boundary(latitude, longitude, geofence)
            
            if violation:
                # Log violation
                logger.warning(
                    f"Geofence violation detected for rental {rental_id}: "
                    f"{geofence.type} zone '{geofence.name}'"
                )
                
                # In production, trigger alert/notification
                # NotificationService.send_geofence_alert(rental_id, geofence)
    
    @staticmethod
    def get_location_stats(rental_id: int, session: Session) -> Dict:
        """
        Get location statistics for rental
        
        Args:
            rental_id: Rental ID
            session: Database session
            
        Returns:
            Location statistics
        """
        logs = session.exec(
            select(GPSTrackingLog)
            .where(GPSTrackingLog.rental_id == rental_id)
        ).all()
        
        if not logs:
            return {
                "total_points": 0,
                "total_distance_km": 0,
                "average_accuracy": 0
            }
        
        # Calculate total distance
        total_distance = 0.0
        for i in range(1, len(logs)):
            distance = GPSTrackingService.calculate_distance(
                logs[i-1].latitude,
                logs[i-1].longitude,
                logs[i].latitude,
                logs[i].longitude
            )
            total_distance += distance
        
        # Calculate average accuracy
        accuracies = [log.accuracy for log in logs if log.accuracy]
        avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0
        
        return {
            "total_points": len(logs),
            "total_distance_km": round(total_distance, 2),
            "average_accuracy_meters": round(avg_accuracy, 2),
            "tracking_duration_hours": (logs[-1].timestamp - logs[0].timestamp).total_seconds() / 3600
        }
