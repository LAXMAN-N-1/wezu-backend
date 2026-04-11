package middleware

import (
	"net/http"
	"time"

	"github.com/google/uuid"
	"wezu/v2/internal/platform/metrics"
)

type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (sr *statusRecorder) WriteHeader(statusCode int) {
	sr.status = statusCode
	sr.ResponseWriter.WriteHeader(statusCode)
}

func RequestMeta(collector *metrics.Collector) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			started := time.Now().UTC()
			traceID := r.Header.Get("X-Request-ID")
			if traceID == "" {
				traceID = uuid.NewString()
			}

			ctx := r.Context()
			ctx = SetTraceID(ctx, traceID)
			ctx = SetStartedAt(ctx, started)
			r = r.WithContext(ctx)

			w.Header().Set("X-Request-ID", traceID)
			sr := &statusRecorder{ResponseWriter: w, status: http.StatusOK}
			next.ServeHTTP(sr, r)

			if collector != nil {
				collector.Observe(r.Method, r.URL.Path, sr.status, time.Since(started))
			}
		})
	}
}
