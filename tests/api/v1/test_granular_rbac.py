"""
Tests for Granular RBAC Implementation (SPEC.md)

Covers:
1. User.all_permissions property
2. User.has_permission() method
3. require_permission dependency (403 on missing permission)
4. require_role dependency (403 on missing role)
5. Row-level filtering: Dealers see only their stations
6. Row-level filtering: Dealers see only batteries at their stations
7. Row-level filtering: Drivers see only batteries assigned to them
8. Admin/Superuser sees everything
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.api import deps
from app.models.user import User
from app.models.rbac import Role, Permission, UserRole, RolePermission
from app.models.station import Station
from app.models.battery import Battery
from app.models.dealer import DealerProfile
from app.models.driver_profile import DriverProfile


# ──────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────

def create_permission(session: Session, slug: str, module: str = "test", action: str = "read") -> Permission:
    perm = Permission(slug=slug, module=module, action=action)
    session.add(perm)
    session.commit()
    session.refresh(perm)
    return perm


def create_role_with_permissions(session: Session, name: str, perm_slugs: list) -> Role:
    role = Role(name=name, is_active=True)
    session.add(role)
    session.commit()

    for slug in perm_slugs:
        perm = session.exec(select(Permission).where(Permission.slug == slug)).first()
        if not perm:
            perm = create_permission(session, slug)
        role.permissions.append(perm)

    session.add(role)
    session.commit()
    session.refresh(role)
    return role


def create_user(session: Session, email: str, is_superuser: bool = False) -> User:
    user = User(email=email, is_active=True, is_superuser=is_superuser)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def assign_role(session: Session, user: User, role: Role):
    session.add(UserRole(user_id=user.id, role_id=role.id))
    session.commit()


def create_dealer_profile(session: Session, user: User) -> DealerProfile:
    profile = DealerProfile(
        user_id=user.id,
        business_name="Test Dealer",
        contact_person="Test Person",
        contact_email="dealer@test.com",
        contact_phone="1234567890",
        address_line1="123 Test St",
        city="Hyderabad",
        state="Telangana",
        pincode="500001",
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def create_driver_profile(session: Session, user: User) -> DriverProfile:
    profile = DriverProfile(
        user_id=user.id,
        license_number="DL12345",
        vehicle_type="e-bike",
        vehicle_plate="KA01AB1234",
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def create_station(session: Session, name: str, dealer_id: int = None) -> Station:
    station = Station(
        name=name,
        address="Test Address",
        latitude=17.385,
        longitude=78.4867,
        dealer_id=dealer_id,
    )
    session.add(station)
    session.commit()
    session.refresh(station)
    return station


def create_battery(session: Session, serial: str, location_type: str = None, location_id: int = None) -> Battery:
    battery = Battery(
        serial_number=serial,
        spec_id=None,
        batch_id=None,
        status="active",
        location_type=location_type,
        location_id=location_id,
    )
    session.add(battery)
    session.commit()
    session.refresh(battery)
    return battery


# ──────────────────────────────────────────────────
# 1. User.all_permissions Tests
# ──────────────────────────────────────────────────

class TestUserAllPermissions:
    def test_no_roles_returns_empty(self, session: Session):
        user = create_user(session, "noroles@test.com")
        assert user.all_permissions == set()

    def test_single_role_returns_permissions(self, session: Session):
        role = create_role_with_permissions(session, "Reader", ["battery:read", "station:read"])
        user = create_user(session, "reader@test.com")
        assign_role(session, user, role)

        session.refresh(user)
        assert user.all_permissions == {"battery:read", "station:read"}

    def test_multiple_roles_aggregates(self, session: Session):
        role1 = create_role_with_permissions(session, "Role A", ["battery:read"])
        role2 = create_role_with_permissions(session, "Role B", ["station:read", "station:create"])
        user = create_user(session, "multi@test.com")
        assign_role(session, user, role1)
        assign_role(session, user, role2)

        session.refresh(user)
        assert user.all_permissions == {"battery:read", "station:read", "station:create"}

    def test_duplicate_permissions_deduped(self, session: Session):
        # Both roles have battery:read
        role1 = create_role_with_permissions(session, "Role X", ["battery:read"])
        role2 = create_role_with_permissions(session, "Role Y", ["battery:read", "station:read"])
        user = create_user(session, "dedup@test.com")
        assign_role(session, user, role1)
        assign_role(session, user, role2)

        session.refresh(user)
        assert user.all_permissions == {"battery:read", "station:read"}


# ──────────────────────────────────────────────────
# 2. User.has_permission Tests
# ──────────────────────────────────────────────────

class TestUserHasPermission:
    def test_has_permission_true(self, session: Session):
        role = create_role_with_permissions(session, "Tester", ["battery:read"])
        user = create_user(session, "hasperm@test.com")
        assign_role(session, user, role)

        session.refresh(user)
        assert user.has_permission("battery:read") is True

    def test_has_permission_false(self, session: Session):
        role = create_role_with_permissions(session, "Limited", ["battery:read"])
        user = create_user(session, "noperm@test.com")
        assign_role(session, user, role)

        session.refresh(user)
        assert user.has_permission("station:delete") is False

    def test_superuser_bypasses(self, session: Session):
        user = create_user(session, "super@test.com", is_superuser=True)
        # Superuser has no roles but should still pass
        assert user.has_permission("any:permission") is True


# ──────────────────────────────────────────────────
# 3. require_permission Dependency Tests
# ──────────────────────────────────────────────────

class TestRequirePermission:
    def test_403_without_permission(self, client: TestClient, session: Session):
        user = create_user(session, "noaccess@test.com")
        role = create_role_with_permissions(session, "NoStation", ["battery:read"])
        assign_role(session, user, role)
        session.refresh(user)

        # Override get_current_user to return our user
        app = client.app
        app.dependency_overrides[deps.get_current_user] = lambda: user

        # GET /stations requires station:read — user only has battery:read
        resp = client.get("/api/v1/stations/")
        assert resp.status_code == 403
        assert "station:read" in resp.json()["detail"]

    def test_200_with_permission(self, client: TestClient, session: Session):
        user = create_user(session, "hasaccess@test.com")
        role = create_role_with_permissions(session, "StationReader", ["station:read"])
        assign_role(session, user, role)
        session.refresh(user)

        app = client.app
        app.dependency_overrides[deps.get_current_user] = lambda: user

        resp = client.get("/api/v1/stations/")
        assert resp.status_code == 200

    def test_superuser_bypasses_permission(self, client: TestClient, session: Session):
        user = create_user(session, "superadmin@test.com", is_superuser=True)

        app = client.app
        app.dependency_overrides[deps.get_current_user] = lambda: user

        resp = client.get("/api/v1/stations/")
        assert resp.status_code == 200

    def test_403_batteries_without_permission(self, client: TestClient, session: Session):
        user = create_user(session, "nobatt@test.com")
        role = create_role_with_permissions(session, "StationOnly", ["station:read"])
        assign_role(session, user, role)
        session.refresh(user)

        app = client.app
        app.dependency_overrides[deps.get_current_user] = lambda: user

        resp = client.get("/api/v1/batteries/")
        assert resp.status_code == 403
        assert "battery:read" in resp.json()["detail"]


# ──────────────────────────────────────────────────
# 4. require_role Dependency Tests (unit-level)
# ──────────────────────────────────────────────────

class TestRequireRole:
    def test_role_check_passes(self, session: Session):
        from fastapi import HTTPException

        role = create_role_with_permissions(session, "Driver", [])
        user = create_user(session, "driver@test.com")
        assign_role(session, user, role)
        session.refresh(user)

        checker = deps.require_role("Driver")
        # Simulate calling the inner function
        inner = checker.__wrapped__ if hasattr(checker, "__wrapped__") else None
        # Direct test: the checker is a closure that returns a function
        # We call it manually
        result = checker(current_user=user)  # type: ignore
        assert result == user

    def test_role_check_fails(self, session: Session):
        from fastapi import HTTPException

        user = create_user(session, "norole@test.com")
        session.refresh(user)

        checker = deps.require_role("Driver")
        with pytest.raises(HTTPException) as exc_info:
            checker(current_user=user)  # type: ignore
        assert exc_info.value.status_code == 403

    def test_superuser_bypasses_role(self, session: Session):
        user = create_user(session, "superboss@test.com", is_superuser=True)

        checker = deps.require_role("NonExistentRole")
        result = checker(current_user=user)  # type: ignore
        assert result == user


# ──────────────────────────────────────────────────
# 5. Row-Level Filtering: Dealer Stations
# ──────────────────────────────────────────────────

class TestDealerStationFiltering:
    def test_dealer_sees_only_own_stations(self, client: TestClient, session: Session):
        # Create dealer user with profile
        user = create_user(session, "dealer@test.com")
        role = create_role_with_permissions(session, "DealerRole", ["station:read"])
        assign_role(session, user, role)
        dealer_profile = create_dealer_profile(session, user)
        session.refresh(user)

        # Create stations: 2 owned by dealer, 1 owned by someone else
        s1 = create_station(session, "Dealer Station 1", dealer_id=dealer_profile.id)
        s2 = create_station(session, "Dealer Station 2", dealer_id=dealer_profile.id)
        s3 = create_station(session, "Other Station", dealer_id=999)

        app = client.app
        app.dependency_overrides[deps.get_current_user] = lambda: user

        resp = client.get("/api/v1/stations/")
        assert resp.status_code == 200
        data = resp.json()
        station_names = [s["name"] for s in data]
        assert "Dealer Station 1" in station_names
        assert "Dealer Station 2" in station_names
        assert "Other Station" not in station_names

    def test_superuser_sees_all_stations(self, client: TestClient, session: Session):
        admin = create_user(session, "admin@test.com", is_superuser=True)

        s1 = create_station(session, "Station A")
        s2 = create_station(session, "Station B")

        app = client.app
        app.dependency_overrides[deps.get_current_user] = lambda: admin

        resp = client.get("/api/v1/stations/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2


# ──────────────────────────────────────────────────
# 6. Row-Level Filtering: Dealer Batteries
# ──────────────────────────────────────────────────

class TestDealerBatteryFiltering:
    def test_dealer_sees_only_batteries_at_own_stations(self, client: TestClient, session: Session):
        user = create_user(session, "dealbat@test.com")
        role = create_role_with_permissions(session, "DealerBat", ["battery:read"])
        assign_role(session, user, role)
        dealer_profile = create_dealer_profile(session, user)
        session.refresh(user)

        # Dealer's station
        own_station = create_station(session, "My Station", dealer_id=dealer_profile.id)
        # Other station
        other_station = create_station(session, "Not Mine", dealer_id=999)

        # Batteries at dealer's station
        b1 = create_battery(session, "BAT-001", location_type="station", location_id=own_station.id)
        # Batteries at other station
        b2 = create_battery(session, "BAT-002", location_type="station", location_id=other_station.id)
        # Battery with a driver (not at a station)
        b3 = create_battery(session, "BAT-003", location_type="driver", location_id=1)

        app = client.app
        app.dependency_overrides[deps.get_current_user] = lambda: user

        resp = client.get("/api/v1/batteries/")
        assert resp.status_code == 200
        data = resp.json()
        serials = [b["serial_number"] for b in data]
        assert "BAT-001" in serials
        assert "BAT-002" not in serials
        assert "BAT-003" not in serials


# ──────────────────────────────────────────────────
# 7. Row-Level Filtering: Driver Batteries
# ──────────────────────────────────────────────────

class TestDriverBatteryFiltering:
    def test_driver_sees_only_assigned_batteries(self, client: TestClient, session: Session):
        user = create_user(session, "drivebat@test.com")
        role = create_role_with_permissions(session, "DriverBat", ["battery:read"])
        assign_role(session, user, role)
        driver_profile = create_driver_profile(session, user)
        session.refresh(user)

        # Battery assigned to this driver
        b1 = create_battery(session, "DRV-001", location_type="driver", location_id=driver_profile.id)
        # Battery assigned to another driver
        b2 = create_battery(session, "DRV-002", location_type="driver", location_id=999)
        # Battery at a station
        b3 = create_battery(session, "STN-001", location_type="station", location_id=1)

        app = client.app
        app.dependency_overrides[deps.get_current_user] = lambda: user

        resp = client.get("/api/v1/batteries/")
        assert resp.status_code == 200
        data = resp.json()
        serials = [b["serial_number"] for b in data]
        assert "DRV-001" in serials
        assert "DRV-002" not in serials
        assert "STN-001" not in serials

    def test_admin_sees_all_batteries(self, client: TestClient, session: Session):
        admin = create_user(session, "adminbat@test.com", is_superuser=True)

        b1 = create_battery(session, "ALL-001", location_type="station", location_id=1)
        b2 = create_battery(session, "ALL-002", location_type="driver", location_id=1)

        app = client.app
        app.dependency_overrides[deps.get_current_user] = lambda: admin

        resp = client.get("/api/v1/batteries/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2
