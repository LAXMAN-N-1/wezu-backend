# WEZU Backend — Copilot Instructions

This is a FastAPI-based high-performance backend powering the WEZU battery swapping ecosystem. This document provides essential context for effective development.

## Quick Start

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Run the server (development):**
```bash
uvicorn app.main:app --reload --port 8000
```

**Interactive API docs:**
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Build, Test & Lint

### Running Tests
```bash
# All tests
pytest

# Single test file
pytest tests/test_audit_core.py

# Single test function
pytest tests/test_audit_core.py::TestAuditLogger::test_creates_record_with_all_fields

# Tests matching pattern
pytest -k "audit" -v

# With coverage
pytest --cov=app tests/
```

**Test fixtures** are defined in `tests/conftest.py`. Database is seeded with basic roles, menus, and permissions per test.

### Code Quality

```bash
# Linting
flake8 app/ tests/

# Type checking
mypy app/

# Code formatting
black app/ tests/

# Import sorting
isort app/ tests/

# All checks (if configured)
pylint app/
ruff check app/
```

### Database Migrations

```bash
# Create migration from model changes
alembic revision --autogenerate -m "description"

# Apply pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

## Architecture & Patterns

### High-Level Structure

```
app/
├── main.py                 # FastAPI app initialization, middleware setup
├── api/v1/                 # Route handlers (auth.py, users.py, stations.py, etc.)
├── services/               # Business logic (auth_service.py, analytics_service.py, etc.)
├── repositories/           # Data access layer (user_repository.py, payment_repository.py, etc.)
├── models/                 # SQLModel definitions + relationships
├── schemas/                # Pydantic request/response validation
├── middleware/             # CORS, security headers, rate limiting, audit, RBAC
├── core/                   # Config, security, logging, database, audit
├── db/                     # Database session management
├── integrations/           # External APIs (Firebase, MQTT, payments, etc.)
├── tasks/                  # Background jobs (APScheduler, async)
├── ml/                     # Machine learning utilities
├── workers/                # Scheduled tasks and background workers
└── utils/                  # Helpers (CORS, decorators, etc.)
```

### Layer Responsibilities

1. **Routes (API Layer)**: Request validation, dependency injection, response serialization
2. **Services**: Core business logic, orchestration, external service calls
3. **Repositories**: CRUD operations, query building, database-specific logic
4. **Models**: SQLModel table definitions with relationships (not for API responses)
5. **Schemas**: Pydantic models for API input/output validation
6. **Core**: Shared utilities (config, security, logging, audit)

### Key Design Patterns

**Dependency Injection:**
```python
from app.api import deps
from app.db.session import Session

@router.get("/users/{user_id}")
def get_user(user_id: int, db: Session = Depends(deps.get_db)):
    return repository.get_user(db, user_id)
```

**Service Pattern:**
Services encapsulate business logic and are called from routes:
```python
from app.services.auth_service import AuthService
result = await AuthService.verify_google_token(token)
```

**Repository Pattern:**
Repositories handle data access; use dependency injection to pass `Session`:
```python
# In services or routes
user = user_repository.get_by_email(db, email)
```

**SQLModel + SQLAlchemy:**
- Models define tables with `table=True`
- Relationships use `Relationship()` for navigation
- Use `select()` queries for type safety
- Session usage: `with Session(engine) as session: ...` or `Depends(get_db)`

### Configuration

**Environment Variables** are loaded in `app/core/config.py` using Pydantic Settings. No defaults for critical secrets:
- `DATABASE_URL` (PostgreSQL connection)
- `REDIS_URL` (caching & sessions)
- `MONGODB_URL` (audit logs)
- `SECRET_KEY` (JWT signing)

**Accessing config:**
```python
from app.core.config import settings
print(settings.PROJECT_NAME, settings.LOG_LEVEL)
```

### Authentication & Authorization

**Auth flow:**
1. User logs in → creates access/refresh tokens via `AuthService`
2. Tokens validated in `RBACMiddleware` (roles & permissions checked)
3. Current user available in routes via `Depends(deps.get_current_user)`

**Role-based access:**
- Roles are stored in DB with `is_system_role=True` for built-ins
- Permissions are linked via `RolePermission` model
- Middleware enforces on all routes marked with `@limiter.limit()`

### Logging

**Structured logging** via `structlog`:
```python
from app.core.logging import get_logger
logger = get_logger(__name__)
logger.info("event_name", user_id=123, action="login")
```

Logs are sent to stderr in JSON format (via `structlog` config in `app/core/logging.py`).

### Audit Trail

**Audit logging** is automatic for sensitive operations:
```python
from app.core.audit import audit_log

@audit_log(action="user_created", resource_type="user")
def create_user(db, user_data):
    ...
