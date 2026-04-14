# Backend Flow Inventory (Route-Derived)

## Snapshot
- Total registered routes (method+path): **943**
- Unique paths: **755**
- Duplicate path+method registrations: **34**

## By Method
- `DELETE`: 64
- `GET`: 470
- `PATCH`: 34
- `POST`: 292
- `PUT`: 83

## By Domain (Top 40)
- `dealer/portal`: 57
- `admin/rbac`: 46
- `logistics`: 37
- `auth`: 33
- `users`: 30
- `dealers`: 28
- `batteries`: 27
- `payments`: 25
- `catalog`: 24
- `admin/stations`: 23
- `stations`: 23
- `admin/cms`: 21
- `admin/users`: 19
- `rentals`: 19
- `support`: 19
- `notifications`: 17
- `dealer/analytics`: 16
- `admin/analytics`: 15
- `admin/dealers`: 15
- `wallet`: 15
- `admin/notifications`: 14
- `admin/support`: 14
- `orders`: 14
- `profile`: 14
- `admin/finance`: 12
- `admin/financial-reports`: 12
- `admin/bess`: 11
- `admin/kyc`: 11
- `admin/logistics`: 11
- `admin/batteries`: 10
- `admin/health`: 10
- `admin/iot`: 10
- `admin/settings`: 10
- `dealer-stations`: 10
- `dealer/campaigns`: 10
- `locations`: 10
- `admin/security`: 9
- `dealer/onboarding`: 9
- `admin/rentals`: 8
- `admin/stock`: 8

## Duplicate Path+Method Registrations
- `GET /api/v1/admin/rbac/hierarchy`
  - `app.api.v1.admin_rbac::get_role_hierarchy`
  - `app.api.v1.admin_rbac::get_role_hierarchy`
- `GET /api/v1/admin/rbac/permissions`
  - `app.api.v1.admin_rbac::read_permissions`
  - `app.api.v1.admin_rbac::read_permissions`
- `POST /api/v1/admin/rbac/permissions`
  - `app.api.v1.admin_rbac::create_permission`
  - `app.api.v1.admin_rbac::create_permission`
- `GET /api/v1/admin/rbac/roles`
  - `app.api.v1.admin_rbac::read_roles`
  - `app.api.v1.admin_rbac::read_roles`
- `POST /api/v1/admin/rbac/roles`
  - `app.api.v1.admin_rbac::create_role`
  - `app.api.v1.admin_rbac::create_role`
- `POST /api/v1/admin/rbac/roles/bulk-assign`
  - `app.api.v1.admin_rbac::bulk_assign_roles`
  - `app.api.v1.admin_rbac::bulk_assign_roles`
- `DELETE /api/v1/admin/rbac/roles/{role_id}`
  - `app.api.v1.admin_rbac::delete_role`
  - `app.api.v1.admin_rbac::delete_role`
- `GET /api/v1/admin/rbac/roles/{role_id}`
  - `app.api.v1.admin_rbac::get_role_detail`
  - `app.api.v1.admin_rbac::get_role_detail`
- `PUT /api/v1/admin/rbac/roles/{role_id}`
  - `app.api.v1.admin_rbac::update_role`
  - `app.api.v1.admin_rbac::update_role`
- `POST /api/v1/admin/rbac/roles/{role_id}/duplicate`
  - `app.api.v1.admin_rbac::duplicate_role`
  - `app.api.v1.admin_rbac::duplicate_role`
- `GET /api/v1/admin/rbac/roles/{role_id}/permissions`
  - `app.api.v1.admin_rbac::get_role_permissions`
  - `app.api.v1.admin_rbac::get_role_permissions`
- `POST /api/v1/admin/rbac/roles/{role_id}/permissions`
  - `app.api.v1.admin_rbac::assign_permissions_to_role`
  - `app.api.v1.admin_rbac::assign_permissions_to_role`
- `GET /api/v1/admin/rbac/roles/{role_id}/users`
  - `app.api.v1.admin_rbac::get_users_by_role`
  - `app.api.v1.admin_rbac::get_users_by_role`
- `POST /api/v1/admin/rbac/users/{source_user_id}/roles/transfer`
  - `app.api.v1.admin_rbac::transfer_role_assignment`
  - `app.api.v1.admin_rbac::transfer_role_assignment`
- `GET /api/v1/admin/rbac/users/{user_id}/access-paths`
  - `app.api.v1.admin_rbac::get_user_access_paths`
  - `app.api.v1.admin_rbac::get_user_access_paths`
- `POST /api/v1/admin/rbac/users/{user_id}/access-paths`
  - `app.api.v1.admin_rbac::assign_access_path`
  - `app.api.v1.admin_rbac::assign_access_path`
- `DELETE /api/v1/admin/rbac/users/{user_id}/access-paths/{path_id}`
  - `app.api.v1.admin_rbac::remove_access_path`
  - `app.api.v1.admin_rbac::remove_access_path`
- `PUT /api/v1/admin/rbac/users/{user_id}/access-paths/{path_id}`
  - `app.api.v1.admin_rbac::update_access_path`
  - `app.api.v1.admin_rbac::update_access_path`
- `GET /api/v1/admin/rbac/users/{user_id}/permissions`
  - `app.api.v1.admin_rbac::get_user_permissions`
  - `app.api.v1.admin_rbac::get_user_permissions`
- `GET /api/v1/admin/rbac/users/{user_id}/permissions/check`
  - `app.api.v1.admin_rbac::check_user_permission`
  - `app.api.v1.admin_rbac::check_user_permission`
- `GET /api/v1/admin/rbac/users/{user_id}/roles`
  - `app.api.v1.admin_rbac::get_user_roles`
  - `app.api.v1.admin_rbac::get_user_roles`
- `POST /api/v1/admin/rbac/users/{user_id}/roles`
  - `app.api.v1.admin_rbac::assign_roles_to_user`
  - `app.api.v1.admin_rbac::assign_roles_to_user`
- `DELETE /api/v1/admin/rbac/users/{user_id}/roles/{role_id}`
  - `app.api.v1.admin_rbac::remove_role_from_user`
  - `app.api.v1.admin_rbac::remove_role_from_user`
- `POST /api/v1/admin/users/{user_id}/reset-password`
  - `app.api.admin.users::reset_user_password`
  - `app.api.v1.admin_users::admin_reset_password`
- `POST /api/v1/notifications/device-token`
  - `app.api.v1.notifications::register_device_token`
  - `app.api.v1.notifications_enhanced::register_device_token`
- `PATCH /api/v1/notifications/read-all`
  - `app.api.v1.notifications::mark_all_notifications_read`
  - `app.api.v1.notifications_enhanced::mark_all_notifications_read`
- `POST /api/v1/payments/methods`
  - `app.api.v1.payments::add_payment_method`
  - `app.api.v1.payments_enhanced::add_payment_method`
- `DELETE /api/v1/payments/methods/{method_id}`
  - `app.api.v1.payments::delete_payment_method`
  - `app.api.v1.payments_enhanced::delete_payment_method`
- `GET /api/v1/rentals/{rental_id}/receipt`
  - `app.api.v1.rentals::get_rental_receipt_v2`
  - `app.api.v1.rentals_enhanced::get_rental_receipt`
- `POST /api/v1/rentals/{rental_id}/report-issue`
  - `app.api.v1.rentals::report_rental_issue`
  - `app.api.v1.rentals_enhanced::report_rental_issue`
- `GET /api/v1/support/faq/search`
  - `app.api.v1.support::search_faq`
  - `app.api.v1.support_enhanced::search_faq`
- `POST /api/v1/support/tickets/{ticket_id}/attachment`
  - `app.api.v1.support::upload_ticket_attachment`
  - `app.api.v1.support_enhanced::upload_ticket_attachment`
- `GET /api/v1/wallet/cashback`
  - `app.api.v1.wallet::get_cashback_history`
  - `app.api.v1.wallet_enhanced::get_cashback_history`
- `POST /api/v1/wallet/transfer`
  - `app.api.v1.wallet::transfer_to_user`
  - `app.api.v1.wallet_enhanced::transfer_to_user`

## Full Route Listing by Domain

### .well-known (1)
- `GET /.well-known/assetlinks.json` | `app.main::android_assetlinks` | tags: -

### aadhaar-verify (1)
- `POST /api/v1/aadhaar-verify` | `app.api.v1.kyc::verify_aadhaar` | tags: KYC

### admin/analytics (15)
- `GET /api/v1/admin/analytics/battery-health-distribution` | `app.api.v1.admin.analytics::get_battery_health_distribution` | tags: Admin: Analytics
- `GET /api/v1/admin/analytics/conversion-funnel` | `app.api.v1.admin.analytics::get_conversion_funnel` | tags: Admin: Analytics
- `GET /api/v1/admin/analytics/dashboard` | `app.api.v1.admin.analytics::get_admin_dashboard` | tags: Admin: Analytics
- `GET /api/v1/admin/analytics/demand-forecast` | `app.api.v1.admin.analytics::get_demand_forecast` | tags: Admin: Analytics
- `GET /api/v1/admin/analytics/export` | `app.api.v1.admin.analytics::export_analytics_report` | tags: Admin: Analytics
- `GET /api/v1/admin/analytics/inventory-status` | `app.api.v1.admin.analytics::get_global_inventory_status` | tags: Admin: Analytics
- `GET /api/v1/admin/analytics/overview` | `app.api.v1.admin.analytics::get_platform_overview` | tags: Admin: Analytics
- `GET /api/v1/admin/analytics/recent-activity` | `app.api.v1.admin.analytics::get_recent_activity` | tags: Admin: Analytics
- `GET /api/v1/admin/analytics/revenue/by-battery-type` | `app.api.v1.admin.analytics::get_revenue_by_battery_type` | tags: Admin: Analytics
- `GET /api/v1/admin/analytics/revenue/by-region` | `app.api.v1.admin.analytics::get_revenue_by_region` | tags: Admin: Analytics
- `GET /api/v1/admin/analytics/revenue/by-station` | `app.api.v1.admin.analytics::get_revenue_by_station` | tags: Admin: Analytics
- `GET /api/v1/admin/analytics/top-stations` | `app.api.v1.admin.analytics::get_top_stations` | tags: Admin: Analytics
- `GET /api/v1/admin/analytics/trends` | `app.api.v1.admin.analytics::get_platform_trends` | tags: Admin: Analytics
- `GET /api/v1/admin/analytics/user-behavior` | `app.api.v1.admin.analytics::get_user_behavior` | tags: Admin: Analytics
- `GET /api/v1/admin/analytics/user-growth` | `app.api.v1.admin.analytics::get_user_growth_metrics` | tags: Admin: Analytics

### admin/audit-logs (4)
- `GET /api/v1/admin/audit-logs/` | `app.api.v1.admin_audit::list_audit_logs` | tags: Admin: Audit
- `GET /api/v1/admin/audit-logs/export/csv` | `app.api.v1.admin_audit::export_audit_csv` | tags: Admin: Audit
- `GET /api/v1/admin/audit-logs/export/json` | `app.api.v1.admin_audit::export_audit_json` | tags: Admin: Audit
- `GET /api/v1/admin/audit-logs/stats` | `app.api.v1.admin_audit::audit_log_stats` | tags: Admin: Audit

### admin/audit-trails (3)
- `GET /api/v1/admin/audit-trails/` | `app.api.admin.audit_trails::list_audit_trails` | tags: Admin: Core, Admin Audit Trails
- `GET /api/v1/admin/audit-trails/stats` | `app.api.admin.audit_trails::get_audit_stats` | tags: Admin: Core, Admin Audit Trails
- `GET /api/v1/admin/audit-trails/{entry_id}` | `app.api.admin.audit_trails::get_audit_detail` | tags: Admin: Core, Admin Audit Trails

### admin/banners (4)
- `GET /api/v1/admin/banners/` | `app.api.v1.admin.banners::read_banners` | tags: Admin: Banners
- `POST /api/v1/admin/banners/` | `app.api.v1.admin.banners::create_banner` | tags: Admin: Banners
- `DELETE /api/v1/admin/banners/{banner_id}` | `app.api.v1.admin.banners::delete_banner` | tags: Admin: Banners
- `PATCH /api/v1/admin/banners/{banner_id}` | `app.api.v1.admin.banners::update_banner` | tags: Admin: Banners

### admin/batteries (10)
- `GET /api/v1/admin/batteries` | `app.api.admin.batteries::list_batteries` | tags: Admin: Core, Admin Batteries
- `POST /api/v1/admin/batteries` | `app.api.admin.batteries::create_battery` | tags: Admin: Core, Admin Batteries
- `POST /api/v1/admin/batteries/bulk-update` | `app.api.admin.batteries::bulk_update_batteries` | tags: Admin: Core, Admin Batteries
- `GET /api/v1/admin/batteries/export` | `app.api.admin.batteries::export_batteries` | tags: Admin: Core, Admin Batteries
- `POST /api/v1/admin/batteries/import` | `app.api.admin.batteries::import_batteries` | tags: Admin: Core, Admin Batteries
- `GET /api/v1/admin/batteries/summary` | `app.api.admin.batteries::get_battery_summary` | tags: Admin: Core, Admin Batteries
- `GET /api/v1/admin/batteries/{battery_id}` | `app.api.admin.batteries::get_battery_detail` | tags: Admin: Core, Admin Batteries
- `PATCH /api/v1/admin/batteries/{battery_id}` | `app.api.admin.batteries::update_battery` | tags: Admin: Core, Admin Batteries
- `GET /api/v1/admin/batteries/{battery_id}/health-history` | `app.api.admin.batteries::get_battery_health_history` | tags: Admin: Core, Admin Batteries
- `GET /api/v1/admin/batteries/{battery_id}/history` | `app.api.admin.batteries::get_battery_audit_logs` | tags: Admin: Core, Admin Batteries

### admin/bess (11)
- `GET /api/v1/admin/bess/energy-logs` | `app.api.admin.bess::list_energy_logs` | tags: Admin: Core, Admin BESS
- `GET /api/v1/admin/bess/energy-logs/summary` | `app.api.admin.bess::energy_summary` | tags: Admin: Core, Admin BESS
- `GET /api/v1/admin/bess/grid-events` | `app.api.admin.bess::list_grid_events` | tags: Admin: Core, Admin BESS
- `POST /api/v1/admin/bess/grid-events` | `app.api.admin.bess::create_grid_event` | tags: Admin: Core, Admin BESS
- `PATCH /api/v1/admin/bess/grid-events/{event_id}` | `app.api.admin.bess::update_grid_event_status` | tags: Admin: Core, Admin BESS
- `GET /api/v1/admin/bess/overview` | `app.api.admin.bess::get_bess_overview` | tags: Admin: Core, Admin BESS
- `GET /api/v1/admin/bess/reports` | `app.api.admin.bess::list_reports` | tags: Admin: Core, Admin BESS
- `GET /api/v1/admin/bess/reports/kpi` | `app.api.admin.bess::reports_kpi` | tags: Admin: Core, Admin BESS
- `GET /api/v1/admin/bess/units` | `app.api.admin.bess::list_bess_units` | tags: Admin: Core, Admin BESS
- `POST /api/v1/admin/bess/units` | `app.api.admin.bess::create_bess_unit` | tags: Admin: Core, Admin BESS
- `GET /api/v1/admin/bess/units/{unit_id}` | `app.api.admin.bess::get_bess_unit` | tags: Admin: Core, Admin BESS

### admin/blogs (5)
- `GET /api/v1/admin/blogs/` | `app.api.v1.admin.blogs::read_blogs` | tags: Admin: Blogs
- `POST /api/v1/admin/blogs/` | `app.api.v1.admin.blogs::create_blog` | tags: Admin: Blogs
- `DELETE /api/v1/admin/blogs/{blog_id}` | `app.api.v1.admin.blogs::delete_blog` | tags: Admin: Blogs
- `GET /api/v1/admin/blogs/{blog_id}` | `app.api.v1.admin.blogs::read_blog` | tags: Admin: Blogs
- `PATCH /api/v1/admin/blogs/{blog_id}` | `app.api.v1.admin.blogs::update_blog` | tags: Admin: Blogs

