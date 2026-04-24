# WEZU Energy Backend — Modular Decomposition Analysis

> **Date:** April 2026
> **Scope:** Feasibility analysis for splitting the monolithic backend into role-based and domain-based modules.
> **Status:** Findings & Plan — no code changes made.

---

## 1. Current State Summary

| Metric | Value |
|--------|-------|
| Total Python files | ~501 |
| API route files (v1) | ~90 files, ~20K LOC |
| Service layer | ~82 files, ~14.5K LOC |
| Model layer | ~80+ SQLModel classes, ~5K LOC |
| Schema layer | ~75+ files |
| Repositories | 14 files |
| Background workers | 6 worker files + 4 task files |
| External integrations | 8 (Razorpay, Firebase, Twilio, Google Maps, AWS S3, Aadhaar, PAN, GST) |

The application is a **single FastAPI monolith** — one `main.py` registers all routers, middleware, and background tasks. All user roles (Admin, Customer, Dealer, Driver, Support Agent, Logistics) share a single process, database connection pool, and deployment artifact.

---

## 2. Identified User Roles / Actors

| Role | UserType Enum | Existing Route Prefix | Approximate Route Count |
|------|---------------|----------------------|------------------------|
| **Customer** | `CUSTOMER` | `/api/v1/*` (default) | ~25 routers |
| **Admin** | `ADMIN` | `/api/v1/admin/*` | ~15 routers |
| **Dealer** | `DEALER` / `DEALER_STAFF` | `/api/v1/dealer/*` | ~13 routers |
| **Driver** | (role-based) | `/api/v1/drivers` | ~2 routers |
| **Support Agent** | `SUPPORT_AGENT` | mixed across admin | ~3 routers |
| **Logistics** | `LOGISTICS` | `/api/v1/logistics` | ~2 routers |
| **System/IoT** | N/A | `/api/v1/iot`, webhooks | ~4 routers |

The codebase already groups routes by actor in `main.py` with clear section comments (`# Customer Endpoints`, `# Admin Endpoints`, `# Dealer Endpoints`, `# Logistics & System`). This is a strong indicator that **decomposition is feasible and already partially designed for**.

---

## 3. Proposed Modular Blocks

### Block 1: **Customer App Backend**
Serves the end-user mobile app (battery rental, swap, payments, profile).

**Routes to include:**
- `auth.py`, `customer_auth.py`, `sessions.py` — Authentication (OTP, Google, Apple)
- `profile.py`, `users.py` (customer-facing subset) — Profile management
- `kyc.py` — KYC submission
- `stations.py` — Station discovery & availability
- `batteries.py` — Battery info & availability
- `rentals.py`, `bookings.py` — Rental lifecycle
- `swaps.py` — Battery swap flow
- `wallet.py`, `payments.py`, `transactions.py` — Payments & wallet
- `notifications.py` — Push/in-app notifications
- `support.py` — Customer support tickets
- `favorites.py` — Saved stations/batteries
- `promo.py`, `catalog.py` — Promos & e-commerce
- `faqs.py`, `i18n.py`, `screens.py` — UI config & content
- `vehicles.py` — Vehicle registration
- `locations.py` — Geolocation

**Services required:** `auth_service`, `rental_service`, `swap_service`, `wallet_service`, `payment_service`, `notification_service`, `station_service`, `battery_service`, `booking_service`, `support_service`, `catalog_service`, `user_service`, `kyc_service`, `otp_service`, `gps_service`, `maps_service`, `qr_service`

**Models required:** `User`, `Rental`, `Battery`, `Station`, `Swap`, `Wallet`, `Transaction`, `Payment`, `SupportTicket`, `Notification`, `KYCDocument`, `Vehicle`, `PromoCode`, `Catalog`

---

### Block 2: **Admin Panel Backend**
Serves the internal admin web dashboard.

