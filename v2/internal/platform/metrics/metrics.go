package metrics

import (
	"net/http"
	"strconv"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

type Collector struct {
	RequestDuration *prometheus.HistogramVec
	RequestTotal    *prometheus.CounterVec
	CacheHits       *prometheus.CounterVec
}

func New() *Collector {
	c := &Collector{
		RequestDuration: prometheus.NewHistogramVec(prometheus.HistogramOpts{
			Namespace: "wezu",
			Subsystem: "api_v2",
			Name:      "request_duration_seconds",
			Help:      "HTTP request latency",
			Buckets:   []float64{0.005, 0.01, 0.02, 0.05, 0.075, 0.1, 0.2, 0.5, 1},
		}, []string{"method", "route", "status"}),
		RequestTotal: prometheus.NewCounterVec(prometheus.CounterOpts{
			Namespace: "wezu",
			Subsystem: "api_v2",
			Name:      "requests_total",
			Help:      "Total http requests",
		}, []string{"method", "route", "status"}),
		CacheHits: prometheus.NewCounterVec(prometheus.CounterOpts{
			Namespace: "wezu",
			Subsystem: "api_v2",
			Name:      "cache_events_total",
			Help:      "Cache hits/misses by layer",
		}, []string{"layer", "state"}),
	}
	prometheus.MustRegister(c.RequestDuration, c.RequestTotal, c.CacheHits)
	return c
}

func Handler() http.Handler {
	return promhttp.Handler()
}

func (c *Collector) Observe(method, route string, status int, elapsed time.Duration) {
	statusLabel := strconv.Itoa(status)
	c.RequestDuration.WithLabelValues(method, route, statusLabel).Observe(elapsed.Seconds())
	c.RequestTotal.WithLabelValues(method, route, statusLabel).Inc()
}
