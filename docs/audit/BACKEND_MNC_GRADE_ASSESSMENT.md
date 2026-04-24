# Backend MNC-Grade Flow Assessment (2026-04-06)

## 1) Inventory: What Flows Exist

This backend is a large merged monolith with route-derived inventory generated from the running FastAPI app:

- Total registered routes (method+path): **943**
- Unique paths: **755**
- Duplicate `path+method` registrations: **34**
- Flow inventory source: `docs/audit/flow_inventory.md`
- Machine-readable inventory: `docs/audit/flow_inventory.json`
- Summary and duplicates list: `docs/audit/flow_summary.json`

### Major Flow Families (Grouped)

- Identity & Access: **168 routes**
- KYC & Fraud: **32 routes**
- Fleet & Rentals: **106 routes**
- Payments & Wallet: **71 routes**
- Commerce & Catalog: **51 routes**
- Dealer Platform: **128 routes**
- Logistics & Operations: **84 routes**
- Comms & Support: **39 routes**
- Admin Ops & Monitoring: **152 routes**
- IoT & Telematics: **14 routes**

## 2) Does It Work Correctly? (Current State)

### Overall Verdict

The codebase has valuable breadth but is **not uniformly MNC-grade yet**.  
It behaves like a merged monolith with partial overlap between legacy and enhanced modules, causing runtime drift and correctness risk.

### Critical Findings (Break / Incorrect Behavior)

1. Duplicate route registrations cause handler shadowing and ambiguity.
- Evidence: `34` duplicates in `docs/audit/flow_summary.json`.
- Most affected: `admin/rbac` (23), plus `payments`, `wallet`, `notifications`, `rentals`, `support`.
- Example: same `POST /api/v1/payments/methods` is registered in both `app/api/v1/payments.py` and `app/api/v1/payments_enhanced.py`.

2. Wallet/payment data model mismatch (high runtime risk).
- `Transaction` model does **not** define fields such as `type`, `category`, `balance_after`, `reference_type`, `reference_id`, `razorpay_payment_id`:
  - See `app/models/financial.py` (`Transaction` fields).
- But these are used in live code:
  - `app/services/wallet_service.py` (e.g., lines creating `Transaction` with those fields).
  - `app/api/v1/wallet_enhanced.py` (`Transaction.category` filters and write fields).
  - `app/api/v1/payments_enhanced.py` (`transaction.type`, `transaction.category` in receipt response).

3. Live routes call service methods that do not exist.
- Wallet:
  - `app/api/v1/wallet.py:138` calls `WalletService.transfer_balance(...)` (missing).
  - `app/api/v1/wallet.py:152` calls `WalletService.get_cashback_history(...)` (missing).
- Auth/Security:
  - `app/api/v1/auth.py` calls missing methods such as `AuthService.initiate_2fa_setup`, `verify_and_enable_2fa`, `register_biometric`, `verify_biometric_signature`.
  - Also calls missing `SecurityService.get_available_questions`, `set_user_security_question`, `verify_security_answer`.
- Admin KYC:
  - `app/api/v1/admin_kyc.py` calls missing `KYCService.approve_document` / `reject_document`.
- Notifications:
  - `app/api/v1/notifications.py` calls missing `NotificationService.clear_all_notifications`, `get_unread_count`, `mark_all_read`, `send_bulk_notification`.
- Rentals:
  - `app/api/v1/rentals.py:103` calls missing `RentalService.get_current_rental(...)`.

4. Customer analytics endpoints depend on non-implemented service APIs.
- `app/api/v1/analytics.py` calls:
  - `AnalyticsService.get_rental_history_stats(...)`
  - `AnalyticsService.get_cost_analytics(...)`
  - `AnalyticsService.get_usage_patterns(...)`
- Those methods are not implemented in `app/services/analytics_service.py`.

5. Placeholder/mock logic still present in multiple business areas.
- Placeholder signals found in **72 files** across `app/api/v1`, `app/api/admin`, `app/services`.
- Includes fraud/kyc/logistics/settlement/admin monitoring and others.

### What Is Improved / Working Better (from current hardening work)

