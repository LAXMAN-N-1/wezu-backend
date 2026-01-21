"""
Real-time / Event-driven Jobs
These are called from API endpoints or webhooks, not scheduled
"""
from sqlmodel import Session
from datetime import datetime
from app.core.database import engine
import logging

logger = logging.getLogger(__name__)

def process_iot_telemetry(device_id: str, telemetry_data: dict):
    """
    Process IoT device telemetry in real-time
    Called from IoT webhook endpoint
    """
    logger.info(f"Processing IoT telemetry for device {device_id}")
    
    try:
        from app.models.iot import IoTDevice
        from app.models.battery_health_log import BatteryHealthLog
        from app.models.battery import Battery
        
        with Session(engine) as session:
            # Get IoT device
            device = session.exec(
                select(IoTDevice).where(IoTDevice.device_id == device_id)
            ).first()
            
            if not device:
                logger.warning(f"Unknown IoT device: {device_id}")
                return
            
            # Update device status
            device.last_communication = datetime.utcnow()
            device.battery_soc = telemetry_data.get('soc', device.battery_soc)
            device.battery_voltage = telemetry_data.get('voltage', device.battery_voltage)
            device.battery_temperature = telemetry_data.get('temperature', device.battery_temperature)
            session.add(device)
            
            # Get associated battery
            battery = session.get(Battery, device.battery_id)
            
            if battery:
                # Create health log
                health_log = BatteryHealthLog(
                    battery_id=battery.id,
                    soc=telemetry_data.get('soc', 0),
                    voltage=telemetry_data.get('voltage', 0),
                    temperature=telemetry_data.get('temperature', 0),
                    cycle_count=telemetry_data.get('cycle_count', 0),
                    health_percentage=telemetry_data.get('health', 100),
                    timestamp=datetime.utcnow()
                )
                session.add(health_log)
                
                # Check for alerts
                if telemetry_data.get('temperature', 0) > 45:
                    logger.warning(f"High temperature alert for battery {battery.id}")
                    # Send notification
                
                if telemetry_data.get('soc', 100) < 10:
                    logger.warning(f"Low battery alert for battery {battery.id}")
                    # Send notification
            
            session.commit()
            logger.info(f"Telemetry processed for device {device_id}")
            
    except Exception as e:
        logger.error(f"IoT telemetry processing failed: {str(e)}")

def update_gps_tracking(rental_id: int, latitude: float, longitude: float):
    """
    Update GPS tracking for active rental
    Called from mobile app location updates
    """
    logger.debug(f"Updating GPS for rental {rental_id}")
    
    try:
        from app.models.gps_log import GPSTrackingLog
        from app.models.rental import Rental
        
        with Session(engine) as session:
            # Verify rental exists and is active
            rental = session.get(Rental, rental_id)
            if not rental or rental.status != "active":
                return
            
            # Create GPS log
            gps_log = GPSTrackingLog(
                rental_id=rental_id,
                battery_id=rental.battery_id,
                latitude=latitude,
                longitude=longitude,
                timestamp=datetime.utcnow()
            )
            session.add(gps_log)
            session.commit()
            
            # Check geofences in real-time
            from app.workers.hourly_jobs import geofence_violation_detection
            # Could trigger immediate check instead of waiting for hourly job
            
    except Exception as e:
        logger.error(f"GPS tracking update failed: {str(e)}")

def send_push_notification(user_id: int, title: str, body: str, data: dict = None):
    """
    Send push notification to user
    Called from various parts of the application
    """
    logger.info(f"Sending push notification to user {user_id}: {title}")
    
    try:
        from app.models.device import Device
        from app.models.notification import Notification
        from app.services.notification_service import NotificationService
        
        with Session(engine) as session:
            # Get user's devices
            devices = session.exec(
                select(Device).where(Device.user_id == user_id)
            ).all()
            
            if not devices:
                logger.warning(f"No devices found for user {user_id}")
                return
            
            # Create notification record
            notification = Notification(
                user_id=user_id,
                title=title,
                message=body,
                type="push",
                channel="push",
                payload=data,
                status="SENT"
            )
            session.add(notification)
            session.commit()
            
            # Send to FCM (Firebase Cloud Messaging)
            for device in devices:
                if device.fcm_token:
                    # In production, would send to FCM
                    # fcm.send(device.fcm_token, title, body, data)
                    logger.info(f"Push sent to device {device.id}")
            
    except Exception as e:
        logger.error(f"Push notification failed: {str(e)}")

def process_webhook_event(event_type: str, event_data: dict):
    """
    Process webhook events from external services
    (Razorpay, SMS gateway, etc.)
    """
    logger.info(f"Processing webhook event: {event_type}")
    
    try:
        if event_type == "payment.success":
            # Handle successful payment
            from app.models.payment import PaymentTransaction
            
            with Session(engine) as session:
                payment_id = event_data.get('payment_id')
                # Update payment status
                # Send confirmation notification
                pass
        
        elif event_type == "payment.failed":
            # Handle failed payment
            # Send failure notification
            pass
        
        elif event_type == "sms.delivered":
            # Update SMS delivery status
            pass
        
        logger.info(f"Webhook event processed: {event_type}")
        
    except Exception as e:
        logger.error(f"Webhook processing failed: {str(e)}")

from sqlmodel import select
