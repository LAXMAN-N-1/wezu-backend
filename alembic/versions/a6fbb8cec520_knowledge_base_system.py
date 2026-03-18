"""Knowledge Base System

Revision ID: a6fbb8cec520
Revises: a1b2c3d4e5f6
Create Date: 2026-03-18 15:05:22.814115

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a6fbb8cec520'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create Article Categories Table
    op.create_table(
        'article_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=120), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['parent_id'], ['core.article_categories.id'], ),
        sa.PrimaryKeyConstraint('id'),
        schema='core'
    )
    op.create_index(op.f('ix_core_article_categories_name'), 'article_categories', ['name'], unique=False, schema='core')
    op.create_index(op.f('ix_core_article_categories_slug'), 'article_categories', ['slug'], unique=True, schema='core')

    # 2. Create Knowledge Articles Table
    op.create_table(
        'knowledge_articles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('slug', sa.String(length=220), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('author_id', sa.Integer(), nullable=True),
        sa.Column('views_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('helpful_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('not_helpful_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['author_id'], ['core.users.id'], ),
        sa.ForeignKeyConstraint(['category_id'], ['core.article_categories.id'], ),
        sa.PrimaryKeyConstraint('id'),
        schema='core'
    )
    op.create_index(op.f('ix_core_knowledge_articles_slug'), 'knowledge_articles', ['slug'], unique=True, schema='core')
    op.create_index(op.f('ix_core_knowledge_articles_status'), 'knowledge_articles', ['status'], unique=False, schema='core')

    # 3. Create Article Views Table
    op.create_table(
        'article_views',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('article_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('viewed_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['article_id'], ['core.knowledge_articles.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['core.users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        schema='core'
    )
    op.create_index(op.f('ix_core_article_views_article_id'), 'article_views', ['article_id'], unique=False, schema='core')
    op.create_index(op.f('ix_core_article_views_user_id'), 'article_views', ['user_id'], unique=False, schema='core')

    # 4. Data Migration
    conn = op.get_bind()
    # Check if faqs table exists
    from sqlalchemy.engine import reflection
    inspector = reflection.Inspector.from_engine(conn)
    if 'faqs' in inspector.get_table_names(schema='core'):
        faqs = conn.execute(sa.text("SELECT id, question, answer, category, is_active, helpful_count, not_helpful_count, created_at, updated_at FROM core.faqs")).fetchall()
        
        if faqs:
            import datetime, re
            categories = list(set([f[3] for f in faqs if f[3]]))
            if not categories:
                categories = ["general"]
            
            cat_map = {}
            for idx, cat_name in enumerate(categories):
                slug = re.sub(r'[^a-z0-9]+', '-', cat_name.lower()).strip('-') + f"-{idx}"
                now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                conn.execute(
                    sa.text(f"INSERT INTO core.article_categories (name, slug, sort_order, is_active, created_at, updated_at) VALUES ('{cat_name}', '{slug}', 0, 1, '{now}', '{now}')")
                )
                res = conn.execute(sa.text(f"SELECT id FROM core.article_categories WHERE slug = '{slug}'")).fetchone()
                cat_map[cat_name] = res[0]
                
            for f in faqs:
                cat_id = cat_map.get(f[3])
                slug = re.sub(r'[^a-z0-9]+', '-', f[1].lower()[:50]).strip('-') + f"-{f[0]}"
                status = "published" if f[4] else "draft"
                created_at = f[7] if isinstance(f[7], str) else f[7].strftime('%Y-%m-%d %H:%M:%S')
                updated_at = f[8] if isinstance(f[8], str) else f[8].strftime('%Y-%m-%d %H:%M:%S')
                published_at = created_at if status == "published" else "NULL"
                
                pub_val = f"'{published_at}'" if published_at != "NULL" else "NULL"
                content = f[2].replace("'", "''")
                title = f[1][:200].replace("'", "''")
                
                conn.execute(
                    sa.text(f"""
                        INSERT INTO core.knowledge_articles 
                        (title, slug, content, category_id, status, views_count, helpful_count, not_helpful_count, created_at, updated_at, published_at, tags)
                        VALUES 
                        ('{title}', '{slug}', '{content}', {cat_id}, '{status}', 0, {f[5]}, {f[6]}, '{created_at}', '{updated_at}', {pub_val}, '[]')
                    """)
                )


def downgrade() -> None:
    op.drop_index(op.f('ix_core_article_views_user_id'), table_name='article_views', schema='core')
    op.drop_index(op.f('ix_core_article_views_article_id'), table_name='article_views', schema='core')
    op.drop_table('article_views', schema='core')
    
    op.drop_index(op.f('ix_core_knowledge_articles_status'), table_name='knowledge_articles', schema='core')
    op.drop_index(op.f('ix_core_knowledge_articles_slug'), table_name='knowledge_articles', schema='core')
    op.drop_table('knowledge_articles', schema='core')
    
    op.drop_index(op.f('ix_core_article_categories_slug'), table_name='article_categories', schema='core')
    op.drop_index(op.f('ix_core_article_categories_name'), table_name='article_categories', schema='core')
    op.drop_table('article_categories', schema='core')
