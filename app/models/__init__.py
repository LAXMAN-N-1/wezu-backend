# Core Identity & Role
from app.models.user import User, UserType, UserStatus
from app.models.user_profile import UserProfile
from app.models.rbac import Role, Permission, RolePermission, UserRole, UserAccessPath
from app.models.menu import Menu
from app.models.role_right import RoleRight
from app.models.station import Station, StationImage, StationSlot, StationStatus
from app.models.station_heartbeat import StationHeartbeat
from app.models.alert import Alert
from app.models.battery import Battery, BatteryLifecycleEvent, BatteryStatus, BatteryHealth
from app.models.battery_catalog import BatteryCatalog, BatterySpec, BatteryBatch
from app.models.logistics import BatteryTransfer, DeliveryOrder, DeliveryType, DeliveryStatus
from app.models.financial import Transaction, Wallet, WalletWithdrawalRequest, TransactionType, TransactionStatus
from app.models.address import Address
from app.models.kyc import KYCDocument, KYCRequest, KYCRecord, KYCDocumentType, KYCDocumentStatus
from app.models.vehicle import Vehicle
from app.models.device import Device
from app.models.review import Review
from app.models.rental import Rental, Purchase, RentalStatus
from app.models.rental_event import RentalEvent
from app.models.invoice import Invoice
from app.models.notification import Notification
from app.models.staff import StaffProfile
from app.models.session import UserSession

# Fleet & Inventory
from app.models.iot import IoTDevice

# Operations
from app.models.swap import Swap
from app.models.telemetry import Telemetry

# Financial
from app.models.payment import PaymentTransaction
from app.models.ecommerce import EcommerceProduct, EcommerceOrder, EcommerceOrderItem

# Support & KYC
from app.models.support import SupportTicket, TicketStatus, TicketPriority

# Location
from app.models.location import Zone, City, Region, Country

# Legacy / Other
from app.models.otp import OTP
from app.models.audit_log import AuditLog, SecurityEvent

# Admin & Support Profiles
from app.models.admin_user import AdminUser
from app.models.dealer import DealerProfile, DealerApplication, FieldVisit
from app.models.driver_profile import DriverProfile
from app.models.delivery_assignment import DeliveryAssignment
from app.models.vendor import Vendor

# Teammate Operations & IoT
from app.models.commission import Commission
from app.models.settlement import Settlement
from app.models.iot import DeviceCommand, FirmwareUpdate

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
