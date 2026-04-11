import sys
import os
import random
import uuid
from datetime import datetime, UTC, timedelta

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlmodel import Session, select, text
from app.db.session import engine
from app.models.user import User
from app.models.battery import Battery, BatteryHealth
from app.models.battery_health import (
    BatteryHealthSnapshot, BatteryMaintenanceSchedule, BatteryHealthAlert,
    SnapshotType, MaintenanceType, MaintenancePriority, MaintenanceStatus,
    AlertType, AlertSeverity
)


# Define degradation profiles for 25 batteries (serial BAT-2024-100 to BAT-2024-124)
BATTERY_PROFILES = {
    "BAT-2024-100": {"start": 82, "end": 78, "profile": "normal"},
    "BAT-2024-101": {"start": 84, "end": 79, "profile": "normal"},
    "BAT-2024-102": {"start": 95, "end": 92, "profile": "healthy"},
    "BAT-2024-103": {"start": 65, "end": 58, "profile": "degrading_fast"},
    "BAT-2024-104": {"start": 88, "end": 85, "profile": "normal"},
    "BAT-2024-105": {"start": 76, "end": 72, "profile": "fair"},
    "BAT-2024-106": {"start": 92, "end": 89, "profile": "healthy"},
    "BAT-2024-107": {"start": 45, "end": 28, "profile": "critical"},
    "BAT-2024-108": {"start": 90, "end": 87, "profile": "healthy"},
    "BAT-2024-109": {"start": 78, "end": 73, "profile": "fair"},
    "BAT-2024-110": {"start": 85, "end": 82, "profile": "normal"},
    "BAT-2024-111": {"start": 70, "end": 62, "profile": "degrading_fast"},
    "BAT-2024-112": {"start": 93, "end": 91, "profile": "healthy"},
    "BAT-2024-113": {"start": 55, "end": 48, "profile": "poor"},
    "BAT-2024-114": {"start": 90, "end": 87, "profile": "healthy"},
    "BAT-2024-115": {"start": 82, "end": 78, "profile": "normal"},
    "BAT-2024-116": {"start": 97, "end": 95, "profile": "excellent"},
    "BAT-2024-117": {"start": 60, "end": 52, "profile": "degrading_fast"},
    "BAT-2024-118": {"start": 88, "end": 86, "profile": "normal"},
    "BAT-2024-119": {"start": 74, "end": 68, "profile": "fair"},
    "BAT-2024-120": {"start": 91, "end": 88, "profile": "healthy"},
    "BAT-2024-121": {"start": 83, "end": 80, "profile": "normal"},
    "BAT-2024-122": {"start": 35, "end": 22, "profile": "critical"},
    "BAT-2024-123": {"start": 87, "end": 84, "profile": "normal"},
    "BAT-2024-124": {"start": 79, "end": 74, "profile": "fair"},
}

