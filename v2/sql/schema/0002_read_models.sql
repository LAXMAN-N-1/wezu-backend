-- read-optimized materialized view for high-traffic analytics reads

CREATE MATERIALIZED VIEW IF NOT EXISTS analytics_overview_mv AS
SELECT
  (SELECT COUNT(*) FROM users WHERE is_deleted = false AND status IN ('active', 'verified')) AS active_users,
  (SELECT COUNT(*) FROM stations WHERE status = 'active' AND approval_status = 'approved') AS active_stations,
  (SELECT COUNT(*) FROM support_tickets WHERE status IN ('open', 'in_progress')) AS open_tickets,
  (SELECT COUNT(*) FROM swap_sessions WHERE created_at >= NOW() - INTERVAL '24 hours') AS swaps_24h,
  (SELECT COALESCE(AVG(swap_amount), 0) FROM swap_sessions WHERE created_at >= NOW() - INTERVAL '24 hours') AS avg_swap_amount_24h,
  (SELECT COUNT(*) FROM stocks WHERE quantity_available <= reorder_level) AS low_stock_items,
  NOW()::timestamptz AS generated_at;

CREATE UNIQUE INDEX IF NOT EXISTS idx_analytics_overview_mv_singleton
  ON analytics_overview_mv ((1));
