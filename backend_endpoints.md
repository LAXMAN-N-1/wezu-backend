# Backend Architecture & API Documentation

## Overview

The `wezu_battery_app` backend is a high-performance, asynchronous web API built using **FastAPI**. It is designed to scale and handles complex battery swapping operations, real-time rentals, user management, and IoT device communication.

### Technology Stack

-   **Framework**: FastAPI (Python)
-   **Database**: PostgreSQL
-   **Migrations**: Alembic
-   **Caching & Sessions**: Redis
-   **Authentication**: JWT (JSON Web Tokens), OAuth2 (Google/Apple), OTP (Twilio/Msg91)
-   **Background Tasks**: Python `asyncio` / Custom Scheduler
-   **Monitoring**: Sentry
-   **Containerization**: Docker

## API Structure

The API is versioned (currently `v1`) and follows a modular structure where each functional domain (Auth, Users, Rentals, etc.) has its own router.

**Base URL**: `/api/v1`

---

## Endpoint Reference

### 1. Authentication (`/auth`)
Handles user registration, login, and security settings.

-   **POST** `/register/request-otp` - Request OTP for new user registration.
-   **POST** `/register/verify-otp` - Verify OTP and complete registration.
-   **POST** `/google` - Google OAuth login.
-   **POST** `/apple` - Apple OAuth login.
-   **POST** `/refresh` - Refresh access token.
-   **POST** `/logout` - Invalidate current session.
-   **POST** `/resend-otp` - Resend OTP for verification.
-   **POST** `/forgot-password` - Initiate password reset flow.
-   **POST** `/reset-password` - Complete password reset.
-   **POST** `/change-password` - Change password for logged-in user.
-   **POST** `/verify-2fa` - Verify Two-Factor Authentication code.
-   **POST** `/biometric/register` - Register biometric credentials.
-   **POST** `/biometric/verify` - Verify biometric login.
-   **POST** `/2fa/enable` - Enable 2FA.
-   **POST** `/2fa/disable` - Disable 2FA.

### 2. Users (`/users`)
Manage user profiles and personal details.

-   **GET** `/me` - Get current user profile.
-   **PUT** `/me` - Update user profile.
-   **PATCH** `/me` - Partial update of user profile.
-   **POST** `/me/avatar` - Upload/Update profile picture.
-   **DELETE** `/me/avatar` - Remove profile picture.
-   **GET** `/me/addresses` - List saved addresses.
-   **POST** `/me/addresses` - Add a new address.
-   **PATCH** `/me/addresses/{address_id}/default` - Set default address.

### 3. KYC (Know Your Customer) (`/kyc`)
Identity verification workflows.

-   **GET** `/me/kyc` - Check current KYC status.
-   **POST** `/me/kyc/documents` - Upload identity documents (PAN, Aadhaar, etc.).
-   **POST** `/me/kyc/submit` - Submit KYC for review.
-   **POST** `/me/kyc/video/schedule` - Schedule a video KYC session.
-   **POST** `/me/kyc/video/start` - detailed video KYC session.

### 4. Stations (`/stations`)
Battery swapping station discovery and interactions.

-   **GET** `/` - List all stations (with filters).
-   **GET** `/nearby` - specific endpoint for finding nearest stations.
-   **POST** `/` - Create a station (Admin/System usually).
-   **GET** `/{station_id}` - Get detailed info for a specific station.
-   **GET** `/{station_id}/reviews` - Get user reviews for a station.
-   **POST** `/{station_id}/reviews` - Submit a review.

### 5. Rentals (`/rentals`)
Core logic for renting batteries.

-   **POST** `/{rental_id}/return` - Return a rented battery.
-   **POST** `/{rental_id}/extend` - Extend rental duration.
-   **POST** `/{rental_id}/pause` - Pause rental (e.g., for maintenance).
-   **POST** `/{rental_id}/resume` - Resume paused rental.
-   **GET** `/{rental_id}/receipt` - Get rental receipt.
-   **GET** `/{rental_id}/late-fees` - Calculate pending late fees.
-   **POST** `/{rental_id}/late-fees/waiver` - Request waiver for late fees.
-   **POST** `/{rental_id}/report-issue` - Report a problem with the rental.
-   **POST** `/{rental_id}/location` - Update rental location (GPS tracking).
-   **GET** `/{rental_id}/location/current` - Get current location.
-   **GET** `/{rental_id}/location/path` - Get historical path.

