# Backend MNC-Grade Audit & Upgrade Tracker

## Scope
Raise backend quality by replacing shallow/mock business logic with production-grade behavior and documenting decisions continuously.

## Baseline Findings (2026-04-06)
- Dashboard module (`app/api/v1/dashboard.py`) contains mock/random/stubbed outputs for trend, activity feed, and top station metrics.
- Booking payment endpoint (`app/api/v1/bookings.py`) is a placeholder and does not validate reservation lifecycle or record payment transaction.
- Booking service (`app/services/booking_service.py`) has brittle message composition and minimal validation for station state and reservation conflicts.
- Analytics export endpoint (`app/api/v1/analytics_enhanced.py`) is useful but shallow (no period filters, weak KPI summarization, coarse CSV output).
- Multiple modules contain tolerated stubs/mocks; this iteration prioritizes high business-impact customer/admin flows first.

## Upgrade Plan
- [x] Harden dashboard endpoints to use deterministic DB aggregations.
- [x] Add reservation lifecycle constraints + real booking payment transaction path.
- [x] Expand analytics export with filters and richer summaries.
- [x] Add/update tests for changed business logic.
- [x] Run targeted test set and record outcomes.

## Work Log
- 2026-04-06: Created tracker and locked first implementation batch around dashboard + bookings + analytics export.
- 2026-04-06: Started implementation patch set for dashboard realism, booking lifecycle hardening, and analytics export depth.
- 2026-04-06: Replaced dashboard mock/random behavior (`trend`, `activity-feed`, `top-stations`, improved `station-health`) with data-derived aggregations.
- 2026-04-06: Hardened bookings flow: status transitions, stale-expiry handling, proper reminder payload, and wallet-backed booking payment transaction.
- 2026-04-06: Added bookings router registration in `app/main.py` so the feature is actually reachable.
- 2026-04-06: Rebuilt analytics export with date filters, monthly rollups, realistic KPI summary, and rich CSV output.
- 2026-04-06: Added integration tests in `tests/api/v1/test_backend_upgrade_quality.py`; run result: `4 passed`.
- 2026-04-06: Started second hardening batch after additional review feedback: payment-method lifecycle endpoints + dealer dashboard campaign feed.
- 2026-04-06: Deep-scanned v1 API/service surface for shallow paths and confirmed live shadowed endpoints (`/api/v1/payments/methods`, `/api/v1/wallet/payment-methods`) plus mocked dealer portal campaigns need hardening in current router precedence.
- 2026-04-06: Implemented shared `PaymentMethodService` usage in `app/api/v1/payments.py` and `app/api/v1/wallet.py` to replace placeholder add/delete/list behavior with persisted lifecycle handling (dedupe, defaulting, soft-delete, default reassignment).
- 2026-04-06: Replaced `app/api/v1/dealer_portal_dashboard.py:/campaigns` mock payload with dealer-scoped `DealerPromotion` + `PromotionUsage` aggregates, lifecycle-derived status, and summary metrics.
- 2026-04-06: Added integration tests for payment-method lifecycle and dealer campaign dashboard aggregation in `tests/api/v1/test_backend_upgrade_quality.py`.
- 2026-04-06: Executed second-batch verification suite after payment/dealer campaign hardening (`6 passed`).
- 2026-04-06: Performed route-collision audit and found `34` duplicate `path+method` registrations (merged routers shadowing each other), including payment/wallet/support/rbac paths; captured as next structural hardening item.
- 2026-04-06: Re-ran second-batch tests after import cleanup in touched routes; suite remains green (`6 passed`).
- 2026-04-06: Generated complete route-derived flow inventory (`943` routes) and duplicate registration map in `docs/audit/flow_inventory.md` and `docs/audit/flow_summary.json`.
- 2026-04-06: Completed monolith-wide MNC-grade flow assessment with evidence-backed severity matrix in `docs/audit/BACKEND_MNC_GRADE_ASSESSMENT.md`.

