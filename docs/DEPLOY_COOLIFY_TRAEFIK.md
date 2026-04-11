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
