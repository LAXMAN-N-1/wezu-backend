package container

import (
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/redis/go-redis/v9"
	"wezu/v2/internal/config"
	"wezu/v2/internal/platform/cache"
	"wezu/v2/internal/platform/events"
	"wezu/v2/internal/platform/metrics"
	"wezu/v2/internal/platform/queue"
	"wezu/v2/internal/platform/security"
)

type Dependencies struct {
	Config      config.Config
	DB          *pgxpool.Pool
	Redis       *redis.Client
	SWR         *cache.SWRCache
	JWT         *security.JWTManager
	Metrics     *metrics.Collector
	Queue       *queue.Queue
	Invalidator *events.Invalidator
}