### admin/cms (21)
- `GET /api/v1/admin/cms/banners/` | `app.api.admin.cms::list_banners` | tags: Admin: Core, Admin CMS
- `POST /api/v1/admin/cms/banners/` | `app.api.admin.cms::create_banner` | tags: Admin: Core, Admin CMS
- `DELETE /api/v1/admin/cms/banners/{banner_id}` | `app.api.admin.cms::delete_banner` | tags: Admin: Core, Admin CMS
- `PATCH /api/v1/admin/cms/banners/{banner_id}` | `app.api.admin.cms::update_banner` | tags: Admin: Core, Admin CMS
- `GET /api/v1/admin/cms/blogs/` | `app.api.admin.cms::list_blogs` | tags: Admin: Core, Admin CMS
- `POST /api/v1/admin/cms/blogs/` | `app.api.admin.cms::create_blog` | tags: Admin: Core, Admin CMS
- `DELETE /api/v1/admin/cms/blogs/{blog_id}` | `app.api.admin.cms::delete_blog` | tags: Admin: Core, Admin CMS
- `GET /api/v1/admin/cms/blogs/{blog_id}` | `app.api.admin.cms::get_blog` | tags: Admin: Core, Admin CMS
- `PUT /api/v1/admin/cms/blogs/{blog_id}` | `app.api.admin.cms::update_blog` | tags: Admin: Core, Admin CMS
- `GET /api/v1/admin/cms/faqs/` | `app.api.admin.cms::list_faqs` | tags: Admin: Core, Admin CMS
- `POST /api/v1/admin/cms/faqs/` | `app.api.admin.cms::create_faq` | tags: Admin: Core, Admin CMS
- `DELETE /api/v1/admin/cms/faqs/{faq_id}` | `app.api.admin.cms::delete_faq` | tags: Admin: Core, Admin CMS
- `PUT /api/v1/admin/cms/faqs/{faq_id}` | `app.api.admin.cms::update_faq` | tags: Admin: Core, Admin CMS
- `GET /api/v1/admin/cms/legal/` | `app.api.admin.cms::list_legal_docs` | tags: Admin: Core, Admin CMS
- `POST /api/v1/admin/cms/legal/` | `app.api.admin.cms::create_legal_doc` | tags: Admin: Core, Admin CMS
- `DELETE /api/v1/admin/cms/legal/{doc_id}` | `app.api.admin.cms::delete_legal_doc` | tags: Admin: Core, Admin CMS
- `PATCH /api/v1/admin/cms/legal/{doc_id}` | `app.api.admin.cms::update_legal_doc` | tags: Admin: Core, Admin CMS
- `GET /api/v1/admin/cms/media/` | `app.api.admin.cms::list_media_assets` | tags: Admin: Core, Admin CMS
- `POST /api/v1/admin/cms/media/` | `app.api.admin.cms::create_media_asset` | tags: Admin: Core, Admin CMS
- `DELETE /api/v1/admin/cms/media/{asset_id}` | `app.api.admin.cms::delete_media_asset` | tags: Admin: Core, Admin CMS
- `PATCH /api/v1/admin/cms/media/{asset_id}` | `app.api.admin.cms::update_media_asset` | tags: Admin: Core, Admin CMS

### admin/dealers (15)
- `GET /api/v1/admin/dealers/` | `app.api.v1.admin_dealers::list_dealers` | tags: Admin: Dealers
- `GET /api/v1/admin/dealers/applications` | `app.api.v1.admin_dealers::list_applications` | tags: Admin: Dealers
- `PUT /api/v1/admin/dealers/applications/{app_id}/stage` | `app.api.v1.admin_dealers::update_application_stage` | tags: Admin: Dealers
- `GET /api/v1/admin/dealers/commissions/configs` | `app.api.v1.admin_dealers::list_commission_configs` | tags: Admin: Dealers
- `POST /api/v1/admin/dealers/commissions/configs` | `app.api.v1.admin_dealers::create_commission_config` | tags: Admin: Dealers
- `PUT /api/v1/admin/dealers/commissions/configs/{config_id}` | `app.api.v1.admin_dealers::update_commission_config` | tags: Admin: Dealers
- `GET /api/v1/admin/dealers/commissions/logs` | `app.api.v1.admin_dealers::list_commission_logs` | tags: Admin: Dealers
- `GET /api/v1/admin/dealers/commissions/stats` | `app.api.v1.admin_dealers::get_commission_stats` | tags: Admin: Dealers
- `POST /api/v1/admin/dealers/create` | `app.api.v1.admin_dealers::create_dealer` | tags: Admin: Dealers
- `GET /api/v1/admin/dealers/documents/all` | `app.api.v1.admin_dealers::list_all_documents` | tags: Admin: Dealers
- `PUT /api/v1/admin/dealers/documents/{doc_id}/verify` | `app.api.v1.admin_dealers::verify_document` | tags: Admin: Dealers
- `GET /api/v1/admin/dealers/kyc` | `app.api.v1.admin_dealers::list_kyc_documents` | tags: Admin: Dealers
- `GET /api/v1/admin/dealers/stats` | `app.api.v1.admin_dealers::get_dealer_stats` | tags: Admin: Dealers
- `GET /api/v1/admin/dealers/{dealer_id}` | `app.api.v1.admin_dealers::get_dealer_detail` | tags: Admin: Dealers
- `PUT /api/v1/admin/dealers/{dealer_id}` | `app.api.v1.admin_dealers::update_dealer` | tags: Admin: Dealers

### admin/finance (12)
- `GET /api/v1/admin/finance/dashboard` | `app.api.admin.finance::get_finance_dashboard` | tags: Admin: Core, Admin Finance
- `GET /api/v1/admin/finance/invoices` | `app.api.admin.finance::list_invoices` | tags: Admin: Core, Admin Finance
- `GET /api/v1/admin/finance/invoices/stats` | `app.api.admin.finance::get_invoice_stats` | tags: Admin: Core, Admin Finance
- `GET /api/v1/admin/finance/profit/analysis` | `app.api.admin.finance::get_profit_analysis` | tags: Admin: Core, Admin Finance
- `POST /api/v1/admin/finance/refunds` | `app.api.admin.finance::initiate_refund` | tags: Admin: Core, Admin Finance
- `GET /api/v1/admin/finance/settlements` | `app.api.admin.finance::list_settlements` | tags: Admin: Core, Admin Finance
- `GET /api/v1/admin/finance/settlements/stats` | `app.api.admin.finance::get_settlement_stats` | tags: Admin: Core, Admin Finance
- `PUT /api/v1/admin/finance/settlements/{settlement_id}/approve` | `app.api.admin.finance::approve_settlement` | tags: Admin: Core, Admin Finance
- `GET /api/v1/admin/finance/transactions` | `app.api.admin.finance::list_transactions` | tags: Admin: Core, Admin Finance
- `GET /api/v1/admin/finance/transactions/stats` | `app.api.admin.finance::get_transaction_stats` | tags: Admin: Core, Admin Finance
- `GET /api/v1/admin/finance/withdrawals` | `app.api.admin.finance::list_withdrawal_requests` | tags: Admin: Core, Admin Finance
- `PUT /api/v1/admin/finance/withdrawals/{request_id}/approve` | `app.api.admin.finance::approve_withdrawal` | tags: Admin: Core, Admin Finance

### admin/financial-reports (12)
- `GET /api/v1/admin/financial-reports/export/csv` | `app.api.v1.admin_financial_reports::export_report_csv` | tags: Admin: Financial Reports
- `GET /api/v1/admin/financial-reports/export/json` | `app.api.v1.admin_financial_reports::export_report_json` | tags: Admin: Financial Reports
- `POST /api/v1/admin/financial-reports/generate` | `app.api.v1.admin_financial_reports::generate_report` | tags: Admin: Financial Reports
- `GET /api/v1/admin/financial-reports/history` | `app.api.v1.admin_financial_reports::list_reports` | tags: Admin: Financial Reports
- `GET /api/v1/admin/financial-reports/reconciliation` | `app.api.v1.admin_financial_reports::get_reconciliation_report` | tags: Admin: Financial Reports
- `GET /api/v1/admin/financial-reports/revenue` | `app.api.v1.admin_financial_reports::get_revenue_report` | tags: Admin: Financial Reports
- `GET /api/v1/admin/financial-reports/revenue/comparison` | `app.api.v1.admin_financial_reports::get_revenue_comparison` | tags: Admin: Financial Reports
- `GET /api/v1/admin/financial-reports/revenue/forecast` | `app.api.v1.admin_financial_reports::get_revenue_forecast` | tags: Admin: Financial Reports
- `GET /api/v1/admin/financial-reports/revenue/forecast/profitability` | `app.api.v1.admin_financial_reports::get_profitability_forecast` | tags: Admin: Financial Reports
- `GET /api/v1/admin/financial-reports/revenue/margins` | `app.api.v1.admin_financial_reports::get_profit_margins` | tags: Admin: Financial Reports
- `GET /api/v1/admin/financial-reports/revenue/trends` | `app.api.v1.admin_financial_reports::get_revenue_trends` | tags: Admin: Financial Reports
- `GET /api/v1/admin/financial-reports/{report_id}` | `app.api.v1.admin_financial_reports::get_report_by_id` | tags: Admin: Financial Reports

### admin/fraud (7)
- `GET /api/v1/admin/fraud/blacklist` | `app.api.admin.fraud::get_blacklist` | tags: Admin: Core, Admin Fraud
- `POST /api/v1/admin/fraud/blacklist` | `app.api.admin.fraud::add_to_blacklist` | tags: Admin: Core, Admin Fraud
- `DELETE /api/v1/admin/fraud/blacklist/{id}` | `app.api.admin.fraud::remove_from_blacklist` | tags: Admin: Core, Admin Fraud
- `GET /api/v1/admin/fraud/device-fingerprints` | `app.api.admin.fraud::get_device_fingerprints` | tags: Admin: Core, Admin Fraud
- `GET /api/v1/admin/fraud/duplicate-accounts` | `app.api.admin.fraud::get_duplicate_accounts` | tags: Admin: Core, Admin Fraud
- `POST /api/v1/admin/fraud/duplicate-accounts/{id}/action` | `app.api.admin.fraud::handle_duplicate_account` | tags: Admin: Core, Admin Fraud
- `GET /api/v1/admin/fraud/high-risk-users` | `app.api.admin.fraud::get_high_risk_users` | tags: Admin: Core, Admin Fraud

### admin/groups (4)
- `GET /api/v1/admin/groups/` | `app.api.admin.admin_groups::read_admin_groups` | tags: Admin: Core, Admin Groups
- `POST /api/v1/admin/groups/` | `app.api.admin.admin_groups::create_admin_group` | tags: Admin: Core, Admin Groups
- `DELETE /api/v1/admin/groups/{group_id}` | `app.api.admin.admin_groups::delete_admin_group` | tags: Admin: Core, Admin Groups
- `PUT /api/v1/admin/groups/{group_id}` | `app.api.admin.admin_groups::update_admin_group` | tags: Admin: Core, Admin Groups

### admin/health (10)
- `GET /api/v1/admin/health/alerts` | `app.api.admin.health::get_health_alerts` | tags: Admin: Core, Admin Battery Health
- `POST /api/v1/admin/health/alerts/{alert_id}/resolve` | `app.api.admin.health::resolve_health_alert` | tags: Admin: Core, Admin Battery Health
- `GET /api/v1/admin/health/analytics` | `app.api.admin.health::get_health_analytics` | tags: Admin: Core, Admin Battery Health
- `GET /api/v1/admin/health/batteries` | `app.api.admin.health::get_health_batteries` | tags: Admin: Core, Admin Battery Health
- `GET /api/v1/admin/health/batteries/{battery_id}` | `app.api.admin.health::get_health_battery_detail` | tags: Admin: Core, Admin Battery Health
- `POST /api/v1/admin/health/batteries/{battery_id}/snapshot` | `app.api.admin.health::record_health_snapshot` | tags: Admin: Core, Admin Battery Health
- `GET /api/v1/admin/health/batteries/{battery_id}/snapshots` | `app.api.admin.health::get_battery_snapshots` | tags: Admin: Core, Admin Battery Health
- `GET /api/v1/admin/health/maintenance` | `app.api.admin.health::get_maintenance_list` | tags: Admin: Core, Admin Battery Health
- `POST /api/v1/admin/health/maintenance` | `app.api.admin.health::schedule_maintenance` | tags: Admin: Core, Admin Battery Health
- `GET /api/v1/admin/health/overview` | `app.api.admin.health::get_health_overview` | tags: Admin: Core, Admin Battery Health

### admin/invoices (2)
- `GET /api/v1/admin/invoices/` | `app.api.v1.admin_invoices::list_admin_invoices` | tags: Admin: Invoices
- `GET /api/v1/admin/invoices/{invoice_id}/pdf` | `app.api.v1.admin_invoices::download_invoice_pdf` | tags: Admin: Invoices

### admin/iot (10)
- `GET /api/v1/admin/iot/alerts` | `app.api.admin.iot::list_alerts` | tags: Admin: Core, Admin IoT
- `PUT /api/v1/admin/iot/alerts/{alert_id}/acknowledge` | `app.api.admin.iot::acknowledge_alert` | tags: Admin: Core, Admin IoT
- `GET /api/v1/admin/iot/batteries/health` | `app.api.admin.iot::get_battery_health_overview` | tags: Admin: Core, Admin IoT
- `POST /api/v1/admin/iot/commands` | `app.api.admin.iot::send_device_command` | tags: Admin: Core, Admin IoT
- `GET /api/v1/admin/iot/commands/history` | `app.api.admin.iot::get_command_history` | tags: Admin: Core, Admin IoT
- `GET /api/v1/admin/iot/devices` | `app.api.admin.iot::list_iot_devices` | tags: Admin: Core, Admin IoT
- `GET /api/v1/admin/iot/geofences` | `app.api.admin.iot::list_geofences` | tags: Admin: Core, Admin IoT
- `POST /api/v1/admin/iot/geofences` | `app.api.admin.iot::create_geofence` | tags: Admin: Core, Admin IoT
- `GET /api/v1/admin/iot/stats` | `app.api.admin.iot::get_iot_stats` | tags: Admin: Core, Admin IoT
- `GET /api/v1/admin/iot/telematics/{battery_id}` | `app.api.admin.iot::get_battery_telematics` | tags: Admin: Core, Admin IoT

### admin/jobs (7)
- `GET /api/v1/admin/jobs/` | `app.api.admin.jobs::list_jobs` | tags: Admin: Core, Admin Jobs
- `GET /api/v1/admin/jobs/executions/recent` | `app.api.admin.jobs::get_recent_executions` | tags: Admin: Core, Admin Jobs
- `GET /api/v1/admin/jobs/{job_id}` | `app.api.admin.jobs::get_job` | tags: Admin: Core, Admin Jobs
- `PUT /api/v1/admin/jobs/{job_id}` | `app.api.admin.jobs::update_job` | tags: Admin: Core, Admin Jobs
- `GET /api/v1/admin/jobs/{job_id}/history` | `app.api.admin.jobs::get_job_history` | tags: Admin: Core, Admin Jobs
- `GET /api/v1/admin/jobs/{job_id}/logs/{execution_id}` | `app.api.admin.jobs::get_execution_logs` | tags: Admin: Core, Admin Jobs
- `POST /api/v1/admin/jobs/{job_id}/run` | `app.api.admin.jobs::trigger_job` | tags: Admin: Core, Admin Jobs

### admin/kyc (11)
- `GET /api/v1/admin/kyc/dashboard` | `app.api.v1.admin_kyc::get_kyc_admin_dashboard` | tags: Admin: KYC
- `GET /api/v1/admin/kyc/documents` | `app.api.v1.admin_kyc::list_kyc_documents` | tags: Admin: KYC
- `POST /api/v1/admin/kyc/documents/{doc_id}/approve` | `app.api.v1.admin_kyc::approve_document` | tags: Admin: KYC
- `POST /api/v1/admin/kyc/documents/{doc_id}/reject` | `app.api.v1.admin_kyc::reject_document` | tags: Admin: KYC
- `GET /api/v1/admin/kyc/pending` | `app.api.v1.admin_kyc::get_pending_kyc_queue` | tags: Admin: KYC
- `GET /api/v1/admin/kyc/stats` | `app.api.v1.admin_kyc::get_kyc_stats` | tags: Admin: KYC
- `POST /api/v1/admin/kyc/video-kyc/{session_id}/complete` | `app.api.v1.admin_kyc::complete_video_kyc` | tags: Admin: KYC
- `PUT /api/v1/admin/kyc/{user_id}/approve` | `app.api.v1.admin_kyc::approve_user_kyc` | tags: Admin: KYC
- `POST /api/v1/admin/kyc/{user_id}/reject` | `app.api.v1.admin_kyc::reject_kyc_submission` | tags: Admin: KYC
- `PUT /api/v1/admin/kyc/{user_id}/reject` | `app.api.v1.admin_kyc::reject_user_kyc` | tags: Admin: KYC
- `POST /api/v1/admin/kyc/{user_id}/verify` | `app.api.v1.admin_kyc::verify_kyc_submission` | tags: Admin: KYC

### admin/kyc-docs (5)
- `GET /api/v1/admin/kyc-docs/` | `app.api.admin.kyc_admin::list_kyc_documents` | tags: Admin: Core, Admin KYC Documents
- `GET /api/v1/admin/kyc-docs/stats` | `app.api.admin.kyc_admin::get_kyc_stats` | tags: Admin: Core, Admin KYC Documents
- `GET /api/v1/admin/kyc-docs/{doc_id}` | `app.api.admin.kyc_admin::get_document_detail` | tags: Admin: Core, Admin KYC Documents
- `PUT /api/v1/admin/kyc-docs/{doc_id}/approve` | `app.api.admin.kyc_admin::approve_document` | tags: Admin: Core, Admin KYC Documents
- `PUT /api/v1/admin/kyc-docs/{doc_id}/reject` | `app.api.admin.kyc_admin::reject_document` | tags: Admin: Core, Admin KYC Documents

### admin/legal (5)
- `GET /api/v1/admin/legal/` | `app.api.v1.admin.legal::read_legal_documents` | tags: Admin: Legal
- `POST /api/v1/admin/legal/` | `app.api.v1.admin.legal::create_legal_document` | tags: Admin: Legal
- `DELETE /api/v1/admin/legal/{doc_id}` | `app.api.v1.admin.legal::delete_legal_document` | tags: Admin: Legal
- `GET /api/v1/admin/legal/{doc_id}` | `app.api.v1.admin.legal::read_legal_document` | tags: Admin: Legal
- `PATCH /api/v1/admin/legal/{doc_id}` | `app.api.v1.admin.legal::update_legal_document` | tags: Admin: Legal

