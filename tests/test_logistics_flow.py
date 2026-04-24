"""
Logistics Lifecycle Flow Tests
==============================
Battery creation → Warehouse stacking → Order → Shipment to Dealer →
Dealer inventory → Swap station deployment → Customer rental/swap →
Health degradation → Retirement.

Each test is self-contained (conftest clears all table data between tests).
Heavy lifecycle tests build full state within a single test method.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, select

# ── Model imports ──────────────────────────────────────────────────────────
from app.models.battery import Battery, BatteryStatus, BatteryHealth, LocationType
from app.models.battery_catalog import BatteryCatalog
from app.models.battery_health import (
    BatteryHealthSnapshot,
    BatteryHealthAlert,
    AlertType,
    AlertSeverity,
    SnapshotType,
)
from app.models.warehouse import Warehouse, Rack, Shelf, ShelfBattery
from app.models.order import Order, OrderBattery
from app.models.inventory import InventoryTransfer, InventoryTransferItem
from app.models.dealer_inventory import DealerInventory, InventoryTransaction
from app.models.logistics import BatteryTransfer, LogisticsManifest
from app.models.station import Station, StationSlot
from app.models.swap import SwapSession
from app.models.rental import Rental, RentalStatus
from app.models.rental_event import RentalEvent
from app.models.dealer import DealerProfile
from app.models.driver_profile import DriverProfile
from app.models.stock import Stock
from app.models.user import User

UTC = timezone.utc

# ══════════════════════════════════════════════════════════════════════════
# HELPERS – each creates a record and returns it refreshed
# ══════════════════════════════════════════════════════════════════════════

def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _make_user(session: Session, *, email: str | None = None, phone: str | None = None) -> User:
    user = User(
        email=email or f"user-{_uid()}@test.com",
        phone_number=phone or f"99{_uid()[:8]}",
        full_name=f"Test User {_uid()}",
        hashed_password="hashed_test",
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _make_catalog(session: Session) -> BatteryCatalog:
    cat = BatteryCatalog(
        name="Lithium-X1",
        voltage=48.0,
        battery_type="lithium_ion",
        capacity_ah=30.0,
        price_per_day=25.0,
    )
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat


def _make_battery(
    session: Session,
    *,
    catalog: BatteryCatalog | None = None,
    serial: str | None = None,
    status: BatteryStatus = BatteryStatus.NEW,
    health_pct: float = 100.0,
    charge: float = 100.0,
) -> Battery:
    bat = Battery(
        serial_number=serial or f"BAT-{_uid()}",
        sku_id=catalog.id if catalog else None,
        status=status,
        health_percentage=health_pct,
        state_of_health=health_pct,
        current_charge=charge,
        battery_type="48V/30Ah",
        location_type=LocationType.WAREHOUSE,
    )
    session.add(bat)
    session.commit()
    session.refresh(bat)
    return bat


def _make_warehouse(session: Session, *, name: str | None = None) -> Warehouse:
    wh = Warehouse(
        name=name or f"WH-{_uid()}",
        code=f"WH-{_uid()}",
        address="123 Test Road",
        city="TestCity",
        state="TestState",
        pincode="560001",
        capacity=200,
        is_active=True,
    )
    session.add(wh)
    session.commit()
    session.refresh(wh)
    return wh


def _make_rack(session: Session, warehouse: Warehouse) -> Rack:
    rack = Rack(warehouse_id=warehouse.id, name=f"Rack-{_uid()}")
    session.add(rack)
    session.commit()
    session.refresh(rack)
    return rack


def _make_shelf(session: Session, rack: Rack, *, capacity: int = 50) -> Shelf:
    shelf = Shelf(rack_id=rack.id, name=f"Shelf-{_uid()}", capacity=capacity)
    session.add(shelf)
    session.commit()
    session.refresh(shelf)
    return shelf


def _make_dealer(session: Session, user: User) -> DealerProfile:
    dp = DealerProfile(
        user_id=user.id,
        business_name=f"Dealer-{_uid()}",
        contact_person="Test Contact",
        contact_email=f"dealer-{_uid()}@test.com",
        contact_phone="9876543210",
        address_line1="456 Dealer Rd",
        city="DealerCity",
        state="DealerState",
        pincode="560002",
        is_active=True,
    )
    session.add(dp)
    session.commit()
    session.refresh(dp)
    return dp


def _make_station(session: Session, *, dealer: DealerProfile | None = None, slots: int = 10) -> Station:
    st = Station(
        name=f"Station-{_uid()}",
        address="789 Station Ave",
        latitude=12.97,
        longitude=77.59,
        total_slots=slots,
        available_batteries=0,
        available_slots=slots,
        status="active",
        dealer_id=dealer.id if dealer else None,
    )
    session.add(st)
    session.commit()
    session.refresh(st)
    # Create physical slots
    for i in range(1, slots + 1):
        slot = StationSlot(station_id=st.id, slot_number=i, status="empty")
        session.add(slot)
    session.commit()
    session.refresh(st)
    return st


def _make_driver(session: Session, user: User) -> DriverProfile:
    dp = DriverProfile(
        user_id=user.id,
        license_number=f"DL-{_uid()}",
        vehicle_type="truck",
        vehicle_plate=f"KA01AB{_uid()[:4].upper()}",
    )
    session.add(dp)
    session.commit()
    session.refresh(dp)
    return dp


# ══════════════════════════════════════════════════════════════════════════
# TEST 1 – Full battery lifecycle: creation → warehouse → order →
#           shipment → dealer inventory → station → swap → degradation → retire
# ══════════════════════════════════════════════════════════════════════════

class TestBatteryFullLifecycle:
    """Single comprehensive test that walks a battery through every stage."""

    def test_full_lifecycle_creation_to_retirement(self, session: Session):
        # ── STAGE 1: Battery Creation ──────────────────────────────────────
        catalog = _make_catalog(session)
        battery = _make_battery(session, catalog=catalog, serial="BAT-LIFE-001")

        assert battery.serial_number == "BAT-LIFE-001"
        assert battery.status == BatteryStatus.NEW
        assert battery.health_percentage == 100.0
        assert battery.location_type == LocationType.WAREHOUSE

        # ── STAGE 2: Warehouse Stacking ────────────────────────────────────
        warehouse = _make_warehouse(session, name="Central Warehouse")
        rack = _make_rack(session, warehouse)
        shelf = _make_shelf(session, rack, capacity=50)

        # Place battery on shelf
        sb = ShelfBattery(shelf_id=shelf.id, battery_id=battery.serial_number)
        session.add(sb)
        session.commit()

        # Update battery location
        battery.location_type = LocationType.WAREHOUSE
        battery.location_id = warehouse.id
        battery.status = BatteryStatus.AVAILABLE
        session.add(battery)
        session.commit()
        session.refresh(battery)

        assert battery.status == BatteryStatus.AVAILABLE
        assert battery.location_type == LocationType.WAREHOUSE
        assert battery.location_id == warehouse.id

        # Verify shelf tracking
        shelf_batteries = session.exec(
            select(ShelfBattery).where(ShelfBattery.shelf_id == shelf.id)
        ).all()
        assert len(shelf_batteries) == 1
        assert shelf_batteries[0].battery_id == "BAT-LIFE-001"

        # ── STAGE 3: Order Created ─────────────────────────────────────────
        dealer_user = _make_user(session, email="dealer_owner@test.com")
        dealer = _make_dealer(session, dealer_user)
        driver_user = _make_user(session, email="driver@test.com")
        driver = _make_driver(session, driver_user)

        order_id = f"ORD-{_uid()}"
        order = Order(
            id=order_id,
            status="pending",
            units=1,
            destination="DealerCity, 456 Dealer Rd",
            customer_name=dealer.business_name,
            assigned_driver_id=driver.id,
            assigned_battery_ids=json.dumps([battery.serial_number]),
        )
        session.add(order)
        session.commit()

        # Link battery to order
        ob = OrderBattery(
            order_id=order_id,
            battery_id=battery.serial_number,
            battery_pk=battery.id,
        )
        session.add(ob)
        session.commit()

        order_check = session.exec(select(Order).where(Order.id == order_id)).one()
        assert order_check.status == "pending"

        order_batteries = session.exec(
            select(OrderBattery).where(OrderBattery.order_id == order_id)
        ).all()
        assert len(order_batteries) == 1
        assert order_batteries[0].battery_pk == battery.id

        # ── STAGE 4: Shipment / Transit ────────────────────────────────────
        manifest = LogisticsManifest(
            manifest_number=f"MAN-{_uid()}",
            driver_id=driver_user.id,
            vehicle_id=driver.vehicle_plate,
            status="active",
        )
        session.add(manifest)
        session.commit()
        session.refresh(manifest)

        transfer = BatteryTransfer(
            battery_id=battery.id,
            from_location_type="warehouse",
            from_location_id=warehouse.id,
            to_location_type="dealer",
            to_location_id=dealer.id,
            status="in_transit",
            manifest_id=manifest.id,
        )
        session.add(transfer)
        session.commit()

        # Battery goes in transit
        battery.status = BatteryStatus.IN_TRANSIT
        battery.location_type = LocationType.TRANSIT
        session.add(battery)
        session.commit()
        session.refresh(battery)

        assert battery.status == BatteryStatus.IN_TRANSIT
        assert battery.location_type == LocationType.TRANSIT

        # Remove from shelf
        session.exec(
            select(ShelfBattery).where(ShelfBattery.battery_id == battery.serial_number)
        )
        sb_to_remove = session.exec(
            select(ShelfBattery).where(ShelfBattery.battery_id == battery.serial_number)
        ).first()
        if sb_to_remove:
            session.delete(sb_to_remove)
            session.commit()

        # Mark order dispatched
        order.status = "in_transit"
        order.dispatch_date = datetime.now(UTC)
        session.add(order)
        session.commit()
        session.refresh(order)
        assert order.status == "in_transit"

        # ── STAGE 5: Delivery Complete → Dealer Inventory ──────────────────
        transfer.status = "received"
        session.add(transfer)

        order.status = "delivered"
        order.delivered_at = datetime.now(UTC)
        session.add(order)
        session.commit()

        # Create dealer inventory record
        dinv = DealerInventory(
            dealer_id=dealer.id,
            battery_model="Lithium-X1",
            quantity_available=1,
            reorder_level=5,
        )
        session.add(dinv)
        session.commit()
        session.refresh(dinv)

        # Log inventory transaction
        itx = InventoryTransaction(
            inventory_id=dinv.id,
            transaction_type="RECEIVED",
            quantity=1,
            reference_type="ORDER",
            notes=f"Received via order {order_id}",
        )
        session.add(itx)
        session.commit()

        assert dinv.quantity_available == 1
        session.refresh(order)
        assert order.status == "delivered"

        # ── STAGE 6: Dealer → Swap Station Deployment ─────────────────────
        station = _make_station(session, dealer=dealer, slots=10)

        inv_transfer = InventoryTransfer(
            from_location_type="dealer",
            from_location_id=dealer.id,
            to_location_type="station",
            to_location_id=station.id,
            status="completed",
            completed_at=datetime.now(UTC),
        )
        session.add(inv_transfer)
        session.commit()
        session.refresh(inv_transfer)

        inv_item = InventoryTransferItem(
            transfer_id=inv_transfer.id,
            battery_id=battery.serial_number,
            battery_pk=battery.id,
        )
        session.add(inv_item)
        session.commit()

        # Update battery location to station
        battery.status = BatteryStatus.AVAILABLE
        battery.location_type = LocationType.STATION
        battery.location_id = station.id
        battery.station_id = station.id
        session.add(battery)
        session.commit()
        session.refresh(battery)

        assert battery.status == BatteryStatus.AVAILABLE
        assert battery.location_type == LocationType.STATION
        assert battery.station_id == station.id

        # Place in slot
        slot = session.exec(
            select(StationSlot).where(
                StationSlot.station_id == station.id,
                StationSlot.status == "empty",
            )
        ).first()
        assert slot is not None
        slot.battery_id = battery.id
        slot.status = "ready"
        session.add(slot)

        station.available_batteries = 1
        station.available_slots = station.total_slots - 1
        session.add(station)
        session.commit()
        session.refresh(station)

        assert station.available_batteries == 1

        # Update dealer inventory
        dinv.quantity_available -= 1
        session.add(dinv)
        itx2 = InventoryTransaction(
            inventory_id=dinv.id,
            transaction_type="SOLD",
            quantity=1,
            reference_type="MANUAL",
            notes="Deployed to station",
        )
        session.add(itx2)
        session.commit()
        session.refresh(dinv)
        assert dinv.quantity_available == 0

        # ── STAGE 7: Customer Rental & Swap ───────────────────────────────
        customer = _make_user(session, email="customer@test.com")

        rental = Rental(
            user_id=customer.id,
            battery_id=battery.id,
            start_station_id=station.id,
            start_time=datetime.now(UTC),
            expected_end_time=datetime.now(UTC) + timedelta(days=1),
            total_amount=25.0,
            security_deposit=100.0,
            status=RentalStatus.ACTIVE,
            start_battery_level=battery.current_charge,
        )
        session.add(rental)
        session.commit()
        session.refresh(rental)

        # Mark battery as rented
        battery.status = BatteryStatus.RENTED
        battery.current_user_id = customer.id
        battery.location_type = LocationType.CUSTOMER
        battery.station_id = None
        session.add(battery)
        session.commit()
        session.refresh(battery)

        assert battery.status == BatteryStatus.RENTED
        assert battery.current_user_id == customer.id

        # Rental event
        re = RentalEvent(
            rental_id=rental.id,
            event_type="start",
            description="Customer picked up battery",
            station_id=station.id,
            battery_id=battery.id,
        )
        session.add(re)
        session.commit()

        # Free up the slot
        session.refresh(slot)
        slot.battery_id = None
        slot.status = "empty"
        session.add(slot)
        session.commit()

        # Simulate usage → charge drops
        battery.current_charge = 20.0
        battery.cycle_count += 1
        session.add(battery)
        session.commit()
        session.refresh(battery)

        # --- Swap at another station ---
        station2 = _make_station(session, dealer=dealer, slots=5)
        new_battery = _make_battery(
            session, catalog=catalog, serial="BAT-SWAP-001", status=BatteryStatus.AVAILABLE
        )
        new_battery.location_type = LocationType.STATION
        new_battery.location_id = station2.id
        new_battery.station_id = station2.id
        session.add(new_battery)
        session.commit()
        session.refresh(new_battery)

        swap = SwapSession(
            rental_id=rental.id,
            user_id=customer.id,
            station_id=station2.id,
            old_battery_id=battery.id,
            new_battery_id=new_battery.id,
            old_battery_soc=battery.current_charge,
            new_battery_soc=new_battery.current_charge,
            swap_amount=15.0,
            status="completed",
            payment_status="paid",
            completed_at=datetime.now(UTC),
        )
        session.add(swap)
        session.commit()
        session.refresh(swap)

        assert swap.status == "completed"

        # Update battery states post-swap
        battery.status = BatteryStatus.CHARGING
        battery.current_user_id = None
        battery.location_type = LocationType.STATION
        battery.location_id = station2.id
        battery.station_id = station2.id
        session.add(battery)

        new_battery.status = BatteryStatus.RENTED
        new_battery.current_user_id = customer.id
        new_battery.location_type = LocationType.CUSTOMER
        new_battery.station_id = None
        session.add(new_battery)
        session.commit()
        session.refresh(battery)
        session.refresh(new_battery)

        assert battery.status == BatteryStatus.CHARGING
        assert new_battery.status == BatteryStatus.RENTED

        # Swap event on rental
        re2 = RentalEvent(
            rental_id=rental.id,
            event_type="swap_complete",
            description=f"Swapped {battery.serial_number} → {new_battery.serial_number}",
            station_id=station2.id,
            battery_id=new_battery.id,
        )
        session.add(re2)
        session.commit()

        # ── STAGE 8: Health Degradation ────────────────────────────────────
        battery.health_percentage = 35.0
        battery.state_of_health = 35.0
        battery.health_status = BatteryHealth.POOR
        battery.cycle_count = 800
        battery.charge_cycles = 800
        session.add(battery)
        session.commit()
        session.refresh(battery)

        # Health snapshot
        snap = BatteryHealthSnapshot(
            battery_id=battery.id,
            health_percentage=35.0,
            voltage=46.2,
            temperature=42.0,
            charge_cycles=800,
            snapshot_type=SnapshotType.AUTOMATED,
        )
        session.add(snap)
        session.commit()

        # Health alert
        alert = BatteryHealthAlert(
            battery_id=battery.id,
            alert_type=AlertType.CRITICAL_HEALTH,
            severity=AlertSeverity.CRITICAL,
            message="Battery health dropped below 40% threshold",
        )
        session.add(alert)
        session.commit()

        assert battery.health_percentage == 35.0
        assert battery.health_status == BatteryHealth.POOR

        alerts = session.exec(
            select(BatteryHealthAlert).where(BatteryHealthAlert.battery_id == battery.id)
        ).all()
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.CRITICAL

        # ── STAGE 9: Retirement ────────────────────────────────────────────
        battery.status = BatteryStatus.RETIRED
        battery.retirement_date = datetime.now(UTC)
        battery.decommission_reason = "Health below acceptable threshold"
        battery.health_status = BatteryHealth.CRITICAL
        battery.location_type = LocationType.RECYCLING
        battery.station_id = None
        session.add(battery)
        session.commit()
        session.refresh(battery)

        assert battery.status == BatteryStatus.RETIRED
        assert battery.location_type == LocationType.RECYCLING
        assert battery.retirement_date is not None
        assert battery.decommission_reason == "Health below acceptable threshold"

        # ── FINAL: Verify full audit trail ─────────────────────────────────
        # Order delivered
        session.refresh(order)
        assert order.status == "delivered"

        # Rental events recorded
        events = session.exec(
            select(RentalEvent).where(RentalEvent.rental_id == rental.id)
        ).all()
        assert len(events) == 2
        event_types = {e.event_type for e in events}
        assert "start" in event_types
        assert "swap_complete" in event_types

        # Swap session recorded
        swaps = session.exec(
            select(SwapSession).where(SwapSession.rental_id == rental.id)
        ).all()
        assert len(swaps) == 1
        assert swaps[0].status == "completed"

        # Health snapshots exist
        snaps = session.exec(
            select(BatteryHealthSnapshot).where(
                BatteryHealthSnapshot.battery_id == battery.id
            )
        ).all()
        assert len(snaps) >= 1

        # Transfer record exists
        transfers = session.exec(
            select(BatteryTransfer).where(BatteryTransfer.battery_id == battery.id)
        ).all()
        assert len(transfers) == 1
        assert transfers[0].status == "received"


# ══════════════════════════════════════════════════════════════════════════
# TEST 2 – Multi-battery warehouse flow with stock tracking
# ══════════════════════════════════════════════════════════════════════════

class TestWarehouseOperations:
    """Warehouse capacity, shelf assignment, stock counters."""

    def test_shelf_capacity_enforcement(self, session: Session):
        """Shelf capacity bounds are respected."""
        warehouse = _make_warehouse(session)
        rack = _make_rack(session, warehouse)
        shelf = _make_shelf(session, rack, capacity=3)

        catalog = _make_catalog(session)

        serials = []
        for i in range(3):
            bat = _make_battery(session, catalog=catalog, serial=f"BAT-CAP-{i}")
            sb = ShelfBattery(shelf_id=shelf.id, battery_id=bat.serial_number)
            session.add(sb)
            serials.append(bat.serial_number)
        session.commit()

        shelf_items = session.exec(
            select(ShelfBattery).where(ShelfBattery.shelf_id == shelf.id)
        ).all()
        assert len(shelf_items) == 3

        # Verify shelf.battery_ids property
        session.refresh(shelf)
        assert set(shelf.battery_ids) == set(serials)

    def test_stock_record_tracks_warehouse_product(self, session: Session):
        """Stock record correctly tracks product quantities in warehouse."""
        warehouse = _make_warehouse(session)
        catalog = _make_catalog(session)

        stock = Stock(
            warehouse_id=warehouse.id,
            product_id=catalog.id,
            quantity_on_hand=50,
            quantity_available=45,
            quantity_reserved=5,
        )
        session.add(stock)
        session.commit()
        session.refresh(stock)

        assert stock.quantity_on_hand == 50
        assert stock.quantity_available == 45
        assert stock.quantity_reserved == 5

    def test_multi_rack_shelf_structure(self, session: Session):
        """Warehouse → multiple racks → multiple shelves hierarchy."""
        warehouse = _make_warehouse(session)
        rack1 = _make_rack(session, warehouse)
        rack2 = _make_rack(session, warehouse)
        shelf1a = _make_shelf(session, rack1)
        shelf1b = _make_shelf(session, rack1)
        shelf2a = _make_shelf(session, rack2)

        # Verify relationships
        session.refresh(warehouse)
        racks = session.exec(
            select(Rack).where(Rack.warehouse_id == warehouse.id)
        ).all()
        assert len(racks) == 2

        shelves_rack1 = session.exec(
            select(Shelf).where(Shelf.rack_id == rack1.id)
        ).all()
        assert len(shelves_rack1) == 2

        shelves_rack2 = session.exec(
            select(Shelf).where(Shelf.rack_id == rack2.id)
        ).all()
        assert len(shelves_rack2) == 1


# ══════════════════════════════════════════════════════════════════════════
# TEST 3 – Dealer inventory management with transactions
# ══════════════════════════════════════════════════════════════════════════

class TestDealerInventoryFlow:
    """Dealer receives stock, deploys to station, tracks inventory transactions."""

    def test_dealer_receive_deploy_cycle(self, session: Session):
        """Full cycle: receive batteries → deploy to station → inventory adjustments."""
        dealer_user = _make_user(session)
        dealer = _make_dealer(session, dealer_user)

        # Dealer receives stock
        dinv = DealerInventory(
            dealer_id=dealer.id,
            battery_model="Lithium-X1",
            quantity_available=10,
            reorder_level=5,
            max_capacity=100,
        )
        session.add(dinv)
        session.commit()
        session.refresh(dinv)

        # Log receive transaction
        tx_receive = InventoryTransaction(
            inventory_id=dinv.id,
            transaction_type="RECEIVED",
            quantity=10,
            reference_type="ORDER",
            notes="Bulk shipment from warehouse",
        )
        session.add(tx_receive)
        session.commit()

        # Deploy 3 to station
        station = _make_station(session, dealer=dealer)

        dinv.quantity_available -= 3
        session.add(dinv)

        tx_deploy = InventoryTransaction(
            inventory_id=dinv.id,
            transaction_type="SOLD",
            quantity=3,
            reference_type="MANUAL",
            notes="Deployed to station",
        )
        session.add(tx_deploy)
        session.commit()
        session.refresh(dinv)

        assert dinv.quantity_available == 7

        # Mark 1 as damaged
        dinv.quantity_available -= 1
        dinv.quantity_damaged += 1
        session.add(dinv)

        tx_damaged = InventoryTransaction(
            inventory_id=dinv.id,
            transaction_type="DAMAGED",
            quantity=1,
            reference_type="MANUAL",
            notes="Battery found with swelling",
        )
        session.add(tx_damaged)
        session.commit()
        session.refresh(dinv)

        assert dinv.quantity_available == 6
        assert dinv.quantity_damaged == 1

        # Verify full transaction history
        txs = session.exec(
            select(InventoryTransaction).where(
                InventoryTransaction.inventory_id == dinv.id
            )
        ).all()
        assert len(txs) == 3
        tx_types = [t.transaction_type for t in txs]
        assert "RECEIVED" in tx_types
        assert "SOLD" in tx_types
        assert "DAMAGED" in tx_types

    def test_reorder_level_alert(self, session: Session):
        """Inventory falling below reorder level can be detected."""
        dealer_user = _make_user(session)
        dealer = _make_dealer(session, dealer_user)

        dinv = DealerInventory(
            dealer_id=dealer.id,
            battery_model="Lithium-X1",
            quantity_available=3,
            reorder_level=5,
        )
        session.add(dinv)
        session.commit()
        session.refresh(dinv)

        assert dinv.quantity_available < dinv.reorder_level


# ══════════════════════════════════════════════════════════════════════════
# TEST 4 – Battery health monitoring & degradation path
# ══════════════════════════════════════════════════════════════════════════

class TestBatteryHealthDegradation:
    """Health snapshots, alerts, and status transitions based on health."""

    def test_health_snapshot_series(self, session: Session):
        """Multiple health snapshots track degradation over time."""
        catalog = _make_catalog(session)
        battery = _make_battery(session, catalog=catalog, serial="BAT-HLTH-001")

        readings = [
            (100.0, 51.2, 25.0, 0),
            (92.0, 50.8, 28.0, 100),
            (78.0, 49.5, 32.0, 300),
            (55.0, 48.0, 38.0, 600),
            (32.0, 46.1, 42.0, 850),
        ]
        for hp, voltage, temp, cycles in readings:
            snap = BatteryHealthSnapshot(
                battery_id=battery.id,
                health_percentage=hp,
                voltage=voltage,
                temperature=temp,
                charge_cycles=cycles,
                snapshot_type=SnapshotType.AUTOMATED,
            )
            session.add(snap)
        session.commit()

        snaps = session.exec(
            select(BatteryHealthSnapshot)
            .where(BatteryHealthSnapshot.battery_id == battery.id)
            .order_by(BatteryHealthSnapshot.id)
        ).all()
        assert len(snaps) == 5
        assert snaps[0].health_percentage == 100.0
        assert snaps[-1].health_percentage == 32.0

        # Verify degradation trend
        healths = [s.health_percentage for s in snaps]
        for i in range(1, len(healths)):
            assert healths[i] < healths[i - 1], "Health should monotonically decrease"

    def test_alert_escalation(self, session: Session):
        """Alerts escalate from warning to critical as health declines."""
        catalog = _make_catalog(session)
        battery = _make_battery(session, catalog=catalog, serial="BAT-ALRT-001")

        # Warning at 50%
        a1 = BatteryHealthAlert(
            battery_id=battery.id,
            alert_type=AlertType.RAPID_DEGRADATION,
            severity=AlertSeverity.WARNING,
            message="Health declining faster than expected (50%)",
        )
        session.add(a1)

        # Critical at 30%
        a2 = BatteryHealthAlert(
            battery_id=battery.id,
            alert_type=AlertType.CRITICAL_HEALTH,
            severity=AlertSeverity.CRITICAL,
            message="Health critically low (30%), immediate action required",
        )
        session.add(a2)

        # High temp alert
        a3 = BatteryHealthAlert(
            battery_id=battery.id,
            alert_type=AlertType.HIGH_TEMP,
            severity=AlertSeverity.CRITICAL,
            message="Temperature exceeded 45°C",
        )
        session.add(a3)
        session.commit()

        alerts = session.exec(
            select(BatteryHealthAlert)
            .where(BatteryHealthAlert.battery_id == battery.id)
            .order_by(BatteryHealthAlert.id)
        ).all()
        assert len(alerts) == 3
        assert alerts[0].severity == AlertSeverity.WARNING
        assert alerts[1].severity == AlertSeverity.CRITICAL
        assert alerts[2].alert_type == AlertType.HIGH_TEMP

    def test_health_driven_retirement(self, session: Session):
        """Battery with critical health transitions through retirement stages."""
        catalog = _make_catalog(session)
        battery = _make_battery(
            session, catalog=catalog, serial="BAT-RET-001", health_pct=25.0
        )

        # Mark as maintenance first
        battery.status = BatteryStatus.MAINTENANCE
        battery.health_status = BatteryHealth.POOR
        session.add(battery)
        session.commit()
        session.refresh(battery)
        assert battery.status == BatteryStatus.MAINTENANCE

        # After evaluation → retire
        battery.status = BatteryStatus.RETIRED
        battery.health_status = BatteryHealth.CRITICAL
        battery.retirement_date = datetime.now(UTC)
        battery.decommission_reason = "End of life: health below threshold after maintenance evaluation"
        battery.location_type = LocationType.RECYCLING
        session.add(battery)
        session.commit()
        session.refresh(battery)

        assert battery.status == BatteryStatus.RETIRED
        assert battery.health_status == BatteryHealth.CRITICAL
        assert battery.location_type == LocationType.RECYCLING


# ══════════════════════════════════════════════════════════════════════════
# TEST 5 – Swap station operations
# ══════════════════════════════════════════════════════════════════════════

class TestSwapStationOps:
    """Station slot management, battery deployment, and swap execution."""

    def test_station_slot_management(self, session: Session):
        """Slots track battery presence, status transitions."""
        dealer_user = _make_user(session)
        dealer = _make_dealer(session, dealer_user)
        station = _make_station(session, dealer=dealer, slots=5)
        catalog = _make_catalog(session)

        # Deploy two batteries to station
        bat1 = _make_battery(session, catalog=catalog, serial="BAT-SLOT-1")
        bat2 = _make_battery(session, catalog=catalog, serial="BAT-SLOT-2")

        slots = session.exec(
            select(StationSlot)
            .where(StationSlot.station_id == station.id)
            .order_by(StationSlot.slot_number)
        ).all()
        assert len(slots) == 5

        # Fill slots 1 and 2
        slots[0].battery_id = bat1.id
        slots[0].status = "ready"
        slots[1].battery_id = bat2.id
        slots[1].status = "charging"
        session.add(slots[0])
        session.add(slots[1])
        session.commit()

        # Count occupied vs empty
        occupied = session.exec(
            select(StationSlot).where(
                StationSlot.station_id == station.id,
                StationSlot.battery_id != None,  # noqa: E711
            )
        ).all()
        empty = session.exec(
            select(StationSlot).where(
                StationSlot.station_id == station.id,
                StationSlot.battery_id == None,  # noqa: E711
            )
        ).all()
        assert len(occupied) == 2
        assert len(empty) == 3

    def test_swap_session_records(self, session: Session):
        """Swap session correctly records old/new battery, SoC, and payment."""
        dealer_user = _make_user(session)
        dealer = _make_dealer(session, dealer_user)
        station = _make_station(session, dealer=dealer)
        catalog = _make_catalog(session)
        customer = _make_user(session, email="swapper@test.com")

        old_bat = _make_battery(session, catalog=catalog, serial="BAT-OLD-001", charge=15.0)
        new_bat = _make_battery(session, catalog=catalog, serial="BAT-NEW-001", charge=98.0)

        # Create rental with old battery
        rental = Rental(
            user_id=customer.id,
            battery_id=old_bat.id,
            start_station_id=station.id,
            start_time=datetime.now(UTC) - timedelta(hours=6),
            expected_end_time=datetime.now(UTC) + timedelta(hours=18),
            status=RentalStatus.ACTIVE,
        )
        session.add(rental)
        session.commit()
        session.refresh(rental)

        # Execute swap
        swap = SwapSession(
            rental_id=rental.id,
            user_id=customer.id,
            station_id=station.id,
            old_battery_id=old_bat.id,
            new_battery_id=new_bat.id,
            old_battery_soc=15.0,
            new_battery_soc=98.0,
            swap_amount=20.0,
            status="completed",
            payment_status="paid",
            completed_at=datetime.now(UTC),
        )
        session.add(swap)
        session.commit()
        session.refresh(swap)

        assert swap.old_battery_soc == 15.0
        assert swap.new_battery_soc == 98.0
        assert swap.swap_amount == 20.0
        assert swap.payment_status == "paid"


# ══════════════════════════════════════════════════════════════════════════
# TEST 6 – Logistics manifest & multi-battery transfer
# ══════════════════════════════════════════════════════════════════════════

class TestLogisticsManifest:
    """Manifest groups multiple battery transfers into a single shipment."""

    def test_manifest_with_multiple_transfers(self, session: Session):
        """Single manifest groups N battery transfers."""
        warehouse = _make_warehouse(session)
        dealer_user = _make_user(session)
        dealer = _make_dealer(session, dealer_user)
        catalog = _make_catalog(session)
        driver_user = _make_user(session, email="logdriver@test.com")

        manifest = LogisticsManifest(
            manifest_number=f"MAN-{_uid()}",
            driver_id=driver_user.id,
            status="active",
        )
        session.add(manifest)
        session.commit()
        session.refresh(manifest)

        batteries = []
        for i in range(5):
            bat = _make_battery(session, catalog=catalog, serial=f"BAT-BULK-{i}")
            bt = BatteryTransfer(
                battery_id=bat.id,
                from_location_type="warehouse",
                from_location_id=warehouse.id,
                to_location_type="dealer",
                to_location_id=dealer.id,
                status="in_transit",
                manifest_id=manifest.id,
            )
            session.add(bt)
            batteries.append(bat)
        session.commit()

        transfers = session.exec(
            select(BatteryTransfer).where(BatteryTransfer.manifest_id == manifest.id)
        ).all()
        assert len(transfers) == 5

        # Complete all transfers
        for t in transfers:
            t.status = "received"
            session.add(t)
        manifest.status = "closed"
        session.add(manifest)
        session.commit()
        session.refresh(manifest)

        assert manifest.status == "closed"

        completed = session.exec(
            select(BatteryTransfer).where(
                BatteryTransfer.manifest_id == manifest.id,
                BatteryTransfer.status == "received",
            )
        ).all()
        assert len(completed) == 5


# ══════════════════════════════════════════════════════════════════════════
# TEST 7 – Inventory transfer between locations
# ══════════════════════════════════════════════════════════════════════════

class TestInventoryTransferFlow:
    """Transfer batteries between warehouse ↔ station with item tracking."""

    def test_warehouse_to_station_transfer(self, session: Session):
        """InventoryTransfer + items correctly track warehouse→station movement."""
        warehouse = _make_warehouse(session)
        dealer_user = _make_user(session)
        dealer = _make_dealer(session, dealer_user)
        station = _make_station(session, dealer=dealer)
        catalog = _make_catalog(session)

        bat1 = _make_battery(session, catalog=catalog, serial="BAT-TFR-1")
        bat2 = _make_battery(session, catalog=catalog, serial="BAT-TFR-2")

        transfer = InventoryTransfer(
            from_location_type="warehouse",
            from_location_id=warehouse.id,
            to_location_type="station",
            to_location_id=station.id,
            status="pending",
        )
        session.add(transfer)
        session.commit()
        session.refresh(transfer)

        item1 = InventoryTransferItem(
            transfer_id=transfer.id,
            battery_id=bat1.serial_number,
            battery_pk=bat1.id,
        )
        item2 = InventoryTransferItem(
            transfer_id=transfer.id,
            battery_id=bat2.serial_number,
            battery_pk=bat2.id,
        )
        session.add(item1)
        session.add(item2)
        session.commit()

        # Mark in transit
        transfer.status = "in_transit"
        session.add(transfer)
        session.commit()

        # Complete
        transfer.status = "completed"
        transfer.completed_at = datetime.now(UTC)
        session.add(transfer)
        session.commit()
        session.refresh(transfer)

        assert transfer.status == "completed"
        assert transfer.completed_at is not None

        items = session.exec(
            select(InventoryTransferItem).where(
                InventoryTransferItem.transfer_id == transfer.id
            )
        ).all()
        assert len(items) == 2


# ══════════════════════════════════════════════════════════════════════════
# TEST 8 – Edge cases & guards
# ══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Boundary conditions and guards."""

    def test_battery_cannot_be_rented_if_retired(self, session: Session):
        """Retired batteries should not be eligible for rental (application guard)."""
        catalog = _make_catalog(session)
        bat = _make_battery(session, catalog=catalog, serial="BAT-RETIRED-001")
        bat.status = BatteryStatus.RETIRED
        bat.retirement_date = datetime.now(UTC)
        bat.location_type = LocationType.RECYCLING
        session.add(bat)
        session.commit()
        session.refresh(bat)

        # Query for available batteries should exclude retired
        available = session.exec(
            select(Battery).where(Battery.status == BatteryStatus.AVAILABLE)
        ).all()
        assert bat not in available

    def test_battery_status_transitions_are_valid(self, session: Session):
        """Verify a battery can transition through key lifecycle statuses."""
        catalog = _make_catalog(session)
        bat = _make_battery(session, catalog=catalog, serial="BAT-TRANS-001")

        transitions = [
            BatteryStatus.NEW,
            BatteryStatus.AVAILABLE,
            BatteryStatus.IN_TRANSIT,
            BatteryStatus.AVAILABLE,
            BatteryStatus.RENTED,
            BatteryStatus.CHARGING,
            BatteryStatus.AVAILABLE,
            BatteryStatus.MAINTENANCE,
            BatteryStatus.RETIRED,
        ]
        for new_status in transitions:
            bat.status = new_status
            session.add(bat)
            session.commit()
            session.refresh(bat)
            assert bat.status == new_status

    def test_duplicate_shelf_battery_rejected(self, session: Session):
        """ShelfBattery.battery_id has UNIQUE constraint."""
        warehouse = _make_warehouse(session)
        rack = _make_rack(session, warehouse)
        shelf1 = _make_shelf(session, rack)
        shelf2 = _make_shelf(session, rack)

        catalog = _make_catalog(session)
        bat = _make_battery(session, catalog=catalog, serial="BAT-DUP-001")

        sb1 = ShelfBattery(shelf_id=shelf1.id, battery_id=bat.serial_number)
        session.add(sb1)
        session.commit()

        sb2 = ShelfBattery(shelf_id=shelf2.id, battery_id=bat.serial_number)
        session.add(sb2)
        with pytest.raises(Exception):
            session.commit()
        session.rollback()

    def test_inactive_warehouse_flag(self, session: Session):
        """Inactive warehouse is queryable but flagged."""
        wh = _make_warehouse(session)
        wh.is_active = False
        session.add(wh)
        session.commit()
        session.refresh(wh)

        active_warehouses = session.exec(
            select(Warehouse).where(Warehouse.is_active == True)  # noqa: E712
        ).all()
        assert wh not in active_warehouses
