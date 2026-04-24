from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.api import deps
from app.db.session import get_session
from app.schemas.telematics import TelemeticsDataIngest
from app.services.telematics_ingest_service import TelematicsIngestService

router = APIRouter()


class InternalTelemetryIngestResponse(BaseModel):
    status: str
    battery_id: int
    timestamp: datetime


@router.post("/telematics/ingest", response_model=InternalTelemetryIngestResponse)
def ingest_telematics_internal(
    *,
    session: Session = Depends(get_session),
    data_in: TelemeticsDataIngest,
    _: bool = Depends(deps.require_internal_service_token),
) -> InternalTelemetryIngestResponse:
    entry = TelematicsIngestService.persist_telemetry(session, data_in=data_in)
    return InternalTelemetryIngestResponse(
        status="ok",
        battery_id=entry.battery_id,
        timestamp=entry.timestamp,
    )