**Routes to include:**
- `admin_users.py`, `admin_user_bulk.py` — User management
- `admin_kyc.py` — KYC review & approval
- `admin_stations.py`, `station_monitoring.py` — Station management
- `admin_analytics.py`, `analytics.py` — Platform analytics & dashboards
- `admin_invoices.py`, `admin_financial_reports.py` — Financial reporting
- `admin_audit.py`, `audit.py` — Audit trail viewing
- `admin_rbac.py`, `admin_roles.py` — RBAC & role management
- `admin_dealers.py` — Dealer oversight
- `dashboard.py` — Admin dashboard bootstrap
- `inventory.py`, `stock.py`, `warehouses.py` — Inventory management
- `fraud.py` — Fraud monitoring
- `system.py` — System configuration
- All `app/api/admin/` routes (global admin: CMS, banners, blogs, BESS, monitoring, etc.)
- `settlements.py` — Settlement management

**Services required:** `admin_analytics_service`, `analytics_service`, `audit_service`, `rbac_service`, `role_service`, `user_service`, `station_service`, `fraud_service`, `settlement_service`, `financial_report_service`, `invoice_service`, `inventory_service`, `feature_flag_service`

**Models required:** All models (read access) + Admin-specific: `AuditLog`, `AdminGroup`, `AdminUser`, `Banner`, `Blog`, `FAQ`, `BatchJob`, `BESS`, `RevenueReport`

---

### Block 3: **Dealer Portal Backend**
Serves the dealer-facing web portal.

**Routes to include:**
- `dealer_portal_auth.py` — Dealer authentication
- `dealer_portal_dashboard.py` — Dealer dashboard
- `dealer_portal_tickets.py` — Dealer support tickets
- `dealer_portal_customers.py` — Dealer's customer view
- `dealer_portal_settings.py` — Dealer settings
- `dealer_portal_roles.py` — Dealer sub-roles
- `dealer_portal_users.py` — Dealer staff management
- `dealers.py` — Dealer profile
- `dealer_stations.py` — Dealer station management
- `dealer_analytics.py` — Dealer-specific analytics
- `dealer_campaigns.py` — Promotional campaigns
- `dealer_onboarding.py`, `dealer_documents.py` — KYC & onboarding
- `dealer_commission.py` — Commission tracking

**Services required:** `dealer_service`, `dealer_analytics_service`, `dealer_kyc_service`, `dealer_ledger_service`, `dealer_station_service`, `commission_service`, `campaign_service`, `notification_service`

**Models required:** `DealerProfile`, `DealerInventory`, `DealerPromotion`, `DealerKYC`, `Commission`, `Station` (dealer-scoped), `User` (dealer type)

---

### Block 4: **IoT & Telemetry Service**
Handles real-time device communication and time-series data.

**Routes to include:**
- `iot.py` — Device management & commands
- `telematics.py` — Telematics data ingestion
- `telemetry.py` — Telemetry queries

**Background tasks to include:**
- MQTT service (`mqtt_service.py`)
- `station_monitor.py` — Station health checks (every 2 min)
- `battery_health_monitor.py` — Battery degradation detection (hourly)
- `charging_optimizer.py` — Charging queue optimization (every 30 min)

**Services required:** `mqtt_service`, `iot_service`, `telematics_service`, `timescale_service`, `gps_service`, `geofence_service`, `websocket_service`

**Infrastructure:** MQTT broker, TimescaleDB, WebSocket, Redis pub/sub

---

### Block 5: **Logistics & Driver Backend**
Serves field operations (battery transfers, route management, driver ops).

**Routes to include:**
- `logistics.py` — Battery transfers, delivery routes
- `drivers.py` — Driver profile & assignment

**Services required:** `logistics_service`, `driver_service`, `notification_service`, `gps_service`

**Models required:** `BatteryTransfer`, `DeliveryRoute`, `DeliveryAssignment`, `DriverProfile`

---

### Block 6: **Background Jobs & ML Pipeline**
Scheduled jobs, analytics aggregation, and ML model training.

**Workers to include:**
- `daily_jobs.py` — Revenue aggregation, inventory sync, late fees, commission accrual, fraud scoring
- `hourly_jobs.py` — Battery health, geofence violations, low stock alerts, swap notifications
- `monthly_jobs.py` — Commission settlement, financial reconciliation, data archival, batch payments
- `rental_worker.py` — Overdue rental processing
- `analytics_tasks.py` — Analytics aggregation

