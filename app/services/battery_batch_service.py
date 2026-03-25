from typing import List, Dict, Any
from sqlmodel import Session, select, col
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
            sku_id_raw = row.get("sku_id")
            station_id_raw = row.get("station_id")
            manufacture_date_raw = row.get("manufacture_date")
            
            parsed_data.append({
                "serial_number": row.get("serial_number", "").strip(),
                "sku_id": int(sku_id_raw) if sku_id_raw else None,
                "status": row.get("status", BatteryStatus.AVAILABLE).strip(),
                "health_status": row.get("health_status", BatteryHealth.GOOD).strip(),
                "health_percentage": float(row.get("health_percentage", 100.0)),
                "station_id": int(station_id_raw) if station_id_raw else None,
                "manufacturer": row.get("manufacturer", "").strip(),
                "location_type": row.get("location_type", "warehouse").strip(),
                "notes": row.get("notes", "").strip(),
                "manufacture_date": datetime.fromisoformat(manufacture_date_raw) if manufacture_date_raw else None
            })
            
        return parsed_data

    @staticmethod
    def process_import(session: Session, parsed_data: List[Dict[str, Any]], dry_run: bool = False) -> Dict[str, Any]:
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
                    select(Battery).where(col(Battery.serial_number) == item["serial_number"])
                ).first()
                
                if existing:
                    raise ValueError(f"Battery with serial '{item['serial_number']}' already exists")

                # Verify SKU if provided
                if item.get("sku_id"):
                    sku = session.exec(select(BatteryCatalog).where(col(BatteryCatalog.id) == item["sku_id"])).first()
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
        if new_batteries and not dry_run:
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
            "id", "serial_number", "status", "health_percentage", "cycle_count",
            "manufacturer", "location_type", "notes", "manufacture_date",
            "station_id", "created_at"
        ])
        
        # Data
        for b in batteries:
            writer.writerow([
                b.id, b.serial_number, b.status, b.health_percentage, b.cycle_count,
                b.manufacturer, b.location_type, b.notes,
                b.manufacture_date.isoformat() if b.manufacture_date else "",
                b.station_id,
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
                    select(Battery).where(col(Battery.serial_number) == serial_num)
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
