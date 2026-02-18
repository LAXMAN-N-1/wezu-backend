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
# Admin & Support Profiles
from app.models.admin_user import AdminUser
from app.models.dealer import DealerProfile, DealerApplication, FieldVisit
from app.models.driver_profile import DriverProfile
from app.models.logistics import DeliveryAssignment
from app.models.staff import StaffProfile
from app.models.vendor import Vendor
from app.models.device import Device
from app.models.role_right import RoleRight
from app.models.menu import Menu

# Teammate Operations & IoT
from app.models.commission import Commission, Settlement
from app.models.iot import DeviceCommand, FirmwareUpdate
from app.models.swap import SwapRequest, SwapHistory
from app.models.fraud import RiskScore, FraudCheckLog, Blacklist
from app.models.maintenance import MaintenanceSchedule, MaintenanceRecord, StationDowntime
from app.models.i18n import Translation
from app.models.branch import Branch
from app.models.organization import Organization, OrganizationSocialLink
from app.models.warehouse import Warehouse
from app.models.stock import Stock
from app.models.stock_movement import StockMovement

# New critical models
from app.models.dealer_inventory import DealerInventory, InventoryTransaction
from app.models.dealer_promotion import DealerPromotion, PromotionUsage
from app.models.delivery_route import DeliveryRoute, RouteStop
from app.models.return_request import ReturnRequest, ReturnInspection
from app.models.rental_modification import RentalExtension, RentalPause
from app.models.late_fee import LateFee, LateFeeWaiver
from app.models.device_fingerprint import DeviceFingerprint, DuplicateAccount
from app.models.swap_suggestion import SwapSuggestion, SwapPreference
from app.models.batch_job import BatchJob, JobExecution
from app.models.notification_preference import NotificationPreference
from app.models.search_history import SearchHistory
from app.models.analytics import DemandForecast, ChurnPrediction, PricingRecommendation

# Models to be pruned or refactored later
from app.models.vehicle import Vehicle
from app.models.review import Review
from app.models.invoice import Invoice