**ML to include:**
- `ml/feature_store.py` — Feature extraction from telemetry, rentals, transactions
- `ml/pipeline.py` — Model training (battery health, demand forecast)
- `ml/registry.py` — Model versioning

**Services required:** Reads from all domain models. Writes to analytics aggregation tables, settlement records, alert records.

---

### Block 7: **Webhook & Payment Gateway**
Handles external callbacks.

**Routes to include:**
- `webhooks/razorpay.py` — Razorpay payment callbacks

**Services required:** `payment_service`, `wallet_service`, `receipt_service`

---

## 4. Shared / Common Layer (Must Be Extracted First)

Before splitting into blocks, these **cross-cutting modules must become a shared library or package**:

| Module | Contents | Used By |
|--------|----------|---------|
| `app/core/` | Config, security, database, logging, scheduler config | All blocks |
| `app/db/` | Session factory, seed data | All blocks |
| `app/models/` | All SQLModel classes (shared DB schema) | All blocks |
| `app/schemas/common.py` | Shared response schemas | All blocks |
| `app/middleware/` | RBAC, rate limiting, audit, security headers, CORS | All API blocks |
| `app/utils/` | Constants, helpers, validators, cache, exceptions, logger | All blocks |
| `app/integrations/` | External API wrappers (Razorpay, Firebase, Twilio, etc.) | Multiple blocks |
| `app/api/deps.py` | Auth dependencies (`get_current_user`, `get_current_admin`, etc.) | All API blocks |
| `app/services/notification_service.py` | Multi-channel notification hub | All blocks |
| `app/services/audit_service.py` | Audit logging (MongoDB) | All blocks |

---

## 5. Cross-Domain Dependency Map

```
                    ┌──────────────────────────────────────┐
                    │         SHARED COMMON LAYER          │
                    │  Models · Auth · Config · Middleware  │
                    │  Notifications · Audit · Integrations│
                    └──────────┬───────────────────────────┘
                               │
        ┌──────────┬───────────┼───────────┬──────────┬────────────┐
        ▼          ▼           ▼           ▼          ▼            ▼
   ┌─────────┐ ┌────────┐ ┌─────────┐ ┌────────┐ ┌──────────┐ ┌────────┐
   │Customer │ │ Admin  │ │ Dealer  │ │  IoT   │ │Logistics │ │  Jobs  │
   │   App   │ │ Panel  │ │ Portal  │ │Telemetry│ │ & Driver │ │  & ML  │
   └────┬────┘ └───┬────┘ └────┬────┘ └───┬────┘ └────┬─────┘ └───┬────┘
        │          │           │           │           │            │
        │          │           │           │           │            │
        ▼          ▼           ▼           ▼           ▼            ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │                     PostgreSQL + TimescaleDB                    │
   │                     Redis · MongoDB · S3                        │
   └─────────────────────────────────────────────────────────────────┘
```

### Critical Coupling Points

| Coupling | Between | Severity | Notes |
|----------|---------|----------|-------|
| Rental → Wallet → Payment | Customer ↔ Financial | **High** | Rental creates payments, debits wallet |
| Rental → Commission → Settlement | Customer ↔ Dealer | **High** | Each rental accrues dealer commission |
| Station inventory | Customer ↔ Admin ↔ Dealer ↔ IoT | **High** | Real-time slot availability shared |
| Notification hub | All blocks → Notification | **Medium** | All domains trigger notifications |
| User model | All blocks | **High** | Single `users` table, polymorphic roles |
| Audit trail | All blocks → MongoDB | **Low** | Write-only, easy to decouple |
| Analytics reads | Jobs/ML ↔ All domains | **Medium** | Read-only aggregation across tables |

---

## 6. Recommended Decomposition Strategy

### Phase 1: Internal Modularization (Low Risk)
Reorganize the **existing monolith** into clearly separated internal packages without splitting the deployment.

