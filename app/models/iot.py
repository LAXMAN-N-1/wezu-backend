from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
import uuid

class IoTDevice(SQLModel, table=True):
    __tablename__ = "iot_devices"
    __table_args__ = {"schema": "inventory"}
    id: Optional[int] = Field(default=None, primary_key=True)
    device_id: str = Field(unique=True, index=True) # Hardware Serial / MAC / UUID
    device_type: str = Field(default="tracker_v1")
    firmware_version: Optional[str] = None
    
    status: str = Field(default="offline") # online, offline, error
    communication_protocol: str = Field(default="mqtt")
    
    battery_id: Optional[uuid.UUID] = Field(default=None, foreign_key="inventory.batteries.id")
    
    auth_token: Optional[str] = None # For device authentication
    
    last_heartbeat: Optional[datetime] = None
    last_ip_address: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    battery: Optional["Battery"] = Relationship(back_populates="iot_device")
    commands: List["DeviceCommand"] = Relationship(back_populates="device")


class DeviceCommand(SQLModel, table=True):
    __tablename__ = "device_commands"
    __table_args__ = {"schema": "inventory"}
    id: Optional[int] = Field(default=None, primary_key=True)
    device_id: int = Field(foreign_key="inventory.iot_devices.id")
    
    command_type: str # LOCK, UNLOCK, REBOOT, DIAGNOSTIC
    payload: Optional[str] = None # JSON string params
    
    status: str = Field(default="queued") # queued, sent, acknowledged, executed, failed
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    response_data: Optional[str] = None # JSON string
    
    # Relationship
    device: IoTDevice = Relationship(back_populates="commands")


class FirmwareUpdate(SQLModel, table=True):
    __tablename__ = "firmware_updates"
    __table_args__ = {"schema": "inventory"}
    id: Optional[int] = Field(default=None, primary_key=True)
    version: str
    file_url: str
    checksum: str
    device_type: str
    
    is_critical: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
