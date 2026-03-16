from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.author import PaperAuthor
from models.citation import Citation
from models.paper import Paper


async def get_paper(
    db: AsyncSession,
    paper_id: uuid.UUID,
) -> Paper | None:
    result = await db.execute(
        select(Paper).where(Paper.id == paper_id)
    )
    return result.scalar_one_or_none()


async def get_papers(
    db: AsyncSession,
    category: str | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> list[Paper]:
    stmt = select(Paper)

    if category:
        stmt = stmt.where(
            or_(
                Paper.primary_category == category,
                Paper.all_categories.any(category),
            )
        )

    if search:
        stmt = stmt.where(Paper.title.ilike(f"%{search}%"))

    stmt = (
        stmt.order_by(Paper.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def count_papers(
    db: AsyncSession,
    category: str | None = None,
    search: str | None = None,
) -> int:
    stmt = select(func.count()).select_from(Paper)

    if category:
        stmt = stmt.where(
            or_(
                Paper.primary_category == category,
                Paper.all_categories.any(category),
            )
        )

    if search:
        stmt = stmt.where(Paper.title.ilike(f"%{search}%"))

    result = await db.execute(stmt)
    return int(result.scalar_one())


async def get_paper_references(
    db: AsyncSession,
    paper_id: uuid.UUID,
) -> list[Paper]:
    """
    Papers this paper cites.
    """
    stmt = (
        select(Paper)
        .join(Citation, Citation.cited_paper_id == Paper.id)
        .where(Citation.citing_paper_id == paper_id)
        .order_by(Paper.title.asc())
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_papers_citing_paper(
    db: AsyncSession,
    paper_id: uuid.UUID,
) -> list[Paper]:
    """
    Papers that cite this paper.
    """
    stmt = (
        select(Paper)
        .join(Citation, Citation.citing_paper_id == Paper.id)
        .where(Citation.cited_paper_id == paper_id)
        .order_by(Paper.title.asc())
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_paper_authors(
    db: AsyncSession,
    paper_id: uuid.UUID,
) -> list[PaperAuthor]:
    """
    Return PaperAuthor ORM rows so the caller has both:
    - position
    - linked Author object
    """
    stmt = (
        select(PaperAuthor)
        .options(selectinload(PaperAuthor.author))
        .where(PaperAuthor.paper_id == paper_id)
        .order_by(PaperAuthor.position.asc())
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_ranked_papers(
    db: AsyncSession,
    category: str | None = None,
    limit: int = 20,
) -> list[Paper]:
    """
    Return top papers ranked by pagerank_score descending.

    Optional category filter matches either primary_category or membership in
    all_categories.
    """
    stmt = select(Paper)

    if category:
        stmt = stmt.where(
            or_(
                Paper.primary_category == category,
                Paper.all_categories.any(category),
            )
        )

    stmt = (
        stmt.order_by(
            desc(Paper.pagerank_score),
            Paper.title.asc(),
        )
        .limit(limit)
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def semantic_search_papers(
    db: AsyncSession,
    query_vector: list[float],
    limit: int = 10,
    category: str | None = None,
) -> list[tuple[Paper, float]]:
    """
    Semantic search over papers using pgvector cosine distance.

    Returns:
        List of (Paper, similarity_score) tuples, ordered by similarity descending.
    """
    cosine_distance = Paper.abstract_embedding.cosine_distance(query_vector)
    similarity_score = (1.0 - cosine_distance).label("similarity_score")

    stmt = (
        select(Paper, similarity_score)
        .where(Paper.abstract_embedding.is_not(None))
    )

    if category:
        stmt = stmt.where(
            or_(
                Paper.primary_category == category,
                Paper.all_categories.any(category),
            )
        )

    stmt = (
        stmt.order_by(cosine_distance.asc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [(paper, float(similarity)) for paper, similarity in rows]


async def get_similar_papers(
    db: AsyncSession,
    source_paper_id: uuid.UUID,
    source_vector: list[float],
    limit: int = 10,
) -> list[tuple[Paper, float]]:
    """
    Find papers similar to a given paper using cosine similarity on abstract embeddings.

    Excludes the source paper itself.
    Returns:
        list of (Paper, similarity_score)
    """
    cosine_distance = Paper.abstract_embedding.cosine_distance(source_vector)
    similarity_score = (1.0 - cosine_distance).label("similarity_score")

    stmt = (
        select(Paper, similarity_score)
        .where(
            Paper.abstract_embedding.is_not(None),
            Paper.id != source_paper_id,
        )
        .order_by(cosine_distance.asc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [(paper, float(similarity)) for paper, similarity in rows]