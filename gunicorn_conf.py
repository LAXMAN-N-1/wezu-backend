import os


def _int_env(name: str, default: int, min_value: int = 1) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError):
        return default
    return max(min_value, parsed)


bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
worker_class = "uvicorn.workers.UvicornWorker"

# Conservative default for small VPS (Hostinger 2-4 vCPU).
# Each Uvicorn worker consumes ~150-250MB.  2 workers ≈ 400-500MB.
# Override with WEB_CONCURRENCY or GUNICORN_WORKERS env var.
workers = _int_env("WEB_CONCURRENCY", _int_env("GUNICORN_WORKERS", 2))
threads = _int_env("GUNICORN_THREADS", 1)
timeout = _int_env("GUNICORN_TIMEOUT", 120)
graceful_timeout = _int_env("GUNICORN_GRACEFUL_TIMEOUT", 30)

# keepalive must exceed Traefik's idle timeout (default 90s) to avoid
# premature connection teardown and TCP RST under load.
keepalive = _int_env("GUNICORN_KEEPALIVE", 65)

# Recycle workers to prevent memory bloat on long-running VPS.
max_requests = _int_env("GUNICORN_MAX_REQUESTS", 1200)
max_requests_jitter = _int_env("GUNICORN_MAX_REQUESTS_JITTER", 120)

preload_app = False
worker_tmp_dir = "/dev/shm"

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()

# Coolify/Traefik terminate TLS and forward headers to the app.
forwarded_allow_ips = os.getenv("FORWARDED_ALLOW_IPS", "*")
