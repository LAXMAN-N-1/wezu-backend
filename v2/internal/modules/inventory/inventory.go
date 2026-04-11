package inventory

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/jackc/pgx/v5"
	"wezu/v2/internal/platform/middleware"
	"wezu/v2/internal/shared/container"
	"wezu/v2/internal/shared/envelope"
)

type Repository struct {
	deps container.Dependencies
}

type Handler struct {
	repo Repository
	deps container.Dependencies
}

type WarehouseSummary struct {
	WarehouseID   int64  `json:"warehouse_id"`
	WarehouseName string `json:"warehouse_name"`
	TotalOnHand   int64  `json:"total_on_hand"`
	Available     int64  `json:"total_available"`
	Reserved      int64  `json:"total_reserved"`
}

type LowStockItem struct {
	StockID           int64  `json:"stock_id"`
	WarehouseID       int64  `json:"warehouse_id"`
	WarehouseName     string `json:"warehouse_name"`
	ProductID         int64  `json:"product_id"`
	QuantityAvailable int    `json:"quantity_available"`
	ReorderLevel      int    `json:"reorder_level"`
}

type adjustRequest struct {
	StockID int64 `json:"stock_id"`
	Delta   int   `json:"delta"`
}

type adjustResponse struct {
	StockID           int64 `json:"stock_id"`
	QuantityOnHand    int   `json:"quantity_on_hand"`
	QuantityAvailable int   `json:"quantity_available"`
}

func NewHandler(deps container.Dependencies) Handler {
	return Handler{repo: Repository{deps: deps}, deps: deps}
}

func RegisterRoutes(r chi.Router, deps container.Dependencies) {
	h := NewHandler(deps)
	r.Route("/inventory", func(ir chi.Router) {
		ir.Use(middleware.RequireAuth(deps.JWT))
		ir.With(middleware.RequirePermission("inventory:view:all")).Get("/summary", h.summary)
		ir.With(middleware.RequirePermission("inventory:view:all")).Get("/low-stock", h.lowStock)
		ir.With(middleware.RequirePermission("inventory:update:all")).Post("/adjust", h.adjust)
	})
}

func (h Handler) summary(w http.ResponseWriter, r *http.Request) {
	cacheKey := "v2:inventory:summary"
	payload, cached, stale, err := h.deps.SWR.GetOrCompute(r.Context(), cacheKey, h.deps.Config.CacheTTL, h.deps.Config.CacheStale, func(ctx context.Context) ([]byte, error) {
		items, err := h.repo.Summary(ctx)
		if err != nil {
			return nil, err
		}
		return json.Marshal(items)
	})
	if err != nil {
		envelope.Fail(w, http.StatusInternalServerError, middleware.BuildMeta(r.Context()), "internal_error", "failed to fetch inventory summary")
		return
	}
	var items []WarehouseSummary
	if err := json.Unmarshal(payload, &items); err != nil {
		envelope.Fail(w, http.StatusInternalServerError, middleware.BuildMeta(r.Context()), "internal_error", "failed to decode summary")
		return
	}
	meta := middleware.BuildMeta(r.Context())
	meta.Cached = cached
	meta.Stale = stale
	envelope.OK(w, meta, items)
}

func (h Handler) lowStock(w http.ResponseWriter, r *http.Request) {
	cacheKey := "v2:inventory:low_stock"
	payload, cached, stale, err := h.deps.SWR.GetOrCompute(r.Context(), cacheKey, h.deps.Config.CacheTTL, h.deps.Config.CacheStale, func(ctx context.Context) ([]byte, error) {
		items, err := h.repo.LowStock(ctx)
		if err != nil {
			return nil, err
		}
		return json.Marshal(items)
	})
	if err != nil {
		envelope.Fail(w, http.StatusInternalServerError, middleware.BuildMeta(r.Context()), "internal_error", "failed to fetch low stock")
		return
	}
	var items []LowStockItem
	if err := json.Unmarshal(payload, &items); err != nil {
		envelope.Fail(w, http.StatusInternalServerError, middleware.BuildMeta(r.Context()), "internal_error", "failed to decode low stock")
		return
	}
	meta := middleware.BuildMeta(r.Context())
	meta.Cached = cached
	meta.Stale = stale
	envelope.OK(w, meta, items)
}

