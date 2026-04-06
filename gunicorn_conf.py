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
workers = _int_env("WEB_CONCURRENCY", 4)
threads = _int_env("GUNICORN_THREADS", 1)
timeout = _int_env("GUNICORN_TIMEOUT", 120)
graceful_timeout = _int_env("GUNICORN_GRACEFUL_TIMEOUT", 30)
keepalive = _int_env("GUNICORN_KEEPALIVE", 5)
max_requests = _int_env("GUNICORN_MAX_REQUESTS", 1200)
max_requests_jitter = _int_env("GUNICORN_MAX_REQUESTS_JITTER", 120)

preload_app = False
worker_tmp_dir = "/dev/shm"

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()

# Coolify/Traefik terminate TLS and forward headers to the app.
forwarded_allow_ips = os.getenv("FORWARDED_ALLOW_IPS", "*")
