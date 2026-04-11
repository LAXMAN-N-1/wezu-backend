-- name: ListUsers :many
SELECT id, full_name, email, phone_number, user_type, status, role_id, created_at
FROM users
WHERE is_deleted = false
  AND (
    sqlc.arg(search)::text IS NULL
    OR full_name ILIKE '%' || sqlc.arg(search) || '%'
    OR email ILIKE '%' || sqlc.arg(search) || '%'
    OR phone_number ILIKE '%' || sqlc.arg(search) || '%'
  )
  AND (
    (sqlc.arg(cursor_created_at)::timestamptz IS NULL AND sqlc.arg(cursor_id)::bigint IS NULL)
    OR (created_at, id) < (sqlc.arg(cursor_created_at)::timestamptz, sqlc.arg(cursor_id)::bigint)
  )
ORDER BY created_at DESC, id DESC
LIMIT sqlc.arg(limit_count);

-- name: GetAuthUserByIdentifier :one
SELECT id, email, phone_number, full_name, hashed_password, role_id, is_superuser, status
FROM users
WHERE is_deleted = false AND (email = sqlc.arg(identifier) OR phone_number = sqlc.arg(identifier))
LIMIT 1;