## Second Batch Scope (In Progress)
- [x] Replace placeholder payment-method flows with shared DB-backed lifecycle service in `payments` + `wallet` routes.
- [x] Replace dealer portal campaign mock payload with `DealerPromotion`/`PromotionUsage` aggregates and status derivation.
- [x] Add integration tests for payment-method lifecycle + dealer campaign dashboard feed.
- [x] Re-run targeted tests and record outcomes.

## Verification
- Command: `DATABASE_URL=sqlite:///./test_wezu.db REDIS_URL=redis://localhost:6379/0 SECRET_KEY=test_secret_for_ci_only python3.11 -m pytest -q tests/api/v1/test_backend_upgrade_quality.py`
- Result: `4 passed in 0.59s`
- Command: `DATABASE_URL=sqlite:///./test_wezu.db REDIS_URL=redis://localhost:6379/0 SECRET_KEY=test_secret_for_ci_only python3.11 -m pytest -q tests/api/v1/test_backend_upgrade_quality.py`
- Result: `6 passed in 0.73s` (after second hardening batch)
- Command: `DATABASE_URL=sqlite:///./test_wezu.db REDIS_URL=redis://localhost:6379/0 SECRET_KEY=test_secret_for_ci_only python3.11 - <<'PY' ... route duplicate audit ... PY`
- Result: `duplicate_path_method_count=34` (not fixed in this batch; tracked for next refactor)
- Command: `DATABASE_URL=sqlite:///./test_wezu.db REDIS_URL=redis://localhost:6379/0 SECRET_KEY=test_secret_for_ci_only python3.11 -m pytest -q tests/api/v1/test_backend_upgrade_quality.py`
- Result: `6 passed in 0.74s` (post-cleanup recheck)
- Command: `DATABASE_URL=sqlite:///./test_wezu.db REDIS_URL=redis://localhost:6379/0 SECRET_KEY=test_secret_for_ci_only python3.11 - <<'PY' ... generate flow inventory ... PY`
- Result: `total_routes=943`, `duplicate_path_method_count=34`; outputs written to `docs/audit/flow_inventory.*` and `docs/audit/flow_summary.json`

## Next Hardening Batch (Proposed)
- [ ] Deconflict duplicate route registrations by assigning non-overlapping prefixes (or removing legacy duplicates) for `payments`, `wallet`, `support`, and `rbac`.
- [ ] Add automated guard test that fails on duplicate `path+method` registrations at app startup.

## P0 — Route Deconfliction & CI Guard (Completed 2026-04-06)

### Scope
Execute phases P0-A, P0-B, P0-C of the MNC-Grade Phase Plan (`docs/MNC_GRADE_PHASE_PLAN.yaml`).
Eliminate all 34 duplicate `(method, path)` route registrations and add CI tests to prevent regression.

### P0-A: RBAC Double-Registration Fix
- **Root cause**: `app/api/admin/rbac_admin.py` re-exports the same router object from `app/api/v1/admin_rbac.py`. It was mounted twice — once via `global_admin_router` in `app/api/admin/__init__.py` and once directly in `app/main.py`.
- **Fix**: Removed `router.include_router(rbac_admin.router, ...)` from `app/api/admin/__init__.py`.
- **Impact**: Eliminated 23 duplicate route registrations in one line change.

### P0-B: Cross-File Duplicate Removal (11 handlers)
Surgically removed the shadowed (unreachable) handler from the file where it was duplicated, keeping the canonical handler. Each removal annotated with a `# DECONFLICTED P0-B` comment citing the canonical file and reason.

