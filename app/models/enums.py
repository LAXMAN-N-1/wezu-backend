"""
Canonical enum definitions for the entire WEZU backend.
Import enums ONLY from this module to avoid duplicate/conflicting definitions.

Legacy enum duplicates in models and utils/constants.py are kept for backward
compatibility but should be migrated to import from here.
"""
from enum import Enum


# ── User ──────────────────────────────────────────────────────────────
class UserType(str, Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"
    DEALER = "dealer"
    DEALER_STAFF = "dealer_staff"
    SUPPORT_AGENT = "support_agent"
    LOGISTICS = "logistics"


class UserStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"
    PENDING = "pending"
    INACTIVE = "inactive"
    VERIFIED = "verified"
    DELETED = "deleted"


class KYCStatus(str, Enum):
    NOT_SUBMITTED = "not_submitted"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    UPLOADED = "uploaded"  # Compat with legacy constants


# ── Roles ─────────────────────────────────────────────────────────────
class RoleEnum(str, Enum):
    ADMIN = "admin"
    DEALER = "dealer"
    DRIVER = "driver"
    CUSTOMER = "customer"
    SUPER_ADMIN = "super_admin"
    SUPPORT_AGENT = "support_agent"
    LOGISTICS = "logistics"


# ── Battery ───────────────────────────────────────────────────────────
class BatteryStatus(str, Enum):
    AVAILABLE = "available"
    RENTED = "rented"
    CHARGING = "charging"
    MAINTENANCE = "maintenance"
    DECOMMISSIONED = "decommissioned"
    IN_TRANSIT = "in_transit"
    RESERVED = "reserved"


# ── Station ───────────────────────────────────────────────────────────
class StationStatus(str, Enum):
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"
    DECOMMISSIONED = "decommissioned"


# ── Rental ────────────────────────────────────────────────────────────
class RentalStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"
    PAUSED = "paused"
    EXTENDED = "extended"


# ── Payment ───────────────────────────────────────────────────────────
class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"


# ── Notifications ─────────────────────────────────────────────────────
class NotificationType(str, Enum):
    INFO = "info"
    ALERT = "alert"
    PROMO = "promo"
    TRANSACTION = "transaction"
    SYSTEM = "system"
