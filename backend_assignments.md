# Backend Team Assignments (Remaining Tasks Only)

The following tasks focus **only** on features and modules that are **not yet implemented** or require significant work to potentialize the existing codebase.

## 1. Ravi - Core Architecture & Identity Management (Advanced)
**Status:** Basic Auth & User models exist.
**Focus:** Enterprise Security & Role Management.
**Files:** `backend/app/api/v1/admin_rbac.py`, `backend/app/core/security.py`

### Tasks (Not Completed):
1.  **Granular RBAC Implementation**:
    *   Ensure `DEALER` and `DRIVER` roles have distinct permission scopes.
    *   Middleware to enforce: `Dealer` can only see *their* inventory; `Driver` can only see *assigned* tasks.
2.  **Audit Logging System**:
    *   Create a `UserActivityLog` table/model.
    *   Track critical actions: "User X unlocked Battery Y", "Admin Z banned User A".
3.  **Session Management**:
    *   Implement "Force Logout" (Revoke token) capability for banned users.
    *   Device Management: List active sessions for a user.

---

## 2. Sri Laxmi - Operations & IoT Logic (Real-time)
**Status:** Basic Station/Battery CRUD exists.
**Focus:** Intelligence & Hardware Communication.
**Files:** `backend/app/api/v1/iot.py`, `backend/app/services/station_service.py`

### Tasks (Not Completed):
1.  **Station Heartbeat & Health**:
    *   Implement logic to mark station as "OFFLINE" if no heartbeat received for 5 minutes.
    *   Alert generation: "Station X offline for 10m".
2.  **Battery Lifecycle Tracking**:
    *   Track `charge_cycles` and `state_of_health` (SOH).
    *   Logic to flag battery as "DAMAGED" if SOH < 70%.
3.  **Smart Charging Logic**:
    *   API to prioritize charging specific batteries based on predicted demand (AI/ML integration point).

---

## 3. Chandhu - Finance, Analytics & Logistics (Supply Chain)
**Status:** Basic Wallet & Transaction models exist.
**Focus:** Movement of Goods & Money.
**Files:** `backend/app/api/v1/logistics.py`, `backend/app/api/v1/analytics.py`

### Tasks (Not Completed):
1.  **Supply Chain Workflows**:
    *   **Manifest Creation**: Logic to bundle multiple batteries into a "Shipment".
    *   **Handover Verification**: API to verify QR scan at both ends (Warehouse -> Driver -> Station).
2.  **Dealer Settlements**:
    *   Automated job to calculate Dealer Commissions based on swaps at their stations.
    *   "Payout Request" API for dealers.
3.  **Advanced Analytics**:
    *   Aggregated Endpoints for Admin Dashboard:
        *   "Hourly Swap Rate"
        *   "Revenue Heatmap" (By region).
        *   "Battery Utilization" (Avg swaps per battery).