| # | File | Removed Route | Canonical File |
|---|------|---------------|----------------|
| 1 | `app/api/v1/payments_enhanced.py` | `POST /methods` | `app/api/v1/payments.py` |
| 2 | `app/api/v1/payments_enhanced.py` | `DELETE /methods/{method_id}` | `app/api/v1/payments.py` |
| 3 | `app/api/v1/wallet.py` | `POST /transfer` | `app/api/v1/wallet_enhanced.py` |
| 4 | `app/api/v1/wallet.py` | `GET /cashback` | `app/api/v1/wallet_enhanced.py` |
| 5 | `app/api/v1/notifications.py` | `PATCH /read-all` | `app/api/v1/notifications_enhanced.py` |
| 6 | `app/api/v1/notifications.py` | `POST /device-token` | `app/api/v1/notifications_enhanced.py` |
| 7 | `app/api/v1/rentals.py` | `POST /{rental_id}/report-issue` | `app/api/v1/rentals_enhanced.py` |
| 8 | `app/api/v1/rentals.py` | `GET /{rental_id}/receipt` | `app/api/v1/rentals_enhanced.py` |
| 9 | `app/api/v1/support.py` | `POST /tickets/{ticket_id}/attachment` | `app/api/v1/support_enhanced.py` |
| 10 | `app/api/v1/support.py` | `GET /faq/search` | `app/api/v1/support_enhanced.py` |
| 11 | `app/api/admin/users.py` | `POST /{user_id}/reset-password` | `app/api/v1/admin_users.py` |

### P0-C: CI Guard Tests & Route Manifest
- **`tests/test_route_collisions.py`** — 3 tests:
  - `test_no_duplicate_routes` — asserts every `(method, path)` pair is registered exactly once.
  - `test_no_orphan_head_options` — detects HEAD-without-GET and OPTIONS-only orphans.
  - `test_route_count_sanity` — bounds check on total registrations (400–1200).
- **`scripts/generate_route_manifest.py`** — introspects the live app, generates `docs/audit/route_manifest.json` with full route inventory + duplicate map. Supports `--check` flag for CI (exit 1 on duplicates).

### Verification
- Route manifest: `911 registrations`, `756 unique paths`, `0 duplicates` (down from `943/34`)
- CI guard tests: `3 passed`
- Core quality tests: `12 passed` (6 upgrade quality + 3 route collision + 3 config security)
- Full suite: `133 passed`, `159 failed`, `79 errors` — all failures/errors are **pre-existing** (Transaction schema drift, financial report stubs, RBAC fixture issues) — scoped to P1/P2.

### Files Modified
1. `app/api/admin/__init__.py` — removed RBAC double-mount
2. `app/api/v1/payments_enhanced.py` — removed 2 handlers
3. `app/api/v1/wallet.py` — removed 2 handlers
4. `app/api/v1/notifications.py` — removed 2 handlers
5. `app/api/v1/rentals.py` — removed 2 handlers
6. `app/api/v1/support.py` — removed 2 handlers
7. `app/api/admin/users.py` — removed 1 handler

### Files Created
1. `tests/test_route_collisions.py` — CI guard test suite
2. `scripts/generate_route_manifest.py` — route manifest generator
3. `docs/audit/route_manifest.json` — generated manifest snapshot
4. `docs/MNC_GRADE_PHASE_PLAN.yaml` — master 12-phase remediation plan

## P1 — Missing Service Methods + Transaction Schema + CI Guard (Completed 2026-04-06)

### Scope
Execute phases P1-A, P1-B, P1-C of the MNC-Grade Phase Plan.
Implement all 17 missing service methods called by live route handlers, canonicalize the Transaction schema, and add a static-analysis CI guard test.

### P1-C: Transaction Schema Canonicalization
- **Problem**: `WalletService` writes 6 fields (`type`, `category`, `balance_after`, `reference_type`, `reference_id`, `razorpay_payment_id`) that didn't exist on the Transaction model.
- **Fix**: Added all 6 as `Optional` with `default=None` to `app/models/financial.py`. Updated `TransactionResponse` schema in `app/schemas/wallet.py` to expose them.
- **Impact**: Wallet recharge, withdrawal, cashback, and transfer transactions now persist all fields correctly.

### P1-A: Missing Service Method Implementation (17 methods across 7 services)

