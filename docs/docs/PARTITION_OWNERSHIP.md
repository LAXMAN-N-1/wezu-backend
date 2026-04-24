# Partition Ownership Contract

Locked ownership contract for Phases 3-7.

## Partition: identity_access

| Field | Contract |
|---|---|
| Owns | User, Session, RefreshToken, Passkey, OTP, AuthLog models and all schemas/services/repositories/routers for identity and authentication flows. Owns JWT encode/decode contract. |
| Depends on | platform_core |
| Exposes | UserService.get_by_id, UserService.get_by_phone, AuthService.verify_token, AuthService.get_current_user |
| Forbidden | Must not import from any other partition. Other partitions must use exposed interfaces only for user context. |
| Owned models/services/repositories/schemas/routers (count) | 54 |

## Partition: kyc_fraud_compliance

| Field | Contract |
|---|---|
| Owns | KYCDocument, KYCStatus, FraudFlag, ComplianceEvent model space and all KYC/fraud/compliance routes/services/schemas. |
| Depends on | platform_core, identity_access (UserService.get_by_id) |
| Exposes | KYCService.get_status(user_id), KYCService.is_verified(user_id), FraudService.flag_event(user_id, event_type) |
| Forbidden | Must not write User model directly. Emit events for status changes instead of inline cross-partition mutations. |
| Owned models/services/repositories/schemas/routers (count) | 17 |

## Partition: customer_rental_swap

| Field | Contract |
|---|---|
| Owns | Rental, Swap, RentalPlan, BatteryAssignment, RentalEvent model space and rental lifecycle APIs. |
| Depends on | platform_core, identity_access, iot_telematics_system, finance_wallet_payments |
| Exposes | RentalService.get_active_rental(user_id), RentalService.get_rental_by_id(rental_id), SwapService.get_swap_history(user_id) |
| Forbidden | Must not write Wallet/Payment models directly; no direct telemetry table queries; no dealer flow mutation. |
| Owned models/services/repositories/schemas/routers (count) | 26 |

## Partition: finance_wallet_payments

| Field | Contract |
|---|---|
| Owns | Wallet, Transaction, PaymentOrder, Refund, Settlement, WalletLedger model space and payment lifecycle APIs. |
| Depends on | platform_core, identity_access |
| Exposes | WalletService.get_balance, WalletService.deduct, WalletService.credit, PaymentService.initiate, PaymentService.get_status |
| Forbidden | Must not import rental/dealer/IoT models. Every balance mutation must write ledger in same transaction. |
| Owned models/services/repositories/schemas/routers (count) | 37 |

## Partition: dealer_portal

| Field | Contract |
|---|---|
| Owns | Dealer, DealerDocument, DealerKYC, DealerCommission, DealerStation model space and dealer portal workflows. |
| Depends on | platform_core, identity_access, kyc_fraud_compliance, finance_wallet_payments |
| Exposes | DealerService.get_by_id, DealerService.get_stations, CommissionService.get_summary |
| Forbidden | Must not directly modify rental or customer wallet records. |
| Owned models/services/repositories/schemas/routers (count) | 44 |

## Partition: logistics_supply

| Field | Contract |
|---|---|
| Owns | LogisticsOrder, Driver, DriverAssignment, Vehicle, DeliveryEvent, InventoryTransfer model space and logistics APIs. |
| Depends on | platform_core, identity_access, iot_telematics_system |
| Exposes | LogisticsService.get_order(order_id), DriverService.get_driver_dashboard_stats(driver_id), InventoryService.get_stock(station_id) |
| Forbidden | Must not initiate payments and must not modify rental state. |
| Owned models/services/repositories/schemas/routers (count) | 54 |

## Partition: iot_telematics_system

| Field | Contract |
|---|---|
| Owns | Battery, Station, BatteryTelemetry, StationTelemetry, MaintenanceRecord, BatteryHealth model space and device-state APIs. |
| Depends on | platform_core |
| Exposes | BatteryService.get_available, BatteryService.get_by_id, StationService.get_by_id, StationService.get_nearby, MaintenanceService.get_maintenance_history, MaintenanceService.get_maintenance_schedule |
| Forbidden | No imports from business partitions. This partition is a state provider only and does not initiate finance/rental operations. |
| Owned models/services/repositories/schemas/routers (count) | 49 |

## Partition: comms_content_engagement

| Field | Contract |
|---|---|
| Owns | Notification, PushToken, EmailLog, SMSLog, ContentTemplate, AppVersion, FAQ model space and content/notification APIs. |
| Depends on | platform_core |
| Exposes | NotificationService.send(user_id, event_type, payload) |
| Forbidden | Must not import business partitions directly. Consume inputs via internal events; avoid storing unnecessary PII/financial data. |
| Owned models/services/repositories/schemas/routers (count) | 55 |

## Partition: admin_platform_ops

| Field | Contract |
|---|---|
| Owns | AdminUser, AdminRole, AdminPermission, AuditLog, AlertRule, AnalyticsSnapshot, BulkOperation model space and admin APIs. |
| Depends on | platform_core, identity_access, all partitions (read interfaces only) |
| Exposes | None (consumer partition) |
| Forbidden | Must not directly mutate records owned by other partitions. All cross-domain writes must go through owner service interfaces. |
| Owned models/services/repositories/schemas/routers (count) | 98 |

## Partition: platform_core

| Field | Contract |
|---|---|
| Owns | app/core and shared infrastructure primitives: config, db, redis, security, middleware, exceptions, events, standard envelopes. |
| Depends on | None |
| Exposes | get_db, get_redis, get_current_user, settings, AppException hierarchy, event bus, StandardResponse, PaginatedResponse |
| Forbidden | No business logic and no imports from business partitions. |
| Owned models/services/repositories/schemas/routers (count) | 29 |
