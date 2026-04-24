# Phase 0 Freeze Manifest

- Generated at: `2026-04-10T11:14:16.997345+00:00`
- Total live routes: **903**
- Total dead routes: **130**
- Total cycles: **36**
- Total boundary violations (router -> repository imports): **5**
- Total unowned models: **0**
- Total stale domain entries resolved: **8**

## Contract Gaps Status
- PASS: `app/api/v1/batteries.py:136` -> `MaintenanceService.get_maintenance_history`
- PASS: `app/api/v1/stations.py:194` -> `MaintenanceService.get_maintenance_schedule`
- PASS: `app/api/v1/logistics.py:82` -> `DriverService.get_driver_dashboard_stats`
- PASS: `app/api/v1/passkeys.py:159` -> `AuthService.create_session`

- All 4 contract methods implemented: **True**

## Contract Gap Tests
- PASS: `DATABASE_URL=sqlite:///./test_wezu.db REDIS_URL=redis://localhost:6379/0 SECRET_KEY=test_secret_for_ci_only ENVIRONMENT=testing /opt/homebrew/bin/python3.11 -m pytest -q tests/test_phase0_contract_gaps.py tests/test_service_contracts.py`
- Result: `5 passed in 1.07s`

## Dead Flow Inventory Coverage
- `app/api/admin/admin_alerts.py`: routes=0 status=`safe_to_mount` conflicts=0
- `app/api/admin/admin_analytics.py`: routes=0 status=`safe_to_mount` conflicts=0
- `app/api/admin/admin_roles.py`: routes=0 status=`safe_to_mount` conflicts=0
- `app/api/admin/admin_user_bulk.py`: routes=0 status=`safe_to_mount` conflicts=0
- `app/api/v1/dealer_commission.py`: routes=13 status=`safe_to_mount` conflicts=0
- `app/api/v1/dealer_documents.py`: routes=4 status=`safe_to_mount` conflicts=0
- `app/api/v1/dealer_kyc.py`: routes=5 status=`safe_to_mount` conflicts=0
- `app/api/v1/vendors.py`: routes=4 status=`safe_to_mount` conflicts=0

## Warning
- These configured dead-flow files were not found in tree: app/api/admin/admin_alerts.py, app/api/admin/admin_analytics.py, app/api/admin/admin_roles.py, app/api/admin/admin_user_bulk.py
