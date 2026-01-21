from enum import Enum

class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

class BatteryStatus(str, Enum):
    AVAILABLE = "available"
    RENTED = "rented"
    CHARGING = "charging"
    MAINTENANCE = "maintenance"
    DECOMMISSIONED = "decommissioned"

class StationStatus(str, Enum):
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"

class RentalStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"

class KYCStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    UPLOADED = "uploaded"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"

class NotificationType(str, Enum):
    INFO = "info"
    ALERT = "alert"
    PROMO = "promo"
    TRANSACTION = "transaction"
