import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

import csv
import io
from sqlmodel import Session, select, func, col, desc

from app.models.rental import Rental
from app.models.commission import CommissionLog
from app.models.station import Station
from app.models.user import User
from app.models.financial import Transaction
from app.schemas.dealer_ledger import LedgerEntry, LedgerResponse, LedgerDetailResponse

logger = logging.getLogger(__name__)

class DealerLedgerService:
    @staticmethod
    def get_ledger_entries(
        db: Session,
        dealer_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        txn_types: Optional[List[str]] = None,
        station_id: Optional[int] = None,
        search: Optional[str] = None,
        amount_min: Optional[float] = None,
        amount_max: Optional[float] = None,
        status_types: Optional[List[str]] = None,
        limit: int = 50,
        skip: int = 0
    ) -> LedgerResponse:
        # Get all stations for this dealer
        station_query = select(Station.id).where(Station.dealer_id == dealer_id)
        if station_id:
            station_query = station_query.where(Station.id == station_id)
        station_ids = db.exec(station_query).all()

        if not station_ids:
            return LedgerResponse(data=[], total=0, total_amount=0.0)

        # In a production app with millions of rows, we would use a SQLAlchemy UNION over indexed queries.
        # For simplicity in this implementation, we query Rentals and Commissions concurrently and merge.
        entries = []
        
        # 1. Fetch Rentals (Rental Income, Penalties) map to Dealer Stations
        if not txn_types or "Rental Income" in txn_types or "Penalty" in txn_types:
            r_query = select(Rental).where(col(Rental.start_station_id).in_(station_ids))
            if start_date:
                r_query = r_query.where(Rental.created_at >= start_date)
            if end_date:
                r_query = r_query.where(Rental.created_at <= end_date)
            if amount_min is not None:
                r_query = r_query.where(Rental.total_amount >= amount_min)
            if amount_max is not None:
                r_query = r_query.where(Rental.total_amount <= amount_max)
            if status_types:
                # Map standard statuses to Rental status
                rental_statuses = []
                for s in status_types:
                    if s == 'completed': rental_statuses.append("completed")
                    if s == 'pending': rental_statuses.append("active")
                    # Failed/refunded handling could be added here
                if rental_statuses:
                    r_query = r_query.where(col(Rental.status).in_(rental_statuses))
            
            if search:
                # Search by TXN-R{id} or user info (simplified for now to rental/battery ID)
                search_term = search.lower().replace('txn-r', '').replace('bat-', '')
                try:
                    search_id = int(search_term)
                    r_query = r_query.where((Rental.id == search_id) | (Rental.battery_id == search_id))
                except ValueError:
                    # If it's a string, we would need to join User table to search names.
                    r_query = r_query.join(User).where(col(User.full_name).ilike(f"%{search}%"))
                
            rentals = db.exec(r_query.order_by(desc(Rental.created_at)).offset(skip).limit(limit)).all()
            
            for r in rentals:
                # Pre-fetch relations if needed, but assuming lazy load or standard queries
                user = db.get(User, r.user_id)
                station = db.get(Station, r.start_station_id)
                
                # Format duration
                duration_str = None
                if r.end_time and r.start_time:
                    diff = r.end_time - r.start_time
                    hours = int(diff.total_seconds() // 3600)
                    mins = int((diff.total_seconds() % 3600) // 60)
                    duration_str = f"{hours}h {mins}m"
                
                status_mapped = "Completed" if r.status.value == "completed" else r.status.value.capitalize()
                
                if not txn_types or "Rental Income" in txn_types:
                    entries.append(LedgerEntry(
                        id=f"RENTAL-{r.id}",
                        transaction_id=f"TXN-R{r.id}",
                        date=r.created_at,
                        customer_name=user.full_name if user else "Unknown",
                        customer_phone=user.phone_number if user else None,
                        station_name=station.name if station else "Unknown",
                        battery_id=f"BAT-{r.battery_id}",
                        type="Rental Income",
                        duration=duration_str,
                        amount=r.total_amount,
                        status=status_mapped
                    ))

        # 2. Fetch Commissions
        if not txn_types or "Commission" in txn_types:
            c_query = select(CommissionLog).where(CommissionLog.dealer_id == dealer_id)
            if start_date:
                c_query = c_query.where(CommissionLog.created_at >= start_date)
            if end_date:
                c_query = c_query.where(CommissionLog.created_at <= end_date)
            if amount_min is not None:
                c_query = c_query.where(CommissionLog.amount >= amount_min)
            if amount_max is not None:
                c_query = c_query.where(CommissionLog.amount <= amount_max)
            if status_types:
                comm_statuses = []
                for s in status_types:
                    if s == 'completed': comm_statuses.append('paid')
                    if s == 'pending': comm_statuses.append('pending')
                if comm_statuses:
                    c_query = c_query.where(col(CommissionLog.status).in_(comm_statuses))
                    
            if search:
                search_term = search.lower().replace('txn-c', '')
                try:
                    search_id = int(search_term)
                    c_query = c_query.where(CommissionLog.id == search_id)
                except ValueError:
                    pass # Custom text search on commissions lacks obvious string fields, omit for now
                
            commissions = db.exec(c_query.order_by(desc(CommissionLog.created_at)).offset(skip).limit(limit)).all()
            
            for c in commissions:
                status_mapped = "Completed" if c.status == "paid" else "Pending"
                entries.append(LedgerEntry(
                    id=f"COMM-{c.id}",
                    transaction_id=f"TXN-C{c.id}",
                    date=c.created_at,
                    type="Commission",
                    amount=c.amount,
                    status=status_mapped
                ))

        # Sort combined entries by date desc
        entries.sort(key=lambda x: x.date, reverse=True)
        
        # Paginate manual merged list
        paginated_entries = entries[0:limit] # Since we already limit, we just ensure it doesn't exceed total limits
        total_count = len(entries) # Approximation for this example
        total_amount = sum(e.amount for e in paginated_entries)

        return LedgerResponse(data=paginated_entries, total=total_count, total_amount=total_amount)

    @staticmethod
    def generate_ledger_csv(
        db: Session,
        dealer_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        txn_types: Optional[List[str]] = None,
        station_id: Optional[int] = None,
        search: Optional[str] = None,
        amount_min: Optional[float] = None,
        amount_max: Optional[float] = None,
        status_types: Optional[List[str]] = None,
    ) -> str:
        # Re-use the query mechanism, but fetch universally
        ledger = DealerLedgerService.get_ledger_entries(
            db, dealer_id, start_date, end_date, txn_types, station_id, 
            search, amount_min, amount_max, status_types, limit=10000, skip=0
        )
        
        output = io.StringIO()
        writer = csv.writer(output)
        # Headers matching UI Column needs
        writer.writerow(["Date & Time", "TXN ID", "Type", "Reference ID", "Station", "Amount", "Status"])
        
        for e in ledger.data:
            writer.writerow([
                e.date.strftime("%Y-%m-%d %H:%M:%S"),
                e.transaction_id,
                e.type,
                e.battery_id or "-",
                e.station_name or "-",
                f"{e.amount:.2f}",
                e.status
            ])
            
        return output.getvalue()

    @staticmethod
    def get_ledger_detail(db: Session, dealer_id: int, entry_id: str) -> LedgerDetailResponse:
        try:
            prefix, db_id_str = entry_id.split("-", 1)
            db_id = int(db_id_str)
        except (ValueError, AttributeError):
            # Non-disclosive: malformed IDs look identical to not-found.
            raise ValueError("Not found")

        # Strict tenant isolation: reject any ledger entry that does not
        # belong to a station owned by the caller dealer. Fails closed with
        # the same error as "not found" so callers cannot probe for IDs.
        dealer_station_ids = set(
            db.exec(select(Station.id).where(Station.dealer_id == dealer_id)).all()
        )

        if prefix == "RENTAL":
            r = db.get(Rental, db_id)
            if not r:
                raise ValueError("Not found")
            if not dealer_station_ids or r.start_station_id not in dealer_station_ids:
                logger.warning(
                    "security.scope_violation",
                    extra={
                        "dealer_id": dealer_id,
                        "target_id": entry_id,
                        "endpoint": "GET /dealers/me/transactions/{txn_id}",
                        "reason": "rental_not_in_dealer_scope",
                    },
                )
                raise ValueError("Not found")

            user = db.get(User, r.user_id)
            station = db.get(Station, r.start_station_id)
            
            duration_str = None
            if r.end_time and r.start_time:
                diff = r.end_time - r.start_time
                hours = int(diff.total_seconds() // 3600)
                mins = int((diff.total_seconds() % 3600) // 60)
                duration_str = f"{hours}h {mins}m"
                
            # Timeline events
            events = [
                {"name": "Rental Started", "status": "completed", "date": r.start_time},
                {"name": "Payment Captured", "status": "completed" if r.status == "completed" else "pending", "date": r.end_time or r.created_at},
                {"name": "Settlement Queued", "status": "pending", "date": datetime.utcnow()} # Mock
            ]
            
            # Fetch real transaction for payment ref
            pay_ref = None
            pay_method = None
            txn = db.exec(select(Transaction).where(Transaction.rental_id == r.id)).first()
            if txn:
                pay_ref = txn.payment_gateway_ref
                pay_method = txn.payment_method
                
            return LedgerDetailResponse(
                id=entry_id,
                transaction_id=f"TXN-R{r.id}",
                date=r.created_at,
                customer_name=user.full_name if user else "Unknown",
                customer_phone=user.phone_number if user else None,
                battery_id=f"BAT-{r.battery_id}",
                station_name=station.name if station else "Unknown",
                terminal_number="Slot 1", # Mock
                rental_start_time=r.start_time,
                rental_end_time=r.end_time,
                duration=duration_str,
                gross_amount=r.total_amount,
                platform_fee=r.total_amount * 0.1, # Mock platform fee
                commission_rate=0.0,
                commission_amount=0.0,
                net_amount=r.total_amount * 0.9,
                payment_method=pay_method,
                payment_gateway_ref=pay_ref,
                settlement_status="Pending",
                expected_settlement_date=datetime.utcnow() + timedelta(days=2),
                type="Rental Income",
                status="Completed" if r.status == "completed" else r.status.name,
                events=events
            )
        elif prefix == "COMM":
            from app.models.commission import CommissionLog

            entry = db.get(CommissionLog, db_id)
            if not entry:
                raise ValueError("Not found")
            # CommissionLog.dealer_id references users.id (dealer owner user id).
            # Map to dealer profile and enforce ownership.
            from app.models.dealer import DealerProfile
            profile = db.get(DealerProfile, dealer_id)
            owner_user_id = profile.user_id if profile else None
            if entry.dealer_id != owner_user_id:
                logger.warning(
                    "security.scope_violation",
                    extra={
                        "dealer_id": dealer_id,
                        "target_id": entry_id,
                        "endpoint": "GET /dealers/me/transactions/{txn_id}",
                        "reason": "commission_not_in_dealer_scope",
                    },
                )
                raise ValueError("Not found")
            raise ValueError("Unsupported detail view for this type")
        else:
            raise ValueError("Not found")