### admin/logistics (11)
- `GET /api/v1/admin/logistics/drivers` | `app.api.admin.logistics::list_drivers` | tags: Admin: Core, Admin Logistics
- `GET /api/v1/admin/logistics/drivers/stats` | `app.api.admin.logistics::get_driver_stats` | tags: Admin: Core, Admin Logistics
- `GET /api/v1/admin/logistics/orders` | `app.api.admin.logistics::list_delivery_orders` | tags: Admin: Core, Admin Logistics
- `POST /api/v1/admin/logistics/orders` | `app.api.admin.logistics::create_delivery_order` | tags: Admin: Core, Admin Logistics
- `GET /api/v1/admin/logistics/orders/stats` | `app.api.admin.logistics::get_order_stats` | tags: Admin: Core, Admin Logistics
- `PUT /api/v1/admin/logistics/orders/{order_id}/status` | `app.api.admin.logistics::update_order_status` | tags: Admin: Core, Admin Logistics
- `GET /api/v1/admin/logistics/returns` | `app.api.admin.logistics::list_returns` | tags: Admin: Core, Admin Logistics
- `GET /api/v1/admin/logistics/returns/stats` | `app.api.admin.logistics::get_return_stats` | tags: Admin: Core, Admin Logistics
- `PUT /api/v1/admin/logistics/returns/{return_id}/status` | `app.api.admin.logistics::update_return_status` | tags: Admin: Core, Admin Logistics
- `GET /api/v1/admin/logistics/routes` | `app.api.admin.logistics::list_routes` | tags: Admin: Core, Admin Logistics
- `GET /api/v1/admin/logistics/tracking` | `app.api.admin.logistics::get_live_tracking` | tags: Admin: Core, Admin Logistics

### admin/monitoring (6)
- `GET /api/v1/admin/monitoring/database/stats` | `app.api.admin.monitoring::database_stats` | tags: Admin: Core, Admin Monitoring
- `GET /api/v1/admin/monitoring/errors` | `app.api.admin.monitoring::error_logs` | tags: Admin: Core, Admin Monitoring
- `GET /api/v1/admin/monitoring/health` | `app.api.admin.monitoring::system_health` | tags: Admin: Core, Admin Monitoring
- `GET /api/v1/admin/monitoring/metrics` | `app.api.admin.monitoring::performance_metrics` | tags: Admin: Core, Admin Monitoring
- `GET /api/v1/admin/monitoring/performance/api` | `app.api.admin.monitoring::api_performance` | tags: Admin: Core, Admin Monitoring
- `GET /api/v1/admin/monitoring/uptime` | `app.api.admin.monitoring::uptime_tracking` | tags: Admin: Core, Admin Monitoring

### admin/notifications (14)
- `GET /api/v1/admin/notifications/campaigns` | `app.api.admin.notifications::list_campaigns` | tags: Admin: Core, Admin Notifications
- `POST /api/v1/admin/notifications/campaigns` | `app.api.admin.notifications::create_campaign` | tags: Admin: Core, Admin Notifications
- `DELETE /api/v1/admin/notifications/campaigns/{campaign_id}` | `app.api.admin.notifications::delete_campaign` | tags: Admin: Core, Admin Notifications
- `POST /api/v1/admin/notifications/campaigns/{campaign_id}/send` | `app.api.admin.notifications::send_campaign` | tags: Admin: Core, Admin Notifications
- `GET /api/v1/admin/notifications/config` | `app.api.admin.notifications::list_notification_configs` | tags: Admin: Core, Admin Notifications
- `POST /api/v1/admin/notifications/config` | `app.api.admin.notifications::create_notification_config` | tags: Admin: Core, Admin Notifications
- `PATCH /api/v1/admin/notifications/config/{config_id}` | `app.api.admin.notifications::update_notification_config` | tags: Admin: Core, Admin Notifications
- `POST /api/v1/admin/notifications/config/{config_id}/test` | `app.api.admin.notifications::test_notification_config` | tags: Admin: Core, Admin Notifications
- `GET /api/v1/admin/notifications/logs` | `app.api.admin.notifications::list_notification_logs` | tags: Admin: Core, Admin Notifications
- `GET /api/v1/admin/notifications/logs/stats` | `app.api.admin.notifications::notification_stats` | tags: Admin: Core, Admin Notifications
- `GET /api/v1/admin/notifications/triggers` | `app.api.admin.notifications::list_triggers` | tags: Admin: Core, Admin Notifications
- `POST /api/v1/admin/notifications/triggers` | `app.api.admin.notifications::create_trigger` | tags: Admin: Core, Admin Notifications
- `DELETE /api/v1/admin/notifications/triggers/{trigger_id}` | `app.api.admin.notifications::delete_trigger` | tags: Admin: Core, Admin Notifications
- `PATCH /api/v1/admin/notifications/triggers/{trigger_id}` | `app.api.admin.notifications::update_trigger` | tags: Admin: Core, Admin Notifications

### admin/rbac (46)
- `GET /api/v1/admin/rbac/hierarchy` | `app.api.v1.admin_rbac::get_role_hierarchy` | tags: Admin: Core, Admin RBAC
- `GET /api/v1/admin/rbac/hierarchy` | `app.api.v1.admin_rbac::get_role_hierarchy` | tags: Admin: RBAC
- `GET /api/v1/admin/rbac/permissions` | `app.api.v1.admin_rbac::read_permissions` | tags: Admin: Core, Admin RBAC
- `GET /api/v1/admin/rbac/permissions` | `app.api.v1.admin_rbac::read_permissions` | tags: Admin: RBAC
- `POST /api/v1/admin/rbac/permissions` | `app.api.v1.admin_rbac::create_permission` | tags: Admin: Core, Admin RBAC
- `POST /api/v1/admin/rbac/permissions` | `app.api.v1.admin_rbac::create_permission` | tags: Admin: RBAC
- `GET /api/v1/admin/rbac/roles` | `app.api.v1.admin_rbac::read_roles` | tags: Admin: Core, Admin RBAC
- `GET /api/v1/admin/rbac/roles` | `app.api.v1.admin_rbac::read_roles` | tags: Admin: RBAC
- `POST /api/v1/admin/rbac/roles` | `app.api.v1.admin_rbac::create_role` | tags: Admin: Core, Admin RBAC
- `POST /api/v1/admin/rbac/roles` | `app.api.v1.admin_rbac::create_role` | tags: Admin: RBAC
- `POST /api/v1/admin/rbac/roles/bulk-assign` | `app.api.v1.admin_rbac::bulk_assign_roles` | tags: Admin: Core, Admin RBAC
- `POST /api/v1/admin/rbac/roles/bulk-assign` | `app.api.v1.admin_rbac::bulk_assign_roles` | tags: Admin: RBAC
- `DELETE /api/v1/admin/rbac/roles/{role_id}` | `app.api.v1.admin_rbac::delete_role` | tags: Admin: Core, Admin RBAC
- `DELETE /api/v1/admin/rbac/roles/{role_id}` | `app.api.v1.admin_rbac::delete_role` | tags: Admin: RBAC
- `GET /api/v1/admin/rbac/roles/{role_id}` | `app.api.v1.admin_rbac::get_role_detail` | tags: Admin: Core, Admin RBAC
- `GET /api/v1/admin/rbac/roles/{role_id}` | `app.api.v1.admin_rbac::get_role_detail` | tags: Admin: RBAC
- `PUT /api/v1/admin/rbac/roles/{role_id}` | `app.api.v1.admin_rbac::update_role` | tags: Admin: Core, Admin RBAC
- `PUT /api/v1/admin/rbac/roles/{role_id}` | `app.api.v1.admin_rbac::update_role` | tags: Admin: RBAC
- `POST /api/v1/admin/rbac/roles/{role_id}/duplicate` | `app.api.v1.admin_rbac::duplicate_role` | tags: Admin: Core, Admin RBAC
- `POST /api/v1/admin/rbac/roles/{role_id}/duplicate` | `app.api.v1.admin_rbac::duplicate_role` | tags: Admin: RBAC
- `GET /api/v1/admin/rbac/roles/{role_id}/permissions` | `app.api.v1.admin_rbac::get_role_permissions` | tags: Admin: Core, Admin RBAC
- `GET /api/v1/admin/rbac/roles/{role_id}/permissions` | `app.api.v1.admin_rbac::get_role_permissions` | tags: Admin: RBAC
- `POST /api/v1/admin/rbac/roles/{role_id}/permissions` | `app.api.v1.admin_rbac::assign_permissions_to_role` | tags: Admin: Core, Admin RBAC
- `POST /api/v1/admin/rbac/roles/{role_id}/permissions` | `app.api.v1.admin_rbac::assign_permissions_to_role` | tags: Admin: RBAC
- `GET /api/v1/admin/rbac/roles/{role_id}/users` | `app.api.v1.admin_rbac::get_users_by_role` | tags: Admin: Core, Admin RBAC
- `GET /api/v1/admin/rbac/roles/{role_id}/users` | `app.api.v1.admin_rbac::get_users_by_role` | tags: Admin: RBAC
- `POST /api/v1/admin/rbac/users/{source_user_id}/roles/transfer` | `app.api.v1.admin_rbac::transfer_role_assignment` | tags: Admin: Core, Admin RBAC
- `POST /api/v1/admin/rbac/users/{source_user_id}/roles/transfer` | `app.api.v1.admin_rbac::transfer_role_assignment` | tags: Admin: RBAC
- `GET /api/v1/admin/rbac/users/{user_id}/access-paths` | `app.api.v1.admin_rbac::get_user_access_paths` | tags: Admin: Core, Admin RBAC
- `GET /api/v1/admin/rbac/users/{user_id}/access-paths` | `app.api.v1.admin_rbac::get_user_access_paths` | tags: Admin: RBAC
- `POST /api/v1/admin/rbac/users/{user_id}/access-paths` | `app.api.v1.admin_rbac::assign_access_path` | tags: Admin: Core, Admin RBAC
- `POST /api/v1/admin/rbac/users/{user_id}/access-paths` | `app.api.v1.admin_rbac::assign_access_path` | tags: Admin: RBAC
- `DELETE /api/v1/admin/rbac/users/{user_id}/access-paths/{path_id}` | `app.api.v1.admin_rbac::remove_access_path` | tags: Admin: Core, Admin RBAC
- `DELETE /api/v1/admin/rbac/users/{user_id}/access-paths/{path_id}` | `app.api.v1.admin_rbac::remove_access_path` | tags: Admin: RBAC
- `PUT /api/v1/admin/rbac/users/{user_id}/access-paths/{path_id}` | `app.api.v1.admin_rbac::update_access_path` | tags: Admin: Core, Admin RBAC
- `PUT /api/v1/admin/rbac/users/{user_id}/access-paths/{path_id}` | `app.api.v1.admin_rbac::update_access_path` | tags: Admin: RBAC
- `GET /api/v1/admin/rbac/users/{user_id}/permissions` | `app.api.v1.admin_rbac::get_user_permissions` | tags: Admin: Core, Admin RBAC
- `GET /api/v1/admin/rbac/users/{user_id}/permissions` | `app.api.v1.admin_rbac::get_user_permissions` | tags: Admin: RBAC
- `GET /api/v1/admin/rbac/users/{user_id}/permissions/check` | `app.api.v1.admin_rbac::check_user_permission` | tags: Admin: Core, Admin RBAC
- `GET /api/v1/admin/rbac/users/{user_id}/permissions/check` | `app.api.v1.admin_rbac::check_user_permission` | tags: Admin: RBAC
- `GET /api/v1/admin/rbac/users/{user_id}/roles` | `app.api.v1.admin_rbac::get_user_roles` | tags: Admin: Core, Admin RBAC
- `GET /api/v1/admin/rbac/users/{user_id}/roles` | `app.api.v1.admin_rbac::get_user_roles` | tags: Admin: RBAC
- `POST /api/v1/admin/rbac/users/{user_id}/roles` | `app.api.v1.admin_rbac::assign_roles_to_user` | tags: Admin: Core, Admin RBAC
- `POST /api/v1/admin/rbac/users/{user_id}/roles` | `app.api.v1.admin_rbac::assign_roles_to_user` | tags: Admin: RBAC
- `DELETE /api/v1/admin/rbac/users/{user_id}/roles/{role_id}` | `app.api.v1.admin_rbac::remove_role_from_user` | tags: Admin: Core, Admin RBAC
- `DELETE /api/v1/admin/rbac/users/{user_id}/roles/{role_id}` | `app.api.v1.admin_rbac::remove_role_from_user` | tags: Admin: RBAC

### admin/rentals (8)
- `GET /api/v1/admin/rentals/active` | `app.api.admin.rentals::list_active_rentals` | tags: Admin: Core, Admin Rentals
- `GET /api/v1/admin/rentals/history` | `app.api.admin.rentals::list_rental_history` | tags: Admin: Core, Admin Rentals
- `GET /api/v1/admin/rentals/late-fees` | `app.api.admin.rentals::list_late_fees` | tags: Admin: Core, Admin Rentals
- `PUT /api/v1/admin/rentals/late-fees/waivers/{waiver_id}/review` | `app.api.admin.rentals::review_waiver` | tags: Admin: Core, Admin Rentals
- `GET /api/v1/admin/rentals/purchases` | `app.api.admin.rentals::list_purchases` | tags: Admin: Core, Admin Rentals
- `GET /api/v1/admin/rentals/stats` | `app.api.admin.rentals::get_rental_stats` | tags: Admin: Core, Admin Rentals
- `GET /api/v1/admin/rentals/swaps` | `app.api.admin.rentals::list_swaps` | tags: Admin: Core, Admin Rentals
- `PUT /api/v1/admin/rentals/{rental_id}/terminate` | `app.api.admin.rentals::terminate_rental` | tags: Admin: Core, Admin Rentals

### admin/security (9)
- `GET /api/v1/admin/security/activity-logs` | `app.api.v1.security::get_activity_logs` | tags: Admin Security
- `GET /api/v1/admin/security/audit-logs` | `app.api.admin.security::list_audit_logs` | tags: Admin: Core, Admin Security
- `GET /api/v1/admin/security/audit-logs/stats` | `app.api.admin.security::audit_stats` | tags: Admin: Core, Admin Security
- `POST /api/v1/admin/security/enable-2fa` | `app.api.v1.security::enable_2fa` | tags: Admin Security
- `GET /api/v1/admin/security/security-events` | `app.api.admin.security::list_security_events` | tags: Admin: Core, Admin Security
- `PATCH /api/v1/admin/security/security-events/{event_id}/resolve` | `app.api.admin.security::resolve_security_event` | tags: Admin: Core, Admin Security
- `GET /api/v1/admin/security/security-settings` | `app.api.admin.security::get_security_settings` | tags: Admin: Core, Admin Security
- `PATCH /api/v1/admin/security/security-settings` | `app.api.admin.security::update_security_settings` | tags: Admin: Core, Admin Security
- `POST /api/v1/admin/security/verify-enable-2fa` | `app.api.v1.security::verify_enable_2fa` | tags: Admin Security

### admin/settings (10)
- `GET /api/v1/admin/settings/api-keys` | `app.api.admin.settings::list_api_keys` | tags: Admin: Core, Admin Settings
- `POST /api/v1/admin/settings/api-keys` | `app.api.admin.settings::create_api_key` | tags: Admin: Core, Admin Settings
- `DELETE /api/v1/admin/settings/api-keys/{key_id}` | `app.api.admin.settings::delete_api_key` | tags: Admin: Core, Admin Settings
- `PATCH /api/v1/admin/settings/api-keys/{key_id}` | `app.api.admin.settings::update_api_key` | tags: Admin: Core, Admin Settings
- `GET /api/v1/admin/settings/feature-flags` | `app.api.admin.settings::list_feature_flags` | tags: Admin: Core, Admin Settings
- `PATCH /api/v1/admin/settings/feature-flags/{flag_id}` | `app.api.admin.settings::toggle_feature_flag` | tags: Admin: Core, Admin Settings
- `GET /api/v1/admin/settings/general` | `app.api.admin.settings::get_general_settings` | tags: Admin: Core, Admin Settings
- `POST /api/v1/admin/settings/general` | `app.api.admin.settings::create_general_setting` | tags: Admin: Core, Admin Settings
- `PATCH /api/v1/admin/settings/general/{config_id}` | `app.api.admin.settings::update_general_setting` | tags: Admin: Core, Admin Settings
- `GET /api/v1/admin/settings/system-health` | `app.api.admin.settings::system_health` | tags: Admin: Core, Admin Settings

