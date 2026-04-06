from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, Optional

from sqlmodel import Session, delete, select

from app.models.rental import Rental
from app.models.station import Station
from app.models.station_metrics import StationDailyMetric


class StationMetricsService:
    @staticmethod
    def refresh_daily_metrics(
        db: Session,
        *,
        start_date: date,
        end_date: date,
        station_id: Optional[int] = None,
    ) -> int:
        if end_date < start_date:
            raise ValueError("end_date must be on or after start_date")

        # Delete existing rows in target window for deterministic recomputation.
        delete_stmt = delete(StationDailyMetric).where(
            StationDailyMetric.metric_date >= start_date,
            StationDailyMetric.metric_date <= end_date,
        )
        if station_id is not None:
            delete_stmt = delete_stmt.where(StationDailyMetric.station_id == station_id)
        db.exec(delete_stmt)

        rental_stmt = select(Rental).where(
            Rental.start_time != None,
            Rental.start_time >= datetime.combine(start_date, datetime.min.time()),
            Rental.start_time <= datetime.combine(end_date, datetime.max.time()),
        )
        rentals = db.exec(rental_stmt).all()

        aggregate: Dict[tuple[int, date], dict[str, float]] = defaultdict(
            lambda: {"started": 0.0, "completed": 0.0, "duration_total": 0.0}
        )

        for rental in rentals:
            if station_id is not None and rental.pickup_station_id != station_id:
                continue
            key = (int(rental.pickup_station_id), rental.start_time.date())
            aggregate[key]["started"] += 1
            if rental.end_time and rental.end_time >= rental.start_time:
                aggregate[key]["completed"] += 1
                aggregate[key]["duration_total"] += (
                    rental.end_time - rental.start_time
                ).total_seconds() / 60.0

        inserted = 0
        now = datetime.utcnow()
        for (metric_station_id, metric_date), row in aggregate.items():
            if station_id is not None and metric_station_id != station_id:
                continue
            completed = int(row["completed"])
            avg_duration = (row["duration_total"] / completed) if completed > 0 else None
            db.add(
                StationDailyMetric(
                    station_id=metric_station_id,
                    metric_date=metric_date,
                    rentals_started=int(row["started"]),
                    rentals_completed=completed,
                    average_duration_minutes=round(avg_duration, 2) if avg_duration is not None else None,
                    refreshed_at=now,
                )
            )
            inserted += 1

        db.flush()
        return inserted

    @staticmethod
    def get_metrics_window(
        db: Session,
        *,
        station_id: int,
        start_date: date,
        end_date: date,
        auto_refresh_if_missing: bool = True,
    ) -> list[StationDailyMetric]:
        station = db.get(Station, station_id)
        if not station or station.is_deleted:
            raise ValueError("Station not found")

        query = (
            select(StationDailyMetric)
            .where(StationDailyMetric.station_id == station_id)
            .where(StationDailyMetric.metric_date >= start_date)
            .where(StationDailyMetric.metric_date <= end_date)
            .order_by(StationDailyMetric.metric_date.asc())
        )
        rows = db.exec(query).all()

        expected_days = (end_date - start_date).days + 1
        if auto_refresh_if_missing and len(rows) < expected_days:
            StationMetricsService.refresh_daily_metrics(
                db,
                start_date=start_date,
                end_date=end_date,
                station_id=station_id,
            )
            rows = db.exec(query).all()
        return rows

    @staticmethod
    def refresh_recent_window(
        db: Session,
        *,
        days: int = 45,
    ) -> int:
        days = max(1, days)
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days - 1)
        return StationMetricsService.refresh_daily_metrics(
            db,
            start_date=start_date,
            end_date=end_date,
            station_id=None,
        )
