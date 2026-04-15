# WEZU — Backend Services

High-performance FastAPI backend powering the WEZU battery swapping ecosystem, including the Dealer Portal and Customer App.

## 🚀 Key Modules
- **Dealer Portal API**: Comprehensive endpoints for onboarding, inventory, and analytics.
- **Onboarding Engine**: 8-stage verification workflow with automated checks.
- **Auth & RBAC**: Real-time authentication and role-based access control.
- **Database**: SQLModel with Neon DB (PostgreSQL).

## 🛠 Tech Stack
- **Language**: Python 3.10+
- **Framework**: FastAPI
- **ORM**: SQLModel / SQLAlchemy
- **Database**: PostgreSQL (Neon)
- **Validation**: Pydantic v2

## 🏁 Development Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the server**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

3. **API Documentation**:
   Access interactive docs at `http://localhost:8000/docs`.

## 🌐 Coolify + Traefik Deployment

For ingress through Coolify/Traefik (no app host port publishing), follow:

- [DEPLOY_COOLIFY_TRAEFIK.md](docs/DEPLOY_COOLIFY_TRAEFIK.md)
- [DOCKER_MULTI_PHASE_DEPLOYMENT.md](docs/DOCKER_MULTI_PHASE_DEPLOYMENT.md)

## 📊 Logging (Production)

The backend now uses a unified structured logging pipeline from `app/core/logging.py`.

- JSON structured logs in production.
- Request/correlation IDs on every request log line.
- Automatic redaction for sensitive fields (`token`, `password`, `secret`, cookies, etc.).
- Safe serialization for validation errors (no bytes serialization crashes).
- Noise controls for health/readiness logs via `LOG_EXCLUDE_PATHS`.

Key envs:
- `LOG_LEVEL`
- `LOG_REQUESTS`
- `LOG_ACCESS_LOGS`
- `LOG_HEALTHCHECKS`
- `LOG_SLOW_REQUEST_THRESHOLD_MS`
- `LOG_REDACT_SENSITIVE_FIELDS`
- `LOG_MAX_FIELD_LENGTH`
- `LOG_MAX_COLLECTION_ITEMS`
- `LOG_EXCLUDE_PATHS`

## 📂 Repository Structure
- `app/api/v1`: Route handlers grouped by domain.
- `app/models`: SQLModel definitions.
- `app/db`: Session management and DB migrations.

---
© 2026 WEZU Tech.