- Admin dashboard data endpoints now DB-driven instead of random/mock in key paths.
- Booking lifecycle and booking payment path upgraded with wallet transaction recording.
- Payment method lifecycle now DB-backed across wallet/payments routes.
- Dealer portal campaigns endpoint now uses real promotion/usage aggregates.
- Targeted regression suite for these hardened flows currently passes.

## 3) MNC-Grade Scorecard by Flow Family

Legend: `Green` (strong), `Amber` (partially strong), `Red` (structural correctness risk)

- Identity & Access: **Amber/Red**
  - Strengths: broad auth/session surface.
  - Risks: missing auth/security service methods called by live endpoints.

- KYC & Fraud: **Red**
  - Risks: admin KYC endpoints call unimplemented service methods; fraud path has mock implementations.

- Fleet & Rentals: **Amber**
  - Strengths: booking hardening and tests added.
  - Risks: rentals endpoint references missing `get_current_rental`; duplicate rental endpoints.

- Payments & Wallet: **Red**
  - Strengths: payment-method lifecycle hardened.
  - Risks: model-schema drift in transaction fields + duplicate route handlers + wallet service method gaps.

- Commerce & Catalog: **Amber**
  - Broad functionality exists; requires deeper business-rule and idempotency audit.

- Dealer Platform: **Amber**
  - Strengths: campaigns feed no longer mocked.
  - Risks: several dealer subflows still rely on placeholders/mocks.

- Logistics & Operations: **Amber/Red**
  - Risks: mocked route snippets and partial placeholders in operational paths.

- Comms & Support: **Red**
  - Risks: live notification endpoints call service methods not implemented; duplicate support/notification routes.

- Admin Ops & Monitoring: **Amber**
  - Strengths: rich route coverage.
  - Risks: duplicate RBAC routes and monitoring endpoints with mocked metrics.

- IoT & Telematics: **Amber**
  - Core routes exist; deeper reliability and command delivery correctness needs dedicated validation.

## 4) Intelligent Solutions (Recommended)

1. Route Manifest Governance (highest leverage).
- Add startup guard test to fail build on duplicate `method+path`.
- Generate `route_manifest.json` in CI and diff against baseline to catch accidental overlaps.
- Keep only one owner router per path.

2. Service Contract Guardrails.
- Add static contract test: every `XService.some_method(...)` called by route modules must exist.
- Fail CI on missing method references (already detected multiple).

3. Canonical Financial Schema + Compatibility Layer.
- Define one authoritative `Transaction` schema and migration plan.
- Introduce compatibility adapter for legacy code paths until all references use canonical fields.
- Enforce typed DTOs at route boundary to prevent ad-hoc field drift.

4. Flow-Level Invariant Engine.
- Codify invariants for money and lifecycle flows:
  - no negative wallet unless explicit overdraft flag
  - idempotent recharge capture by gateway reference
  - exactly-once refund state transitions
  - reservation/rental state machine constraints
- Add property-based tests for these invariants.

5. Bounded Context Modularization (without full rewrite).
- Split monolith into clear internal domains (auth, wallet/payments, fleet/rentals, dealer, logistics, admin) with stable interfaces.
- Keep a modular monolith first; avoid premature microservices.

6. Production-Grade Observability and SLOs.
- Add request tracing and flow IDs to payment/rental/dealer critical paths.
- Define SLOs per core flow (p95 latency, error rate, reconciliation lag, settlement success rate).
- Add alerting tied to business KPIs, not only infra metrics.

7. Test Strategy Upgrade.
- Current route surface: 943; unique tested literal method-paths are far lower.
- Adopt risk-based flow test matrix:
  - P0: wallet/payment/refund/booking/rental transitions/admin auth.
  - P1: dealer campaign/settlement/logistics dispatch.
  - P2: content/FAQ/read-only analytics.

## 5) Practical Next Steps (Execution Order)

1. Deconflict duplicate routes (start with payments/wallet/notifications/support/rentals/admin-rbac).
2. Fix missing service-method gaps in loaded routes (auth, security, wallet, notifications, rentals, admin KYC).
3. Resolve `Transaction` schema drift and migrate impacted code paths.
4. Add CI guards: duplicate-route check + service-contract check.
5. Expand P0 end-to-end tests for money and identity flows before adding more features.
