from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from crud.authors import get_author_papers, get_author_with_stats, get_authors_with_stats
from schemas.author import AuthorDetailResponse, AuthorListItem, AuthorListResponse
from schemas.paper import PaperResponse
from schemas.utils import build_links

router = APIRouter()


@router.get("", response_model=AuthorListResponse)
async def list_authors(
    db: AsyncSession = Depends(get_db),
) -> AuthorListResponse:
    rows = await get_authors_with_stats(db)

    items = [
        AuthorListItem(
            id=author.id,
            name=author.name,
            paper_count=int(paper_count),
            avg_pagerank_score=float(avg_pagerank_score) if avg_pagerank_score is not None else None,
        )
        for author, paper_count, avg_pagerank_score in rows
    ]

    return AuthorListResponse(
        items=items,
        total=len(items),
    )


@router.get("/{author_id}", response_model=AuthorDetailResponse)
async def get_author_by_id(
    author_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthorDetailResponse:
    row = await get_author_with_stats(db, author_id)

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Author with id '{author_id}' was not found.",
        )

    author, paper_count, avg_pagerank_score = row
    papers = await get_author_papers(db, author_id)

    paper_items: list[PaperResponse] = []
    for paper in papers:
        item = PaperResponse.model_validate(paper)
        item.links = build_links(paper.id, str(request.base_url))
        paper_items.append(item)

    return AuthorDetailResponse(
        id=author.id,
        name=author.name,
        paper_count=int(paper_count),
        avg_pagerank_score=float(avg_pagerank_score) if avg_pagerank_score is not None else None,
        papers=paper_items,
    )