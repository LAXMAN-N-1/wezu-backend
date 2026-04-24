"""
Enhanced Analytics Endpoints
Carbon savings and export utilities backed by rental + transaction data.
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date, datetime, time, timezone; UTC = timezone.utc
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from app.api import deps
from app.db.session import get_session
from app.models.financial import Transaction
from app.models.rental import Rental
from app.models.user import User

router = APIRouter()


def _parse_iso_datetime(value: str | None, *, field_name: str, end_of_day: bool = False) -> datetime | None:
    if value is None:
        return None

    raw = value.strip()
    if not raw:
        return None

    try:
        if "T" not in raw and len(raw) == 10:
            parsed_date = date.fromisoformat(raw)
            parsed_time = time.max if end_of_day else time.min
            return datetime.combine(parsed_date, parsed_time, tzinfo=UTC)

        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name}. Use ISO-8601 date or datetime.",
        ) from exc


def _enum_value(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _month_key(ts: datetime | None) -> str:
    if ts is None:
        return "unknown"
    normalized = ts if ts.tzinfo else ts.replace(tzinfo=UTC)
    return normalized.strftime("%Y-%m")


@router.get("/carbon-savings")
def get_carbon_savings(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
):
    """Calculate estimated carbon savings from completed battery rentals."""
    rentals = db.exec(
        select(Rental).where(
            Rental.user_id == current_user.id,
            Rental.status == "completed",
        )
    ).all()

    total_hours = 0.0
    for rental in rentals:
        if rental.end_time and rental.start_time:
            duration = (rental.end_time - rental.start_time).total_seconds() / 3600
            if duration > 0:
                total_hours += duration

    carbon_saved_kg = total_hours * 0.5
    trees_equivalent = carbon_saved_kg / 21 if carbon_saved_kg > 0 else 0.0

    return {
        "total_rentals": len(rentals),
        "total_hours": round(total_hours, 2),
        "carbon_saved_kg": round(carbon_saved_kg, 2),
        "trees_equivalent": round(trees_equivalent, 2),
        "comparison": {
            "car_km_saved": round(carbon_saved_kg * 5, 2),
            "plastic_bottles_saved": round(carbon_saved_kg * 50, 0),
        },
    }


@router.get("/export")
def export_analytics_data(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
    format: str = Query("json", pattern="^(json|csv)$"),
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
):
    """Export user rentals and transactions in JSON/CSV with date filters and KPI summary."""
    fmt = (format or "json").lower()

    start_at = _parse_iso_datetime(from_date, field_name="from_date")
    end_at = _parse_iso_datetime(to_date, field_name="to_date", end_of_day=True)
    if start_at and end_at and start_at > end_at:
        raise HTTPException(status_code=400, detail="from_date must be earlier than to_date")

    rental_query = select(Rental).where(Rental.user_id == current_user.id)
    if start_at is not None:
        rental_query = rental_query.where(Rental.start_time >= start_at)
    if end_at is not None:
        rental_query = rental_query.where(Rental.start_time <= end_at)
    rental_query = rental_query.order_by(Rental.start_time.desc())
    rentals = db.exec(rental_query).all()

    txn_query = select(Transaction).where(Transaction.user_id == current_user.id)
    if start_at is not None:
        txn_query = txn_query.where(Transaction.created_at >= start_at)
    if end_at is not None:
        txn_query = txn_query.where(Transaction.created_at <= end_at)
    txn_query = txn_query.order_by(Transaction.created_at.desc())
    transactions = db.exec(txn_query).all()

    total_rental_amount = 0.0
    total_late_fees = 0.0
    total_distance_km = 0.0
    completed_rentals = 0
    active_rentals = 0
    total_duration_minutes = 0.0
    rental_duration_count = 0

    monthly_rental_breakdown: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {
            "rentals": 0,
            "revenue": 0.0,
            "distance_km": 0.0,
        }
    )

    serialized_rentals: list[dict[str, Any]] = []
    for rental in rentals:
        status = _enum_value(rental.status)
        start_time = rental.start_time
        end_time = rental.end_time

        total_rental_amount += float(rental.total_amount or 0.0)
        total_late_fees += float(rental.late_fee or 0.0)
        total_distance_km += float(rental.distance_traveled_km or 0.0)

        if status == "completed":
            completed_rentals += 1
        if status == "active":
            active_rentals += 1

        duration_minutes = None
        if start_time and end_time and end_time > start_time:
            duration_minutes = round((end_time - start_time).total_seconds() / 60, 2)
            total_duration_minutes += duration_minutes
            rental_duration_count += 1

        month_key = _month_key(start_time)
        monthly_rental_breakdown[month_key]["rentals"] += 1
        monthly_rental_breakdown[month_key]["revenue"] += float(rental.total_amount or 0.0)
        monthly_rental_breakdown[month_key]["distance_km"] += float(rental.distance_traveled_km or 0.0)

        serialized_rentals.append(
            {
                "id": rental.id,
                "battery_id": rental.battery_id,
                "start_station_id": rental.start_station_id,
                "end_station_id": rental.end_station_id,
                "start_time": start_time.isoformat() if start_time else None,
                "end_time": end_time.isoformat() if end_time else None,
                "duration_minutes": duration_minutes,
                "total_amount": round(float(rental.total_amount or 0.0), 2),
                "late_fee": round(float(rental.late_fee or 0.0), 2),
                "distance_traveled_km": round(float(rental.distance_traveled_km or 0.0), 2),
                "status": status,
            }
        )

    total_transaction_amount = 0.0
    successful_transaction_amount = 0.0
    failed_transactions = 0

    by_transaction_type: dict[str, float] = defaultdict(float)
    by_payment_method: dict[str, float] = defaultdict(float)
    monthly_transaction_breakdown: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {
            "transactions": 0,
            "amount": 0.0,
            "successful_amount": 0.0,
        }
    )

    serialized_transactions: list[dict[str, Any]] = []
    for txn in transactions:
        status = _enum_value(txn.status)
        txn_type = _enum_value(txn.transaction_type)
        payment_method = (txn.payment_method or "").strip().lower() or "unknown"
        amount_value = float(txn.amount or 0.0)

        total_transaction_amount += amount_value
        by_transaction_type[txn_type] += amount_value
        by_payment_method[payment_method] += amount_value

        month_key = _month_key(txn.created_at)
        monthly_transaction_breakdown[month_key]["transactions"] += 1
        monthly_transaction_breakdown[month_key]["amount"] += amount_value

        if status == "success":
            successful_transaction_amount += amount_value
            monthly_transaction_breakdown[month_key]["successful_amount"] += amount_value
        elif status in {"failed", "cancelled"}:
            failed_transactions += 1

        serialized_transactions.append(
            {
                "id": txn.id,
                "rental_id": txn.rental_id,
                "wallet_id": txn.wallet_id,
                "amount": round(amount_value, 2),
                "currency": txn.currency,
                "transaction_type": txn_type,
                "status": status,
                "payment_method": payment_method,
                "payment_gateway_ref": txn.payment_gateway_ref,
                "created_at": txn.created_at.isoformat() if txn.created_at else None,
                "description": txn.description,
            }
        )

    avg_rental_duration_minutes = (
        round(total_duration_minutes / rental_duration_count, 2) if rental_duration_count > 0 else 0.0
    )

    summary = {
        "window": {
            "from": start_at.isoformat() if start_at else None,
            "to": end_at.isoformat() if end_at else None,
            "generated_at": datetime.now(UTC).isoformat(),
        },
        "rentals": {
            "total_count": len(rentals),
            "completed_count": completed_rentals,
            "active_count": active_rentals,
            "total_amount": round(total_rental_amount, 2),
            "total_late_fees": round(total_late_fees, 2),
            "total_distance_km": round(total_distance_km, 2),
            "avg_duration_minutes": avg_rental_duration_minutes,
        },
        "transactions": {
            "total_count": len(transactions),
            "failed_count": failed_transactions,
            "total_amount": round(total_transaction_amount, 2),
            "successful_amount": round(successful_transaction_amount, 2),
            "by_type": {key: round(value, 2) for key, value in sorted(by_transaction_type.items())},
            "by_payment_method": {key: round(value, 2) for key, value in sorted(by_payment_method.items())},
        },
        "monthly_breakdown": {
            "rentals": {
                key: {
                    "rentals": int(value["rentals"]),
                    "revenue": round(float(value["revenue"]), 2),
                    "distance_km": round(float(value["distance_km"]), 2),
                }
                for key, value in sorted(monthly_rental_breakdown.items())
            },
            "transactions": {
                key: {
                    "transactions": int(value["transactions"]),
                    "amount": round(float(value["amount"]), 2),
                    "successful_amount": round(float(value["successful_amount"]), 2),
                }
                for key, value in sorted(monthly_transaction_breakdown.items())
            },
        },
    }

    payload = {
        "user_id": current_user.id,
        "summary": summary,
        "rentals": serialized_rentals,
        "transactions": serialized_transactions,
    }

    if fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "section",
                "id",
                "status",
                "amount",
                "currency",
                "transaction_type",
                "payment_method",
                "start_time",
                "end_time",
                "created_at",
                "details",
            ]
        )

        for row in serialized_rentals:
            writer.writerow(
                [
                    "rental",
                    row["id"],
                    row["status"],
                    row["total_amount"],
                    "INR",
                    "rental",
                    "",
                    row["start_time"],
                    row["end_time"],
                    "",
                    (
                        f"battery_id={row['battery_id']};start_station={row['start_station_id']};"
                        f"end_station={row['end_station_id']};distance_km={row['distance_traveled_km']};"
                        f"late_fee={row['late_fee']}"
                    ),
                ]
            )

        for row in serialized_transactions:
            writer.writerow(
                [
                    "transaction",
                    row["id"],
                    row["status"],
                    row["amount"],
                    row["currency"],
                    row["transaction_type"],
                    row["payment_method"],
                    "",
                    "",
                    row["created_at"],
                    row.get("description") or "",
                ]
            )

        writer.writerow([
            "summary",
            "totals",
            "",
            summary["rentals"]["total_amount"],
            "INR",
            "rental_totals",
            "",
            "",
            "",
            summary["window"]["generated_at"],
            (
                f"rentals={summary['rentals']['total_count']};completed={summary['rentals']['completed_count']};"
                f"distance_km={summary['rentals']['total_distance_km']};avg_duration_min={summary['rentals']['avg_duration_minutes']}"
            ),
        ])
        writer.writerow([
            "summary",
            "transactions",
            "",
            summary["transactions"]["total_amount"],
            "INR",
            "transaction_totals",
            "",
            "",
            "",
            summary["window"]["generated_at"],
            (
                f"transactions={summary['transactions']['total_count']};failed={summary['transactions']['failed_count']};"
                f"successful_amount={summary['transactions']['successful_amount']}"
            ),
        ])

        output.seek(0)
        filename_window = summary["window"]["from"] or "all"
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=analytics_{current_user.id}_{filename_window}.csv"},
        )

    return payload