def seed_health_data():
    with Session(engine) as session:
        print("🚀 Starting Battery Health Data Seeding...")

        # Ensure schema exists
        with engine.connect() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS inventory;"))
            conn.commit()

        # Create tables if they don't exist
        from sqlmodel import SQLModel
        SQLModel.metadata.create_all(engine)
        print("📦 Ensured all tables exist.")

        # Get admin user for recorded_by
        admin = session.exec(select(User).where(User.is_superuser == True)).first()
        admin_id = admin.id if admin else None

        # Clean existing health data (idempotent)
        try:
            session.exec(text("DELETE FROM inventory.battery_health_alerts"))
            session.exec(text("DELETE FROM inventory.battery_maintenance_schedules"))
            session.exec(text("DELETE FROM inventory.battery_health_snapshots"))
            session.commit()
            print("🧹 Cleaned existing health data.")
        except Exception:
            session.rollback()
            print("🧹 Tables are fresh — no data to clean.")

        batteries = session.exec(select(Battery)).all()
        if not batteries:
            print("❌ No batteries found. Run seed_batteries_advanced.py first.")
            return

        battery_map = {b.serial_number: b for b in batteries}
        now = datetime.now(UTC)
        snapshot_count = 0
        maintenance_count = 0
        alert_count = 0

        for serial, profile in BATTERY_PROFILES.items():
            battery = battery_map.get(serial)
            if not battery:
                print(f"⏩ Battery {serial} not found. Skipping.")
                continue

            start_health = profile["start"]
            end_health = profile["end"]
            total_drop = start_health - end_health

            # --- 1. Generate 13 weekly health snapshots (90 days) ---
            for week in range(13):
                # Linear interpolation with slight randomness
                base_health = start_health - (total_drop * week / 12)
                jitter = random.uniform(-0.5, 0.5)
                health = round(max(0, min(100, base_health + jitter)), 1)

                # Realistic telemetry
                base_voltage = 48.0 + (health / 100 * 4.0)  # 48-52V range
                voltage = round(base_voltage + random.uniform(-0.3, 0.3), 1)
                
                temp = round(random.uniform(28, 42) if profile["profile"] != "critical" else random.uniform(38, 52), 1)
                resistance = round(15 + (100 - health) * 0.3 + random.uniform(-1, 1), 1)
                cycles_value = battery.total_cycles + (week * random.randint(3, 8)) if battery.total_cycles else random.randint(100, 500) + week * 5

                snapshot = BatteryHealthSnapshot(
                    battery_id=battery.id,
                    health_percentage=health,
                    voltage=voltage,
                    temperature=temp,
                    internal_resistance=max(5, resistance),
                    charge_cycles=cycles_value,
                    snapshot_type=random.choice([SnapshotType.MANUAL, SnapshotType.AUTOMATED, SnapshotType.IOT_SYNC]),
                    recorded_by=admin_id if random.random() > 0.4 else None,
                    recorded_at=now - timedelta(weeks=12 - week, hours=random.randint(0, 12))
                )
                session.add(snapshot)
                snapshot_count += 1

            # --- 2. Update battery's current health to the end value ---
            battery.health_percentage = end_health
            if end_health > 80:
                battery.health_status = BatteryHealth.GOOD
            elif end_health > 50:
                battery.health_status = BatteryHealth.FAIR
            elif end_health > 30:
                battery.health_status = BatteryHealth.POOR
            else:
                battery.health_status = BatteryHealth.CRITICAL
            session.add(battery)

            # --- 3. Generate maintenance schedules ---
            if profile["profile"] in ("degrading_fast", "critical", "poor"):
                # More maintenance for degrading batteries
                for m in range(random.randint(2, 4)):
                    days_ago = random.randint(5, 80)
                    m_type = random.choice(list(MaintenanceType))
                    m_status = random.choice([MaintenanceStatus.COMPLETED, MaintenanceStatus.COMPLETED, MaintenanceStatus.OVERDUE])
                    
                    sched = BatteryMaintenanceSchedule(
                        battery_id=battery.id,
                        scheduled_date=now - timedelta(days=days_ago),
                        maintenance_type=m_type,
                        priority=MaintenancePriority.HIGH if profile["profile"] == "critical" else MaintenancePriority.MEDIUM,
                        assigned_to=admin_id,
                        status=m_status,
                        notes=f"{'Urgent' if profile['profile'] == 'critical' else 'Routine'} {m_type.value} for {serial}",
                        health_before=start_health - random.randint(0, 5) if m_status == MaintenanceStatus.COMPLETED else None,
                        health_after=start_health - random.randint(0, 3) + random.randint(2, 8) if m_status == MaintenanceStatus.COMPLETED else None,
                        completed_at=now - timedelta(days=days_ago - 1) if m_status == MaintenanceStatus.COMPLETED else None,
                        created_by=admin_id,
                    )
                    session.add(sched)
                    maintenance_count += 1

                # Add an upcoming scheduled maintenance
                sched_future = BatteryMaintenanceSchedule(
                    battery_id=battery.id,
                    scheduled_date=now + timedelta(days=random.randint(1, 7)),
                    maintenance_type=MaintenanceType.DEEP_SERVICE,
                    priority=MaintenancePriority.CRITICAL if profile["profile"] == "critical" else MaintenancePriority.HIGH,
                    assigned_to=admin_id,
                    status=MaintenanceStatus.SCHEDULED,
                    notes=f"Upcoming service for {serial} — health at {end_health}%",
                    created_by=admin_id,
                )
                session.add(sched_future)
                maintenance_count += 1

            elif profile["profile"] in ("normal", "healthy", "excellent"):
                # Occasional scheduled maintenance
                if random.random() > 0.5:
                    sched = BatteryMaintenanceSchedule(
                        battery_id=battery.id,
                        scheduled_date=now - timedelta(days=random.randint(15, 45)),
                        maintenance_type=MaintenanceType.INSPECTION,
                        priority=MaintenancePriority.LOW,
                        assigned_to=admin_id,
                        status=MaintenanceStatus.COMPLETED,
                        notes=f"Routine inspection for {serial}",
                        health_before=start_health,
                        health_after=start_health + random.randint(0, 2),
                        completed_at=now - timedelta(days=random.randint(14, 44)),
                        created_by=admin_id,
                    )
                    session.add(sched)
                    maintenance_count += 1

            # --- 4. Generate health alerts ---
            if profile["profile"] == "critical":
                alert1 = BatteryHealthAlert(
                    battery_id=battery.id,
                    alert_type=AlertType.CRITICAL_HEALTH,
                    severity=AlertSeverity.CRITICAL,
                    message=f"Battery {serial} health critically low at {end_health}%. Immediate replacement recommended.",
                    is_resolved=False,
                    created_at=now - timedelta(days=3)
                )
                session.add(alert1)
                alert_count += 1

                if profile.get("start", 100) - profile.get("end", 0) > 10:
                    alert2 = BatteryHealthAlert(
                        battery_id=battery.id,
                        alert_type=AlertType.RAPID_DEGRADATION,
                        severity=AlertSeverity.CRITICAL,
                        message=f"Battery {serial} lost {start_health - end_health}% health in 90 days — rapid degradation detected.",
                        is_resolved=False,
                        created_at=now - timedelta(days=7)
                    )
                    session.add(alert2)
                    alert_count += 1

            elif profile["profile"] == "degrading_fast":
                alert = BatteryHealthAlert(
                    battery_id=battery.id,
                    alert_type=AlertType.RAPID_DEGRADATION,
                    severity=AlertSeverity.WARNING,
                    message=f"Battery {serial} health dropped {start_health - end_health}% in last 90 days.",
                    is_resolved=False,
                    created_at=now - timedelta(days=5)
                )
                session.add(alert)
                alert_count += 1

            elif profile["profile"] == "poor":
                alert = BatteryHealthAlert(
                    battery_id=battery.id,
                    alert_type=AlertType.OVERDUE_SERVICE,
                    severity=AlertSeverity.WARNING,
                    message=f"Battery {serial} overdue for deep service — health at {end_health}%.",
                    is_resolved=False,
                    created_at=now - timedelta(days=10)
                )
                session.add(alert)
                alert_count += 1

            # Resolved alerts for variety
            if profile["profile"] in ("normal", "fair") and random.random() > 0.6:
                old_alert = BatteryHealthAlert(
                    battery_id=battery.id,
                    alert_type=AlertType.HIGH_TEMP,
                    severity=AlertSeverity.INFO,
                    message=f"Battery {serial} recorded high temperature during charging.",
                    is_resolved=True,
                    resolved_by=admin_id,
                    resolved_at=now - timedelta(days=random.randint(10, 30)),
                    resolution_reason="Temperature normalized after cooling period.",
                    created_at=now - timedelta(days=random.randint(31, 60))
                )
                session.add(old_alert)
                alert_count += 1

            print(f"✅ Seeded health data for {serial} ({profile['profile']})")

        session.commit()
        print(f"\n✨ Battery Health Seeding Complete!")
        print(f"   📊 Snapshots: {snapshot_count}")
        print(f"   🔧 Maintenance Schedules: {maintenance_count}")
        print(f"   🚨 Alerts: {alert_count}")


if __name__ == "__main__":
    seed_health_data()