### admin/stations (23)
- `GET /api/v1/admin/stations/` | `app.api.admin.stations::list_stations` | tags: Admin: Core, Admin Stations
- `POST /api/v1/admin/stations/` | `app.api.admin.stations::create_station` | tags: Admin: Core, Admin Stations
- `GET /api/v1/admin/stations/health` | `app.api.v1.admin_stations::get_station_health_stats` | tags: Admin: Stations
- `GET /api/v1/admin/stations/maintenance/all` | `app.api.admin.stations::list_all_maintenance` | tags: Admin: Core, Admin Stations
- `GET /api/v1/admin/stations/maintenance/checklists/submissions` | `app.api.admin.stations::list_checklist_submissions` | tags: Admin: Core, Admin Stations
- `POST /api/v1/admin/stations/maintenance/checklists/submissions` | `app.api.admin.stations::create_checklist_submission` | tags: Admin: Core, Admin Stations
- `GET /api/v1/admin/stations/maintenance/checklists/templates` | `app.api.admin.stations::list_checklist_templates` | tags: Admin: Core, Admin Stations
- `POST /api/v1/admin/stations/maintenance/checklists/templates` | `app.api.admin.stations::create_checklist_template` | tags: Admin: Core, Admin Stations
- `DELETE /api/v1/admin/stations/maintenance/checklists/templates/{template_id}` | `app.api.admin.stations::delete_checklist_template` | tags: Admin: Core, Admin Stations
- `PUT /api/v1/admin/stations/maintenance/checklists/templates/{template_id}` | `app.api.admin.stations::update_checklist_template` | tags: Admin: Core, Admin Stations
- `POST /api/v1/admin/stations/maintenance/create` | `app.api.admin.stations::create_maintenance_record` | tags: Admin: Core, Admin Stations
- `GET /api/v1/admin/stations/maintenance/stats` | `app.api.admin.stations::get_maintenance_stats` | tags: Admin: Core, Admin Stations
- `PUT /api/v1/admin/stations/maintenance/{record_id}/status` | `app.api.admin.stations::update_maintenance_status` | tags: Admin: Core, Admin Stations
- `GET /api/v1/admin/stations/performance/all` | `app.api.admin.stations::get_all_station_performance` | tags: Admin: Core, Admin Stations
- `GET /api/v1/admin/stations/stats` | `app.api.admin.stations::get_station_stats` | tags: Admin: Core, Admin Stations
- `DELETE /api/v1/admin/stations/{station_id}` | `app.api.admin.stations::delete_station` | tags: Admin: Core, Admin Stations
- `GET /api/v1/admin/stations/{station_id}` | `app.api.admin.stations::get_station_detail` | tags: Admin: Core, Admin Stations
- `PUT /api/v1/admin/stations/{station_id}` | `app.api.admin.stations::update_station` | tags: Admin: Core, Admin Stations
- `GET /api/v1/admin/stations/{station_id}/alerts` | `app.api.v1.admin_stations::get_station_alerts` | tags: Admin: Stations
- `GET /api/v1/admin/stations/{station_id}/charging-queue` | `app.api.v1.admin_stations::get_station_charging_queue` | tags: Admin: Stations
- `GET /api/v1/admin/stations/{station_id}/maintenance` | `app.api.admin.stations::get_station_maintenance` | tags: Admin: Core, Admin Stations
- `GET /api/v1/admin/stations/{station_id}/performance` | `app.api.admin.stations::get_station_performance` | tags: Admin: Core, Admin Stations
- `GET /api/v1/admin/stations/{station_id}/specs` | `app.api.admin.stations::get_station_specs` | tags: Admin: Core, Admin Stations

### admin/stats (1)
- `GET /api/v1/admin/stats` | `app.api.admin.main::get_admin_stats` | tags: Admin: Core

### admin/stock (8)
- `GET /api/v1/admin/stock/alerts` | `app.api.admin.stock::get_active_stock_alerts` | tags: Admin: Core, Admin Stock Levels
- `POST /api/v1/admin/stock/alerts/{station_id}/dismiss` | `app.api.admin.stock::dismiss_stock_alert` | tags: Admin: Core, Admin Stock Levels
- `GET /api/v1/admin/stock/locations` | `app.api.admin.stock::get_locations_stock` | tags: Admin: Core, Admin Stock Levels
- `GET /api/v1/admin/stock/overview` | `app.api.admin.stock::get_stock_overview` | tags: Admin: Core, Admin Stock Levels
- `POST /api/v1/admin/stock/reorder` | `app.api.admin.stock::create_reorder_request` | tags: Admin: Core, Admin Stock Levels
- `GET /api/v1/admin/stock/stations` | `app.api.admin.stock::get_stations_stock` | tags: Admin: Core, Admin Stock Levels
- `GET /api/v1/admin/stock/stations/{station_id}` | `app.api.admin.stock::get_station_stock_detail` | tags: Admin: Core, Admin Stock Levels
- `PUT /api/v1/admin/stock/stations/{station_id}/config` | `app.api.admin.stock::update_station_stock_config` | tags: Admin: Core, Admin Stock Levels

### admin/support (14)
- `GET /api/v1/admin/support/knowledge-base` | `app.api.admin.support::get_knowledge_base` | tags: Admin: Core, Admin Support
- `POST /api/v1/admin/support/knowledge-base` | `app.api.admin.support::create_kb_article` | tags: Admin: Core, Admin Support
- `GET /api/v1/admin/support/knowledge-base/stats` | `app.api.admin.support::get_kb_stats` | tags: Admin: Core, Admin Support
- `DELETE /api/v1/admin/support/knowledge-base/{article_id}` | `app.api.admin.support::delete_kb_article` | tags: Admin: Core, Admin Support
- `PUT /api/v1/admin/support/knowledge-base/{article_id}` | `app.api.admin.support::update_kb_article` | tags: Admin: Core, Admin Support
- `GET /api/v1/admin/support/team/overview` | `app.api.admin.support::get_team_overview` | tags: Admin: Core, Admin Support
- `GET /api/v1/admin/support/team/performance` | `app.api.admin.support::get_team_performance` | tags: Admin: Core, Admin Support
- `GET /api/v1/admin/support/tickets` | `app.api.admin.support::get_tickets` | tags: Admin: Core, Admin Support
- `GET /api/v1/admin/support/tickets/stats` | `app.api.admin.support::get_ticket_stats` | tags: Admin: Core, Admin Support
- `GET /api/v1/admin/support/tickets/{ticket_id}` | `app.api.admin.support::get_ticket_detail` | tags: Admin: Core, Admin Support
- `PUT /api/v1/admin/support/tickets/{ticket_id}/assign` | `app.api.admin.support::assign_ticket` | tags: Admin: Core, Admin Support
- `POST /api/v1/admin/support/tickets/{ticket_id}/messages` | `app.api.admin.support::add_ticket_message` | tags: Admin: Core, Admin Support
- `PUT /api/v1/admin/support/tickets/{ticket_id}/priority` | `app.api.admin.support::update_ticket_priority` | tags: Admin: Core, Admin Support
- `PUT /api/v1/admin/support/tickets/{ticket_id}/status` | `app.api.admin.support::update_ticket_status` | tags: Admin: Core, Admin Support

### admin/users (19)
- `GET /api/v1/admin/users/` | `app.api.admin.users::list_users` | tags: Admin: Core, Admin Users
- `POST /api/v1/admin/users/` | `app.api.admin.users::admin_create_user` | tags: Admin: Core, Admin Users
- `GET /api/v1/admin/users/summary` | `app.api.admin.users::get_user_summary` | tags: Admin: Core, Admin Users
- `GET /api/v1/admin/users/suspended` | `app.api.admin.users::list_suspended_users` | tags: Admin: Core, Admin Users
- `DELETE /api/v1/admin/users/{user_id}` | `app.api.admin.users::delete_user` | tags: Admin: Core, Admin Users
- `GET /api/v1/admin/users/{user_id}` | `app.api.admin.users::get_user_detail` | tags: Admin: Core, Admin Users
- `PUT /api/v1/admin/users/{user_id}` | `app.api.admin.users::update_user_detail` | tags: Admin: Core, Admin Users
- `POST /api/v1/admin/users/{user_id}/ban` | `app.api.v1.admin_users::ban_user` | tags: Admin: Users
- `POST /api/v1/admin/users/{user_id}/force-logout` | `app.api.v1.admin_users::force_logout_user` | tags: Admin: Users
- `POST /api/v1/admin/users/{user_id}/force-password-change` | `app.api.v1.admin_users::force_password_change` | tags: Admin: Users
- `PUT /api/v1/admin/users/{user_id}/kyc-status` | `app.api.admin.users::update_user_kyc_status` | tags: Admin: Core, Admin Users
- `PUT /api/v1/admin/users/{user_id}/password` | `app.api.admin.users::update_user_password` | tags: Admin: Core, Admin Users
- `PUT /api/v1/admin/users/{user_id}/reactivate` | `app.api.admin.users::reactivate_user` | tags: Admin: Core, Admin Users
- `POST /api/v1/admin/users/{user_id}/reset-password` | `app.api.admin.users::reset_user_password` | tags: Admin: Core, Admin Users
- `POST /api/v1/admin/users/{user_id}/reset-password` | `app.api.v1.admin_users::admin_reset_password` | tags: Admin: Users
- `PUT /api/v1/admin/users/{user_id}/suspend` | `app.api.admin.users::suspend_user` | tags: Admin: Core, Admin Users
- `PUT /api/v1/admin/users/{user_id}/toggle-active` | `app.api.admin.users::toggle_user_active` | tags: Admin: Core, Admin Users
- `POST /api/v1/admin/users/{user_id}/transition` | `app.api.v1.admin_users::transition_user_state` | tags: Admin: Users
- `POST /api/v1/admin/users/{user_id}/unban` | `app.api.v1.admin_users::unban_user` | tags: Admin: Users

### analytics (6)
- `GET /api/v1/analytics/admin/overview` | `app.api.v1.analytics.admin::get_admin_overview` | tags: Analytics, analytics-admin
- `GET /api/v1/analytics/carbon-savings` | `app.api.v1.analytics_enhanced::get_carbon_savings` | tags: Analytics Enhanced
- `GET /api/v1/analytics/customer/overview` | `app.api.v1.analytics.customer::get_customer_overview` | tags: Analytics, analytics-customer
- `GET /api/v1/analytics/dealer/overview` | `app.api.v1.analytics.dealer::get_dealer_overview` | tags: Analytics, analytics-dealer
- `GET /api/v1/analytics/export` | `app.api.v1.analytics_enhanced::export_analytics_data` | tags: Analytics Enhanced
- `GET /api/v1/analytics/logistics/overview` | `app.api.v1.analytics.logistics::get_logistics_overview` | tags: Analytics, analytics-logistics

### api/internal (1)
- `POST /api/internal/hotspots/telematics/ingest` | `app.api.internal.hotspots::ingest_telematics_internal` | tags: Internal

### api/webhooks (1)
- `POST /api/webhooks/razorpay` | `app.api.webhooks.razorpay::razorpay_webhook_event` | tags: Webhooks

### audit (5)
- `GET /api/v1/audit/auth/failures` | `app.api.v1.audit::get_auth_failures` | tags: Audit Logs
- `GET /api/v1/audit/data-access` | `app.api.v1.audit::get_data_access_log` | tags: Audit Logs
- `GET /api/v1/audit/permissions/usage` | `app.api.v1.audit::get_permission_usage_analytics` | tags: Audit Logs
- `GET /api/v1/audit/roles/{role_id}/changes` | `app.api.v1.audit::get_role_audit_log` | tags: Audit Logs
- `GET /api/v1/audit/users/{user_id}` | `app.api.v1.audit::get_user_audit_log` | tags: Audit Logs

### auth (33)
- `POST /api/v1/auth/2fa/disable` | `app.api.v1.auth::disable_2fa` | tags: Auth
- `POST /api/v1/auth/admin/login` | `app.api.v1.auth::admin_login` | tags: Auth
- `POST /api/v1/auth/biometric-login` | `app.api.v1.auth::biometric_login` | tags: Auth
- `POST /api/v1/auth/biometric/register` | `app.api.v1.auth::biometric_register` | tags: Auth
- `POST /api/v1/auth/change-password` | `app.api.v1.auth::change_password` | tags: Auth
- `POST /api/v1/auth/email/send-verification` | `app.api.v1.auth::send_email_verification` | tags: Auth
- `POST /api/v1/auth/enable-2fa` | `app.api.v1.auth::enable_2fa_request` | tags: Auth
- `POST /api/v1/auth/forgot-password` | `app.api.v1.auth::forgot_password` | tags: Auth
- `POST /api/v1/auth/login` | `app.api.v1.auth::login` | tags: Auth
- `POST /api/v1/auth/logout` | `app.api.v1.auth::logout` | tags: Auth
- `POST /api/v1/auth/logout-all` | `app.api.v1.auth::logout_all` | tags: Auth
- `GET /api/v1/auth/passkeys` | `app.api.v1.passkeys::list_passkeys` | tags: Auth Passkeys
- `POST /api/v1/auth/passkeys/auth/options` | `app.api.v1.passkeys::create_authentication_options` | tags: Auth Passkeys
- `POST /api/v1/auth/passkeys/auth/verify` | `app.api.v1.passkeys::verify_authentication` | tags: Auth Passkeys
- `POST /api/v1/auth/passkeys/register/options` | `app.api.v1.passkeys::create_registration_options` | tags: Auth Passkeys
- `POST /api/v1/auth/passkeys/register/verify` | `app.api.v1.passkeys::verify_registration` | tags: Auth Passkeys
- `DELETE /api/v1/auth/passkeys/{credential_id}` | `app.api.v1.passkeys::delete_passkey` | tags: Auth Passkeys
- `POST /api/v1/auth/refresh` | `app.api.v1.auth::refresh_token` | tags: Auth
- `POST /api/v1/auth/register` | `app.api.v1.auth::register` | tags: Auth
- `POST /api/v1/auth/register/password` | `app.api.v1.auth::register_with_password` | tags: Auth
- `POST /api/v1/auth/register/request-otp` | `app.api.v1.auth::request_registration_otp` | tags: Auth
- `POST /api/v1/auth/register/verify-otp` | `app.api.v1.auth::verify_registration_otp` | tags: Auth
- `POST /api/v1/auth/resend-otp` | `app.api.v1.auth::resend_otp` | tags: Auth
- `POST /api/v1/auth/resend-verification` | `app.api.v1.auth::send_email_verification` | tags: Auth
- `GET /api/v1/auth/security-questions` | `app.api.v1.auth::list_security_questions` | tags: Auth
- `POST /api/v1/auth/security-questions/set` | `app.api.v1.auth::set_security_question` | tags: Auth
- `POST /api/v1/auth/security-questions/verify` | `app.api.v1.auth::verify_security_question_route` | tags: Auth
- `POST /api/v1/auth/select-role` | `app.api.v1.auth::select_role` | tags: Auth
- `POST /api/v1/auth/social-login` | `app.api.v1.auth::social_login` | tags: Auth
- `POST /api/v1/auth/token` | `app.api.v1.auth::login_access_token` | tags: Auth, authentication
- `POST /api/v1/auth/verify-2fa` | `app.api.v1.auth::verify_2fa_and_enable` | tags: Auth
- `POST /api/v1/auth/verify-email` | `app.api.v1.auth::verify_email` | tags: Auth
- `POST /api/v1/auth/verify-otp` | `app.api.v1.auth::verify_otp_alias` | tags: Auth

### batteries (27)
- `GET /api/v1/batteries/` | `app.api.v1.batteries::read_batteries` | tags: Batteries
- `POST /api/v1/batteries/` | `app.api.v1.batteries::create_battery` | tags: Batteries
- `GET /api/v1/batteries/batch/export` | `app.api.v1.batteries::export_batteries_csv` | tags: Batteries
- `POST /api/v1/batteries/batch/import` | `app.api.v1.batteries::import_batteries_csv` | tags: Batteries
- `PUT /api/v1/batteries/batch/update` | `app.api.v1.batteries::update_batteries_batch` | tags: Batteries
- `POST /api/v1/batteries/batches` | `app.api.v1.battery_catalog::create_battery_batch` | tags: Battery Catalog
- `GET /api/v1/batteries/low-health` | `app.api.v1.batteries::get_low_health_batteries` | tags: Batteries
- `POST /api/v1/batteries/qr/generate` | `app.api.v1.batteries::generate_qr_code` | tags: Batteries
- `POST /api/v1/batteries/qr/verify` | `app.api.v1.batteries::verify_qr_code` | tags: Batteries
- `POST /api/v1/batteries/scan-qr` | `app.api.v1.batteries::scan_battery_qr` | tags: Batteries
- `GET /api/v1/batteries/specs` | `app.api.v1.battery_catalog::read_battery_specs` | tags: Battery Catalog
- `POST /api/v1/batteries/specs` | `app.api.v1.battery_catalog::create_battery_spec` | tags: Battery Catalog
- `GET /api/v1/batteries/utilization-report` | `app.api.v1.batteries::get_battery_utilization_report` | tags: Batteries
- `DELETE /api/v1/batteries/{battery_id}` | `app.api.v1.batteries::decommission_battery` | tags: Batteries
- `GET /api/v1/batteries/{battery_id}` | `app.api.v1.batteries::read_battery` | tags: Batteries
- `PUT /api/v1/batteries/{battery_id}` | `app.api.v1.batteries::update_battery` | tags: Batteries
- `GET /api/v1/batteries/{battery_id}/alerts` | `app.api.v1.batteries::get_battery_alerts` | tags: Batteries
- `POST /api/v1/batteries/{battery_id}/assign-station` | `app.api.v1.batteries::assign_battery_station` | tags: Batteries
- `GET /api/v1/batteries/{battery_id}/audit-logs` | `app.api.v1.batteries::get_battery_audit_logs` | tags: Batteries
- `GET /api/v1/batteries/{battery_id}/health-history` | `app.api.v1.batteries::get_battery_health_history` | tags: Batteries
- `PUT /api/v1/batteries/{battery_id}/lifecycle` | `app.api.v1.batteries::update_battery_lifecycle` | tags: Batteries
- `POST /api/v1/batteries/{battery_id}/maintenance` | `app.api.v1.batteries::log_battery_maintenance` | tags: Batteries
- `GET /api/v1/batteries/{battery_id}/maintenance-history` | `app.api.v1.batteries::get_battery_maintenance_history` | tags: Batteries
- `GET /api/v1/batteries/{battery_id}/rental-history` | `app.api.v1.batteries::get_battery_rental_history` | tags: Batteries
- `PUT /api/v1/batteries/{battery_id}/status` | `app.api.v1.batteries::update_battery_status` | tags: Batteries
- `GET /api/v1/batteries/{battery_id}/telemetry` | `app.api.v1.batteries::get_battery_telemetry` | tags: Batteries
- `POST /api/v1/batteries/{battery_id}/transfer` | `app.api.v1.batteries::transfer_battery` | tags: Batteries

