#!/bin/sh
set -eu

log() {
  printf '%s %s\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$*"
}

wait_for_service() {
  service_name="$1"
  service_url="$2"
  timeout_seconds="$3"

  python - "$service_name" "$service_url" "$timeout_seconds" <<'PY'
import socket
import sys
import time
from urllib.parse import urlsplit

name = sys.argv[1]
url = sys.argv[2]
timeout = int(sys.argv[3])

parsed = urlsplit(url)

# Local sqlite deployments do not need TCP dependency checks.
if parsed.scheme.startswith("sqlite"):
    print(f"[entrypoint] {name}: sqlite URL detected, skipping wait")
    sys.exit(0)

host = parsed.hostname
if not host:
    print(f"[entrypoint] {name}: no hostname in URL, skipping wait")
    sys.exit(0)

if parsed.port:
    port = parsed.port
elif parsed.scheme.startswith("postgres"):
    port = 5432
elif parsed.scheme.startswith("redis"):
    port = 6379
elif parsed.scheme.startswith("mqtt"):
    port = 1883
else:
    port = 0

if port <= 0:
    print(f"[entrypoint] {name}: could not infer TCP port from URL {url}")
    sys.exit(1)

deadline = time.time() + timeout
while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"[entrypoint] {name}: reachable at {host}:{port}")
            sys.exit(0)
    except OSError:
        time.sleep(2)

print(f"[entrypoint] {name}: timeout waiting for {host}:{port} ({timeout}s)", file=sys.stderr)
sys.exit(1)
PY
}

STARTUP_TIMEOUT_SECONDS="${STARTUP_TIMEOUT_SECONDS:-180}"
WAIT_FOR_DB="${WAIT_FOR_DB:-true}"
WAIT_FOR_REDIS="${WAIT_FOR_REDIS:-true}"
RUN_DB_MIGRATIONS="${RUN_DB_MIGRATIONS:-false}"

if [ "$WAIT_FOR_DB" = "true" ] && [ "${DATABASE_URL:-}" != "" ]; then
  log "Waiting for database dependency"
  wait_for_service "database" "$DATABASE_URL" "$STARTUP_TIMEOUT_SECONDS"
fi

if [ "$WAIT_FOR_REDIS" = "true" ] && [ "${REDIS_URL:-}" != "" ]; then
  log "Waiting for redis dependency"
  wait_for_service "redis" "$REDIS_URL" "$STARTUP_TIMEOUT_SECONDS"
fi

if [ "$RUN_DB_MIGRATIONS" = "true" ]; then
  log "Running Alembic migrations before start"
  alembic upgrade head
fi

log "Starting process: $*"
exec "$@"
