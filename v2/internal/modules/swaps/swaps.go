package swaps

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"sync"
	"time"

	"github.com/go-chi/chi/v5"
	"wezu/v2/internal/platform/middleware"
	"wezu/v2/internal/platform/queue"
	"wezu/v2/internal/shared/container"
	"wezu/v2/internal/shared/envelope"
	"wezu/v2/internal/shared/pagination"
)

var registerQueueOnce sync.Once

type Repository struct {
	deps container.Dependencies
}

type Handler struct {
	repo Repository
	deps container.Dependencies
}

type Swap struct {
	ID            int64     `json:"id"`
	UserID        int64     `json:"user_id"`
	StationID     int64     `json:"station_id"`
	OldBatteryID  *int64    `json:"old_battery_id,omitempty"`
	NewBatteryID  *int64    `json:"new_battery_id,omitempty"`
	SwapAmount    float64   `json:"swap_amount"`
	Currency      string    `json:"currency"`
	Status        string    `json:"status"`
	PaymentStatus string    `json:"payment_status"`
	CreatedAt     time.Time `json:"created_at"`
}

type createRequest struct {
	StationID     int64   `json:"station_id"`
	OldBatteryID  *int64  `json:"old_battery_id,omitempty"`
	NewBatteryID  *int64  `json:"new_battery_id,omitempty"`
	OldBatterySOC float64 `json:"old_battery_soc"`
	NewBatterySOC float64 `json:"new_battery_soc"`
	SwapAmount    float64 `json:"swap_amount"`
	Currency      string  `json:"currency"`
}

type createResponse struct {
	Swap   Swap   `json:"swap"`
	TaskID string `json:"task_id"`
}

type completionJob struct {
	SwapID int64 `json:"swap_id"`
}

func NewHandler(deps container.Dependencies) Handler {
	h := Handler{repo: Repository{deps: deps}, deps: deps}
	registerQueueOnce.Do(func() {
		deps.Queue.Register("swap.complete", h.completeSwap)
	})
	return h
}

func RegisterRoutes(r chi.Router, deps container.Dependencies) {
	h := NewHandler(deps)
	r.Route("/swaps", func(sr chi.Router) {
		sr.Use(middleware.RequireAuth(deps.JWT))
		sr.With(middleware.RequirePermission("swap:create:all")).Post("/", h.create)
		sr.With(middleware.RequirePermission("swap:view:all")).Get("/", h.list)
		sr.With(middleware.RequirePermission("swap:view:all")).Get("/tasks/{task_id}", h.taskStatus)
	})
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
	if req.StationID <= 0 || req.SwapAmount < 0 {
		envelope.Fail(w, http.StatusBadRequest, middleware.BuildMeta(r.Context()), "bad_request", "invalid swap payload")
		return
	}
	if req.Currency == "" {
		req.Currency = "INR"
	}

	swap, err := h.repo.Create(r.Context(), claims.UserID, req)
	if err != nil {
		envelope.Fail(w, http.StatusInternalServerError, middleware.BuildMeta(r.Context()), "internal_error", "failed to create swap")
		return
	}

	taskID, err := h.deps.Queue.Enqueue("swap.complete", completionJob{SwapID: swap.ID})
	if err != nil {
		envelope.Fail(w, http.StatusInternalServerError, middleware.BuildMeta(r.Context()), "internal_error", "failed to queue swap completion")
		return
	}
	envelope.Created(w, middleware.BuildMeta(r.Context()), createResponse{Swap: swap, TaskID: taskID})
}

func (h Handler) list(w http.ResponseWriter, r *http.Request) {
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
	userID, _ := parseInt64Query(r, "user_id")
	stationID, _ := parseInt64Query(r, "station_id")

	items, next, err := h.repo.List(r.Context(), userID, stationID, cursor, limit)
	if err != nil {
		envelope.Fail(w, http.StatusInternalServerError, middleware.BuildMeta(r.Context()), "internal_error", "failed to list swaps")
		return
	}
	meta := middleware.BuildMeta(r.Context())
	meta.Cursor = next
	envelope.OK(w, meta, items)
}

