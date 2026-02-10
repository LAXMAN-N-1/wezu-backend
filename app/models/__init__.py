from app.models.user import User
from app.models.role import Role
from app.models.menu import Menu
from app.models.role_right import RoleRight
from app.models.station import Station
from app.models.battery import Battery
from app.models.financial import Transaction, Wallet, WalletWithdrawalRequest
from app.models.address import Address
from app.models.kyc import KYCDocument, KYCRequest
from app.models.device import Device
from app.models.review import Review
from app.models.station import Station, StationImage
from app.models.rental import Rental, Purchase
from app.models.rental_event import RentalEvent
from app.models.invoice import Invoice
from app.models.notification import Notification
from app.models.support import SupportTicket, ChatSession, ChatMessage, FAQCategory, FAQItem, AutoResponse
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
from app.models.commission import Commission, Settlement
from app.models.iot import IoTDevice, DeviceCommand, FirmwareUpdate
from app.models.dealer import DealerProfile, DealerApplication, FieldVisit
from app.models.logistics import DriverProfile, DeliveryAssignment
from app.models.swap import SwapRequest, SwapHistory
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
from app.models.analytics import DemandForecast, ChurnPrediction, PricingRecommendation

