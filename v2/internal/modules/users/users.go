package users

import (
	"context"
	"database/sql"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"
	"wezu/v2/internal/platform/middleware"
	"wezu/v2/internal/shared/container"
	"wezu/v2/internal/shared/envelope"
	"wezu/v2/internal/shared/pagination"
)

type Repository struct {
	deps container.Dependencies
}

type Handler struct {
	repo Repository
}

type User struct {
	ID        int64     `json:"id"`
	FullName  string    `json:"full_name,omitempty"`
	Email     string    `json:"email,omitempty"`
	Phone     string    `json:"phone_number,omitempty"`
	UserType  string    `json:"user_type"`
	Status    string    `json:"status"`
	RoleID    *int64    `json:"role_id,omitempty"`
	CreatedAt time.Time `json:"created_at"`
}

func NewHandler(deps container.Dependencies) Handler {
	return Handler{repo: Repository{deps: deps}}
}

func RegisterRoutes(r chi.Router, deps container.Dependencies) {
	h := NewHandler(deps)
	r.With(
		middleware.RequireAuth(deps.JWT),
		middleware.RequirePermission("user:view:all"),
	).Get("/users", h.list)
}

func (h Handler) list(w http.ResponseWriter, r *http.Request) {
	limit := pagination.ParseLimit(r.URL.Query().Get("limit"), 50, 200)
	cursorRaw := strings.TrimSpace(r.URL.Query().Get("cursor"))
	search := strings.TrimSpace(r.URL.Query().Get("q"))

	var cursor *pagination.Cursor
	if cursorRaw != "" {
		c, err := pagination.Decode(cursorRaw)
		if err != nil {
			envelope.Fail(w, http.StatusBadRequest, middleware.BuildMeta(r.Context()), "bad_request", "invalid cursor")
			return
		}
		cursor = &c
	}

	items, next, err := h.repo.ListUsers(r.Context(), search, cursor, limit)
	if err != nil {
		envelope.Fail(w, http.StatusInternalServerError, middleware.BuildMeta(r.Context()), "internal_error", "failed to fetch users")
		return
	}

	meta := middleware.BuildMeta(r.Context())
	meta.Cursor = next
	envelope.OK(w, meta, items)
}

func (r Repository) ListUsers(ctx context.Context, search string, cursor *pagination.Cursor, limit int) ([]User, *string, error) {
	query := `
SELECT id, full_name, email, phone_number, user_type, status, role_id, created_at
FROM users
WHERE is_deleted = false`

	args := make([]any, 0, 5)
	argPos := 1
	if search != "" {
		query += fmt.Sprintf(" AND (full_name ILIKE $%d OR email ILIKE $%d OR phone_number ILIKE $%d)", argPos, argPos, argPos)
		args = append(args, "%"+search+"%")
		argPos++
	}
	if cursor != nil {
		query += fmt.Sprintf(" AND (created_at, id) < ($%d, $%d)", argPos, argPos+1)
		args = append(args, cursor.CreatedAt, cursor.ID)
		argPos += 2
	}
	query += fmt.Sprintf(" ORDER BY created_at DESC, id DESC LIMIT $%d", argPos)
	args = append(args, limit+1)

	rows, err := r.deps.DB.Query(ctx, query, args...)
	if err != nil {
		return nil, nil, err
	}
	defer rows.Close()

	users := make([]User, 0, limit+1)
	for rows.Next() {
		var (
			u               User
			fullName, email sql.NullString
			phone           sql.NullString
			roleID          sql.NullInt64
		)
		if err := rows.Scan(&u.ID, &fullName, &email, &phone, &u.UserType, &u.Status, &roleID, &u.CreatedAt); err != nil {
			return nil, nil, err
		}
		u.FullName = fullName.String
		u.Email = email.String
		u.Phone = phone.String
		if roleID.Valid {
			v := roleID.Int64
			u.RoleID = &v
		}
		users = append(users, u)
	}
	if rows.Err() != nil {
		return nil, nil, rows.Err()
	}

	var next *string
	if len(users) > limit {
		last := users[limit-1]
		c, err := pagination.Encode(pagination.Cursor{CreatedAt: last.CreatedAt, ID: last.ID})
		if err != nil {
			return nil, nil, err
		}
		next = &c
		users = users[:limit]
	}

	return users, next, nil
}