func (h Handler) taskStatus(w http.ResponseWriter, r *http.Request) {
	taskID := chi.URLParam(r, "task_id")
	status, ok := h.deps.Queue.Status(taskID)
	if !ok {
		envelope.Fail(w, http.StatusNotFound, middleware.BuildMeta(r.Context()), "not_found", "task not found")
		return
	}
	envelope.OK(w, middleware.BuildMeta(r.Context()), status)
}

func (r Repository) Create(ctx context.Context, userID int64, req createRequest) (Swap, error) {
	const q = `
INSERT INTO swap_sessions (
    user_id, station_id, old_battery_id, new_battery_id,
    old_battery_soc, new_battery_soc, swap_amount, currency,
    status, payment_status, created_at
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'initiated', 'pending', NOW())
RETURNING id, user_id, station_id, old_battery_id, new_battery_id, swap_amount, currency, status, payment_status, created_at`

	var (
		s     Swap
		old   sql.NullInt64
		newID sql.NullInt64
	)
	if err := r.deps.DB.QueryRow(ctx, q, userID, req.StationID, req.OldBatteryID, req.NewBatteryID, req.OldBatterySOC, req.NewBatterySOC, req.SwapAmount, req.Currency).
		Scan(&s.ID, &s.UserID, &s.StationID, &old, &newID, &s.SwapAmount, &s.Currency, &s.Status, &s.PaymentStatus, &s.CreatedAt); err != nil {
		return Swap{}, err
	}
	if old.Valid {
		v := old.Int64
		s.OldBatteryID = &v
	}
	if newID.Valid {
		v := newID.Int64
		s.NewBatteryID = &v
	}
	return s, nil
}

func (r Repository) List(ctx context.Context, userID, stationID int64, cursor *pagination.Cursor, limit int) ([]Swap, *string, error) {
	query := `
SELECT id, user_id, station_id, old_battery_id, new_battery_id, swap_amount, currency, status, payment_status, created_at
FROM swap_sessions
WHERE 1=1`
	args := make([]any, 0, 6)
	argPos := 1

	if userID > 0 {
		query += fmt.Sprintf(" AND user_id = $%d", argPos)
		args = append(args, userID)
		argPos++
	}
	if stationID > 0 {
		query += fmt.Sprintf(" AND station_id = $%d", argPos)
		args = append(args, stationID)
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

	items := make([]Swap, 0, limit+1)
	for rows.Next() {
		var (
			s     Swap
			old   sql.NullInt64
			newID sql.NullInt64
		)
		if err := rows.Scan(&s.ID, &s.UserID, &s.StationID, &old, &newID, &s.SwapAmount, &s.Currency, &s.Status, &s.PaymentStatus, &s.CreatedAt); err != nil {
			return nil, nil, err
		}
		if old.Valid {
			v := old.Int64
			s.OldBatteryID = &v
		}
		if newID.Valid {
			v := newID.Int64
			s.NewBatteryID = &v
		}
		items = append(items, s)
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

func (h Handler) completeSwap(ctx context.Context, task queue.Task) error {
	var job completionJob
	if err := json.Unmarshal(task.Payload, &job); err != nil {
		return err
	}
	_, err := h.deps.DB.Exec(ctx, `
UPDATE swap_sessions
SET status = 'completed', payment_status = 'paid', completed_at = NOW()
WHERE id = $1 AND status IN ('initiated', 'processing')
`, job.SwapID)
	if err != nil {
		return err
	}
	_ = h.deps.Invalidator.Publish(ctx, "v2:analytics:overview")
	return nil
}

func parseInt64Query(r *http.Request, key string) (int64, error) {
	raw := r.URL.Query().Get(key)
	if raw == "" {
		return 0, nil
	}
	v, err := strconv.ParseInt(raw, 10, 64)
	if err != nil {
		return 0, err
	}
	return v, nil
}
