package stations

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
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
	deps container.Dependencies
}

type Station struct {
	ID                 int64     `json:"id"`
	Name               string    `json:"name"`
	City               string    `json:"city,omitempty"`
	Address            string    `json:"address"`
	Latitude           float64   `json:"latitude"`
	Longitude          float64   `json:"longitude"`
	Status             string    `json:"status"`
	AvailableBatteries int       `json:"available_batteries"`
	AvailableSlots     int       `json:"available_slots"`
	UpdatedAt          time.Time `json:"updated_at"`
	DistanceKM         *float64  `json:"distance_km,omitempty"`
}

type listParams struct {
	Limit    int
	Cursor   *pagination.Cursor
	City     string
	Status   string
	Lat      *float64
	Lng      *float64
	RadiusKM *float64
}

func NewHandler(deps container.Dependencies) Handler {
	return Handler{repo: Repository{deps: deps}, deps: deps}
}

func RegisterRoutes(r chi.Router, deps container.Dependencies) {
	h := NewHandler(deps)
	r.With(middleware.RequireAuth(deps.JWT)).Get("/stations", h.list)
}

func (h Handler) list(w http.ResponseWriter, r *http.Request) {
	params, err := parseParams(r)
	if err != nil {
		envelope.Fail(w, http.StatusBadRequest, middleware.BuildMeta(r.Context()), "bad_request", err.Error())
		return
	}

	cacheKey := fmt.Sprintf("v2:stations:list:%d:%s:%s:%s:%s:%s:%s", params.Limit, cursorString(params.Cursor), params.City, params.Status, floatStr(params.Lat), floatStr(params.Lng), floatStr(params.RadiusKM))
	payload, cached, stale, err := h.deps.SWR.GetOrCompute(r.Context(), cacheKey, h.deps.Config.CacheTTL, h.deps.Config.CacheStale, func(ctx context.Context) ([]byte, error) {
		items, next, err := h.repo.List(ctx, params)
		if err != nil {
			return nil, err
		}
		return json.Marshal(map[string]any{"items": items, "next": next})
	})
	if err != nil {
		envelope.Fail(w, http.StatusInternalServerError, middleware.BuildMeta(r.Context()), "internal_error", "failed to fetch stations")
		return
	}

	var out struct {
		Items []Station `json:"items"`
		Next  *string   `json:"next"`
	}
	if err := json.Unmarshal(payload, &out); err != nil {
		envelope.Fail(w, http.StatusInternalServerError, middleware.BuildMeta(r.Context()), "internal_error", "failed to decode response")
		return
	}

	meta := middleware.BuildMeta(r.Context())
	meta.Cursor = out.Next
	meta.Cached = cached
	meta.Stale = stale
	envelope.OK(w, meta, out.Items)
}

