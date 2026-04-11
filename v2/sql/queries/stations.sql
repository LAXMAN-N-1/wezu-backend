-- name: ListStationsByCityStatus :many
SELECT id, name, city, address, latitude, longitude, status, available_batteries, available_slots, updated_at
FROM stations
WHERE approval_status = 'approved'
  AND (sqlc.arg(city)::text IS NULL OR city ILIKE '%' || sqlc.arg(city) || '%')
  AND (sqlc.arg(status)::text IS NULL OR status = sqlc.arg(status))
  AND (
    (sqlc.arg(cursor_updated_at)::timestamptz IS NULL AND sqlc.arg(cursor_id)::bigint IS NULL)
    OR (updated_at, id) < (sqlc.arg(cursor_updated_at)::timestamptz, sqlc.arg(cursor_id)::bigint)
  )
ORDER BY updated_at DESC, id DESC
LIMIT sqlc.arg(limit_count);
