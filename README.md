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

## 🌐 Hostinger VPS (Multi-Project)

For shared VPS deployment with multiple subdomains/projects, follow:

- [DEPLOY_HOSTINGER_MULTIPROJECT.md](DEPLOY_HOSTINGER_MULTIPROJECT.md)

## 📂 Repository Structure
- `app/api/v1`: Route handlers grouped by domain.
- `app/models`: SQLModel definitions.
- `app/db`: Session management and DB migrations.

---
© 2026 WEZU Tech.
