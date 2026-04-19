from __future__ import annotations
"""
MQTT Service for Real-time Battery Monitoring
Subscribes to IoT device telemetry and processes battery data
"""
import json
import logging
from datetime import datetime
from typing import Optional, Callable
import paho.mqtt.client as mqtt
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import engine
from app.models.battery import Battery
import redis

from app.schemas.telematics import TelemeticsDataIngest
from app.services.event_stream_service import EventStreamService
from app.services.telematics_ingest_service import TelematicsIngestService

logger = logging.getLogger(__name__)

class MQTTService:
    """MQTT service for battery telemetry"""
    
    def __init__(self):
        self.client: Optional[mqtt.Client] = None
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.callbacks = {}
        
    def connect(self):
        """Connect to MQTT broker"""
        try:
            # Parse MQTT URL
            broker_url = settings.MQTT_BROKER_URL.replace('mqtt://', '')
            if ':' in broker_url:
                host, port = broker_url.split(':')
                port = int(port)
            else:
                host = broker_url
                port = 1883
            
            # Create client
            client_id = f"{settings.MQTT_CLIENT_ID_PREFIX}_{datetime.utcnow().timestamp()}"
            self.client = mqtt.Client(client_id=client_id)
            
            # Set callbacks
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.on_disconnect = self._on_disconnect
            
            # Set credentials if provided
            if settings.MQTT_USERNAME and settings.MQTT_PASSWORD:
                self.client.username_pw_set(
                    settings.MQTT_USERNAME,
                    settings.MQTT_PASSWORD
                )
            
            # Connect
            self.client.connect(host, port, keepalive=60)
            self.client.loop_start()
            
            logger.info(f"Connected to MQTT broker at {host}:{port}")
            
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {str(e)}")
            raise
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("Disconnected from MQTT broker")
    
    def subscribe(self, topic: str, callback: Optional[Callable] = None):
        """
        Subscribe to MQTT topic
        
        Args:
            topic: MQTT topic to subscribe to
            callback: Optional callback function for messages
        """
        if not self.client:
            raise Exception("MQTT client not connected")
        
        self.client.subscribe(topic)
        if callback:
            self.callbacks[topic] = callback
        
        logger.info(f"Subscribed to topic: {topic}")
    
    def publish(self, topic: str, payload: dict):
        """
        Publish message to MQTT topic
        
        Args:
            topic: MQTT topic
            payload: Message payload (dict)
        """
        if not self.client:
            raise Exception("MQTT client not connected")
        
        message = json.dumps(payload)
        self.client.publish(topic, message, qos=1)
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker"""
        if rc == 0:
            logger.info("Successfully connected to MQTT broker")
            # Subscribe to all battery topics
            topic = f"{settings.MQTT_TOPIC_PREFIX}/+/telemetry"
            client.subscribe(topic)
            logger.info(f"Subscribed to: {topic}")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from broker"""
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker: {rc}")
    
    def _on_message(self, client, userdata, msg):
        """
        Callback when message received
        
        Message format:
        Topic: wezu/batteries/{battery_id}/telemetry
        Payload: {
            "voltage": 12.6,
            "current": 2.5,
            "temperature": 25.3,
            "soc": 85.5,
            "health": 95.0,
            "timestamp": "2024-12-22T10:30:00Z"
        }
        """
        try:
            # Parse topic to get battery_id
            topic_parts = msg.topic.split('/')
            if len(topic_parts) >= 3:
                battery_id = topic_parts[2]
            else:
                logger.error(f"Invalid topic format: {msg.topic}")
                return
            
            # Parse payload
            payload = json.loads(msg.payload.decode())
            
            # Process telemetry data
            self._process_telemetry(battery_id, payload)
            
            # Call custom callback if registered
            if msg.topic in self.callbacks:
                self.callbacks[msg.topic](battery_id, payload)
            
        except Exception as e:
            logger.error(f"Error processing MQTT message: {str(e)}")
    
    def _resolve_battery_id(self, battery_key: str) -> int | None:
        try:
            return int(battery_key)
        except (TypeError, ValueError):
            logger.debug(f"battery_key '{battery_key}' is not numeric, resolving by serial_number")

        with Session(engine) as session:
            battery = session.exec(
                select(Battery).where(Battery.serial_number == battery_key)
            ).first()
            return int(battery.id) if battery else None

    def _build_ingest_payload(self, battery_id: int, data: dict) -> TelemeticsDataIngest:
        timestamp_raw = data.get("timestamp")
        parsed_timestamp = None
        if timestamp_raw:
            try:
                parsed_timestamp = datetime.fromisoformat(str(timestamp_raw).replace("Z", "+00:00"))
            except Exception:
                parsed_timestamp = None

        return TelemeticsDataIngest(
            battery_id=battery_id,
            timestamp=parsed_timestamp or datetime.utcnow(),
            voltage=float(data.get("voltage", 0.0)),
            current=float(data.get("current", 0.0)),
            temperature=float(data.get("temperature", data.get("temp", 0.0))),
            soc=float(data.get("soc", 0.0)),
            soh=float(data.get("soh", data.get("health", 100.0))),
            gps_latitude=data.get("gps_latitude") if data.get("gps_latitude") is not None else data.get("lat"),
            gps_longitude=data.get("gps_longitude") if data.get("gps_longitude") is not None else data.get("lng"),
            gps_altitude=data.get("gps_altitude"),
            gps_speed=data.get("gps_speed") if data.get("gps_speed") is not None else data.get("speed"),
            error_codes=data.get("error_codes"),
            raw_payload=data,
        )

    def _process_telemetry(self, battery_key: str, data: dict):
        """
        Process battery telemetry data
        
        Args:
            battery_key: Topic key (numeric battery ID or serial number)
            data: Telemetry data payload
        """
        try:
            # Store in Redis for real-time access (5-minute TTL)
            redis_key = f"battery:{battery_key}:telemetry"
            try:
                self.redis_client.setex(
                    redis_key,
                    300,  # 5 minutes
                    json.dumps(data)
                )
            except Exception as redis_exc:
                logger.warning(f"Failed to cache telemetry for battery {battery_key}: {redis_exc}")
            
            resolved_battery_id = self._resolve_battery_id(battery_key)
            if not resolved_battery_id:
                logger.warning("Telemetry received for unknown battery key=%s", battery_key)
                return

            ingest_payload = self._build_ingest_payload(resolved_battery_id, data)
            if settings.TELEMATICS_QUEUE_ENABLED:
                event = EventStreamService.build_event(
                    event_type="telematics.ingest.v1",
                    source="mqtt",
                    payload=ingest_payload.model_dump(mode="json"),
                    idempotency_key=f"mqtt:{battery_key}:{ingest_payload.timestamp.isoformat()}",
                )
                stream_id = EventStreamService.publish(settings.TELEMATICS_STREAM_NAME, event)
                if stream_id is None and settings.TELEMATICS_QUEUE_REQUIRED:
                    logger.warning("Telemetry queue unavailable for battery_key=%s", battery_key)
                    return

                if settings.TELEMATICS_DUAL_WRITE_SHADOW or stream_id is None:
                    with Session(engine) as session:
                        TelematicsIngestService.persist_telemetry(session, data_in=ingest_payload)
            else:
                with Session(engine) as session:
                    TelematicsIngestService.persist_telemetry(session, data_in=ingest_payload)

            # Check for alerts
            self._check_alerts(str(resolved_battery_id), data)
            
            logger.debug(f"Processed telemetry for battery {resolved_battery_id}")
            
        except Exception as e:
            logger.error(f"Failed to process telemetry: {str(e)}")
    
    def _check_alerts(self, battery_id: str, data: dict):
        """
        Check telemetry data for alert conditions
        
        Args:
            battery_id: Battery ID
            data: Telemetry data
        """
        alerts = []
        
        # Low battery alert
        if data.get('soc', 100) < 10:
            alerts.append({
                'type': 'LOW_BATTERY',
                'severity': 'HIGH',
                'message': f'Battery {battery_id} charge critically low: {data.get("soc")}%'
            })
        
        # High temperature alert
        if data.get('temperature', 0) > 45:
            alerts.append({
                'type': 'HIGH_TEMPERATURE',
                'severity': 'CRITICAL',
                'message': f'Battery {battery_id} temperature too high: {data.get("temperature")}°C'
            })
        
        # Low health alert
        if data.get('health', 100) < 80:
            alerts.append({
                'type': 'LOW_HEALTH',
                'severity': 'MEDIUM',
                'message': f'Battery {battery_id} health degraded: {data.get("health")}%'
            })
        
        # Store alerts in Redis
        if alerts:
            redis_key = f"battery:{battery_id}:alerts"
            self.redis_client.lpush(redis_key, *[json.dumps(alert) for alert in alerts])
            self.redis_client.expire(redis_key, 86400)  # 24 hours
            
            logger.warning(f"Alerts generated for battery {battery_id}: {len(alerts)}")
    
    def get_realtime_data(self, battery_id: int) -> Optional[dict]:
        """
        Get real-time telemetry data from Redis
        
        Args:
            battery_id: Battery ID
            
        Returns:
            Telemetry data or None
        """
        redis_key = f"battery:{battery_id}:telemetry"
        try:
            data = self.redis_client.get(redis_key)
        except Exception as exc:
            logger.warning(f"Failed to fetch telemetry cache for battery {battery_id}: {exc}")
            return None
        
        if data:
            return json.loads(data)
        return None
    
    def get_alerts(self, battery_id: int) -> list:
        """
        Get active alerts for battery
        
        Args:
            battery_id: Battery ID
            
        Returns:
            List of alerts
        """
        redis_key = f"battery:{battery_id}:alerts"
        try:
            alerts_data = self.redis_client.lrange(redis_key, 0, -1)
        except Exception as exc:
            logger.warning(f"Failed to fetch alerts cache for battery {battery_id}: {exc}")
            return []
        
        return [json.loads(alert) for alert in alerts_data]


# Global MQTT service instance
mqtt_service = MQTTService()

def start_mqtt_service():
    """Start MQTT service"""
    mqtt_service.connect()

def stop_mqtt_service():
    """Stop MQTT service"""
    mqtt_service.disconnect()
