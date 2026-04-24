# WEZU Backend — Comparison & Merge Plan

> **Date:** April 6, 2026
> **Repos:** `wezu-backend` (hardened) vs `wezu-backend-laxman` (feature-rich)
> **Goal:** Combine the strongest parts of each into a single production-ready, modularizable backend.

---

## 1. High-Level Stats

| Metric | `wezu-backend` (Hardened) | `wezu-backend-laxman` (Laxman) | Winner |
|--------|:-------------------------:|:------------------------------:|:------:|
| Total Python files (app/) | **337** | **501** | Laxman (more features) |
| Files only in this repo | 68 | 232 | — |
| Common files | 269 | 269 | — |
| API route files | ~60 | ~90 | Laxman |
| Service files | ~79 | ~85 | Comparable |
| Model files | ~55 | ~80+ | Laxman |
| Schema files | ~30 | ~75+ | Laxman |
| Test files | **0** (no tests/ dir) | **80+** tests | **Laxman** |
| Background workers | 7 (incl. event_stream) | 6 + 4 tasks | Hardened (infra) |

---

## 2. Component-by-Component Comparison

### 2.1 Configuration (`app/core/config.py`)

| Aspect | Hardened | Laxman | Stronger |
|--------|----------|--------|----------|
| Lines | 438 | 249 | **Hardened** |
| Required env vars (no defaults) | `SECRET_KEY` only | `SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `MONGODB_URL` | **Laxman** (fail-fast) |
| Production safety enforcement | `ENFORCE_PRODUCTION_SAFETY` flag + `_validate_production_safety()` in main.py | `_validate_production_secrets` model validator | **Hardened** (more thorough) |
| Event stream settings | ✅ Full Redis Streams config (telematics, webhooks, notifications, outbox) | ❌ None | **Hardened** |
| Passkey / WebAuthn config | ✅ Full PASSKEY_* settings | ❌ None | **Hardened** |
| Fraud compute config | ✅ Circuit breaker settings | ❌ None | **Hardened** |
| Background runtime mode | ✅ `auto\|api_only\|workers_only` + leader lock | Basic `RUN_BACKGROUND_TASKS` + `SCHEDULER_ENABLED` | **Hardened** |
| Audit queue settings | ❌ None | ✅ `AUDIT_REQUEST_*` settings (queue, batch, flush) | **Laxman** |
| MongoDB config | ❌ None | ✅ `MONGODB_URL`, `MONGODB_DB` | **Laxman** |
| CORS validation | Basic list parse | ✅ Rejects `*` with credentials, auto-adds admin frontend origin, regex localhost | **Laxman** |
| Database URL normalization | ✅ Strips `search_path` from query, fixes `postgres://` → `postgresql://` | ❌ None | **Hardened** |
| Allowed hosts normalization | ✅ Strips ports, URLs, deduplicates, lowercases | ❌ Basic list | **Hardened** |
| Structured logging config | Basic | ✅ `SQLALCHEMY_ECHO`, `LOG_ACCESS_LOGS`, `LOG_REQUESTS`, `LOG_HEALTHCHECKS`, `LOG_SLOW_REQUEST_THRESHOLD_MS` | **Laxman** |
| Cache TTL granularity | ✅ Extremely granular per-feature TTLs | Basic per-domain TTLs | **Hardened** |

**Verdict:** Take the Hardened config as the base. Add Laxman's required env vars (no defaults for DATABASE_URL, REDIS_URL), CORS validation logic, MongoDB config, audit queue settings, and structured logging toggles.

---

### 2.2 Database (`app/core/database.py`)

| Aspect | Hardened (90 LOC) | Laxman (43 LOC) | Stronger |
|--------|-------------------|------------------|----------|
| Search path safety | ✅ `SET search_path TO public` on every connect | ❌ None | **Hardened** |
| Slow query logging | ✅ `SQL_SLOW_QUERY_LOG_MS` threshold with timing events | ❌ None | **Hardened** |
| SQLite fallback | ❌ None | ✅ NullPool + WAL pragma for dev/test | **Laxman** |
| LIFO pool | ❌ No | ✅ `pool_use_lifo=True` | **Laxman** |
| SSL mode support | ✅ `DATABASE_SSL_MODE` in connect_args | ❌ None | **Hardened** |
| Connect timeout | ✅ `DATABASE_CONNECT_TIMEOUT_SECONDS` | ❌ None | **Hardened** |

