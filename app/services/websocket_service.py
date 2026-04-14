"""
WebSocket Service for Real-time Updates
Manages WebSocket connections for battery status streaming
"""
from fastapi import WebSocket, WebSocketDisconnect
from typing import Any, Dict, Optional, Set
import contextlib
import json
import asyncio
import logging
import random
from datetime import datetime

from app.services.redis_service import RedisService
from app.services.order_realtime_outbox_service import OrderRealtimeOutboxService
from app.core.config import settings

logger = logging.getLogger(__name__)
ORDER_UPDATES_CHANNEL = "wezu:orders:updates"
INVENTORY_LOCATION_TYPES = {"warehouse", "station", "shelf"}


def _normalize_inventory_location_type(raw_location_type: Any) -> str:
    location_type = str(raw_location_type or "").strip().lower()
    if location_type not in INVENTORY_LOCATION_TYPES:
        raise ValueError(
            f"Invalid location_type '{raw_location_type}'. Allowed: {sorted(INVENTORY_LOCATION_TYPES)}"
        )
    return location_type


def _inventory_location_key(location_type: str, location_id: int) -> str:
    return f"{location_type}:{location_id}"

class ConnectionManager:
    """Manages WebSocket connections"""
    
    def __init__(self):
        # Active connections: {user_id: Set[WebSocket]}
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # Battery subscriptions: {battery_id: Set[user_id]}
        self.battery_subscriptions: Dict[int, Set[int]] = {}
        # Order subscriptions: {"*": Set[user_id], "ORD-XXXX": Set[user_id]}
        self.order_subscriptions: Dict[str, Set[int]] = {}
        # Inventory subscriptions: {"warehouse:1": Set[user_id], ...}
        self.inventory_subscriptions: Dict[str, Set[int]] = {}
        self._order_pubsub_task: Optional[asyncio.Task] = None
        self._order_outbox_task: Optional[asyncio.Task] = None
        self._order_pubsub_started = False
        
    async def connect(self, websocket: WebSocket, user_id: int):
        """
        Accept new WebSocket connection
        
        Args:
            websocket: WebSocket connection
            user_id: User ID
        """
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        
        self.active_connections[user_id].add(websocket)
        logger.info(f"User {user_id} connected via WebSocket")
    
    def disconnect(self, websocket: WebSocket, user_id: int):
        """
        Remove WebSocket connection
        
        Args:
            websocket: WebSocket connection
            user_id: User ID
        """
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        
        # Remove from battery subscriptions
        for battery_id in list(self.battery_subscriptions.keys()):
            if user_id in self.battery_subscriptions[battery_id]:
                self.battery_subscriptions[battery_id].discard(user_id)
                
                if not self.battery_subscriptions[battery_id]:
                    del self.battery_subscriptions[battery_id]

        # Remove from order subscriptions
        for order_key in list(self.order_subscriptions.keys()):
            if user_id in self.order_subscriptions[order_key]:
                self.order_subscriptions[order_key].discard(user_id)
                if not self.order_subscriptions[order_key]:
                    del self.order_subscriptions[order_key]

        # Remove from inventory location subscriptions
        for location_key in list(self.inventory_subscriptions.keys()):
            if user_id in self.inventory_subscriptions[location_key]:
                self.inventory_subscriptions[location_key].discard(user_id)
                if not self.inventory_subscriptions[location_key]:
                    del self.inventory_subscriptions[location_key]
        
        logger.info(f"User {user_id} disconnected from WebSocket")
    
    async def subscribe_battery(self, user_id: int, battery_id: int):
        """
        Subscribe user to battery updates
        
        Args:
            user_id: User ID
            battery_id: Battery ID
        """
        if battery_id not in self.battery_subscriptions:
            self.battery_subscriptions[battery_id] = set()
        
        self.battery_subscriptions[battery_id].add(user_id)
        logger.info(f"User {user_id} subscribed to battery {battery_id}")
    
    async def unsubscribe_battery(self, user_id: int, battery_id: int):
        """
        Unsubscribe user from battery updates
        
        Args:
            user_id: User ID
            battery_id: Battery ID
        """
        if battery_id in self.battery_subscriptions:
            self.battery_subscriptions[battery_id].discard(user_id)
            
            if not self.battery_subscriptions[battery_id]:
                del self.battery_subscriptions[battery_id]
        
        logger.info(f"User {user_id} unsubscribed from battery {battery_id}")

    async def subscribe_all_orders(self, user_id: int):
        """Subscribe user to all order updates."""
        if "*" not in self.order_subscriptions:
            self.order_subscriptions["*"] = set()
        self.order_subscriptions["*"].add(user_id)
        logger.info("User %s subscribed to all order updates", user_id)

    async def subscribe_order(self, user_id: int, order_id: str):
        """Subscribe user to one order's updates."""
        order_key = str(order_id).strip()
        if not order_key:
            return
        if order_key not in self.order_subscriptions:
            self.order_subscriptions[order_key] = set()
        self.order_subscriptions[order_key].add(user_id)
        logger.info("User %s subscribed to order %s updates", user_id, order_key)

    async def unsubscribe_order(self, user_id: int, order_id: str):
        """Unsubscribe user from one order's updates."""
        order_key = str(order_id).strip()
        if not order_key:
            return
        subscribers = self.order_subscriptions.get(order_key)
        if not subscribers:
            return
        subscribers.discard(user_id)
        if not subscribers:
            del self.order_subscriptions[order_key]
        logger.info("User %s unsubscribed from order %s updates", user_id, order_key)

    async def subscribe_inventory_location(
        self,
        user_id: int,
        location_type: str,
        location_id: int,
    ) -> str:
        """Subscribe user to inventory updates for one location."""
        normalized_type = _normalize_inventory_location_type(location_type)
        normalized_location_id = int(location_id)
        key = _inventory_location_key(normalized_type, normalized_location_id)
        if key not in self.inventory_subscriptions:
            self.inventory_subscriptions[key] = set()
        self.inventory_subscriptions[key].add(user_id)
        logger.info(
            "User %s subscribed to inventory location %s#%s",
            user_id,
            normalized_type,
            normalized_location_id,
        )
        return key

    async def unsubscribe_inventory_location(
        self,
        user_id: int,
        location_type: str,
        location_id: int,
    ) -> str:
        """Unsubscribe user from inventory updates for one location."""
        normalized_type = _normalize_inventory_location_type(location_type)
        normalized_location_id = int(location_id)
        key = _inventory_location_key(normalized_type, normalized_location_id)
        subscribers = self.inventory_subscriptions.get(key)
        if subscribers:
            subscribers.discard(user_id)
            if not subscribers:
                del self.inventory_subscriptions[key]
        logger.info(
            "User %s unsubscribed from inventory location %s#%s",
            user_id,
            normalized_type,
            normalized_location_id,
        )
        return key
    
    async def send_personal_message(self, message: dict, user_id: int):
        """
        Send message to specific user
        
        Args:
            message: Message data
            user_id: User ID
        """
        if user_id in self.active_connections:
            disconnected = set()
            
            for websocket in self.active_connections[user_id]:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message to user {user_id}: {str(e)}")
                    disconnected.add(websocket)
            
            # Clean up disconnected websockets
            for websocket in disconnected:
                self.disconnect(websocket, user_id)

    async def broadcast_order_update(self, event: Dict[str, Any]):
        """Broadcast order update to relevant subscribers."""
        order_id = str(event.get("order_id") or "").strip()
        wildcard_subscribers = self.order_subscriptions.get("*", set())
        specific_subscribers = self.order_subscriptions.get(order_id, set()) if order_id else set()
        target_users = set(wildcard_subscribers).union(specific_subscribers)
        if not target_users:
            return

        message = {
            "type": "order_update",
            "timestamp": datetime.utcnow().isoformat(),
            "data": event,
        }
        for user_id in target_users:
            await self.send_personal_message(message, user_id)

    async def broadcast_inventory_update(self, event: Dict[str, Any]):
        """Broadcast inventory transfer updates to subscribed location watchers."""
        raw_locations = event.get("affected_locations") or []
        if not isinstance(raw_locations, list):
            return

        target_users: Set[int] = set()
        for location in raw_locations:
            if not isinstance(location, dict):
                continue
            raw_type = location.get("location_type")
            raw_id = location.get("location_id")
            if raw_id is None:
                continue
            try:
                normalized_type = _normalize_inventory_location_type(raw_type)
                key = _inventory_location_key(normalized_type, int(raw_id))
            except (ValueError, TypeError):
                continue
            target_users.update(self.inventory_subscriptions.get(key, set()))

        if not target_users:
            return

        message = {
            "type": "inventory_update",
            "timestamp": datetime.utcnow().isoformat(),
            "data": event,
        }
        for user_id in target_users:
            await self.send_personal_message(message, user_id)

    async def _order_pubsub_loop(self):
        """Listen to Redis pub/sub channel and forward order updates to websocket clients."""
        while True:
            pubsub = None
            try:
                redis_client = RedisService.get_client()
                if redis_client is None:
                    await asyncio.sleep(2)
                    continue

                pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
                pubsub.subscribe(ORDER_UPDATES_CHANNEL)
                logger.info("Subscribed to Redis order updates channel '%s'", ORDER_UPDATES_CHANNEL)

                while True:
                    message = await asyncio.to_thread(pubsub.get_message, True, 1.0)
                    if message and message.get("type") == "message":
                        raw_data = message.get("data")
                        try:
                            if isinstance(raw_data, bytes):
                                raw_data = raw_data.decode("utf-8", errors="replace")
                            event = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                        except Exception:
                            logger.warning("Failed to decode order update payload from Redis: %s", raw_data)
                            continue

                        if isinstance(event, dict):
                            scope = str(event.get("scope") or "order").strip().lower()
                            if scope == "inventory":
                                await self.broadcast_inventory_update(event)
                            else:
                                await self.broadcast_order_update(event)
                    await asyncio.sleep(0)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Order pub/sub loop error: %s", exc)
                await asyncio.sleep(2)
            finally:
                if pubsub is not None:
                    with contextlib.suppress(Exception):
                        pubsub.close()

    async def _order_outbox_dispatch_loop(self):
        """Drain DB-backed realtime outbox and publish to Redis channel."""
        base_idle_sleep = max(0.1, float(settings.ORDER_REALTIME_OUTBOX_POLL_INTERVAL_SECONDS))
        max_idle_sleep = max(
            base_idle_sleep,
            float(getattr(settings, "ORDER_REALTIME_OUTBOX_IDLE_BACKOFF_MAX_SECONDS", 3.0)),
        )
        error_base_sleep = max(
            base_idle_sleep,
            float(getattr(settings, "ORDER_REALTIME_OUTBOX_ERROR_BACKOFF_BASE_SECONDS", 2.0)),
        )
        max_error_sleep = max(
            error_base_sleep,
            float(getattr(settings, "ORDER_REALTIME_OUTBOX_ERROR_BACKOFF_MAX_SECONDS", 30.0)),
        )
        lock_unavailable_sleep = max(
            error_base_sleep,
            float(getattr(settings, "ORDER_REALTIME_OUTBOX_LOCK_UNAVAILABLE_BACKOFF_SECONDS", 15.0)),
        )
        idle_sleep = base_idle_sleep
        error_sleep = error_base_sleep
        consecutive_errors = 0
        while True:
            try:
                summary = await asyncio.to_thread(OrderRealtimeOutboxService.dispatch_pending_once)
                lock_backend_checked = bool(summary.get("lock_backend_checked", 0))
                lock_state_code = int(summary.get("lock_state_code", 0) or 0)

                consecutive_errors = 0
                error_sleep = error_base_sleep
                if (
                    bool(getattr(settings, "ORDER_REALTIME_OUTBOX_USE_REDIS_DISPATCH_LOCK", True))
                    and not lock_backend_checked
                    and lock_state_code == 2
                ):
                    # Redis lock backend unavailable: apply conservative sleep to avoid polling storms.
                    jitter = random.uniform(0.0, min(2.0, lock_unavailable_sleep * 0.2))
                    await asyncio.sleep(lock_unavailable_sleep + jitter)
                    idle_sleep = min(max_idle_sleep, max(idle_sleep, base_idle_sleep * 2))
                    continue
                if summary.get("claimed", 0) > 0:
                    idle_sleep = base_idle_sleep
                    await asyncio.sleep(0)
                else:
                    # Stagger idle workers to reduce synchronized polling bursts.
                    jitter = random.uniform(0.0, min(0.25, idle_sleep * 0.2))
                    await asyncio.sleep(idle_sleep + jitter)
                    idle_sleep = min(max_idle_sleep, idle_sleep * 1.5)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                consecutive_errors += 1
                if consecutive_errors == 1 or consecutive_errors % 5 == 0:
                    logger.warning(
                        "Order outbox dispatcher loop error (attempt=%s retry_in=%.2fs): %s",
                        consecutive_errors,
                        error_sleep,
                        exc,
                    )
                else:
                    logger.debug(
                        "Order outbox dispatcher loop transient error (attempt=%s retry_in=%.2fs): %s",
                        consecutive_errors,
                        error_sleep,
                        exc,
                    )
                idle_sleep = min(max_idle_sleep, max(base_idle_sleep, idle_sleep * 1.25))
                jitter = random.uniform(0.0, min(1.0, error_sleep * 0.2))
                await asyncio.sleep(error_sleep + jitter)
                error_sleep = min(max_error_sleep, error_sleep * 2)

    async def start_order_pubsub_listener(self, *, run_outbox_dispatch: bool = True):
        """Start Redis pub/sub listener once per process."""
        if self._order_pubsub_started and self._order_pubsub_task and not self._order_pubsub_task.done():
            return
        self._order_pubsub_task = asyncio.create_task(self._order_pubsub_loop())
        if settings.ORDER_REALTIME_OUTBOX_ENABLED and run_outbox_dispatch:
            self._order_outbox_task = asyncio.create_task(self._order_outbox_dispatch_loop())
        else:
            logger.info(
                "Order outbox dispatch loop disabled for this process run_outbox_dispatch=%s",
                run_outbox_dispatch,
            )
        self._order_pubsub_started = True

    async def stop_order_pubsub_listener(self):
        """Stop Redis pub/sub listener."""
        if self._order_pubsub_task is None:
            pass
        else:
            self._order_pubsub_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._order_pubsub_task
            self._order_pubsub_task = None
        if self._order_outbox_task is not None:
            self._order_outbox_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._order_outbox_task
            self._order_outbox_task = None
        self._order_pubsub_started = False
    
    async def broadcast_battery_update(self, battery_id: int, data: dict):
        """
        Broadcast battery update to all subscribed users
        
        Args:
            battery_id: Battery ID
            data: Update data
        """
        if battery_id not in self.battery_subscriptions:
            return
        
        message = {
            "type": "battery_update",
            "battery_id": battery_id,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        for user_id in self.battery_subscriptions[battery_id]:
            await self.send_personal_message(message, user_id)
    
    async def broadcast_alert(self, battery_id: int, alert: dict):
        """
        Broadcast alert to subscribed users
        
        Args:
            battery_id: Battery ID
            alert: Alert data
        """
        if battery_id not in self.battery_subscriptions:
            return
        
        message = {
            "type": "alert",
            "battery_id": battery_id,
            "alert": alert,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        for user_id in self.battery_subscriptions[battery_id]:
            await self.send_personal_message(message, user_id)
    
    async def send_heartbeat(self):
        """Send heartbeat to all connected clients"""
        message = {
            "type": "heartbeat",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        for user_id in list(self.active_connections.keys()):
            await self.send_personal_message(message, user_id)
    
    def get_connection_count(self) -> int:
        """Get total number of active connections"""
        return sum(len(connections) for connections in self.active_connections.values())
    
    def get_user_connection_count(self, user_id: int) -> int:
        """Get number of connections for specific user"""
        return len(self.active_connections.get(user_id, set()))


# Global connection manager
manager = ConnectionManager()


def publish_order_update(event: Dict[str, Any]) -> bool:
    """
    Publish order update event to Redis so all API workers can push to their local websocket clients.
    Returns True when publish is attempted successfully.
    """
    redis_client = RedisService.get_client()
    if redis_client is None:
        return False
    try:
        payload = dict(event)
        payload.setdefault("scope", "order")
        redis_client.publish(ORDER_UPDATES_CHANNEL, json.dumps(payload, default=str))
        return True
    except Exception as exc:
        logger.warning("Failed to publish order update: %s", exc)
        return False


def publish_inventory_update(event: Dict[str, Any]) -> bool:
    """
    Publish inventory update event to Redis for all API workers.
    """
    redis_client = RedisService.get_client()
    if redis_client is None:
        return False
    try:
        payload = dict(event)
        payload["scope"] = "inventory"
        redis_client.publish(ORDER_UPDATES_CHANNEL, json.dumps(payload, default=str))
        return True
    except Exception as exc:
        logger.warning("Failed to publish inventory update: %s", exc)
        return False

async def heartbeat_task():
    """Background task to send periodic heartbeats"""
    while True:
        await asyncio.sleep(30)  # Every 30 seconds
        await manager.send_heartbeat()
