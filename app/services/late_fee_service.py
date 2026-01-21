"""
Late Fee Service
Calculate and manage late fees for overdue rentals
"""
from sqlmodel import Session, select
from typing import Optional, Dict
from datetime import datetime, timedelta
from app.models.rental import Rental
from app.models.financial import Transaction
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class LateFeeService:
    """Late fee calculation and management"""
    
    @staticmethod
    def calculate_late_fee(rental_id: int, session: Session) -> Dict:
        """
        Calculate late fee for rental
        
        Args:
            rental_id: Rental ID
            session: Database session
            
        Returns:
            Dict with late fee details
        """
        rental = session.get(Rental, rental_id)
        if not rental:
            return {'late_fee': 0, 'hours_late': 0, 'is_late': False}
        
        # Check if rental has ended
        if not rental.end_time:
            # Still active, check if overdue
            expected_end = rental.start_time + timedelta(hours=rental.duration_hours or 24)
            now = datetime.utcnow()
            
            if now <= expected_end:
                return {'late_fee': 0, 'hours_late': 0, 'is_late': False}
            
            # Calculate hours late
            hours_late = (now - expected_end).total_seconds() / 3600
        else:
            # Rental ended, check if it was late
            expected_end = rental.start_time + timedelta(hours=rental.duration_hours or 24)
            
            if rental.end_time <= expected_end:
                return {'late_fee': 0, 'hours_late': 0, 'is_late': False}
            
            hours_late = (rental.end_time - expected_end).total_seconds() / 3600
        
        # Apply grace period
        grace_period_hours = settings.RENTAL_GRACE_PERIOD_HOURS if hasattr(settings, 'RENTAL_GRACE_PERIOD_HOURS') else 2
        
        if hours_late <= grace_period_hours:
            return {
                'late_fee': 0,
                'hours_late': round(hours_late, 2),
                'is_late': True,
                'in_grace_period': True
            }
        
        # Calculate late fee
        chargeable_hours = hours_late - grace_period_hours
        
        # Late fee is 1.5x the daily rate per hour
        late_fee_multiplier = settings.LATE_FEE_MULTIPLIER if hasattr(settings, 'LATE_FEE_MULTIPLIER') else 1.5
        hourly_rate = rental.daily_rate / 24
        late_fee = chargeable_hours * hourly_rate * late_fee_multiplier
        
        return {
            'late_fee': round(late_fee, 2),
            'hours_late': round(hours_late, 2),
            'chargeable_hours': round(chargeable_hours, 2),
            'hourly_rate': round(hourly_rate, 2),
            'is_late': True,
            'in_grace_period': False
        }
    
    @staticmethod
    def apply_late_fee(rental_id: int, session: Session) -> Optional[Transaction]:
        """
        Apply late fee to rental and create transaction
        
        Args:
            rental_id: Rental ID
            session: Database session
            
        Returns:
            Transaction record or None
        """
        try:
            rental = session.get(Rental, rental_id)
            if not rental:
                return None
            
            # Calculate late fee
            fee_details = LateFeeService.calculate_late_fee(rental_id, session)
            
            if fee_details['late_fee'] <= 0:
                return None
            
            # Check if late fee already applied
            existing_fee = session.exec(
                select(Transaction)
                .where(Transaction.rental_id == rental_id)
                .where(Transaction.transaction_type == "LATE_FEE")
            ).first()
            
            if existing_fee:
                logger.info(f"Late fee already applied for rental {rental_id}")
                return existing_fee
            
            # Create late fee transaction
            transaction = Transaction(
                user_id=rental.user_id,
                rental_id=rental_id,
                transaction_type="LATE_FEE",
                amount=fee_details['late_fee'],
                status="PENDING",
                description=f"Late fee for {fee_details['chargeable_hours']:.1f} hours overdue",
                metadata=str(fee_details)
            )
            session.add(transaction)
            
            # Update rental total cost
            rental.total_cost += fee_details['late_fee']
            session.add(rental)
            
            session.commit()
            session.refresh(transaction)
            
            logger.info(f"Late fee of ₹{fee_details['late_fee']} applied to rental {rental_id}")
            return transaction
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to apply late fee: {str(e)}")
            return None
    
    @staticmethod
    def get_overdue_rentals(session: Session) -> list:
        """Get all overdue rentals"""
        now = datetime.utcnow()
        
        # Get active rentals
        active_rentals = session.exec(
            select(Rental).where(Rental.status == "active")
        ).all()
        
        overdue = []
        for rental in active_rentals:
            expected_end = rental.start_time + timedelta(hours=rental.duration_hours or 24)
            
            if now > expected_end:
                fee_details = LateFeeService.calculate_late_fee(rental.id, session)
                overdue.append({
                    'rental_id': rental.id,
                    'user_id': rental.user_id,
                    'hours_late': fee_details['hours_late'],
                    'late_fee': fee_details['late_fee']
                })
        
        return overdue
