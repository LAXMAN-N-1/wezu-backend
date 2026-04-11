package admin

import (
	"context"
	"database/sql"
	"fmt"
	"net/http"
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
	deps container.Dependencies
}

type AuditRecord struct {
	ID           int64     `json:"id"`
	UserID       *int64    `json:"user_id,omitempty"`
	Action       string    `json:"action"`
	ResourceType string    `json:"resource_type"`
	TargetID     *int64    `json:"target_id,omitempty"`
	IPAddress    string    `json:"ip_address,omitempty"`
	Timestamp    time.Time `json:"timestamp"`
}

func NewHandler(deps container.Dependencies) Handler {
	return Handler{repo: Repository{deps: deps}, deps: deps}
}

func RegisterRoutes(r chi.Router, deps container.Dependencies) {
	h := NewHandler(deps)
	r.Route("/admin", func(ar chi.Router) {
		ar.Use(middleware.RequireAuth(deps.JWT))
		ar.With(middleware.RequirePermission("admin:view:all")).Get("/health", h.health)
		ar.With(middleware.RequirePermission("audit:view:all")).Get("/audit", h.audit)
	})
}

func (h Handler) health(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 1200*time.Millisecond)
	defer cancel()
	if err := h.deps.DB.Ping(ctx); err != nil {
		envelope.Fail(w, http.StatusServiceUnavailable, middleware.BuildMeta(r.Context()), "db_unavailable", "database ping failed")
		return
	}
	if err := h.deps.Redis.Ping(ctx).Err(); err != nil {
		envelope.Fail(w, http.StatusServiceUnavailable, middleware.BuildMeta(r.Context()), "cache_unavailable", "redis ping failed")
		return
	}
	envelope.OK(w, middleware.BuildMeta(r.Context()), map[string]any{
		"status":  "ok",
		"service": h.deps.Config.ServiceName,
		"time":    time.Now().UTC(),
	})
}

func (h Handler) audit(w http.ResponseWriter, r *http.Request) {
	limit := pagination.ParseLimit(r.URL.Query().Get("limit"), 50, 200)
	var cursor *pagination.Cursor
	if raw := r.URL.Query().Get("cursor"); raw != "" {
		c, err := pagination.Decode(raw)
		if err != nil {
			envelope.Fail(w, http.StatusBadRequest, middleware.BuildMeta(r.Context()), "bad_request", "invalid cursor")
			return
		}
		cursor = &c
	}

	items, next, err := h.repo.ListAudit(r.Context(), cursor, limit)
	if err != nil {
		envelope.Fail(w, http.StatusInternalServerError, middleware.BuildMeta(r.Context()), "internal_error", "failed to load audit logs")
		return
	}
	meta := middleware.BuildMeta(r.Context())
	meta.Cursor = next
	envelope.OK(w, meta, items)
}

func (r Repository) ListAudit(ctx context.Context, cursor *pagination.Cursor, limit int) ([]AuditRecord, *string, error) {
	query := `
SELECT id, user_id, action, resource_type, target_id, ip_address, timestamp
FROM audit_logs
WHERE 1=1`
	args := make([]any, 0, 4)
	argPos := 1
	if cursor != nil {
		query += fmt.Sprintf(" AND (timestamp, id) < ($%d, $%d)", argPos, argPos+1)
		args = append(args, cursor.CreatedAt, cursor.ID)
		argPos += 2
	}
	query += fmt.Sprintf(" ORDER BY timestamp DESC, id DESC LIMIT $%d", argPos)
	args = append(args, limit+1)

	rows, err := r.deps.DB.Query(ctx, query, args...)
	if err != nil {
		return nil, nil, err
	}
	defer rows.Close()

	items := make([]AuditRecord, 0, limit+1)
	for rows.Next() {
		var (
			it       AuditRecord
			userID   sql.NullInt64
			targetID sql.NullInt64
			ip       sql.NullString
		)
		if err := rows.Scan(&it.ID, &userID, &it.Action, &it.ResourceType, &targetID, &ip, &it.Timestamp); err != nil {
			return nil, nil, err
		}
		if userID.Valid {
			v := userID.Int64
			it.UserID = &v
		}
		if targetID.Valid {
			v := targetID.Int64
			it.TargetID = &v
		}
		it.IPAddress = ip.String
		items = append(items, it)
	}
	if rows.Err() != nil {
		return nil, nil, rows.Err()
	}

	var next *string
	if len(items) > limit {
		last := items[limit-1]
		cur, err := pagination.Encode(pagination.Cursor{CreatedAt: last.Timestamp, ID: last.ID})
		if err != nil {
			return nil, nil, err
		}
		next = &cur
		items = items[:limit]
	}
	return items, next, nil
}
