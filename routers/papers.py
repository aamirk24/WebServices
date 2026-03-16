from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from crud.papers import (
    count_papers,
    get_paper,
    get_paper_authors,
    get_paper_references,
    get_papers,
    get_papers_citing_paper,
    get_ranked_papers,
)
from schemas.paper import (
    CitationPaperList,
    CitationPaperResponse,
    PaperAuthorList,
    PaperAuthorResponse,
    PaperList,
    PaperResponse,
    RankedPaperList,
    RankedPaperResponse,
)
from schemas.utils import build_links

router = APIRouter()


@router.get("", response_model=PaperList)
async def list_papers(
    request: Request,
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PaperList:
    skip = (page - 1) * size

    papers = await get_papers(
        db=db,
        category=category,
        search=search,
        skip=skip,
        limit=size,
    )

    total = await count_papers(
        db=db,
        category=category,
        search=search,
    )

    items: list[PaperResponse] = []
    for paper in papers:
        item = PaperResponse.model_validate(paper)
        item.links = build_links(paper.id, str(request.base_url))
        items.append(item)

    return PaperList(
        items=items,
        total=total,
        page=page,
        size=size,
    )

@router.get("/ranked", response_model=RankedPaperList)
async def get_ranked_papers_endpoint(
    request: Request,
    category: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> RankedPaperList:
    """
    Return top papers by PageRank score.

    Query params:
    - category: optional category/topic filter
    - limit: top N papers to return (default 20, max 100)
    """
    papers = await get_ranked_papers(
        db=db,
        category=category,
        limit=limit,
    )

    items: list[RankedPaperResponse] = []
    for idx, paper in enumerate(papers, start=1):
        base_item = PaperResponse.model_validate(paper)
        item = RankedPaperResponse(
            **base_item.model_dump(),
            rank=idx,
        )
        item.links = build_links(paper.id, str(request.base_url))
        items.append(item)

    return RankedPaperList(
        items=items,
        total=len(items),
        limit=limit,
        category=category,
    )
    

@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper_by_id(
    paper_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> PaperResponse:
    paper = await get_paper(db=db, paper_id=paper_id)

    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper with id '{paper_id}' was not found.",
        )

    response = PaperResponse.model_validate(paper)
    response.links = build_links(paper.id, str(request.base_url))
    return response


@router.get("/{paper_id}/citations", response_model=CitationPaperList)
async def get_paper_citations_endpoint(
    paper_id: uuid.UUID,
    request: Request,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> CitationPaperList:
    """
    Return both citation directions for a paper:

    - cited_by: papers that cite this paper
    - references: papers this paper cites
    """
    paper = await get_paper(db=db, paper_id=paper_id)
    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper with id '{paper_id}' was not found.",
        )

    incoming = await get_papers_citing_paper(db=db, paper_id=paper_id)
    outgoing = await get_paper_references(db=db, paper_id=paper_id)

    combined: list[CitationPaperResponse] = []

    for cited_by_paper in incoming:
        base_item = PaperResponse.model_validate(cited_by_paper)
        item = CitationPaperResponse(
            **base_item.model_dump(),
            direction="cited_by",
        )
        item.links = build_links(cited_by_paper.id, str(request.base_url))
        combined.append(item)

    for referenced_paper in outgoing:
        base_item = PaperResponse.model_validate(referenced_paper)
        item = CitationPaperResponse(
            **base_item.model_dump(),
            direction="references",
        )
        item.links = build_links(referenced_paper.id, str(request.base_url))
        combined.append(item)

    combined.sort(key=lambda item: (item.direction, item.title.lower()))

    total = len(combined)
    start = (page - 1) * size
    end = start + size
    paginated_items = combined[start:end]

    return CitationPaperList(
        items=paginated_items,
        total=total,
        page=page,
        size=size,
    )


@router.get("/{paper_id}/authors", response_model=PaperAuthorList)
async def get_paper_authors_endpoint(
    paper_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PaperAuthorList:
    """
    Return authors for a paper, including their position on the paper.
    """
    paper = await get_paper(db=db, paper_id=paper_id)
    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper with id '{paper_id}' was not found.",
        )

    author_links = await get_paper_authors(db=db, paper_id=paper_id)

    total = len(author_links)
    start = (page - 1) * size
    end = start + size
    paginated_links = author_links[start:end]

    items: list[PaperAuthorResponse] = []
    for link in paginated_links:
        if link.author is None:
            continue

        items.append(
            PaperAuthorResponse(
                id=link.author.id,
                name=link.author.name,
                position=link.position,
            )
        )

    return PaperAuthorList(
        items=items,
        total=total,
        page=page,
        size=size,
    )