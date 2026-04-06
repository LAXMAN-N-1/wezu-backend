"""
Enhanced Analytics Endpoints
Carbon savings and export utilities backed by current rental/transaction schema.
"""
from datetime import datetime
import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from app.api import deps
from app.db.session import get_session
from app.models.financial import Transaction, Wallet
from app.models.rental import Rental
from app.models.user import User

router = APIRouter()


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
    format: str = "json",
):
    """Export user rentals and wallet transactions in JSON/CSV placeholder format."""
    fmt = (format or "json").lower()
    if fmt not in {"json", "csv"}:
        raise HTTPException(status_code=400, detail="format must be either 'json' or 'csv'")

    rentals = db.exec(select(Rental).where(Rental.user_id == current_user.id)).all()

    transactions = db.exec(
        select(Transaction)
        .join(Wallet, Wallet.id == Transaction.wallet_id)
        .where(Wallet.user_id == current_user.id)
        .order_by(Transaction.created_at.desc())
    ).all()

    total_spent = sum(abs(t.amount) for t in transactions if t.type == "debit")
    total_received = sum(t.amount for t in transactions if t.type == "credit")

    data = {
        "user_id": current_user.id,
        "export_date": datetime.utcnow().isoformat(),
        "rentals": [
            {
                "id": r.id,
                "battery_id": r.battery_id,
                "start_time": r.start_time.isoformat() if r.start_time else None,
                "end_time": r.end_time.isoformat() if r.end_time else None,
                "total_price": float(r.total_price),
                "late_fee_amount": float(r.late_fee_amount),
                "status": r.status,
            }
            for r in rentals
        ],
        "transactions": [
            {
                "id": t.id,
                "amount": t.amount,
                "type": t.type,
                "category": t.category,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "description": t.description,
                "reference_type": t.reference_type,
                "reference_id": t.reference_id,
            }
            for t in transactions
        ],
        "summary": {
            "total_rentals": len(rentals),
            "total_spent": round(total_spent, 2),
            "total_received": round(total_received, 2),
            "net_change": round(total_received - total_spent, 2),
        },
    }

    if fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["section", "id", "type", "status", "amount", "start_time", "end_time", "created_at", "description"])
        for row in data["rentals"]:
            writer.writerow(
                [
                    "rental",
                    row["id"],
                    "rental",
                    row["status"],
                    row["total_price"],
                    row["start_time"],
                    row["end_time"],
                    "",
                    f"battery_id={row['battery_id']}",
                ]
            )
        for row in data["transactions"]:
            writer.writerow(
                [
                    "transaction",
                    row["id"],
                    row["type"],
                    row["status"],
                    row["amount"],
                    "",
                    "",
                    row["created_at"],
                    row.get("description"),
                ]
            )

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=analytics_{current_user.id}.csv"},
        )

    return data
