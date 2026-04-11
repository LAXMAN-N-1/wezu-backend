package app

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net/http"
	"time"

	"wezu/v2/internal/config"
	"wezu/v2/internal/platform/cache"
	"wezu/v2/internal/platform/db"
	"wezu/v2/internal/platform/events"
	httpx "wezu/v2/internal/platform/http"
	"wezu/v2/internal/platform/metrics"
	"wezu/v2/internal/platform/observability"
	"wezu/v2/internal/platform/queue"
	"wezu/v2/internal/platform/security"
	"wezu/v2/internal/shared/container"
)

type App struct {
	cfg            config.Config
	server         *http.Server
	dbPool         interface{ Close() }
	redis          interface{ Close() error }
	tracerShutdown func(context.Context) error
}

func New(ctx context.Context, cfg config.Config) (*App, error) {
	tracerShutdown, err := observability.Init(ctx, cfg.OTelEnabled, cfg.ServiceName)
	if err != nil {
		return nil, err
	}

	dbPool, err := db.NewPool(ctx, cfg)
	if err != nil {
		return nil, err
	}
	redisClient, err := cache.NewRedis(cfg.RedisURL)
	if err != nil {
		dbPool.Close()
		return nil, err
	}

	collector := metrics.New()
	swr := cache.NewSWR(redisClient)
	jwtManager := security.NewJWTManager(cfg, redisClient)
	q := queue.New(2048)
	invalidator := events.NewInvalidator(redisClient, "cache:invalidate")

	deps := container.Dependencies{
		Config:      cfg,
		DB:          dbPool,
		Redis:       redisClient,
		SWR:         swr,
		JWT:         jwtManager,
		Metrics:     collector,
		Queue:       q,
		Invalidator: invalidator,
	}

	q.Start(ctx, 4)
	go func() {
		err := invalidator.Subscribe(ctx, func(keys []string) error {
			if len(keys) == 0 {
				return nil
			}
			return swr.Invalidate(context.Background(), keys...)
		})
		if err != nil && !errors.Is(err, context.Canceled) {
			log.Printf("cache invalidation subscriber stopped: %v", err)
		}
	}()

	router := httpx.NewRouter(deps)
	server := &http.Server{
		Addr:              cfg.HTTPAddr,
		Handler:           router,
		ReadTimeout:       cfg.ReadTimeout,
		WriteTimeout:      cfg.WriteTimeout,
		ReadHeaderTimeout: 5 * time.Second,
	}

	return &App{cfg: cfg, server: server, dbPool: dbPool, redis: redisClient, tracerShutdown: tracerShutdown}, nil
}

func (a *App) Run(ctx context.Context) error {
	errCh := make(chan error, 1)
	go func() {
		log.Printf("starting %s on %s", a.cfg.ServiceName, a.cfg.HTTPAddr)
		err := a.server.ListenAndServe()
		if err != nil && !errors.Is(err, http.ErrServerClosed) {
			errCh <- err
			return
		}
		errCh <- nil
	}()

	select {
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), a.cfg.ShutdownTimeout)
		defer cancel()
		if err := a.server.Shutdown(shutdownCtx); err != nil {
			return fmt.Errorf("shutdown server: %w", err)
		}
	case err := <-errCh:
		if err != nil {
			return err
		}
	}

	if err := a.redis.Close(); err != nil {
		log.Printf("redis close: %v", err)
	}
	a.dbPool.Close()
	if a.tracerShutdown != nil {
		if err := a.tracerShutdown(context.Background()); err != nil {
			log.Printf("tracer shutdown: %v", err)
		}
	}
	return nil
}
