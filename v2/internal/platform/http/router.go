package httpx

import (
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	chimid "github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"
	"github.com/go-chi/httprate"
	"wezu/v2/internal/modules/admin"
	"wezu/v2/internal/modules/analytics"
	"wezu/v2/internal/modules/auth"
	"wezu/v2/internal/modules/inventory"
	"wezu/v2/internal/modules/stations"
	"wezu/v2/internal/modules/swaps"
	"wezu/v2/internal/modules/tickets"
	"wezu/v2/internal/modules/users"
	"wezu/v2/internal/platform/metrics"
	"wezu/v2/internal/platform/middleware"
	"wezu/v2/internal/shared/container"
	"wezu/v2/internal/shared/envelope"
)

func NewRouter(deps container.Dependencies) http.Handler {
	r := chi.NewRouter()
	r.Use(chimid.RealIP)
	r.Use(middleware.RequestMeta(deps.Metrics))
	r.Use(chimid.Recoverer)
	r.Use(chimid.Timeout(12 * time.Second))
	r.Use(httprate.Limit(
		deps.Config.RateLimitPerMinute,
		time.Minute,
		httprate.WithKeyFuncs(httprate.KeyByIP, httprate.KeyByEndpoint),
	))
	r.Use(cors.Handler(cors.Options{
		AllowedOrigins: deps.Config.CORSOrigins,
		AllowedMethods: []string{"GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"},
		AllowedHeaders: []string{"Accept", "Authorization", "Content-Type", "X-Request-ID"},
		ExposedHeaders: []string{"X-Request-ID"},
		MaxAge:         300,
	}))

	r.Get("/live", func(w http.ResponseWriter, r *http.Request) {
		envelope.OK(w, middleware.BuildMeta(r.Context()), map[string]any{"status": "live"})
	})

	r.Get("/ready", func(w http.ResponseWriter, r *http.Request) {
		if err := deps.DB.Ping(r.Context()); err != nil {
			envelope.Fail(w, http.StatusServiceUnavailable, middleware.BuildMeta(r.Context()), "db_unavailable", "database unavailable")
			return
		}
		if err := deps.Redis.Ping(r.Context()).Err(); err != nil {
			envelope.Fail(w, http.StatusServiceUnavailable, middleware.BuildMeta(r.Context()), "cache_unavailable", "redis unavailable")
			return
		}
		envelope.OK(w, middleware.BuildMeta(r.Context()), map[string]any{"status": "ready"})
	})

	r.Handle("/metrics", metrics.Handler())

	r.Route("/api/v2", func(v2 chi.Router) {
		auth.RegisterRoutes(v2, deps)
		users.RegisterRoutes(v2, deps)
		stations.RegisterRoutes(v2, deps)
		swaps.RegisterRoutes(v2, deps)
		inventory.RegisterRoutes(v2, deps)
		tickets.RegisterRoutes(v2, deps)
		analytics.RegisterRoutes(v2, deps)
		admin.RegisterRoutes(v2, deps)
	})

	return r
}