### bookings (7)
- `GET /api/v1/bookings/` | `app.api.v1.bookings::list_my_bookings` | tags: Bookings
- `POST /api/v1/bookings/` | `app.api.v1.bookings::create_booking` | tags: Bookings
- `DELETE /api/v1/bookings/{booking_id}` | `app.api.v1.bookings::cancel_booking` | tags: Bookings
- `GET /api/v1/bookings/{booking_id}` | `app.api.v1.bookings::get_booking_details` | tags: Bookings
- `PUT /api/v1/bookings/{booking_id}` | `app.api.v1.bookings::update_booking` | tags: Bookings
- `POST /api/v1/bookings/{booking_id}/pay` | `app.api.v1.bookings::pay_for_booking` | tags: Bookings
- `POST /api/v1/bookings/{booking_id}/reminder` | `app.api.v1.bookings::send_booking_reminder` | tags: Bookings

### branches (5)
- `GET /api/v1/branches/` | `app.api.v1.branches::read_branches` | tags: Branches
- `POST /api/v1/branches/` | `app.api.v1.branches::create_branch` | tags: Branches
- `DELETE /api/v1/branches/{branch_id}` | `app.api.v1.branches::delete_branch` | tags: Branches
- `GET /api/v1/branches/{branch_id}` | `app.api.v1.branches::read_branch` | tags: Branches
- `PATCH /api/v1/branches/{branch_id}` | `app.api.v1.branches::update_branch` | tags: Branches

### catalog (24)
- `GET /api/v1/catalog/admin/catalog/orders` | `app.api.v1.catalog::admin_get_orders` | tags: Catalog
- `POST /api/v1/catalog/admin/products` | `app.api.v1.catalog::admin_create_product` | tags: Catalog
- `DELETE /api/v1/catalog/admin/products/{id}` | `app.api.v1.catalog::admin_delete_product` | tags: Catalog
- `PUT /api/v1/catalog/admin/products/{id}` | `app.api.v1.catalog::admin_update_product` | tags: Catalog
- `DELETE /api/v1/catalog/cart` | `app.api.v1.catalog::clear_cart` | tags: Catalog
- `GET /api/v1/catalog/cart` | `app.api.v1.catalog::get_cart` | tags: Catalog
- `POST /api/v1/catalog/cart` | `app.api.v1.catalog::add_to_cart` | tags: Catalog
- `DELETE /api/v1/catalog/cart/{item_id}` | `app.api.v1.catalog::remove_cart_item` | tags: Catalog
- `PATCH /api/v1/catalog/cart/{item_id}` | `app.api.v1.catalog::update_cart_item` | tags: Catalog
- `GET /api/v1/catalog/orders` | `app.api.v1.catalog::get_user_orders` | tags: Catalog
- `POST /api/v1/catalog/orders` | `app.api.v1.catalog::create_order` | tags: Catalog
- `POST /api/v1/catalog/orders/checkout` | `app.api.v1.catalog::checkout_cart` | tags: Catalog
- `GET /api/v1/catalog/orders/{order_id}` | `app.api.v1.catalog::get_order_details` | tags: Catalog
- `POST /api/v1/catalog/orders/{order_id}/cancel` | `app.api.v1.catalog::cancel_order` | tags: Catalog
- `GET /api/v1/catalog/orders/{order_id}/invoice` | `app.api.v1.catalog::get_order_invoice` | tags: Catalog
- `POST /api/v1/catalog/orders/{order_id}/return` | `app.api.v1.catalog::initiate_order_return` | tags: Catalog
- `GET /api/v1/catalog/orders/{order_id}/tracking` | `app.api.v1.catalog::get_order_tracking` | tags: Catalog
- `POST /api/v1/catalog/orders/{order_id}/warranty` | `app.api.v1.catalog::claim_warranty` | tags: Catalog
- `GET /api/v1/catalog/products` | `app.api.v1.catalog::get_products` | tags: Catalog
- `GET /api/v1/catalog/products/categories` | `app.api.v1.catalog::get_product_categories` | tags: Catalog
- `GET /api/v1/catalog/products/featured` | `app.api.v1.catalog::get_featured_products` | tags: Catalog
- `GET /api/v1/catalog/products/metadata` | `app.api.v1.catalog::get_catalog_metadata` | tags: Catalog
- `POST /api/v1/catalog/products/search` | `app.api.v1.catalog::search_products` | tags: Catalog
- `GET /api/v1/catalog/products/{product_id}` | `app.api.v1.catalog::get_product_details` | tags: Catalog

### config (1)
- `GET /api/v1/config` | `app.api.v1.system::get_public_config` | tags: System

### customer (2)
- `POST /api/v1/customer/auth/login` | `app.api.v1.customer_auth::customer_login` | tags: Customer Auth
- `POST /api/v1/customer/auth/register` | `app.api.v1.customer_auth::customer_register` | tags: Customer Auth

### dashboard (5)
- `GET /api/v1/dashboard/activity-feed` | `app.api.v1.dashboard::get_dashboard_activity_feed` | tags: Admin: Dashboard
- `GET /api/v1/dashboard/station-health` | `app.api.v1.dashboard::get_station_health` | tags: Admin: Dashboard
- `GET /api/v1/dashboard/summary` | `app.api.v1.dashboard::get_dashboard_summary` | tags: Admin: Dashboard
- `GET /api/v1/dashboard/top-stations` | `app.api.v1.dashboard::get_dashboard_top_stations` | tags: Admin: Dashboard
- `GET /api/v1/dashboard/trend` | `app.api.v1.dashboard::get_dashboard_trend` | tags: Admin: Dashboard

### dealer-stations (10)
- `GET /api/v1/dealer-stations` | `app.api.v1.dealer_stations::list_stations` | tags: Dealer: Stations
- `GET /api/v1/dealer-stations/inventory/alerts` | `app.api.v1.dealer_stations::fetch_inventory_alerts` | tags: Dealer: Stations
- `POST /api/v1/dealer-stations/new` | `app.api.v1.dealer_stations::submit_new_station` | tags: Dealer: Stations
- `GET /api/v1/dealer-stations/{station_id}` | `app.api.v1.dealer_stations::get_station_detail` | tags: Dealer: Stations
- `PUT /api/v1/dealer-stations/{station_id}` | `app.api.v1.dealer_stations::update_station` | tags: Dealer: Stations
- `GET /api/v1/dealer-stations/{station_id}/batteries` | `app.api.v1.dealer_stations::get_station_batteries` | tags: Dealer: Stations
- `PUT /api/v1/dealer-stations/{station_id}/hours` | `app.api.v1.dealer_stations::update_opening_hours` | tags: Dealer: Stations
- `PUT /api/v1/dealer-stations/{station_id}/inventory-rules` | `app.api.v1.dealer_stations::update_inventory_rules` | tags: Dealer: Stations
- `GET /api/v1/dealer-stations/{station_id}/maintenance` | `app.api.v1.dealer_stations::get_station_maintenance` | tags: Dealer: Stations
- `POST /api/v1/dealer-stations/{station_id}/schedule-maintenance` | `app.api.v1.dealer_stations::schedule_maintenance` | tags: Dealer: Stations

### dealer/analytics (16)
- `GET /api/v1/dealer/analytics` | `app.api.v1.dealer_portal_customers::list_customers` | tags: Dealer: Customers
- `GET /api/v1/dealer/analytics/comparison` | `app.api.v1.dealer_analytics::get_comparison` | tags: Dealer: Analytics
- `GET /api/v1/dealer/analytics/customers` | `app.api.v1.dealer_analytics::get_customer_insights` | tags: Dealer: Analytics
- `POST /api/v1/dealer/analytics/email-report` | `app.api.v1.dealer_analytics::email_report` | tags: Dealer: Analytics
- `GET /api/v1/dealer/analytics/export/csv` | `app.api.v1.dealer_analytics::export_csv` | tags: Dealer: Analytics
- `GET /api/v1/dealer/analytics/export/json` | `app.api.v1.dealer_analytics::export_json` | tags: Dealer: Analytics
- `GET /api/v1/dealer/analytics/export/pdf` | `app.api.v1.dealer_analytics::export_pdf` | tags: Dealer: Analytics
- `GET /api/v1/dealer/analytics/margin-by-battery` | `app.api.v1.dealer_analytics::get_margin_by_battery` | tags: Dealer: Analytics
- `GET /api/v1/dealer/analytics/overview` | `app.api.v1.dealer_analytics::get_overview` | tags: Dealer: Analytics
- `GET /api/v1/dealer/analytics/peak-hours` | `app.api.v1.dealer_analytics::get_peak_hours` | tags: Dealer: Analytics
- `GET /api/v1/dealer/analytics/profitability` | `app.api.v1.dealer_analytics::get_profitability_analysis` | tags: Dealer: Analytics
- `GET /api/v1/dealer/analytics/rentals/active` | `app.api.v1.dealer_portal_customers::get_active_rentals` | tags: Dealer: Customers
- `GET /api/v1/dealer/analytics/revenue-breakdown` | `app.api.v1.dealer_analytics::get_revenue_breakdown` | tags: Dealer: Analytics
- `GET /api/v1/dealer/analytics/stations` | `app.api.v1.dealer_analytics::get_station_metrics` | tags: Dealer: Analytics
- `GET /api/v1/dealer/analytics/trends` | `app.api.v1.dealer_analytics::get_trends` | tags: Dealer: Analytics
- `GET /api/v1/dealer/analytics/{customer_id}` | `app.api.v1.dealer_portal_customers::get_customer_detail` | tags: Dealer: Customers

### dealer/auth (8)
- `POST /api/v1/dealer/auth/activate/{token}` | `app.api.v1.dealer_portal_auth::activate_account` | tags: Dealer: Auth
- `POST /api/v1/dealer/auth/change-password` | `app.api.v1.dealer_portal_auth::change_password` | tags: Dealer: Auth
- `POST /api/v1/dealer/auth/force-change-password` | `app.api.v1.dealer_portal_auth::force_change_password` | tags: Dealer: Auth
- `POST /api/v1/dealer/auth/login` | `app.api.v1.dealer_portal_auth::dealer_login` | tags: Dealer: Auth
- `POST /api/v1/dealer/auth/refresh` | `app.api.v1.dealer_portal_auth::refresh_token` | tags: Dealer: Auth
- `POST /api/v1/dealer/auth/register` | `app.api.v1.dealer_portal_auth::dealer_register` | tags: Dealer: Auth
- `GET /api/v1/dealer/auth/register/status` | `app.api.v1.dealer_portal_auth::registration_status` | tags: Dealer: Auth
- `GET /api/v1/dealer/auth/validate-invite/{token}` | `app.api.v1.dealer_portal_auth::validate_invite_token` | tags: Dealer: Auth

### dealer/campaigns (10)
- `GET /api/v1/dealer/campaigns` | `app.api.v1.dealer_campaigns::list_campaigns` | tags: Dealer: Campaigns
- `POST /api/v1/dealer/campaigns` | `app.api.v1.dealer_campaigns::create_campaign` | tags: Dealer: Campaigns
- `POST /api/v1/dealer/campaigns/bulk-create` | `app.api.v1.dealer_campaigns::bulk_create_csv` | tags: Dealer: Campaigns
- `POST /api/v1/dealer/campaigns/bulk-toggle` | `app.api.v1.dealer_campaigns::bulk_toggle` | tags: Dealer: Campaigns
- `POST /api/v1/dealer/campaigns/validate` | `app.api.v1.dealer_campaigns::validate_promo` | tags: Dealer: Campaigns
- `DELETE /api/v1/dealer/campaigns/{campaign_id}` | `app.api.v1.dealer_campaigns::deactivate_campaign` | tags: Dealer: Campaigns
- `GET /api/v1/dealer/campaigns/{campaign_id}` | `app.api.v1.dealer_campaigns::get_campaign` | tags: Dealer: Campaigns
- `PUT /api/v1/dealer/campaigns/{campaign_id}` | `app.api.v1.dealer_campaigns::update_campaign` | tags: Dealer: Campaigns
- `GET /api/v1/dealer/campaigns/{campaign_id}/analytics` | `app.api.v1.dealer_campaigns::get_campaign_analytics` | tags: Dealer: Campaigns
- `POST /api/v1/dealer/campaigns/{campaign_id}/clone` | `app.api.v1.dealer_campaigns::clone_campaign` | tags: Dealer: Campaigns

### dealer/onboarding (9)
- `POST /api/v1/dealer/onboarding/admin/{application_id}/approve` | `app.api.v1.dealer_onboarding::admin_final_approve` | tags: Dealer: Onboarding
- `POST /api/v1/dealer/onboarding/admin/{application_id}/complete-visit` | `app.api.v1.dealer_onboarding::admin_complete_visit` | tags: Dealer: Onboarding
- `POST /api/v1/dealer/onboarding/admin/{application_id}/handover-inventory` | `app.api.v1.dealer_onboarding::admin_handover_inventory` | tags: Dealer: Onboarding
- `POST /api/v1/dealer/onboarding/admin/{application_id}/review` | `app.api.v1.dealer_onboarding::admin_manual_review` | tags: Dealer: Onboarding
- `POST /api/v1/dealer/onboarding/admin/{application_id}/schedule-visit` | `app.api.v1.dealer_onboarding::admin_schedule_visit` | tags: Dealer: Onboarding
- `POST /api/v1/dealer/onboarding/stage/complete-training` | `app.api.v1.dealer_onboarding::complete_training` | tags: Dealer: Onboarding
- `POST /api/v1/dealer/onboarding/stage/submit-kyc` | `app.api.v1.dealer_onboarding::submit_kyc` | tags: Dealer: Onboarding
- `POST /api/v1/dealer/onboarding/stage/trigger-checks` | `app.api.v1.dealer_onboarding::trigger_automated_checks` | tags: Dealer: Onboarding
- `GET /api/v1/dealer/onboarding/status` | `app.api.v1.dealer_onboarding::get_onboarding_status` | tags: Dealer: Onboarding

