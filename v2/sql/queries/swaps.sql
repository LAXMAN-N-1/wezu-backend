-- name: ListSwapsByScope :many
SELECT id, user_id, station_id, old_battery_id, new_battery_id, swap_amount, currency, status, payment_status, created_at
FROM swap_sessions
WHERE (sqlc.arg(user_id)::bigint IS NULL OR user_id = sqlc.arg(user_id))
  AND (sqlc.arg(station_id)::bigint IS NULL OR station_id = sqlc.arg(station_id))
  AND (
    (sqlc.arg(cursor_created_at)::timestamptz IS NULL AND sqlc.arg(cursor_id)::bigint IS NULL)
    OR (created_at, id) < (sqlc.arg(cursor_created_at)::timestamptz, sqlc.arg(cursor_id)::bigint)
  )
ORDER BY created_at DESC, id DESC
LIMIT sqlc.arg(limit_count);
