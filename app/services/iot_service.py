from __future__ import annotations
import json
import logging
from datetime import datetime, timezone; UTC = timezone.utc
import random
import paho.mqtt.client as mqtt
from sqlmodel import Session, select
from app.core.database import engine
from app.core.config import settings
from app.models.gps_log import GPSTrackingLog
from app.models.battery_health_log import BatteryHealthLog
from app.models.iot import IoTDevice, DeviceCommand
from app.models.battery import Battery
# from app.services.geofence_service import GeofenceService

logger = logging.getLogger(__name__)

class IoTService:
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        client = mqtt.Client()

    @staticmethod
    def on_connect(client, userdata, flags, rc):
        logger.info(f"Connected to MQTT Broker with result code {rc}")
        # Subscribe to device topics
        client.subscribe("wezu/devices/+/telemetry")
        client.subscribe("wezu/devices/+/status")
        client.subscribe("wezu/devices/+/response")

    @staticmethod
    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            topic_parts = msg.topic.split("/")
            # Topic format: wezu/devices/{device_id}/{type}
            if len(topic_parts) < 4:
                return

            device_id = topic_parts[2]
            msg_type = topic_parts[3]

            with Session(engine) as session:
                device = session.exec(select(IoTDevice).where(IoTDevice.device_id == device_id)).first()
                if not device:
                    logger.warning(f"Received message from unknown device: {device_id}")
                    return

                # Update Heartbeat
                device.last_heartbeat = datetime.now(UTC)
                device.status = "online"
                device.last_ip_address = payload.get("ip", device.last_ip_address)
                session.add(device)
                session.commit()
                session.refresh(device)

                if msg_type == "telemetry":
                    IoTService.process_telemetry(session, device, payload)
                elif msg_type == "response":
                    IoTService.process_command_response(session, device, payload)
                elif msg_type == "status":
                    pass # Handled by heartbeat update above

        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    @staticmethod
    def process_telemetry(session: Session, device: IoTDevice, data: dict):
        if not device.battery_id:
            return

        # 1. Save Telemetry (TimescaleDB Hypertable)
        from app.models.iot import Telemetry
        telemetry = Telemetry(
            battery_id=device.battery_id,
            timestamp=datetime.now(UTC),
            soc=data.get("soc", 0.0),
            soh=data.get("soh", 100.0),
            voltage=data.get("voltage", 0.0),
            current=data.get("current", 0.0),
            temperature=data.get("temp", 0.0),
            latitude=data.get("lat"),
            longitude=data.get("lng"),
            speed=data.get("speed"),
            status_flags=json.dumps(data.get("flags", {}))
        )
        session.add(telemetry)

        # 2. Update Battery Current State
        battery = session.get(Battery, device.battery_id)
        if battery:
            battery.current_charge = telemetry.soc
            battery.health_percentage = telemetry.soh
            battery.temperature_c = telemetry.temperature
            battery.last_telemetry_at = telemetry.timestamp
            session.add(battery)

            # 3. Link to Active Rental (for logistics/monitoring)
            from app.models.rental import Rental
            active_rental = session.exec(
                select(Rental).where(
                    Rental.battery_id == battery.id,
                    Rental.status == "active"
                )
            ).first()
            
            if active_rental:
                if not active_rental.metadata:
                    active_rental.metadata = "{}"
                
                try:
                    meta = json.loads(active_rental.metadata)
                    meta["last_soc"] = telemetry.soc
                    meta["last_lat"] = telemetry.latitude
                    meta["last_lng"] = telemetry.longitude
                    active_rental.metadata = json.dumps(meta)
                except Exception:
                    logger.warning("iot.rental_metadata_update_failed rental_id=%s", active_rental.id, exc_info=True)
                
                session.add(active_rental)

        session.commit()

    @staticmethod
    def process_command_response(session: Session, device: IoTDevice, data: dict):
        command_id = data.get("command_id")
        if command_id:
            cmd = session.get(DeviceCommand, command_id)
            if cmd:
                cmd.status = data.get("status", "executed")
                cmd.executed_at = datetime.now(UTC)
                cmd.response_data = json.dumps(data)
                session.add(cmd)
                session.commit()

    @staticmethod
    def send_command(device_id: str, command_type: str, payload: dict) -> DeviceCommand:
        with Session(engine) as session:
            device = session.exec(select(IoTDevice).where(IoTDevice.device_id == device_id)).first()
            if not device:
                raise ValueError("Device not found")

            # create command record
            cmd = DeviceCommand(
                device_id=device.id,
                command_type=command_type,
                payload=json.dumps(payload),
                status="queued"
            )
            session.add(cmd)
            session.commit()
            session.refresh(cmd)
            
            # Publish to MQTT
            topic = f"wezu/devices/{device_id}/command"
            msg_payload = {
                "command_id": cmd.id,
                "type": command_type,
                "params": payload,
                "timestamp": datetime.now(UTC).isoformat()
            }
            IoTService.client.publish(topic, json.dumps(msg_payload))
            
            cmd.status = "sent"
            cmd.sent_at = datetime.now(UTC)
            session.add(cmd)
            session.commit()
            return cmd

    @staticmethod
    def register_device(device_id: str, device_type: str, battery_id: int = None) -> IoTDevice:
        with Session(engine) as session:
            device = IoTDevice(
                device_id=device_id, 
                device_type=device_type, 
                battery_id=battery_id,
                status="registered"
            )
            session.add(device)
            session.commit()
            session.refresh(device)
            return device

    @staticmethod
    def start_listener():
        broker = settings.MQTT_BROKER_URL or "test.mosquitto.org"
        port = settings.MQTT_PORT or 1883
        
        IoTService.client.on_connect = IoTService.on_connect
        IoTService.client.on_message = IoTService.on_message
        
        try:
            IoTService.client.connect(broker, port, 60)
            IoTService.client.loop_start()
            logger.info(f"MQTT Listener started on {broker}:{port}")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")

    @staticmethod
    def get_battery_metrics(battery_id: int) -> dict:
        # Fallback to DB or Mock
        with Session(engine) as session:
             # Try to get latest health log
             log = session.exec(select(BatteryHealthLog).where(BatteryHealthLog.battery_id == battery_id).order_by(BatteryHealthLog.timestamp.desc())).first()
             if log:
                 return {
                     "battery_id": battery_id,
                     "charge_percentage": log.charge_percentage,
                     "voltage": log.voltage,
                     "current": log.current,
                     "temperature": log.temperature,
                     "timestamp": log.timestamp
                 }
        return {
            "battery_id": battery_id,
            "charge_percentage": 0,
            "status": "unknown"
        }