### dealer/portal (57)
- `GET /api/v1/dealer/portal/activity` | `app.api.v1.dealer_portal_dashboard::get_activity_feed` | tags: Dealer: Dashboard
- `GET /api/v1/dealer/portal/alerts` | `app.api.v1.dealer_portal_dashboard::get_alerts` | tags: Dealer: Dashboard
- `GET /api/v1/dealer/portal/campaigns` | `app.api.v1.dealer_portal_dashboard::get_dealer_campaigns` | tags: Dealer: Dashboard
- `GET /api/v1/dealer/portal/customers` | `app.api.v1.dealer_portal_dashboard::get_customers_list` | tags: Dealer: Dashboard
- `GET /api/v1/dealer/portal/dashboard` | `app.api.v1.dealer_portal_dashboard::get_dashboard_summary` | tags: Dealer: Dashboard
- `GET /api/v1/dealer/portal/documents` | `app.api.v1.dealer_portal_dashboard::list_dealer_documents` | tags: Dealer: Dashboard
- `POST /api/v1/dealer/portal/documents/upload` | `app.api.v1.dealer_portal_dashboard::upload_dealer_document` | tags: Dealer: Dashboard
- `GET /api/v1/dealer/portal/profile` | `app.api.v1.dealer_portal_dashboard::get_dealer_profile_details` | tags: Dealer: Dashboard
- `GET /api/v1/dealer/portal/roles` | `app.api.v1.dealer_portal_roles::get_roles` | tags: Dealer: Roles
- `POST /api/v1/dealer/portal/roles` | `app.api.v1.dealer_portal_roles::create_role` | tags: Dealer: Roles
- `GET /api/v1/dealer/portal/roles/matrix` | `app.api.v1.dealer_portal_roles::get_roles_matrix` | tags: Dealer: Roles
- `GET /api/v1/dealer/portal/roles/permissions/modules` | `app.api.v1.dealer_portal_roles::get_permission_modules` | tags: Dealer: Roles
- `POST /api/v1/dealer/portal/roles/users/invite` | `app.api.v1.dealer_portal_roles::invite_user` | tags: Dealer: Roles
- `DELETE /api/v1/dealer/portal/roles/{role_id}` | `app.api.v1.dealer_portal_roles::delete_role` | tags: Dealer: Roles
- `GET /api/v1/dealer/portal/roles/{role_id}` | `app.api.v1.dealer_portal_roles::get_role_detail` | tags: Dealer: Roles
- `PUT /api/v1/dealer/portal/roles/{role_id}` | `app.api.v1.dealer_portal_roles::update_role` | tags: Dealer: Roles
- `GET /api/v1/dealer/portal/roles/{role_id}/audit-log` | `app.api.v1.dealer_portal_roles::get_role_audit_log` | tags: Dealer: Roles
- `GET /api/v1/dealer/portal/roles/{role_id}/users` | `app.api.v1.dealer_portal_roles::get_role_users` | tags: Dealer: Roles
- `POST /api/v1/dealer/portal/roles/{role_id}/users` | `app.api.v1.dealer_portal_roles::assign_user_to_role` | tags: Dealer: Roles
- `DELETE /api/v1/dealer/portal/roles/{role_id}/users/{user_id}` | `app.api.v1.dealer_portal_roles::remove_user_from_role` | tags: Dealer: Roles
- `GET /api/v1/dealer/portal/settings/bank-account` | `app.api.v1.dealer_portal_settings::get_bank_account` | tags: Dealer: Settings
- `POST /api/v1/dealer/portal/settings/bank-account` | `app.api.v1.dealer_portal_settings::update_bank_account` | tags: Dealer: Settings
- `GET /api/v1/dealer/portal/settings/holiday-calendar` | `app.api.v1.dealer_portal_settings::get_holiday_calendar` | tags: Dealer: Settings
- `PATCH /api/v1/dealer/portal/settings/holiday-calendar` | `app.api.v1.dealer_portal_settings::update_holiday_calendar` | tags: Dealer: Settings
- `GET /api/v1/dealer/portal/settings/inventory-rules` | `app.api.v1.dealer_portal_settings::get_inventory_rules` | tags: Dealer: Settings
- `PATCH /api/v1/dealer/portal/settings/inventory-rules` | `app.api.v1.dealer_portal_settings::update_inventory_rules` | tags: Dealer: Settings
- `GET /api/v1/dealer/portal/settings/notification-preferences` | `app.api.v1.dealer_portal_settings::get_notification_preferences` | tags: Dealer: Settings
- `PUT /api/v1/dealer/portal/settings/notification-preferences` | `app.api.v1.dealer_portal_settings::update_notification_preferences` | tags: Dealer: Settings
- `GET /api/v1/dealer/portal/settings/notifications` | `app.api.v1.dealer_portal_settings::list_notifications` | tags: Dealer: Settings
- `PATCH /api/v1/dealer/portal/settings/notifications/read-all` | `app.api.v1.dealer_portal_settings::mark_all_read` | tags: Dealer: Settings
- `PATCH /api/v1/dealer/portal/settings/notifications/{notification_id}/read` | `app.api.v1.dealer_portal_settings::mark_notification_read` | tags: Dealer: Settings
- `GET /api/v1/dealer/portal/settings/profile` | `app.api.v1.dealer_portal_settings::get_profile` | tags: Dealer: Settings
- `PATCH /api/v1/dealer/portal/settings/profile` | `app.api.v1.dealer_portal_settings::update_profile` | tags: Dealer: Settings
- `GET /api/v1/dealer/portal/settings/rental-settings` | `app.api.v1.dealer_portal_settings::get_rental_settings` | tags: Dealer: Settings
- `PATCH /api/v1/dealer/portal/settings/rental-settings` | `app.api.v1.dealer_portal_settings::update_rental_settings` | tags: Dealer: Settings
- `GET /api/v1/dealer/portal/settings/station-defaults` | `app.api.v1.dealer_portal_settings::get_station_defaults` | tags: Dealer: Settings
- `PATCH /api/v1/dealer/portal/settings/station-defaults` | `app.api.v1.dealer_portal_settings::update_station_defaults` | tags: Dealer: Settings
- `GET /api/v1/dealer/portal/tickets` | `app.api.v1.dealer_portal_tickets::list_tickets` | tags: Dealer: Tickets
- `POST /api/v1/dealer/portal/tickets` | `app.api.v1.dealer_portal_tickets::create_ticket` | tags: Dealer: Tickets
- `GET /api/v1/dealer/portal/tickets/{ticket_id}` | `app.api.v1.dealer_portal_tickets::get_ticket_detail` | tags: Dealer: Tickets
- `PATCH /api/v1/dealer/portal/tickets/{ticket_id}/close` | `app.api.v1.dealer_portal_tickets::close_ticket` | tags: Dealer: Tickets
- `POST /api/v1/dealer/portal/tickets/{ticket_id}/reply` | `app.api.v1.dealer_portal_tickets::reply_to_ticket` | tags: Dealer: Tickets
- `GET /api/v1/dealer/portal/transactions` | `app.api.v1.dealer_portal_dashboard::get_dealer_transactions` | tags: Dealer: Dashboard
- `GET /api/v1/dealer/portal/users` | `app.api.v1.dealer_portal_users::list_dealer_users` | tags: Dealer: Users
- `POST /api/v1/dealer/portal/users` | `app.api.v1.dealer_portal_users::create_dealer_user` | tags: Dealer: Users
- `POST /api/v1/dealer/portal/users/bulk` | `app.api.v1.dealer_portal_users::bulk_action` | tags: Dealer: Users
- `POST /api/v1/dealer/portal/users/check-email` | `app.api.v1.dealer_portal_users::check_email_availability` | tags: Dealer: Users
- `GET /api/v1/dealer/portal/users/stats` | `app.api.v1.dealer_portal_users::get_user_stats` | tags: Dealer: Users
- `DELETE /api/v1/dealer/portal/users/{user_id}` | `app.api.v1.dealer_portal_users::delete_dealer_user` | tags: Dealer: Users
- `GET /api/v1/dealer/portal/users/{user_id}` | `app.api.v1.dealer_portal_users::get_dealer_user_detail` | tags: Dealer: Users
- `PUT /api/v1/dealer/portal/users/{user_id}` | `app.api.v1.dealer_portal_users::update_dealer_user` | tags: Dealer: Users
- `POST /api/v1/dealer/portal/users/{user_id}/resend-invite` | `app.api.v1.dealer_portal_users::resend_invite` | tags: Dealer: Users
- `POST /api/v1/dealer/portal/users/{user_id}/reset-password` | `app.api.v1.dealer_portal_users::reset_user_password` | tags: Dealer: Users
- `DELETE /api/v1/dealer/portal/users/{user_id}/sessions` | `app.api.v1.dealer_portal_users::terminate_all_sessions` | tags: Dealer: Users
- `GET /api/v1/dealer/portal/users/{user_id}/sessions` | `app.api.v1.dealer_portal_users::get_user_sessions` | tags: Dealer: Users
- `DELETE /api/v1/dealer/portal/users/{user_id}/sessions/{session_id}` | `app.api.v1.dealer_portal_users::terminate_session` | tags: Dealer: Users
- `PATCH /api/v1/dealer/portal/users/{user_id}/status` | `app.api.v1.dealer_portal_users::change_user_status` | tags: Dealer: Users

### dealers (28)
- `GET /api/v1/dealers/` | `app.api.v1.dealers::read_dealers` | tags: Dealer: Profile
- `POST /api/v1/dealers/` | `app.api.v1.dealers::create_dealer_profile` | tags: Dealer: Profile
- `POST /api/v1/dealers/application/{app_id}/stage` | `app.api.v1.dealers::update_stage` | tags: Dealer: Profile
- `PUT /api/v1/dealers/me` | `app.api.v1.dealers::update_my_profile` | tags: Dealer: Profile
- `GET /api/v1/dealers/me/bank-account` | `app.api.v1.dealers::get_bank_account` | tags: Dealer: Profile
- `POST /api/v1/dealers/me/bank-account` | `app.api.v1.dealers::update_bank_account` | tags: Dealer: Profile
- `GET /api/v1/dealers/me/commission-statement/{month}` | `app.api.v1.dealers::get_commission_statement` | tags: Dealer: Profile
- `GET /api/v1/dealers/me/commissions` | `app.api.v1.dealers::get_dealer_commissions` | tags: Dealer: Profile
- `GET /api/v1/dealers/me/dashboard` | `app.api.v1.dealers::get_dealer_dashboard` | tags: Dealer: Profile
- `GET /api/v1/dealers/me/documents` | `app.api.v1.dealers::list_dealer_documents` | tags: Dealer: Profile
- `POST /api/v1/dealers/me/documents` | `app.api.v1.dealers::upload_dealer_document` | tags: Dealer: Profile
- `DELETE /api/v1/dealers/me/documents/{id}` | `app.api.v1.dealers::delete_dealer_document` | tags: Dealer: Profile
- `GET /api/v1/dealers/me/inventory` | `app.api.v1.dealers::get_dealer_inventory` | tags: Dealer: Profile
- `GET /api/v1/dealers/me/promotions` | `app.api.v1.dealers::list_dealer_promotions` | tags: Dealer: Profile
- `POST /api/v1/dealers/me/promotions` | `app.api.v1.dealers::create_dealer_promotion` | tags: Dealer: Profile
- `PUT /api/v1/dealers/me/promotions/{id}` | `app.api.v1.dealers::update_dealer_promotion` | tags: Dealer: Profile
- `GET /api/v1/dealers/me/sales` | `app.api.v1.dealers::get_dealer_sales` | tags: Dealer: Profile
- `GET /api/v1/dealers/me/stations` | `app.api.v1.dealers::get_dealer_stations` | tags: Dealer: Profile
- `GET /api/v1/dealers/me/support-tickets` | `app.api.v1.dealers::get_dealer_support_tickets` | tags: Dealer: Profile
- `GET /api/v1/dealers/me/transactions` | `app.api.v1.dealers::get_dealer_transactions` | tags: Dealer: Profile
- `GET /api/v1/dealers/me/transactions/export` | `app.api.v1.dealers::export_dealer_transactions` | tags: Dealer: Profile
- `GET /api/v1/dealers/me/transactions/{txn_id}` | `app.api.v1.dealers::get_dealer_transaction_details` | tags: Dealer: Profile
- `GET /api/v1/dealers/registration-status` | `app.api.v1.dealers::get_registration_status` | tags: Dealer: Profile
- `GET /api/v1/dealers/settlements` | `app.api.v1.dealers::get_my_settlements` | tags: Dealer: Profile
- `POST /api/v1/dealers/settlements/generate` | `app.api.v1.dealers::generate_settlement` | tags: Dealer: Profile
- `POST /api/v1/dealers/visits/schedule` | `app.api.v1.dealers::schedule_visit` | tags: Dealer: Profile
- `GET /api/v1/dealers/{id}` | `app.api.v1.dealers::read_dealer` | tags: Dealer: Profile
- `PUT /api/v1/dealers/{id}` | `app.api.v1.dealers::update_dealer` | tags: Dealer: Profile

### drivers (3)
- `GET /api/v1/drivers/me` | `app.api.v1.drivers::get_my_driver_profile` | tags: Fleet Drivers
- `POST /api/v1/drivers/onboard` | `app.api.v1.drivers::onboard_driver` | tags: Fleet Drivers
- `GET /api/v1/drivers/routes` | `app.api.v1.drivers::get_assigned_routes` | tags: Fleet Drivers

### faqs (4)
- `GET /api/v1/faqs/` | `app.api.v1.faqs::get_faqs` | tags: FAQs
- `GET /api/v1/faqs/categories` | `app.api.v1.faqs::get_faq_categories` | tags: FAQs
- `GET /api/v1/faqs/{id}` | `app.api.v1.faqs::get_faq_detail` | tags: FAQs
- `POST /api/v1/faqs/{id}/helpful` | `app.api.v1.faqs::mark_faq_helpful` | tags: FAQs

### favorites (3)
- `GET /api/v1/favorites/stations` | `app.api.v1.favorites::get_favorite_stations` | tags: Favorites
- `DELETE /api/v1/favorites/stations/{station_id}` | `app.api.v1.favorites::remove_favorite_station` | tags: Favorites
- `POST /api/v1/favorites/stations/{station_id}` | `app.api.v1.favorites::add_favorite_station` | tags: Favorites

### fraud (5)
- `POST /api/v1/fraud/device/fingerprint` | `app.api.v1.fraud::submit_device_fingerprint` | tags: Fraud Detection
- `GET /api/v1/fraud/users/{user_id}/risk-score` | `app.api.v1.fraud::get_user_risk_score` | tags: Fraud Detection
- `POST /api/v1/fraud/verify/gst` | `app.api.v1.fraud::verify_gst` | tags: Fraud Detection
- `POST /api/v1/fraud/verify/pan` | `app.api.v1.fraud::verify_pan` | tags: Fraud Detection
- `POST /api/v1/fraud/verify/phone` | `app.api.v1.fraud::verify_phone` | tags: Fraud Detection

### health (2)
- `GET /api/v1/health` | `app.api.v1.system::health_check` | tags: System
- `GET /api/v1/health/detailed` | `app.api.v1.system::detailed_health_check` | tags: System

### i18n (2)
- `POST /api/v1/i18n/` | `app.api.v1.i18n::update_translation` | tags: i18n
- `GET /api/v1/i18n/{lang}` | `app.api.v1.i18n::get_translations` | tags: i18n

### inventory (7)
- `GET /api/v1/inventory/audit-trail` | `app.api.v1.inventory::get_inventory_audit_trail` | tags: Inventory
- `POST /api/v1/inventory/audit-trail/export` | `app.api.v1.inventory::export_inventory_audit` | tags: Inventory
- `GET /api/v1/inventory/low-stock` | `app.api.v1.inventory::get_low_stock_alerts` | tags: Inventory
- `GET /api/v1/inventory/transfers` | `app.api.v1.inventory::list_transfers` | tags: Inventory
- `POST /api/v1/inventory/transfers` | `app.api.v1.inventory::create_transfer_order` | tags: Inventory
- `GET /api/v1/inventory/transfers/{id}` | `app.api.v1.inventory::get_transfer_detail` | tags: Inventory
- `PUT /api/v1/inventory/transfers/{id}/confirm` | `app.api.v1.inventory::confirm_transfer_receipt` | tags: Inventory

### iot (3)
- `POST /api/v1/iot/{battery_id}/lock` | `app.api.v1.iot::lock_battery` | tags: IoT
- `POST /api/v1/iot/{battery_id}/shutdown` | `app.api.v1.iot::shutdown_battery` | tags: IoT
- `POST /api/v1/iot/{battery_id}/unlock` | `app.api.v1.iot::unlock_battery` | tags: IoT

### location (6)
- `GET /api/v1/location/{rental_id}/geofence/status` | `app.api.v1.location::get_geofence_status` | tags: Location
- `POST /api/v1/location/{rental_id}/location` | `app.api.v1.location::update_location` | tags: Location
- `GET /api/v1/location/{rental_id}/location/current` | `app.api.v1.location::get_current_location` | tags: Location
- `POST /api/v1/location/{rental_id}/location/history` | `app.api.v1.location::get_location_history` | tags: Location
- `GET /api/v1/location/{rental_id}/location/path` | `app.api.v1.location::get_travel_path` | tags: Location
- `GET /api/v1/location/{rental_id}/location/stats` | `app.api.v1.location::get_location_stats` | tags: Location

### locations (10)
- `GET /api/v1/locations/cities` | `app.api.v1.locations::read_cities` | tags: Locations Hierarchy
- `POST /api/v1/locations/cities` | `app.api.v1.locations::create_city` | tags: Locations Hierarchy
- `GET /api/v1/locations/continents` | `app.api.v1.locations::read_continents` | tags: Locations Hierarchy
- `POST /api/v1/locations/continents` | `app.api.v1.locations::create_continent` | tags: Locations Hierarchy
- `GET /api/v1/locations/countries` | `app.api.v1.locations::read_countries` | tags: Locations Hierarchy
- `POST /api/v1/locations/countries` | `app.api.v1.locations::create_country` | tags: Locations Hierarchy
- `GET /api/v1/locations/regions` | `app.api.v1.locations::read_regions` | tags: Locations Hierarchy
- `POST /api/v1/locations/regions` | `app.api.v1.locations::create_region` | tags: Locations Hierarchy
- `GET /api/v1/locations/zones` | `app.api.v1.locations::read_zones` | tags: Locations Hierarchy
- `POST /api/v1/locations/zones` | `app.api.v1.locations::create_zone` | tags: Locations Hierarchy