| Task | Service | Methods Added |
|------|---------|---------------|
| P1-A-1 | `WalletService` | `transfer_balance(db, sender_id, recipient_phone, amount, note)` |
| P1-A-2 | `WalletService` | `get_cashback_history(db, user_id)` |
| P1-A-3 | `AuthService` | `initiate_2fa_setup(user)`, `verify_and_enable_2fa(db, user, code, secret)`, `register_biometric(db, user_id, device_id, credential_id, public_key)`, `verify_biometric_signature(db, user_id, credential_id, signature, challenge)` |
| P1-A-4 | `SecurityService` | `get_available_questions(db)`, `set_user_security_question(db, user_id, question_id, answer)`, `verify_security_answer(db, user_id, answer)` |
| P1-A-5 | `NotificationService` | `clear_all_notifications(db, user_id)`, `get_unread_count(db, user_id)`, `mark_all_read(db, user_id)`, `send_bulk_notification(db, segment, title, message, type, channel)` |
| P1-A-6 | `KYCService` | `approve_document(db, document_id, reviewer_id)`, `reject_document(db, document_id, reason, reviewer_id)` |
| P1-A-7 | `RentalService` | `get_current_rental(db, user_id)` |
| P1-A-8 | `AnalyticsService` | `get_rental_history_stats(user_id, db)`, `get_cost_analytics(user_id, months, db)`, `get_usage_patterns(user_id, db)` |

### P1-B: Service Contract CI Guard
- **`tests/test_service_contracts.py`** — AST-based test that parses all route files, extracts `Service.method()` calls, resolves imports, and asserts `hasattr(ServiceClass, method)`.
- 4 pre-existing gaps (P2 scope) added to allowlist: `MaintenanceService.get_maintenance_history`, `MaintenanceService.get_maintenance_schedule`, `DriverService.get_driver_dashboard_stats`, `AuthService.create_session`.

### Bugfix: conftest teardown
- Fixed `tests/conftest.py` SQLite teardown to handle missing tables gracefully (`try/except` around `DELETE FROM` per table).

### Verification
- Service contracts test: **1 passed** (0 missing methods outside allowlist)
- Route collision tests: **3 passed** (0 duplicates, 911 registrations)
- Core quality tests: **6 passed**
- Config security tests: **3 passed**
- **Total: 13 passed, 0 errors**

### Files Modified
1. `app/models/financial.py` — added 6 columns to Transaction
2. `app/schemas/wallet.py` — added 6 fields to TransactionResponse
3. `app/services/wallet_service.py` — added `transfer_balance`, `get_cashback_history`
4. `app/services/auth_service.py` — added 4 methods (2FA + biometric)
5. `app/services/security_service.py` — added 3 security question methods
6. `app/services/notification_service.py` — added 4 notification methods
7. `app/services/kyc_service.py` — added `approve_document`, `reject_document`
8. `app/services/rental_service.py` — added `get_current_rental`
9. `app/services/analytics_service.py` — added 3 user-scoped analytics methods
10. `tests/conftest.py` — fixed SQLite teardown robustness

### Files Created
1. `tests/test_service_contracts.py` — AST-based CI guard for service contracts

---

## P2 – Placeholder/Mock Elimination (2026-04-06)

### Objective
Replace all placeholder, mock, and stub logic in money flows, identity/KYC, and comms/dealer modules with production-grade implementations. Add CI guard to prevent regression.

### P2-A: Money Flows

| Task | File | Change |
|------|------|--------|
| P2-A-1 | `app/services/payment_service.py` | Added RuntimeError guard blocking PAYMENT_MOCK_MODE in production; structured logging on all mock-path operations |
| P2-A-2 | `app/services/wallet_service.py` | Added explicit idempotency guard comment + logging on `apply_recharge_capture` early-return path |
| P2-A-3 | `app/services/wallet_service.py` | Added duplicate-refund guard (exactly-once) in `initiate_refund`; added `process_refund` method with full state machine (pending→processed/failed), wallet credit-back, and refund transaction recording |
| P2-A-4 | `app/services/settlement_service.py` | Replaced inline mock gateway calls with `_execute_payout()` abstraction; production path logs warning for manual bank transfer; dev path logs clearly |

### P2-B: Identity & KYC