**Verdict:** Use Hardened as base. Add SQLite fallback logic and LIFO pool option from Laxman.

---

### 2.3 Security (`app/core/security.py`)

| Aspect | Hardened (65 LOC) | Laxman (76 LOC) | Stronger |
|--------|-------------------|------------------|----------|
| UTC-aware timestamps | ❌ `datetime.utcnow()` (deprecated) | ✅ `datetime.now(UTC)` | **Laxman** |
| Extra claims on access token | ❌ No | ✅ `extra_claims` parameter | **Laxman** |
| Custom JTI on refresh token | ❌ Auto-generated only | ✅ `jti` parameter | **Laxman** |
| TOTP verify window | ✅ `valid_window=1` (30-sec tolerance) | ❌ Strict (no tolerance) | **Hardened** |
| TOTP null safety | ✅ Null checks on secret/code | ❌ No null checks | **Hardened** |
| QR URI generation | ✅ Manual string construction | ✅ Uses `pyotp.provisioning_uri()` | **Laxman** (cleaner) |
| `verify_permission` helper | ❌ None | ✅ Permission check utility | **Laxman** |

**Verdict:** Use Laxman as base (UTC-aware, extra claims, verify_permission). Add Hardened's TOTP null safety and valid_window.

---

### 2.4 Middleware

| Middleware | Hardened | Laxman | Stronger |
|-----------|----------|--------|----------|
| **Rate limiting** | ✅ Proxy-aware key extraction, Redis fallback to memory, configurable storage URL | Basic Redis URL, no fallback | **Hardened** |
| **Proxy host rewrite** | ✅ Full RFC 7239 parsing, trusted CIDR validation, Host header rewrite | Basic `TrustedProxyHeadersMiddleware` | **Hardened** |
| **Server timing** | ✅ `Server-Timing` header for browser waterfall | ❌ None | **Hardened** |
| **Secure headers** | ❌ None (relies on reverse proxy) | ✅ CSP, HSTS, X-Frame-Options, X-XSS-Protection | **Laxman** |
| **RBAC middleware** | ❌ None (auth in deps only) | ✅ Pre-resolves user + role on every request | **Laxman** |
| **Request logging** | ❌ None | ✅ Structlog, request-id, correlation-id, slow request warnings | **Laxman** |
| **Audit middleware** | ❌ None | ✅ Async audit queue with batch MongoDB writes | **Laxman** |
| **Error handler** | ✅ Basic with DEBUG toggle | ✅ Same | Comparable |

**Verdict:** Need ALL of them. Merge Hardened's rate_limit, proxy_host, server_timing WITH Laxman's security, rbac, request_logging, audit.

---

### 2.5 Proxy IP Resolution (`app/core/proxy.py`)

| Aspect | Hardened | Laxman | Stronger |
|--------|----------|--------|----------|
| Lines | ~100 | ~170 | Laxman (more complete) |
| Trusted CIDR check | ✅ Configurable `TRUSTED_PROXY_CIDRS` | ✅ Configurable `FORWARDED_ALLOW_IPS` | Comparable |
| X-Forwarded-For parsing | ✅ With IPv6, port stripping | ✅ With IPv6, port stripping | Comparable |
| RFC 7239 `Forwarded` header | ✅ Full regex parsing | ✅ Manual token parsing | **Hardened** |
| `X-Real-IP` fallback | ✅ | ✅ | Comparable |
| Host header rewriting | ❌ (in middleware) | ✅ `get_forwarded_host()`, `rewrite_host_header()`, host validation | **Laxman** |
| Request-level caching | ❌ | ✅ `request.state.client_ip` caching | **Laxman** |
| Host header validation | ❌ | ✅ `_normalize_host()` with DNS label checks | **Laxman** |

**Verdict:** Use Laxman's proxy.py as the base (more complete, request-caching, host rewriting). Port Hardened's regex-based Forwarded header parsing.

---

