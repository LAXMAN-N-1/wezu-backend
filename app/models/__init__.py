# Core Identity & Role
from app.models.user import User, UserType, UserStatus
from app.models.user_profile import UserProfile
from app.models.rbac import Role, Permission, RolePermission, UserRole, UserAccessPath, AdminUserRole
from app.models.token import SessionToken
from app.models.two_factor_auth import TwoFactorAuth
from app.models.session import UserSession
from app.models.password_history import PasswordHistory
from app.models.device_fingerprint import DeviceFingerprint, DuplicateAccount
from app.models.login_history import LoginHistory

# Fleet, Inventory & IoT
from app.models.station import Station, StationImage, StationSlot, StationStatus
from app.models.station_heartbeat import StationHeartbeat
from app.models.battery import Battery, BatteryLifecycleEvent, BatteryStatus, BatteryHealth, LocationType, BatteryAuditLog, BatteryHealthHistory
from app.models.battery_catalog import BatteryCatalog, BatterySpec, BatteryBatch
from app.models.battery_health import BatteryHealthSnapshot, BatteryMaintenanceSchedule, BatteryHealthAlert
from app.models.battery_health_log import BatteryHealthLog
from app.models.station_stock import StationStockConfig, ReorderRequest, StockAlertDismissal
from app.models.iot import IoTDevice, DeviceCommand, FirmwareUpdate
from app.models.device import Device
from app.models.gps_log import GPSTrackingLog
from app.models.telemetry import Telemetry
from app.models.geofence import Geofence
from app.models.alert import Alert

# Operations & Rentals
from app.models.rental import Rental, RentalStatus, Purchase
from app.models.rental_event import RentalEvent
from app.models.rental_modification import RentalExtension, RentalPause
from app.models.swap import SwapSession # SwapRequest and SwapHistory don't exist
from app.models.swap_suggestion import SwapSuggestion, SwapPreference
from app.models.logistics import DeliveryOrder, DeliveryType, DeliveryStatus, BatteryTransfer
from app.models.delivery_assignment import DeliveryAssignment
from app.models.delivery_route import DeliveryRoute, RouteStop
from app.models.return_request import ReturnRequest
from app.models.maintenance import MaintenanceSchedule, MaintenanceRecord, StationDowntime
from app.models.charging_queue import ChargingQueue
from app.models.vehicle import Vehicle

# Financial & E-commerce
from app.models.financial import Transaction, Wallet, TransactionType, TransactionStatus, WalletWithdrawalRequest
from app.models.payment import PaymentTransaction
from app.models.ecommerce import EcommerceProduct, EcommerceOrder, EcommerceOrderItem
from app.models.catalog import CatalogProduct, CatalogProductImage, CatalogProductVariant, CatalogOrder, CatalogOrderItem, DeliveryTracking, DeliveryEvent
from app.models.invoice import Invoice
from app.models.revenue_report import RevenueReport
from app.models.commission import CommissionConfig, CommissionTier, CommissionLog
from app.models.settlement import Settlement
from app.models.settlement_dispute import SettlementDispute
from app.models.chargeback import Chargeback
from app.models.refund import Refund
from app.models.late_fee import LateFee, LateFeeWaiver
from app.models.promo_code import PromoCode
from app.models.referral import Referral

# Support, KYC & Feedback
from app.models.support import SupportTicket, TicketStatus, TicketPriority
from app.models.kyc import KYCDocument, KYCRecord, KYCRequest, KYCDocumentType, KYCDocumentStatus
from app.models.video_kyc import VideoKYCSession
from app.models.feedback import Feedback
from app.models.review import Review
from app.models.faq import FAQ
from app.models.blog import Blog
from app.models.banner import Banner
from app.models.legal import LegalDocument
from app.models.media import MediaAsset

# Location & Org
from app.models.location import Zone, City, Region, Country, Continent
from app.models.address import Address
from app.models.payment import PaymentTransaction
from app.models.refund import Refund
from app.models.gps_log import GPSTrackingLog
from app.models.video_kyc import VideoKYCSession
from app.models.audit_log import AuditLog, SecurityEvent
from app.models.iot import IoTDevice, DeviceCommand, FirmwareUpdate
from app.models.dealer import DealerProfile, DealerApplication, FieldVisit