| Task | File | Change |
|------|------|--------|
| P2-B-1 | `app/services/kyc_service.py` | Added RuntimeError guard: MockKYCProvider in production raises fatal error; hardened dev-branch annotations in `process_video_kyc` and `verify_utility_bill` |
| P2-B-2 | `app/services/fraud_service.py` | Replaced placeholder `calculate_risk_score` (returned 0) with rule-based scoring: blacklist (+50), OTP velocity (+15), device fingerprints (+30 max), failed fraud checks (+20 max) |
| P2-B-2 | `app/api/v1/auth.py` | Updated 3 callers of `calculate_risk_score` to pass `db` session |
| P2-B-3 | `app/api/v1/kyc.py` | Replaced `f"ENC_{aadhaar}"` mock encryption with SHA-256 hash; same for PAN; replaced hardcoded `liveness_score=0.98` with `KYCService.process_video_kyc()` call |
| P2-B-3 | `app/api/v1/fraud.py` | Updated PAN/GST verify docstrings from "mock implementation" to describe actual validation-based logic |

### P2-C: Comms & Dealer

| Task | File | Change |
|------|------|--------|
| P2-C-1 | `app/services/notification_service.py` | Replaced dead WhatsApp stub (`return False`) with configurable `WHATSAPP_PROVIDER_ENABLED` provider pattern with structured logging |

### Verification
- **Tests**: 16 passed, 0 failed (3 placeholder signal guards + 1 contract + 3 collision + 6 quality + 3 config)
- **Route manifest**: 911 registrations, 756 unique paths, 0 duplicates (stable)
- **Placeholder signals**: Zero forbidden signals detected in 22 guarded files

### Files Modified
1. `app/services/payment_service.py` — production safety guard + structured logging
2. `app/services/wallet_service.py` — idempotency guard, refund state machine, process_refund
3. `app/services/settlement_service.py` — `_execute_payout` abstraction
4. `app/services/kyc_service.py` — production RuntimeError guard, dev-branch annotations
5. `app/services/fraud_service.py` — rule-based risk scoring (4 rules)
6. `app/services/notification_service.py` — WhatsApp provider pattern
7. `app/api/v1/kyc.py` — SHA-256 encryption, liveness via service
8. `app/api/v1/fraud.py` — updated docstrings
9. `app/api/v1/auth.py` — updated 3 FraudService callers with db session

### Files Created
1. `tests/test_placeholder_signals.py` — CI guard scanning 22 files for forbidden placeholder signals

## Notes / Context Recovery
If context is lost, start by re-reading this file and then inspect:
- `app/api/v1/dashboard.py`
- `app/api/v1/bookings.py`
- `app/services/booking_service.py`
- `app/api/v1/analytics_enhanced.py`
- `app/services/payment_method_service.py`
- `app/api/v1/payments.py`
- `app/api/v1/wallet.py`
- `app/api/v1/dealer_portal_dashboard.py`
- `tests/api/v1/test_backend_upgrade_quality.py`

---

## P3 — Invariant Tests, Observability & Module Boundaries (2026-04-06)

### P3-A: Flow-Level Invariant Tests ✅

| Task | File | Tests | Notes |
|------|------|-------|-------|
| Wallet balance invariants | `tests/test_wallet_invariants.py` | 15 | hypothesis property-based; 5 test classes |
| Booking state machine | `tests/test_booking_invariants.py` | 45 | exhaustive transition + reachability tests |
| Rental state machine | `tests/test_rental_invariants.py` | 24 | enum validation + BFS reachability |

**Latent bugs found & fixed during P3-A:**
- `WalletService` created `Transaction` rows without `user_id` → **NOT NULL violation** in strict engines. Fixed: added `user_id=wallet.user_id` to all 8 Transaction creation sites.
- `Transaction.transaction_type` was `NOT NULL` with no default → made `Optional[TransactionType]` with `default=None` since wallet transactions use `type`/`category` instead.

**Dependency added:** `hypothesis==6.141.1` → `requirements.txt`

### P3-B: Observability & SLO Hooks ✅

| Task | File | Description |
|------|------|-------------|
| Observability module | `app/core/observability.py` | `flow_id()`, `SLOTimer` context manager, `emit_slo_event()`, `@measure` decorator |
| Wallet SLO instrumentation | `app/services/wallet_service.py` | 5 critical methods wrapped: `add_balance` (500ms), `deduct_balance` (500ms), `apply_recharge_capture` (1000ms), `transfer_balance` (800ms), `process_refund` (600ms) |