### 2.6 Logging (`app/core/logging.py`)

| Aspect | Hardened | Laxman | Stronger |
|--------|----------|--------|----------|
| Library | stdlib `logging` + custom `JsonFormatter` | ✅ **structlog** + stdlib bridge | **Laxman** |
| JSON output | ✅ Custom formatter | ✅ structlog JSONRenderer (production) | **Laxman** (industry standard) |
| Dev mode rendering | ❌ Always JSON | ✅ `ConsoleRenderer` for dev | **Laxman** |
| Context variables | ❌ None | ✅ `contextvars` (request-id, correlation-id) | **Laxman** |
| Healthcheck filtering | ❌ None | ✅ `_HealthcheckAccessFilter` | **Laxman** |
| `get_logger()` helper | ❌ None | ✅ Returns `BoundLogger` | **Laxman** |

**Verdict:** Use Laxman's structlog-based logging. It's strictly superior.

---

### 2.7 Main Application (`app/main.py`)

| Aspect | Hardened (399 LOC) | Laxman (428 LOC) | Stronger |
|--------|-------------------|------------------|----------|
| Production safety validation | ✅ `_validate_production_safety()` — checks OTP bypass, API docs, hosts, CORS, secret key, DB URL, service tokens | ❌ None at startup | **Hardened** |
| Graceful degraded startup | ✅ `ALLOW_START_WITHOUT_DB`, catches SQLAlchemyError, continues in degraded mode | Basic | **Hardened** |
| Startup diagnostics | ✅ `StartupDiagnosticsService.enforce_required_dependencies()` | ❌ None | **Hardened** |
| Background runtime modes | ✅ `BackgroundRuntimeService` (leader election, mode detection) | Basic `if` checks | **Hardened** |
| WebSocket/Outbox startup | ✅ `websocket_manager.start_order_pubsub_listener()` | ✅ `heartbeat_task()` | Both |
| Crash loop prevention | ✅ `asyncio.sleep(10)` on fatal startup error | ❌ Crashes immediately | **Hardened** |
| Sentry integration | ❌ None in main.py | ✅ `sentry_sdk.init()` with FastAPI integration | **Laxman** |
| Router organization | Flat, all in main.py with comments | ✅ Grouped by actor (Customer/Admin/Dealer/Logistics) with admin dependencies | **Laxman** |
| Admin route dependencies | ❌ Per-endpoint | ✅ `dependencies=[Depends(get_current_active_admin)]` at router level | **Laxman** |
| CORS error middleware | ❌ None | ✅ `CORSErrorMiddleware` + global OPTIONS handler | **Laxman** |
| Readiness probe depth | ✅ Checks DB, Redis, payment, SMS, email, fraud, scheduler, event streams, notification outbox, background runtime | ✅ Checks DB, Redis, MongoDB | **Hardened** |
| Schema guard | ✅ `validate_logistics_schema()` | ❌ None | **Hardened** |
| Passkey endpoints | ✅ `.well-known/assetlinks.json` for Android | ❌ None | **Hardened** |
| Alembic auto-migration | ❌ None | ✅ `DB_INIT_ON_STARTUP` runs `alembic upgrade head` | **Laxman** |
| Trusted Host middleware | ✅ Always on with derived public hosts | ✅ Toggle `ENABLE_TRUSTED_HOST_MIDDLEWARE` | **Hardened** (safer default) |

**Verdict:** Merge both. Hardened's startup safety/diagnostics/degraded mode + Laxman's router organization/Sentry/CORS handling.

---

### 2.8 Services (Unique to Each)

