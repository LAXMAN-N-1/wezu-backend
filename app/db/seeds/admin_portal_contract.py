from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScreenRequirement:
    screen: str
    route: str
    table: str
    min_rows: int
    rationale: str


ADMIN_PORTAL_CONTRACT: tuple[ScreenRequirement, ...] = (
    ScreenRequirement("Dashboard", "/dashboard", "users", 12, "Top-line user growth and totals."),
    ScreenRequirement("Dashboard", "/dashboard", "stations", 6, "Network KPIs and station summaries."),
    ScreenRequirement("Dashboard", "/dashboard", "batteries", 24, "Fleet utilization and health distribution."),
    ScreenRequirement("Dashboard", "/dashboard", "rentals", 12, "Trend charts, conversion funnel, recent activity."),
    ScreenRequirement("Dashboard", "/dashboard", "transactions", 20, "Revenue, payment, and activity cards."),
    ScreenRequirement("User Master", "/user-master", "users", 12, "Customer and staff list views."),
    ScreenRequirement("User Master", "/user-master/roles", "roles", 8, "RBAC role management."),
    ScreenRequirement("User Master", "/user-master/roles", "permissions", 24, "Permission catalog."),
    ScreenRequirement("User Master", "/user-master/groups", "admin_groups", 3, "Admin group listings."),
    ScreenRequirement("User Master", "/user-master/logs", "audit_logs", 12, "Account and RBAC audit timeline."),
    ScreenRequirement("User Master", "/user-master", "kyc_documents", 8, "KYC moderation queue."),
    ScreenRequirement("Locations", "/locations", "zones", 8, "City and zone filters for operating footprint."),
    ScreenRequirement("Fleet Batteries", "/fleet/batteries", "batteries", 24, "Battery inventory grid."),
    ScreenRequirement("Fleet Batteries", "/fleet/batteries", "battery_audit_logs", 18, "Battery history drawer."),
    ScreenRequirement("Fleet Stock", "/fleet/stock", "station_stock_configs", 6, "Station stock thresholds."),
    ScreenRequirement("Fleet Stock", "/fleet/stock", "reorder_requests", 4, "Reorder queue and alert states."),
    ScreenRequirement("Fleet Health", "/fleet/health", "battery_health_snapshots", 48, "Trend and detail charts."),
    ScreenRequirement("Fleet Health", "/fleet/health", "battery_health_alerts", 6, "Open critical battery alerts."),
    ScreenRequirement("Fleet Audit", "/fleet/audit", "battery_lifecycle_events", 18, "Fleet audit history."),
    ScreenRequirement("Fleet Audit", "/fleet/audit", "inventory_audit_logs", 12, "Inventory movement and custody trail."),
    ScreenRequirement("Stations", "/stations", "stations", 6, "Station listing and map."),
    ScreenRequirement("Stations", "/stations", "station_slots", 36, "Slot utilization and detail drawer."),
    ScreenRequirement("Stations", "/stations/maintenance", "maintenance_records", 6, "Maintenance timeline."),
    ScreenRequirement("Dealers", "/dealers", "dealer_profiles", 4, "Dealer master list."),
    ScreenRequirement("Dealers", "/dealers/registrations", "dealer_applications", 4, "Onboarding pipeline."),
    ScreenRequirement("Dealers", "/dealers/documents", "dealer_documents", 8, "Dealer document verification."),
    ScreenRequirement("Dealers", "/dealers/commissions", "commission_configs", 4, "Commission setup."),
    ScreenRequirement("Dealers", "/dealers/commissions", "commission_logs", 8, "Commission earnings."),
    ScreenRequirement("Rentals", "/rentals/active", "rentals", 12, "Active and historical rental views."),
    ScreenRequirement("Rentals", "/rentals/swaps", "swap_sessions", 4, "Swap management."),
    ScreenRequirement("Rentals", "/rentals/late-fees", "late_fees", 3, "Late fee operations."),
    ScreenRequirement("Finance", "/finance", "transactions", 20, "Transaction ledger."),
    ScreenRequirement("Finance", "/finance/invoices", "invoices", 12, "Invoice list and stats."),
    ScreenRequirement("Finance", "/finance/settlements", "settlements", 4, "Dealer/vendor settlement review."),
    ScreenRequirement("Logistics", "/logistics/orders", "delivery_orders", 6, "Order operations."),
    ScreenRequirement("Logistics", "/logistics/drivers", "driver_profiles", 4, "Driver roster."),
    ScreenRequirement("Logistics", "/logistics/routes", "delivery_routes", 3, "Route optimization views."),
    ScreenRequirement("Logistics", "/logistics/returns", "return_requests", 2, "Reverse logistics queue."),
    ScreenRequirement("Fleet Ops", "/fleet-ops/iot", "iot_devices", 18, "Device fleet status."),
    ScreenRequirement("Fleet Ops", "/fleet-ops/iot", "device_commands", 12, "Command history."),
    ScreenRequirement("Fleet Ops", "/fleet-ops/geofence", "geofence", 4, "Geofence rules."),
    ScreenRequirement("Fleet Ops", "/fleet-ops/alerts", "alerts", 6, "Operations alerts."),
    ScreenRequirement("BESS", "/bess", "bess_units", 2, "Energy storage overview."),
    ScreenRequirement("BESS", "/bess/monitoring", "bess_energy_logs", 16, "BESS monitoring charts."),
    ScreenRequirement("BESS", "/bess/grid", "bess_grid_events", 4, "Grid interaction events."),
    ScreenRequirement("BESS", "/bess/reports", "bess_reports", 4, "BESS report history."),
    ScreenRequirement("Support", "/support/tickets", "support_tickets", 8, "Ticket inbox."),
    ScreenRequirement("Support", "/support/tickets", "ticket_messages", 16, "Ticket conversation view."),
    ScreenRequirement("Support", "/support/knowledge", "faqs", 6, "Knowledge base listings."),
    ScreenRequirement("Notifications", "/notifications", "push_campaigns", 3, "Campaign management."),
    ScreenRequirement("Notifications", "/notifications/logs", "notification_logs", 10, "Delivery analytics."),
    ScreenRequirement("Notifications", "/notifications/config", "notification_configs", 4, "Provider configuration."),
    ScreenRequirement("CMS", "/cms/blogs", "blog", 4, "Blog management."),
    ScreenRequirement("CMS", "/cms/banners", "banners", 3, "Campaign banners."),
    ScreenRequirement("CMS", "/cms/legal", "legal_documents", 3, "Legal content."),
    ScreenRequirement("CMS", "/cms/media", "media_assets", 8, "Media library."),
    ScreenRequirement("Settings", "/settings", "system_configs", 6, "General settings."),
    ScreenRequirement("Settings", "/settings/features", "feature_flags", 6, "Feature toggles."),
    ScreenRequirement("Settings", "/settings/api-keys", "api_key_configs", 5, "API key management."),
    ScreenRequirement("Audit", "/audit/logs", "audit_logs", 12, "Audit logging."),
    ScreenRequirement("Audit", "/audit/security-events", "security_events", 6, "Security operations."),
    ScreenRequirement("Audit", "/audit/fraud", "risk_scores", 4, "Fraud risk review."),
)