```
app/
├── common/                  # Shared layer (extracted from core/, utils/, middleware/)
│   ├── auth/
│   ├── config/
│   ├── database/
│   ├── middleware/
│   └── integrations/
├── modules/
│   ├── customer/            # Customer-facing routes, services, schemas
│   │   ├── api/
│   │   ├── services/
│   │   └── schemas/
│   ├── admin/               # Admin routes, services, schemas
│   │   ├── api/
│   │   ├── services/
│   │   └── schemas/
│   ├── dealer/              # Dealer portal routes, services, schemas
│   │   ├── api/
│   │   ├── services/
│   │   └── schemas/
│   ├── iot/                 # IoT & telemetry
│   │   ├── api/
│   │   ├── services/
│   │   └── tasks/
│   ├── logistics/           # Logistics & driver
│   │   ├── api/
│   │   └── services/
│   ├── financial/           # Payments, wallet, settlements, invoices
│   │   ├── api/
│   │   └── services/
│   └── jobs/                # Background workers & ML
│       ├── workers/
│       ├── tasks/
│       └── ml/
├── models/                  # Stays shared (single DB schema)
└── main.py                  # Composes modules
```

**Why:** This gives you clean domain boundaries, testability per module, and clear ownership — without any infrastructure changes.

### Phase 2: Separate FastAPI Apps per Block (Medium Risk)
Split into **multiple FastAPI applications** that can be deployed independently behind a reverse proxy (e.g., Traefik, already in use per `DEPLOY_COOLIFY_TRAEFIK.md`).

| App | Port/Path | Deployment |
|-----|-----------|------------|
| `customer-api` | `/api/v1/customer/*`, `/api/v1/auth/*`, etc. | Scales with mobile traffic |
| `admin-api` | `/api/v1/admin/*`, `/api/v1/dashboard/*` | Low traffic, high privilege |
| `dealer-api` | `/api/v1/dealer/*` | Medium traffic |
| `iot-api` | `/api/v1/iot/*`, `/api/v1/telematics/*` | High throughput, MQTT |
| `worker` | No HTTP | Background jobs only |

**Shared via:**
- A `wezu-common` Python package (models, schemas, auth, config)
- Same PostgreSQL / Redis / MongoDB cluster
- Inter-service calls via **direct DB access** (same schema) or internal HTTP if needed

### Phase 3: Full Microservices (High Risk, Long Term)
Only if scale demands it — extract Financial, IoT, and Notification into independent services with API contracts and event-driven communication.

---

## 7. Key Risks & Considerations

| Risk | Mitigation |
|------|------------|
| **Shared User model** across all blocks | Keep `models/` as a shared package; do NOT duplicate the User table |
| **Circular service dependencies** (Rental → Wallet → Payment → Finance → Settlement → Commission → Rental) | Break cycles with events or a shared `financial` module |
| **MQTT + WebSocket** tightly coupled to main app lifespan | Isolate IoT block with its own lifespan manager |
| **Background jobs** touch all domains | Jobs block gets read-only access to all models; domain services invoked via direct import |
| **Alembic migrations** assume a single source of model definitions | Keep a single `models/` package and single migration history |
| **Test suite** may have cross-module assumptions | Audit tests per module after restructure |
| **Deployment complexity** increases with multiple apps | Use Docker Compose profiles or K8s namespaces (infra already exists in `k8s/`) |

---

## 8. Verdict

**Yes, this project can and should be modularized.** The codebase already exhibits natural domain boundaries with clear role-based route grouping in `main.py`. The recommended approach:

1. **Start with Phase 1** (internal package reorganization) — lowest risk, highest immediate value
2. **Proceed to Phase 2** only when deployment scaling needs differ per block (e.g., IoT needs more instances than Admin)
3. **Phase 3** is unnecessary unless the team grows to 10+ engineers working simultaneously

The biggest win is separating **Customer**, **Admin**, and **Dealer** concerns, as these serve different frontends, have different traffic patterns, and are developed by potentially different team members.