#### Only in Hardened (Infrastructure/Operational):
| Service | Purpose | LOC | Keep? |
|---------|---------|-----|-------|
| `startup_diagnostics_service` | Deep production readiness checks | 311 | ✅ **Yes** — critical for production |
| `background_runtime_service` | Leader election for scheduler | 257 | ✅ **Yes** — prevents duplicate jobs |
| `distributed_cache_service` | Redis cache with stale-while-revalidate + distributed locks | 230 | ✅ **Yes** — superior to simple cache |
| `event_stream_service` | Redis Streams consumer/producer with DLQ | 220 | ✅ **Yes** — async event processing |
| `notification_outbox_service` | Transactional outbox for notifications | 371 | ✅ **Yes** — guaranteed delivery |
| `idempotency_service` | Request idempotency with fingerprinting | ~130 | ✅ **Yes** — payment safety |
| `redis_service` | Centralized Redis client factory | 73 | ✅ **Yes** — single connection management |
| `bootstrap_service` | Service bootstrapping/initialization | 311 | ✅ **Yes** |
| `fraud_compute_service` | External fraud scoring with circuit breaker | 87 | ✅ **Yes** |
| `passkey_service` | WebAuthn passkey auth | ~100 | ✅ **Yes** |
| `razorpay_webhook_service` | Razorpay webhook handling | ~100 | ✅ **Yes** |
| `telematics_ingest_service` | Stream-based telematics ingestion | ~100 | ✅ **Yes** |
| `battery_consistency` | Battery data consistency checks | ~50 | ✅ **Yes** |
| `analytics_dashboard_service` | Dashboard analytics + caching | ~100 | ✅ **Yes** |
| `analytics_report_service` | Report generation | ~100 | ✅ **Yes** |
| `station_metrics_service` | Station performance metrics | ~100 | ✅ **Yes** |
| `workflow_automation_service` | Automated workflow triggers | ~100 | ✅ **Yes** |

#### Only in Laxman (Business Domain):
| Service | Purpose | LOC | Keep? |
|---------|---------|-----|-------|
| `request_audit_queue` | Async audit log queue (MongoDB) | 192 | ✅ **Yes** — non-blocking audit |
| `settlement_service` | Financial settlements | 396 | ✅ **Yes** — dealer settlements |
| `financial_report_service` | Financial reporting | 366 | ✅ **Yes** — admin reports |
| `booking_service` | Battery bookings | 132 | ✅ **Yes** — customer booking flow |
| `logistics_service` | Battery transfers | 232 | ✅ **Yes** — logistics operations |
| `inventory_service` | Stock/inventory management | ~150 | ✅ **Yes** |
| `password_service` | Password history/validation | 86 | ✅ **Yes** — security hardening |
| `dealer_kyc_service` | Dealer KYC processing | ~100 | ✅ **Yes** |
| `dealer_ledger_service` | Dealer financial ledger | ~100 | ✅ **Yes** |
| `dealer_station_service` | Dealer station management | ~100 | ✅ **Yes** |
| `dealer_analytics_service` | Dealer-specific analytics | ~100 | ✅ **Yes** |
| `campaign_service` | Dealer campaigns | ~100 | ✅ **Yes** |
| `charging_service` | Battery charging management | ~100 | ✅ **Yes** |
| `dispute_service` | Settlement disputes | ~100 | ✅ **Yes** |
| `alert_service` | System alerts | ~100 | ✅ **Yes** |
| `admin_analytics_service` | Admin analytics | ~100 | ✅ **Yes** |
| `user_state_service` | User state machine | ~100 | ✅ **Yes** |
| `membership_service` | Customer memberships | ~100 | ✅ **Yes** |
| `receipt_service` | Receipt generation | ~100 | ✅ **Yes** |
| `rental_alert_service` | Rental notifications | ~100 | ✅ **Yes** |
| `demand_predictor` | Demand forecasting | ~100 | ✅ **Yes** |
| Analytics module (`services/analytics/`) | Per-actor analytics | ~500 | ✅ **Yes** |

**Verdict:** Keep ALL unique services from both sides. There is zero overlap — Hardened has infrastructure, Laxman has business domain.

---

### 2.9 Common Services — Which Version is Stronger?

Services where BOTH repos have the file, but with different implementations:

