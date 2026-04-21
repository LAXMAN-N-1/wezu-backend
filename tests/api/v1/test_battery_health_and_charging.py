import pytest
from sqlmodel import Session, create_engine, SQLModel
from app.models.battery import Battery, BatteryLifecycleEvent
from app.models.battery_catalog import BatterySpec
from app.models.battery_health_log import BatteryHealthLog
from app.models.battery_reservation import BatteryReservation
from app.services.battery_service import BatteryService
from app.services.charging_service import ChargingService
from app.schemas.station_monitoring import OptimizationBattery
from datetime import datetime, UTC, timedelta
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.dialects.postgresql import JSONB

# Allow JSONB when running against SQLite in these unit tests
def visit_JSONB(self, type_, **kw):
    return "JSON"
SQLiteTypeCompiler.visit_JSONB = visit_JSONB

# Setup in-memory SQLite for testing
engine = create_engine("sqlite://")

@pytest.fixture(name="session")
def session_fixture():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)

def test_calculate_soh(session: Session):
    # 1. Create Spec
    spec = BatterySpec(
        name="Test Spec",
        manufacturer="Test Man",
        voltage=60.0,
        capacity_ah=20.0,
        cycle_life_expectancy=1000
    )
    session.add(spec)
    session.commit()
    
    # 2. Create Battery
    battery = Battery(
        serial_number="TEST001",
        spec_id=spec.id,
        charge_cycles=1200, # 200 over expectancy
        temperature_history=[30.0, 50.0, 50.0] # 2 high temp readings
    )
    session.add(battery)
    session.commit()
    
    # 3. Create Health Log with capacity degradation (18 Ah instead of 20 Ah)
    log = BatteryHealthLog(
        battery_id=battery.id,
        charge_percentage=100.0,
        voltage=60.0,
        current=0.0,
        temperature=30.0,
        cycle_count=1200,
        health_percentage=90.0,
        current_capacity_mah=18000.0
    )
    session.add(log)
    session.commit()
    
    # 4. Calculate SOH
    # Base: (18000/20000)*100 = 90.0
    # Cycle penalty: 200 * 0.01 = 2.0
    # Temp penalty: 2 * 0.05 = 0.1
    # Expected: 90.0 - 2.0 - 0.1 = 87.9
    
    soh = BatteryService.calculate_soh(session, battery)
    assert round(soh, 1) == 87.9

def test_update_health_status(session: Session):
    battery = Battery(serial_number="TEST002", state_of_health=65.0)
    session.add(battery)
    session.commit()
    
    status = BatteryService.update_health_status(session, battery)
    assert status == "DAMAGED"
    assert battery.health_status == "DAMAGED"
    
    # Check if alert event was logged
    from sqlmodel import select
    stmt = select(BatteryLifecycleEvent).where(BatteryLifecycleEvent.battery_id == battery.id)
    event = session.exec(stmt).first()
    assert event.event_type == "health_alert"

def test_prioritize_charging(session: Session):
    # 1. Setup Batteries
    b1 = OptimizationBattery(battery_id="1", current_charge=20.0, state_of_health=90.0)
    b2 = OptimizationBattery(battery_id="2", current_charge=80.0, state_of_health=95.0)
    
    # 2. Add a reservation for b2 (urgent)
    res = BatteryReservation(
        user_id=1,
        station_id=1,
        battery_id=2,
        start_time=datetime.now(UTC) + timedelta(minutes=30),
        end_time=datetime.now(UTC) + timedelta(hours=1),
        status="PENDING"
    )
    session.add(res)
    session.commit()
    
    # 3. Prioritize
    # b1 has lower charge but b2 is reserved. reservation_boost (1000) should win.
    queue = ChargingService.prioritize_charging(session, 1, [b1, b2])
    
    assert queue[0].battery_id == "2"
    assert queue[1].battery_id == "1"
    assert queue[0].priority_score > 1000

def test_energy_cost_penalty(session: Session, monkeypatch):
    import datetime as dt
    # Simulate Peak Hour (7 PM)
    class MockDateTime:
        def utcnow(self): return dt.datetime(2023, 1, 1, 19, 0, 0)
    monkeypatch.setattr("app.services.charging_service.datetime", MockDateTime())
    
    # Mock Demand Predictor to return 0 for predictable scoring
    monkeypatch.setattr("app.services.demand_predictor.MockDemandPredictor.predict_demand", lambda *args, **kwargs: 0.0)
    
    b1 = OptimizationBattery(battery_id="1", current_charge=50.0, state_of_health=100.0)
    # Score calculation check:
    # 1. Base Score: (100-50)*0.5 = 25.0
    # 2. Health Score: 100*0.2 = 20.0
    # 3. Peak penalty: energy_multiplier for 19:00 is 1.5. 1.5 > 1.0, so base_score *= 0.5 -> 12.5
    # 4. Final: 12.5 + 20.0 + 0 (res) + 0 (demand*10) = 32.5
    
    queue = ChargingService.prioritize_charging(session, 1, [b1])
    assert queue[0].priority_score == 32.5

def test_hardware_alert_thresholds(session: Session):
    from app.models.station import Station
    from app.models.alert import Alert
    from app.services.station_service import StationService
    
    station = Station(id=1, name="Test Station", address="Street 1", latitude=0, longitude=0)
    session.add(station)
    session.commit()
    
    # Send high temperature heartbeat
    metrics = {"temperature": 85.0, "power_consumption": 10.0, "network_latency": 100.0}
    StationService.record_heartbeat(session, 1, "ONLINE", metrics)
    
    # Check if a CRITICAL alert was created
    from sqlmodel import select
    alert = session.exec(select(Alert).where(Alert.station_id == 1)).first()
    assert alert is not None
    assert alert.severity == "CRITICAL"
    assert "High temperature" in alert.message