# Teammate Operations & IoT
from app.models.commission import CommissionConfig, CommissionLog, CommissionTier
from app.models.settlement import Settlement
from app.models.fraud import RiskScore, FraudCheckLog, Blacklist
from app.models.maintenance import MaintenanceSchedule, MaintenanceRecord, StationDowntime
from app.models.i18n import Translation
from app.models.branch import Branch
from app.models.organization import Organization, OrganizationSocialLink
from app.models.warehouse import Warehouse

# System & Other
from app.models.otp import OTP
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from app.models.audit_log import AuditLog, SecurityEvent
from app.models.admin_user import AdminUser
from app.models.dealer import DealerProfile, DealerApplication, FieldVisit
from app.models.driver_profile import DriverProfile
from app.models.staff import StaffProfile
from app.models.vendor import Vendor, VendorDocument
from app.models.role_right import RoleRight
from app.models.menu import Menu
from app.models.favorite import Favorite
from app.models.i18n import Translation
from app.models.fraud import RiskScore, FraudCheckLog, Blacklist
from app.models.batch_job import BatchJob, JobExecution
from app.models.membership import UserMembership
from app.models.oauth import BlacklistedToken
from app.models.dealer_kyc import DealerKYCApplication, KYCStateTransition
from app.models.dealer_inventory import DealerInventory, InventoryTransaction
from app.models.dealer_promotion import DealerPromotion, PromotionUsage
from app.models.search_history import SearchHistory
# Phase 1.5 & Phase 1 PowerFill Models
from app.models.telemetry import Telemetry
from app.models.vendor import Vendor, VendorDocument
from app.models.swap import SwapSession
from app.models.settlement import Settlement

# E-commerce & Catalog
from app.models.catalog import (
    CatalogProduct, CatalogProductImage, CatalogProductVariant, 
    CatalogOrder, CatalogOrderItem, DeliveryTracking, DeliveryEvent
)
from app.models.promo_code import PromoCode
from app.models.referral import Referral

# KYC & Support
from app.models.kyc import KYCDocument, KYCRequest, KYCRecord, KYCDocumentType, KYCDocumentStatus
from app.models.video_kyc import VideoKYCSession
from app.models.support import SupportTicket, TicketStatus, TicketPriority
from app.models.feedback import Feedback

# Operations & Logistics
from app.models.logistics import BatteryTransfer, DeliveryOrder, DeliveryType, DeliveryStatus
from app.models.delivery_assignment import DeliveryAssignment
from app.models.oauth import BlacklistedToken
from app.models.dealer_kyc import DealerKYCApplication, KYCStateTransition
from app.models.chargeback import Chargeback
from app.models.settlement_dispute import SettlementDispute
from app.models.password_history import PasswordHistory
from app.models.revenue_report import RevenueReport
from app.models.delivery_route import DeliveryRoute, RouteStop
from app.models.battery_reservation import BatteryReservation
from app.models.batch_job import BatchJob, JobExecution

# Security & Sessions
from app.models.otp import OTP
from app.models.two_factor_auth import TwoFactorAuth
from app.models.session import UserSession
from app.models.login_history import LoginHistory
from app.models.favorite import Favorite
from app.models.device_fingerprint import DeviceFingerprint, DuplicateAccount
from app.models.security_question import SecurityQuestion, UserSecurityQuestion
from app.models.token import SessionToken

# Misc & History
from app.models.user_history import UserStatusLog
from app.models.search_history import SearchHistory
from app.models.address import Address
from app.models.vehicle import Vehicle
from app.models.device import Device
from app.models.review import Review
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from app.models.membership import UserMembership
from app.models.analytics import DemandForecast, ChurnPrediction, PricingRecommendation

# Profiles
from app.models.admin_user import AdminUser
from app.models.staff import StaffProfile
from app.models.dealer import DealerProfile, DealerApplication, FieldVisit
from app.models.driver_profile import DriverProfile
from app.models.vendor import Vendor

# Promotional Campaign Engine
from app.models.campaign import Campaign, CampaignTarget, CampaignSend

# Knowledge Base (Task 9)
from app.models.article_category import ArticleCategory
from app.models.knowledge_article import KnowledgeArticle
from app.models.article_view import ArticleView

# Dealer Notifications
from app.models.dealer_notification_pref import DealerNotificationPreference
