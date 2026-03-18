import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.main import app
from app.api import deps
from app.models.user import User
from app.services.knowledge_base_service import KnowledgeBaseService
from app.schemas.knowledge_base import CategoryCreate, ArticleCreate


@pytest.fixture
def mock_customer():
    user = MagicMock(spec=User)
    user.id = 1
    user.is_superuser = False
    return user

@pytest.fixture
def mock_admin():
    user = MagicMock(spec=User)
    user.id = 2
    user.is_superuser = True
    return user

@pytest.fixture
def customer_client(mock_customer, session: Session):
    app.dependency_overrides[deps.get_optional_user] = lambda: mock_customer
    app.dependency_overrides[deps.get_current_user] = lambda: mock_customer
    app.dependency_overrides[deps.get_db] = lambda: session
    from app.db.session import get_session as db_get_session
    app.dependency_overrides[db_get_session] = lambda: session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

@pytest.fixture
def admin_client(mock_admin, session: Session):
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: mock_admin
    app.dependency_overrides[deps.get_db] = lambda: session
    from app.db.session import get_session as db_get_session
    app.dependency_overrides[db_get_session] = lambda: session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

@pytest.fixture
def seed_kb_data(session: Session):
    cat = KnowledgeBaseService.create_category(session, CategoryCreate(name="FAQ Sync"))
    art1 = KnowledgeBaseService.create_article(session, ArticleCreate(title="Battery Swapping", content="Just swap it", category_id=cat.id, status="published"), author_id=1)
    art2 = KnowledgeBaseService.create_article(session, ArticleCreate(title="Account Recovery", content="Draft mode", category_id=cat.id, status="draft"), author_id=1)
    return {"cat_id": cat.id, "pub_id": art1.id, "draft_id": art2.id}


def test_customer_list_articles(customer_client: TestClient, seed_kb_data: dict):
    response = customer_client.get("/api/v1/customer/knowledge/articles")
    assert response.status_code == 200
    data = response.json()["data"]
    
    assert any(a["id"] == seed_kb_data["pub_id"] for a in data)
    assert not any(a["id"] == seed_kb_data["draft_id"] for a in data)


def test_customer_read_article_increments_views(customer_client: TestClient, seed_kb_data: dict, session: Session):
    pub_id = seed_kb_data["pub_id"]
    response = customer_client.get(f"/api/v1/customer/knowledge/articles/{pub_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == pub_id
    assert data["views_count"] >= 1


def test_customer_search_articles(customer_client: TestClient, seed_kb_data: dict):
    response = customer_client.get("/api/v1/customer/knowledge/search?q=swap")
    assert response.status_code == 200
    data = response.json()["data"]
    
    assert data["total"] >= 1
    assert "Battery Swapping" in data["results"][0]["title"]


def test_admin_create_article(admin_client: TestClient, seed_kb_data: dict):
    payload = {
        "title": "Security Updates",
        "content": "Make sure your passwords are secure.",
        "category_id": seed_kb_data["cat_id"]
    }
    response = admin_client.post(
        "/api/v1/admin/knowledge/articles",
        json=payload
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["title"] == "Security Updates"
    assert data["status"] == "draft"


def test_admin_get_analytics(admin_client: TestClient, seed_kb_data: dict):
    response = admin_client.get("/api/v1/admin/knowledge/analytics")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "total_articles" in data
    assert "total_published" in data
