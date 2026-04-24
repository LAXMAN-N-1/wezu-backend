from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, List, Optional

from sqlalchemy import and_, case, func, inspect, or_
from sqlmodel import Session, select

from app.models.analytics_dashboard import AnalyticsActivityEvent, AnalyticsReportJob
from app.models.battery import Battery, BatteryLifecycleEvent
from app.models.inventory import InventoryTransfer, InventoryTransferItem, StockDiscrepancy
from app.models.order import Order
from app.models.station import Station


class AnalyticsDashboardRepository:
    _TABLE_EXISTS_CACHE_KEY = "_analytics_table_exists_cache"

    @staticmethod
    def _table_exists(session: Session, table_name: str) -> bool:
        cache = session.info.setdefault(AnalyticsDashboardRepository._TABLE_EXISTS_CACHE_KEY, {})
        cached = cache.get(table_name)
        if isinstance(cached, bool):
            return cached

        bind = session.get_bind()
        if bind is None:
            cache[table_name] = False
            return False
        inspector = inspect(bind)
        exists = table_name in inspector.get_table_names()
        cache[table_name] = exists
        return exists

    @staticmethod
    def fetch_battery_kpis(session: Session) -> dict[str, int]:
        if not AnalyticsDashboardRepository._table_exists(session, Battery.__tablename__):
            return {
                "total_batteries": 0,
                "available_batteries": 0,
                "deployed_batteries": 0,
                "in_transit_batteries": 0,
                "issue_count": 0,
            }

        total_batteries, available_batteries, deployed_batteries, in_transit_batteries, issue_count = session.exec(
            select(
                func.count(Battery.id),
                func.coalesce(
                    func.sum(
                        case(
                            (Battery.status.in_(["available", "ready", "new"]), 1),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(func.sum(case((Battery.status == "deployed", 1), else_=0)), 0),
                func.coalesce(
                    func.sum(case((Battery.status.in_(["in_transit", "reserved"]), 1), else_=0)),
                    0,
                ),
                func.coalesce(
                    func.sum(case((Battery.status.in_(["faulty", "maintenance"]), 1), else_=0)),
                    0,
                ),
            )
        ).one()

        return {
            "total_batteries": int(total_batteries or 0),
            "available_batteries": int(available_batteries or 0),
            "deployed_batteries": int(deployed_batteries or 0),
            "in_transit_batteries": int(in_transit_batteries or 0),
            "issue_count": int(issue_count or 0),
        }

    @staticmethod
    def fetch_pending_orders(session: Session) -> int:
        if not AnalyticsDashboardRepository._table_exists(session, Order.__tablename__):
            return 0

        normalized_status = func.lower(func.replace(func.replace(Order.status, "-", "_"), " ", "_"))
        stmt = select(func.count(Order.id)).where(normalized_status.in_(["pending", "assigned", "new"]))
        return int(session.exec(stmt).one() or 0)

    @staticmethod
    def fetch_revenue_for_window(
        session: Session,
        *,
        window_start_utc: datetime,
        window_end_utc: datetime,
    ) -> float:
        if not AnalyticsDashboardRepository._table_exists(session, Order.__tablename__):
            return 0.0

        normalized_status = func.lower(func.replace(func.replace(Order.status, "-", "_"), " ", "_"))
        stmt = select(func.coalesce(func.sum(Order.total_value), 0)).where(
            normalized_status.in_(["delivered", "completed", "complete", "done"]),
            Order.delivered_at.is_not(None),
            Order.delivered_at >= window_start_utc,
            Order.delivered_at <= window_end_utc,
        )
        value = session.exec(stmt).one()
        return float(value or 0.0)

    @staticmethod
    def fetch_transfer_kpis(
        session: Session,
        *,
        day_start_utc: datetime,
        day_end_utc: datetime,
        month_start_utc: datetime,
        now_utc: datetime,
    ) -> dict[str, int]:
        if not (
            AnalyticsDashboardRepository._table_exists(session, InventoryTransfer.__tablename__)
            and AnalyticsDashboardRepository._table_exists(session, InventoryTransferItem.__tablename__)
        ):
            return {
                "sent_today": 0,
                "received_today": 0,
                "pending_receipts": 0,
                "monthly_dispatch": 0,
            }

        sent_today = session.exec(
            select(func.count(InventoryTransferItem.id))
            .join(InventoryTransfer, InventoryTransferItem.transfer_id == InventoryTransfer.id)
            .where(
                InventoryTransfer.created_at >= day_start_utc,
                InventoryTransfer.created_at < day_end_utc,
            )
        ).one()

        received_today = session.exec(
            select(func.count(InventoryTransferItem.id))
            .join(InventoryTransfer, InventoryTransferItem.transfer_id == InventoryTransfer.id)
            .where(
                InventoryTransfer.status == "completed",
                InventoryTransfer.completed_at.is_not(None),
                InventoryTransfer.completed_at >= day_start_utc,
                InventoryTransfer.completed_at < day_end_utc,
            )
        ).one()

        pending_receipts = session.exec(
            select(func.count(InventoryTransfer.id)).where(InventoryTransfer.status.in_(["pending", "in_transit"]))
        ).one()

        monthly_dispatch = session.exec(
            select(func.count(InventoryTransferItem.id))
            .join(InventoryTransfer, InventoryTransferItem.transfer_id == InventoryTransfer.id)
            .where(
                InventoryTransfer.created_at >= month_start_utc,
                InventoryTransfer.created_at <= now_utc,
            )
        ).one()

        return {
            "sent_today": int(sent_today or 0),
            "received_today": int(received_today or 0),
            "pending_receipts": int(pending_receipts or 0),
            "monthly_dispatch": int(monthly_dispatch or 0),
        }

    @staticmethod
    def fetch_battery_health_distribution(session: Session) -> list[dict[str, Any]]:
        if not AnalyticsDashboardRepository._table_exists(session, Battery.__tablename__):
            return [
                {"label": "Good", "value": 0, "color": "#4CAF50"},
                {"label": "Fair", "value": 0, "color": "#FF9800"},
                {"label": "Poor", "value": 0, "color": "#F44336"},
            ]

        good, fair, poor = session.exec(
            select(
                func.coalesce(func.sum(case((Battery.health_percentage >= 70, 1), else_=0)), 0),
                func.coalesce(
                    func.sum(case((and_(Battery.health_percentage >= 40, Battery.health_percentage < 70), 1), else_=0)),
                    0,
                ),
                func.coalesce(func.sum(case((Battery.health_percentage < 40, 1), else_=0)), 0),
            )
        ).one()
        return [
            {"label": "Good", "value": int(good or 0), "color": "#4CAF50"},
            {"label": "Fair", "value": int(fair or 0), "color": "#FF9800"},
            {"label": "Poor", "value": int(poor or 0), "color": "#F44336"},
        ]

    @staticmethod
    def fetch_battery_status_distribution(session: Session) -> list[dict[str, Any]]:
        if not AnalyticsDashboardRepository._table_exists(session, Battery.__tablename__):
            return [
                {"label": "Available", "value": 0, "color": "#4CAF50"},
                {"label": "Deployed", "value": 0, "color": "#2196F3"},
                {"label": "In Transit", "value": 0, "color": "#FF9800"},
                {"label": "Issue", "value": 0, "color": "#F44336"},
            ]

        available, deployed, in_transit, issues = session.exec(
            select(
                func.coalesce(func.sum(case((Battery.status.in_(["available", "ready", "new"]), 1), else_=0)), 0),
                func.coalesce(func.sum(case((Battery.status == "deployed", 1), else_=0)), 0),
                func.coalesce(func.sum(case((Battery.status.in_(["in_transit", "reserved"]), 1), else_=0)), 0),
                func.coalesce(func.sum(case((Battery.status.in_(["faulty", "maintenance"]), 1), else_=0)), 0),
            )
        ).one()
        return [
            {"label": "Available", "value": int(available or 0), "color": "#4CAF50"},
            {"label": "Deployed", "value": int(deployed or 0), "color": "#2196F3"},
            {"label": "In Transit", "value": int(in_transit or 0), "color": "#FF9800"},
            {"label": "Issue", "value": int(issues or 0), "color": "#F44336"},
        ]

    @staticmethod
    def fetch_cycle_count_distribution(session: Session) -> list[dict[str, Any]]:
        if not AnalyticsDashboardRepository._table_exists(session, Battery.__tablename__):
            return [
                {"category": "0-100", "value": 0},
                {"category": "101-300", "value": 0},
                {"category": "301+", "value": 0},
            ]

        low, mid, high = session.exec(
            select(
                func.coalesce(func.sum(case((Battery.cycle_count <= 100, 1), else_=0)), 0),
                func.coalesce(
                    func.sum(case((and_(Battery.cycle_count > 100, Battery.cycle_count <= 300), 1), else_=0)),
                    0,
                ),
                func.coalesce(func.sum(case((Battery.cycle_count > 300, 1), else_=0)), 0),
            )
        ).one()
        return [
            {"category": "0-100", "value": int(low or 0)},
            {"category": "101-300", "value": int(mid or 0)},
            {"category": "301+", "value": int(high or 0)},
        ]

    @staticmethod
    def fetch_orders_for_dispatch_trend(
        session: Session,
        *,
        trend_start_utc: datetime,
        trend_end_utc: datetime,
    ) -> list[Order]:
        if not AnalyticsDashboardRepository._table_exists(session, Order.__tablename__):
            return []
        stmt = select(Order).where(
            Order.dispatch_date.is_not(None),
            Order.dispatch_date >= trend_start_utc,
            Order.dispatch_date <= trend_end_utc,
        )
        return list(session.exec(stmt).all())

    @staticmethod
    def fetch_batteries_for_inventory_trend(
        session: Session,
        *,
        trend_start_utc: datetime,
        trend_end_utc: datetime,
    ) -> tuple[int, list[Battery]]:
        if not AnalyticsDashboardRepository._table_exists(session, Battery.__tablename__):
            return 0, []

        base_count = int(
            session.exec(select(func.count(Battery.id)).where(Battery.created_at < trend_start_utc)).one() or 0
        )
        rows = list(
            session.exec(
                select(Battery).where(
                    Battery.created_at >= trend_start_utc,
                    Battery.created_at <= trend_end_utc,
                )
            ).all()
        )
        return base_count, rows

    @staticmethod
    def fetch_station_dispatch_distribution(session: Session, *, top_n: int = 6) -> list[dict[str, Any]]:
        if not (
            AnalyticsDashboardRepository._table_exists(session, InventoryTransfer.__tablename__)
            and AnalyticsDashboardRepository._table_exists(session, InventoryTransferItem.__tablename__)
            and AnalyticsDashboardRepository._table_exists(session, Station.__tablename__)
        ):
            return []

        rows = session.exec(
            select(
                InventoryTransfer.to_location_id,
                Station.name,
                func.count(InventoryTransferItem.id).label("count_items"),
            )
            .join(InventoryTransferItem, InventoryTransferItem.transfer_id == InventoryTransfer.id)
            .outerjoin(
                Station,
                and_(
                    InventoryTransfer.to_location_type == "station",
                    Station.id == InventoryTransfer.to_location_id,
                ),
            )
            .where(InventoryTransfer.to_location_type == "station")
            .group_by(InventoryTransfer.to_location_id, Station.name)
            .order_by(func.count(InventoryTransferItem.id).desc())
            .limit(top_n)
        ).all()

        return [
            {
                "category": row[1] or f"Station #{row[0]}",
                "value": int(row[2] or 0),
            }
            for row in rows
        ]

    @staticmethod
    def fetch_orders_for_activity(
        session: Session,
        *,
        from_utc: Optional[datetime],
        to_utc: Optional[datetime],
        row_limit: Optional[int] = None,
    ) -> list[Order]:
        if not AnalyticsDashboardRepository._table_exists(session, Order.__tablename__):
            return []

        query = select(Order)
        if from_utc is not None or to_utc is not None:
            window_conditions: list[Any] = []
            for column in (Order.order_date, Order.dispatch_date, Order.delivered_at, Order.updated_at):
                clauses = [column.is_not(None)]
                if from_utc is not None:
                    clauses.append(column >= from_utc)
                if to_utc is not None:
                    clauses.append(column <= to_utc)
                window_conditions.append(and_(*clauses))
            query = query.where(or_(*window_conditions))
        query = query.order_by(Order.updated_at.desc(), Order.order_date.desc(), Order.id.desc())
        if row_limit is not None and row_limit > 0:
            query = query.limit(row_limit)
        return list(session.exec(query).all())

    @staticmethod
    def fetch_transfers_for_activity(
        session: Session,
        *,
        from_utc: Optional[datetime],
        to_utc: Optional[datetime],
        row_limit: Optional[int] = None,
    ) -> list[InventoryTransfer]:
        if not AnalyticsDashboardRepository._table_exists(session, InventoryTransfer.__tablename__):
            return []

        query = select(InventoryTransfer)
        if from_utc is not None:
            query = query.where(
                or_(
                    InventoryTransfer.created_at >= from_utc,
                    InventoryTransfer.updated_at >= from_utc,
                    InventoryTransfer.completed_at >= from_utc,
                )
            )
        if to_utc is not None:
            query = query.where(
                or_(
                    InventoryTransfer.created_at <= to_utc,
                    InventoryTransfer.updated_at <= to_utc,
                    InventoryTransfer.completed_at <= to_utc,
                )
            )
        query = query.order_by(
            InventoryTransfer.updated_at.desc(),
            InventoryTransfer.created_at.desc(),
            InventoryTransfer.id.desc(),
        )
        if row_limit is not None and row_limit > 0:
            query = query.limit(row_limit)
        return list(session.exec(query).all())

    @staticmethod
    def fetch_discrepancies_for_activity(
        session: Session,
        *,
        from_utc: Optional[datetime],
        to_utc: Optional[datetime],
        row_limit: Optional[int] = None,
    ) -> list[StockDiscrepancy]:
        if not AnalyticsDashboardRepository._table_exists(session, StockDiscrepancy.__tablename__):
            return []

        query = select(StockDiscrepancy)
        if from_utc is not None:
            query = query.where(StockDiscrepancy.created_at >= from_utc)
        if to_utc is not None:
            query = query.where(StockDiscrepancy.created_at <= to_utc)
        query = query.order_by(StockDiscrepancy.created_at.desc(), StockDiscrepancy.id.desc())
        if row_limit is not None and row_limit > 0:
            query = query.limit(row_limit)
        return list(session.exec(query).all())

    @staticmethod
    def fetch_battery_lifecycle_for_activity(
        session: Session,
        *,
        from_utc: Optional[datetime],
        to_utc: Optional[datetime],
        row_limit: Optional[int] = None,
    ) -> list[tuple[BatteryLifecycleEvent, Optional[Battery]]]:
        if not AnalyticsDashboardRepository._table_exists(session, BatteryLifecycleEvent.__tablename__):
            return []

        query = select(BatteryLifecycleEvent, Battery).outerjoin(Battery, Battery.id == BatteryLifecycleEvent.battery_id)
        if from_utc is not None:
            query = query.where(BatteryLifecycleEvent.timestamp >= from_utc)
        if to_utc is not None:
            query = query.where(BatteryLifecycleEvent.timestamp <= to_utc)
        query = query.order_by(BatteryLifecycleEvent.timestamp.desc(), BatteryLifecycleEvent.id.desc())
        if row_limit is not None and row_limit > 0:
            query = query.limit(row_limit)
        return list(session.exec(query).all())

    @staticmethod
    def fetch_activity_table_rows(
        session: Session,
        *,
        from_utc: Optional[datetime],
        to_utc: Optional[datetime],
        row_limit: Optional[int] = None,
    ) -> list[AnalyticsActivityEvent]:
        if not AnalyticsDashboardRepository._table_exists(session, AnalyticsActivityEvent.__tablename__):
            return []

        query = select(AnalyticsActivityEvent)
        if from_utc is not None:
            query = query.where(AnalyticsActivityEvent.event_timestamp >= from_utc)
        if to_utc is not None:
            query = query.where(AnalyticsActivityEvent.event_timestamp <= to_utc)
        query = query.order_by(AnalyticsActivityEvent.event_timestamp.desc(), AnalyticsActivityEvent.id.desc())
        if row_limit is not None and row_limit > 0:
            query = query.limit(row_limit)
        return list(session.exec(query).all())

    @staticmethod
    def fetch_low_inventory_counts(session: Session, *, threshold: int = 5) -> list[dict[str, Any]]:
        if not AnalyticsDashboardRepository._table_exists(session, Battery.__tablename__):
            return []
        rows = session.exec(
            select(
                Battery.location_type,
                Battery.location_id,
                func.count(Battery.id).label("available_count"),
            )
            .where(
                Battery.location_type.in_(["warehouse", "station"]),
                Battery.location_id.is_not(None),
                Battery.status.in_(["available", "ready", "new"]),
            )
            .group_by(Battery.location_type, Battery.location_id)
            .having(func.count(Battery.id) < threshold)
        ).all()

        return [
            {
                "location_type": row[0],
                "location_id": int(row[1]),
                "available_count": int(row[2] or 0),
                "threshold": threshold,
            }
            for row in rows
        ]

    @staticmethod
    def create_report_job(session: Session, report_job: AnalyticsReportJob) -> AnalyticsReportJob:
        session.add(report_job)
        session.commit()
        session.refresh(report_job)
        return report_job

    @staticmethod
    def get_report_job(session: Session, report_id: str) -> Optional[AnalyticsReportJob]:
        return session.get(AnalyticsReportJob, report_id)

    @staticmethod
    def update_report_job(
        session: Session,
        report_id: str,
        *,
        status: Optional[str] = None,
        file_path: Optional[str] = None,
        file_url: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        detail: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> Optional[AnalyticsReportJob]:
        job = session.get(AnalyticsReportJob, report_id)
        if job is None:
            return None
        if status is not None:
            job.status = status
        if file_path is not None:
            job.file_path = file_path
        if file_url is not None:
            job.file_url = file_url
        if expires_at is not None:
            job.expires_at = expires_at
        if detail is not None:
            job.detail = detail
        if started_at is not None:
            job.started_at = started_at
        if completed_at is not None:
            job.completed_at = completed_at
        job.updated_at = datetime.utcnow()
        session.add(job)
        session.commit()
        session.refresh(job)
        return job

    @staticmethod
    def active_report_rows(session: Session, *, from_utc: datetime, to_utc: datetime) -> Iterable[AnalyticsReportJob]:
        if not AnalyticsDashboardRepository._table_exists(session, AnalyticsReportJob.__tablename__):
            return []
        return list(
            session.exec(
                select(AnalyticsReportJob).where(
                    AnalyticsReportJob.created_at >= from_utc,
                    AnalyticsReportJob.created_at <= to_utc,
                )
            ).all()
        )
