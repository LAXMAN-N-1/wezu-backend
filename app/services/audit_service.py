from datetime import datetime
from typing import Any, Dict, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

class AuditService:
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Any = None
        self.collection: Any = None

    def connect(self):
        """Initialize MongoDB connection"""
        if not self.client:
            self.client = AsyncIOMotorClient(settings.MONGODB_URL)
            self.db = self.client[settings.MONGODB_DB]
            self.collection = self.db["audit_logs"]

    async def log_event(
        self,
        event_type: str,
        user_id: Optional[int] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        status: str = "success",
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ):
        """
        Record an audit log entry.
        """
        self.connect()
        
        log_entry = {
            "timestamp": datetime.utcnow(),
            "event_type": event_type,
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "status": status,
            "metadata": metadata or {},
            "ip_address": ip_address
        }
        
        try:
            await self.collection.insert_one(log_entry)
        except Exception as e:
            # Fallback to standard logging if MongoDB fails
            import logging
            logging.error(f"Failed to write audit log to MongoDB: {e}")
            logging.info(f"Audit Event: {log_entry}")

    async def log_security_event(self, user_id: int, event: str, metadata: Dict[str, Any]):
        """Specialized helper for security-related events like login/password change"""
        await self.log_event(
            event_type="security",
            user_id=user_id,
            action=event,
            metadata=metadata
        )

    async def get_logs(
        self,
        user_id: Optional[int] = None,
        event_type: Optional[str] = None,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Fetch logs from MongoDB with filtering and pagination.
        """
        self.connect()
        
        query = {}
        if user_id:
            query["user_id"] = user_id
        if event_type:
            query["event_type"] = event_type
        if action:
            query["action"] = action
        if resource:
            query["resource"] = {"$regex": resource, "$options": "i"}
        
        if start_date or end_date:
            query["timestamp"] = {}
            if start_date:
                query["timestamp"]["$gte"] = start_date
            if end_date:
                query["timestamp"]["$lte"] = end_date
        
        total_count = await self.collection.count_documents(query)
        
        cursor = self.collection.find(query) \
            .sort("timestamp", -1) \
            .skip((page - 1) * limit) \
            .limit(limit)
            
        logs = await cursor.to_list(length=limit)
        
        # Convert ObjectId and datetime for JSON serialization if needed, 
        # but motor might handle datetime. 
        for log in logs:
            log["_id"] = str(log["_id"])
            
        return {
            "logs": logs,
            "total_count": total_count,
            "page": page,
            "limit": limit
        }

audit_service = AuditService()