func (r Repository) List(ctx context.Context, params listParams) ([]Station, *string, error) {
	args := make([]any, 0, 10)
	argPos := 1

	selectDistance := "NULL::double precision AS distance_km"
	if params.Lat != nil && params.Lng != nil {
		selectDistance = fmt.Sprintf(`(6371 * acos(cos(radians($%d)) * cos(radians(latitude)) * cos(radians(longitude) - radians($%d)) + sin(radians($%d)) * sin(radians(latitude)))) AS distance_km`, argPos, argPos+1, argPos)
		args = append(args, *params.Lat, *params.Lng)
		argPos += 2
	}

	query := fmt.Sprintf(`
SELECT id, name, city, address, latitude, longitude, status, available_batteries, available_slots, updated_at, %s
FROM stations
WHERE approval_status = 'approved'`, selectDistance)

	if params.City != "" {
		query += fmt.Sprintf(" AND city ILIKE $%d", argPos)
		args = append(args, "%"+params.City+"%")
		argPos++
	}
	if params.Status != "" {
		query += fmt.Sprintf(" AND status = $%d", argPos)
		args = append(args, params.Status)
		argPos++
	}
	if params.RadiusKM != nil && params.Lat != nil && params.Lng != nil {
		query += fmt.Sprintf(" AND (6371 * acos(cos(radians($1)) * cos(radians(latitude)) * cos(radians(longitude) - radians($2)) + sin(radians($1)) * sin(radians(latitude)))) <= $%d", argPos)
		args = append(args, *params.RadiusKM)
		argPos++
	}
	if params.Cursor != nil {
		query += fmt.Sprintf(" AND (updated_at, id) < ($%d, $%d)", argPos, argPos+1)
		args = append(args, params.Cursor.CreatedAt, params.Cursor.ID)
		argPos += 2
	}
	query += fmt.Sprintf(" ORDER BY updated_at DESC, id DESC LIMIT $%d", argPos)
	args = append(args, params.Limit+1)

	rows, err := r.deps.DB.Query(ctx, query, args...)
	if err != nil {
		return nil, nil, err
	}
	defer rows.Close()

	items := make([]Station, 0, params.Limit+1)
	for rows.Next() {
		var (
			st         Station
			city       sql.NullString
			distanceKM sql.NullFloat64
		)
		if err := rows.Scan(&st.ID, &st.Name, &city, &st.Address, &st.Latitude, &st.Longitude, &st.Status, &st.AvailableBatteries, &st.AvailableSlots, &st.UpdatedAt, &distanceKM); err != nil {
			return nil, nil, err
		}
		st.City = city.String
		if distanceKM.Valid {
			v := distanceKM.Float64
			st.DistanceKM = &v
		}
		items = append(items, st)
	}
	if rows.Err() != nil {
		return nil, nil, rows.Err()
	}

	var next *string
	if len(items) > params.Limit {
		last := items[params.Limit-1]
		cur, err := pagination.Encode(pagination.Cursor{CreatedAt: last.UpdatedAt, ID: last.ID})
		if err != nil {
			return nil, nil, err
		}
		next = &cur
		items = items[:params.Limit]
	}

	return items, next, nil
}

func parseParams(r *http.Request) (listParams, error) {
	params := listParams{Limit: pagination.ParseLimit(r.URL.Query().Get("limit"), 50, 200)}

	if cursorRaw := strings.TrimSpace(r.URL.Query().Get("cursor")); cursorRaw != "" {
		c, err := pagination.Decode(cursorRaw)
		if err != nil {
			return listParams{}, fmt.Errorf("invalid cursor")
		}
		params.Cursor = &c
	}
	params.City = strings.TrimSpace(r.URL.Query().Get("city"))
	params.Status = strings.TrimSpace(r.URL.Query().Get("status"))

	lat, latSet, err := parseFloatParam(r, "lat")
	if err != nil {
		return listParams{}, err
	}
	lng, lngSet, err := parseFloatParam(r, "lng")
	if err != nil {
		return listParams{}, err
	}
	radius, radiusSet, err := parseFloatParam(r, "radius_km")
	if err != nil {
		return listParams{}, err
	}

	if latSet != lngSet {
		return listParams{}, fmt.Errorf("lat and lng must both be provided")
	}
	if latSet {
		params.Lat = &lat
		params.Lng = &lng
	}
	if radiusSet {
		params.RadiusKM = &radius
	}

	return params, nil
}

func parseFloatParam(r *http.Request, key string) (float64, bool, error) {
	raw := strings.TrimSpace(r.URL.Query().Get(key))
	if raw == "" {
		return 0, false, nil
	}
	v, err := strconv.ParseFloat(raw, 64)
	if err != nil {
		return 0, false, fmt.Errorf("invalid %s", key)
	}
	return v, true, nil
}

func cursorString(c *pagination.Cursor) string {
	if c == nil {
		return ""
	}
	s, err := pagination.Encode(*c)
	if err != nil {
		return ""
	}
	return s
}

func floatStr(v *float64) string {
	if v == nil {
		return ""
	}
	return strconv.FormatFloat(*v, 'f', 6, 64)
}