| Service | Hardened LOC | Laxman LOC | Stronger | Notes |
|---------|:-----------:|:----------:|----------|-------|
| `rental_service.py` | **811** | 291 | **Hardened** | 3x larger, enhanced workflows |
| `notification_service.py` | **535** | 140 | **Hardened** | Multi-channel, outbox integration |
| `websocket_service.py` | **527** | 183 | **Hardened** | Order pubsub, realtime outbox |
| `wallet_service.py` | **479** | 312 | **Hardened** | Enhanced transactions |
| `analytics_service.py` | 116 | **1623** | **Laxman** | 14x larger, full analytics engine |
| `auth_service.py` | 237 | **480** | **Laxman** | 2x, more auth flows |
| `audit_service.py` | 43 | **213** | **Laxman** | Full audit system |
| `station_service.py` | 207 | **297** | **Laxman** | More station features |
| `battery_service.py` | 58 | **257** | **Laxman** | Richer battery management |
| `mqtt_service.py` | **342** | 306 | **Hardened** | More robust connection handling |
| `order_service.py` | 279 | **335** | **Laxman** | More order workflows |
| `maintenance_service.py` | **403** | 123 | **Hardened** | Comprehensive maintenance |
| `qr_service.py` | **338** | 84 | **Hardened** | Signed QR codes |
| `gps_service.py` | 260 | **267** | Comparable | |
| `catalog_service.py` | 228 | **304** | **Laxman** | E-commerce catalog |
| `otp_service.py` | **217** | 194 | **Hardened** | Better error handling |
| `swap_service.py` | **224** | 197 | **Hardened** | |
| `kyc_service.py` | 98 | **183** | **Laxman** | More KYC flows |
| `dealer_service.py` | 133 | **222** | **Laxman** | Richer dealer ops |
| `late_fee_service.py` | 138 | **200** | **Laxman** | |
| `support_service.py` | 57 | **170** | **Laxman** | Full ticketing |
| `user_service.py` | 58 | **167** | **Laxman** | User lifecycle |
| `rbac_service.py` | 113 | **151** | **Laxman** | More RBAC features |
| `commission_service.py` | 53 | **108** | **Laxman** | |
| `fcm_service.py` | **113** | 47 | **Hardened** | Better push notifications |
| `geofence_service.py` | **112** | 42 | **Hardened** | Advanced geofencing |
| `iot_service.py` | 222 | **218** | Comparable | |
| `security_service.py` | **87** | 65 | **Hardened** | |
| `maps_service.py` | **72** | 26 | **Hardened** | Google Maps integration |
| `storage_service.py` | **84** | 31 | **Hardened** | S3 + local storage |
| `sms_service.py` | **73** | 15 | **Hardened** | Multi-provider SMS |
| `email_service.py` | **55** | 33 | **Hardened** | SendGrid integration |

---

### 2.10 Models (Unique to Each)

#### Only in Hardened:
- `idempotency.py` — Idempotency key tracking
- `passkey.py` — WebAuthn credentials
- `order.py`, `order_realtime_outbox.py` — Logistics orders + realtime outbox
- `manifest.py` — Delivery manifests
- `analytics_dashboard.py` — Dashboard snapshots
- `station_metrics.py` — Station performance metrics
- `notification_outbox.py` — Notification delivery tracking
- `inventory.py` — Warehouse inventory
- `payment_method.py` — Saved payment methods
- `telematics.py` — Raw telematics data

#### Only in Laxman (35 additional models):
- `admin_group.py`, `roles.py`, `password_history.py`, `login_history.py`, `security_question.py`, `api_key.py` — **Security & RBAC**
- `banner.py`, `blog.py`, `legal.py`, `media.py`, `feedback.py` — **CMS/Content**
- `bess.py`, `battery_health.py`, `battery_reservation.py`, `charging_queue.py` — **Battery Management**
- `cart.py`, `membership.py` — **E-commerce**
- `station_stock.py`, `stock.py`, `stock_movement.py`, `station_heartbeat.py`, `inventory_audit.py` — **Inventory/Stock**
- `dealer_kyc.py`, `chargeback.py`, `settlement_dispute.py`, `revenue_report.py` — **Financial**
- `logistics.py`, `maintenance_checklist.py` — **Operations**
- `notification_admin.py`, `alert.py`, `telemetry.py` — **System**
- `enums.py`, `all.py`, `user_profile.py`, `user_history.py` — **Core utilities**

**Verdict:** Keep ALL models from both. Zero conflict — they cover different domains.

---

### 2.11 Docker & Deployment

