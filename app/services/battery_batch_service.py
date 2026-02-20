from typing import List, Dict, Any
from sqlmodel import Session, select
from datetime import datetime
from io import StringIO
import csv

from app.models.battery import Battery, BatteryStatus, BatteryHealth
from app.models.battery_catalog import BatteryCatalog

class BatteryBatchService:
    @staticmethod
    def parse_import_csv(content: str) -> List[Dict[str, Any]]:
        """Parse CSV content for battery import"""
        file_stream = StringIO(content)
        reader = csv.DictReader(file_stream)
        
        parsed_data = []
        for row in reader:
            parsed_data.append({
                "serial_number": row.get("serial_number", "").strip(),
                "sku_id": int(row.get("sku_id", 0)) if row.get("sku_id") else None,
                "status": row.get("status", BatteryStatus.AVAILABLE).strip(),
                "health_status": row.get("health_status", BatteryHealth.GOOD).strip(),
                "current_charge": float(row.get("current_charge", 100.0)),
                "health_percentage": float(row.get("health_percentage", 100.0)),
                "temperature_c": float(row.get("temperature_c", 25.0)),
                "station_id": int(row.get("station_id")) if row.get("station_id") else None,
                "warehouse_id": int(row.get("warehouse_id")) if row.get("warehouse_id") else None
            })
            
        return parsed_data

    @staticmethod
    def process_import(session: Session, parsed_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process bulk import of batteries from parsed data"""
        success_count = 0
        error_count = 0
        errors = []

        new_batteries = []
        for index, item in enumerate(parsed_data):
            try:
                # Validation: serial_number is required
                if not item.get("serial_number"):
                    raise ValueError("serial_number is required")
                
                # Check if exists
                existing = session.exec(
                    select(Battery).where(Battery.serial_number == item["serial_number"])
                ).first()
                
                if existing:
                    raise ValueError(f"Battery with serial '{item['serial_number']}' already exists")

                # Verify SKU if provided
                if item.get("sku_id"):
                    sku = session.exec(select(BatteryCatalog).where(BatteryCatalog.id == item["sku_id"])).first()
                    if not sku:
                        raise ValueError(f"SKU ID '{item['sku_id']}' not found")
                
                battery = Battery(**item)
                # optionally generate QR code implicitly here, or wait until specifically requested.
                new_batteries.append(battery)
                success_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append({"row": index + 2, "error": str(e)}) # +2 for 1-based indexing skipping header

        # Bulk save
        if new_batteries:
            session.add_all(new_batteries)
            session.commit()

        return {
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors
        }

    @staticmethod
    def generate_export_csv(session: Session) -> str:
        """Generate CSV string of all batteries"""
        batteries = session.exec(select(Battery)).all()
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            "id", "serial_number", "sku_id", "status", "health_status", 
            "current_charge", "health_percentage", "cycle_count", "temperature_c",
            "station_id", "warehouse_id", "iot_device_id", "purchase_date", "created_at"
        ])
        
        # Data
        for b in batteries:
            writer.writerow([
                b.id, b.serial_number, b.sku_id, b.status, b.health_status,
                b.current_charge, b.health_percentage, b.cycle_count, b.temperature_c,
                b.station_id, b.warehouse_id, b.iot_device_id, 
                b.purchase_date.isoformat() if b.purchase_date else "",
                b.created_at.isoformat() if b.created_at else ""
            ])
            
        return output.getvalue()

    @staticmethod
    def process_bulk_update(session: Session, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process bulk update operations"""
        success_count = 0
        error_count = 0
        errors = []

        for index, update_data in enumerate(updates):
            try:
                serial_num = update_data.get("serial_number")
                if not serial_num:
                    raise ValueError("serial_number is required for update")
                
                battery = session.exec(
                    select(Battery).where(Battery.serial_number == serial_num)
                ).first()
                
                if not battery:
                    raise ValueError(f"Battery with serial '{serial_num}' not found")

                # Update allowed fields
                allowed_fields = ["status", "health_status", "station_id", "warehouse_id"]
                for field in allowed_fields:
                    if field in update_data and update_data[field] is not None:
                        setattr(battery, field, update_data[field])
                
                battery.updated_at = datetime.utcnow()
                success_count += 1

            except Exception as e:
                error_count += 1
                errors.append({"row": index, "error": str(e)})

        if success_count > 0:
            session.commit()

        return {
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors
        }

battery_batch_service = BatteryBatchService()
