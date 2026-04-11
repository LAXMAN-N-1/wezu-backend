-- name: GetAnalyticsOverviewMV :one
SELECT active_users, active_stations, open_tickets, swaps_24h, avg_swap_amount_24h, low_stock_items, generated_at
FROM analytics_overview_mv;