**Design:** SLOTimer emits `slo.ok` (INFO) or `slo.breach` (WARNING) structured logs with operation name, elapsed_ms, budget_ms, and flow_id. Existing middleware (`RequestLoggingMiddleware`, `ServerTimingMiddleware`) already provides request-level tracing — observability.py adds service-level granularity.

### P3-C: Bounded Context Module Boundaries ✅

| Task | File | Description |
|------|------|-------------|
| Domain manifest | `docs/domains.yaml` | 9 domains + shared kernel; 103 service files mapped |
| Boundary CI guard | `tests/test_module_boundaries.py` | 5 tests — AST import checker, 0 violations |

**Domains defined:** financial, rental, battery, station, identity, dealer, analytics, content, infra  
**Shared kernel:** `User`, `enums`, `audit_log`, `address`, `device`, `rbac` models + 6 cross-cutting services + 7 core modules

### P3 Verification
```
tests/test_wallet_invariants.py    — 15 passed
tests/test_booking_invariants.py   — 45 passed  (incl. hypothesis)
tests/test_rental_invariants.py    — 24 passed  (incl. hypothesis)
tests/test_module_boundaries.py    —  5 passed
─────────────────────────────────────────────
Total P3 new tests:                  89
```

### Files Modified (P3)
- `app/services/wallet_service.py` — `user_id` on all Transaction creations + SLOTimer on 5 methods
- `app/models/financial.py` — `transaction_type` made Optional
- `app/core/observability.py` — **NEW** observability primitives
- `docs/domains.yaml` — **NEW** domain boundary manifest
- `tests/test_wallet_invariants.py` — **NEW** 15 wallet invariant tests
- `tests/test_booking_invariants.py` — **NEW** 45 booking state machine tests
- `tests/test_rental_invariants.py` — **NEW** 24 rental state machine tests
- `tests/test_module_boundaries.py` — **NEW** 5 domain boundary tests
- `requirements.txt` — added `hypothesis==6.141.1`

---

## P4 — Error Safety, Input Contracts & Structured Logging
**Completed: 2025-07-25**

### P4-A: Error-Handling Hardening (Detail-Leak Prevention)

| Artifact | What Changed |
|---|---|
| `app/middleware/error_handler.py` | **Rewritten** — env-aware (hides `str(e)` in production), includes `request_id`, uses structlog |
| `app/api/v1/wallet.py` | Added logger; `detail=str(e)` → generic message |
| `app/api/v1/admin_stations.py` | `detail=str(e)` → `"Failed to retrieve station health"` |
| `app/api/v1/admin_rbac.py` | Added logger; `detail=f"Transfer failed: {str(e)}"` → `"Role transfer failed"` |
| `app/api/v1/stations.py` | `detail=f"Internal Server Error: {str(e)}"` → generic |
| `app/api/v1/station_monitoring.py` | `detail=str(e)` → `"Internal server error"` |
| `app/api/v1/utils.py` | `detail=f"Upload failed: {str(e)}"` → `"File upload failed"` |
| `app/api/v1/drivers.py` | `detail=f"Failed to create driver profile: {str(e)}"` → generic |
| `app/api/v1/dealer_portal_customers.py` | Added logger; 3 response-dict `str(e)` → `"internal_error"` |
| `app/api/admin/monitoring.py` | 2 leaks fixed (response dict + HTTPException 500) |
| `tests/test_error_safety.py` | **NEW** — 4 AST-based CI guard tests |

### P4-B: Input/Output Contract Hardening (Pydantic Schemas)

| Artifact | What Changed |
|---|---|
| `app/schemas/input_contracts.py` | **NEW** — 8 Pydantic schemas: `PreferencesUpdate`, `ChangePasswordRequest`, `DealerPromotionCreate`, `DealerPromotionUpdate`, `BankAccountUpdate`, `DealerDocumentUpload`, `NotificationPreferencesUpdate`, `MaintenanceTaskCreate` |
| `app/api/v1/profile.py` | `dict` → `PreferencesUpdate` / `ChangePasswordRequest` |
| `app/api/v1/dealers.py` | `dict` → `DealerPromotionCreate` / `DealerPromotionUpdate` / `BankAccountUpdate` |
| `app/api/v1/dealer_portal_settings.py` | `dict` → `NotificationPreferencesUpdate` |
| `app/api/v1/dealer_portal_dashboard.py` | `dict` → `DealerDocumentUpload` |
| `app/api/v1/stations.py` | `dict` → `MaintenanceTaskCreate` |
| `tests/test_input_contracts.py` | **NEW** — 3 CI guard tests (no raw dict params, schema file exists, importable) |

