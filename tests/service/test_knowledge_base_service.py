import pytest
from sqlmodel import Session
from app.services.knowledge_base_service import KnowledgeBaseService
from app.schemas.knowledge_base import ArticleCreate, ArticleUpdate, CategoryCreate, CategoryUpdate
from app.models.knowledge_article import ArticleStatus


def test_create_and_get_category(session: Session):
    cat_in = CategoryCreate(name="Hardware APIs", description="All about APIs")
    cat = KnowledgeBaseService.create_category(session, cat_in)
    
    assert cat.id is not None
    assert cat.name == "Hardware APIs"
    assert "hardware-apis" in cat.slug

    tree = KnowledgeBaseService.get_category_tree(session)
    assert len(tree) >= 1
    assert any(c.name == "Hardware APIs" for c in tree)

def test_article_crud_and_status(session: Session):
    # Setup Category
    cat_in = CategoryCreate(name="Setup Guide")
    cat = KnowledgeBaseService.create_category(session, cat_in)
    
    # Create Article
    article_in = ArticleCreate(title="How to install", content="Step 1...", category_id=cat.id, tags=["setup", "install"], status="draft")
    article = KnowledgeBaseService.create_article(session, article_in, author_id=1)
    
    assert article.id is not None
    assert article.status == ArticleStatus.DRAFT
    assert article.published_at is None
    
    # Update Article to Published
    update_in = ArticleUpdate(status="published")
    updated = KnowledgeBaseService.update_article(session, article.id, update_in)
    
    assert updated.status == ArticleStatus.PUBLISHED
    assert updated.published_at is not None

def test_public_articles_list(session: Session):
    cat = KnowledgeBaseService.create_category(session, CategoryCreate(name="Public Testing"))
    
    # Create Draft
    KnowledgeBaseService.create_article(session, ArticleCreate(title="Draft 1", content="X", category_id=cat.id), author_id=1)
    
    # Create Published
    KnowledgeBaseService.create_article(session, ArticleCreate(title="Pub 1", content="Y", category_id=cat.id, status="published"), author_id=1)
    
    public_articles = KnowledgeBaseService.get_public_articles(session)
    assert len(public_articles) >= 1
    assert any(a.title == "Pub 1" for a in public_articles)
    assert all(a.status == ArticleStatus.PUBLISHED for a in public_articles)

def test_views_and_helpfulness(session: Session):
    cat = KnowledgeBaseService.create_category(session, CategoryCreate(name="Testing Helpfulness"))
    article = KnowledgeBaseService.create_article(session, ArticleCreate(title="Helpful Tricks", content="Yes", category_id=cat.id, status="published"), author_id=1)
    
    assert article.views_count == 0
    assert article.helpful_count == 0
    
    # Record view
    KnowledgeBaseService.record_view(session, article.id, user_id=2, ip_address="127.0.0.1")
    assert article.views_count == 1
    assert len(article.views) == 1
    
    # Record helpful vote
    KnowledgeBaseService.record_helpful_vote(session, article.id, is_helpful=True)
    KnowledgeBaseService.record_helpful_vote(session, article.id, is_helpful=False)
    
    assert article.helpful_count == 1
    assert article.not_helpful_count == 1

def test_article_search(session: Session):
    cat = KnowledgeBaseService.create_category(session, CategoryCreate(name="Networking"))
    KnowledgeBaseService.create_article(session, ArticleCreate(title="Router Config", content="Configure your local 192.168.1.1 router", category_id=cat.id, status="published"), author_id=1)
    
    # Searching for "router"
    results = KnowledgeBaseService.search_articles(session, "router")
    assert len(results) >= 1
    
    first = results[0]
    assert "Router Config" in first["title"]
    assert "..." in first["snippet"]
