# WEZU Backend - Project Overview

## Introduction
The **WEZU Backend** is a high-performance, enterprise-grade system built to power the **WEZU Energy Monetization Platform**. It manages energy distribution, battery swapping networks, financial transactions, and fleet logistics.

---

## 🛠 Core Technology Stack

- **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Asynchronous, High Performance)
- **Database Architecture**:
  - **SQL**: PostgreSQL with [SQLModel](https://sqlmodel.tiangolo.com/) / [SQLAlchemy](https://www.sqlalchemy.org/)
  - **Migrations**: [Alembic](https://alembic.sqlalchemy.org/)
  - **Timeseries**: Support for TimescaleDB (for telematics and IoT data)
- **Task Management**:
  - **Workers**: [Celery](https://docs.celeryq.dev/) with [Redis](https://redis.io/)
  - **Scheduling**: APScheduler
- **Communications**:
  - **IoT**: MQTT (using `paho-mqtt`)
  - **Real-time**: WebSockets
  - **External**: Firebase FCM (Push Notifications), Twilio (SMS), SendGrid (Email)
- **Deployment**: Docker, Docker Compose, and Kubernetes (k8s)

---

## 📁 Project Structure & Modules

The codebase follows a modular clean architecture in the `app/` directory:

### 1. Business Logic & Services (`app/services/`)
This is the "brain" of the application. Key services include:
- **`battery_service.py` & `swap_service.py`**: Handles battery health, swapping logic, and station management.
- **`iot_service.py` & `telematics_service.py`**: Processes real-time data from battery hardware.
- **`payment_service.py` & `wallet_service.py`**: Manages Razorpay integrations, prepaid wallets, and transactions.
- **`kyc_service.py` & `video_kyc_service.py`**: Handles user verification and compliance.
- **`ml_fraud_service.py`**: Uses Machine Learning to detect fraudulent activities.

### 2. Data Models (`app/models/`)
Contains over 60 schemas defining the business entities:
- **Core Entities**: `User`, `Battery`, `Station`, `Vehicle`.
- **Logistics**: `Dealer`, `Warehouse`, `DeliveryRoute`, `Inventory`.
- **Financials**: `Invoice`, `Settlement`, `Commission`, `PromoCode`.
- **Security**: `AuditLog`, `RBAC` (Role Based Access Control), `Fingerprint`.

### 3. API Layer (`app/api/`)
- **V1 Routes**: Comprehensive REST endpoints for all services.
- **Admin**: Exclusive endpoints for system administration and monitoring.
- **Webhooks**: Handles callbacks from Razorpay, Firebase, and other external integrations.

---

## 🚀 Key Functional Areas

### 🔋 Energy & Battery Management
The system provides real-time monitoring of battery health, GPS tracking, and geofencing. It includes a **Swap Suggestion** engine to guide users to the nearest swapping station.

### 🚛 Logistics & Fleet
Engineered for scale, the system manages `Dealers`, `Sub-dealers`, and `Vendors`. It handles warehouse inventory, delivery assignments, and route optimization.

### 💳 Financial Ecosystem
Comprehensive billing system including:
- **Wallet Model**: Prepaid vault for instant transactions.
- **Automated Invoicing**: PDF generation for rentals and substitutions.
- **Commission Engine**: Calculates payouts for dealers and partners.

### 🔒 Security & Compliance
- **Advanced Auth**: Biometric login, Google OAuth, and 2FA via OTP.
- **Identity**: Full KYC pipeline including automated video KYC verification.
- **Role-Based Access**: Granular permissions for admins, staff, drivers, and dealers.

---

## 🧪 DevOps & Testing
- **K8s Manifests**: Located in `k8s/` for production-ready deployment.
- **Automated Testing**: Uses `pytest` with a dedicated `tests/` directory covering most services.
- **Maintenance**: Includes specialized scripts for database schema repairs and migration validation.
