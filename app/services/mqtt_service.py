"""
MQTT Service for Real-time Battery Monitoring
Subscribes to IoT device telemetry and processes battery data
"""
import paho.mqtt.client as mqtt
import json
import logging
from datetime import datetime
from typing import Optional, Callable
from sqlmodel import Session
from app.core.config import settings
from app.core.database import engine
from app.models.battery import Battery
from app.models.telemetry import Telemetry
from app.services.telematics_service import TelematicsService
from app.services.websocket_service import manager
import redis
import asyncio

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
        """
        if not self.client:
            raise Exception("MQTT client not connected")
        
        message = json.dumps(payload)
        self.client.publish(topic, message, qos=1)

    def send_command(self, device_id: str, command_type: str, params: Optional[dict] = None):
        """
        Send command to IoT device
        Topic: wezu/batteries/{device_id}/commands
        """
        topic = f"{settings.MQTT_TOPIC_PREFIX}/{device_id}/commands"
        payload = {
            "command": command_type,
            "params": params or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        self.publish(topic, payload)
        logger.info(f"Command {command_type} sent to device {device_id}")
    
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
    
    def _process_telemetry(self, battery_id: str, data: dict):
        """
        Process battery telemetry data
        
        Args:
            battery_id: Battery ID
            data: Telemetry data
        """
        try:
            # Store in Redis for real-time access (5-minute TTL)
            redis_key = f"battery:{battery_id}:telemetry"
            self.redis_client.setex(
                redis_key,
                300,  # 5 minutes
                json.dumps(data)
            )
            
            # Use centralized TelematicsService for DB updates and advanced logic
            with Session(engine) as session:
                TelematicsService.process_telemetry(session, battery_id, data)
            
            # Check for alerts
            self._check_alerts(battery_id, data)
            
            # 3. Broadcast to WebSockets
            try:
                # MQTT usually runs in its own background thread, so we schedule the coroutine in the main loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        manager.broadcast_battery_update(int(battery_id) if battery_id.isdigit() else 0, data),
                        loop
                    )
            except Exception as e:
                logger.error(f"Failed to broadcast WS update: {str(e)}")
            
            logger.debug(f"Processed telemetry for battery {battery_id}")
            
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
            
            # Broadcast alerts via WebSocket
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    for alert in alerts:
                        asyncio.run_coroutine_threadsafe(
                            manager.broadcast_alert(int(battery_id) if battery_id.isdigit() else 0, alert),
                            loop
                        )
            except Exception as e:
                logger.error(f"Failed to broadcast WS alert: {str(e)}")

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
        data = self.redis_client.get(redis_key)
        
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
        alerts_data = self.redis_client.lrange(redis_key, 0, -1)
        
        return [json.loads(alert) for alert in alerts_data]


# Global MQTT service instance
mqtt_service = MQTTService()

def start_mqtt_service():
    """Start MQTT service"""
    mqtt_service.connect()

def stop_mqtt_service():
    """Stop MQTT service"""
    mqtt_service.disconnect()