```

Audit records are stored in both PostgreSQL and MongoDB for redundancy.

### Background Tasks

**APScheduler** is used for recurring tasks (in `app/tasks/` and `app/workers/`):
- `charging_optimizer.py` — optimize charging schedules
- `analytics_tasks.py` — compute analytics
- `battery_health_monitor.py` — health checks
- `station_monitor.py` — station status

Scheduler is started in `app/main.py` via `start_scheduler()` and stopped via `stop_scheduler()`.

### External Integrations

- **Firebase Admin SDK** — push notifications, messaging
- **MQTT** — IoT device communication (started in `main.py`)
- **Razorpay** — payment processing (webhook at `/webhooks/razorpay`)
- **Twilio** — SMS/OTP delivery
- **Google/Apple OAuth** — third-party authentication

## Middleware Stack

The app applies middleware in this order (bottom = first executed):

1. **TrustedHostMiddleware** — validates Host header
2. **TrustedProxyHeadersMiddleware** — trusts X-Forwarded-* headers
3. **CORSMiddleware** — configures CORS (see `cors_headers_for_origin()` utility)
4. **GZipMiddleware** — compresses responses
5. **RequestLoggingMiddleware** — logs incoming requests
6. **RBACMiddleware** — checks roles/permissions
7. **SecureHeadersMiddleware** — adds security headers (CSP, HSTS, etc.)
8. **AuditMiddleware** — queues audit events
9. **Rate limiter** — enforces request limits per route (via `@limiter.limit()`)

Error handlers (in `app/api/errors/handlers.py`) catch and standardize exceptions.

## Common Development Tasks

### Adding a New Endpoint

1. **Define the route** in `app/api/v1/{domain}.py`:
   ```python
   from fastapi import APIRouter, Depends
   router = APIRouter(prefix="/items", tags=["items"])
   
   @router.post("/", response_model=ItemResponse)
   def create_item(item: ItemCreate, db: Session = Depends(deps.get_db)):
       return item_service.create(db, item)
   ```

2. **Define schemas** in `app/schemas/{domain}.py` for request/response:
   ```python
   class ItemCreate(BaseModel):
       name: str
       price: float
   
   class ItemResponse(ItemCreate):
       id: int
   ```

3. **Create/update the model** in `app/models/{domain}.py`:
   ```python
   class Item(SQLModel, table=True):
       id: Optional[int] = Field(default=None, primary_key=True)
       name: str = Field(index=True)
       price: float
   ```

4. **Add service logic** in `app/services/{domain}_service.py`.

5. **Register the route** in `app/main.py`:
   ```python
   from app.api.v1 import items
   app.include_router(items.router, prefix="/api/v1")
   ```

6. **Write tests** in `tests/{domain}_test.py`.

### Adding a Database Migration

```bash
# Create migration from model changes
alembic revision --autogenerate -m "add item table"

# Review generated migration in alembic/versions/
# Edit if needed, then apply:
alembic upgrade head
```

### Running a Single Test

```bash
pytest tests/test_audit_core.py::TestAuditLogger::test_creates_record_with_all_fields -v
```

### Debugging a Request

Enable request/response logging in `.env`:
```
LOG_REQUESTS=true
LOG_ACCESS_LOGS=true
LOG_LEVEL=DEBUG
```

Logs go to stderr; tail them or pipe them through a JSON parser:
```bash
python -m uvicorn app.main:app | jq '.'
```

## File Organization Conventions

- **Routes** (`app/api/v1/*.py`): One file per domain, functions prefixed with HTTP method
- **Services** (`app/services/*.py`): One file per domain, class-based or static methods
- **Models** (`app/models/*.py`): One file per domain, SQLModel tables only
- **Schemas** (`app/schemas/*.py`): One file per domain, Pydantic models for validation
- **Tests** (`tests/*.py`): Match domain structure, use `conftest.py` for fixtures

## Deployment

**Docker build** (uses multi-stage to minimize image size):
```bash
docker build -t wezu-backend:latest .
```

**Production startup** (in Dockerfile CMD):
```bash
alembic upgrade head && exec gunicorn app.main:app -c gunicorn.conf.py ...
```

**Environment variables** are required at runtime (see `app/core/config.py`).

## Important Notes

- **All model imports**: Use `import app.models.all` in `main.py` to ensure all SQLModel classes are registered before the first query.
- **SQLite JSON workaround**: For local dev with SQLite, JSONB columns are patched to JSON (see `tests/conftest.py`).
- **Gunicorn worker logging**: The `gunicorn.conf.py` file re-initializes structured logging in each worker process (post_fork hook).
- **Rate limiting**: Routes can be protected with `@limiter.limit("10/minute")` decorator.
- **Async support**: Services can use `async def` and `await`; `run_in_threadpool()` is available for CPU-bound work.
- **Email/SMS**: Configured via `app/core/config.py` (Twilio, SendGrid, etc.); integrations in `app/integrations/`.
