package tickets

import (
	"context"
	"database/sql"
	"encoding/json"
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

type Ticket struct {
	ID         int64     `json:"id"`
	UserID     int64     `json:"user_id"`
	UserName   string    `json:"user_name,omitempty"`
	AssignedTo *int64    `json:"assigned_to,omitempty"`
	Subject    string    `json:"subject"`
	Status     string    `json:"status"`
	Priority   string    `json:"priority"`
	Category   string    `json:"category"`
	CreatedAt  time.Time `json:"created_at"`
	UpdatedAt  time.Time `json:"updated_at"`
}

type createRequest struct {
	Subject     string `json:"subject"`
	Description string `json:"description"`
	Priority    string `json:"priority"`
	Category    string `json:"category"`
}

func NewHandler(deps container.Dependencies) Handler {
	return Handler{repo: Repository{deps: deps}}
}

func RegisterRoutes(r chi.Router, deps container.Dependencies) {
	h := NewHandler(deps)
	r.Route("/tickets", func(tr chi.Router) {
		tr.Use(middleware.RequireAuth(deps.JWT))
		tr.With(middleware.RequirePermission("support:view:all")).Get("/", h.list)
		tr.With(middleware.RequirePermission("support:create:all")).Post("/", h.create)
	})
}

func (h Handler) list(w http.ResponseWriter, r *http.Request) {
	limit := pagination.ParseLimit(r.URL.Query().Get("limit"), 50, 200)
	status := strings.TrimSpace(r.URL.Query().Get("status"))
	priority := strings.TrimSpace(r.URL.Query().Get("priority"))
	var cursor *pagination.Cursor
	if raw := strings.TrimSpace(r.URL.Query().Get("cursor")); raw != "" {
		c, err := pagination.Decode(raw)
		if err != nil {
			envelope.Fail(w, http.StatusBadRequest, middleware.BuildMeta(r.Context()), "bad_request", "invalid cursor")
			return
		}
		cursor = &c
	}

	items, next, err := h.repo.List(r.Context(), status, priority, cursor, limit)
	if err != nil {
		envelope.Fail(w, http.StatusInternalServerError, middleware.BuildMeta(r.Context()), "internal_error", "failed to list tickets")
		return
	}
	meta := middleware.BuildMeta(r.Context())
	meta.Cursor = next
	envelope.OK(w, meta, items)
}

func (h Handler) create(w http.ResponseWriter, r *http.Request) {
	claims, ok := middleware.GetClaims(r.Context())
	if !ok {
		envelope.Fail(w, http.StatusUnauthorized, middleware.BuildMeta(r.Context()), "unauthorized", "missing claims")
		return
	}
	var req createRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		envelope.Fail(w, http.StatusBadRequest, middleware.BuildMeta(r.Context()), "bad_request", "invalid json")
		return
	}
	if strings.TrimSpace(req.Subject) == "" || strings.TrimSpace(req.Description) == "" {
		envelope.Fail(w, http.StatusBadRequest, middleware.BuildMeta(r.Context()), "bad_request", "subject and description required")
		return
	}
	if req.Priority == "" {
		req.Priority = "medium"
	}
	if req.Category == "" {
		req.Category = "general"
	}

	ticket, err := h.repo.Create(r.Context(), claims.UserID, req)
	if err != nil {
		envelope.Fail(w, http.StatusInternalServerError, middleware.BuildMeta(r.Context()), "internal_error", "failed to create ticket")
		return
	}
	envelope.Created(w, middleware.BuildMeta(r.Context()), ticket)
}

func (r Repository) List(ctx context.Context, status, priority string, cursor *pagination.Cursor, limit int) ([]Ticket, *string, error) {
	query := `
SELECT t.id, t.user_id, u.full_name, t.assigned_to, t.subject, t.status, t.priority, t.category, t.created_at, t.updated_at
FROM support_tickets t
JOIN users u ON u.id = t.user_id
WHERE 1=1`
	args := make([]any, 0, 6)
	argPos := 1
	if status != "" {
		query += fmt.Sprintf(" AND t.status = $%d", argPos)
		args = append(args, status)
		argPos++
	}
	if priority != "" {
		query += fmt.Sprintf(" AND t.priority = $%d", argPos)
		args = append(args, priority)
		argPos++
	}
	if cursor != nil {
		query += fmt.Sprintf(" AND (t.created_at, t.id) < ($%d, $%d)", argPos, argPos+1)
		args = append(args, cursor.CreatedAt, cursor.ID)
		argPos += 2
	}
	query += fmt.Sprintf(" ORDER BY t.created_at DESC, t.id DESC LIMIT $%d", argPos)
	args = append(args, limit+1)

	rows, err := r.deps.DB.Query(ctx, query, args...)
	if err != nil {
		return nil, nil, err
	}
	defer rows.Close()

	items := make([]Ticket, 0, limit+1)
	for rows.Next() {
		var (
			t        Ticket
			assigned sql.NullInt64
			userName sql.NullString
		)
		if err := rows.Scan(&t.ID, &t.UserID, &userName, &assigned, &t.Subject, &t.Status, &t.Priority, &t.Category, &t.CreatedAt, &t.UpdatedAt); err != nil {
			return nil, nil, err
		}
		t.UserName = userName.String
		if assigned.Valid {
			v := assigned.Int64
			t.AssignedTo = &v
		}
		items = append(items, t)
	}
	if rows.Err() != nil {
		return nil, nil, rows.Err()
	}

	var next *string
	if len(items) > limit {
		last := items[limit-1]
		cur, err := pagination.Encode(pagination.Cursor{CreatedAt: last.CreatedAt, ID: last.ID})
		if err != nil {
			return nil, nil, err
		}
		next = &cur
		items = items[:limit]
	}
	return items, next, nil
}

func (r Repository) Create(ctx context.Context, userID int64, req createRequest) (Ticket, error) {
	const q = `
INSERT INTO support_tickets (user_id, subject, description, status, priority, category, created_at, updated_at)
VALUES ($1, $2, $3, 'open', $4, $5, NOW(), NOW())
RETURNING id, user_id, subject, status, priority, category, created_at, updated_at`
	var t Ticket
	if err := r.deps.DB.QueryRow(ctx, q, userID, req.Subject, req.Description, req.Priority, req.Category).
		Scan(&t.ID, &t.UserID, &t.Subject, &t.Status, &t.Priority, &t.Category, &t.CreatedAt, &t.UpdatedAt); err != nil {
		return Ticket{}, err
	}
	return t, nil
}
