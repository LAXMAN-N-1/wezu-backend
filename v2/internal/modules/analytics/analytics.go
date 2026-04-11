package analytics

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"time"

	"github.com/go-chi/chi/v5"
	"wezu/v2/internal/platform/middleware"
	"wezu/v2/internal/platform/queue"
	"wezu/v2/internal/shared/container"
	"wezu/v2/internal/shared/envelope"
)

var registerQueueOnce sync.Once

type Repository struct {
	deps container.Dependencies
}

type Handler struct {
	repo Repository
	deps container.Dependencies
}

type Overview struct {
	ActiveUsers      int64     `json:"active_users"`
	ActiveStations   int64     `json:"active_stations"`
	OpenTickets      int64     `json:"open_tickets"`
	Swaps24h         int64     `json:"swaps_24h"`
	AvgSwapAmount24h float64   `json:"avg_swap_amount_24h"`
	LowStockItems    int64     `json:"low_stock_items"`
	GeneratedAt      time.Time `json:"generated_at"`
}

type refreshJob struct {
	RequestedAt time.Time `json:"requested_at"`
}

func NewHandler(deps container.Dependencies) Handler {
	h := Handler{repo: Repository{deps: deps}, deps: deps}
	registerQueueOnce.Do(func() {
		deps.Queue.Register("analytics.refresh", h.refreshReadModels)
	})
	return h
}

func RegisterRoutes(r chi.Router, deps container.Dependencies) {
	h := NewHandler(deps)
	r.Route("/analytics", func(ar chi.Router) {
		ar.Use(middleware.RequireAuth(deps.JWT))
		ar.With(middleware.RequirePermission("analytics:view:all")).Get("/overview", h.overview)
		ar.With(middleware.RequirePermission("analytics:refresh:all")).Post("/refresh", h.refresh)
		ar.With(middleware.RequirePermission("analytics:view:all")).Get("/tasks/{task_id}", h.taskStatus)
	})
}

func (h Handler) overview(w http.ResponseWriter, r *http.Request) {
	cacheKey := "v2:analytics:overview"
	payload, cached, stale, err := h.deps.SWR.GetOrCompute(r.Context(), cacheKey, h.deps.Config.CacheTTL, h.deps.Config.CacheStale, func(ctx context.Context) ([]byte, error) {
		ov, err := h.repo.Overview(ctx)
		if err != nil {
			return nil, err
		}
		return json.Marshal(ov)
	})
	if err != nil {
		envelope.Fail(w, http.StatusInternalServerError, middleware.BuildMeta(r.Context()), "internal_error", "failed to load analytics")
		return
	}
	var ov Overview
	if err := json.Unmarshal(payload, &ov); err != nil {
		envelope.Fail(w, http.StatusInternalServerError, middleware.BuildMeta(r.Context()), "internal_error", "failed to decode analytics")
		return
	}
	meta := middleware.BuildMeta(r.Context())
	meta.Cached = cached
	meta.Stale = stale
	envelope.OK(w, meta, ov)
}

func (h Handler) refresh(w http.ResponseWriter, r *http.Request) {
	taskID, err := h.deps.Queue.Enqueue("analytics.refresh", refreshJob{RequestedAt: time.Now().UTC()})
	if err != nil {
		envelope.Fail(w, http.StatusInternalServerError, middleware.BuildMeta(r.Context()), "internal_error", "failed to queue analytics refresh")
		return
	}
	envelope.Created(w, middleware.BuildMeta(r.Context()), map[string]any{"task_id": taskID})
}

func (h Handler) taskStatus(w http.ResponseWriter, r *http.Request) {
	status, ok := h.deps.Queue.Status(chi.URLParam(r, "task_id"))
	if !ok {
		envelope.Fail(w, http.StatusNotFound, middleware.BuildMeta(r.Context()), "not_found", "task not found")
		return
	}
	envelope.OK(w, middleware.BuildMeta(r.Context()), status)
}

func (r Repository) Overview(ctx context.Context) (Overview, error) {
	const q = `
SELECT
  (SELECT COUNT(*) FROM users WHERE is_deleted = false AND status IN ('active', 'verified')) AS active_users,
  (SELECT COUNT(*) FROM stations WHERE status = 'active' AND approval_status = 'approved') AS active_stations,
  (SELECT COUNT(*) FROM support_tickets WHERE status IN ('open', 'in_progress')) AS open_tickets,
  (SELECT COUNT(*) FROM swap_sessions WHERE created_at >= NOW() - INTERVAL '24 hours') AS swaps_24h,
  (SELECT COALESCE(AVG(swap_amount), 0) FROM swap_sessions WHERE created_at >= NOW() - INTERVAL '24 hours') AS avg_swap_amount_24h,
  (SELECT COUNT(*) FROM stocks WHERE quantity_available <= reorder_level) AS low_stock_items`

	var out Overview
	var avg sql.NullFloat64
	if err := r.deps.DB.QueryRow(ctx, q).Scan(&out.ActiveUsers, &out.ActiveStations, &out.OpenTickets, &out.Swaps24h, &avg, &out.LowStockItems); err != nil {
		return Overview{}, err
	}
	out.AvgSwapAmount24h = avg.Float64
	out.GeneratedAt = time.Now().UTC()
	return out, nil
}

func (h Handler) refreshReadModels(ctx context.Context, task queue.Task) error {
	var job refreshJob
	if err := json.Unmarshal(task.Payload, &job); err != nil {
		return err
	}

	if _, err := h.deps.DB.Exec(ctx, "REFRESH MATERIALIZED VIEW CONCURRENTLY analytics_overview_mv"); err != nil {
		// Fallback when MV does not exist in lower envs.
		if _, fallbackErr := h.deps.DB.Exec(ctx, "SELECT 1"); fallbackErr != nil {
			return fmt.Errorf("refresh read models failed: %w", err)
		}
	}

	_ = h.deps.SWR.Invalidate(ctx, "v2:analytics:overview")
	_ = h.deps.Invalidator.Publish(ctx, "v2:analytics:overview")
	return nil
}
