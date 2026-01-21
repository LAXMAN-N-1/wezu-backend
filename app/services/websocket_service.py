"""
WebSocket Service for Real-time Updates
Manages WebSocket connections for battery status streaming
"""
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages WebSocket connections"""
    
    def __init__(self):
        # Active connections: {user_id: Set[WebSocket]}
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # Battery subscriptions: {battery_id: Set[user_id]}
        self.battery_subscriptions: Dict[int, Set[int]] = {}
        
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

async def heartbeat_task():
    """Background task to send periodic heartbeats"""
    while True:
        await asyncio.sleep(30)  # Every 30 seconds
        await manager.send_heartbeat()
