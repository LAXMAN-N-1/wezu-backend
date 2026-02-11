from app.models.user import User
from app.models.role import Role
from app.models.menu import Menu
from app.models.role_right import RoleRight
from app.models.station import Station, StationImage, StationSlot
from app.models.battery import Battery, BatteryLifecycleEvent
from app.models.battery_catalog import BatterySpec, BatteryBatch
from app.models.logistics import Warehouse, BatteryTransfer
from app.models.financial import Transaction, Wallet, WalletWithdrawalRequest
from app.models.address import Address
from app.models.kyc import KYCDocument, KYCRequest
from app.models.vehicle import Vehicle
from app.models.device import Device
from app.models.review import Review
from app.models.rental import Rental, Purchase
from app.models.rental_event import RentalEvent
from app.models.invoice import Invoice
from app.models.notification import Notification

from app.models.battery_health_log import BatteryHealthLog
from app.models.otp import OTP
from app.models.geofence import Geofence
from app.models.favorite import Favorite
from app.models.promo_code import PromoCode
from app.models.faq import FAQ
from app.models.referral import Referral
from app.models.admin_user import AdminUser
from app.models.ecommerce import EcommerceProduct, EcommerceOrder, EcommerceOrderItem
from app.models.catalog import CatalogProduct, CatalogProductImage, CatalogProductVariant, CatalogOrder, CatalogOrderItem, DeliveryTracking, DeliveryEvent
from app.models.payment import PaymentTransaction
from app.models.refund import Refund
from app.models.gps_log import GPSTrackingLog
from app.models.video_kyc import VideoKYCSession
from app.models.audit_log import AuditLog, SecurityEvent
from app.models.iot import IoTDevice, DeviceCommand, FirmwareUpdate
from app.models.dealer import DealerProfile, DealerApplication, FieldVisit


from app.models.fraud import RiskScore, FraudCheckLog, Blacklist
from app.models.maintenance import MaintenanceSchedule, MaintenanceRecord, StationDowntime
from app.models.i18n import Translation
from app.models.branch import Branch
from app.models.organization import Organization, OrganizationSocialLink
from app.models.warehouse import Warehouse

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
# Phase 1.5 & Phase 1 PowerFill Models
from app.models.rbac import Role, Permission, RolePermission, AdminUserRole, UserRole
from app.models.location import Continent, Country, Region, City, Zone
from app.models.telematics import TelemeticsData
from app.models.vendor import Vendor, VendorDocument
from app.models.swap import SwapSession
from app.models.settlement import Settlement
from app.models.support import SupportTicket, TicketMessage
from app.models.driver_profile import DriverProfile
from app.models.delivery_assignment import DeliveryAssignment
from app.models.oauth import BlacklistedToken
from app.models.commission import CommissionConfig, CommissionLog
