# Expected End-to-End Flows & Process Series

> **Purpose**: Exhaustive specification of every meaningful user journey across the Wezu EV Battery Swap platform.  
> Each flow documents: actors, preconditions, step-by-step sequence, state transitions, side effects, generated artifacts, and failure/rollback paths.  
> **Generated**: 2026-04-06 from codebase reconnaissance of 160+ models, 100+ services, 1034 routes.

---

## Table of Contents

1. [Customer Lifecycle Flows](#1-customer-lifecycle-flows)
   - 1.1 [Registration & Onboarding](#11-registration--onboarding)
   - 1.2 [KYC Verification](#12-kyc-verification)
   - 1.3 [Wallet Top-Up & Payment Methods](#13-wallet-top-up--payment-methods)
   - 1.4 [Station Discovery & Battery Reservation](#14-station-discovery--battery-reservation)
   - 1.5 [Battery Rental (Core Transaction)](#15-battery-rental-core-transaction)
   - 1.6 [Battery Swap at Station](#16-battery-swap-at-station)
   - 1.7 [Battery Return & Rental Completion](#17-battery-return--rental-completion)
   - 1.8 [Overdue Rental & Late Fee](#18-overdue-rental--late-fee)
   - 1.9 [Rental Extension](#19-rental-extension)
   - 1.10 [Rental Pause / Resume](#110-rental-pause--resume)
   - 1.11 [Refund Request](#111-refund-request)
   - 1.12 [Wallet Withdrawal](#112-wallet-withdrawal)
   - 1.13 [Support Ticket & Chat](#113-support-ticket--chat)
   - 1.14 [Referral Program](#114-referral-program)
   - 1.15 [Membership & Loyalty Points](#115-membership--loyalty-points)
   - 1.16 [Promo Code Redemption](#116-promo-code-redemption)
   - 1.17 [Review & Rating](#117-review--rating)

2. [Dealer Lifecycle Flows](#2-dealer-lifecycle-flows)
   - 2.1 [Dealer Application & Onboarding](#21-dealer-application--onboarding)
   - 2.2 [Dealer KYC & Document Verification](#22-dealer-kyc--document-verification)
   - 2.3 [Station Setup & Activation](#23-station-setup--activation)
   - 2.4 [Inventory Management & Stock Movement](#24-inventory-management--stock-movement)
   - 2.5 [Dealer Dashboard: Real-Time Order/Swap Visibility](#25-dealer-dashboard-real-time-orderswap-visibility)
   - 2.6 [Commission Accrual & Settlement Payout](#26-commission-accrual--settlement-payout)
   - 2.7 [Dealer Promotions & Campaigns](#27-dealer-promotions--campaigns)
   - 2.8 [Staff Management](#28-staff-management)

3. [Admin / Platform Flows](#3-admin--platform-flows)
   - 3.1 [Admin User & RBAC Management](#31-admin-user--rbac-management)
   - 3.2 [Customer KYC Queue Review](#32-customer-kyc-queue-review)
   - 3.3 [Dealer Application Review Pipeline](#33-dealer-application-review-pipeline)
   - 3.4 [Fleet-Wide Battery Lifecycle Management](#34-fleet-wide-battery-lifecycle-management)
   - 3.5 [Station Monitoring & Heartbeat](#35-station-monitoring--heartbeat)
   - 3.6 [Fraud Detection & Blacklisting](#36-fraud-detection--blacklisting)
   - 3.7 [Revenue Reporting & Analytics](#37-revenue-reporting--analytics)
   - 3.8 [Settlement Approval & Batch Payout](#38-settlement-approval--batch-payout)
   - 3.9 [Maintenance Scheduling & Automation](#39-maintenance-scheduling--automation)
   - 3.10 [Notification Campaigns (Push/SMS/WhatsApp)](#310-notification-campaigns-pushsmswhatsapp)
   - 3.11 [CMS Management (Banners, Blogs, FAQs, Legal)](#311-cms-management)
   - 3.12 [Feature Flags & System Configuration](#312-feature-flags--system-configuration)

4. [IoT & Hardware Flows](#4-iot--hardware-flows)
   - 4.1 [Station Slot Lock/Unlock & Swap Execution](#41-station-slot-lockunlock--swap-execution)
   - 4.2 [Battery Telemetry Ingestion](#42-battery-telemetry-ingestion)
   - 4.3 [Charging Queue Optimization](#43-charging-queue-optimization)
   - 4.4 [BESS (Battery Energy Storage System) Grid Events](#44-bess-grid-events)

5. [Logistics & Supply Chain Flows](#5-logistics--supply-chain-flows)
   - 5.1 [Battery Transfer Between Locations](#51-battery-transfer-between-locations)
   - 5.2 [Logistics Order & Delivery Tracking](#52-logistics-order--delivery-tracking)
   - 5.3 [Reverse Logistics (Returns)](#53-reverse-logistics-returns)
   - 5.4 [Warehouse Rack/Shelf Inventory](#54-warehouse-rackshelf-inventory)

6. [Financial Flows](#6-financial-flows)
   - 6.1 [End-to-End Cash Flow: Rental → Commission → Settlement](#61-end-to-end-cash-flow)
   - 6.2 [Invoice Generation](#62-invoice-generation)
   - 6.3 [Chargeback Processing](#63-chargeback-processing)

---

## 1. Customer Lifecycle Flows

### 1.1 Registration & Onboarding

**Actors**: Customer (mobile app), Backend, Firebase/Google/Apple Auth  
**Preconditions**: None

| Step | Actor | Action | State Change | Side Effects |
|------|-------|--------|-------------|-------------|
| 1 | Customer | Sends `POST /api/v1/auth/register` with phone/email + password (or social OAuth token) | — | — |
| 2 | Backend | Validates uniqueness of phone/email | — | — |
| 3 | Backend | Creates `User` record (`status=active`, `kyc_status=NOT_SUBMITTED`) | `User.created` | — |
| 4 | Backend | Creates `Wallet` (balance=0.0, currency=INR) linked to user | `Wallet.created` | — |
| 5 | Backend | Creates `NotificationPreference` with defaults | `NotifPref.created` | — |
| 6 | Backend | Generates OTP → stores in `OTP` table, sends via SMS | `OTP.created` | SMS sent |
| 7 | Customer | Submits OTP via `POST /api/v1/auth/verify-otp` | — | — |
| 8 | Backend | Validates OTP, creates `UserSession` (access + refresh tokens) | `User.is_verified=true`, `Session.created` | — |
| 9 | Backend | Records `LoginHistory` entry | `LoginHistory.created` | — |
| 10 | Backend | Fires notification: "Welcome to Wezu Energy!" | `Notification.created` | Push via FCM |

**Auto-Generated Artifacts**: User ID, Wallet ID, Session Tokens (JWT), OTP  
**Failure Path**: Duplicate phone/email → 409. Invalid OTP → 401. Rate-limited OTP → 429 (FraudService.check_velocity).

---

### 1.2 KYC Verification

**Actors**: Customer, Backend, KYCService (MockKYC / PendingReviewProvider), Admin  
**Preconditions**: User registered & verified

| Step | Actor | Action | State Change | Side Effects |
|------|-------|--------|-------------|-------------|
| 1 | Customer | Uploads Aadhaar via `POST /api/v1/kyc/aadhaar` | — | — |
| 2 | Backend | `KYCService.verify_aadhaar()` → mock auto-approve (dev) or queue for manual review (prod) | `User.kyc_status → PENDING or APPROVED` | `KYCDocument.created` |
| 3 | Customer | Uploads PAN via `POST /api/v1/kyc/pan` | `User.kyc_status → APPROVED` (if both pass) | `KYCDocument.created` |
| 4 | Customer | (Optional) Video KYC via `POST /api/v1/kyc/video` | `User.kyc_status → PENDING` (prod) | Queued for manual review |
| 5 | Admin | Reviews pending KYC docs in admin queue | — | — |
| 6 | Admin | Approves/rejects via `POST /api/v1/admin/kyc/{user_id}/verify` | `KYCDocument.status → VERIFIED/REJECTED`, `User.kyc_status → APPROVED/REJECTED` | Notification to customer |

**Guard**: `KYCService.__init__` raises `RuntimeError` if `MockKYCProvider` is active in production.  
**Failure Path**: Blurry document → REJECTED with reason code (DOC_BLURRY). Customer can resubmit via `KYCService.resubmit_kyc`.

---

### 1.3 Wallet Top-Up & Payment Methods

**Actors**: Customer, Backend, Razorpay Gateway  
**Preconditions**: User registered

| Step | Actor | Action | State Change | Side Effects |
|------|-------|--------|-------------|-------------|
| 1 | Customer | Adds payment method via `POST /api/v1/wallet/payment-methods` | `PaymentMethod.created` | Deduplication check |
| 2 | Customer | Initiates recharge via `POST /api/v1/wallet/recharge` (amount=₹500) | — | — |
| 3 | Backend | `WalletService.create_recharge_intent()` → creates `Transaction(status=pending, type=credit, category=deposit)` + Razorpay order | `Transaction.created (pending)` | Razorpay order ID generated |
| 4 | Customer | Completes Razorpay payment on frontend | — | — |
| 5 | Razorpay | Sends webhook `payment.captured` to `POST /api/webhooks/razorpay` | — | Signature verified |
| 6 | Backend | `WalletService.apply_recharge_capture()` → credits wallet, marks transaction success | `Wallet.balance += 500`, `Transaction.status → success` | `balance_after` recorded |
| 7 | Backend | Fires notification: "₹500 added to wallet" | `Notification.created` | Push via FCM |

**Idempotency**: Double-capture returns existing successful transaction (tested in `test_wallet_invariants`).  
**Failure Path**: Payment failed → `WalletService.mark_recharge_intent_failed()` → `Transaction.status → failed`. Wallet balance unchanged.

---

### 1.4 Station Discovery & Battery Reservation

**Actors**: Customer, Backend  
**Preconditions**: User registered, KYC approved (for rental), wallet has balance

| Step | Actor | Action | State Change | Side Effects |
|------|-------|--------|-------------|-------------|
| 1 | Customer | Searches nearby stations via `GET /api/v1/bookings/stations?lat=X&lon=Y&radius=Z` | — | Haversine distance calculation |
| 2 | Backend | `BookingService.get_stations_nearby()` → filters by status=OPERATIONAL, available_batteries > 0 | — | Returns station list with distance |
| 3 | Customer | Creates reservation via `POST /api/v1/bookings/reserve` (station_id) | — | — |
| 4 | Backend | `BookingService.create_reservation()` → validates station bookable, no stale reservation, assigns battery | `BatteryReservation.created (PENDING)`, `Battery.status → rented (reserved)` | TTL-based expiry |
| 5 | Backend | Background: `BookingService.release_expired_reservations()` runs periodically | Stale reservations → `EXPIRED`, battery → `available` | Batteries freed |

**Auto-Generated**: Reservation ID, battery assignment  
**Failure Path**: Station full → 400. Station offline → 400. Existing active reservation → 409.

---

### 1.5 Battery Rental (Core Transaction)

**Actors**: Customer, Backend, Razorpay  
**Preconditions**: Active reservation OR direct walk-in, KYC approved, wallet funded

| Step | Actor | Action | State Change | Side Effects |
|------|-------|--------|-------------|-------------|
| 1 | Customer | Initiates rental via `POST /api/v1/rentals` (battery_id, station_id, duration_days) | — | — |
| 2 | Backend | `RentalService.calculate_price()` → base price + promo discount + tax | — | Returns price breakdown |
| 3 | Backend | `RentalService.initiate_rental()` → creates Rental (PENDING_PAYMENT) | `Rental.created (pending_payment)` | — |
| 4 | Backend | `RentalService.create_rental_payment_order()` → Razorpay order for rental amount + security deposit | `Transaction.created (pending, RENTAL_PAYMENT)`, `Transaction.created (pending, SECURITY_DEPOSIT)` | Razorpay order ID |
| 5 | Customer | Pays via Razorpay (or wallet deduct) | — | — |
| 6 | Backend | `RentalService.confirm_rental_verified()` → activates rental | `Rental.status → active`, `Battery.status → rented`, `Battery.current_user_id = user_id`, `Battery.station_id = NULL` | — |
| 7 | Backend | `WalletService.deduct_balance()` (if wallet payment) | `Wallet.balance -= amount`, `Transaction.status → success` | `balance_after` recorded |
| 8 | Backend | `CommissionService.calculate_and_log()` → dealer commission entry | `CommissionLog.created (pending)` | — |
| 9 | Backend | `MembershipService.earn_points()` → loyalty points accrual | `UserMembership.points += X` | Tier promotion check |
| 10 | Backend | `StationService.release_battery_from_slot()` → slot freed | `StationSlot.status → empty`, `StationSlot.battery_id = NULL`, `Station.available_batteries -= 1` | — |
| 11 | Backend | Fires notification: "Rental started! Battery #{serial} assigned" | `Notification.created` | Push + in-app |
| 12 | Backend | `BatteryService.log_lifecycle_event()` → "rented_out" event | `BatteryLifecycleEvent.created` | — |
| 13 | Backend | `RentalEvent.created` → "rental_started" | `RentalEvent.created` | — |

**Auto-Generated**: Rental ID, Transaction IDs (rental + deposit), Commission Log ID, Invoice (on completion)  
**Dealer Dashboard Sees**: New active rental in station metrics, available_batteries count decremented  
**Admin Dashboard Sees**: Real-time rental count incremented, revenue credited  

**Failure Path**: Insufficient wallet → 400. Battery unavailable → 409. Payment fails → rental stays `pending_payment`, cleaned up by `cleanup_stale_pending_rentals`.

---

### 1.6 Battery Swap at Station

**Actors**: Customer (at physical station), Station Hardware (IoT), Backend  
**Preconditions**: Active rental, customer at a station, station has available charged batteries

| Step | Actor | Action | State Change | Side Effects |
|------|-------|--------|-------------|-------------|
| 1 | Customer | Requests swap suggestions via `GET /api/v1/swap/suggestions?rental_id=X&station_id=Y` | — | — |
| 2 | Backend | `SwapService.get_swap_suggestions()` → finds available batteries at station sorted by SOC descending | — | Returns battery options with SOC % |
| 3 | Customer | Initiates swap via `POST /api/v1/swap/execute` | — | — |
| 4 | Backend | `SwapService.execute_swap()` begins: | — | — |
| 4a | Backend | Creates `SwapSession(status=initiated)` | `SwapSession.created` | — |
| 4b | Backend | Records old battery SOC from `Battery.current_charge` | `SwapSession.old_battery_soc = X%` | — |
| 4c | Backend | **Old battery**: `Battery.status → available`, `station_id = this_station`, `current_user_id = NULL` | Battery returned to station pool | — |
| 4d | Backend | `StationService.assign_battery_to_slot()` → old battery into charging slot | `StationSlot.battery_id = old_battery_id`, `StationSlot.status → charging` | Station available_batteries += 1 |
| 4e | Backend | **New battery**: `Battery.status → rented`, `station_id = NULL`, `current_user_id = user_id` | Battery assigned to customer | — |
| 4f | Backend | `StationService.release_battery_from_slot()` → new battery removed from slot | `StationSlot.status → empty`, `StationSlot.battery_id = NULL` | Station available_batteries -= 1 |
| 4g | Backend | `Rental.battery_id = new_battery_id` | Rental now tracks new battery | — |
| 4h | Backend | `SwapService.calculate_swap_fee()` → differential pricing based on SOC delta | `SwapSession.swap_amount = ₹Y` | — |
| 4i | Backend | `WalletService.deduct_balance()` → swap fee deducted from wallet | `Wallet.balance -= Y`, `Transaction.created (SWAP_FEE)` | — |
| 4j | Backend | `CommissionService.calculate_and_log()` → station dealer earns commission | `CommissionLog.created` | — |
| 4k | Backend | `SwapSession.status → completed`, `payment_status → paid` | Session complete | — |
| 5 | Backend | Fires notification: "Swap complete! New battery at X% charge" | `Notification.created` | Push |
| 6 | Backend | `BatteryService.log_lifecycle_event()` × 2 → "swapped_in" + "swapped_out" | `BatteryLifecycleEvent × 2` | — |

**Dealer Dashboard Sees**: Swap logged in station activity feed, commission accrued, inventory counts updated  
**Admin Dashboard Sees**: Swap in platform-wide analytics, revenue from swap fee  
**IoT Side Effect**: Old battery starts charging in slot → telemetry begins reporting charge progress  

**Failure Path**: No available batteries → 400. Wallet insufficient → 400. Station offline → 503. Swap fails mid-transaction → `SwapSession.status → failed`, old battery assignment restored.

---

### 1.7 Battery Return & Rental Completion

**Actors**: Customer (at station), Backend  
**Preconditions**: Active rental

| Step | Actor | Action | State Change | Side Effects |
|------|-------|--------|-------------|-------------|
| 1 | Customer | Returns battery at station via `POST /api/v1/rentals/{id}/return` (station_id) | — | — |
| 2 | Backend | `RentalService.return_battery()`: | — | — |
| 2a | Backend | Records `end_station_id`, `end_time`, `end_battery_level` | `Rental.end_station_id = X`, `Rental.end_time = now` | — |
| 2b | Backend | Calculates final amount (pro-rated if early, late fee if overdue) | `Rental.total_amount = final`, `Rental.late_fee = Z` | — |
| 2c | Backend | `Battery.status → available`, `station_id = return_station`, `current_user_id = NULL` | Battery back in pool | — |
| 2d | Backend | `StationService.assign_battery_to_slot()` → battery into slot for charging | `StationSlot.battery_id = battery_id`, `Station.available_batteries += 1` | — |
| 2e | Backend | `Rental.status → completed` | Rental closed | — |
| 3 | Backend | Security deposit refund: `WalletService.add_balance()` | `Wallet.balance += deposit`, `Rental.is_deposit_refunded = true` | `Transaction.created (credit, refund)` |
| 4 | Backend | `InvoiceService.generate_rental_invoice()` → PDF generated | `Invoice.created` | PDF stored in S3 |
| 5 | Backend | `RentalEvent.created` → "rental_completed" | `RentalEvent.created` | — |
| 6 | Backend | `BatteryService.log_lifecycle_event()` → "returned" | `BatteryLifecycleEvent.created` | — |
| 7 | Backend | Fires notification: "Rental completed! ₹X deposit refunded" | `Notification.created` | Push |

**Dealer Dashboard Sees**: Rental completed in activity log, battery count restored, revenue finalized  
**Admin Dashboard Sees**: Rental closed in analytics, deposit refund processed

---

### 1.8 Overdue Rental & Late Fee

**Actors**: Background Worker, Backend, Customer  
**Preconditions**: Active rental past `expected_end_time`

| Step | Actor | Action | State Change | Side Effects |
|------|-------|--------|-------------|-------------|
| 1 | Worker | `rental_worker.py` / `hourly_jobs.py` scans active rentals past expiry | — | — |
| 2 | Backend | `Rental.status → overdue` | State transition | — |
| 3 | Backend | `LateFeeService.calculate_late_fee()` → per-day rate × overdue days | Computed fee | — |
| 4 | Backend | `LateFeeService.apply_late_fee()` → creates `LateFee` record + deducts from wallet | `LateFee.created`, `Wallet.balance -= fee`, `Transaction.created (LATE_FEE)` | — |
| 5 | Backend | Fires notification: "Your rental is overdue. Late fee ₹X applied" | `Notification.created` | Push + SMS |
| 6 | Backend | `RentalAlert` created for admin visibility | `Alert.created` | — |

**Failure Path**: Wallet insufficient for late fee → fee recorded as pending, blocks further rentals.  
**Customer Can**: Request late fee waiver via `RentalService.request_late_fee_waiver()`. Admin reviews via `review_late_fee_waiver()`.

---

### 1.9 Rental Extension

**Actors**: Customer, Admin  
**Preconditions**: Active or overdue rental

| Step | Actor | Action | State Change | Side Effects |
|------|-------|--------|-------------|-------------|
| 1 | Customer | Requests extension via `POST /api/v1/rentals/{id}/extension` (extra_days) | — | — |
| 2 | Backend | `RentalService.request_extension()` → creates `RentalExtension(status=pending)` | `RentalExtension.created` | Notification to admin |
| 3 | Admin | Reviews via `PUT /api/v1/admin/rentals/{id}/extension/{ext_id}` (approve/reject) | — | — |
| 4 | Backend | `RentalService.review_extension()` → if approved: extends `expected_end_time`, charges additional amount | `Rental.expected_end_time += days`, `RentalExtension.status → approved`, `Transaction.created` | Wallet deducted |

---

### 1.10 Rental Pause / Resume

**Actors**: Customer, Admin  
**Preconditions**: Active rental

| Step | Actor | Action | State Change | Side Effects |
|------|-------|--------|-------------|-------------|
| 1 | Customer | Requests pause via `POST /api/v1/rentals/{id}/pause` | `RentalPause.created (pending)` | Admin notified |
| 2 | Admin | Approves pause | `RentalPause.status → approved`, billing paused | — |
| 3 | Customer | Resumes via `POST /api/v1/rentals/{id}/resume` | `RentalPause.resumed_at = now`, billing resumed, `expected_end_time` extended by pause duration | — |

---

### 1.11 Refund Request

**Actors**: Customer, Admin, Backend  
**Preconditions**: Completed transaction exists

| Step | Actor | Action | State Change | Side Effects |
|------|-------|--------|-------------|-------------|
| 1 | Customer/Admin | Initiates refund via service call | — | — |
| 2 | Backend | `WalletService.initiate_refund()` → creates `Refund(status=pending)` | `Refund.created` | Idempotent: duplicate returns existing |
| 3 | Admin | Processes refund via `WalletService.process_refund()` | `Refund.status → processed`, `Wallet.balance += amount`, `Transaction.created (credit, refund)` | Balance restored |

**Invariant**: Refund amount cannot exceed original transaction (enforced, tested).  
**Idempotency**: process_refund on already-processed refund returns existing (no double credit).

---

### 1.12 Wallet Withdrawal

**Actors**: Customer, Admin  
**Preconditions**: Wallet balance > 0

| Step | Actor | Action | State Change | Side Effects |
|------|-------|--------|-------------|-------------|
| 1 | Customer | Requests withdrawal via `POST /api/v1/wallet/withdraw` (amount, bank_details) | `WalletWithdrawalRequest.created (requested)`, `Wallet.balance -= amount` (held) | — |
| 2 | Admin | Approves: `WalletService.approve_withdrawal_request()` | `Request.status → processed`, `Transaction.created (debit, withdrawal)` | Bank transfer initiated |
| 2' | Admin | Rejects: `WalletService.reject_withdrawal_request()` | `Request.status → rejected`, `Wallet.balance += amount` (restored) | Balance returned |

**Invariant**: Rejection restores full balance (tested in `test_wallet_invariants`).

---

### 1.13 Support Ticket & Chat

| Step | Actor | Action | State Change |
|------|-------|--------|-------------|
| 1 | Customer | Creates ticket via `POST /api/v1/support/tickets` | `SupportTicket.created (open)` |
| 2 | Backend | `SupportService.assign_ticket_to_agent()` → auto-assignment | `SupportTicket.assigned_to = agent_id` |
| 3 | Backend | `SupportService.get_automated_response()` → keyword-based auto-reply | `TicketMessage.created` |
| 4 | Agent | Responds via internal message | `TicketMessage.created (is_internal=false)` |
| 5 | Customer | Can also start live chat: `SupportService.initiate_chat()` | `ChatSession.created`, `ChatMessage` flow |

---

### 1.14 Referral Program

| Step | Actor | Action | State Change |
|------|-------|--------|-------------|
| 1 | Existing user | Generates referral code via `POST /api/v1/referral/generate` | `Referral.created` with unique code |
| 2 | New user | Registers with referral code | — |
| 3 | Backend | `ReferralService.claim_referral()` → credits both referrer and referee wallets | `Wallet.balance += reward` × 2, `Referral.status → claimed` |

---

### 1.15 Membership & Loyalty Points

| Step | Actor | Action | State Change |
|------|-------|--------|-------------|
| 1 | (Auto) | After each rental/swap, `MembershipService.earn_points()` fires | `UserMembership.points += X` |
| 2 | Backend | `_process_tier_promotion()` checks upgrade eligibility | `UserMembership.tier → SILVER/GOLD/PLATINUM` if threshold met |
| 3 | Customer | Views tier benefits via `GET /api/v1/membership` | Returns tier-specific perks |

---

### 1.16 Promo Code Redemption

| Step | Actor | Action | State Change |
|------|-------|--------|-------------|
| 1 | Customer | Applies promo at checkout via `POST /api/v1/promo/validate` | — |
| 2 | Backend | `PromoService.validate_promo()` → checks expiry, usage limit, min order | Returns discount amount |
| 3 | Backend | On rental confirm: `PromoService.apply_promo()` → increments usage count | `PromoCode.current_uses += 1` |

---

### 1.17 Review & Rating

| Step | Actor | Action | State Change |
|------|-------|--------|-------------|
| 1 | Customer | Submits review via `POST /api/v1/reviews` (station_id, rating, comment) | `Review.created` |
| 2 | Backend | Updates station aggregate: `Station.rating` recalculated, `Station.total_reviews += 1` | Station rating updated |

---

## 2. Dealer Lifecycle Flows

### 2.1 Dealer Application & Onboarding

**Actors**: Prospective dealer, Backend, Admin  
**Pipeline stages**: `SUBMITTED → AUTOMATED_CHECKS_PASSED → KYC_SUBMITTED → MANUAL_REVIEW_PASSED → FIELD_VISIT_SCHEDULED → FIELD_VISIT_COMPLETED → APPROVED → TRAINING_COMPLETED → ACTIVE`

| Step | Actor | Action | State Change | Side Effects |
|------|-------|--------|-------------|-------------|
| 1 | Dealer | Registers as user, then applies via `POST /api/v1/dealers/apply` | `User.created`, `DealerProfile.created (is_active=false)`, `DealerApplication.created (SUBMITTED)` | — |
| 2 | Backend | `DealerKYCService.run_auto_checks()` → GST verification, PAN check | `DealerApplication.current_stage → AUTOMATED_CHECKS_PASSED` | `risk_score` computed |
| 3 | Dealer | Submits KYC documents via `DealerKYCService.submit_documents()` | `DealerKYCApplication.created`, `DealerDocument × N created` | S3 upload |
| 4 | Admin | Manual review via `DealerKYCService.manual_review()` | `→ MANUAL_REVIEW_PASSED` or `→ REJECTED` | — |
| 5 | Admin | Schedules field visit via `DealerService.schedule_field_visit()` | `FieldVisit.created`, `→ FIELD_VISIT_SCHEDULED` | — |
| 6 | Field officer | Completes visit via `DealerService.complete_field_visit()` | `FieldVisit.report = {...}`, `→ FIELD_VISIT_COMPLETED` | Photos uploaded |
| 7 | Admin | Final approval via `DealerKYCService.activate_dealer()` | `→ APPROVED → ACTIVE`, `DealerProfile.is_active = true` | Notification to dealer |

**Each stage transition**: `KYCStateTransition` logged, `DealerApplication.status_history` JSON appended.

---

### 2.2 Dealer KYC & Document Verification

Separate from user KYC. Uses `DealerKYCService` with its own document types (GST certificate, PAN, cancelled cheque, registration certificate).

| Step | Actor | Action | State Change |
|------|-------|--------|-------------|
| 1 | Dealer | Uploads via `POST /api/v1/dealer-kyc/documents` | `DealerDocument.created (PENDING)` |
| 2 | Admin | Reviews in admin KYC queue | — |
| 3 | Admin | Approves/rejects each document | `DealerDocument.status → VERIFIED/REJECTED` |

---

### 2.3 Station Setup & Activation

| Step | Actor | Action | State Change |
|------|-------|--------|-------------|
| 1 | Dealer/Admin | Creates station via `POST /api/v1/admin/stations` | `Station.created (approval_status=pending)` |
| 2 | Backend | Creates `StationSlot × N` based on `total_slots` | `StationSlot × N created (empty)` |
| 3 | Admin | Approves station | `Station.approval_status → approved`, `Station.status → active` |
| 4 | Logistics | Batteries delivered and assigned to slots via `StationService.assign_battery_to_slot()` | `StationSlot.battery_id = X`, `Battery.station_id = station_id`, `Station.available_batteries += 1` |
| 5 | IoT | Station heartbeat begins via `StationService.record_heartbeat()` | `StationHeartbeat.created` periodically |

---

### 2.4 Inventory Management & Stock Movement

| Step | Actor | Action | State Change |
|------|-------|--------|-------------|
| 1 | Admin | Creates battery transfer: `InventoryService.create_transfer()` | `BatteryTransfer.created (pending)`, `DealerInventory` updated |
| 2 | Logistics | Manifest created: `LogisticsService.create_manifest()` | `Manifest.created`, `ManifestItem` entries |
| 3 | Driver | Starts trip: `LogisticsService.start_manifest_trip()` | `Manifest.status → in_transit` |
| 4 | Receiver | Confirms receipt: `InventoryService.confirm_receipt()` | `BatteryTransfer.status → completed`, battery location updated |
| 5 | Backend | `InventoryService.log_inventory_change()` → audit trail | `InventoryAuditLog.created` |
| 6 | Backend | `StockMovement.created` for each battery movement | Tracks stock flow |

**Auto-restock trigger**: `LogisticsService.check_and_trigger_restock()` fires when station drops below threshold.

---

### 2.5 Dealer Dashboard: Real-Time Order/Swap Visibility

**What the dealer sees after a customer completes a swap at their station**:

| Data Point | Source | Updated When |
|-----------|--------|-------------|
| Active rental count | `Rental` table, `station_id = dealer's stations` | Rental created/completed |
| Today's swap count | `SwapSession` table, `station_id` filter | Each swap |
| Revenue today | `Transaction` table, linked via swap/rental | Each transaction |
| Commission earned (month) | `CommissionLog` table, `dealer_id` filter | Each commission logged |
| Battery inventory per station | `Station.available_batteries`, `StationSlot` status counts | Each swap/rental/return |
| Station health alerts | `BatteryHealthAlert`, `StationHeartbeat` | IoT telemetry |
| Pending settlement | `Settlement` table, current month | Monthly generation |

---

### 2.6 Commission Accrual & Settlement Payout

| Step | Actor | Action | State Change | Side Effects |
|------|-------|--------|-------------|-------------|
| 1 | (Auto) | On each rental/swap transaction: `CommissionService.calculate_and_log()` | `CommissionLog.created (pending)` | Rate from `CommissionConfig` + `CommissionTier` |
| 2 | Monthly | `SettlementService.generate_monthly_settlement()` → aggregates all pending commissions | `Settlement.created`, all linked `CommissionLog.settlement_id` set | Net payable calculated |
| 3 | Admin | Reviews settlement dashboard | — | — |
| 4 | Admin | Triggers batch payout: `SettlementService.process_batch_payments()` | Each `Settlement.status → paid`, `transaction_reference` set | Bank transfer proof |
| 5 | Backend | `SettlementService.generate_settlement_pdf()` → PDF statement | PDF stored | — |

**Chargeback deduction**: `Settlement.chargeback_amount` deducted from `net_payable`.

---

### 2.7 Dealer Promotions & Campaigns

| Step | Actor | Action | State Change |
|------|-------|--------|-------------|
| 1 | Dealer | Creates promotion via `POST /api/v1/dealers/promotions` | `DealerPromotion.created` |
| 2 | Customer | Applies promo code during rental | `PromotionUsage.created` |
| 3 | Dashboard | Shows promotion performance: redemptions, budget utilization | Aggregated from `PromotionUsage` |

---

### 2.8 Staff Management

| Step | Actor | Action | State Change |
|------|-------|--------|-------------|
| 1 | Dealer | Creates staff member via dealer portal | `StaffProfile.created` linked to `DealerProfile` |
| 2 | Staff | Logs in with delegated permissions | `UserSession.created` with role-scoped access |
| 3 | Staff | Can perform station operations based on assigned role | RBAC-enforced |

---

## 3. Admin / Platform Flows

### 3.1 Admin User & RBAC Management

| Step | Actor | Action | State Change |
|------|-------|--------|-------------|
| 1 | Super Admin | Creates admin user | `AdminUser.created` |
| 2 | Super Admin | Creates role with permissions | `Role.created`, `Permission × N`, `RolePermission × N` |
| 3 | Super Admin | Assigns role to admin | `AdminUserRole.created` |
| 4 | Admin | Logs in → token contains role/permissions | `UserSession.created` |
| 5 | RBAC Middleware | Validates each request against `Permission` table | 403 if insufficient |

---

### 3.2 Customer KYC Queue Review

| Step | Actor | Action | State Change |
|------|-------|--------|-------------|
| 1 | Admin | Views queue: `GET /api/v1/admin/kyc/queue` | Returns users with PENDING KYC |
| 2 | Admin | Reviews each document | — |
| 3 | Admin | Approves/rejects: `POST /api/v1/admin/kyc/{user_id}/verify` | `KYCDocument.status`, `User.kyc_status` updated |
| 4 | Backend | Notification sent to customer | Push notification |

---

### 3.3 Dealer Application Review Pipeline

Full pipeline detailed in [2.1](#21-dealer-application--onboarding). Admin actions at each gate:

| Gate | Admin Action | Model Updated |
|------|-------------|--------------|
| Auto-checks | Review risk score | `DealerApplication` |
| Manual review | Approve/reject application | `DealerApplication`, `KYCStateTransition` |
| Field visit | Schedule + review report | `FieldVisit` |
| Activation | Final activate | `DealerProfile.is_active = true` |

---

### 3.4 Fleet-Wide Battery Lifecycle Management

| Step | Actor | Action | State Change |
|------|-------|--------|-------------|
| 1 | Admin | Registers battery: `BatteryService.create_battery()` | `Battery.created (available)`, `BatteryLifecycleEvent (registered)` |
| 2 | Admin | Assigns to station: `BatteryService.assign_station()` | `Battery.station_id = X`, `location_type = station` |
| 3 | (Runtime) | Battery goes through: available → rented → available → charging → available → maintenance → retired | Each transition logged as `BatteryLifecycleEvent` |
| 4 | Admin | Views health: `BatteryService.calculate_soh()` | State-of-health computed from cycle count + temperature history |
| 5 | Admin | Retires battery: `BatteryService.update_status(RETIRED)` | `Battery.status → retired`, removed from availability pool |
| 6 | Admin | Utilization report: `BatteryService.get_utilization_report()` | Fleet-wide stats |

---

### 3.5 Station Monitoring & Heartbeat

| Step | Actor | Action | State Change |
|------|-------|--------|-------------|
| 1 | IoT/Station | Sends heartbeat every N minutes | `StationHeartbeat.created` |
| 2 | Backend | `StationService.record_heartbeat()` → updates `Station.last_heartbeat` | `Station.last_heartbeat = now` |
| 3 | Admin | Monitors via `GET /api/v1/admin/stations/health` | Returns station status map |
| 4 | Backend | Station missed heartbeat > threshold → `Station.status → OFFLINE` | Alert raised |
| 5 | Admin | `StationDailyMetric` aggregated daily (total swaps, revenue, uptime) | `StationDailyMetric.created` |

---

### 3.6 Fraud Detection & Blacklisting

| Step | Actor | Action | State Change |
|------|-------|--------|-------------|
| 1 | Backend | On auth/payment: `FraudService.check_velocity()` → rate limiting | 429 if exceeded |
| 2 | Backend | On signup/transaction: `FraudService.is_blacklisted()` → checks device/phone/user | Block if matched |
| 3 | Backend | `FraudService.calculate_risk_score()` → composite score | `RiskScore.created/updated` |
| 4 | Admin | Blacklists user: `FraudService.add_to_blacklist()` | `Blacklist.created` |
| 5 | ML | `FraudCheckLog` entries feed ML model training | Historical data |
| 6 | Admin | `DeviceFingerprint` tracking detects multi-accounting | `DuplicateAccount` flagged |

---

### 3.7 Revenue Reporting & Analytics

| Step | Actor | Action | Data Source |
|------|-------|--------|-----------|
| 1 | Admin | Dashboard: `GET /api/v1/admin/dashboard` | Aggregated from Transaction, Rental, User tables |
| 2 | Admin | Revenue report: `GET /api/v1/admin/finance/revenue` | `RevenueReport` + real-time computation |
| 3 | Admin | Export analytics: `GET /api/v1/analytics/export` | CSV with date filters, monthly rollups |
| 4 | Scheduler | `AnalyticsReportJob` scheduled for periodic generation | Pre-computed reports |
| 5 | ML | `DemandForecast`, `ChurnPrediction`, `PricingRecommendation` | ML pipeline outputs |

---

### 3.8 Settlement Approval & Batch Payout

Detailed in [2.6](#26-commission-accrual--settlement-payout). Admin-specific:

| Step | Actor | Action |
|------|-------|--------|
| 1 | Admin | View all settlements: `GET /api/v1/admin/finance/settlements` |
| 2 | Admin | Trigger batch: `POST /api/v1/admin/finance/settlements/process` |
| 3 | Admin | Handle failures: `SettlementService.process_single_payment()` for retries |
| 4 | Admin | View dispute: `SettlementDispute` records |

---

### 3.9 Maintenance Scheduling & Automation

| Step | Actor | Action | State Change |
|------|-------|--------|-------------|
| 1 | Admin | Creates schedule: `MaintenanceService.create_schedule()` | `MaintenanceSchedule.created` (interval-based) |
| 2 | Worker | `MaintenanceService.run_schedule_automation()` auto-generates due records | `MaintenanceRecord.created` for each due schedule |
| 3 | Technician | Completes maintenance: `MaintenanceService.record_maintenance()` | `MaintenanceRecord.completed_at`, `Battery.last_maintenance_date` |
| 4 | Admin | Reports downtime: `MaintenanceService.report_downtime()` | `StationDowntime.created` |
| 5 | Admin | Checklist templates: `MaintenanceChecklistTemplate` + `MaintenanceChecklistSubmission` | Structured inspection data |

---

### 3.10 Notification Campaigns (Push/SMS/WhatsApp)

| Step | Actor | Action | State Change |
|------|-------|--------|-------------|
| 1 | Admin | Creates campaign: `PushCampaign.created` | Campaign with targeting rules |
| 2 | Admin | Sends bulk: `NotificationService.send_bulk_notification()` | `Notification × N created`, dispatched via FCM/SMS/WhatsApp |
| 3 | Backend | Respects `NotificationPreference` + quiet hours | Skipped notifications logged |
| 4 | Backend | `AutomatedTrigger` fires on events (rental overdue, etc.) | Event-driven notifications |
| 5 | Admin | Views delivery stats: `NotificationLog` entries | sent/failed/skipped counts |

---

### 3.11 CMS Management

| Content Type | Model | Admin Action |
|-------------|-------|-------------|
| Banners | `Banner` | CRUD via `/api/v1/admin/cms/banners` |
| Blogs | (Blog model) | CRUD via `/api/v1/admin/cms/blogs` |
| FAQs | `FAQ` | CRUD via `/api/v1/admin/cms/faqs` |
| Legal docs | `LegalDocument` | Terms, privacy policy, refund policy |
| Menus | `Menu` | Navigation structure |

---

### 3.12 Feature Flags & System Configuration

| Step | Actor | Action | State Change |
|------|-------|--------|-------------|
| 1 | Admin | Toggles feature flag via `FeatureFlag` | Runtime feature control |
| 2 | Admin | Updates system config via `SystemConfig` | Platform-wide settings |
| 3 | Backend | `FeatureFlagService.is_enabled()` checked at runtime | Conditional feature execution |

---

## 4. IoT & Hardware Flows

### 4.1 Station Slot Lock/Unlock & Swap Execution

| Step | Actor | Action | Hardware Effect |
|------|-------|--------|----------------|
| 1 | Backend | Swap initiated → slot unlock command via MQTT | `DeviceCommand.created`, MQTT published |
| 2 | Station | Slot mechanism unlocks, customer removes old battery | Slot sensor detects removal |
| 3 | Station | Slot with new battery unlocks, customer takes battery | Slot sensor detects removal |
| 4 | Station | Old battery inserted into charging slot | Slot sensor detects insertion, charging begins |
| 5 | Station | Sends telemetry confirmation back via MQTT | Backend updates `SwapSession.status → completed` |

---

### 4.2 Battery Telemetry Ingestion

| Step | Actor | Action | Data Stored |
|------|-------|--------|------------|
| 1 | IoT device | Sends telemetry via MQTT (SOC, temperature, voltage, current) | — |
| 2 | Backend | `TelematicsIngestService` processes message | `TelemeticsData.created`, `Telemetry.created` |
| 3 | Backend | Updates `Battery.current_charge`, `temperature_c`, `last_telemetry_at` | Real-time battery state |
| 4 | Backend | `BatteryHealthSnapshot` recorded periodically | Health trend data |
| 5 | Backend | If anomaly detected → `BatteryHealthAlert.created` | Alert to admin dashboard |

---

### 4.3 Charging Queue Optimization

| Step | Actor | Action | Result |
|------|-------|--------|--------|
| 1 | Backend | `ChargingService.prioritize_charging()` → SOC-based priority queue | Lowest-SOC batteries charge first |
| 2 | Backend | `ChargingService.reprioritize_queue()` → urgent override | Specific batteries jumped to front |
| 3 | Station | Charging power distributed per priority | Energy cost multiplier applied |

---

### 4.4 BESS (Battery Energy Storage System) Grid Events

| Step | Actor | Action | State Change |
|------|-------|--------|-------------|
| 1 | Grid | Demand signal received | — |
| 2 | Backend | `BessGridEvent.created` → grid interaction logged | `BessUnit` state updated |
| 3 | Backend | `BessEnergyLog` → energy flow recorded (charge/discharge) | kWh tracking |
| 4 | Admin | `BessReport` generated | Performance analytics |

---

## 5. Logistics & Supply Chain Flows

### 5.1 Battery Transfer Between Locations

| Step | Actor | Action | State Change |
|------|-------|--------|-------------|
| 1 | Admin | Creates transfer: `InventoryService.create_transfer()` | `BatteryTransfer.created (pending)` |
| 2 | Backend | `Battery.location_type = transit` | In transit |
| 3 | Receiver | Confirms receipt: `InventoryService.confirm_receipt()` | `BatteryTransfer.status → completed`, `Battery.station_id` updated |

---

### 5.2 Logistics Order & Delivery Tracking

| Step | Actor | Action | State Change |
|------|-------|--------|-------------|
| 1 | Admin | Creates order: `OrderService.create_order()` | `Order.created (pending)`, `OrderBattery × N` |
| 2 | Admin | Assigns driver: `LogisticsService.assign_order()` | `Order.assigned_driver_id = X` |
| 3 | Driver | Starts delivery | `Order.status → in_transit`, `dispatch_date` set |
| 4 | Backend | `DeliveryTracking` + `DeliveryEvent` entries | GPS tracking |
| 5 | Driver | Captures proof of delivery | `Order.proof_of_delivery_url`, `recipient_name` |
| 6 | Backend | `Order.status → delivered` | `delivered_at` set |
| 7 | Backend | `InvoiceService.generate_order_invoice()` → PDF | `Invoice.created` |

---

### 5.3 Reverse Logistics (Returns)

| Step | Actor | Action | State Change |
|------|-------|--------|-------------|
| 1 | Admin | Initiates return: `OrderService.initiate_return()` | `Order.type → return`, `original_order_id` set |
| 2 | Driver | Picks up battery | `Order.status → in_transit` |
| 3 | Warehouse | Receives + inspects | `ReturnInspection.created`, `ReturnRequest.status` updated |
| 4 | Backend | Refund processed if applicable | `Order.refund_status → processed` |

---

### 5.4 Warehouse Rack/Shelf Inventory

| Step | Actor | Action | State Change |
|------|-------|--------|-------------|
| 1 | Admin | Creates warehouse structure: `Warehouse → Rack → Shelf` | Hierarchical storage |
| 2 | Admin | Assigns battery to shelf: `ShelfBattery.created` | Physical location tracked |
| 3 | Admin | Moves battery between locations | `ShelfBattery` updated, `StockMovement.created` |

---

## 6. Financial Flows

### 6.1 End-to-End Cash Flow: Rental → Commission → Settlement

This is the **complete money trail** for a single rental:

```
Customer Wallet (₹500)
    │
    ├─► Rental Payment (₹300)
    │       ├─► Transaction (RENTAL_PAYMENT, success)
    │       ├─► CommissionLog (dealer_id, ₹30 = 10%)
    │       └─► Platform retains ₹270
    │
    ├─► Security Deposit (₹200)
    │       └─► Transaction (SECURITY_DEPOSIT, success)
    │
    ├─► [Swap Fee: ₹50]
    │       ├─► Transaction (SWAP_FEE, success)
    │       └─► CommissionLog (station_dealer_id, ₹5)
    │
    ├─► [Late Fee: ₹25]
    │       └─► Transaction (LATE_FEE, success)
    │
    └─► Return: Deposit Refund (₹200)
            └─► Transaction (credit, refund)

Monthly Settlement:
    CommissionLog (pending) × N  ──►  Settlement.generated
        │
        ├─► total_commission = Σ commissions
        ├─► chargeback_amount = Σ chargebacks
        ├─► platform_fee = X%
        ├─► tax_amount = GST
        └─► net_payable = total - chargebacks - fee - tax
                │
                └─► Bank Transfer → Settlement.status = paid
```

---

### 6.2 Invoice Generation

| Trigger | Service Method | Generated Artifact |
|---------|---------------|--------------------|
| Rental completed | `InvoiceService.generate_rental_invoice()` | PDF with rental details, tax breakdown, HSN code |
| Logistics order delivered | `InvoiceService.generate_order_invoice()` | PDF with order details, battery list, delivery info |
| Settlement paid | `SettlementService.generate_settlement_pdf()` | PDF statement with commission breakdown |

**Invoice Number**: Auto-generated unique `invoice_number` per `Invoice` record.

---

### 6.3 Chargeback Processing

| Step | Actor | Action | State Change |
|------|-------|--------|-------------|
| 1 | Customer/Bank | Disputes a transaction | — |
| 2 | Admin | Creates chargeback: `Chargeback.created` linked to transaction | `Chargeback.status = pending` |
| 3 | Admin | Resolves (accept/reject) | `Chargeback.status → resolved/rejected` |
| 4 | Backend | If accepted: deducted from next settlement | `Settlement.chargeback_amount += X` |

---

## Summary: All Auto-Generated Artifacts

Every flow generates traceable records. Here's the complete list of artifacts that the system creates automatically:

| Artifact | Model | Generated By |
|----------|-------|-------------|
| User ID | `User` | Registration |
| Wallet | `Wallet` | Registration |
| OTP | `OTP` | Auth |
| Session Tokens (JWT) | `UserSession` | Login |
| Login History | `LoginHistory` | Login |
| KYC Documents | `KYCDocument` | KYC upload |
| Reservation ID | `BatteryReservation` | Booking |
| Rental ID | `Rental` | Rental initiation |
| Transaction ID | `Transaction` | Every money movement |
| Invoice + PDF | `Invoice` | Rental completion / order delivery |
| Swap Session ID | `SwapSession` | Battery swap |
| Commission Log | `CommissionLog` | Each rental/swap |
| Settlement + PDF | `Settlement` | Monthly aggregation |
| Battery Lifecycle Events | `BatteryLifecycleEvent` | Every battery state change |
| Rental Events | `RentalEvent` | Every rental state change |
| Audit Log | `AuditLog` | Admin actions |
| Stock Movements | `StockMovement` | Inventory changes |
| Notifications | `Notification` | Every user-facing event |
| Station Heartbeats | `StationHeartbeat` | IoT periodic |
| Telemetry Records | `TelemeticsData` | IoT continuous |
| Device Commands | `DeviceCommand` | Slot lock/unlock |
| Support Tickets | `SupportTicket` | Customer support |
| Referral Codes | `Referral` | Referral program |
| Membership Points | `UserMembership` | Loyalty accrual |

---

## State Machine Reference

### Rental: `pending_payment → active → completed | cancelled | overdue → completed | cancelled`
### Booking: `PENDING → ACTIVE → COMPLETED | CANCELLED | EXPIRED`
### Battery: `available → rented → available → charging → available → maintenance → retired`
### Swap: `initiated → processing → completed | failed`
### Order: `pending → in_transit → delivered | failed | cancelled`
### Settlement: `pending → generated → approved → processing → paid | failed`
### Dealer Application: `SUBMITTED → AUTOMATED_CHECKS_PASSED → KYC_SUBMITTED → MANUAL_REVIEW_PASSED → FIELD_VISIT_SCHEDULED → FIELD_VISIT_COMPLETED → APPROVED → TRAINING_COMPLETED → ACTIVE`
### KYC Document: `PENDING → VERIFIED | REJECTED → (resubmit) → PENDING`
### Refund: `pending → processed | failed`
### Withdrawal: `requested → approved → processed | rejected`