### logistics (37)
- `GET /api/v1/logistics/analytics/forecasting` | `app.api.v1.logistics::get_demand_forecasting` | tags: Logistics
- `GET /api/v1/logistics/analytics/performance` | `app.api.v1.logistics::get_logistics_performance_summary` | tags: Logistics
- `GET /api/v1/logistics/analytics/ranking` | `app.api.v1.logistics::get_driver_ranking` | tags: Logistics
- `GET /api/v1/logistics/analytics/utilization` | `app.api.v1.logistics::get_utilization_metrics` | tags: Logistics
- `GET /api/v1/logistics/dashboard` | `app.api.v1.logistics::get_driver_dashboard` | tags: Logistics
- `GET /api/v1/logistics/deliveries/active` | `app.api.v1.logistics::get_active_deliveries` | tags: Logistics
- `GET /api/v1/logistics/deliveries/history` | `app.api.v1.logistics::get_delivery_history` | tags: Logistics
- `GET /api/v1/logistics/deliveries/{id}/tracking` | `app.api.v1.logistics::track_delivery_live` | tags: Logistics
- `GET /api/v1/logistics/drivers` | `app.api.v1.logistics::list_drivers` | tags: Logistics
- `POST /api/v1/logistics/drivers` | `app.api.v1.logistics::create_driver` | tags: Logistics
- `GET /api/v1/logistics/drivers/{id}` | `app.api.v1.logistics::get_driver_detail` | tags: Logistics
- `PUT /api/v1/logistics/drivers/{id}` | `app.api.v1.logistics::update_driver_profile` | tags: Logistics
- `POST /api/v1/logistics/drivers/{id}/assign-vehicle` | `app.api.v1.logistics::assign_vehicle` | tags: Logistics
- `PUT /api/v1/logistics/drivers/{id}/availability` | `app.api.v1.logistics::toggle_driver_availability` | tags: Logistics
- `GET /api/v1/logistics/drivers/{id}/performance` | `app.api.v1.logistics::get_driver_kp_metrics` | tags: Logistics
- `PUT /api/v1/logistics/drivers/{id}/status` | `app.api.v1.logistics::update_driver_status` | tags: Logistics
- `POST /api/v1/logistics/handover/generate-qr` | `app.api.v1.logistics::generate_handover_qr` | tags: Logistics
- `POST /api/v1/logistics/handover/transfer` | `app.api.v1.logistics::process_transfer` | tags: Logistics
- `POST /api/v1/logistics/handover/verify` | `app.api.v1.logistics::verify_handover` | tags: Logistics
- `POST /api/v1/logistics/handover/warehouse-scan` | `app.api.v1.logistics::warehouse_scan` | tags: Logistics
- `GET /api/v1/logistics/me/assignments` | `app.api.v1.logistics::get_my_assignments` | tags: Logistics
- `POST /api/v1/logistics/notifications/delivery-update` | `app.api.v1.logistics::send_delivery_notification` | tags: Logistics
- `GET /api/v1/logistics/orders` | `app.api.v1.logistics::list_logistics_orders` | tags: Logistics
- `POST /api/v1/logistics/orders` | `app.api.v1.logistics::create_logistics_order` | tags: Logistics
- `GET /api/v1/logistics/orders/{id}` | `app.api.v1.logistics::get_order_details` | tags: Logistics
- `PUT /api/v1/logistics/orders/{id}/assign` | `app.api.v1.logistics::assign_order_to_driver` | tags: Logistics
- `GET /api/v1/logistics/orders/{id}/pod` | `app.api.v1.logistics::retrieve_order_pod` | tags: Logistics
- `POST /api/v1/logistics/orders/{id}/pod` | `app.api.v1.logistics::upload_order_pod` | tags: Logistics
- `GET /api/v1/logistics/orders/{id}/route` | `app.api.v1.logistics::get_order_live_route` | tags: Logistics
- `PUT /api/v1/logistics/orders/{id}/status` | `app.api.v1.logistics::update_order_status` | tags: Logistics
- `GET /api/v1/logistics/performance` | `app.api.v1.logistics::platform_logistics_metrics` | tags: Logistics
- `POST /api/v1/logistics/returns` | `app.api.v1.logistics::initiate_return_logistics` | tags: Logistics
- `GET /api/v1/logistics/returns/{id}` | `app.api.v1.logistics::get_return_request_detail` | tags: Logistics
- `GET /api/v1/logistics/routes/history` | `app.api.v1.logistics::get_route_history_endpoint` | tags: Logistics
- `POST /api/v1/logistics/routes/optimize` | `app.api.v1.logistics::optimize_driver_route` | tags: Logistics
- `GET /api/v1/logistics/routes/{id}` | `app.api.v1.logistics::get_route_details_endpoint` | tags: Logistics
- `PUT /api/v1/logistics/routes/{id}/recalculate` | `app.api.v1.logistics::recalculate_route_endpoint` | tags: Logistics

### maintenance (3)
- `POST /api/v1/maintenance/downtime` | `app.api.v1.maintenance::report_downtime` | tags: Maintenance
- `GET /api/v1/maintenance/history` | `app.api.v1.maintenance::get_maintenance_history` | tags: Maintenance
- `POST /api/v1/maintenance/record` | `app.api.v1.maintenance::create_maintenance_record` | tags: Maintenance

### manifests (5)
- `GET /api/v1/manifests/` | `app.api.v1.manifests::get_manifests` | tags: Manifests
- `POST /api/v1/manifests/` | `app.api.v1.manifests::create_manifest` | tags: Manifests
- `GET /api/v1/manifests/{manifest_id}` | `app.api.v1.manifests::get_manifest` | tags: Manifests
- `POST /api/v1/manifests/{manifest_id}/process` | `app.api.v1.manifests::process_manifest` | tags: Manifests
- `POST /api/v1/manifests/{manifest_id}/receive` | `app.api.v1.manifests::receive_manifest` | tags: Manifests

### me (1)
- `POST /api/v1/me/kyc/video-kyc/request` | `app.api.v1.kyc::request_video_kyc` | tags: KYC

### menus (5)
- `GET /api/v1/menus/` | `app.api.v1.menus::read_menus` | tags: Menus
- `POST /api/v1/menus/` | `app.api.v1.menus::create_menu` | tags: Menus
- `DELETE /api/v1/menus/{menu_id}` | `app.api.v1.menus::delete_menu` | tags: Menus
- `GET /api/v1/menus/{menu_id}` | `app.api.v1.menus::read_menu` | tags: Menus
- `PUT /api/v1/menus/{menu_id}` | `app.api.v1.menus::update_menu` | tags: Menus

### ml (2)
- `GET /api/v1/ml/battery-health/{battery_id}/predict` | `app.api.v1.ml::predict_battery_health` | tags: Machine Learning
- `GET /api/v1/ml/demand/forecast/{station_id}` | `app.api.v1.ml::forecast_demand` | tags: Machine Learning

### notifications (17)
- `DELETE /api/v1/notifications` | `app.api.v1.notifications_enhanced::clear_all_notifications` | tags: Notifications Enhanced
- `DELETE /api/v1/notifications/` | `app.api.v1.notifications::clear_all_notifications` | tags: Notifications
- `POST /api/v1/notifications/admin/bulk` | `app.api.v1.notifications::admin_bulk_notification` | tags: Notifications
- `DELETE /api/v1/notifications/device-token` | `app.api.v1.notifications_enhanced::unregister_device_token` | tags: Notifications Enhanced
- `POST /api/v1/notifications/device-token` | `app.api.v1.notifications::register_device_token` | tags: Notifications
- `POST /api/v1/notifications/device-token` | `app.api.v1.notifications_enhanced::register_device_token` | tags: Notifications Enhanced
- `GET /api/v1/notifications/my` | `app.api.v1.notifications::read_notifications` | tags: Notifications
- `PATCH /api/v1/notifications/read-all` | `app.api.v1.notifications::mark_all_notifications_read` | tags: Notifications
- `PATCH /api/v1/notifications/read-all` | `app.api.v1.notifications_enhanced::mark_all_notifications_read` | tags: Notifications Enhanced
- `PUT /api/v1/notifications/read-all` | `app.api.v1.notifications::put_mark_all_read` | tags: Notifications
- `POST /api/v1/notifications/send` | `app.api.v1.notifications::admin_send_notification` | tags: Notifications
- `GET /api/v1/notifications/unread-count` | `app.api.v1.notifications::get_my_unread_count` | tags: Notifications
- `DELETE /api/v1/notifications/{notification_id:int}` | `app.api.v1.notifications_enhanced::delete_notification` | tags: Notifications Enhanced
- `PATCH /api/v1/notifications/{notification_id:int}/read` | `app.api.v1.notifications_enhanced::mark_notification_read` | tags: Notifications Enhanced
- `DELETE /api/v1/notifications/{notification_id}` | `app.api.v1.notifications::delete_notification` | tags: Notifications
- `PATCH /api/v1/notifications/{notification_id}/read` | `app.api.v1.notifications::mark_notification_read` | tags: Notifications
- `PUT /api/v1/notifications/{notification_id}/read` | `app.api.v1.notifications::put_mark_notification_read` | tags: Notifications

### orders (14)
- `GET /api/v1/orders/` | `app.api.v1.orders::get_orders` | tags: Logistics Orders
- `POST /api/v1/orders/` | `app.api.v1.orders::create_order` | tags: Logistics Orders
- `GET /api/v1/orders/{order_id}` | `app.api.v1.orders::get_order` | tags: Logistics Orders
- `POST /api/v1/orders/{order_id}/assign-driver` | `app.api.v1.orders::assign_driver` | tags: Logistics Orders
- `PUT /api/v1/orders/{order_id}/assign-driver` | `app.api.v1.orders::assign_driver` | tags: Logistics Orders
- `POST /api/v1/orders/{order_id}/confirm-request` | `app.api.v1.orders::request_confirmation` | tags: Logistics Orders
- `POST /api/v1/orders/{order_id}/mark-failed` | `app.api.v1.orders::mark_failed` | tags: Logistics Orders
- `POST /api/v1/orders/{order_id}/mark-in-transit` | `app.api.v1.orders::mark_in_transit` | tags: Logistics Orders
- `POST /api/v1/orders/{order_id}/notify` | `app.api.v1.orders::send_notification` | tags: Logistics Orders
- `POST /api/v1/orders/{order_id}/proof-of-delivery` | `app.api.v1.orders::submit_proof_of_delivery` | tags: Logistics Orders
- `POST /api/v1/orders/{order_id}/refund` | `app.api.v1.orders::process_refund` | tags: Logistics Orders
- `POST /api/v1/orders/{order_id}/return` | `app.api.v1.orders::initiate_return` | tags: Logistics Orders
- `PUT /api/v1/orders/{order_id}/schedule` | `app.api.v1.orders::schedule_delivery` | tags: Logistics Orders
- `PUT /api/v1/orders/{order_id}/status` | `app.api.v1.orders::update_order_status` | tags: Logistics Orders

### organizations (6)
- `GET /api/v1/organizations/` | `app.api.v1.organizations::read_organizations` | tags: Organizations
- `POST /api/v1/organizations/` | `app.api.v1.organizations::create_organization` | tags: Organizations
- `DELETE /api/v1/organizations/{organization_id}` | `app.api.v1.organizations::delete_organization` | tags: Organizations
- `GET /api/v1/organizations/{organization_id}` | `app.api.v1.organizations::read_organization` | tags: Organizations
- `PATCH /api/v1/organizations/{organization_id}` | `app.api.v1.organizations::update_organization` | tags: Organizations
- `POST /api/v1/organizations/{organization_id}/logo` | `app.api.v1.organizations::upload_organization_logo` | tags: Organizations

### pan-verify (1)
- `POST /api/v1/pan-verify` | `app.api.v1.kyc::verify_pan` | tags: KYC

### payments (25)
- `GET /api/v1/payments/admin/payments` | `app.api.v1.payments::admin_get_all_payments` | tags: Payments
- `GET /api/v1/payments/admin/profit-margins` | `app.api.v1.payments::get_profit_margins` | tags: Payments
- `GET /api/v1/payments/admin/revenue` | `app.api.v1.payments::get_revenue_dashboard` | tags: Payments
- `GET /api/v1/payments/admin/revenue/by-station` | `app.api.v1.payments::get_revenue_by_station` | tags: Payments
- `GET /api/v1/payments/admin/revenue/forecast` | `app.api.v1.payments::get_revenue_forecast` | tags: Payments
- `GET /api/v1/payments/invoice/{transaction_id}` | `app.api.v1.payments_enhanced::get_invoice` | tags: Payments Enhanced
- `GET /api/v1/payments/methods` | `app.api.v1.payments_enhanced::list_payment_methods` | tags: Payments Enhanced
- `POST /api/v1/payments/methods` | `app.api.v1.payments::add_payment_method` | tags: Payments
- `POST /api/v1/payments/methods` | `app.api.v1.payments_enhanced::add_payment_method` | tags: Payments Enhanced
- `DELETE /api/v1/payments/methods/{method_id}` | `app.api.v1.payments::delete_payment_method` | tags: Payments
- `DELETE /api/v1/payments/methods/{method_id}` | `app.api.v1.payments_enhanced::delete_payment_method` | tags: Payments Enhanced
- `POST /api/v1/payments/methods/{method_id}/default` | `app.api.v1.payments_enhanced::set_default_payment_method` | tags: Payments Enhanced
- `GET /api/v1/payments/orders/{order_id}/invoice` | `app.api.v1.payments::download_order_invoice` | tags: Payments
- `POST /api/v1/payments/orders/{order_id}/refund` | `app.api.v1.payments::request_refund` | tags: Payments
- `GET /api/v1/payments/payment-methods` | `app.api.v1.payments::get_payment_methods` | tags: Payments
- `POST /api/v1/payments/razorpay/webhook` | `app.api.v1.payments_enhanced::razorpay_webhook` | tags: Payments Enhanced
- `GET /api/v1/payments/refunds` | `app.api.v1.payments::get_user_refunds` | tags: Payments
- `GET /api/v1/payments/refunds/history` | `app.api.v1.payments_enhanced::list_refunds` | tags: Payments Enhanced
- `GET /api/v1/payments/rentals/{rental_id}/invoice` | `app.api.v1.payments::download_rental_invoice` | tags: Payments
- `GET /api/v1/payments/transactions` | `app.api.v1.payments::get_user_all_payments` | tags: Payments
- `POST /api/v1/payments/webhooks/razorpay` | `app.api.v1.payments::razorpay_webhook` | tags: Payments
- `GET /api/v1/payments/{id}` | `app.api.v1.payments::get_payment_detail` | tags: Payments
- `POST /api/v1/payments/{id}/refund` | `app.api.v1.payments::admin_initiate_refund` | tags: Payments
- `GET /api/v1/payments/{id}/refund-status` | `app.api.v1.payments::get_refund_status` | tags: Payments
- `GET /api/v1/payments/{transaction_id}/receipt` | `app.api.v1.payments_enhanced::get_receipt` | tags: Payments Enhanced

### profile (14)
- `GET /api/v1/profile` | `app.api.v1.profile::get_profile` | tags: Profile
- `PUT /api/v1/profile` | `app.api.v1.profile::update_profile` | tags: Profile
- `DELETE /api/v1/profile/account` | `app.api.v1.profile::deactivate_account` | tags: Profile
- `GET /api/v1/profile/addresses` | `app.api.v1.profile::get_addresses` | tags: Profile
- `POST /api/v1/profile/addresses` | `app.api.v1.profile::create_address` | tags: Profile
- `DELETE /api/v1/profile/addresses/{address_id}` | `app.api.v1.profile::delete_address` | tags: Profile
- `PUT /api/v1/profile/addresses/{address_id}` | `app.api.v1.profile::update_address` | tags: Profile
- `POST /api/v1/profile/change-password` | `app.api.v1.profile::change_password` | tags: Profile
- `GET /api/v1/profile/login-history` | `app.api.v1.profile::login_history` | tags: Profile
- `POST /api/v1/profile/picture` | `app.api.v1.profile::upload_profile_picture` | tags: Profile
- `GET /api/v1/profile/preferences` | `app.api.v1.profile::get_preferences` | tags: Profile
- `PUT /api/v1/profile/preferences` | `app.api.v1.profile::update_preferences` | tags: Profile
- `GET /api/v1/profile/sessions` | `app.api.v1.profile::get_sessions` | tags: Profile
- `DELETE /api/v1/profile/sessions/{session_id}` | `app.api.v1.profile::revoke_session` | tags: Profile

### promo (2)
- `POST /api/v1/promo/apply` | `app.api.v1.promo::apply_promo` | tags: Promo
- `POST /api/v1/promo/validate` | `app.api.v1.promo::validate_promo` | tags: Promo

### purchases (4)
- `DELETE /api/v1/purchases/cart/{item_id}` | `app.api.v1.purchases_enhanced::remove_cart_item` | tags: Purchases Enhanced
- `PATCH /api/v1/purchases/cart/{item_id}` | `app.api.v1.purchases_enhanced::update_cart_item` | tags: Purchases Enhanced
- `POST /api/v1/purchases/orders/{order_id}/cancel` | `app.api.v1.purchases_enhanced::cancel_order` | tags: Purchases Enhanced
- `POST /api/v1/purchases/orders/{order_id}/warranty` | `app.api.v1.purchases_enhanced::claim_warranty` | tags: Purchases Enhanced

### rejection-reasons (1)
- `GET /api/v1/rejection-reasons` | `app.api.v1.kyc::get_kyc_rejection_reasons` | tags: KYC

### rentals (19)
- `GET /api/v1/rentals/` | `app.api.v1.rentals::read_rentals` | tags: Rentals
- `POST /api/v1/rentals/` | `app.api.v1.rentals::create_rental` | tags: Rentals
- `GET /api/v1/rentals/active` | `app.api.v1.rentals::read_active_rentals` | tags: Rentals
- `GET /api/v1/rentals/active/current` | `app.api.v1.rentals::read_current_active_rental` | tags: Rentals
- `GET /api/v1/rentals/admin/all` | `app.api.v1.rentals::read_rentals` | tags: Rentals
- `GET /api/v1/rentals/history` | `app.api.v1.rentals::read_rental_history` | tags: Rentals
- `GET /api/v1/rentals/my` | `app.api.v1.rentals::read_my_rentals` | tags: Rentals
- `POST /api/v1/rentals/{rental_id}/extend` | `app.api.v1.rentals::request_extension` | tags: Rentals
- `GET /api/v1/rentals/{rental_id}/late-fees` | `app.api.v1.rentals::get_late_fees` | tags: Rentals
- `POST /api/v1/rentals/{rental_id}/late-fees/waiver` | `app.api.v1.rentals::request_late_fee_waiver` | tags: Rentals
- `POST /api/v1/rentals/{rental_id}/pause` | `app.api.v1.rentals::request_pause` | tags: Rentals
- `GET /api/v1/rentals/{rental_id}/receipt` | `app.api.v1.rentals::get_rental_receipt_v2` | tags: Rentals
- `GET /api/v1/rentals/{rental_id}/receipt` | `app.api.v1.rentals_enhanced::get_rental_receipt` | tags: Rentals Enhanced
- `POST /api/v1/rentals/{rental_id}/report-issue` | `app.api.v1.rentals::report_rental_issue` | tags: Rentals
- `POST /api/v1/rentals/{rental_id}/report-issue` | `app.api.v1.rentals_enhanced::report_rental_issue` | tags: Rentals Enhanced
- `POST /api/v1/rentals/{rental_id}/resume` | `app.api.v1.rentals::resume_rental` | tags: Rentals
- `POST /api/v1/rentals/{rental_id}/return` | `app.api.v1.rentals::return_rental_battery` | tags: Rentals
- `POST /api/v1/rentals/{rental_id}/swap-request` | `app.api.v1.rentals::request_battery_swap` | tags: Rentals
- `GET /api/v1/rentals/{rental_id}/swap-suggestions` | `app.api.v1.rentals::get_swap_suggestions` | tags: Rentals