| Aspect | Hardened | Laxman | Stronger |
|--------|----------|--------|----------|
| Multi-stage build | ❌ Single stage | ✅ Builder + runtime (smaller image) | **Laxman** |
| Non-root user | ❌ Runs as root | ✅ `wezu_user` | **Laxman** |
| Security options | ❌ None | ✅ (Hardened docker-compose has `no-new-privileges`) | **Hardened** (compose) |
| Gunicorn config | ✅ Separate `gunicorn_conf.py` with env vars, worker_tmp_dir, preload control | ✅ Inline CMD with env substitution | **Hardened** |
| Healthcheck | ✅ `curl` based | ✅ Python-based (no curl needed) | **Laxman** (fewer deps) |
| Docker Compose | ✅ Redis + web, required secrets | ✅ Redis + API + optional local DB, resource limits | **Laxman** (more complete) |
| `.dockerignore` | ✅ | ❌ | **Hardened** |

**Verdict:** Use Laxman's multi-stage Dockerfile with non-root user. Add Hardened's `gunicorn_conf.py`, `.dockerignore`, and `no-new-privileges`. Merge docker-compose with best of both.

---

### 2.12 Tests

| Aspect | Hardened | Laxman | Stronger |
|--------|----------|--------|----------|
| Test directory | ❌ **Does not exist** | ✅ **80+ test files** | **Laxman** |
| Coverage areas | — | Auth, RBAC, KYC, audit, analytics, dealer, admin, roles, permissions, sessions, financial | **Laxman** |
| conftest.py | — | ✅ Shared fixtures, DB session, test user factories | **Laxman** |

**Verdict:** Use Laxman's entire test suite. No tests to merge from Hardened.

---

## 3. Strength Summary

### Hardened (`wezu-backend`) is stronger in:
1. **Production safety gates** — startup validation, diagnostics, degraded mode
2. **Infrastructure services** — distributed cache, event streams, outbox, leader election, idempotency
3. **Core service implementations** — rental (811 LOC), notification (535 LOC), websocket (527 LOC), wallet (479 LOC), QR (338 LOC)
4. **Rate limiting** — proxy-aware, Redis with memory fallback
5. **Proxy/host handling** — RFC 7239, trusted CIDR
6. **Gunicorn configuration** — separate config file with all knobs
7. **Config granularity** — per-feature cache TTLs, event stream tuning
8. **Passkey/WebAuthn** — full flow with Android asset links
9. **Database hardening** — search_path safety, slow query logging, SSL, connect timeout

### Laxman (`wezu-backend-laxman`) is stronger in:
1. **Business domain coverage** — 232 additional files covering admin, dealer, logistics, analytics, CMS, e-commerce
2. **Structured logging** — structlog with request-id, correlation-id, slow request detection
3. **Middleware stack** — secure headers, RBAC middleware, request logging, audit middleware
4. **Test suite** — 80+ tests covering RBAC, auth, analytics, dealer, financial
5. **Models** — 35 additional domain models (CMS, stock, battery health, dealer KYC, etc.)
6. **Schemas** — 75+ schemas vs ~30
7. **Analytics engine** — 1,623 LOC analytics service + per-actor analytics modules
8. **Router organization** — grouped by actor with admin dependencies at router level
9. **Docker** — multi-stage build, non-root user, resource limits
10. **MongoDB audit trail** — async queue with batch writes
11. **Sentry integration** — production error tracking
12. **CORS handling** — validates `*` with credentials, regex localhost, global OPTIONS handler
13. **UTC-aware timestamps** — uses `datetime.now(UTC)` instead of deprecated `utcnow()`

---

## 4. Merge Strategy

### Phase 0: Prepare Base (Use Laxman as base)
Laxman has **232 more files**, a test suite, better logging, and all business domain logic. It's the natural base.

### Phase 1: Port Hardened Infrastructure Into Laxman

