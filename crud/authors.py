from __future__ import annotations

import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.author import Author, PaperAuthor
from models.paper import Paper
from models.citation import Citation


async def get_authors_with_stats(
    db: AsyncSession,
) -> list[tuple[Author, int, float | None]]:
    """
    Return all authors with:
    - paper count
    - average paper pagerank_score

    Average pagerank is computed in the DB query.
    """
    stmt = (
        select(
            Author,
            func.count(Paper.id).label("paper_count"),
            func.avg(Paper.pagerank_score).label("avg_pagerank_score"),
        )
        .join(PaperAuthor, PaperAuthor.author_id == Author.id)
        .join(Paper, Paper.id == PaperAuthor.paper_id)
        .group_by(Author.id)
        .order_by(func.count(Paper.id).desc(), Author.name.asc())
    )

    result = await db.execute(stmt)
    return list(result.all())


async def get_author_with_stats(
    db: AsyncSession,
    author_id: uuid.UUID,
) -> tuple[Author, int, float | None] | None:
    """
    Return one author with:
    - paper count
    - average paper pagerank_score

    Average pagerank is computed in the DB query.
    """
    stmt = (
        select(
            Author,
            func.count(Paper.id).label("paper_count"),
            func.avg(Paper.pagerank_score).label("avg_pagerank_score"),
        )
        .join(PaperAuthor, PaperAuthor.author_id == Author.id)
        .join(Paper, Paper.id == PaperAuthor.paper_id)
        .where(Author.id == author_id)
        .group_by(Author.id)
    )

    result = await db.execute(stmt)
    return result.one_or_none()


async def get_author_papers(
    db: AsyncSession,
    author_id: uuid.UUID,
) -> list[Paper]:
    """
    Return all papers for one author, sorted by date descending.
    """
    stmt = (
        select(Paper)
        .join(PaperAuthor, PaperAuthor.paper_id == Paper.id)
        .where(PaperAuthor.author_id == author_id)
        .order_by(
            desc(Paper.published_date),
            desc(Paper.created_at),
        )
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_author_total_citations_received(
    db: AsyncSession,
    author_id: uuid.UUID,
) -> int:
    """
    Return the total number of citations received across all papers by this author.
    """
    stmt = (
        select(func.count(Citation.id))
        .select_from(Paper)
        .join(PaperAuthor, PaperAuthor.paper_id == Paper.id)
        .outerjoin(Citation, Citation.cited_paper_id == Paper.id)
        .where(PaperAuthor.author_id == author_id)
    )

    result = await db.execute(stmt)
    return int(result.scalar_one() or 0)


async def get_author_top_papers_by_pagerank(
    db: AsyncSession,
    author_id: uuid.UUID,
    limit: int = 5,
) -> list[Paper]:
    """
    Return the author's top papers by pagerank_score descending.
    """
    stmt = (
        select(Paper)
        .join(PaperAuthor, PaperAuthor.paper_id == Paper.id)
        .where(PaperAuthor.author_id == author_id)
        .order_by(
            Paper.pagerank_score.desc(),
            Paper.published_date.desc(),
            Paper.created_at.desc(),
        )
        .limit(limit)
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())