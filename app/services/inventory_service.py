from sqlmodel import Session, select
from app.models.logistics import BatteryTransfer
from app.models.inventory_audit import InventoryAuditLog
from app.models.battery import Battery, BatteryStatus, LocationType
from app.schemas.inventory import TransferCreate
from datetime import datetime
from typing import List, Optional

class InventoryService:
    @staticmethod
    def log_inventory_change(
        db: Session,
        battery_id: int,
        action_type: str,
        from_loc_type: Optional[str] = None,
        from_loc_id: Optional[int] = None,
        to_loc_type: Optional[str] = None,
        to_loc_id: Optional[int] = None,
        actor_id: Optional[int] = None,
        notes: Optional[str] = None
    ):
        audit = InventoryAuditLog(
            battery_id=battery_id,
            action_type=action_type,
            from_location_type=from_loc_type,
            from_location_id=from_loc_id,
            to_location_type=to_loc_type,
            to_location_id=to_loc_id,
            actor_id=actor_id,
            notes=notes
        )
        db.add(audit)
        db.commit()

    @staticmethod
    def create_transfer(db: Session, transfer_in: TransferCreate, actor_id: int) -> BatteryTransfer:
        # Validate battery exists
        battery = db.get(Battery, transfer_in.battery_id)
        if not battery:
            raise ValueError("Battery not found")
        
        transfer = BatteryTransfer(
            battery_id=transfer_in.battery_id,
            from_location_type=transfer_in.from_location_type,
            from_location_id=transfer_in.from_location_id,
            to_location_type=transfer_in.to_location_type,
            to_location_id=transfer_in.to_location_id,
            status="pending"
        )
        db.add(transfer)
        
        # Log the initiation
        InventoryService.log_inventory_change(
            db=db,
            battery_id=transfer_in.battery_id,
            action_type="transfer_initiated",
            from_loc_type=transfer_in.from_location_type,
            from_loc_id=transfer_in.from_location_id,
            to_loc_type=transfer_in.to_location_type,
            to_loc_id=transfer_in.to_location_id,
            actor_id=actor_id
        )
        
        db.commit()
        db.refresh(transfer)
        return transfer

    @staticmethod
    def confirm_receipt(db: Session, transfer_id: int, actor_id: int) -> BatteryTransfer:
        transfer = db.get(BatteryTransfer, transfer_id)
        if not transfer:
            raise ValueError("Transfer not found")
        
        if transfer.status == "received":
            return transfer
            
        battery = db.get(Battery, transfer.battery_id)
        if not battery:
            raise ValueError("Battery not found")
            
        # Update transfer status
        transfer.status = "received"
        transfer.updated_at = datetime.utcnow()
        
        # Update battery location
        if transfer.to_location_type == "station":
            battery.station_id = transfer.to_location_id
            battery.location_type = LocationType.STATION
            battery.location_id = transfer.to_location_id
        elif transfer.to_location_type == "warehouse":
            battery.station_id = None
            battery.location_type = LocationType.WAREHOUSE
            battery.location_id = transfer.to_location_id
            
        battery.status = BatteryStatus.AVAILABLE
        battery.updated_at = datetime.utcnow()
        
        db.add(transfer)
        db.add(battery)
        
        # Log the confirmation
        assert battery.id is not None
        InventoryService.log_inventory_change(
            db=db,
            battery_id=battery.id,
            action_type="transfer_completed",
            from_loc_type=transfer.from_location_type,
            from_loc_id=transfer.from_location_id,
            to_loc_type=transfer.to_location_type,
            to_loc_id=transfer.to_location_id,
            actor_id=actor_id,
            notes=f"Transfer {transfer_id} confirmed"
        )
        
        db.commit()
        db.refresh(transfer)
        return transfer
