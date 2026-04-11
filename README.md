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

## ⚡ Go Rewrite (v2)
- New low-latency rewrite lives in `v2/` using Go + PostgreSQL + Redis.
- Includes modular domain boundaries, keyset pagination, SWR caching, queue workers, and k6 performance gates.
- Quick start:
  ```bash
  cd v2
  cp .env.example .env
  make tidy
  make run
  ```

## 🌐 Coolify + Traefik Deployment

For ingress through Coolify/Traefik (no app host port publishing), follow:

- [DEPLOY_COOLIFY_TRAEFIK.md](docs/DEPLOY_COOLIFY_TRAEFIK.md)

## 📂 Repository Structure
- `app/api/v1`: Route handlers grouped by domain.
- `app/models`: SQLModel definitions.
- `app/db`: Session management and DB migrations.

---
© 2026 WEZU Tech.
