# Core Identity & Role
from app.models.user import User, UserType, UserStatus
from app.models.user_profile import UserProfile
from app.models.rbac import Role, Permission, RolePermission, UserRole, UserAccessPath

# Fleet & Inventory
from app.models.station import Station, StationImage, StationSlot, StationStatus
from app.models.battery import Battery, BatteryLifecycleEvent, BatteryStatus, BatteryHealth
from app.models.battery_catalog import BatteryCatalog
from app.models.iot import IoTDevice

# Operations
from app.models.rental import Rental, RentalStatus
from app.models.swap import Swap
from app.models.telemetry import Telemetry
from app.models.logistics import DeliveryOrder, DeliveryType, DeliveryStatus

# Financial
from app.models.financial import Transaction, Wallet, TransactionType, TransactionStatus

# Support & KYC
from app.models.support import SupportTicket, TicketStatus, TicketPriority
from app.models.kyc import KYCDocument, KYCRecord, KYCRequest, KYCDocumentType, KYCDocumentStatus

# Location
from app.models.location import Zone, City, Region, Country

# Legacy / Other (Keep specific ones if needed, comment out if replaced)
from app.models.address import Address
from app.models.otp import OTP
from app.models.notification import Notification
from app.models.audit_log import AuditLog, SecurityEvent
from app.models.admin_user import AdminUser
from app.models.dealer import DealerProfile
from app.models.driver_profile import DriverProfile
from app.models.staff import StaffProfile
from app.models.vendor import Vendor
from app.models.device import Device
from app.models.role_right import RoleRight
from app.models.menu import Menu

# Models to be pruned or refactored later
from app.models.vehicle import Vehicle
from app.models.review import Review
from app.models.invoice import Invoice
