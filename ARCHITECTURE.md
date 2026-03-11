# WEZU Backend - System Architecture & Flow

This document details the technical architecture, data flows, and component interactions of the WEZU Backend.

## 🏗 High-Level Architecture

The system follows a **Modular Monolith** architecture with a clear separation of concerns, designed for high performance using **FastAPI** (Async) and **SQLModel**.

```mermaid
graph TD
    Client[Mobile App / Web Dashboard] -->|HTTPS| LB[Load Balancer / Nginx]
    LB --> API[FastAPI Application]
    
    subgraph "Application Layer"
        API -->|Validates| AuthMid[Auth Middleware & Deps]
        AuthMid -->|Routes| Routers[API Routers (v1)]
        Routers -->|Calls| Services[Service Layer]
    end
    
    subgraph "Data & State"
        Services -->|Reads/Writes| DB[(PostgreSQL + TimescaleDB)]
        Services -->|Cache/Queue| Redis[(Redis)]
        Services -->|Async Tasks| Celery[Celery Workers]
    end
    
    subgraph "External Integrations"
        Services -->|Payments| Razorpay[Razorpay]
        Services -->|Notifications| FCM[Firebase Cloud Messaging]
        Services -->|Auth| OAuth[Google / Apple / Facebook]
    end
    
    subgraph "IoT Ecosystem"
        IoT[Battery / Station HW] -->|MQTT| Broker[MQTT Broker]
        Broker -->|Subscribes| MQTTService[MQTT Service]
        MQTTService -->|Hot Storage| Redis
        MQTTService -->|Cold Storage| DB
    end
```

---

## 🔄 Core Data Flows

### 1. Request Lifecycle (Standard API)
Every API request follows this path:
1.  **Entry**: Request hits `app/main.py`.
2.  **Middleware**:
    *   `CORSMiddleware`: Checks allowed origins.
    *   `GZipMiddleware`: Compresses responses.
    *   `RateLimitMiddleware`: Checks Redis for rate limits.
3.  **Routing**: Dispatched to `app/api/v1/` based on prefix (e.g., `/users`, `/swaps`).
4.  **Dependencies (`app/api/deps.py`)**:
    *   `get_db()`: Creates a scoped DB session.
    *   `get_current_user()`: Validates JWT, checks `BlacklistedToken`, and verifies User existence/status.
5.  **Service Layer**: Router calls specific service (e.g., `BatteryService.get_battery()`).
6.  **Database**: Service interacts with `SQLModel` models.
7.  **Response**: Pydantic schemas serialize data back to JSON.

### 2. Authentication Flow (Google/Apple/Social)
Handles secure user onboarding and session management.
```mermaid
sequenceDiagram
    participant Client
    participant API as API (Auth Route)
    participant Service as AuthService
    participant Google as Google/Apple
    participant DB

    Client->>Client: User signs in with Google
    Client->>API: POST /auth/login/google (id_token)
    API->>Service: verify_google_token(token)
    Service->>Google: Verify Token Integrity
    Google-->>Service: User Info (Email, ID)
    Service->>DB: Find or Create User
    Service->>DB: Create SessionToken
    Service-->>API: Access + Refresh Token
    API-->>Client: JSON { tokens, user_info }
```

### 3. Battery Swap Flow
Critical business logic for finding stations and executing swaps.
```mermaid
sequenceDiagram
    participant User
    participant API
    participant SwapService
    participant DB

    User->>API: GET /swaps/suggestions (lat, long)
    API->>SwapService: get_swap_suggestions()
    SwapService->>DB: Query Active Stations
    loop For each station
        SwapService->>SwapService: Calculate Distance (Haversine/PostGIS)
        SwapService->>DB: Check Available Batteries (SoC > 80%, Health > 85%)
    end
    SwapService-->>API: List of Optimal Stations
    API-->>User: Display Map Pins

    User->>API: POST /swaps/execute (station_id, battery_qr)
    API->>SwapService: execute_swap()
    SwapService->>DB: Verify Rental & Battery Status
    SwapService->>DB: Updates:
    Note right of DB: 1. Old Battery -> Available<br/>2. New Battery -> Rented<br/>3. Rental -> New Battery ID<br/>4. Log RentalHistory
    SwapService-->>API: Success
    API-->>User: Swap Confirmed
```

### 4. IoT Telemetry Ingestion (Real-time)
Handles high-frequency data from batteries.
1.  **Source**: Battery BMS sends JSON payload via MQTT to `wezu/batteries/{id}/telemetry`.
2.  **Ingestion**: `app/services/mqtt_service.py` listens to topic.
3.  **Processing**:
    *   **Hot Path**: Data stored in **Redis** with 5-min TTL for real-time app dashboard usage (`get_realtime_data`).
    *   **Cold Path**: `TelematicsService` writes to **TimescaleDB** for historical analysis.
    *   **Alerting**: Checks thresholds (Temp > 45°C, SoC < 10%). If triggered, pushes alert to Redis and triggers Notification Service.

---

## 📂 Directory Structure & Module Responsibilities

| Directory | Role | Key Files |
|-----------|------|-----------|
| `app/api/v1` | **Controllers**: Validates inputs, calls services. | `auth.py`, `swaps.py`, `batteries.py` |
| `app/services` | **Business Logic**: Complex rules, transactions. | `swap_service.py`, `auth_service.py` |
| `app/models` | **Data Access**: DB Schemas & Relationships. | `user.py`, `battery.py`, `rental.py` |
| `app/core` | **Config**: Settings, Security, DB connect. | `config.py`, `security.py`, `database.py` |
| `app/workers` | **Background**: Scheduled tasks. | `celery_app.py`, `tasks.py` |

## 🛠 Key Technology Decisions
*   **FastAPI**: Chosen for native Async support (critical for IoT/Chat) and auto-generated OpenApi docs.
*   **SQLModel**: Combines Pydantic verification with SQLAlchemy ORM ease of use.
*   **TimescaleDB**: Optimizes storage for millions of battery telemetry rows.
*   **Redis**: Used for caching (rate limits, session storage) and real-time state (current battery metrics).