func (h Handler) adjust(w http.ResponseWriter, r *http.Request) {
	var req adjustRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		envelope.Fail(w, http.StatusBadRequest, middleware.BuildMeta(r.Context()), "bad_request", "invalid json")
		return
	}
	if req.StockID <= 0 || req.Delta == 0 {
		envelope.Fail(w, http.StatusBadRequest, middleware.BuildMeta(r.Context()), "bad_request", "stock_id and non-zero delta required")
		return
	}

	res, err := h.repo.Adjust(r.Context(), req)
	if err != nil {
		envelope.Fail(w, http.StatusInternalServerError, middleware.BuildMeta(r.Context()), "internal_error", "failed to adjust inventory")
		return
	}

	_ = h.deps.SWR.Invalidate(r.Context(), "v2:inventory:summary", "v2:inventory:low_stock")
	_ = h.deps.Invalidator.Publish(r.Context(), "v2:inventory:summary", "v2:inventory:low_stock")
	envelope.OK(w, middleware.BuildMeta(r.Context()), res)
}

func (r Repository) Summary(ctx context.Context) ([]WarehouseSummary, error) {
	const q = `
SELECT w.id, w.name,
       COALESCE(SUM(s.quantity_on_hand), 0) AS total_on_hand,
       COALESCE(SUM(s.quantity_available), 0) AS total_available,
       COALESCE(SUM(s.quantity_reserved), 0) AS total_reserved
FROM warehouses w
LEFT JOIN stocks s ON s.warehouse_id = w.id
WHERE w.is_active = true
GROUP BY w.id, w.name
ORDER BY w.name`
	rows, err := r.deps.DB.Query(ctx, q)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	items := make([]WarehouseSummary, 0, 64)
	for rows.Next() {
		var it WarehouseSummary
		if err := rows.Scan(&it.WarehouseID, &it.WarehouseName, &it.TotalOnHand, &it.Available, &it.Reserved); err != nil {
			return nil, err
		}
		items = append(items, it)
	}
	if rows.Err() != nil {
		return nil, rows.Err()
	}
	return items, nil
}

func (r Repository) LowStock(ctx context.Context) ([]LowStockItem, error) {
	const q = `
SELECT s.id, s.warehouse_id, w.name, s.product_id, s.quantity_available, s.reorder_level
FROM stocks s
JOIN warehouses w ON w.id = s.warehouse_id
WHERE s.quantity_available <= s.reorder_level
ORDER BY (s.reorder_level - s.quantity_available) DESC, s.id DESC
LIMIT 500`

	rows, err := r.deps.DB.Query(ctx, q)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	items := make([]LowStockItem, 0, 128)
	for rows.Next() {
		var it LowStockItem
		if err := rows.Scan(&it.StockID, &it.WarehouseID, &it.WarehouseName, &it.ProductID, &it.QuantityAvailable, &it.ReorderLevel); err != nil {
			return nil, err
		}
		items = append(items, it)
	}
	if rows.Err() != nil {
		return nil, rows.Err()
	}
	return items, nil
}

func (r Repository) Adjust(ctx context.Context, req adjustRequest) (adjustResponse, error) {
	tx, err := r.deps.DB.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return adjustResponse{}, err
	}
	defer tx.Rollback(ctx)

	ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()

	const q = `
UPDATE stocks
SET quantity_on_hand = GREATEST(quantity_on_hand + $2, 0),
    quantity_available = GREATEST(quantity_available + $2, 0),
    updated_at = NOW()
WHERE id = $1
RETURNING id, quantity_on_hand, quantity_available`

	var res adjustResponse
	if err := tx.QueryRow(ctx, q, req.StockID, req.Delta).Scan(&res.StockID, &res.QuantityOnHand, &res.QuantityAvailable); err != nil {
		return adjustResponse{}, err
	}

	claims, ok := middleware.GetClaims(ctx)
	if ok {
		_, _ = tx.Exec(ctx, `
INSERT INTO audit_logs (user_id, action, resource_type, target_id, details, timestamp)
VALUES ($1, 'DATA_MODIFICATION', 'STOCK', $2, $3, NOW())
`, claims.UserID, req.StockID, fmt.Sprintf("inventory delta applied: %d", req.Delta))
	}

	if err := tx.Commit(ctx); err != nil {
		return adjustResponse{}, err
	}
	return res, nil
}
