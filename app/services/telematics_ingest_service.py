from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session

from app.models.battery import Battery, BatteryLifecycleEvent
from app.models.battery_health_log import BatteryHealthLog
from app.models.telematics import TelemeticsData
from app.schemas.telematics import TelemeticsDataIngest, TelemeticsDataResponse
from app.services.telematics_service import TelematicsService

logger = logging.getLogger(__name__)


class TelematicsIngestService:
    """Canonical persistence path for telemetry ingestion."""

    @staticmethod
    def persist_telemetry(
        session: Session,
        *,
        data_in: TelemeticsDataIngest,
        create_alert_events: bool = True,
        commit: bool = True,
    ) -> TelemeticsData:
        battery = session.get(Battery, data_in.battery_id)
        if not battery:
            raise HTTPException(status_code=404, detail="Battery not found")

        if not data_in.timestamp:
            data_in.timestamp = datetime.utcnow()

        telemetry_entry = TelemeticsData.model_validate(data_in)
        session.add(telemetry_entry)

        health_log = BatteryHealthLog(
            battery_id=battery.id,
            charge_percentage=data_in.soc,
            voltage=data_in.voltage,
            current=data_in.current,
            temperature=data_in.temperature,
            cycle_count=0,
            health_percentage=data_in.soh,
            latitude=data_in.gps_latitude,
            longitude=data_in.gps_longitude,
            timestamp=data_in.timestamp,
        )
        session.add(health_log)

        TelematicsService.apply_battery_snapshot(
            battery,
            soc=data_in.soc,
            soh=data_in.soh,
        )
        session.add(battery)

        if create_alert_events:
            TelematicsIngestService.create_alert_events(
                session,
                battery_id=battery.id,
                data_in=data_in,
            )

        if commit:
            session.commit()
            session.refresh(telemetry_entry)
        else:
            session.flush()

        return telemetry_entry

    @staticmethod
    def create_alert_events(
        session: Session,
        *,
        battery_id: int,
        data_in: TelemeticsDataIngest,
    ) -> None:
        alerts: list[BatteryLifecycleEvent] = []
        if data_in.temperature > 45.0:
            alerts.append(
                BatteryLifecycleEvent(
                    battery_id=battery_id,
                    event_type="alert_overheating",
                    description=f"Critical temperature detected: {data_in.temperature}C",
                )
            )
        if data_in.soc < 10.0:
            alerts.append(
                BatteryLifecycleEvent(
                    battery_id=battery_id,
                    event_type="alert_low_battery",
                    description=f"Critically low charge: {data_in.soc}%",
                )
            )

        if not alerts:
            return

        for event in alerts:
            session.add(event)

    @staticmethod
    def response_from_ingest(data_in: TelemeticsDataIngest) -> TelemeticsDataResponse:
        timestamp = data_in.timestamp or datetime.utcnow()
        return TelemeticsDataResponse(
            battery_id=data_in.battery_id,
            timestamp=timestamp,
            received_at=datetime.utcnow(),
            voltage=data_in.voltage,
            current=data_in.current,
            temperature=data_in.temperature,
            soc=data_in.soc,
            soh=data_in.soh,
            gps_latitude=data_in.gps_latitude,
            gps_longitude=data_in.gps_longitude,
            gps_altitude=data_in.gps_altitude,
            gps_speed=data_in.gps_speed,
            error_codes=data_in.error_codes,
            raw_payload=data_in.raw_payload,
        )

    @staticmethod
    def ingest_payload_from_dict(payload: dict[str, Any]) -> TelemeticsDataIngest:
        return TelemeticsDataIngest.model_validate(payload)