### 6. Wallet (`/wallet`)
In-app wallet for payments.

-   **GET** `/` - Get wallet balance and status.
-   **POST** `/recharge` - Add money to wallet.
-   **GET** `/transactions` - List wallet transactions.
-   **POST** `/withdraw` - Withdraw funds to bank account.
-   **GET** `/cashback` - Check available cashback offers.
-   **POST** `/transfer` - Transfer funds between users (if supported).

### 7. Payments (`/payments`)
Payment processing and history.

-   **GET** `/orders/{order_id}/invoice` - Download order invoice.
-   **GET** `/rentals/{rental_id}/invoice` - Download rental invoice.
-   **POST** `/orders/{order_id}/refund` - Initiate a refund.
-   **GET** `/refunds` - List refund requests.
-   **GET** `/payment-methods` - List saved payment methods (cards/UPI).
-   **POST** `/methods` - Add a payment method.
-   **DELETE** `/methods/{method_id}` - Remove a payment method.
-   **POST** `/razorpay/webhook` - Webhook handler from Razorpay.

### 8. Batteries (`/batteries`)
Battery asset management.

-   **GET** `/{serial_number}` - Get details of a specific battery.
-   **POST** `/` - Add/Register a new battery.
-   **GET** `/timeseries/battery-health/{battery_id}` - Get battery health history.

### 9. Swaps (`/swaps`)
Logic for swapping depleted batteries for charged ones.

-   **POST** `/request` - Initiate a swap request.
-   **POST** `/execute` - Confirm swap completion.
-   **POST** `/stations` - Find stations supporting swaps.
-   **GET** `/{rental_id}/suggestions` - Get swap suggestions based on usage.
-   **GET** `/{rental_id}/history` - Get swap history.
-   **GET** `/preferences` - Get user swap preferences.
-   **POST** `/preferences` - Set user swap preferences.

### 10. IoT & Devices (`/iot`)
Communication with smart hardware.

-   **GET** `/devices` - List user's paired devices.
-   **POST** `/devices` - Register/Pair a new device.
-   **POST** `/devices/{device_id}/command` - Send remote command (Lock/Unlock/Immobilize).
-   **POST** `/devices/{device_id}/pair` - Bluetooth pairing handshake.

### 11. Support (`/support`)
Customer service features.

-   **POST** `/tickets` - Create a support ticket.
-   **GET** `/tickets` - List my tickets.
-   **POST** `/tickets/{ticket_id}/attachment` - Upload file to ticket.
-   **POST** `/chat/start` - Start live chat session.
-   **POST** `/chat/{session_id}/message` - Send chat message.
-   **POST** `/chat/{session_id}/close` - End chat session.
-   **GET** `/faq` - List all FAQs.
-   **GET** `/faq/search` - Search FAQs.

### 12. Notifications (`/notifications`)
User alerts and messages.

-   **GET** `/` - List notifications.
-   **PUT** `/{notification_id}/read` - Mark specific notification as read.
-   **PATCH** `/read-all` - Mark all as read.
-   **DELETE** `/{notification_id}` - Delete a notification.
-   **POST** `/device-token` - Register FCM/APNS token for push notifications.

### 13. Favorites (`/favorites`)
-   **GET** `/` - List favorite stations.
-   **POST** `/{station_id}` - Add station to favorites.
-   **DELETE** `/{station_id}` - Remove station from favorites.

### 14. Analytics (`/analytics`)
-   **GET** `/dashboard` - User main aggregation dashboard.
-   **GET** `/rental-history` - Aggregated rental stats.
-   **GET** `/cost-analytics` - Spending analysis.
-   **GET** `/usage-patterns` - Battery usage insights.

### 15. Fraud & Security (`/fraud`)
-   **GET** `/users/{user_id}/risk-score` - Get risk profile.
-   **POST** `/verify/pan` - Validate PAN card.
-   **POST** `/verify/gst` - Validate GST number.
-   **POST** `/device/fingerprint` - Submit device fingerprinting data.