| Priority | Component | Source | Action |
|----------|-----------|--------|--------|
| **P0** | `core/config.py` | Merge | Add Hardened's production safety settings, event stream config, passkey config, fraud compute config, background runtime mode, DB URL normalization, allowed hosts normalization |
| **P0** | `main.py` startup | Merge | Add `_validate_production_safety()`, `StartupDiagnosticsService`, degraded-mode startup, crash loop prevention |
| **P0** | `services/startup_diagnostics_service.py` | Copy from Hardened | Deep readiness checks |
| **P0** | `services/background_runtime_service.py` | Copy from Hardened | Leader election for scheduler |
| **P0** | `services/redis_service.py` | Copy from Hardened | Centralized Redis client |
| **P0** | `services/distributed_cache_service.py` | Copy from Hardened | Stale-while-revalidate caching |
| **P1** | `services/idempotency_service.py` + `models/idempotency.py` | Copy from Hardened | Payment safety |
| **P1** | `services/event_stream_service.py` | Copy from Hardened | Redis Streams |
| **P1** | `services/notification_outbox_service.py` + `models/notification_outbox.py` | Copy from Hardened | Guaranteed notification delivery |
| **P1** | `middleware/rate_limit.py` | Replace with Hardened | Proxy-aware + Redis fallback |
| **P1** | `middleware/server_timing.py` | Copy from Hardened | Browser waterfall diagnostics |
| **P1** | `middleware/proxy_host.py` | Copy from Hardened | RFC 7239 proxy host rewrite |
| **P1** | `core/database.py` | Merge | Add search_path safety, slow query logging, SSL, connect timeout |
| **P1** | `gunicorn_conf.py` | Copy from Hardened | Separate config file |
| **P1** | `.dockerignore` | Copy from Hardened | |
| **P2** | `services/passkey_service.py` + `models/passkey.py` | Copy from Hardened | WebAuthn |
| **P2** | `services/fraud_compute_service.py` | Copy from Hardened | External fraud scoring |
| **P2** | `services/telematics_ingest_service.py` | Copy from Hardened | Stream ingestion |
| **P2** | `services/workflow_automation_service.py` | Copy from Hardened | |
| **P2** | `workers/event_stream_worker.py`, `workers/event_runner.py`, `workers/runner.py` | Copy from Hardened | Event processing workers |
| **P2** | `db/logistics_schema_guard.py` | Copy from Hardened | Schema validation |

### Phase 2: Upgrade Common Services (Take Stronger Version)

| Service | Take From | Reason |
|---------|-----------|--------|
| `rental_service.py` | **Hardened** | 811 vs 291 LOC — much richer workflows |
| `notification_service.py` | **Hardened** | 535 vs 140 LOC — multi-channel + outbox |
| `websocket_service.py` | **Hardened** | 527 vs 183 LOC — pubsub + outbox |
| `wallet_service.py` | **Hardened** | 479 vs 312 LOC — enhanced transactions |
| `mqtt_service.py` | **Hardened** | 342 vs 306 LOC — more robust |
| `qr_service.py` | **Hardened** | 338 vs 84 LOC — signed QR codes |
| `maintenance_service.py` | **Hardened** | 403 vs 123 LOC |
| `swap_service.py` | **Hardened** | 224 vs 197 LOC |
| `geofence_service.py` | **Hardened** | 112 vs 42 LOC |
| `fcm_service.py` | **Hardened** | 113 vs 47 LOC |
| `maps_service.py` | **Hardened** | 72 vs 26 LOC |
| `storage_service.py` | **Hardened** | 84 vs 31 LOC |
| `sms_service.py` | **Hardened** | 73 vs 15 LOC |
| `email_service.py` | **Hardened** | 55 vs 33 LOC |
| `otp_service.py` | **Hardened** | 217 vs 194 LOC |
| `security_service.py` | **Hardened** | 87 vs 65 LOC |
| `analytics_service.py` | **Laxman** | 1623 vs 116 LOC — full analytics |
| `auth_service.py` | **Laxman** | 480 vs 237 LOC — more auth flows |
| `audit_service.py` | **Laxman** | 213 vs 43 LOC |
| `station_service.py` | **Laxman** | 297 vs 207 LOC |
| `battery_service.py` | **Laxman** | 257 vs 58 LOC |
| `order_service.py` | **Laxman** | 335 vs 279 LOC |
| `catalog_service.py` | **Laxman** | 304 vs 228 LOC |
| `dealer_service.py` | **Laxman** | 222 vs 133 LOC |
| `late_fee_service.py` | **Laxman** | 200 vs 138 LOC |
| `support_service.py` | **Laxman** | 170 vs 57 LOC |
| `user_service.py` | **Laxman** | 167 vs 58 LOC |
| `kyc_service.py` | **Laxman** | 183 vs 98 LOC |
| `rbac_service.py` | **Laxman** | 151 vs 113 LOC |
| `commission_service.py` | **Laxman** | 108 vs 53 LOC |

