# Multi-Phase Docker Compose Deployment

This repository now uses a layered Compose deployment model with a multi-stage Docker build.

- `Dockerfile`: multi-stage (`runtime`, `dev-runtime`)
- `docker-compose.yml`: shared baseline (infra + API + optional workers)
- `docker-compose.dev.yml`: local development overrides
- `docker-compose.prod.yml`: production hardening overrides

## Deployment Phases

### Phase 1 — Infra Bring-up
Start stateful dependencies first.

```bash
docker compose -f docker-compose.yml up -d db redis
# Optional IoT broker:
docker compose -f docker-compose.yml --profile iot up -d mqtt
```

### Phase 2 — Schema Migration
Run one-shot migrations.

```bash
docker compose -f docker-compose.yml --profile migrations run --rm migrate
```

### Phase 3 — API Bring-up
Start API after infra and schema are ready.

```bash
docker compose -f docker-compose.yml up -d api
```

### Phase 4 — Worker Bring-up (Optional)
Start background scheduler and event workers.

```bash
docker compose -f docker-compose.yml --profile workers up -d scheduler event-worker
```

## Local Development

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

What changes in dev mode:
- Hot reload via Uvicorn (`--reload`)
- Source mounted as a bind volume
- Host ports published for API/DB/Redis
- Safer dev defaults (`ENABLE_API_DOCS=true`, `ALLOW_TEST_OTP_BYPASS=true`)

## Production Deployment

```bash
# External managed Postgres (recommended)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build api redis

# Optional local Postgres profile (if managed DB is unavailable)
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile local-db up -d db redis api
```

### Production worker scale-up

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile workers up -d scheduler event-worker
```

### Production migration step

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile migrations run --rm migrate
```

### Coolify Stability Defaults

Use these to prevent startup crash loops while bootstrapping:

```env
ENFORCE_PRODUCTION_SAFETY=false
STRICT_STARTUP_DEPENDENCY_CHECKS=false
ALLOW_START_WITHOUT_DB=true
WAIT_FOR_DB=false
WAIT_FOR_REDIS=false
```

After infra/env is verified, you can progressively harden by setting:
- `ENFORCE_PRODUCTION_SAFETY=true`
- `STRICT_STARTUP_DEPENDENCY_CHECKS=true`
- `ALLOW_START_WITHOUT_DB=false`
- `WAIT_FOR_DB=true`
- `WAIT_FOR_REDIS=true`

## MNC-Grade Controls Implemented

- Non-root runtime image with `tini` init process
- Dependency-aware startup entrypoint (`WAIT_FOR_DB`, `WAIT_FOR_REDIS`)
- Optional pre-start migration hook (`RUN_DB_MIGRATIONS=true`)
- Service health checks for API/DB/Redis/MQTT
- Worker isolation via `workers` profile
- One-shot migration service via `migrations` profile
- Security baseline (`no-new-privileges`, `cap_drop: ALL`, `/tmp` tmpfs)
- Production overrides: `read_only`, tighter CPU/memory/pid limits

## Quick Validation

```bash
docker compose -f docker-compose.yml config
docker compose -f docker-compose.yml -f docker-compose.dev.yml config
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
```
