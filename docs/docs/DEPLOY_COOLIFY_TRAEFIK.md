# Coolify + Traefik Deployment Guide

This backend is configured for Coolify/Traefik ingress.

- No direct host port publishing from the app container.
- Backend listens on `0.0.0.0:8000` inside Docker.
- Traefik routes domain traffic to the service.
- Strict host validation is optional and should be enabled only after host values are verified.

## 1. Coolify Service Setup

1. Create a new service in Coolify from this repository.
2. Track branch `main`.
3. Use Docker Compose deployment (root `docker-compose.yml`).
4. Set the public domain on the API service (for example `api1.powerfrill.com`).
5. In Coolify, map the service internal port to `8000`.

## 2. Required Environment Variables

Set these in Coolify Environment Variables (application service):

```env
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<generate-64-hex-or-strong-random>

DATABASE_URL=<your-neon-postgresql-url>
REDIS_URL=redis://redis:6379/0

ALLOWED_HOSTS=api1.powerfrill.com
CORS_ORIGINS=https://app.powerfrill.com,https://admin.powerfrill.com

ENABLE_TRUSTED_HOST_MIDDLEWARE=true
TRUST_X_FORWARDED_HOST=true
FORWARDED_ALLOW_IPS=127.0.0.1/32,::1/128,172.16.0.0/12

API_PUBLIC_BASE_URL=https://api1.powerfrill.com
MEDIA_BASE_URL=https://api1.powerfrill.com/uploads

DB_INIT_ON_STARTUP=false
RUN_BACKGROUND_TASKS=false
SCHEDULER_ENABLED=false
MQTT_ENABLED=false
```

Notes:
- Keep `DATABASE_URL` pointed to Neon if Neon is your source of truth.
- If `ENABLE_TRUSTED_HOST_MIDDLEWARE=true`, `ALLOWED_HOSTS` must include every public API hostname routed by Traefik.
- `CORS_ORIGINS` must include exact frontend origins (scheme + host).
- `FORWARDED_ALLOW_IPS` should include the proxy network CIDRs that can reach this container.

## 3. Compose Behavior in This Repo

- API service uses `expose: ["8000"]` (not `ports`).
- Internal nginx service is removed.
- Production compose no longer publishes `80/443` from a bundled nginx.

## 4. Deploy

1. Trigger Deploy in Coolify.
2. Wait for build + startup to finish.
3. Confirm health in Coolify logs and endpoint checks.

## 5. Runtime Validation

Run from any machine with access to the domain:

```bash
curl -I https://api1.powerfrill.com/health
curl -fsS https://api1.powerfrill.com/ready
curl -fsS -H "Content-Type: application/json" \
  --data '{"credential":"admin@wezu.com","password":"admin123"}' \
  https://api1.powerfrill.com/api/v1/auth/login
```

Expected:
- `/health` responds `200` with JSON payload.
- `/ready` responds `200`.
- auth endpoint behavior remains unchanged for valid credentials.

## 6. Troubleshooting

If you see `Invalid host header`:
- Temporarily set `ENABLE_TRUSTED_HOST_MIDDLEWARE=false` to restore traffic while you validate host/proxy settings.
- Ensure domain is present in `ALLOWED_HOSTS`.
- Ensure Traefik forwards `X-Forwarded-Host`.
- Ensure proxy source subnet is in `FORWARDED_ALLOW_IPS`.

If client IPs are wrong in logs/rate limits:
- Verify `FORWARDED_ALLOW_IPS` includes the actual Traefik container subnet.

If deployment fails from env conflicts in Coolify:
- Remove stale variables from compose-level environment blocks first.
- Re-add them only in Coolify Environment Variables.

## 7. Hostinger VPS Performance Tuning

### Recommended VPS Specs (India region)
| Component | Minimum | Recommended |
|---|---|---|
| vCPUs | 2 | 4 |
| RAM | 4 GB | 8 GB |
| Storage | 40 GB SSD | 80 GB NVMe |
| Region | Mumbai (ap-south-1) | Mumbai or Singapore |

### Gunicorn Workers
Workers default to **2** (env: `GUNICORN_WORKERS`). Each Uvicorn worker uses ~150–250 MB.

| VPS RAM | Workers | Approx Memory |
|---|---|---|
| 4 GB | 2 | ~400–500 MB |
| 8 GB | 3–4 | ~600–1000 MB |

Set in Coolify environment:
```env
GUNICORN_WORKERS=2
GUNICORN_KEEPALIVE=65
GUNICORN_TIMEOUT=120
```

### Database Pool Sizing
Pool is **per worker process**. Total connections = `pool_size × workers + max_overflow × workers`.

| Setting | Value | Rationale |
|---|---|---|
| `DB_POOL_SIZE` | 3 | 3 conns × 2 workers = 6 base |
| `DB_MAX_OVERFLOW` | 3 | 6 + 6 overflow = 12 max total |
| `DB_POOL_TIMEOUT` | 20 | Fail fast on pool exhaustion |
| `DB_POOL_RECYCLE` | 900 | 15 min — avoids stale Neon connections |
| `DB_POOL_PRE_PING` | true | Detects closed connections before use |
| `DB_POOL_USE_LIFO` | true | Reuses hot connections first |
| `SQL_SLOW_QUERY_LOG_MS` | 500 | Logs queries > 500 ms to stdout |

> **Neon free tier**: 25 connection limit. Keep `pool_size × workers` ≤ 12.

### Redis
Redis should be in the same Docker network. Use `redis:7-alpine` with AOF persistence:
```yaml
redis:
  image: redis:7-alpine
  command: redis-server --appendonly yes --maxmemory 128mb --maxmemory-policy allkeys-lru
```

### Traefik Connection Tuning
Add these labels in Coolify for Traefik transport optimization:
```env
# In Coolify service labels / environment
traefik.http.services.api.loadbalancer.server.scheme=http
traefik.http.middlewares.api-compress.compress=true
```

The backend's `GUNICORN_KEEPALIVE=65` is set above Traefik's default idle timeout (60s) to prevent premature connection drops.

### Response Caching
The `SecureHeadersMiddleware` applies `Cache-Control` headers automatically:
- **Cacheable** (60s TTL): `/live`, `/api/v1/stations/map`, `/api/v1/faqs`, `/api/v1/catalog`, `/api/v1/locations`, `/api/v1/i18n`
- **No-store**: All other endpoints (mutations, user-specific data)

### GZip Compression
Enabled for responses ≥ 1000 bytes via `GZipMiddleware(minimum_size=1000)`. JSON API responses are typically 2–10× smaller after compression.

### Monitoring
- `Server-Timing` header on every response (`app;dur=X.XXms`) — visible in browser DevTools waterfall
- Slow query logging: set `SQL_SLOW_QUERY_LOG_MS=200` for aggressive monitoring during rollout
- Sentry integration: set `SENTRY_DSN` for error tracking + `SENTRY_TRACES_SAMPLE_RATE=0.1` for 10% performance tracing