### Phase 3: Port Hardened API Endpoints

| Endpoint | Source | Notes |
|----------|--------|-------|
| `api/v1/passkeys.py` | Hardened | WebAuthn auth |
| `api/v1/orders.py`, `orders_realtime.py` | Hardened | Logistics orders with WebSocket |
| `api/v1/manifests.py` | Hardened | Delivery manifests |
| `api/v1/routes.py` | Hardened | Route optimization |
| `api/v1/warehouse_structure.py` | Hardened | Warehouse zones/locations |
| `api/v1/battery_catalog.py` | Hardened | Battery specs |
| `api/v1/location.py` | Hardened | Single location endpoint |
| `api/v1/*_enhanced.py` | Hardened | Enhanced wallet, payments, notifications, support, rentals, analytics, purchases |
| `api/v1/utils.py` | Hardened | Utility endpoints |
| `api/internal/hotspots.py` | Hardened | Internal hotspot API |
| `api/webhooks/razorpay.py` | Hardened (if more complete) | Webhook handling |

### Phase 4: Docker & Deployment Merge

1. Take Laxman's multi-stage Dockerfile
2. Add `gunicorn_conf.py` from Hardened and update CMD to use it
3. Add Hardened's `.dockerignore`
4. Merge docker-compose: use Laxman's structure + add `no-new-privileges`, `HEALTHCHECK` from Hardened, required secrets validation
5. Keep Laxman's `prod/docker-compose.yml`

### Phase 5: Fix Security Details
1. Replace all `datetime.utcnow()` with `datetime.now(UTC)` across codebase (Laxman already does this)
2. Add `structlog` to Hardened's service files that still use plain `logging`
3. Ensure `models/all.py` imports all models from both repos

---

## 5. Post-Merge: Ready for Modularization

After merging, the combined codebase will have:
- **~570+ Python files** in `app/`
- **All business domains** from Laxman
- **All infrastructure hardening** from Hardened
- **80+ tests** ready to validate
- **Production-safe** startup with diagnostics
- **Structured logging** throughout

This combined backend is then ready for Phase 1 modularization as described in `MODULAR_DECOMPOSITION_PLAN.md` — reorganizing into `app/modules/{customer,admin,dealer,iot,logistics,financial,jobs}/` with a shared `app/common/` layer.

---

## 6. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Import conflicts when porting Hardened services | Medium | Hardened services reference `redis_service`, `distributed_cache_service` — port these first |
| Hardened's rental_service may reference models not in Laxman | Low | Both share the same `Rental`, `Payment`, `Wallet` models |
| Config setting name differences (`DB_POOL_SIZE` vs `DATABASE_POOL_SIZE`) | Medium | Standardize on one naming convention during merge |
| CORS middleware ordering | High | Laxman's ordering is correct (CORS outermost). Keep it. |
| `workers/__init__.py` expects `event_stream_worker` | Low | Port the worker file alongside |
| Hardened's `gunicorn_conf.py` vs Laxman's inline CMD | Low | Switch to conf file, remove inline CMD |
| `requirements.txt` reconciliation | Medium | Use Laxman's pinned `requirements.prod.txt` as base, add Hardened's `webauthn` dependency |

---

## 7. Execution Order (Recommended)

```
Week 1: P0 — Config merge, startup safety, diagnostics, redis service, background runtime
Week 2: P1 — Middleware merge, database hardening, stronger common services (rental, notification, wallet, websocket)
Week 3: P2 — Port remaining Hardened services (passkey, event streams, fraud compute, telematics)
Week 4: P1/P2 — Port Hardened API endpoints, merge Docker setup
Week 5: Testing & Validation — Run full test suite, fix import errors, validate all endpoints
Week 6: Begin Phase 1 Modularization per MODULAR_DECOMPOSITION_PLAN.md
```
