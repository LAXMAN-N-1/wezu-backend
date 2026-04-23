# Hostinger VPS Backend Runbook

This runbook is for non-Docker VPS deployments of `wezu-backend`.

## 1. Incident Root Cause (Fixed in code)

The crash below was caused by FastAPI dependency introspection against postponed annotations:

`TypeError: ForwardRef('EmailPasswordRequestForm') is not a callable object`

The fix is now in code:
- `app/api/v1/auth.py`: `/auth/token` now uses `Depends(EmailPasswordRequestForm)`
- `app/api/v1/stations.py`: nearby filters now use `Depends(NearbyFilterSchema)`

This avoids ForwardRef callability crashes on older FastAPI/Python combinations.

## 2. Production Deployment Checklist

Run from `/var/www/wezu/wezu-backend`:

```bash
python3 --version
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.prod.txt
```

Create and validate `.env`:
- `ENVIRONMENT=production`
- `SECRET_KEY` must be a real random key (not placeholder)
- `DATABASE_URL`, `REDIS_URL`, `ALLOWED_HOSTS`, `CORS_ORIGINS` must be production values

Generate secret key:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

Run preflight before starting service:

```bash
python3 scripts/vps_preflight.py
```

If preflight fails, do not restart systemd until errors are resolved.

## 3. Run with Gunicorn (Production)

Do not run long-term production with raw `uvicorn` command.

Use:

```bash
source venv/bin/activate
gunicorn -c gunicorn_conf.py app.main:app
```

## 4. Systemd Service (Recommended)

Use template file:

- `prod/systemd/wezu-backend.service.example`

Install:

```bash
cp prod/systemd/wezu-backend.service.example /etc/systemd/system/wezu-backend.service
systemctl daemon-reload
systemctl enable wezu-backend
systemctl restart wezu-backend
systemctl status wezu-backend --no-pager
```

Logs:

```bash
journalctl -u wezu-backend -n 200 --no-pager
journalctl -u wezu-backend -f
```

## 5. Post-Deploy Verification

```bash
curl -fsS http://127.0.0.1:8000/live
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/ready
```

Expected:
- `/live` returns `status: ok`
- `/health` returns `ok` or `degraded` with dependency details
- `/ready` returns `status: ready` when required dependencies are healthy

## 6. Fast Troubleshooting Map

`SECRET_KEY contains a placeholder value`
- Fix `.env` with generated random key.

`ForwardRef(... ) is not a callable object`
- Pull latest backend code (this is fixed).
- Re-run `python3 scripts/vps_preflight.py`.

`CORS_ORIGINS must include production origin(s)`
- Set exact frontend origins in `.env`, comma-separated.

`ALLOWED_HOSTS must include production domain(s)`
- Add API domain values in `.env`.

`Database/Redis unavailable`
- Validate connection strings, firewall, and service health before app restart.