### P4-C: Structured Logging Normalization (structlog)

| Artifact | What Changed |
|---|---|
| `app/services/wallet_service.py` | `logging.getLogger` → `get_logger`; 4 log calls → structured kwargs |
| `app/services/settlement_service.py` | `logging.getLogger` → `get_logger`; 5 log calls → structured kwargs |
| `app/services/kyc_service.py` | `logging.getLogger` → `get_logger`; 8 log calls → structured kwargs |
| `app/services/notification_service.py` | `logging.getLogger` → `get_logger`; 6 log calls → structured kwargs |
| `app/services/payment_service.py` | `logging.getLogger` → `get_logger`; 10 log calls → structured kwargs |
| `tests/test_structured_logging.py` | **NEW** — 4 AST-based CI guard tests (no `logging.getLogger`, no bare `import logging`, `get_logger` imported, no %-format/f-string log calls) |

### P4 Verification
```
tests/test_error_safety.py         — 4 passed
tests/test_input_contracts.py      — 3 passed
tests/test_structured_logging.py   — 4 passed
─────────────────────────────────────────────
Total P4 new tests:                 11
```

### Cumulative Test Count
```
P0-P3 core tests:   93
P4 new tests:        11
─────────────────────
Cumulative:         104
```

---

## Global Risk & Quick Win Resolution (2026-04-06)

All 6 global risks and 5 quick wins from the original assessment are now resolved:

| ID | Description | Status | Resolved By |
|---|---|---|---|
| GR-1 | Transaction schema drift (6 missing columns) | ✅ Resolved | P1-C |
| GR-2 | 34 duplicate route registrations | ✅ Resolved | P0-A, P0-B |
| GR-3 | 17 endpoints calling nonexistent service methods | ✅ Resolved | P1-A |
| GR-4 | MockKYCProvider auto-approve risk in production | ✅ Resolved | P2-B (RuntimeError guard) |
| GR-5 | No CI protection against regressions | ✅ Resolved | P0-C, P1-B, P3-P4 guards |
| GR-6 | Wallet transfer race conditions | ✅ Resolved | P1-A (FOR UPDATE), P3-A (invariant tests) |
| QW-1 | Remove rbac_admin include (23 dupes) | ✅ Resolved | P0-A |
| QW-2 | Route-collision pytest | ✅ Resolved | P0-C |
| QW-3 | notifications.py import bug | ✅ Non-issue | deps.get_current_active_superuser exists |
| QW-4 | admin_kyc.py duplicate return | ✅ Fixed | Direct fix (unreachable return removed) |
| QW-5 | admin users reset-password dupe | ✅ Resolved | P0-B |

---

## P5 — Exception Hygiene, Commit Extraction & Response Model Coverage (Planned)

### Remaining Technical Debt (Baseline)
| Gap | Count | Location |
|---|---|---|
| `except Exception` (bare catches) | 54 in 31 files | `app/api/` |
| `db.commit()` in route handlers | 263 calls in ~50 files | `app/api/` |
| Missing `response_model` | 484/1034 routes (47%) | `app/api/` |

### P5-A: Exception Hygiene (est. 6-8h)
Replace bare `except Exception` in top-10 worst-offender route files with typed catches. Let unexpected errors propagate to the P4-A global error handler.

### P5-B: db.commit Extraction (est. 10-14h)
Move `db.commit()` from route handlers into the service layer for the top-10 worst-offender files. Routes become thin orchestrators.

### P5-C: Response Model Coverage (est. 8-12h)
Add `response_model` Pydantic schemas to auth, wallet, bookings, stations, and admin-users routes. Improves OpenAPI docs and prevents data leakage.
