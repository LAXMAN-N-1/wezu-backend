from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import ceil
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.config import settings
from app.models.battery import Battery
from app.models.battery_catalog import BatteryCatalog
from app.models.late_fee import LateFee, LateFeeWaiver
from app.models.payment import PaymentTransaction
from app.models.promo_code import PromoCode
from app.models.rental import Rental
from app.models.rental_event import RentalEvent
from app.models.rental_modification import RentalExtension, RentalPause
from app.schemas.rental import RentalCreate
from app.services.battery_consistency import apply_battery_transition
from app.services.payment_service import PaymentService
from app.core.logging import get_logger

logger = get_logger("wezu_rentals")


class RentalService:
    @staticmethod
    def _safe_commit(db: Session, *, context: str = "rental_service") -> None:
        """Commit with rollback-on-failure and structured logging."""
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("db.commit_failed", context=context)
            raise

    @staticmethod
    def _to_money(value: Decimal | float | int | str) -> Decimal:
        try:
            return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid monetary amount") from exc

    @staticmethod
    def cleanup_stale_pending_rentals(db: Session, *, user_id: Optional[int] = None) -> int:
        timeout_minutes = max(1, int(getattr(settings, "RENTAL_PAYMENT_PENDING_TIMEOUT_MINUTES", 30)))
        cutoff = datetime.utcnow() - timedelta(minutes=timeout_minutes)

        statement = (
            select(Rental)
            .where(Rental.status == "pending_payment")
            .where(Rental.start_time < cutoff)
            .with_for_update()
        )
        if user_id is not None:
            statement = statement.where(Rental.user_id == user_id)

        stale_rentals = db.exec(statement).all()
        if not stale_rentals:
            return 0

        for rental in stale_rentals:
            rental.status = "cancelled"
            rental.end_time = datetime.utcnow()
            db.add(rental)
            db.add(
                RentalEvent(
                    rental_id=rental.id,
                    event_type="payment_timeout_cancelled",
                    station_id=rental.start_station_id,
                    battery_id=rental.battery_id,
                    description="Pending payment timed out; rental cancelled and battery released",
                )
            )

            battery = db.exec(
                select(Battery).where(Battery.id == rental.battery_id).with_for_update()
            ).first()
            if battery and battery.status == "reserved":
                apply_battery_transition(
                    db,
                    battery=battery,
                    to_status="available",
                    to_location_type="station",
                    to_location_id=rental.start_station_id,
                    event_type="rental_reservation_timeout_release",
                    event_description=f"Released reservation for expired rental #{rental.id}",
                    actor_id=rental.user_id,
                )

        RentalService._safe_commit(db, context="cleanup_stale_pending_rentals")
        return len(stale_rentals)

    @staticmethod
    def calculate_price(db: Session, battery_id: int, duration_days: int, promo_code: Optional[str] = None):
        if duration_days <= 0:
            raise HTTPException(status_code=400, detail="duration_days must be greater than 0")

        battery = db.exec(select(Battery).where(Battery.id == battery_id).with_for_update()).first()
        if not battery:
            raise HTTPException(status_code=404, detail="Battery not found")

        # Pricing comes from the BatteryCatalog (SKU) linked to the battery
        catalog = db.get(BatteryCatalog, battery.sku_id) if battery.sku_id else None
        daily_rate = Decimal(str(catalog.price_per_day)) if catalog and catalog.price_per_day else Decimal("0")
        deposit = Decimal(str(battery.purchase_cost)) * Decimal("0.10") if battery.purchase_cost else Decimal("0")
        total_rent = daily_rate * duration_days
        discount = Decimal("0")
        promo_id = None

        if promo_code:
            normalized_code = promo_code.strip().upper()
            if not normalized_code:
                raise HTTPException(status_code=400, detail="promo_code cannot be empty")

            promo = db.exec(
                select(PromoCode).where(func.upper(PromoCode.code) == normalized_code).with_for_update()
            ).first()
            if not promo:
                raise HTTPException(status_code=400, detail="Invalid promo code")

            now = datetime.utcnow()
            if not promo.is_active:
                raise HTTPException(status_code=400, detail="Promo code is inactive")
            if promo.valid_from and promo.valid_from > now:
                raise HTTPException(status_code=400, detail="Promo code is not yet active")
            if promo.valid_until and promo.valid_until < now:
                raise HTTPException(status_code=400, detail="Promo code has expired")
            if promo.usage_limit > 0 and promo.usage_count >= promo.usage_limit:
                raise HTTPException(status_code=400, detail="Promo code usage limit reached")
            if duration_days < max(0, promo.min_rental_days):
                raise HTTPException(
                    status_code=400,
                    detail=f"Promo code requires a minimum rental of {promo.min_rental_days} day(s)",
                )
            if total_rent < (promo.min_order_amount or Decimal("0")):
                raise HTTPException(
                    status_code=400,
                    detail=f"Promo code requires a minimum order amount of {promo.min_order_amount}",
                )

            if promo.discount_amount and promo.discount_amount > 0:
                discount += promo.discount_amount
            if promo.discount_percentage and promo.discount_percentage > 0:
                discount += (total_rent * promo.discount_percentage) / Decimal("100")
            if promo.max_discount_amount is not None and discount > promo.max_discount_amount:
                discount = promo.max_discount_amount
            if discount > total_rent:
                discount = total_rent
            promo_id = promo.id

        return {
            "daily_rate": daily_rate,
            "duration_days": duration_days,
            "rental_cost": total_rent,
            "discount": discount,
            "deposit": deposit,
            "total_payable": total_rent - discount + deposit,
            "promo_code_id": promo_id,
        }

    @staticmethod
    def initiate_rental(db: Session, user_id: int, rental_in: RentalCreate) -> Rental:
        RentalService.cleanup_stale_pending_rentals(db, user_id=user_id)

        max_active = max(1, int(getattr(settings, "MAX_ACTIVE_RENTALS_PER_USER", 1)))
        current_active = db.exec(
            select(func.count()).select_from(Rental).where(
                Rental.user_id == user_id,
                Rental.status.in_(["active", "pending_payment"]),
            )
        ).one()
        if current_active >= max_active:
            raise HTTPException(
                status_code=409,
                detail=f"Maximum active rentals reached ({max_active})",
            )

        battery = db.exec(select(Battery).where(Battery.id == rental_in.battery_id).with_for_update()).first()
        if not battery:
            raise HTTPException(status_code=404, detail="Battery not found")
        if battery.status not in ["ready", "available"]:
            raise HTTPException(
                status_code=400,
                detail=f"Battery is not available for rental (current status: {battery.status})",
            )
        if battery.location_type != "station" or battery.location_id != rental_in.start_station_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Battery is not available at pickup station {rental_in.start_station_id}. "
                    f"Current location: {battery.location_type} #{battery.location_id}"
                ),
            )

        min_soc = max(0, int(getattr(settings, "MIN_BATTERY_SOC_FOR_RENTAL", 20)))
        current_soc = int(battery.current_charge or 0)
        if current_soc < min_soc:
            raise HTTPException(
                status_code=400,
                detail=f"Battery SOC {current_soc}% is below rental minimum {min_soc}%",
            )

        active_rental = db.exec(
            select(func.count()).select_from(Rental)
            .where(Rental.battery_id == rental_in.battery_id)
            .where(Rental.status.in_(["active", "pending_payment", "reserved"]))
        ).one()
        if active_rental > 0:
            raise HTTPException(status_code=409, detail="Battery is already assigned to an active rental")

        price_details = RentalService.calculate_price(
            db,
            rental_in.battery_id,
            rental_in.duration_days,
            rental_in.promo_code,
        )

        rental = Rental(
            user_id=user_id,
            battery_id=rental_in.battery_id,
            start_station_id=rental_in.start_station_id,
            start_time=datetime.utcnow(),
            expected_end_time=datetime.utcnow() + timedelta(days=rental_in.duration_days),
            status="pending_payment",
            total_amount=price_details["total_payable"],
            security_deposit=price_details["deposit"],
        )
        db.add(rental)
        db.flush()

        apply_battery_transition(
            db,
            battery=battery,
            to_status="reserved",
            to_location_type="station",
            to_location_id=rental_in.start_station_id,
            event_type="rental_reserved",
            event_description=f"Reserved for rental #{rental.id}",
            actor_id=user_id,
        )

        RentalService._safe_commit(db, context="initiate_rental")
        db.refresh(rental)
        return rental

    @staticmethod
    def create_rental_payment_order(db: Session, rental_id: int, user_id: int) -> dict:
        rental = db.exec(select(Rental).where(Rental.id == rental_id).with_for_update()).first()
        if not rental or rental.user_id != user_id:
            raise HTTPException(status_code=404, detail="Rental not found")
        if rental.status != "pending_payment":
            raise HTTPException(status_code=400, detail="Rental is not awaiting payment")

        notes = {
            "purpose": "rental_payment",
            "rental_id": str(rental.id),
            "user_id": str(user_id),
        }
        receipt = f"rental_{rental.id}_{int(datetime.utcnow().timestamp())}"
        amount = RentalService._to_money(rental.total_amount)
        order = PaymentService.create_order(
            amount=float(amount),
            receipt=receipt,
            notes=notes,
        )

        stale_pending = db.exec(
            select(PaymentTransaction)
            .where(PaymentTransaction.user_id == user_id)
            .where(PaymentTransaction.reference_type == "rental")
            .where(PaymentTransaction.reference_id == str(rental.id))
            .where(PaymentTransaction.status == "pending")
            .with_for_update()
        ).all()
        for txn in stale_pending:
            txn.status = "failed"
            txn.error_code = "replaced"
            txn.error_description = "Superseded by a newer payment order"
            db.add(txn)

        payment_txn = PaymentTransaction(
            user_id=user_id,
            amount=amount,
            status="pending",
            payment_method="razorpay",
            razorpay_order_id=order.get("id"),
            reference_type="rental",
            reference_id=str(rental.id),
        )
        db.add(payment_txn)
        db.add(
            RentalEvent(
                rental_id=rental.id,
                event_type="payment_order_created",
                station_id=rental.start_station_id,
                battery_id=rental.battery_id,
                description=f"Created payment order {order.get('id')}",
            )
        )
        RentalService._safe_commit(db, context="create_rental_payment_order")
        db.refresh(payment_txn)

        return {
            "rental_id": rental.id,
            "payment_transaction_id": payment_txn.id,
            "order": order,
        }

    @staticmethod
    def confirm_rental_verified(
        db: Session,
        *,
        rental_id: int,
        user_id: int,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
        payment_reference: Optional[str] = None,
    ) -> Rental:
        if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
            raise HTTPException(status_code=400, detail="Payment verification payload is required")

        rental = db.exec(select(Rental).where(Rental.id == rental_id).with_for_update()).first()
        if not rental or rental.user_id != user_id:
            raise HTTPException(status_code=404, detail="Rental not found")

        if rental.status == "active":
            existing = db.exec(
                select(PaymentTransaction)
                .where(PaymentTransaction.reference_type == "rental")
                .where(PaymentTransaction.reference_id == str(rental.id))
                .where(PaymentTransaction.razorpay_payment_id == razorpay_payment_id)
                .where(PaymentTransaction.status == "success")
            ).first()
            if existing:
                return rental
            raise HTTPException(status_code=409, detail="Rental already confirmed")

        if rental.status != "pending_payment":
            raise HTTPException(status_code=400, detail="Invalid rental state")

        signature_ok = PaymentService.verify_payment_signature(
            {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            }
        )
        if not signature_ok:
            raise HTTPException(status_code=400, detail="Invalid payment signature")

        payment = PaymentService.fetch_payment(razorpay_payment_id)
        if payment.get("order_id") != razorpay_order_id:
            raise HTTPException(status_code=400, detail="Payment does not match order")

        payment_status = str(payment.get("status", "")).lower()
        if payment_status not in {"captured", "authorized"}:
            raise HTTPException(status_code=400, detail=f"Payment not settled (status={payment_status})")

        required_amount = RentalService._to_money(rental.total_amount)
        paid_amount = RentalService._to_money(Decimal(str(payment.get("amount", 0))) / Decimal("100"))
        if paid_amount < required_amount:
            raise HTTPException(status_code=400, detail="Paid amount is below rental payable amount")

        payment_notes = payment.get("notes") or {}
        note_rental_id = str(payment_notes.get("rental_id", "")).strip()
        note_user_id = str(payment_notes.get("user_id", "")).strip()
        if note_rental_id and note_rental_id != str(rental.id):
            raise HTTPException(status_code=400, detail="Payment note rental_id mismatch")
        if note_user_id and note_user_id != str(rental.user_id):
            raise HTTPException(status_code=400, detail="Payment note user_id mismatch")

        payment_txn = db.exec(
            select(PaymentTransaction)
            .where(PaymentTransaction.user_id == user_id)
            .where(PaymentTransaction.reference_type == "rental")
            .where(PaymentTransaction.reference_id == str(rental.id))
            .where(PaymentTransaction.razorpay_order_id == razorpay_order_id)
            .with_for_update()
        ).first()
        if not payment_txn:
            payment_txn = PaymentTransaction(
                user_id=user_id,
                amount=required_amount,
                status="pending",
                payment_method="razorpay",
                razorpay_order_id=razorpay_order_id,
                reference_type="rental",
                reference_id=str(rental.id),
            )
            db.add(payment_txn)
            db.flush()

        payment_txn.status = "success"
        payment_txn.amount = paid_amount
        payment_txn.razorpay_payment_id = razorpay_payment_id
        payment_txn.razorpay_signature = razorpay_signature
        payment_txn.error_code = None
        payment_txn.error_description = None
        db.add(payment_txn)

        rental.status = "active"
        db.add(
            RentalEvent(
                rental_id=rental.id,
                event_type="payment_confirmed",
                station_id=rental.start_station_id,
                battery_id=rental.battery_id,
                description=(
                    f"Rental payment verified. payment_id={razorpay_payment_id} "
                    f"reference={payment_reference or 'n/a'}"
                ),
            )
        )

        # Note: Promo code usage count was already incremented during calculate_price()
        # in initiate_rental(). No phantom promo_code_id field needed.

        battery = db.exec(select(Battery).where(Battery.id == rental.battery_id).with_for_update()).first()
        if not battery:
            raise HTTPException(status_code=404, detail="Battery not found")
        apply_battery_transition(
            db,
            battery=battery,
            to_status="deployed",
            to_location_type="customer",
            to_location_id=None,
            event_type="rental_started",
            event_description=f"Rental #{rental.id} confirmed",
            actor_id=rental.user_id,
        )

        db.add(rental)
        RentalService._safe_commit(db, context="confirm_rental_verified")
        db.refresh(rental)
        return rental

    @staticmethod
    def create_rental(db: Session, user_id: int, rental_in: RentalCreate) -> Rental:
        return RentalService.initiate_rental(db, user_id, rental_in)

    @staticmethod
    def get_active_rentals(db: Session, user_id: int) -> List[Rental]:
        from sqlalchemy.orm import selectinload

        return db.exec(
            select(Rental)
            .options(selectinload(Rental.battery), selectinload(Rental.events))
            .where(Rental.user_id == user_id, Rental.status == "active")
        ).all()

    @staticmethod
    def get_current_rental(db: Session, user_id: int) -> Optional[Rental]:
        """Return the single most-recent active or pending rental for a user, or None."""
        from sqlalchemy.orm import selectinload

        return db.exec(
            select(Rental)
            .options(selectinload(Rental.battery), selectinload(Rental.events))
            .where(
                Rental.user_id == user_id,
                Rental.status.in_(["active", "pending_payment"]),
            )
            .order_by(Rental.created_at.desc())
        ).first()

    @staticmethod
    def get_history(db: Session, user_id: int) -> List[Rental]:
        from sqlalchemy.orm import selectinload

        return db.exec(
            select(Rental)
            .options(selectinload(Rental.battery), selectinload(Rental.events))
            .where(Rental.user_id == user_id)
            .order_by(Rental.start_time.desc())
        ).all()

    @staticmethod
    def return_battery(db: Session, rental_id: int, station_id: int) -> Rental:
        rental = db.exec(select(Rental).where(Rental.id == rental_id).with_for_update()).first()
        if not rental or rental.status != "active":
            raise HTTPException(status_code=400, detail="Invalid rental")

        rental.status = "completed"
        rental.end_station_id = station_id
        rental.end_time = datetime.utcnow()

        battery = db.exec(select(Battery).where(Battery.id == rental.battery_id).with_for_update()).first()
        if not battery:
            raise HTTPException(status_code=404, detail="Battery not found")
        apply_battery_transition(
            db,
            battery=battery,
            to_status="available",
            to_location_type="station",
            to_location_id=station_id,
            event_type="rental_completed",
            event_description=f"Returned to station #{station_id} for rental #{rental.id}",
            actor_id=rental.user_id,
        )

        db.add(rental)
        db.add(
            RentalEvent(
                rental_id=rental.id,
                event_type="stop",
                station_id=station_id,
                battery_id=rental.battery_id,
                description="Rental completed",
            )
        )

        RentalService._safe_commit(db, context="return_battery")
        db.refresh(rental)
        return rental

    @staticmethod
    def request_extension(
        db: Session,
        *,
        rental_id: int,
        user_id: int,
        requested_end_date: datetime,
        reason: Optional[str],
    ) -> RentalExtension:
        rental = db.exec(select(Rental).where(Rental.id == rental_id).with_for_update()).first()
        if not rental or rental.user_id != user_id:
            raise HTTPException(status_code=404, detail="Rental not found")
        if rental.status != "active":
            raise HTTPException(status_code=400, detail="Rental is not active")
        if rental.end_time is None:
            raise HTTPException(status_code=400, detail="Rental has no scheduled end time")

        total_seconds = (requested_end_date - rental.end_time).total_seconds()
        extension_days = int(ceil(total_seconds / 86400))
        if extension_days <= 0:
            raise HTTPException(status_code=400, detail="Extension date must be after current end date")

        existing_pending = db.exec(
            select(RentalExtension)
            .where(RentalExtension.rental_id == rental_id)
            .where(RentalExtension.status == "PENDING")
        ).first()
        if existing_pending:
            raise HTTPException(status_code=409, detail="An extension request is already pending")

        # Compute daily rate from total_amount and original duration
        duration_secs = (rental.expected_end_time - rental.start_time).total_seconds()
        original_days = max(1, int(ceil(duration_secs / 86400)))
        computed_daily_rate = RentalService._to_money(rental.total_amount) / Decimal(original_days)
        additional_cost = computed_daily_rate * Decimal(extension_days)
        extension = RentalExtension(
            rental_id=rental_id,
            user_id=user_id,
            current_end_date=rental.end_time,
            requested_end_date=requested_end_date,
            extension_days=extension_days,
            additional_cost=RentalService._to_money(additional_cost),
            reason=reason,
            status="PENDING",
        )
        db.add(extension)
        db.add(
            RentalEvent(
                rental_id=rental.id,
                event_type="extension_requested",
                station_id=rental.start_station_id,
                battery_id=rental.battery_id,
                description=f"Extension requested until {requested_end_date.isoformat()}",
            )
        )
        RentalService._safe_commit(db, context="request_extension")
        db.refresh(extension)
        return extension

    @staticmethod
    def review_extension(
        db: Session,
        *,
        extension_id: int,
        reviewer_id: int,
        approve: bool,
        admin_notes: Optional[str] = None,
    ) -> RentalExtension:
        extension = db.exec(
            select(RentalExtension).where(RentalExtension.id == extension_id).with_for_update()
        ).first()
        if not extension:
            raise HTTPException(status_code=404, detail="Extension request not found")
        if extension.status != "PENDING":
            raise HTTPException(status_code=400, detail="Extension request already processed")

        rental = db.exec(select(Rental).where(Rental.id == extension.rental_id).with_for_update()).first()
        if not rental:
            raise HTTPException(status_code=404, detail="Rental not found")

        extension.approved_by = reviewer_id
        extension.approved_at = datetime.utcnow()
        extension.admin_notes = admin_notes

        if approve:
            extension.status = "APPROVED"
            rental.end_time = extension.requested_end_date
            db.add(
                RentalEvent(
                    rental_id=rental.id,
                    event_type="extension_approved",
                    station_id=rental.start_station_id,
                    battery_id=rental.battery_id,
                    description=f"Extension approved to {extension.requested_end_date.isoformat()}",
                )
            )
        else:
            extension.status = "REJECTED"
            db.add(
                RentalEvent(
                    rental_id=rental.id,
                    event_type="extension_rejected",
                    station_id=rental.start_station_id,
                    battery_id=rental.battery_id,
                    description=admin_notes or "Extension request rejected",
                )
            )

        db.add(rental)
        db.add(extension)
        RentalService._safe_commit(db, context="review_extension")
        db.refresh(extension)
        return extension

    @staticmethod
    def request_pause(
        db: Session,
        *,
        rental_id: int,
        user_id: int,
        pause_start_date: datetime,
        pause_end_date: datetime,
        reason: str,
    ) -> RentalPause:
        rental = db.exec(select(Rental).where(Rental.id == rental_id).with_for_update()).first()
        if not rental or rental.user_id != user_id:
            raise HTTPException(status_code=404, detail="Rental not found")
        if rental.status != "active":
            raise HTTPException(status_code=400, detail="Rental is not active")

        pause_days = int(ceil((pause_end_date - pause_start_date).total_seconds() / 86400))
        if pause_days <= 0:
            raise HTTPException(status_code=400, detail="Invalid pause period")

        existing_pending = db.exec(
            select(RentalPause)
            .where(RentalPause.rental_id == rental_id)
            .where(RentalPause.status.in_(["PENDING", "APPROVED", "ACTIVE"]))
        ).first()
        if existing_pending:
            raise HTTPException(status_code=409, detail="A pause request is already active")

        # Compute daily rate from total_amount and original duration
        duration_secs = (rental.expected_end_time - rental.start_time).total_seconds()
        original_days = max(1, int(ceil(duration_secs / 86400)))
        computed_daily_rate = RentalService._to_money(rental.total_amount) / Decimal(original_days)
        daily_pause_charge = computed_daily_rate * Decimal("0.20")
        total_pause_cost = RentalService._to_money(daily_pause_charge * Decimal(pause_days))

        pause = RentalPause(
            rental_id=rental_id,
            user_id=user_id,
            pause_start_date=pause_start_date,
            pause_end_date=pause_end_date,
            pause_days=pause_days,
            reason=reason,
            daily_pause_charge=daily_pause_charge,
            total_pause_cost=total_pause_cost,
            status="PENDING",
        )
        db.add(pause)
        db.add(
            RentalEvent(
                rental_id=rental.id,
                event_type="pause_requested",
                station_id=rental.start_station_id,
                battery_id=rental.battery_id,
                description=f"Pause requested from {pause_start_date.isoformat()} to {pause_end_date.isoformat()}",
            )
        )
        RentalService._safe_commit(db, context="request_pause")
        db.refresh(pause)
        return pause

    @staticmethod
    def review_pause(
        db: Session,
        *,
        pause_id: int,
        reviewer_id: int,
        approve: bool,
        admin_notes: Optional[str] = None,
    ) -> RentalPause:
        pause = db.exec(select(RentalPause).where(RentalPause.id == pause_id).with_for_update()).first()
        if not pause:
            raise HTTPException(status_code=404, detail="Pause request not found")
        if pause.status != "PENDING":
            raise HTTPException(status_code=400, detail="Pause request already processed")

        pause.approved_by = reviewer_id
        pause.approved_at = datetime.utcnow()
        pause.admin_notes = admin_notes
        pause.status = "APPROVED" if approve else "REJECTED"
        db.add(pause)
        RentalService._safe_commit(db, context="review_pause")
        db.refresh(pause)
        return pause

    @staticmethod
    def resume_pause(db: Session, *, rental_id: int, user_id: int) -> RentalPause:
        pause = db.exec(
            select(RentalPause)
            .where(RentalPause.rental_id == rental_id)
            .where(RentalPause.status.in_(["ACTIVE", "APPROVED"]))
            .order_by(RentalPause.id.desc())
            .with_for_update()
        ).first()
        if not pause:
            raise HTTPException(status_code=404, detail="No active pause found")
        if pause.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        pause.status = "COMPLETED"
        pause.battery_reclaimed_at = datetime.utcnow()
        db.add(pause)
        RentalService._safe_commit(db, context="resume_pause")
        db.refresh(pause)
        return pause

    @staticmethod
    def request_late_fee_waiver(
        db: Session,
        *,
        rental_id: int,
        user_id: int,
        requested_waiver_amount: Decimal | float,
        reason: str,
        supporting_documents: Optional[str] = None,
    ) -> LateFeeWaiver:
        late_fee = db.exec(
            select(LateFee).where(LateFee.rental_id == rental_id).with_for_update()
        ).first()
        if not late_fee:
            raise HTTPException(status_code=404, detail="No late fees found")
        if late_fee.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        if RentalService._to_money(late_fee.amount_outstanding) <= Decimal("0.00"):
            raise HTTPException(status_code=400, detail="No outstanding late fees")

        requested_amount = RentalService._to_money(requested_waiver_amount)
        if requested_amount <= 0:
            raise HTTPException(status_code=400, detail="requested_waiver_amount must be greater than zero")
        if requested_amount > RentalService._to_money(late_fee.amount_outstanding):
            raise HTTPException(status_code=400, detail="Waiver amount exceeds outstanding late fee")

        existing = db.exec(
            select(LateFeeWaiver)
            .where(LateFeeWaiver.late_fee_id == late_fee.id)
            .where(LateFeeWaiver.status == "PENDING")
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="A waiver request is already pending")

        waiver = LateFeeWaiver(
            late_fee_id=late_fee.id,
            user_id=user_id,
            requested_waiver_amount=requested_amount,
            reason=reason,
            supporting_documents=supporting_documents,
            status="PENDING",
        )
        db.add(waiver)
        RentalService._safe_commit(db, context="request_late_fee_waiver")
        db.refresh(waiver)
        return waiver

    @staticmethod
    def review_late_fee_waiver(
        db: Session,
        *,
        waiver_id: int,
        reviewer_id: int,
        approve: bool,
        approved_waiver_amount: Optional[Decimal | float] = None,
        admin_notes: Optional[str] = None,
    ) -> LateFeeWaiver:
        waiver = db.exec(select(LateFeeWaiver).where(LateFeeWaiver.id == waiver_id).with_for_update()).first()
        if not waiver:
            raise HTTPException(status_code=404, detail="Waiver request not found")
        if waiver.status != "PENDING":
            raise HTTPException(status_code=400, detail="Waiver request already processed")

        late_fee = db.exec(select(LateFee).where(LateFee.id == waiver.late_fee_id).with_for_update()).first()
        if not late_fee:
            raise HTTPException(status_code=404, detail="Late fee record not found")

        waiver.reviewed_by = reviewer_id
        waiver.reviewed_at = datetime.utcnow()
        waiver.admin_notes = admin_notes

        if approve:
            target_amount = (
                RentalService._to_money(approved_waiver_amount)
                if approved_waiver_amount is not None
                else RentalService._to_money(waiver.requested_waiver_amount)
            )
            if target_amount <= 0:
                raise HTTPException(status_code=400, detail="Approved waiver amount must be greater than zero")
            outstanding = RentalService._to_money(late_fee.amount_outstanding)
            if target_amount > outstanding:
                raise HTTPException(status_code=400, detail="Approved waiver exceeds outstanding amount")

            waiver.status = "APPROVED"
            waiver.approved_waiver_amount = target_amount
            late_fee.amount_waived = RentalService._to_money(late_fee.amount_waived) + target_amount
            late_fee.amount_outstanding = outstanding - target_amount
            if RentalService._to_money(late_fee.amount_outstanding) == Decimal("0.00"):
                late_fee.payment_status = "WAIVED"
            else:
                late_fee.payment_status = "PARTIAL"
            db.add(late_fee)
        else:
            waiver.status = "REJECTED"
            waiver.rejection_reason = admin_notes or "Waiver request rejected"

        db.add(waiver)
        RentalService._safe_commit(db, context="review_late_fee_waiver")
        db.refresh(waiver)
        return waiver
