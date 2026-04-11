-- v2 hot-path indexes for keyset pagination and filtered reads

CREATE INDEX IF NOT EXISTS idx_users_created_desc
  ON users (created_at DESC, id DESC)
  WHERE is_deleted = false;

CREATE INDEX IF NOT EXISTS idx_users_identity_lookup
  ON users (email, phone_number)
  WHERE is_deleted = false;

CREATE INDEX IF NOT EXISTS idx_stations_updated_desc
  ON stations (updated_at DESC, id DESC)
  WHERE approval_status = 'approved';

CREATE INDEX IF NOT EXISTS idx_stations_city_status
  ON stations (city, status, updated_at DESC)
  WHERE approval_status = 'approved';

CREATE INDEX IF NOT EXISTS idx_swap_sessions_created_desc
  ON swap_sessions (created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_swap_sessions_user_created
  ON swap_sessions (user_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_swap_sessions_station_created
  ON swap_sessions (station_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_support_tickets_created_desc
  ON support_tickets (created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_support_tickets_status_priority_created
  ON support_tickets (status, priority, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_stocks_low_inventory
  ON stocks (warehouse_id, quantity_available, reorder_level)
  WHERE quantity_available <= reorder_level;

CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp_desc
  ON audit_logs (timestamp DESC, id DESC);
