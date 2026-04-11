package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	ServiceName string
	Environment string
	HTTPAddr    string

	ReadTimeout     time.Duration
	WriteTimeout    time.Duration
	ShutdownTimeout time.Duration

	DatabaseURL        string
	DBMaxConns         int32
	DBMinConns         int32
	DBConnMaxLifetime  time.Duration
	DBConnMaxIdle      time.Duration
	DBStatementTimeout time.Duration

	RedisURL string

	JWTIssuer        string
	JWTAudience      string
	JWTAccessSecret  string
	JWTRefreshSecret string
	AccessTokenTTL   time.Duration
	RefreshTokenTTL  time.Duration

	CacheTTL   time.Duration
	CacheStale time.Duration

	RateLimitPerMinute int
	RateLimitBurst     int

	CORSOrigins []string

	OTelEnabled bool
}

func Load() (Config, error) {
	cfg := Config{
		ServiceName: env("SERVICE_NAME", "wezu-api-v2"),
		Environment: env("ENVIRONMENT", "development"),
		HTTPAddr:    env("HTTP_ADDR", ":8081"),

		ReadTimeout:     envDuration("HTTP_READ_TIMEOUT", 8*time.Second),
		WriteTimeout:    envDuration("HTTP_WRITE_TIMEOUT", 10*time.Second),
		ShutdownTimeout: envDuration("HTTP_SHUTDOWN_TIMEOUT", 15*time.Second),

		DatabaseURL:        os.Getenv("DATABASE_URL"),
		DBMaxConns:         int32(envInt("DB_MAX_CONNS", 32)),
		DBMinConns:         int32(envInt("DB_MIN_CONNS", 4)),
		DBConnMaxLifetime:  envDuration("DB_CONN_MAX_LIFETIME", 45*time.Minute),
		DBConnMaxIdle:      envDuration("DB_CONN_MAX_IDLE", 15*time.Minute),
		DBStatementTimeout: envDuration("DB_STATEMENT_TIMEOUT", 1500*time.Millisecond),

		RedisURL: env("REDIS_URL", "redis://127.0.0.1:6379/0"),

		JWTIssuer:        env("JWT_ISSUER", "wezu-v2"),
		JWTAudience:      env("JWT_AUDIENCE", "wezu-clients"),
		JWTAccessSecret:  env("JWT_ACCESS_SECRET", "change-me-access-secret"),
		JWTRefreshSecret: env("JWT_REFRESH_SECRET", "change-me-refresh-secret"),
		AccessTokenTTL:   envDuration("ACCESS_TOKEN_TTL", 15*time.Minute),
		RefreshTokenTTL:  envDuration("REFRESH_TOKEN_TTL", 720*time.Hour),

		CacheTTL:   envDuration("CACHE_TTL", 45*time.Second),
		CacheStale: envDuration("CACHE_STALE", 75*time.Second),

		RateLimitPerMinute: envInt("RATE_LIMIT_PER_MINUTE", 600),
		RateLimitBurst:     envInt("RATE_LIMIT_BURST", 200),

		CORSOrigins: splitCSV(env("CORS_ORIGINS", "*")),
		OTelEnabled: envBool("OTEL_ENABLED", true),
	}

	if cfg.DatabaseURL == "" {
		return Config{}, fmt.Errorf("DATABASE_URL is required")
	}

	return cfg, nil
}

func env(key, fallback string) string {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return fallback
	}
	return v
}

func envInt(key string, fallback int) int {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return fallback
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		return fallback
	}
	return n
}

func envBool(key string, fallback bool) bool {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return fallback
	}
	b, err := strconv.ParseBool(v)
	if err != nil {
		return fallback
	}
	return b
}

func envDuration(key string, fallback time.Duration) time.Duration {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return fallback
	}
	d, err := time.ParseDuration(v)
	if err != nil {
		return fallback
	}
	return d
}

func splitCSV(raw string) []string {
	parts := strings.Split(raw, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p != "" {
			out = append(out, p)
		}
	}
	if len(out) == 0 {
		return []string{"*"}
	}
	return out
}
