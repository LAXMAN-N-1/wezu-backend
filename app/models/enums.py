from __future__ import annotations
"""
Canonical enum definitions for the entire WEZU backend.
Import enums ONLY from this module to avoid duplicate/conflicting definitions.

Legacy enum duplicates in models and utils/constants.py are kept for backward
compatibility but should be migrated to import from here.
"""
from enum import Enum


# ── User ──────────────────────────────────────────────────────────────
class UserType(str, Enum):
    CUSTOMER = "CUSTOMER"
    ADMIN = "ADMIN"
    DEALER = "DEALER"
    DEALER_STAFF = "DEALER_STAFF"
    SUPPORT_AGENT = "SUPPORT_AGENT"
    LOGISTICS = "LOGISTICS"


class UserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    PENDING = "PENDING"
    INACTIVE = "INACTIVE"
    VERIFIED = "VERIFIED"
    DELETED = "DELETED"


class KYCStatus(str, Enum):
    NOT_SUBMITTED = "NOT_SUBMITTED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    UPLOADED = "UPLOADED"  # Compat with legacy constants


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
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    CLOSED = "closed"
    ERROR = "error"
    OFFLINE = "offline"


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
