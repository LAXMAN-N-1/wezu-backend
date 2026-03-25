import re
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from sqlmodel import Session, select, func, desc, or_, col
from sqlalchemy.orm import selectinload

from app.models.article_category import ArticleCategory
from app.models.knowledge_article import KnowledgeArticle, ArticleStatus
from app.models.article_view import ArticleView
from app.schemas.knowledge_base import (
    ArticleCreate,
    ArticleUpdate,
    CategoryCreate,
    CategoryUpdate,
)


def _generate_slug(title: str, db: Session, model_class: Any) -> str:
    """Helper to generate unique slug based on title/name."""
    base_slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    if not base_slug:
        import uuid
        base_slug = uuid.uuid4().hex[:8]

    slug = base_slug
    counter = 1
    while db.exec(select(model_class).where(col(getattr(model_class, "slug")) == slug)).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


class KnowledgeBaseService:

    # ── Categories ──────────────────────────────────────────────────

    @staticmethod
    def create_category(db: Session, cat_in: CategoryCreate) -> ArticleCategory:
        slug = _generate_slug(cat_in.name, db, ArticleCategory)
        cat = ArticleCategory(
            name=cat_in.name,
            slug=slug,
            description=cat_in.description,
            parent_id=cat_in.parent_id,
            sort_order=cat_in.sort_order,
        )
        db.add(cat)
        db.commit()
        db.refresh(cat)
        return cat

    @staticmethod
    def update_category(db: Session, cat_id: int, cat_in: CategoryUpdate) -> Optional[ArticleCategory]:
        cat = db.get(ArticleCategory, cat_id)
        if not cat:
            return None

        update_data = cat_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(cat, field, value)
            
        if "name" in update_data:
            cat.slug = _generate_slug(cat.name, db, ArticleCategory)

        cat.updated_at = datetime.utcnow()
        db.add(cat)
        db.commit()
        db.refresh(cat)
        return cat

    @staticmethod
    def delete_category(db: Session, cat_id: int) -> bool:
        cat = db.get(ArticleCategory, cat_id)
        if not cat:
            return False
            
        # Cannot delete if it has articles or children
        has_articles = db.exec(select(KnowledgeArticle).where(col(KnowledgeArticle.category_id) == cat_id)).first()
        has_children = db.exec(select(ArticleCategory).where(col(ArticleCategory.parent_id) == cat_id)).first()
        
        if has_articles or has_children:
            raise ValueError("Cannot delete category with active articles or subcategories")

        db.delete(cat)
        db.commit()
        return True

    @staticmethod
    def get_category_tree(db: Session) -> List[ArticleCategory]:
        # Return root categories; selectinload children
        statement = select(ArticleCategory).where(
            col(ArticleCategory.parent_id) == None,
            col(ArticleCategory.is_active) == True
        ).order_by(col(ArticleCategory.sort_order)).options(selectinload("children"))
        
        return list(db.exec(statement).all())


    # ── Articles ────────────────────────────────────────────────────

    @staticmethod
    def create_article(db: Session, article_in: ArticleCreate, author_id: int) -> KnowledgeArticle:
        slug = _generate_slug(article_in.title, db, KnowledgeArticle)
        article = KnowledgeArticle(
            title=article_in.title,
            slug=slug,
            content=article_in.content,
            category_id=article_in.category_id,
            tags=article_in.tags,
            status=ArticleStatus(article_in.status),
            author_id=author_id,
        )
        
        if article.status == ArticleStatus.PUBLISHED:
            article.published_at = datetime.utcnow()
            
        db.add(article)
        db.commit()
        db.refresh(article)
        return article

    @staticmethod
    def update_article(db: Session, article_id: int, article_in: ArticleUpdate) -> Optional[KnowledgeArticle]:
        article = db.get(KnowledgeArticle, article_id)
        if not article:
            return None

        update_data = article_in.model_dump(exclude_unset=True)
        old_status = article.status
        
        for field, value in update_data.items():
            if field == "status" and value:
                setattr(article, field, ArticleStatus(value))
            else:
                setattr(article, field, value)
                
        if "title" in update_data:
            article.slug = _generate_slug(article.title, db, KnowledgeArticle)

        # Handle publish timestamp
        if old_status != ArticleStatus.PUBLISHED and article.status == ArticleStatus.PUBLISHED:
            article.published_at = datetime.utcnow()

        article.updated_at = datetime.utcnow()
        db.add(article)
        db.commit()
        db.refresh(article)
        return article

    @staticmethod
    def delete_article(db: Session, article_id: int) -> bool:
        article = db.get(KnowledgeArticle, article_id)
        if not article:
            return False
            
        # Optional: Delete associated views first or let cascade handle it if configured
        views = db.exec(select(ArticleView).where(col(ArticleView.article_id) == article_id)).all()
        for v in views:
            db.delete(v)
            
        db.delete(article)
        db.commit()
        return True

    @staticmethod
    def get_public_articles(db: Session, category_id: Optional[int] = None, skip: int = 0, limit: int = 50) -> List[KnowledgeArticle]:
        statement = select(KnowledgeArticle).where(col(KnowledgeArticle.status) == ArticleStatus.PUBLISHED)
        if category_id:
            statement = statement.where(col(KnowledgeArticle.category_id) == category_id)
            
        statement = statement.order_by(desc(col(KnowledgeArticle.published_at))).offset(skip).limit(limit)
        return list(db.exec(statement).all())


    # ── Interactions (Views & Helpfulness) ──────────────────────────

    @staticmethod
    def record_view(db: Session, article_id: int, user_id: Optional[int] = None, ip_address: Optional[str] = None) -> Optional[KnowledgeArticle]:
        article = db.get(KnowledgeArticle, article_id)
        if not article or article.status != ArticleStatus.PUBLISHED:
            return None

        # Record event
        view = ArticleView(article_id=article_id, user_id=user_id, ip_address=ip_address)
        db.add(view)
        
        # Increment counter
        article.views_count += 1
        db.add(article)
        db.commit()
        db.refresh(article)
        return article

    @staticmethod
    def record_helpful_vote(db: Session, article_id: int, is_helpful: bool) -> bool:
        article = db.get(KnowledgeArticle, article_id)
        if not article or article.status != ArticleStatus.PUBLISHED:
            return False

        if is_helpful:
            article.helpful_count += 1
        else:
            article.not_helpful_count += 1
            
        db.add(article)
        db.commit()
        return True


    # ── Search ──────────────────────────────────────────────────────

    @staticmethod
    def search_articles(db: Session, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Basic full-text search implementation using ILIKE.
        In a real prod pg environment, tsvector would be utilized.
        """
        if not query or len(query) < 3:
            return []

        search_term = f"%{query}%"
        
        statement = select(KnowledgeArticle).where(
            col(KnowledgeArticle.status) == ArticleStatus.PUBLISHED,
            or_(
                col(KnowledgeArticle.title).ilike(search_term),
                col(KnowledgeArticle.content).ilike(search_term)
            )
        ).order_by(desc(col(KnowledgeArticle.views_count))).limit(limit)
        
        results = list(db.exec(statement).all())
        
        formatted = []
        for r in results:
            # Generate a snippet around the matched query if it's in the content
            snippet = r.content[:150] + "..."  # Default snippet
            lower_content = r.content.lower()
            lower_query = query.lower()
            idx = lower_content.find(lower_query)
            
            if idx != -1:
                start = max(0, idx - 50)
                end = min(len(r.content), idx + len(query) + 50)
                snippet = "..." + r.content[start:end] + "..."
                
                # Simple highlighting for the output if requested (markdown compatible)
                # snippet = snippet.replace(query, f"**{query}**")  # careful with capitalization
                
            formatted.append({
                "id": r.id,
                "title": r.title,
                "slug": r.slug,
                "snippet": snippet,
                "category_id": r.category_id,
                "tags": r.tags,
                "views_count": r.views_count
            })
            
        return formatted


    # ── Admin Analytics ─────────────────────────────────────────────

    @staticmethod
    def get_analytics(db: Session) -> Dict[str, Any]:
        total_articles = db.exec(select(func.count(col(KnowledgeArticle.id)))).one()
        total_published = db.exec(
            select(func.count(col(KnowledgeArticle.id))).where(col(KnowledgeArticle.status) == ArticleStatus.PUBLISHED)
        ).one()
        
        total_views = db.exec(select(func.sum(col(KnowledgeArticle.views_count)))).one() or 0

        # Top Viewed
        top_viewed = db.exec(
            select(KnowledgeArticle).order_by(desc(col(KnowledgeArticle.views_count))).limit(5)
        ).all()

        # Helpfulness metrics (at least 5 total votes)
        articles = db.exec(select(KnowledgeArticle).where(
            (col(KnowledgeArticle.helpful_count) + col(KnowledgeArticle.not_helpful_count)) >= 5
        )).all()

        ratios = []
        for a in articles:
            total_votes = a.helpful_count + a.not_helpful_count
            ratio = a.helpful_count / total_votes if total_votes > 0 else 0.0
            ratios.append({
                "id": a.id,
                "title": a.title,
                "helpful_count": a.helpful_count,
                "not_helpful_count": a.not_helpful_count,
                "ratio": round(ratio, 2)
            })
            
        ratios.sort(key=lambda x: x["ratio"], reverse=True)
        
        most_helpful = ratios[:5]
        least_helpful = list(reversed(ratios))[:5] if ratios else []

        return {
            "total_articles": total_articles,
            "total_published": total_published,
            "total_views": int(total_views),
            "top_viewed": [
                {
                    "id": a.id, 
                    "title": a.title, 
                    "views_count": a.views_count,
                    "helpful_count": a.helpful_count,
                    "not_helpful_count": a.not_helpful_count
                } for a in top_viewed
            ],
            "most_helpful": most_helpful,
            "least_helpful": least_helpful
        }
