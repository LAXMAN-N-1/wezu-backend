from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Dict, List

from sqlmodel import Session, select

from app.models.battery import Battery, BatteryStatus
from app.models.battery_reservation import BatteryReservation
from app.models.station import Station
from app.services.gps_service import GPSTrackingService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class BookingService:
    ACTIVE_RESERVATION_STATUSES = {"PENDING", "ACTIVE"}
    TERMINAL_STATUSES = {"COMPLETED", "CANCELLED", "EXPIRED"}
    DEFAULT_RESERVATION_MINUTES = 30

    @staticmethod
    def _utcnow() -> datetime:
        # Store/query as naive UTC for compatibility across engines (SQLite/Postgres).
        return datetime.now(UTC).replace(tzinfo=None)

    @staticmethod
    def _normalize_status(value: str | None) -> str:
        return (value or "").strip().upper()

    @staticmethod
    def _normalize_station_status(value: str | None) -> str:
        return (value or "").strip().lower()

    @staticmethod
    def _is_station_bookable(station: Station) -> bool:
        status = BookingService._normalize_station_status(station.status)
        if status in {"maintenance", "closed", "offline", "error"}:
            return False
        return True

    @staticmethod
    def release_expired_reservations(db: Session, *, user_id: int | None = None) -> int:
        """Expire pending reservations whose reservation window has elapsed."""
        now = BookingService._utcnow()
        statement = select(BatteryReservation).where(
            BatteryReservation.status == "PENDING",
            BatteryReservation.end_time <= now,
        )
        if user_id is not None:
            statement = statement.where(BatteryReservation.user_id == user_id)

        expired = db.exec(statement).all()
        for reservation in expired:
            reservation.status = "EXPIRED"
            reservation.updated_at = now
            db.add(reservation)

        if expired:
            db.commit()
        return len(expired)

    @staticmethod
    def mark_expired_if_due(db: Session, reservation: BatteryReservation) -> bool:
        if BookingService._normalize_status(reservation.status) != "PENDING":
            return False

        now = BookingService._utcnow()
        end_time = reservation.end_time
        if end_time.tzinfo is not None:
            end_time = end_time.astimezone(UTC).replace(tzinfo=None)
        if end_time > now:
            return False

        reservation.status = "EXPIRED"
        reservation.updated_at = now
        db.add(reservation)
        db.commit()
        db.refresh(reservation)
        return True

    @staticmethod
    def get_stations_nearby(
        db: Session,
        lat: float,
        lon: float,
        radius_km: float = 10,
        limit: int = 10,
    ) -> List[Dict]:
        """Find nearby stations with currently bookable batteries."""
        stations = db.exec(select(Station)).all()

        now = BookingService._utcnow()
        reserved_rows = db.exec(
            select(BatteryReservation.battery_id)
            .where(BatteryReservation.status.in_(list(BookingService.ACTIVE_RESERVATION_STATUSES)))
            .where(BatteryReservation.end_time > now)
            .where(BatteryReservation.battery_id.is_not(None))
        ).all()
        reserved_ids = {int(row[0] if isinstance(row, tuple) else row) for row in reserved_rows if row is not None}

        results: list[dict] = []
        for station in stations:
            if not BookingService._is_station_bookable(station):
                continue
            distance = GPSTrackingService.calculate_distance(lat, lon, station.latitude, station.longitude)
            if distance > radius_km:
                continue

            battery_query = (
                select(Battery)
                .where(Battery.station_id == station.id)
                .where(Battery.status == BatteryStatus.AVAILABLE)
                .where(Battery.current_charge >= 70)
            )
            if reserved_ids:
                battery_query = battery_query.where(Battery.id.notin_(reserved_ids))

            available_count = len(db.exec(battery_query).all())
            results.append(
                {
                    "id": station.id,
                    "name": station.name,
                    "address": station.address,
                    "latitude": station.latitude,
                    "longitude": station.longitude,
                    "distance": round(distance, 2),
                    "available_batteries": available_count,
                    "rating": station.rating,
                    "is_24x7": station.is_24x7,
                }
            )

        results.sort(key=lambda row: row["distance"])
        return results[:limit]

    @staticmethod
    def create_reservation(db: Session, user_id: int, station_id: int) -> BatteryReservation:
        """Create a reservation only when station and battery availability checks pass."""
        BookingService.release_expired_reservations(db, user_id=user_id)

        station = db.get(Station, station_id)
        if not station:
            raise ValueError("Station not found")
        if not BookingService._is_station_bookable(station):
            raise ValueError("Station is currently not accepting bookings")

        now = BookingService._utcnow()
        existing = db.exec(
            select(BatteryReservation)
            .where(BatteryReservation.user_id == user_id)
            .where(BatteryReservation.status.in_(list(BookingService.ACTIVE_RESERVATION_STATUSES)))
            .where(BatteryReservation.end_time > now)
            .order_by(BatteryReservation.end_time.desc())
        ).first()
        if existing:
            raise ValueError("User already has an active reservation")

        reserved_rows = db.exec(
            select(BatteryReservation.battery_id)
            .where(BatteryReservation.status.in_(list(BookingService.ACTIVE_RESERVATION_STATUSES)))
            .where(BatteryReservation.end_time > now)
            .where(BatteryReservation.battery_id.is_not(None))
        ).all()
        reserved_ids = {int(row[0] if isinstance(row, tuple) else row) for row in reserved_rows if row is not None}

        battery_query = (
            select(Battery)
            .where(Battery.station_id == station_id)
            .where(Battery.status == BatteryStatus.AVAILABLE)
            .where(Battery.current_charge >= 70)
            .order_by(Battery.current_charge.desc(), Battery.id.asc())
        )
        if reserved_ids:
            battery_query = battery_query.where(Battery.id.notin_(reserved_ids))

        battery = db.exec(battery_query).first()
        if not battery:
            raise ValueError("No bookable batteries available at this station")

        expiry = now + timedelta(minutes=BookingService.DEFAULT_RESERVATION_MINUTES)
        reservation = BatteryReservation(
            user_id=user_id,
            station_id=station_id,
            battery_id=battery.id,
            start_time=now,
            end_time=expiry,
            status="PENDING",
            updated_at=now,
        )

        db.add(reservation)
        db.commit()
        db.refresh(reservation)

        reminder_time = reservation.end_time - timedelta(minutes=10)
        if reminder_time > BookingService._utcnow():
            try:
                NotificationService.schedule_notification(
                    db=db,
                    user_id=user_id,
                    title="Reservation Reminder",
                    message=f"Your battery reservation at {station.name} expires in 10 minutes.",
                    scheduled_at=reminder_time,
                )
            except Exception:
                logger.exception("Failed to schedule reservation reminder reservation_id=%s", reservation.id)

        return reservation

    @staticmethod
    def is_transition_allowed(current_status: str, target_status: str) -> bool:
        current = BookingService._normalize_status(current_status)
        target = BookingService._normalize_status(target_status)

        allowed_transitions = {
            "PENDING": {"ACTIVE", "CANCELLED", "EXPIRED"},
            "ACTIVE": {"COMPLETED", "CANCELLED"},
            "COMPLETED": set(),
            "CANCELLED": set(),
            "EXPIRED": set(),
        }
        return target in allowed_transitions.get(current, set())
