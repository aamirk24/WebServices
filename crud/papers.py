from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
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