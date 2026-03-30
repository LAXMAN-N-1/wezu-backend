"""
Seed script for Finance, Logistics, and Fleet Ops modules.
Seeds: Transactions, Invoices, Settlements, Delivery Orders, Drivers, Routes, Returns,
       IoT Devices, Telemetry, Geofences, Alerts
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, UTC, timedelta
from sqlmodel import Session, select
from app.core.database import engine
from app.models.user import User
from app.models.financial import Transaction, TransactionType, TransactionStatus
from app.models.invoice import Invoice
from app.models.settlement import Settlement
from app.models.logistics import DeliveryOrder, DeliveryType, DeliveryStatus
from app.models.driver_profile import DriverProfile
from app.models.delivery_route import DeliveryRoute, RouteStop
from app.models.return_request import ReturnRequest
from app.models.iot import IoTDevice, DeviceCommand
from app.models.geofence import Geofence
from app.models.alert import Alert
from app.models.telemetry import Telemetry
from app.models.battery import Battery

def random_date(days_back=90):
    return datetime.now(UTC) - timedelta(days=random.randint(0, days_back), hours=random.randint(0, 23), minutes=random.randint(0, 59))

def seed_all():
    with Session(engine) as db:
        users = db.exec(select(User)).all()
        if not users:
            print("ERROR: No users found. Run base seed first.")
            return
        user_ids = [u.id for u in users]

        # ─── FINANCE: TRANSACTIONS ────────────────────────────────────────
        existing_txns = db.exec(select(Transaction)).all()
        if len(existing_txns) < 10:
            print("Seeding transactions...")
            tx_types = list(TransactionType)
            methods = ["upi", "card", "netbanking", "wallet"]
            descriptions = {
                "RENTAL_PAYMENT": "Battery rental payment",
                "SECURITY_DEPOSIT": "Security deposit for rental",
                "WALLET_TOPUP": "Wallet recharge",
                "REFUND": "Refund processed",
                "FINE": "Late return fine",
                "SUBSCRIPTION": "Monthly subscription",
                "PURCHASE": "Battery purchase",
                "SWAP_FEE": "Battery swap fee",
                "LATE_FEE": "Late fee charge",
                "CASHBACK": "Cashback reward",
                "TRANSFER": "Fund transfer",
                "WITHDRAWAL": "Wallet withdrawal",
            }

            for i in range(60):
                t_type = random.choice(tx_types)
                amount = round(random.uniform(50, 8000), 2)
                tax = round(amount * 0.18, 2)
                status = random.choices(
                    [TransactionStatus.SUCCESS, TransactionStatus.PENDING, TransactionStatus.FAILED],
                    weights=[75, 15, 10]
                )[0]

                tx = Transaction(
                    user_id=random.choice(user_ids),
                    amount=amount,
                    tax_amount=tax,
                    subtotal=amount - tax,
                    transaction_type=t_type,
                    status=status,
                    payment_method=random.choice(methods),
                    payment_gateway_ref=f"pay_{random.randint(10000, 99999)}",
                    description=descriptions.get(t_type.value, "Transaction"),
                    created_at=random_date(90),
                )
                db.add(tx)
            db.commit()
            print(f"  ✓ Created 60 transactions")

        # ─── FINANCE: INVOICES ────────────────────────────────────────────
        existing_inv = db.exec(select(Invoice)).all()
        if len(existing_inv) < 5:
            print("Seeding invoices...")
            txns = db.exec(select(Transaction).where(Transaction.status == TransactionStatus.SUCCESS).limit(30)).all()
            for i, tx in enumerate(txns):
                inv = Invoice(
                    user_id=tx.user_id,
                    transaction_id=tx.id,
                    invoice_number=f"INV-2025-{1000 + i}",
                    amount=tx.amount,
                    subtotal=tx.subtotal,
                    tax_amount=tx.tax_amount,
                    total=tx.amount + tx.tax_amount,
                    gstin=f"29AABCU{random.randint(1000, 9999)}F1Z{random.randint(1, 9)}",
                    hsn_code=f"8507{random.randint(10, 99)}",
                    is_late_fee=(tx.transaction_type == TransactionType.LATE_FEE),
                    created_at=tx.created_at,
                )
                db.add(inv)
            db.commit()
            print(f"  ✓ Created {len(txns)} invoices")

        # ─── FINANCE: SETTLEMENTS ─────────────────────────────────────────
        existing_set = db.exec(select(Settlement)).all()
        if len(existing_set) < 3:
            print("Seeding settlements...")
            from app.models.dealer import DealerProfile
            dealers = db.exec(select(DealerProfile)).all()
            dealer_ids = [d.id for d in dealers] if dealers else [None]

            statuses = ["pending", "generated", "approved", "paid", "paid", "paid"]
            for i in range(15):
                month_offset = random.randint(0, 5)
                m_date = datetime.now(UTC) - timedelta(days=30 * month_offset)
                rev = round(random.uniform(20000, 80000), 2)
                comm = round(rev * random.uniform(0.08, 0.15), 2)
                platform = round(rev * 0.05, 2)
                tax = round(comm * 0.18, 2)
                net = round(comm - platform - tax, 2)
                st = random.choice(statuses)

                s = Settlement(
                    dealer_id=random.choice(dealer_ids),
                    settlement_month=m_date.strftime("%Y-%m"),
                    start_date=m_date.replace(day=1),
                    end_date=(m_date.replace(day=1) + timedelta(days=30)),
                    due_date=(m_date.replace(day=1) + timedelta(days=45)),
                    total_revenue=rev,
                    total_commission=comm,
                    platform_fee=platform,
                    tax_amount=tax,
                    net_payable=net,
                    status=st,
                    paid_at=random_date(30) if st == "paid" else None,
                    created_at=m_date,
                )
                db.add(s)
            db.commit()
            print(f"  ✓ Created 15 settlements")

        # ─── LOGISTICS: DRIVERS ───────────────────────────────────────────
        existing_drivers = db.exec(select(DriverProfile)).all()
        if len(existing_drivers) < 3:
            print("Seeding drivers...")
            driver_data = [
                ("Rajesh Kumar", "DL1234567890", "e-bike", "TS09AB1234", True, 17.445, 78.380),
                ("Sunil Yadav", "DL0987654321", "scooter", "TS10CD5678", True, 17.450, 78.375),
                ("Amit Sharma", "DL1122334455", "truck", "TS11EF9012", False, 17.440, 78.385),
                ("Venkat Reddy", "DL5566778899", "e-bike", "TS12GH3456", True, 17.435, 78.370),
                ("Pradeep Goud", "DL6677889900", "scooter", "TS13IJ7890", False, 17.455, 78.390),
                ("Manoj Singh", "DL7788990011", "e-bike", "TS14KL1234", True, 17.460, 78.365),
                ("Ravi Teja", "DL8899001122", "truck", "TS15MN5678", True, 17.430, 78.395),
                ("Kiran Babu", "DL9900112233", "scooter", "TS16OP9012", False, 17.448, 78.372),
            ]
            for name, lic, vtype, plate, online, lat, lng in driver_data:
                # Create user for driver
                driver_user = User(
                    full_name=name,
                    email=f"{name.lower().replace(' ', '.')}@wezu.com",
                    phone_number=f"+91{random.randint(7000000000, 9999999999)}",
                    hashed_password="$2b$12$placeholder",
                    role="driver",
                    is_active=True,
                )
                db.add(driver_user)
                db.flush()

                dp = DriverProfile(
                    user_id=driver_user.id,
                    license_number=lic,
                    vehicle_type=vtype,
                    vehicle_plate=plate,
                    is_online=online,
                    current_latitude=lat + random.uniform(-0.01, 0.01),
                    current_longitude=lng + random.uniform(-0.01, 0.01),
                    last_location_update=datetime.now(UTC) - timedelta(minutes=random.randint(1, 120)),
                    rating=round(random.uniform(3.5, 5.0), 1),
                    total_deliveries=random.randint(10, 200),
                    on_time_deliveries=random.randint(8, 180),
                )
                db.add(dp)
            db.commit()
            print(f"  ✓ Created 8 drivers")

        # ─── LOGISTICS: DELIVERY ORDERS ───────────────────────────────────
        existing_orders = db.exec(select(DeliveryOrder)).all()
        if len(existing_orders) < 5:
            print("Seeding delivery orders...")
            drivers = db.exec(select(DriverProfile)).all()
            driver_user_ids = [d.user_id for d in drivers] if drivers else []

            addresses = [
                ("WEZU Warehouse, Hitech City", 17.4480, 78.3774),
                ("Station Alpha, Madhapur", 17.4445, 78.3867),
                ("Station Beta, Gachibowli", 17.4405, 78.3505),
                ("Station Gamma, Jubilee Hills", 17.4325, 78.4088),
                ("Dealer Hub, Kondapur", 17.4569, 78.3627),
                ("Customer Address, Kukatpally", 17.4947, 78.3996),
                ("Return Center, Miyapur", 17.4962, 78.3563),
                ("Station Delta, Begumpet", 17.4419, 78.4678),
            ]

            for i in range(30):
                origin = random.choice(addresses)
                dest = random.choice([a for a in addresses if a != origin])
                d_type = random.choice(list(DeliveryType))
                d_status = random.choice(list(DeliveryStatus))
                driver_id = random.choice(driver_user_ids) if driver_user_ids and d_status != DeliveryStatus.PENDING else None

                order = DeliveryOrder(
                    order_type=d_type,
                    status=d_status,
                    origin_address=origin[0],
                    origin_lat=origin[1],
                    origin_lng=origin[2],
                    destination_address=dest[0],
                    destination_lat=dest[1],
                    destination_lng=dest[2],
                    assigned_driver_id=driver_id,
                    scheduled_at=random_date(30),
                    started_at=random_date(20) if d_status in [DeliveryStatus.IN_TRANSIT, DeliveryStatus.DELIVERED] else None,
                    completed_at=random_date(10) if d_status == DeliveryStatus.DELIVERED else None,
                    otp_verified=(d_status == DeliveryStatus.DELIVERED),
                    created_at=random_date(60),
                )
                db.add(order)
            db.commit()
            print(f"  ✓ Created 30 delivery orders")

        # ─── LOGISTICS: ROUTES ────────────────────────────────────────────
        existing_routes = db.exec(select(DeliveryRoute)).all()
        if len(existing_routes) < 3:
            print("Seeding routes...")
            from app.models.delivery_assignment import DeliveryAssignment
            drivers = db.exec(select(DriverProfile)).all()

            # Create dummy delivery assignments for route stops
            dummy_assignments = []
            for di in range(15):
                d = random.choice(drivers) if drivers else None
                da = DeliveryAssignment(
                    driver_id=d.id if d else None,
                    status="delivered",
                    pickup_address=f"Pickup Point {di+1}, Hyderabad",
                    delivery_address=f"Delivery Point {di+1}, Hyderabad",
                )
                db.add(da)
            db.flush()
            dummy_assignments = db.exec(select(DeliveryAssignment)).all()
            da_ids = [a.id for a in dummy_assignments]

            route_names = [
                "North Hyderabad Route", "South HiTech Route", "Gachibowli Circle",
                "Madhapur Loop", "Kondapur Express", "HITEC City Run",
                "Jubilee Hills Route", "Banjara Hills Loop", "Kukatpally North",
                "Miyapur Express"
            ]
            statuses = ["PLANNED", "IN_PROGRESS", "COMPLETED", "COMPLETED", "PLANNED"]

            for i, rname in enumerate(route_names):
                d = random.choice(drivers) if drivers else None
                st = random.choice(statuses)
                total_stops = random.randint(3, 8)

                route = DeliveryRoute(
                    driver_id=d.id if d else 1,
                    route_name=rname,
                    status=st,
                    total_stops=total_stops,
                    completed_stops=total_stops if st == "COMPLETED" else random.randint(0, total_stops),
                    estimated_distance_km=round(random.uniform(10, 50), 1),
                    estimated_duration_minutes=random.randint(30, 180),
                    created_at=random_date(30),
                )
                db.add(route)
                db.flush()

                # Add stops
                for s in range(total_stops):
                    stop = RouteStop(
                        route_id=route.id,
                        delivery_assignment_id=random.choice(da_ids),
                        stop_sequence=s + 1,
                        stop_type=random.choice(["PICKUP", "DELIVERY"]),
                        address=f"Stop {s+1}, {random.choice(['Madhapur', 'Gachibowli', 'Kondapur', 'Miyapur'])}",
                        latitude=17.44 + random.uniform(-0.03, 0.03),
                        longitude=78.37 + random.uniform(-0.03, 0.03),
                        status="COMPLETED" if st == "COMPLETED" else random.choice(["PENDING", "COMPLETED"]),
                    )
                    db.add(stop)
            db.commit()
            print(f"  ✓ Created {len(route_names)} routes with stops")

        # ─── LOGISTICS: RETURNS ───────────────────────────────────────────
        existing_returns = db.exec(select(ReturnRequest)).all()
        if len(existing_returns) < 3:
            print("Seeding return requests...")
            # Get valid ecommerce order IDs
            from app.models.ecommerce import EcommerceOrder
            ecom_orders = db.exec(select(EcommerceOrder)).all()
            if ecom_orders:
                order_ids = [o.id for o in ecom_orders]
            else:
                # Create some dummy ecommerce orders
                from app.models.ecommerce import EcommerceProduct
                products = db.exec(select(EcommerceProduct).limit(1)).all()
                if products:
                    for di in range(5):
                        eo = EcommerceOrder(
                            user_id=random.choice(user_ids),
                            total_amount=round(random.uniform(500, 5000), 2),
                            status="delivered",
                        )
                        db.add(eo)
                    db.flush()
                    ecom_orders = db.exec(select(EcommerceOrder)).all()
                    order_ids = [o.id for o in ecom_orders]
                else:
                    print("  ⚠ Skipping returns (no ecommerce orders)")
                    order_ids = []

            if order_ids:
                reasons = ["Battery defective", "Wrong battery delivered", "Changed mind", "Not as expected", "Performance issues", "Damaged on arrival"]
                statuses_r = ["pending", "pickup_assigned", "in_transit", "received", "inspected", "completed", "cancelled"]
                for i in range(12):
                    ret = ReturnRequest(
                        order_id=random.choice(order_ids),
                        user_id=random.choice(user_ids),
                        reason=random.choice(reasons),
                        status=random.choice(statuses_r),
                        refund_amount=round(random.uniform(100, 5000), 2) if random.random() > 0.3 else None,
                        inspection_notes=random.choice(["Minor wear", "Good condition", "Damaged casing", None]),
                        created_at=random_date(45),
                    )
                    db.add(ret)
                db.commit()
                print(f"  ✓ Created 12 return requests")

        # ─── FLEET OPS: IOT DEVICES ──────────────────────────────────────
        existing_iot = db.exec(select(IoTDevice)).all()
        if len(existing_iot) < 5:
            print("Seeding IoT devices...")
            batteries = db.exec(select(Battery).limit(20)).all()
            battery_ids = [b.id for b in batteries] if batteries else list(range(1, 21))

            device_types = ["tracker_v1", "tracker_v2", "smart_lock", "temp_sensor"]
            protocols = ["mqtt", "http", "ble", "lora"]
            firmwares = ["v1.0.3", "v1.1.0", "v2.0.1", "v2.1.0-beta"]

            for i in range(20):
                device = IoTDevice(
                    device_id=f"WEZU-IOT-{1000 + i}",
                    device_type=random.choice(device_types),
                    firmware_version=random.choice(firmwares),
                    status=random.choices(["online", "offline", "error"], weights=[70, 20, 10])[0],
                    communication_protocol=random.choice(protocols),
                    battery_id=battery_ids[i] if i < len(battery_ids) else None,
                    last_heartbeat=datetime.now(UTC) - timedelta(minutes=random.randint(1, 600)),
                    last_ip_address=f"192.168.1.{random.randint(10, 250)}",
                )
                db.add(device)
            db.commit()
            print(f"  ✓ Created 20 IoT devices")

            # Device commands
            devices = db.exec(select(IoTDevice)).all()
            for d in random.sample(devices, min(10, len(devices))):
                for _ in range(random.randint(1, 5)):
                    cmd = DeviceCommand(
                        device_id=d.id,
                        command_type=random.choice(["LOCK", "UNLOCK", "REBOOT", "DIAGNOSTIC"]),
                        status=random.choice(["queued", "sent", "acknowledged", "executed"]),
                        created_at=random_date(30),
                    )
                    db.add(cmd)
            db.commit()
            print(f"  ✓ Created device commands")

        # ─── FLEET OPS: GEOFENCES ────────────────────────────────────────
        existing_geo = db.exec(select(Geofence)).all()
        if len(existing_geo) < 3:
            print("Seeding geofences...")
            zones = [
                ("Hitech City Zone", 17.4480, 78.3774, 2000.0, True),
                ("Gachibowli Zone", 17.4405, 78.3505, 1500.0, True),
                ("Madhapur Zone", 17.4445, 78.3867, 1800.0, True),
                ("Jubilee Hills Zone", 17.4325, 78.4088, 2500.0, True),
                ("Kondapur Zone", 17.4569, 78.3627, 1200.0, True),
                ("Kukatpally Zone", 17.4947, 78.3996, 3000.0, False),
                ("Begumpet Zone", 17.4419, 78.4678, 1000.0, True),
                ("Miyapur Zone", 17.4962, 78.3563, 2200.0, False),
            ]
            for name, lat, lng, radius, active in zones:
                geo = Geofence(
                    name=name,
                    latitude=lat,
                    longitude=lng,
                    radius_meters=radius,
                    is_active=active,
                )
                db.add(geo)
            db.commit()
            print(f"  ✓ Created 8 geofences")

        # ─── FLEET OPS: TELEMETRY ────────────────────────────────────────
        existing_tel = db.exec(select(Telemetry)).all()
        if len(existing_tel) < 10:
            print("Seeding telemetry data...")
            batteries = db.exec(select(Battery).limit(10)).all()
            bat_ids = [b.id for b in batteries] if batteries else list(range(1, 11))

            for bid in bat_ids[:5]:
                for h in range(0, 48, 2):
                    tel = Telemetry(
                        device_id=f"WEZU-IOT-{1000 + (bid % 20)}",
                        battery_id=bid,
                        voltage=round(random.uniform(48.0, 54.0), 2),
                        current=round(random.uniform(-5.0, 15.0), 2),
                        temperature=round(random.uniform(25.0, 45.0), 1),
                        soc=round(random.uniform(10.0, 100.0), 1),
                        latitude=17.44 + random.uniform(-0.02, 0.02),
                        longitude=78.37 + random.uniform(-0.02, 0.02),
                        timestamp=datetime.now(UTC) - timedelta(hours=h),
                    )
                    db.add(tel)
            db.commit()
            print(f"  ✓ Created telemetry records")

        # ─── FLEET OPS: ALERTS ────────────────────────────────────────────
        existing_alerts = db.exec(select(Alert)).all()
        if len(existing_alerts) < 5:
            print("Seeding alerts...")
            alert_types = [
                ("Battery overheating detected", "critical", "temperature"),
                ("Device went offline", "warning", "connectivity"),
                ("Low battery SoC < 10%", "warning", "battery"),
                ("Geofence breach detected", "critical", "geofence"),
                ("Firmware update available", "info", "firmware"),
                ("Unusual discharge rate", "warning", "battery"),
                ("Communication timeout", "warning", "connectivity"),
                ("Battery voltage anomaly", "critical", "voltage"),
                ("Device reboot detected", "info", "system"),
                ("SoC calibration needed", "info", "maintenance"),
                ("High current draw", "warning", "current"),
                ("GPS signal lost", "warning", "gps"),
                ("Unauthorized movement", "critical", "security"),
                ("Battery health degraded", "warning", "health"),
                ("Charging anomaly detected", "critical", "charging"),
                ("Temperature sensor fault", "critical", "sensor"),
                ("Scheduled maintenance due", "info", "maintenance"),
                ("Power supply fluctuation", "warning", "power"),
                ("Network switch detected", "info", "connectivity"),
                ("Battery cycle count high", "warning", "lifecycle"),
                ("Vibration alert", "warning", "physical"),
                ("Humidity sensor alert", "info", "environment"),
                ("Module reset required", "critical", "system"),
                ("Data sync delayed", "info", "system"),
                ("Overcurrent protection triggered", "critical", "safety"),
            ]
            from app.models.station import Station
            stations = db.exec(select(Station)).all()
            station_ids = [s.id for s in stations] if stations else [None]

            for msg, severity, atype in alert_types:
                alert = Alert(
                    station_id=random.choice(station_ids),
                    message=msg,
                    severity=severity,
                    alert_type=atype,
                    created_at=random_date(30),
                    acknowledged_at=random_date(10) if random.random() > 0.4 else None,
                )
                db.add(alert)
            db.commit()
            print(f"  ✓ Created 25 alerts")

        print("\n✅ All Phase 2 seeding complete!")


if __name__ == "__main__":
    seed_all()
