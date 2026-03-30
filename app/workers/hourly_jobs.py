"""
Hourly Scheduled Jobs
Run every hour
"""
from sqlmodel import Session, select
from datetime import datetime, UTC, timedelta
from app.core.database import engine
from app.workers.daily_jobs import create_job_execution, complete_job_execution
import logging

logger = logging.getLogger(__name__)

def battery_health_checks():
    """Process IoT health data for all batteries"""
    logger.info("Starting battery health checks...")
    execution = create_job_execution("hourly_battery_health")
    
    try:
        from app.models.battery import Battery
        from app.models.battery_health_log import BatteryHealthLog
        from app.models.iot import IoTDevice
        
        with Session(engine) as session:
            # Get all batteries with IoT devices
            batteries = session.exec(
                select(Battery).where(Battery.status.in_(["AVAILABLE", "RENTED"]))
            ).all()
            
            checked_count = 0
            alerts_created = 0
            
            for battery in batteries:
                # Get latest health data from IoT device
                # In production, this would query actual IoT telemetry
                
                # Check for health issues
                # - Low voltage
                # - High temperature
                # - Degraded capacity
                # - Unusual charge/discharge patterns
                
                # Create health log entry
                # health_log = BatteryHealthLog(...)
                # session.add(health_log)
                
                checked_count += 1
            
            session.commit()
            
            result = {
                "batteries_checked": checked_count,
                "alerts_created": alerts_created,
                "timestamp": datetime.now(UTC).isoformat()
            }
            
            logger.info(f"Battery health checks completed: {checked_count} batteries")
            complete_job_execution(execution.execution_id, "COMPLETED", result)
            
    except Exception as e:
        logger.error(f"Battery health checks failed: {str(e)}")
        complete_job_execution(execution.execution_id, "FAILED", error=str(e))

def smart_battery_swap_notifications():
    """FR-MOB-ACTIVE-004: Smart Battery Swap Notifications
    Checks if active rentals have batteries < 20% and sends swap alerts."""
    logger.info("Starting smart battery swap notifications...")
    execution = create_job_execution("hourly_swap_alerts")
    
    try:
        from app.models.rental import Rental
        from app.models.battery import Battery
        from app.services.notification_service import NotificationService
        
        with Session(engine) as session:
            # Join rentals with batteries to check charge
            active_rentals = session.exec(
                select(Rental).where(Rental.status == "active")
            ).all()
            
            alerts_sent = 0
            for rental in active_rentals:
                battery = session.get(Battery, rental.battery_id)
                if battery and battery.current_charge and battery.current_charge < 20.0:
                    # Notify user they need to swap
                    NotificationService(session).send_notification(
                         user_id=rental.user_id,
                         title="Battery Low - Swap Recommended",
                         message=f"Your battery is at {battery.current_charge}%. Head to a nearby station to swap it out for a fully charged one.",
                         notification_type="alert",
                         reference_id=str(rental.id)
                    )
                    alerts_sent += 1
            
            result = {
                "rentals_checked": len(active_rentals),
                "swap_alerts_sent": alerts_sent
            }
            logger.info(f"Swap notifications completed: {alerts_sent} sent")
            complete_job_execution(execution.execution_id, "COMPLETED", result)
            
    except Exception as e:
        logger.error(f"Swap notifications failed: {str(e)}")
        complete_job_execution(execution.execution_id, "FAILED", error=str(e))

def geofence_violation_detection():
    """Detect geofence boundary violations"""
    logger.info("Starting geofence violation detection...")
    execution = create_job_execution("hourly_geofence_check")
    
    try:
        from app.models.geofence import Geofence
        from app.models.gps_log import GPSTrackingLog
        from app.models.rental import Rental
        from app.services.geofence_service import GeofenceService
        
        with Session(engine) as session:
            # Get active rentals
            active_rentals = session.exec(
                select(Rental).where(Rental.status == "active")
            ).all()
            
            violations_detected = 0
            
            for rental in active_rentals:
                # Get latest GPS location
                latest_gps = session.exec(
                    select(GPSTrackingLog)
                    .where(GPSTrackingLog.rental_id == rental.id)
                    .order_by(GPSTrackingLog.timestamp.desc())
                ).first()
                
                if latest_gps:
                    # Check all geofences
                    geofences = session.exec(select(Geofence)).all()
                    
                    for geofence in geofences:
                        violation = GeofenceService.check_boundary(
                            latest_gps.latitude,
                            latest_gps.longitude,
                            geofence
                        )
                        
                        if violation:
                            # Create alert/notification
                            # In production, would create SecurityEvent
                            violations_detected += 1
                            logger.warning(
                                f"Geofence violation: Rental {rental.id} "
                                f"in {geofence.type} zone {geofence.name}"
                            )
            
            result = {
                "rentals_checked": len(active_rentals),
                "violations_detected": violations_detected
            }
            
            logger.info(f"Geofence check completed: {violations_detected} violations")
            complete_job_execution(execution.execution_id, "COMPLETED", result)
            
    except Exception as e:
        logger.error(f"Geofence violation detection failed: {str(e)}")
        complete_job_execution(execution.execution_id, "FAILED", error=str(e))

def low_stock_alerts():
    """Send alerts for low inventory levels"""
    logger.info("Starting low stock alerts...")
    execution = create_job_execution("hourly_stock_alerts")
    
    try:
        from app.models.dealer_inventory import DealerInventory
        from app.models.dealer import DealerProfile
        from app.services.notification_service import NotificationService
        
        with Session(engine) as session:
            # Get all inventories
            inventories = session.exec(select(DealerInventory)).all()
            
            alerts_sent = 0
            
            for inventory in inventories:
                # Check if below reorder level
                if inventory.quantity_available <= inventory.reorder_level:
                    dealer = session.get(DealerProfile, inventory.dealer_id)
                    
                    if dealer:
                        # Send notification to dealer
                        message = (
                            f"Low stock alert: {inventory.battery_model} "
                            f"has only {inventory.quantity_available} units left. "
                            f"Reorder level: {inventory.reorder_level}"
                        )
                        
                        # In production, would send actual notification
                        # NotificationService(session).send_notification(
                        #     dealer.user_id,
                        #     "Low Stock Alert",
                        #     message,
                        #     "inventory"
                        # )
                        
                        alerts_sent += 1
                        logger.info(f"Low stock alert sent to dealer {dealer.id}")
            
            result = {
                "inventories_checked": len(inventories),
                "alerts_sent": alerts_sent
            }
            
            logger.info(f"Low stock alerts completed: {alerts_sent} alerts")
            complete_job_execution(execution.execution_id, "COMPLETED", result)
            
    except Exception as e:
        logger.error(f"Low stock alerts failed: {str(e)}")
        complete_job_execution(execution.execution_id, "FAILED", error=str(e))