### resubmit (1)
- `POST /api/v1/resubmit` | `app.api.v1.kyc::resubmit_kyc` | tags: KYC

### role-rights (3)
- `POST /api/v1/role-rights/` | `app.api.v1.role_rights::create_role_right` | tags: Role Rights
- `GET /api/v1/role-rights/role/{role_id}` | `app.api.v1.role_rights::read_role_rights` | tags: Role Rights
- `PUT /api/v1/role-rights/{right_id}` | `app.api.v1.role_rights::update_role_right` | tags: Role Rights

### roles (5)
- `GET /api/v1/roles/` | `app.api.v1.roles::read_roles` | tags: Roles
- `POST /api/v1/roles/` | `app.api.v1.roles::create_role` | tags: Roles
- `DELETE /api/v1/roles/{role_id}` | `app.api.v1.roles::delete_role` | tags: Roles
- `GET /api/v1/roles/{role_id}` | `app.api.v1.roles::read_role` | tags: Roles
- `PUT /api/v1/roles/{role_id}` | `app.api.v1.roles::update_role` | tags: Roles

### root (4)
- `GET /` | `app.main::root` | tags: System
- `GET /health` | `app.main::health_check` | tags: System
- `GET /live` | `app.main::live_check` | tags: System
- `GET /ready` | `app.main::readiness_check` | tags: System

### routes (1)
- `POST /api/v1/routes/optimize` | `app.api.v1.routes::optimize_route` | tags: Route Optimization

### screens (1)
- `GET /api/v1/screens/{screen_id}/config` | `app.api.v1.screens::get_screen_config` | tags: UI Config

### sessions (2)
- `GET /api/v1/sessions/list` | `app.api.v1.sessions::list_sessions` | tags: Sessions
- `POST /api/v1/sessions/revoke/{session_id}` | `app.api.v1.sessions::revoke_session` | tags: Sessions

### settlements (3)
- `GET /api/v1/settlements/` | `app.api.v1.settlements::read_settlements` | tags: Settlements
- `POST /api/v1/settlements/generate` | `app.api.v1.settlements::generate_settlement` | tags: Settlements
- `PUT /api/v1/settlements/{settlement_id}` | `app.api.v1.settlements::update_settlement_status` | tags: Settlements

### station-monitoring (3)
- `POST /api/v1/station-monitoring/charging/prioritize` | `app.api.v1.station_monitoring::prioritize_charging` | tags: Station Monitoring
- `PATCH /api/v1/station-monitoring/charging/reprioritize` | `app.api.v1.station_monitoring::reprioritize_charging` | tags: Station Monitoring
- `POST /api/v1/station-monitoring/heartbeat` | `app.api.v1.station_monitoring::record_heartbeat` | tags: Station Monitoring

### stations (23)
- `GET /api/v1/stations/` | `app.api.v1.stations::read_stations` | tags: Stations
- `POST /api/v1/stations/` | `app.api.v1.stations::create_station` | tags: Stations
- `GET /api/v1/stations/heatmap` | `app.api.v1.stations::get_stations_heatmap` | tags: Stations
- `GET /api/v1/stations/map` | `app.api.v1.stations::get_stations_map` | tags: Stations
- `GET /api/v1/stations/nearby` | `app.api.v1.stations::search_nearby_stations` | tags: Stations
- `DELETE /api/v1/stations/{station_id}` | `app.api.v1.stations::delete_station` | tags: Stations
- `GET /api/v1/stations/{station_id}` | `app.api.v1.stations::read_station` | tags: Stations
- `PUT /api/v1/stations/{station_id}` | `app.api.v1.stations::update_station` | tags: Stations
- `GET /api/v1/stations/{station_id}/batteries` | `app.api.v1.stations::read_station_batteries` | tags: Stations
- `DELETE /api/v1/stations/{station_id}/favorite` | `app.api.v1.stations::unfavorite_station` | tags: Stations
- `POST /api/v1/stations/{station_id}/favorite` | `app.api.v1.stations::favorite_station` | tags: Stations
- `GET /api/v1/stations/{station_id}/maintenance-schedule` | `app.api.v1.stations::read_station_maintenance_schedule` | tags: Stations
- `POST /api/v1/stations/{station_id}/maintenance-schedule` | `app.api.v1.stations::create_station_maintenance_task` | tags: Stations
- `PUT /api/v1/stations/{station_id}/maintenance-schedule/{task_id}` | `app.api.v1.stations::update_station_maintenance_task` | tags: Stations
- `GET /api/v1/stations/{station_id}/performance` | `app.api.v1.stations::read_station_performance` | tags: Stations
- `POST /api/v1/stations/{station_id}/photos` | `app.api.v1.stations::upload_station_photo` | tags: Stations
- `DELETE /api/v1/stations/{station_id}/photos/{photo_id}` | `app.api.v1.stations::delete_station_photo` | tags: Stations
- `GET /api/v1/stations/{station_id}/rental-history` | `app.api.v1.stations::read_station_rental_history` | tags: Stations
- `GET /api/v1/stations/{station_id}/reviews` | `app.api.v1.stations::read_station_reviews` | tags: Stations
- `POST /api/v1/stations/{station_id}/reviews` | `app.api.v1.stations::create_review` | tags: Stations
- `DELETE /api/v1/stations/{station_id}/reviews/{review_id}` | `app.api.v1.stations::delete_review` | tags: Stations
- `PUT /api/v1/stations/{station_id}/reviews/{review_id}` | `app.api.v1.stations::update_review` | tags: Stations
- `PUT /api/v1/stations/{station_id}/status` | `app.api.v1.stations::update_station_status` | tags: Stations

### status (1)
- `GET /api/v1/status` | `app.api.v1.kyc::get_kyc_status` | tags: KYC

### stock (5)
- `POST /api/v1/stock/adjust` | `app.api.v1.stock::adjust_stock` | tags: Stock
- `GET /api/v1/stock/product/{product_id}` | `app.api.v1.stock::read_product_stock` | tags: Stock
- `POST /api/v1/stock/receive` | `app.api.v1.stock::receive_stock` | tags: Stock
- `POST /api/v1/stock/transfer` | `app.api.v1.stock::transfer_stock` | tags: Stock
- `GET /api/v1/stock/warehouse/{warehouse_id}` | `app.api.v1.stock::read_warehouse_stock` | tags: Stock

### submit (1)
- `POST /api/v1/submit` | `app.api.v1.kyc::submit_kyc_document` | tags: KYC

### support (19)
- `GET /api/v1/support/admin/support/performance` | `app.api.v1.support::get_support_agent_performance` | tags: Support
- `GET /api/v1/support/admin/support/queue` | `app.api.v1.support::get_support_queue_stats` | tags: Support
- `GET /api/v1/support/admin/tickets` | `app.api.v1.support::admin_read_tickets` | tags: Support
- `POST /api/v1/support/chat/initiate` | `app.api.v1.support::initiate_live_chat` | tags: Support
- `GET /api/v1/support/chat/{sessionId}/history` | `app.api.v1.support::get_chat_history` | tags: Support
- `POST /api/v1/support/chat/{sessionId}/message` | `app.api.v1.support::send_chat_message` | tags: Support
- `GET /api/v1/support/faq` | `app.api.v1.support::list_faqs` | tags: Support
- `GET /api/v1/support/faq/search` | `app.api.v1.support::search_faq` | tags: Support
- `GET /api/v1/support/faq/search` | `app.api.v1.support_enhanced::search_faq` | tags: Support Enhanced
- `GET /api/v1/support/faq/{faq_id}` | `app.api.v1.support::get_faq_detail` | tags: Support
- `POST /api/v1/support/feedback` | `app.api.v1.support::submit_feedback` | tags: Support
- `GET /api/v1/support/feedback/my` | `app.api.v1.support::list_my_feedback` | tags: Support
- `POST /api/v1/support/tickets` | `app.api.v1.support::create_ticket` | tags: Support
- `GET /api/v1/support/tickets/my` | `app.api.v1.support::read_my_tickets` | tags: Support
- `GET /api/v1/support/tickets/{ticket_id}` | `app.api.v1.support::read_ticket_detail` | tags: Support
- `POST /api/v1/support/tickets/{ticket_id}/attachment` | `app.api.v1.support::upload_ticket_attachment` | tags: Support
- `POST /api/v1/support/tickets/{ticket_id}/attachment` | `app.api.v1.support_enhanced::upload_ticket_attachment` | tags: Support Enhanced
- `PUT /api/v1/support/tickets/{ticket_id}/close` | `app.api.v1.support::close_ticket` | tags: Support
- `POST /api/v1/support/tickets/{ticket_id}/reply` | `app.api.v1.support::reply_ticket` | tags: Support

### swaps (2)
- `POST /api/v1/swaps/initiate` | `app.api.v1.swaps::initiate_swap` | tags: Swaps
- `POST /api/v1/swaps/{swap_id}/complete` | `app.api.v1.swaps::complete_swap` | tags: Swaps

### telematics (2)
- `GET /api/v1/telematics/battery/{battery_id}/latest` | `app.api.v1.telematics::get_latest_telemetry` | tags: Telematics
- `POST /api/v1/telematics/ingest` | `app.api.v1.telematics::ingest_telemetry` | tags: Telematics

### telemetry (5)
- `GET /api/v1/telemetry/rentals/{rental_id}/geofence-status` | `app.api.v1.telemetry::get_geofence_status` | tags: Telemetry
- `POST /api/v1/telemetry/rentals/{rental_id}/location` | `app.api.v1.telemetry::update_location` | tags: Telemetry
- `GET /api/v1/telemetry/rentals/{rental_id}/location-history` | `app.api.v1.telemetry::get_location_history_points` | tags: Telemetry
- `GET /api/v1/telemetry/rentals/{rental_id}/telemetry` | `app.api.v1.telemetry::get_rental_telemetry` | tags: Telemetry
- `GET /api/v1/telemetry/rentals/{rental_id}/travel-path` | `app.api.v1.telemetry::get_travel_path` | tags: Telemetry

### transactions (2)
- `GET /api/v1/transactions/` | `app.api.v1.transactions::get_my_transactions` | tags: Transactions
- `GET /api/v1/transactions/{id}/invoice` | `app.api.v1.transactions::get_invoice` | tags: Transactions

### users (30)
- `GET /api/v1/users/` | `app.api.v1.users::read_users` | tags: Users
- `POST /api/v1/users/` | `app.api.v1.users::create_user` | tags: Users
- `DELETE /api/v1/users/me` | `app.api.v1.users::delete_my_account` | tags: Users
- `GET /api/v1/users/me` | `app.api.v1.users::read_user_me` | tags: Users
- `PATCH /api/v1/users/me` | `app.api.v1.users::partial_update_user_me` | tags: Users
- `PUT /api/v1/users/me` | `app.api.v1.users::update_user_me` | tags: Users
- `GET /api/v1/users/me/activity-log` | `app.api.v1.users::get_my_activity_log` | tags: Users
- `GET /api/v1/users/me/addresses` | `app.api.v1.users::read_addresses` | tags: Users
- `POST /api/v1/users/me/addresses` | `app.api.v1.users::create_address` | tags: Users
- `DELETE /api/v1/users/me/addresses/{address_id}` | `app.api.v1.users::delete_address` | tags: Users
- `PUT /api/v1/users/me/addresses/{address_id}` | `app.api.v1.users::update_address` | tags: Users
- `PUT /api/v1/users/me/addresses/{address_id}/default` | `app.api.v1.users::set_default_address` | tags: Users
- `DELETE /api/v1/users/me/avatar` | `app.api.v1.users::delete_avatar` | tags: Users
- `POST /api/v1/users/me/avatar` | `app.api.v1.users::upload_avatar` | tags: Users
- `GET /api/v1/users/me/dashboard-summary` | `app.api.v1.users::get_my_dashboard_summary` | tags: Users
- `GET /api/v1/users/me/dashboard-widgets` | `app.api.v1.users::get_user_dashboard_config` | tags: Users
- `GET /api/v1/users/me/feature-flags` | `app.api.v1.users::get_user_feature_flags` | tags: Users
- `GET /api/v1/users/me/login-history` | `app.api.v1.users::get_my_login_history` | tags: Users
- `GET /api/v1/users/me/membership` | `app.api.v1.users::get_my_membership` | tags: Users
- `GET /api/v1/users/me/menu-config` | `app.api.v1.users::get_user_menu_config` | tags: Users
- `GET /api/v1/users/me/notification-preferences` | `app.api.v1.users::get_notification_preferences` | tags: Users
- `PUT /api/v1/users/me/notification-preferences` | `app.api.v1.users::update_notification_preferences` | tags: Users
- `POST /api/v1/users/me/profile-picture` | `app.api.v1.users::upload_profile_picture` | tags: Users
- `GET /api/v1/users/me/sessions` | `app.api.v1.users::get_my_sessions` | tags: Users
- `DELETE /api/v1/users/me/sessions/{session_id}` | `app.api.v1.users::revoke_session` | tags: Users
- `GET /api/v1/users/search` | `app.api.v1.users::search_users` | tags: Users
- `DELETE /api/v1/users/{user_id}` | `app.api.v1.users::delete_user` | tags: Users
- `GET /api/v1/users/{user_id}` | `app.api.v1.users::get_user_by_id` | tags: Users
- `GET /api/v1/users/{user_id}/activity` | `app.api.v1.users::get_user_activity` | tags: Users
- `PUT /api/v1/users/{user_id}/status` | `app.api.v1.users::update_user_status` | tags: Users

### utility-bill-verify (1)
- `POST /api/v1/utility-bill-verify` | `app.api.v1.kyc::verify_utility_bill` | tags: KYC

### utils (1)
- `POST /api/v1/utils/upload` | `app.api.v1.utils::upload_file` | tags: Utilities

### vehicles (3)
- `GET /api/v1/vehicles/` | `app.api.v1.vehicles::read_my_vehicles` | tags: Vehicles
- `POST /api/v1/vehicles/` | `app.api.v1.vehicles::create_vehicle` | tags: Vehicles
- `DELETE /api/v1/vehicles/{vehicle_id}` | `app.api.v1.vehicles::delete_vehicle` | tags: Vehicles

### version (1)
- `GET /api/v1/version` | `app.api.v1.system::get_version` | tags: System

### video-kyc (1)
- `POST /api/v1/video-kyc` | `app.api.v1.kyc::upload_video_kyc` | tags: KYC

### wallet (15)
- `GET /api/v1/wallet/` | `app.api.v1.wallet::get_wallet_balance` | tags: Wallet
- `GET /api/v1/wallet/balance` | `app.api.v1.wallet::get_wallet_balance` | tags: Wallet
- `GET /api/v1/wallet/cashback` | `app.api.v1.wallet::get_cashback_history` | tags: Wallet
- `GET /api/v1/wallet/cashback` | `app.api.v1.wallet_enhanced::get_cashback_history` | tags: Wallet Enhanced
- `GET /api/v1/wallet/lookup` | `app.api.v1.wallet::lookup_user_by_phone` | tags: Wallet
- `GET /api/v1/wallet/payment-methods` | `app.api.v1.wallet::list_payment_methods` | tags: Wallet
- `POST /api/v1/wallet/payment-methods` | `app.api.v1.wallet::add_payment_method` | tags: Wallet
- `DELETE /api/v1/wallet/payment-methods/{method_id}` | `app.api.v1.wallet::remove_payment_method` | tags: Wallet
- `POST /api/v1/wallet/recharge` | `app.api.v1.wallet::recharge_wallet` | tags: Wallet
- `GET /api/v1/wallet/transactions` | `app.api.v1.wallet::get_wallet_transactions` | tags: Wallet
- `GET /api/v1/wallet/transactions/{payment_id}/receipt` | `app.api.v1.wallet::get_payment_receipt` | tags: Wallet
- `POST /api/v1/wallet/transfer` | `app.api.v1.wallet::transfer_to_user` | tags: Wallet
- `POST /api/v1/wallet/transfer` | `app.api.v1.wallet_enhanced::transfer_to_user` | tags: Wallet Enhanced
- `POST /api/v1/wallet/withdraw` | `app.api.v1.wallet::request_withdrawal` | tags: Wallet
- `POST /api/v1/wallet/withdrawals` | `app.api.v1.wallet_enhanced::withdraw_from_wallet` | tags: Wallet Enhanced

### warehouse (3)
- `GET /api/v1/warehouse/` | `app.api.v1.warehouse_structure::get_warehouse_structure` | tags: Warehouse Structure
- `GET /api/v1/warehouse/all` | `app.api.v1.warehouse_structure::list_warehouse_structures` | tags: Warehouse Structure
- `POST /api/v1/warehouse/shelves/{shelf_id}/batteries` | `app.api.v1.warehouse_structure::assign_battery_to_shelf` | tags: Warehouse Structure

### warehouses (5)
- `GET /api/v1/warehouses/` | `app.api.v1.warehouses::read_warehouses` | tags: Warehouses
- `POST /api/v1/warehouses/` | `app.api.v1.warehouses::create_warehouse` | tags: Warehouses
- `DELETE /api/v1/warehouses/{id}` | `app.api.v1.warehouses::delete_warehouse` | tags: Warehouses
- `GET /api/v1/warehouses/{id}` | `app.api.v1.warehouses::read_warehouse` | tags: Warehouses
- `PUT /api/v1/warehouses/{id}` | `app.api.v1.warehouses::update_warehouse` | tags: Warehouses